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
 * and for two fingers (on a multitouch screen, which reports each finger in a slot):
 *
 *   two fingers that move     the mouse wheel, up and down or sideways (whichever way they
 *                             first moved farther), so the page follows the fingers wherever
 *                             the wheel scrolls. It lasts until the last finger is lifted
 *
 * Programs then see a mouse, not a touchscreen: no pinch to zoom in the web browser.
 * Desktop Settings can turn it off (long_press=no in desktop.conf); /usr/lib/pivuan/long-press
 * starts and stops it with the session.
 *
 *   pivuan-long-press [--delay MS] [--distance PERCENT] [--scroll PERCENT] [--session-pid PID]
 *                     [--device PATH]
 *
 *   --delay MS          how long a finger must stay still to be a right click (default 600)
 *   --distance PERCENT  how far a finger may move and still be a tap or a long press, in
 *                       percent of the screen's width (default 1.5: about 20 pixels on a
 *                       1280-pixel screen)
 *   --scroll PERCENT    how far two fingers move for one step of the wheel, in percent of the
 *                       screen's height (default 5: 40 pixels on an 800-pixel screen)
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

/* The device's axes: the single-touch ones if it has them, else slot 0's multitouch ones.
 * slots: how many fingers it reports apart (multitouch protocol B), 0 if it does not. */
struct axes {
    int x_code, y_code;
    struct input_absinfo x, y;
    int slots, first_slot;
};

/* The fingers this program follows; a screen with more slots has the rest ignored. */
#define MAX_SLOTS 10

/* One finger of a multitouch screen: its tracking id (-1: no finger) and where it is. */
struct slot {
    int id, x, y;
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
    /* The fingers apart, for two-finger scrolling: slots with a tracking id and a position. */
    axes->slots = 0;
    axes->first_slot = 0;
    struct input_absinfo slot;
    if (test_bit(abs, ABS_MT_SLOT) && test_bit(abs, ABS_MT_TRACKING_ID)
        && test_bit(abs, ABS_MT_POSITION_X) && test_bit(abs, ABS_MT_POSITION_Y)
        && ioctl(fd, EVIOCGABS(ABS_MT_SLOT), &slot) == 0 && slot.maximum >= 1) {
        axes->slots = slot.maximum + 1 < MAX_SLOTS ? slot.maximum + 1 : MAX_SLOTS;
        axes->first_slot = slot.value;
    }
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

/* The pointer X sees instead: absolute X and Y with the touchscreen's ranges, the left
 * and right buttons, and a wheel both ways (with the high-resolution steps, 120 to a click,
 * so it scrolls smoothly where programs can). No INPUT_PROP_DIRECT and no BTN_TOUCH, so libinput
 * takes it for an absolute pointer (as a virtual machine's tablet), which X maps to the whole
 * screen. */
static int create_pointer(const struct axes *axes, const char *touch_name)
{
    int fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0)
        die("/dev/uinput: %s", strerror(errno));

    if (ioctl(fd, UI_SET_EVBIT, EV_KEY) < 0 || ioctl(fd, UI_SET_KEYBIT, BTN_LEFT) < 0
        || ioctl(fd, UI_SET_KEYBIT, BTN_RIGHT) < 0 || ioctl(fd, UI_SET_EVBIT, EV_ABS) < 0
        || ioctl(fd, UI_SET_ABSBIT, ABS_X) < 0 || ioctl(fd, UI_SET_ABSBIT, ABS_Y) < 0
        || ioctl(fd, UI_SET_EVBIT, EV_REL) < 0 || ioctl(fd, UI_SET_RELBIT, REL_WHEEL) < 0
        || ioctl(fd, UI_SET_RELBIT, REL_HWHEEL) < 0
        || ioctl(fd, UI_SET_RELBIT, REL_WHEEL_HI_RES) < 0
        || ioctl(fd, UI_SET_RELBIT, REL_HWHEEL_HI_RES) < 0
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

/* Two-finger scrolling: how many fingers there were and their middle when last looked at, the
 * wheel they turn (0 until they have moved farther than a tap may, then REL_WHEEL or
 * REL_HWHEEL, for the rest of the touch), the part of a high-resolution step not sent yet, and
 * the high-resolution steps sent since the last whole click. */
struct scroll {
    int fingers;
    long long x, y;
    unsigned short axis;
    double rest;
    int clicks;
};

/* How many fingers are down, and their middle. */
static int fingers_middle(const struct slot *slots, int count, long long *x, long long *y)
{
    long long sum_x = 0, sum_y = 0;
    int n = 0;
    for (int i = 0; i < count; i++) {
        if (slots[i].id < 0)
            continue;
        sum_x += slots[i].x;
        sum_y += slots[i].y;
        n++;
    }
    if (n > 0) {
        *x = sum_x / n;
        *y = sum_y / n;
    }
    return n;
}

/* Turns the wheel by AMOUNT high-resolution steps: the high-resolution event for programs that
 * scroll smoothly, and a click each time 120 have added up, as a mouse's wheel sends both. */
static void turn_wheel(int fd, struct scroll *s, int amount)
{
    emit(fd, EV_REL, s->axis == REL_WHEEL ? REL_WHEEL_HI_RES : REL_HWHEEL_HI_RES, amount);
    s->clicks += amount;
    int whole = s->clicks / 120;
    if (whole != 0) {
        emit(fd, EV_REL, s->axis, whole);
        s->clicks -= whole * 120;
    }
    emit(fd, EV_SYN, SYN_REPORT, 0);
}

/* Starts two-finger scrolling from where the fingers are. */
static void start_scroll(struct scroll *s, const struct slot *slots, int count)
{
    memset(s, 0, sizeof(*s));
    s->fingers = fingers_middle(slots, count, &s->x, &s->y);
}

/* The wheel follows the fingers' middle. STEP_X and STEP_Y: how far they move for one click,
 * in the device's units; LIMIT2: the square of how far they move before the wheel turns. */
static void follow_fingers(int fd, struct scroll *s, const struct slot *slots, int count,
                           double step_x, double step_y, long long limit2)
{
    long long x = s->x, y = s->y;
    int n = fingers_middle(slots, count, &x, &y);
    if (n != s->fingers) {
        /* A finger came or went, so the middle jumped: go on from the new one. */
        s->fingers = n;
        s->x = x;
        s->y = y;
        return;
    }
    if (n < 2)
        return;  /* one finger left: nothing until it is lifted too */
    long long dx = x - s->x, dy = y - s->y;
    if (s->axis == 0) {
        if (dx * dx + dy * dy <= limit2)
            return;
        s->axis = llabs(dy) >= llabs(dx) ? REL_WHEEL : REL_HWHEEL;
    }
    /* The page follows the fingers: down turns the wheel up (positive), which shows what is
     * above; right turns it left (negative), which shows what is to the left. */
    double amount = s->axis == REL_WHEEL ? (double)dy / step_y * 120.0
                                         : -(double)dx / step_x * 120.0;
    amount += s->rest;
    int whole = (int)amount;
    s->rest = amount - whole;
    s->x = x;
    s->y = y;
    if (whole != 0)
        turn_wheel(fd, s, whole);
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
    DRAGGING,  /* the left button is down and the pointer follows */
    SCROLLING  /* two fingers came down before any button: the wheel follows them */
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
    double scroll_percent = 5;
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
        } else if (i + 1 < argc && strcmp(argv[i], "--scroll") == 0) {
            char *end;
            scroll_percent = strtod(argv[++i], &end);
            if (*end != '\0' || scroll_percent < 0.5 || scroll_percent > 50)
                die("--scroll must be a number from 0.5 to 50");
        } else if (i + 1 < argc && strcmp(argv[i], "--session-pid") == 0) {
            session_pid = parse_int(argv[++i], "--session-pid", 1, INT_MAX);
        } else if (i + 1 < argc && strcmp(argv[i], "--device") == 0) {
            device = argv[++i];
        } else {
            fprintf(stderr, "usage: pivuan-long-press [--delay MS] [--distance PERCENT] "
                            "[--scroll PERCENT] [--session-pid PID] [--device PATH]\n");
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
    /* How far two fingers move for one click of the wheel, in the device's units. */
    const double step_x = range * scroll_percent / 100.0;
    const double step_y = ((double)axes.y.maximum - axes.y.minimum) * scroll_percent / 100.0;

    enum state state = IDLE;
    int x = axes.x.minimum, y = axes.y.minimum;  /* where the finger is */
    int touch_x = x, touch_y = y;                /* where it touched */
    int finger = 0, finger_was = 0;
    int moved = 0;
    long long pressed_at = 0, drag_at = 0, session_checked = now_ms();
    /* The fingers apart (multitouch screens only), and two-finger scrolling. */
    struct slot slots[MAX_SLOTS];
    for (int i = 0; i < MAX_SLOTS; i++)
        slots[i] = (struct slot){.id = -1};
    int slot = axes.first_slot;
    struct scroll scroll = {0};

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
                /* Each finger apart, besides the single-touch axes below. */
                if (ev.type == EV_ABS && axes.slots > 0) {
                    if (ev.code == ABS_MT_SLOT)
                        slot = ev.value;
                    else if (slot >= 0 && slot < axes.slots && ev.code == ABS_MT_TRACKING_ID)
                        slots[slot].id = ev.value;
                    else if (slot >= 0 && slot < axes.slots && ev.code == ABS_MT_POSITION_X)
                        slots[slot].x = ev.value;
                    else if (slot >= 0 && slot < axes.slots && ev.code == ABS_MT_POSITION_Y)
                        slots[slot].y = ev.value;
                }
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
                    long long mid_x, mid_y;
                    int fingers = fingers_middle(slots, axes.slots, &mid_x, &mid_y);
                    if (finger && !finger_was) {
                        /* Touched: the pointer goes there, the buttons wait. */
                        touch_x = x;
                        touch_y = y;
                        pressed_at = now_ms();
                        move_to(pointer, x, y);
                        state = PENDING;
                    }
                    if (state == SCROLLING) {
                        /* Two fingers: the wheel follows them until the last one lifts. The
                         * wheel turns what is under the pointer, where the first finger
                         * touched. */
                        if (finger)
                            follow_fingers(pointer, &scroll, slots, axes.slots, step_x, step_y,
                                           limit2);
                        else
                            state = IDLE;
                    } else if (state == PENDING && fingers >= 2) {
                        /* A second finger before any button: scrolling, not a click. */
                        start_scroll(&scroll, slots, axes.slots);
                        state = SCROLLING;
                    } else if (finger && finger_was && moved && state == PENDING) {
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
                    /* Events were lost: end any touch cleanly. Fingers still down count again
                     * only once lifted and put down. */
                    if (state == STARTING || state == DRAGGING)
                        button(pointer, BTN_LEFT, 0);
                    state = IDLE;
                    finger = finger_was = 0;
                    for (int i = 0; i < MAX_SLOTS; i++)
                        slots[i].id = -1;
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
