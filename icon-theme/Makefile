# Build a freedesktop icon theme from Haiku's icons. See README.md.

include config.mk

BUILD     := build
HVIF_SRC  := third_party/hvif-tools
HVIF_COPY := $(BUILD)/hvif-tools-src
HVIF_OBJ  := $(BUILD)/hvif-tools
ICON2ICON := $(HVIF_OBJ)/icon2icon
LODSCAN   := $(BUILD)/bin/lodscan
PATCHES   := $(sort $(wildcard patches/hvif-tools/*.patch))
THEME_DIR := $(BUILD)/theme/$(THEME_NAME)
ICONS_DIR := $(DESTDIR)$(PREFIX)/share/icons
DEB_VERSION := $(VERSION)-pivuan$(DEB_REVISION)
DEB_ROOT  := $(BUILD)/deb/root
DEB_FILE  := $(BUILD)/$(DEB_PACKAGE)_$(DEB_VERSION)_all.deb
HAIKU_FETCH := $(BUILD)/haiku
# Fetch Haiku first unless HAIKU_SRC is a tree of your own
HAIKU_DEP := $(if $(filter $(HAIKU_FETCH),$(HAIKU_SRC)),haiku)

.PHONY: all haiku extract theme coverage lodscan install uninstall deb clean

all: theme

# hvif-tools is built from a copy of the submodule with our patches applied,
# so the submodule itself stays a clean upstream checkout.
$(HVIF_COPY)/.stamp: $(PATCHES) $(HVIF_SRC)/CMakeLists.txt
	@test -f $(HVIF_SRC)/external/stb/stb_image.h || \
		{ echo "hvif-tools submodules missing: git submodule update --init --recursive"; exit 1; }
	rm -rf $(HVIF_COPY)
	mkdir -p $(BUILD)
	cp -a $(HVIF_SRC) $(HVIF_COPY)
	set -e; for p in $(PATCHES); do patch -d $(HVIF_COPY) -p1 --quiet < $$p; done
	touch $@

$(ICON2ICON): $(HVIF_COPY)/.stamp
	cmake -S $(HVIF_COPY) -B $(HVIF_OBJ) -DCMAKE_BUILD_TYPE=Release \
		-DBUILD_IMG2SVG=OFF -DBUILD_IMG2SVG_SERVER=OFF -DHVIF_TOOLS_INSTALL=OFF \
		-DCMAKE_CXX_FLAGS=-Wno-multichar > /dev/null
	cmake --build $(HVIF_OBJ) --target icon2icon -j$$(nproc)
	touch $@

$(LODSCAN): tools/lodscan.cpp $(ICON2ICON)
	mkdir -p $(dir $@)
	$(CXX) -std=c++17 -O2 -w -I$(HVIF_COPY)/src/import -I$(HVIF_COPY)/src/common \
		-o $@ $< $(HVIF_OBJ)/libhviftools.a

# Haiku at HAIKU_COMMIT, with only the files the theme reads: the icons, the
# .rdef files, the MIME database and the artwork license. Nothing is fetched
# when the checkout is already at that commit.
haiku:
	set -e; d=$(HAIKU_FETCH); \
	if [ ! -d $$d/.git ] || [ "$$(git -C $$d rev-parse HEAD 2>/dev/null)" != "$(HAIKU_COMMIT)" ]; then \
		rm -rf $$d; mkdir -p $$d; git -C $$d init -q; \
		git -C $$d config core.sparseCheckout true; \
		printf '%s\n' /data/artwork/icons/ /data/artwork/ReadMe /License.md \
			'/src/**/*.rdef' /src/data/mime_db/ > $$d/.git/info/sparse-checkout; \
		git -C $$d fetch -q --depth 1 --filter=blob:none $(HAIKU_REPO) $(HAIKU_COMMIT); \
		git -C $$d checkout -q FETCH_HEAD; \
	fi

# Pull the HVIF icons out of Haiku's .rdef files and MIME database (fast; only
# changed files are rewritten).
extract: $(HAIKU_DEP)
	python3 tools/extract_rdef.py $(HAIKU_SRC) $(BUILD)/src

theme: $(ICON2ICON) extract
	python3 tools/build_theme.py --haiku-src $(HAIKU_SRC) --build $(BUILD) \
		--icon2icon $(ICON2ICON) --name "$(THEME_NAME)" \
		--comment "$(THEME_COMMENT)" --sizes "$(SIZES)" \
		--inherits "$(INHERITS)"

# Which freedesktop icon names the theme has, and which it still lacks
coverage: extract
	python3 tools/coverage.py --haiku-src $(HAIKU_SRC) --build $(BUILD)

# Haiku icons with shapes drawn only at some sizes (and ones that fail to parse)
lodscan: $(LODSCAN) $(HAIKU_DEP)
	find $(HAIKU_SRC)/data/artwork/icons -type f ! -name '*.wonderbrush' -print0 \
		| xargs -0 $(LODSCAN) | grep -v ' lod=0 ' || true

install: theme
	mkdir -p $(ICONS_DIR)
	rm -rf $(ICONS_DIR)/$(THEME_NAME)
	cp -a $(THEME_DIR) $(ICONS_DIR)/
	if [ -z "$(DESTDIR)" ]; then gtk-update-icon-cache -f -t -q $(ICONS_DIR)/$(THEME_NAME); fi

uninstall:
	rm -rf $(ICONS_DIR)/$(THEME_NAME)

# Architecture-independent package for Debian/Devuan (and the Pivuan apt repository)
deb: theme
	rm -rf $(BUILD)/deb
	$(MAKE) --no-print-directory install DESTDIR=$(DEB_ROOT) PREFIX=/usr
	mkdir -p $(DEB_ROOT)/DEBIAN $(DEB_ROOT)/usr/share/doc/$(DEB_PACKAGE)
	set -e; \
	commit=$$(git -C $(HAIKU_SRC) rev-parse HEAD 2>/dev/null || echo unknown); \
	size=$$(du -sk --apparent-size $(DEB_ROOT)/usr | cut -f1); \
	subst() { sed -e 's|@PACKAGE@|$(DEB_PACKAGE)|g' -e 's|@VERSION@|$(DEB_VERSION)|g' \
		-e 's|@MAINTAINER@|$(MAINTAINER)|g' -e 's|@THEME@|$(THEME_NAME)|g' \
		-e "s|@COMMIT@|$$commit|g" -e "s|@SIZE@|$$size|g" "$$1"; }; \
	subst packaging/deb/control.in > $(DEB_ROOT)/DEBIAN/control; \
	subst packaging/deb/copyright > $(DEB_ROOT)/usr/share/doc/$(DEB_PACKAGE)/copyright; \
	for s in postinst postrm; do \
		subst packaging/deb/$$s > $(DEB_ROOT)/DEBIAN/$$s; chmod 0755 $(DEB_ROOT)/DEBIAN/$$s; \
	done
	dpkg-deb --root-owner-group -Zxz --build $(DEB_ROOT) $(DEB_FILE)
	@echo "built $(DEB_FILE)"

clean:
	rm -rf $(BUILD)
