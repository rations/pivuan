# Settings for the Makefile; override any of them on the command line
# (make CANVAS_W=1000).

# The logo the images are made from (the project logo; the trace corners in
# theme/pivuan.script are for this 1774x887 picture)
LOGO ?= ../pivuan-logo.png
# Width in pixels of the logo images (the logo with its glow border). The script
# scales them once at boot to 42% of the screen width: 1400 covers a 4K screen
# with little enlarging.
CANVAS_W ?= 1400

# Theme directory name (under share/plymouth/themes); the script and the
# .plymouth file name it too
THEME_NAME ?= pivuan

# make install puts the theme in $(DESTDIR)$(PREFIX)/share/plymouth/themes/$(THEME_NAME)
PREFIX ?= /usr

# Debian package (make deb): name, version (<VERSION>-pivuan<DEB_REVISION>; a
# published version can never be reused, so bump one of them for every release)
DEB_PACKAGE ?= pivuan-plymouth-theme
VERSION ?= 1.0.0
DEB_REVISION ?= 2
MAINTAINER ?= Pivuan <https://github.com/rations/pivuan>
