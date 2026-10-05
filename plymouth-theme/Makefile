# Build the Pivuan boot splash, a plymouth theme. See README.md.

include config.mk

BUILD     := build
THEME_DIR := $(BUILD)/theme/$(THEME_NAME)
THEMES    := $(DESTDIR)$(PREFIX)/share/plymouth/themes
DEB_VERSION := $(VERSION)-pivuan$(DEB_REVISION)
DEB_ROOT  := $(BUILD)/deb/root
DEB_FILE  := $(BUILD)/$(DEB_PACKAGE)_$(DEB_VERSION)_all.deb

.PHONY: all theme preview install uninstall deb clean

all: theme

# The images (make-assets.sh), then the script and the .plymouth file next to them
$(THEME_DIR)/.stamp: make-assets.sh $(LOGO) config.mk
	rm -rf $(THEME_DIR)
	./make-assets.sh $(LOGO) $(THEME_DIR) $(CANVAS_W)
	touch $@

theme: $(THEME_DIR)/.stamp theme/pivuan.script theme/pivuan.plymouth
	cp theme/pivuan.script $(THEME_DIR)/$(THEME_NAME).script
	sed 's|/themes/pivuan|/themes/$(THEME_NAME)|g; s|pivuan\.script|$(THEME_NAME).script|' \
		theme/pivuan.plymouth > $(THEME_DIR)/$(THEME_NAME).plymouth

# The animation as a GIF, to look at without booting (build/pivuan-splash.gif)
preview: theme
	python3 preview.py $(THEME_DIR) $(BUILD)/pivuan-splash.gif

install: theme
	mkdir -p $(THEMES)/$(THEME_NAME)
	install -m 0644 $(THEME_DIR)/*.png $(THEME_DIR)/$(THEME_NAME).script \
		$(THEME_DIR)/$(THEME_NAME).plymouth $(THEMES)/$(THEME_NAME)/

uninstall:
	rm -rf $(THEMES)/$(THEME_NAME)

# Architecture-independent package for Debian/Devuan (and the Pivuan apt repository)
deb: theme
	rm -rf $(BUILD)/deb
	$(MAKE) --no-print-directory install DESTDIR=$(DEB_ROOT) PREFIX=/usr
	mkdir -p $(DEB_ROOT)/DEBIAN $(DEB_ROOT)/usr/share/doc/$(DEB_PACKAGE)
	set -e; \
	size=$$(du -sk --apparent-size $(DEB_ROOT)/usr | cut -f1); \
	subst() { sed -e 's|@PACKAGE@|$(DEB_PACKAGE)|g' -e 's|@VERSION@|$(DEB_VERSION)|g' \
		-e 's|@MAINTAINER@|$(MAINTAINER)|g' -e 's|@THEME@|$(THEME_NAME)|g' \
		-e "s|@SIZE@|$$size|g" "$$1"; }; \
	subst packaging/deb/control.in > $(DEB_ROOT)/DEBIAN/control; \
	subst packaging/deb/copyright > $(DEB_ROOT)/usr/share/doc/$(DEB_PACKAGE)/copyright; \
	for s in postinst prerm postrm; do \
		subst packaging/deb/$$s > $(DEB_ROOT)/DEBIAN/$$s; chmod 0755 $(DEB_ROOT)/DEBIAN/$$s; \
	done
	dpkg-deb --root-owner-group -Zxz --build $(DEB_ROOT) $(DEB_FILE)
	@echo "built $(DEB_FILE)"

clean:
	rm -rf $(BUILD)
