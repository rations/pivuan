# Settings for the Makefile; override any of them on the command line
# (make PREFIX=/usr/local install).

# make install puts the window in $(DESTDIR)$(PREFIX)/bin and the helper in
# $(DESTDIR)$(PREFIX)/lib/pivuan/plugin-licenses
PREFIX ?= /usr
# The helper is an x86-64 Windows program (it runs in Wine, through FEX on ARM)
MINGW_CC ?= x86_64-w64-mingw32-gcc
CFLAGS ?= -O2
WARNINGS := -std=c11 -Wall -Wextra -Wpedantic -Wshadow

# Debian package (make deb): name, version (<VERSION>-pivuan<DEB_REVISION>; a
# published version can never be reused, so bump one of them for every release)
DEB_PACKAGE ?= pivuan-plugin-licenses
VERSION ?= 1.0.0
DEB_REVISION ?= 1
MAINTAINER ?= Pivuan <https://github.com/rations/pivuan>
