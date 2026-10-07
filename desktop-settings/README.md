# Desktop Settings (Pivuan Audio)

The settings window of the Pivuan Audio desktop (JWM), System → Desktop Settings in the
Pivuan menu. It sets:

- the desktop background: one of the Pivuan backgrounds (black by default) or any picture;
- program icons on the panel, in order, all drawn at the same size;
- the panel's size and color (by default the grey of the Pivuan logo, #959597), the icons'
  size, and hiding the panel until the mouse reaches the bottom edge;
- the on-screen keyboard button: automatic (with a touchscreen), always or never;
- icons on the desktop (on by default): the program shortcuts Windows installers make and the
  files in the Desktop folder, drawn by pcmanfm through `/usr/lib/pivuan/desktop-icons`.

**Apply** is highlighted only when something differs from what is saved, and goes back to
normal once it is applied. Applying saves `~/.config/pivuan/desktop.conf` and the panel's
icons (`~/.config/pivuan/panel-icons/`) and restarts JWM; open windows stay.

JWM reads the settings through `/usr/lib/pivuan/jwm-desktop`, part of Pivuan Audio in
[rations/configng](https://github.com/rations/configng) (`tools/modules/desktops/branding/jwm/`),
which installs this package. The settings file's format and the defaults (black background,
panel #959597 and 30 pixels, icons 22, desktop icons on) are in both: change them together.

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
