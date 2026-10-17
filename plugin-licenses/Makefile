# Build Plugin Licenses for Pivuan Audio (pivuan-plugin-licenses). See README.md.

include config.mk

PROGRAM   := pivuan-plugin-licenses
HELPER    := plugin-license-wait.exe
BUILD     := build
BINDIR    := $(DESTDIR)$(PREFIX)/bin
LIBDIR    := $(DESTDIR)$(PREFIX)/lib/pivuan/plugin-licenses
APPSDIR   := $(DESTDIR)$(PREFIX)/share/applications
DEB_VERSION := $(VERSION)-pivuan$(DEB_REVISION)
DEB_ROOT  := $(BUILD)/deb/root
# Only for Pivuan's arm64 systems, where wine-fex runs it
DEB_FILE  := $(BUILD)/$(DEB_PACKAGE)_$(DEB_VERSION)_arm64.deb

.PHONY: all check test install uninstall deb clean

all: $(BUILD)/$(HELPER)

$(BUILD)/$(HELPER): plugin-license-wait.c
	mkdir -p $(BUILD)
	$(MINGW_CC) $(WARNINGS) -Werror $(CFLAGS) -s -o $@ $< -ladvapi32

# The helper builds, the window's program compiles (no GTK needed), and the desktop file is valid
check: $(BUILD)/$(HELPER)
	python3 -c 'import ast, sys; ast.parse(open(sys.argv[1]).read(), sys.argv[1])' $(PROGRAM)
	! command -v desktop-file-validate > /dev/null || desktop-file-validate $(PROGRAM).desktop

# The window with a stand-in helper: it reaches "Ready" and closes the helper's input when it
# closes (needs an X display)
test: check
	python3 test-window.py $(PROGRAM)

install: $(BUILD)/$(HELPER)
	install -Dm 0755 $(PROGRAM) $(BINDIR)/$(PROGRAM)
	install -Dm 0644 $(BUILD)/$(HELPER) $(LIBDIR)/$(HELPER)
	install -Dm 0644 $(PROGRAM).desktop $(APPSDIR)/$(PROGRAM).desktop

uninstall:
	rm -f $(BINDIR)/$(PROGRAM) $(LIBDIR)/$(HELPER) $(APPSDIR)/$(PROGRAM).desktop
	-rmdir $(LIBDIR)

# Package for Debian/Devuan (and the Pivuan apt repository)
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
