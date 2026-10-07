# Settings for the Makefile; override any of them on the command line
# (make PREFIX=/usr/local install).

# make install puts the program in $(DESTDIR)$(PREFIX)/bin
PREFIX ?= /usr

# Debian package (make deb): name, version (<VERSION>-pivuan<DEB_REVISION>; a
# published version can never be reused, so bump one of them for every release)
DEB_PACKAGE ?= pivuan-desktop-settings
VERSION ?= 1.2.0
DEB_REVISION ?= 1
MAINTAINER ?= Pivuan <https://github.com/rations/pivuan>
