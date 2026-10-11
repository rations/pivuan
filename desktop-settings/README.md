# Desktop Settings (Pivuan Audio)

The settings window of the Pivuan Audio desktop (JWM), Settings → Desktop Settings in the
Pivuan menu. Its tabs (Background, Screen, Panel, Panel Icons) fit small screens, down to
7-inch ones at 800x480; a tab longer than the screen scrolls. It sets:

- the desktop background: one of the Pivuan backgrounds (black by default) or any picture;
- program icons on the panel, in order, all drawn at the same size;
- the panel's size and color (by default the grey of the Pivuan logo, #959597), the icons'
  size, and hiding the panel until the mouse reaches the bottom edge. With a touchscreen the
  panel is 48 pixels and its icons 32 by default;
- the on-screen keyboard button: automatic (with a touchscreen), always or never;
- icons on the desktop (on by default): the program shortcuts Windows installers make and the
  files in the Desktop folder, drawn by pcmanfm through `/usr/lib/pivuan/desktop-icons`;
- turning the screen off after 10 minutes without use (off by default: the screen stays on).
  `/usr/lib/pivuan/jwm-desktop` sets it with `xset` each time JWM starts or restarts;
- the screen's brightness, through `/usr/lib/pivuan/brightness` (the screen's backlight, else
  the monitor's own setting over DDC/CI, else software dimming). The slider changes it at once;
  Close without Apply puts back the saved brightness. A brightness button on the panel (on by
  default) opens just the slider: `pivuan-desktop-settings --brightness`;
- long press for right click on a touchscreen (on by default; shown only with a touchscreen),
  through the `pivuan-long-press` package ([long-press/](../long-press/)).

`pivuan-desktop-settings --volume` is the slider the panel's volume button opens (the default
output's volume and mute, and a button for Volume Control). Run again, `--brightness` and
`--volume` close their slider.

**Apply** is highlighted only when something differs from what is saved, and goes back to
normal once it is applied. Applying saves `~/.config/pivuan/desktop.conf` and the panel's
icons (`~/.config/pivuan/panel-icons/`) and restarts JWM; open windows stay.

JWM reads the settings through `/usr/lib/pivuan/jwm-desktop`, part of Pivuan Audio in
[rations/configng](https://github.com/rations/configng) (`tools/modules/desktops/branding/jwm/`),
which installs this package. The settings file's format and the defaults (black background,
panel #959597 and 30 pixels, or 48 with a touchscreen, icons 22, or 32, desktop icons on, screen
always on, brightness button on, long press on) are in both: change them together.

## Build

Needs `python3` and `make`, and `dpkg-deb` for the package. The test needs GTK 3 for Python
(`python3-gi`, `gir1.2-gtk-3.0`) and an X display; it never shows the window.

```sh
cd pivuan/desktop-settings
make test   # the window: Apply highlighted only while there is something to apply
make deb    # build/pivuan-desktop-settings_<version>-pivuan<rev>_all.deb
```

Without a window: `pivuan-desktop-settings --check` prints the saved settings and
`--render-icons` makes the panel's icons from them.

## Package

`pivuan-desktop-settings` (architecture all) puts the program in `/usr/bin`. The version is in
[config.mk](config.mk); a published version can never be reused, so bump `VERSION` or
`DEB_REVISION` for each release. The workflow
[desktop-settings.yml](../.github/workflows/desktop-settings.yml) builds and checks it (in
Debian trixie, under Xvfb) and, run with "publish", adds it to the Pivuan apt repository.

License: GPL-3 ([packaging/deb/copyright](packaging/deb/copyright)).
