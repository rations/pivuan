# Screenshot (Pivuan Audio)

Screenshots on the Pivuan Audio desktop (JWM), taken with `scrot`:

| Key | Takes | Saved as |
|---|---|---|
| Print | the whole screen | `~/Pictures/screenshot_<date>_<time>.png` |
| Alt+Print | an area you drag out with the mouse | `~/Pictures/area_<date>_<time>.png` |
| Super+Print | a window you click, with its frame | `~/Pictures/window_<date>_<time>.png` |

The keys run `pivuan-screenshot screen`, `area` and `window`, which save at once without
loading GTK. They are bound in Pivuan Audio's `pivuan.jwmrc`, in
[rations/configng](https://github.com/rations/configng)
(`tools/modules/desktops/branding/jwm/`), which installs this package.

**Accessories → Screenshot** in the Pivuan menu (`pivuan-screenshot` with no arguments) opens a
small window with the same three, and a delay of up to 30 seconds (time to open a menu first;
for a window or an area it starts after the click or the drag). After the shot it shows a
preview, the name (the same as the keys would give) and the folder (`~/Pictures` at first, or
any other). **Save** adds `.png` if the name has none and asks before replacing a file;
**Discard** throws the shot away. Both go back to the first page. Escape during a click or a
drag takes no shot.

Starting it again brings the open window to the front. The shot waits in
`~/.cache/pivuan/screenshot.png` until it is saved or discarded.

Two things about scrot:

- An area without a delay is dragged over a frozen picture of the screen (`--freeze`), so a
  menu or a tooltip stays in it. scrot holds the X server meanwhile: programs that drive the
  screen through XTest wait until the drag ends, but the mouse and keyboard work.
- With a delay the screen is not frozen (the delay would come after the picture), and the
  outline of the area is a window of its own (`--line mode=edge`): scrot's usual outline is
  drawn on the desktop, where the compositor (picom) leaves it, and it would be in the shot.

The window gives the focus to Save, not the name: a text box with the focus brings up the
on-screen keyboard, which would cover the preview. Enter saves; a click on the name changes it.

## Build

Needs `python3` and `make`, and `dpkg-deb` for the package. The test needs GTK 3 for Python
(`python3-gi`, `gir1.2-gtk-3.0`) and an X display; it never shows the window and takes no
real screenshot.

```sh
cd pivuan/screenshot
make test   # scrot's options, and the window's pages with a made-up shot
make deb    # build/pivuan-screenshot_<version>-pivuan<rev>_all.deb
```

## Package

`pivuan-screenshot` (architecture all) puts the program in `/usr/bin` and its menu entry in
`/usr/share/applications`; it depends on `scrot`. The version is in [config.mk](config.mk); a
published version can never be reused, so bump `VERSION` or `DEB_REVISION` for each release.
The workflow [screenshot.yml](../.github/workflows/screenshot.yml) builds and checks it (in
Debian trixie, under Xvfb) and, run with "publish", adds it to the Pivuan apt repository.

License: GPL-3 ([packaging/deb/copyright](packaging/deb/copyright)).
