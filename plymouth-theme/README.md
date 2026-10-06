# Pivuan boot splash

The plymouth theme Pivuan shows while it starts and shuts down: the Pivuan logo on black. At
boot a band of light sweeps over the logo and leaves it dim, the logo brightens, then sparks of
electricity run along its three circuit traces (the top one rises out of the "v") and light up
the trace and its ring when they arrive, until the boot is done. There is no spinner or
progress bar. At shutdown and reboot the logo is shown straight away, with the sparks.

![The boot splash](../pivuan-logo.gif)

It uses plymouth's `script` module ([theme/pivuan.script](theme/pivuan.script)): the sweep is
drawn live from one full-size image, so it stays sharp on any screen.

## Build

Needs ImageMagick (6 or 7), `make`, and `dpkg-deb` for the package; `python3` for the preview.

```sh
cd pivuan/plymouth-theme
make            # the theme in build/theme/pivuan
make preview    # build/pivuan-splash.gif: the animation, without booting
make deb        # build/pivuan-plymouth-theme_<version>-pivuan<rev>_all.deb
```

[make-assets.sh](make-assets.sh) makes the images from the project logo,
[../pivuan-logo.png](../pivuan-logo.png): the logo, the light of the sweep, each trace lit up,
the sparks and the ring flashes. The trace corners in `pivuan.script` are in that logo's pixels;
change them together with the logo.

Timings, sizes and speeds are settings at the top of `theme/pivuan.script`; the colors of the
light, sparks and glows are in `make-assets.sh`. `make preview` ([preview.py](preview.py))
draws the script's timeline with ImageMagick, close to what plymouth draws.
[test-x11.sh](test-x11.sh) runs the installed theme in real plymouth on a virtual X screen
(plymouth-x11 and xvfb) and takes screenshots; the workflow does this for every build.

Settings (logo, image size, package version) are in [config.mk](config.mk). Bump `VERSION` or
`DEB_REVISION` before publishing a new package.

## The package

`pivuan-plymouth-theme` installs the theme in `/usr/share/plymouth/themes/pivuan`, makes it
plymouth's theme, adds `splash plymouth.ignore-serial-consoles` to the Raspberry Pi's
`/boot/firmware/cmdline.txt` (not if `nosplash` is there) and rebuilds the initramfs. Removing
it gives plymouth back its default theme and takes the two options out again.

It also has an init script, `/etc/init.d/pivuan-splash`, which ends the splash at the end of the
boot. Devuan's own `/etc/init.d/plymouth` ends it with `--retain-splash`, leaving the screen in
graphics mode for a display manager to take over; without one (the minimal image, a console
login, Pivuan Audio's xlogin) the screen would never change again and the login on tty1 would
not be seen. The script ends it plainly, unless the display manager in
`/etc/X11/default-display-manager` (LightDM on XFCE and MATE) starts in that runlevel.
[test-quit.sh](test-quit.sh) checks this with real plymouth.

Pivuan images have it from the start (rations/build `extensions/pivuan-plymouth.sh` builds it
from this directory), and the Pivuan desktops install it from the apt repository.

## Publishing

The workflow [plymouth-theme.yml](../.github/workflows/plymouth-theme.yml) builds the package,
installs it in a clean Debian trixie container, checks the command line, the initramfs and real
plymouth (the screenshots are kept with the run), and with **publish** adds it to the Pivuan apt
repository.

## License

The script, the Makefile and the tools are under the GPL, version 2, like this repository. The
images are made from the Pivuan logo and are Pivuan artwork: all rights reserved (see the
[README](../README.md#license)).
