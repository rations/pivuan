#!/bin/bash
#
# Build XLibre for Pivuan (Devuan excalibur, arm64) from the pins in xlibre.conf, or check the
# packages built.
#
# Usage (as root, inside an excalibur root; .github/workflows/xlibre.yml runs it in Docker):
#   build-xlibre.sh build <out-dir>   build the X server and the libinput driver into <out-dir>
#   build-xlibre.sh check <deb-dir>   install the published set in a clean root and check it
#
# The source is X11Libre's release tag at the pinned commit; debian/ comes from xlibre-debian's
# packaging at its pinned commit, adapted so that everything builds and installs with Devuan
# excalibur alone (xlibre-debian's own packages need backports on excalibur):
# - x11proto-dev (>= 2025.1) becomes (>= 2024.1): excalibur's headers have everything the
#   server's meson.build asks for;
# - xserver-xlibre-common accepts Devuan's x11-common instead of xlibre-x11-common;
# - the build profiles are nosystemd (libseat and seatd instead of systemd-logind) and noudeb,
#   and the test suite is skipped (nocheck), as in LCOS's XLibre build.
# Versions end in +pivuan1 (xlibre.conf).
#
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
conf="${here}/xlibre.conf"
# The packages Pivuan installs; the rest of what the build makes (Xephyr, Xvfb, Xnest,
# development files, debug symbols) is not published. Nor is xserver-xlibre-legacy, the
# setuid Xorg.wrap for startx: seatd (Pivuan Audio's xlogin) and LightDM (as root) give X its
# devices.
PUBLISH=(xserver-xlibre-core xserver-xlibre-common xserver-xlibre-input-libinput)
export DEBIAN_FRONTEND=noninteractive

die() { echo "::error::$*" >&2; exit 1; }

# conf_field <name> <field number>
conf_field() { awk -v n="$1" -v f="$2" '!/^#/ && $1 == n { print $f; exit }' "${conf}"; }

# fetch <repo> <commit> <dir>: that exact commit, nothing else.
fetch() {
	git init -q "$3"
	git -C "$3" fetch -q --depth 1 "$1" "$2"
	git -C "$3" checkout -q FETCH_HEAD
	[[ "$(git -C "$3" rev-parse HEAD)" == "$2" ]] || die "$1: got $(git -C "$3" rev-parse HEAD), expected $2"
}

# prepare <name> <work-dir>: the upstream tag with xlibre-debian's debian/, and a changelog entry
# for the Pivuan version. Prints the source directory.
prepare() {
	local name="$1" work="$2" src tag commit pkg pkg_commit version tag_commit source maint
	src="$(conf_field "${name}" 2)"
	tag="$(conf_field "${name}" 3)"
	commit="$(conf_field "${name}" 4)"
	pkg="$(conf_field "${name}" 5)"
	pkg_commit="$(conf_field "${name}" 6)"
	version="$(conf_field "${name}" 7)"
	[[ -n "${version}" ]] || die "${name}: incomplete line in ${conf}"

	# The tag must still name the pinned commit (annotated tags: the commit it points to).
	tag_commit="$(git ls-remote "${src}" "refs/tags/${tag}^{}" "refs/tags/${tag}" | awk 'NR == 1 || /\^\{\}$/ { c = $1 } END { print c }')"
	[[ "${tag_commit}" == "${commit}" ]] || die "${src} ${tag} is ${tag_commit:-missing}, xlibre.conf pins ${commit}"

	fetch "${src}" "${commit}" "${work}/${name}" >&2
	fetch "${pkg}" "${pkg_commit}" "${work}/${name}-packaging" >&2
	rm -rf "${work}/${name}/debian"
	cp -a "${work}/${name}-packaging/debian" "${work}/${name}/debian"

	source="$(dpkg-parsechangelog -l "${work}/${name}/debian/changelog" -S Source)"
	maint="Pivuan <pivuan@users.noreply.github.com>"
	{
		printf '%s (%s) excalibur; urgency=medium\n\n' "${source}" "${version}"
		printf '  * Rebuilt for Pivuan (Devuan excalibur, arm64) without backports.\n'
		printf '  * Source: %s %s (%s).\n' "${src}" "${tag}" "${commit}"
		printf '  * Packaging: %s (%s).\n\n' "${pkg}" "${pkg_commit}"
		printf ' -- %s  %s\n\n' "${maint}" "$(date -R)"
		cat "${work}/${name}/debian/changelog"
	} > "${work}/changelog.new"
	mv "${work}/changelog.new" "${work}/${name}/debian/changelog"
	echo "${work}/${name}"
}

# build_in <source-dir>: build dependencies from excalibur, then the binary packages.
build_in() {
	local dir="$1"
	apt-get build-dep -y -q --no-install-recommends -P "${DEB_BUILD_PROFILES// /,}" "${dir}"
	(cd "${dir}" && dpkg-buildpackage -b -uc -us)
}

cmd_build() {
	local out work dir
	out="$(realpath -m "${1:?usage: build-xlibre.sh build <out-dir>}")"
	work="$(mktemp -d)"
	mkdir -p "${out}"
	export DEB_BUILD_PROFILES="nosystemd noudeb"
	DEB_BUILD_OPTIONS="nocheck parallel=$(nproc)"
	export DEB_BUILD_OPTIONS

	apt-get update -q
	# xauth: debian/rules starts the new Xvfb once while installing, even with nocheck.
	apt-get install -y -q --no-install-recommends \
		build-essential dpkg-dev fakeroot git ca-certificates quilt xauth

	# 1. The X server.
	dir="$(prepare xserver "${work}")"
	sed -i 's/x11proto-dev (>= 2025\.1)/x11proto-dev (>= 2024.1)/' "${dir}/debian/control"
	sed -i 's/^ xlibre-x11-common,$/ xlibre-x11-common | x11-common,/' "${dir}/debian/control"
	grep -q '^ xlibre-x11-common | x11-common,$' "${dir}/debian/control" || die "xserver-xlibre-common: the xlibre-x11-common dependency was not found"
	if grep -q '2025\.1' "${dir}/debian/control"; then die "debian/control still asks for x11proto-dev 2025.1"; fi
	build_in "${dir}"

	# 2. The libinput driver, built against that server (its -dev package brings the xsf
	#    debhelper add-on and the input ABI the driver depends on).
	apt-get install -y -q --no-install-recommends "${work}"/xserver-xlibre-dev_*.deb "${work}"/xserver-xlibre-common_*.deb
	dir="$(prepare libinput "${work}")"
	build_in "${dir}"

	# 3. The packages Pivuan installs.
	local p f
	for p in "${PUBLISH[@]}"; do
		f="$(find "${work}" -maxdepth 1 -name "${p}_*.deb" | head -n 1)"
		[[ -n "${f}" ]] || die "the build made no ${p}"
		cp "${f}" "${out}/"
	done
	echo "Built:"
	ls -l "${out}"
}

cmd_check() {
	local debs fail=0 f
	debs="$(realpath "${1:?usage: build-xlibre.sh check <deb-dir>}")"
	summary() { [[ -n "${SUMMARY:-}" ]] && echo "$*" >> "${SUMMARY}"; return 0; }

	# Only Devuan excalibur main is configured here: no backports, no xlibre-debian.
	if grep -rhs '^[^#]*\(backports\|xlibre-debian\)' /etc/apt/sources.list /etc/apt/sources.list.d/; then
		die "the check root has a backports or xlibre-debian source"
	fi
	apt-get update -q
	apt-get install -y -q --no-install-recommends "${debs}"/*.deb libgl1-mesa-dri

	summary "## XLibre for Pivuan"
	summary ""
	for f in "${debs}"/*.deb; do
		summary "- \`$(dpkg-deb -f "${f}" Package) $(dpkg-deb -f "${f}" Version)\`: Depends \`$(dpkg-deb -f "${f}" Depends)\`"
	done

	# The server runs and says it is XLibre.
	local version
	version="$(Xorg -version 2>&1 || true)"
	echo "${version}"
	grep -q 'XLibre' <<< "${version}" || { echo "::error::Xorg -version does not report XLibre"; fail=1; }
	summary ""
	summary "\`Xorg -version\`: $(grep -m1 'XLibre' <<< "${version}" || echo 'no XLibre line')"

	# What the Pi 5 needs: modesetting with glamor (GPU acceleration through Mesa), libinput.
	# XLibre keeps its own modules in modules/xlibre-25 (the ABI tag); driver packages may use
	# the base folder, which the loader also searches.
	local mod path
	for mod in modesetting_drv.so libglamoregl.so libinput_drv.so; do
		path="$(find /usr/lib/xorg/modules -name "${mod}" -print -quit)"
		[[ -n "${path}" ]] || { echo "::error::no ${mod} under /usr/lib/xorg/modules"; fail=1; continue; }
		summary "- \`${path}\`"
		if ldd "${path}" 2>&1 | grep -q 'not found'; then
			echo "::error::${path}: $(ldd "${path}" | grep 'not found' | tr '\n' ' ')"
			fail=1
		fi
		if [[ "${mod}" == libglamoregl.so ]] && ! ldd "${path}" | grep -q 'libgbm'; then
			echo "::error::glamor is not linked with Mesa's GBM"
			fail=1
		fi
	done
	if ldd /usr/lib/xorg/Xorg 2>&1 | grep -q 'not found'; then
		echo "::error::/usr/lib/xorg/Xorg: $(ldd /usr/lib/xorg/Xorg | grep 'not found' | tr '\n' ' ')"
		fail=1
	fi

	# The server was built with libseat (seatd), not systemd-logind. (Devuan's libseat itself
	# pulls in libsystemd0, so only the server's own dependencies count: its dynamic string
	# table names the libraries it links.)
	ldd /usr/lib/xorg/Xorg | grep -q 'libseat' || { echo "::error::Xorg is not linked with libseat"; fail=1; }
	if grep -q 'libsystemd\.so' /usr/lib/xorg/Xorg; then echo "::error::Xorg itself links libsystemd"; fail=1; fi

	summary ""
	summary "Checks: $([[ ${fail} == 0 ]] && echo passed || echo '**failed**')"
	return "${fail}"
}

case "${1:-}" in
	build) cmd_build "${2:-}" ;;
	check) cmd_check "${2:-}" ;;
	*) die "usage: build-xlibre.sh build <out-dir> | check <deb-dir>" ;;
esac
