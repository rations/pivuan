# Long press (Pivuan Audio)

Right click on a touchscreen for the Pivuan Audio desktop (JWM). X's touchscreen drivers have
no long press: libinput offers none, and evdev's "third button emulation" never sees a button
from a multitouch screen. So `pivuan-long-press` takes the touchscreen for itself and gives X a
pointer of its own (`/dev/uinput`, an absolute pointer like a virtual machine's tablet):

- a **tap** is a left click where the finger touched;
- a finger that **moves** drags with the left button from where it touched: a dial, a
  selection, a window border or corner (resize);
- a finger **held still and then lifted** after 0.6 seconds is a **right click**: the menus
  of JackDAW, jack-graph (disconnect a cable), pcmanfm and the desktop;
- **two fingers that move** turn the mouse wheel, so the page or list under the first finger
  follows them, up and down or sideways (whichever way they first moved farther): it
  scrolls wherever the mouse wheel does (the web browser, GTK and Qt lists). The wheel has
  high-resolution steps, so programs that can scroll smoothly do.

Programs then see a mouse, not a touchscreen, so pinch to zoom in the web browser is gone
while it runs.

`/usr/lib/pivuan/long-press start | stop | restart` starts and stops it with the session:
`/usr/lib/pivuan/jwm-desktop` (Pivuan Audio in
[rations/configng](https://github.com/rations/configng)) starts it at login when a
touchscreen is attached, and it ends with JWM, so the login screen gets the touchscreen back.
Desktop Settings turns it off (Screen tab, "Long press for right click": `long_press=no` in
`~/.config/pivuan/desktop.conf`).

```
pivuan-long-press [--delay MS] [--distance PERCENT] [--scroll PERCENT] [--session-pid PID]
                  [--device PATH]
```

## Two details that were measured

- **A drag waits 150 ms before the pointer follows.** The left button goes down only once
  the finger has moved, so without a pause the first motion arrives with the press, which a
  mouse never does. JWM takes the pointer for a resize after the press, and a motion before
  that ends it: on a Pi 5, 30 ms between press and motion lost the resize every time and
  50 ms never did.
- **The right click comes on lifting, not after the delay.** A timer-based right click made
  "touch a border, hold, then drag" open JWM's window menu instead of resizing.

## Build

Needs a C compiler and `make`, and `dpkg-deb` for the package.

```sh
cd pivuan/long-press
make        # build/pivuan-long-press
make check  # it starts, and the control script is valid sh
make deb    # build/pivuan-long-press_<version>-pivuan<rev>_<arch>.deb
```

## Package

`pivuan-long-press` puts the program in `/usr/bin`, the control script in `/usr/lib/pivuan`,
a udev rule giving the `input` group `/dev/uinput`, and `uinput` in
`/usr/lib/modules-load.d`. The version is in [config.mk](config.mk); a published version can
never be reused, so bump `VERSION` or `DEB_REVISION` for each release. The workflow
[long-press.yml](../.github/workflows/long-press.yml) builds it for arm64 (in Debian trixie,
on GitHub's arm64 runner) and, run with "publish", adds it to the Pivuan apt repository. The
compiler stays on the build machine.

License: GPL-3 ([packaging/deb/copyright](packaging/deb/copyright)).
