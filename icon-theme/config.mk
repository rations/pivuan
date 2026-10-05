# Settings for the Makefile; override any of them on the command line
# (make HAIKU_SRC=/path/to/haiku).

# Haiku commit the icons come from. make fetches only the files it needs from
# it into build/haiku; change it (and bump VERSION) to take newer icons.
HAIKU_REPO ?= https://github.com/haiku/haiku
HAIKU_COMMIT ?= 211a7cf1e386a061a090315cb8fafe5e84bed44d
# Haiku source tree the icons come from: the fetched one, or a full checkout of
# your own (then HAIKU_COMMIT is not used)
HAIKU_SRC ?= build/haiku

# Theme directory name (under share/icons) and its description
THEME_NAME ?= Pivuan
THEME_COMMENT ?= Icons from the Haiku operating system (unofficial)
# Themes that supply the names this one lacks, in order; ones not installed are
# skipped. Numix is the default icon theme of Pivuan's XFCE and MATE desktops
# (Pivuan Audio uses this theme, and Numix for the rest).
INHERITS ?= Numix,Adwaita,hicolor

# Fixed sizes rendered as PNG next to the scalable SVGs
SIZES ?= 16 22 24 32 48 64 128 256

# make install puts the theme in $(DESTDIR)$(PREFIX)/share/icons/$(THEME_NAME)
PREFIX ?= $(HOME)/.local

# Debian package (make deb): name, version (<VERSION>-pivuan<DEB_REVISION>; a
# published version can never be reused, so bump one of them for every release)
DEB_PACKAGE ?= pivuan-icon-theme
VERSION ?= 0.1.0
DEB_REVISION ?= 1
MAINTAINER ?= Pivuan <https://github.com/rations/pivuan>
