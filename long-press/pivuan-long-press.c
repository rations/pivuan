/*
 * pivuan-long-press: long press for right click on a touchscreen (Pivuan Audio).
 *
 * X's touchscreen drivers have no long press: libinput has none, and evdev's "third button
 * emulation" works on button events, which a multitouch screen does not send. So this program
 * takes the touchscreen for itself (EVIOCGRAB) and gives X a pointer of its own instead (uinput,
 * an absolute pointer like a virtual machine's tablet), with these rules for one finger:
 *
 *   a tap                     a left click where the finger touched
 *   a finger that moves       a left-button drag from where it touched (a dial, a window
 *                             border, a selection): the button goes down once the finger has
 *                             moved farther than the distance below, however long it was held
 *                             first, so touching, holding and then dragging is a drag
 *   a finger held still       a right click where it touched, when it is lifted after at least
 *                             the delay below
 *
 * Programs then see a mouse, not a touchscreen: no two-finger gestures (the web browser's zoom
 * and finger scrolling). Desktop Settings can turn it off (long_press=no in desktop.conf);
 * /usr/lib/pivuan/long-press starts and stops it with the session.
 *
 *   pivuan-long-press [--delay MS] [--distance PERCENT] [--session-pid PID] [--device PATH]
 *
 *   --delay MS          how long a finger must stay still to be a right click (default 600)
 *   --distance PERCENT  how far a finger may move and still be a tap or a long press, in
 *                       percent of the screen's width (default 1.5: about 20 pixels on a
 *                       1280-pixel screen)
 *   --session-pid PID   exit when this process (the window manager) has ended, so the login
 *                       screen gets the touchscreen back
 *   --device PATH       the touchscreen (default: the first input device with
 *                       INPUT_PROP_DIRECT, absolute X and Y, and BTN_TOUCH)
 *
 * It needs to read /dev/input/event* (the input group) and write /dev/uinput (the input
 * group too, by this package's udev rule).
 */
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <linux/input.h>
#include <linux/uinput.h>
#include <poll.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

#define BITS_PER_LONG (sizeof(long) * CHAR_BIT)
#define NLONGS(n) (((n) + BITS_PER_LONG - 1) / BITS_PER_LONG)

static volatile sig_atomic_t stop_requested;

static void on_signal(int sig)
{
    (void)sig;
    stop_requested = 1;
}

static void die(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    fputs("pivuan-long-press: ", stderr);
    vfprintf(stderr, fmt, ap);
    fputc('\n', stderr);
    va_end(ap);
    exit(1);
}

static int test_bit(const unsigned long *bits, unsigned bit)
{
    return (bits[bit / BITS_PER_LONG] >> (bit % BITS_PER_LONG)) & 1UL;
}

static long long now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long long)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
}

/* The device's axes: the single-touch ones if it has them, else slot 0's multitouch ones. */
struct axes {
    int x_code, y_code;
    struct input_absinfo x, y;
};

/* A touchscreen: INPUT_PROP_DIRECT, BTN_TOUCH, and absolute X and Y (single-touch or
 * multitouch). Fills in the axes it uses. */
static int is_touchscreen(int fd, struct axes *axes)
{
    unsigned long props[NLONGS(INPUT_PROP_CNT)] = {0};
    unsigned long keys[NLONGS(KEY_CNT)] = {0};
    unsigned long abs[NLONGS(ABS_CNT)] = {0};

    if (ioctl(fd, EVIOCGPROP(sizeof(props)), props) < 0
        || ioctl(fd, EVIOCGBIT(EV_KEY, sizeof(keys)), keys) < 0
        || ioctl(fd, EVIOCGBIT(EV_ABS, sizeof(abs)), abs) < 0)
        return 0;
    if (!test_bit(props, INPUT_PROP_DIRECT) || !test_bit(keys, BTN_TOUCH))
        return 0;
    if (test_bit(abs, ABS_X) && test_bit(abs, ABS_Y)) {
        axes->x_code = ABS_X;
        axes->y_code = ABS_Y;
    } else if (test_bit(abs, ABS_MT_POSITION_X) && test_bit(abs, ABS_MT_POSITION_Y)) {
        axes->x_code = ABS_MT_POSITION_X;
        axes->y_code = ABS_MT_POSITION_Y;
    } else {
        return 0;
    }
    if (ioctl(fd, EVIOCGABS(axes->x_code), &axes->x) < 0
        || ioctl(fd, EVIOCGABS(axes->y_code), &axes->y) < 0
        || axes->x.maximum <= axes->x.minimum || axes->y.maximum <= axes->y.minimum)
        return 0;
    return 1;
}

/* Opens the touchscreen: the one given, or the first one found. */
static int open_touchscreen(const char *path, struct axes *axes, char *name, size_t name_size)
{
    if (path) {
        int fd = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
        if (fd < 0)
            die("%s: %s", path, strerror(errno));
        if (!is_touchscreen(fd, axes))
            die("%s is not a touchscreen", path);
        if (ioctl(fd, EVIOCGNAME(name_size), name) < 0)
            snprintf(name, name_size, "touchscreen");
        return fd;
    }

    DIR *dir = opendir("/dev/input");
    if (!dir)
        die("/dev/input: %s", strerror(errno));
    struct dirent *entry;
    int found = -1;
    while (found < 0 && (entry = readdir(dir)) != NULL) {
        if (strncmp(entry->d_name, "event", 5) != 0)
            continue;
        char device[PATH_MAX];
        snprintf(device, sizeof(device), "/dev/input/%s", entry->d_name);
        int fd = open(device, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
        if (fd < 0)
            continue;
        if (is_touchscreen(fd, axes)) {
            if (ioctl(fd, EVIOCGNAME(name_size), name) < 0)
                snprintf(name, name_size, "touchscreen");
            found = fd;
        } else {
            close(fd);
        }
    }
    closedir(dir);
    return found;
}

/* The pointer X sees instead: absolute X and Y with the touchscreen's ranges, and the left
 * and right buttons. No INPUT_PROP_DIRECT and no BTN_TOUCH, so libinput takes it for an
 * absolute pointer (as a virtual machine's tablet), which X maps to the whole screen. */
static int create_pointer(const struct axes *axes, const char *touch_name)
{
    int fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0)
        die("/dev/uinput: %s", strerror(errno));

    if (ioctl(fd, UI_SET_EVBIT, EV_KEY) < 0 || ioctl(fd, UI_SET_KEYBIT, BTN_LEFT) < 0
        || ioctl(fd, UI_SET_KEYBIT, BTN_RIGHT) < 0 || ioctl(fd, UI_SET_EVBIT, EV_ABS) < 0
        || ioctl(fd, UI_SET_ABSBIT, ABS_X) < 0 || ioctl(fd, UI_SET_ABSBIT, ABS_Y) < 0
        || ioctl(fd, UI_SET_EVBIT, EV_SYN) < 0)
        die("uinput: %s", strerror(errno));

    struct uinput_abs_setup abs = {0};
    abs.code = ABS_X;
    abs.absinfo = axes->x;
    abs.absinfo.value = axes->x.minimum;
    if (ioctl(fd, UI_ABS_SETUP, &abs) < 0)
        die("uinput: %s", strerror(errno));
    abs.code = ABS_Y;
    abs.absinfo = axes->y;
    abs.absinfo.value = axes->y.minimum;
    if (ioctl(fd, UI_ABS_SETUP, &abs) < 0)
        die("uinput: %s", strerror(errno));

    struct uinput_setup setup = {0};
    setup.id.bustype = BUS_VIRTUAL;
    setup.id.vendor = 0x1d6b;  /* Linux Foundation, as for other virtual devices */
    setup.id.product = 0x0104;
    setup.id.version = 1;
    snprintf(setup.name, UINPUT_MAX_NAME_SIZE, "Pivuan long press (%s)", touch_name);
    if (ioctl(fd, UI_DEV_SETUP, &setup) < 0 || ioctl(fd, UI_DEV_CREATE) < 0)
        die("uinput: %s", strerror(errno));
    return fd;
}

static void emit(int fd, unsigned short type, unsigned short code, int value)
{
    struct input_event ev = {0};
    ev.type = type;
    ev.code = code;
    ev.value = value;
    /* A full uinput buffer drops the event; nothing better to do with it. */
    if (write(fd, &ev, sizeof(ev)) < 0 && errno != EAGAIN)
        stop_requested = 1;
}

static void move_to(int fd, int x, int y)
{
    emit(fd, EV_ABS, ABS_X, x);
    emit(fd, EV_ABS, ABS_Y, y);
    emit(fd, EV_SYN, SYN_REPORT, 0);
}

static void button(int fd, unsigned short code, int down)
{
    emit(fd, EV_KEY, code, down);
    emit(fd, EV_SYN, SYN_REPORT, 0);
}

static void click(int fd, unsigned short code)
{
    button(fd, code, 1);
    button(fd, code, 0);
}

/* How long the left button is down before the pointer starts to follow a drag. The finger has
 * already moved when the button goes down, so without a pause the first motion comes at once,
 * which a mouse never does: JWM then misses the start of a resize from a window border (it
 * takes the pointer for the resize only after the press, and a motion before that ends it; on a
 * Pi 5, 30 ms was too short and 50 ms enough). */
#define DRAG_PAUSE_MS 150

enum state {
    IDLE,      /* no finger */
    PENDING,   /* finger down, still near where it touched: a tap or a long press so far */
    STARTING,  /* moved: the left button is down where it touched, for DRAG_PAUSE_MS */
    DRAGGING   /* the left button is down and the pointer follows */
};

static int parse_int(const char *arg, const char *what, int low, int high)
{
    char *end;
    long value = strtol(arg, &end, 10);
    if (*arg == '\0' || *end != '\0' || value < low || value > high)
        die("%s must be a number from %d to %d", what, low, high);
    return (int)value;
}

int main(int argc, char **argv)
{
    int delay_ms = 600;
    double distance_percent = 1.5;
    pid_t session_pid = 0;
    const char *device = NULL;

    for (int i = 1; i < argc; i++) {
        if (i + 1 < argc && strcmp(argv[i], "--delay") == 0) {
            delay_ms = parse_int(argv[++i], "--delay", 100, 5000);
        } else if (i + 1 < argc && strcmp(argv[i], "--distance") == 0) {
            char *end;
            distance_percent = strtod(argv[++i], &end);
            if (*end != '\0' || distance_percent < 0.1 || distance_percent > 20)
                die("--distance must be a number from 0.1 to 20");
        } else if (i + 1 < argc && strcmp(argv[i], "--session-pid") == 0) {
            session_pid = parse_int(argv[++i], "--session-pid", 1, INT_MAX);
        } else if (i + 1 < argc && strcmp(argv[i], "--device") == 0) {
            device = argv[++i];
        } else {
            fprintf(stderr, "usage: pivuan-long-press [--delay MS] [--distance PERCENT] "
                            "[--session-pid PID] [--device PATH]\n");
            return 2;
        }
    }

    struct axes axes;
    char name[256] = "";
    int touch = open_touchscreen(device, &axes, name, sizeof(name));
    if (touch < 0)
        die("no touchscreen found");

    struct sigaction sa = {0};
    sa.sa_handler = on_signal;
    sigaction(SIGTERM, &sa, NULL);
    sigaction(SIGINT, &sa, NULL);
    sigaction(SIGHUP, &sa, NULL);

    int pointer = create_pointer(&axes, name);
    if (ioctl(touch, EVIOCGRAB, (void *)1) < 0)
        die("%s: cannot take the touchscreen: %s", name, strerror(errno));

    /* How far a finger may move and still be a tap or a long press, in the device's units
     * (the X axis's scale for both, as screens have square pixels). */
    const double range = (double)axes.x.maximum - axes.x.minimum;
    const long long limit = (long long)(range * distance_percent / 100.0 + 0.5);
    const long long limit2 = limit * limit;

    enum state state = IDLE;
    int x = axes.x.minimum, y = axes.y.minimum;  /* where the finger is */
    int touch_x = x, touch_y = y;                /* where it touched */
    int finger = 0, finger_was = 0;
    int moved = 0;
    long long pressed_at = 0, drag_at = 0, session_checked = now_ms();

    while (!stop_requested) {
        struct pollfd pfd = {.fd = touch, .events = POLLIN};
        int timeout = 1000;
        if (state == STARTING) {
            long long left = drag_at + DRAG_PAUSE_MS - now_ms();
            timeout = left > 0 ? (int)left : 0;
        }
        int ready = poll(&pfd, 1, timeout);
        if (ready < 0 && errno != EINTR)
            break;

        if (ready > 0) {
            if (pfd.revents & (POLLERR | POLLHUP | POLLNVAL))
                break;  /* unplugged */
            struct input_event ev;
            ssize_t got;
            while ((got = read(touch, &ev, sizeof(ev))) == (ssize_t)sizeof(ev)) {
                if (ev.type == EV_KEY && ev.code == BTN_TOUCH) {
                    finger = ev.value != 0;
                } else if (ev.type == EV_ABS && ev.code == axes.x_code) {
                    x = ev.value;
                    moved = 1;
                } else if (ev.type == EV_ABS && ev.code == axes.y_code) {
                    y = ev.value;
                    moved = 1;
                } else if (ev.type == EV_SYN && ev.code == SYN_REPORT) {
                    /* One complete report: act on it. */
                    if (finger && !finger_was) {
                        /* Touched: the pointer goes there, the buttons wait. */
                        touch_x = x;
                        touch_y = y;
                        pressed_at = now_ms();
                        move_to(pointer, x, y);
                        state = PENDING;
                    } else if (finger && moved && state == PENDING) {
                        long long dx = x - touch_x, dy = y - touch_y;
                        if (dx * dx + dy * dy > limit2) {
                            /* A drag: from where the finger touched; the pointer follows
                             * after DRAG_PAUSE_MS. */
                            button(pointer, BTN_LEFT, 1);
                            drag_at = now_ms();
                            state = STARTING;
                        }
                    } else if (finger && moved && state == DRAGGING) {
                        move_to(pointer, x, y);
                    } else if (!finger && finger_was) {
                        /* Lifted without moving: a long press or a tap. */
                        if (state == PENDING && now_ms() - pressed_at >= delay_ms) {
                            click(pointer, BTN_RIGHT);
                        } else if (state == PENDING) {
                            click(pointer, BTN_LEFT);
                        } else if (state == STARTING) {
                            /* A quick flick: finish the pause, then drag to where it lifted. */
                            long long left = drag_at + DRAG_PAUSE_MS - now_ms();
                            if (left > 0)
                                usleep((useconds_t)(left * 1000));
                            move_to(pointer, x, y);
                            button(pointer, BTN_LEFT, 0);
                        } else if (state == DRAGGING) {
                            button(pointer, BTN_LEFT, 0);
                        }
                        state = IDLE;
                    }
                    finger_was = finger;
                    moved = 0;
                } else if (ev.type == EV_SYN && ev.code == SYN_DROPPED) {
                    /* Events were lost: end any touch cleanly. */
                    if (state == STARTING || state == DRAGGING)
                        button(pointer, BTN_LEFT, 0);
                    state = IDLE;
                    finger = finger_was = 0;
                }
            }
            if (got < 0 && errno != EAGAIN && errno != EINTR)
                break;  /* unplugged */
        }

        if (state == STARTING && now_ms() - drag_at >= DRAG_PAUSE_MS) {
            /* The pause is over: the pointer catches up with the finger. */
            move_to(pointer, x, y);
            state = DRAGGING;
        }

        if (session_pid && now_ms() - session_checked >= 1000) {
            session_checked = now_ms();
            if (kill(session_pid, 0) < 0 && errno == ESRCH)
                break;
        }
    }

    if (state == STARTING || state == DRAGGING)
        button(pointer, BTN_LEFT, 0);
    ioctl(touch, EVIOCGRAB, (void *)0);
    ioctl(pointer, UI_DEV_DESTROY);
    close(pointer);
    close(touch);
    return 0;
}
