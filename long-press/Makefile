# Build long press for right click on a touchscreen (pivuan-long-press). See README.md.

include config.mk

PROGRAM   := pivuan-long-press
BUILD     := build
BINDIR    := $(DESTDIR)$(PREFIX)/bin
LIBDIR    := $(DESTDIR)$(PREFIX)/lib/pivuan
RULESDIR  := $(DESTDIR)$(PREFIX)/lib/udev/rules.d
MODULESDIR := $(DESTDIR)$(PREFIX)/lib/modules-load.d
DEB_ARCH  = $(shell dpkg --print-architecture)
DEB_VERSION := $(VERSION)-pivuan$(DEB_REVISION)
DEB_ROOT  := $(BUILD)/deb/root
DEB_FILE  = $(BUILD)/$(DEB_PACKAGE)_$(DEB_VERSION)_$(DEB_ARCH).deb

.PHONY: all check install uninstall deb clean

all: $(BUILD)/$(PROGRAM)

$(BUILD)/$(PROGRAM): $(PROGRAM).c
	mkdir -p $(BUILD)
	$(CC) $(WARNINGS) -Werror $(CPPFLAGS) $(CFLAGS) $(LDFLAGS) -o $@ $<

# The program builds, and the control script is valid sh
check: $(BUILD)/$(PROGRAM)
	sh -n long-press
	$(BUILD)/$(PROGRAM) --help 2>&1 | grep -q '^usage: pivuan-long-press'

install: $(BUILD)/$(PROGRAM)
	install -Dm 0755 $(BUILD)/$(PROGRAM) $(BINDIR)/$(PROGRAM)
	install -Dm 0755 long-press $(LIBDIR)/long-press
	install -Dm 0644 70-pivuan-uinput.rules $(RULESDIR)/70-pivuan-uinput.rules
	install -d $(MODULESDIR)
	echo uinput > $(MODULESDIR)/pivuan-uinput.conf

uninstall:
	rm -f $(BINDIR)/$(PROGRAM) $(LIBDIR)/long-press $(RULESDIR)/70-pivuan-uinput.rules \
		$(MODULESDIR)/pivuan-uinput.conf

# Package for Debian/Devuan (and the Pivuan apt repository), for this machine's architecture
deb: check
	rm -rf $(BUILD)/deb
	$(MAKE) --no-print-directory install DESTDIR=$(DEB_ROOT) PREFIX=/usr
	mkdir -p $(DEB_ROOT)/DEBIAN $(DEB_ROOT)/usr/share/doc/$(DEB_PACKAGE)
	set -e; \
	size=$$(du -sk --apparent-size $(DEB_ROOT)/usr | cut -f1); \
	subst() { sed -e 's|@PACKAGE@|$(DEB_PACKAGE)|g' -e 's|@VERSION@|$(DEB_VERSION)|g' \
		-e 's|@ARCH@|$(DEB_ARCH)|g' -e 's|@MAINTAINER@|$(MAINTAINER)|g' \
		-e "s|@SIZE@|$$size|g" "$$1"; }; \
	subst packaging/deb/control.in > $(DEB_ROOT)/DEBIAN/control; \
	subst packaging/deb/copyright > $(DEB_ROOT)/usr/share/doc/$(DEB_PACKAGE)/copyright
	install -m 0755 packaging/deb/postinst $(DEB_ROOT)/DEBIAN/postinst
	dpkg-deb --root-owner-group -Zxz --build $(DEB_ROOT) $(DEB_FILE)
	@echo "built $(DEB_FILE)"

clean:
	rm -rf $(BUILD)
