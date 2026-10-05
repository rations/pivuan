# Build Desktop Settings for Pivuan Audio (pivuan-desktop-settings). See README.md.

include config.mk

PROGRAM   := pivuan-desktop-settings
BUILD     := build
BINDIR    := $(DESTDIR)$(PREFIX)/bin
DEB_VERSION := $(VERSION)-pivuan$(DEB_REVISION)
DEB_ROOT  := $(BUILD)/deb/root
DEB_FILE  := $(BUILD)/$(DEB_PACKAGE)_$(DEB_VERSION)_all.deb

.PHONY: all check test install uninstall deb clean

all: check

# The program compiles (no GTK needed)
check:
	python3 -c 'import ast, sys; ast.parse(open(sys.argv[1]).read(), sys.argv[1])' $(PROGRAM)

# The window: Apply highlighted only while something is to be applied (needs an X display)
test: check
	python3 test-window.py $(PROGRAM)

install: check
	install -Dm 0755 $(PROGRAM) $(BINDIR)/$(PROGRAM)

uninstall:
	rm -f $(BINDIR)/$(PROGRAM)

# Architecture-independent package for Debian/Devuan (and the Pivuan apt repository)
deb: check
	rm -rf $(BUILD)/deb
	$(MAKE) --no-print-directory install DESTDIR=$(DEB_ROOT) PREFIX=/usr
	mkdir -p $(DEB_ROOT)/DEBIAN $(DEB_ROOT)/usr/share/doc/$(DEB_PACKAGE)
	set -e; \
	size=$$(du -sk --apparent-size $(DEB_ROOT)/usr | cut -f1); \
	subst() { sed -e 's|@PACKAGE@|$(DEB_PACKAGE)|g' -e 's|@VERSION@|$(DEB_VERSION)|g' \
		-e 's|@MAINTAINER@|$(MAINTAINER)|g' -e "s|@SIZE@|$$size|g" "$$1"; }; \
	subst packaging/deb/control.in > $(DEB_ROOT)/DEBIAN/control; \
	subst packaging/deb/copyright > $(DEB_ROOT)/usr/share/doc/$(DEB_PACKAGE)/copyright
	dpkg-deb --root-owner-group -Zxz --build $(DEB_ROOT) $(DEB_FILE)
	@echo "built $(DEB_FILE)"

clean:
	rm -rf $(BUILD)
