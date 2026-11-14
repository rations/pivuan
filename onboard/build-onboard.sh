#!/bin/bash
#
# Build Onboard, the on-screen keyboard, for Pivuan (Devuan excalibur, arm64): Devuan's source
# at the version in onboard.conf with Pivuan's patches, or check the packages built.
#
# Usage (as root, inside an excalibur root; .github/workflows/onboard.yml runs it in Docker):
#   build-onboard.sh build <out-dir>   build onboard, onboard-common and onboard-data
#   build-onboard.sh check <deb-dir>   install them in a clean root and check them (no session:
#                                      the change is in the files, the C module finds its libraries)
#
# patches/*.patch (DEP-3) are added to the end of debian/patches/series, after Debian's. The
# build stops if Devuan has a newer onboard than the one pinned, or if a patch does not apply.
#
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
read -r source_version version < <(awk '!/^#/ && NF' "${here}/onboard.conf")
# All three, as onboard-data needs an onboard of its own version.
PUBLISH=(onboard onboard-common onboard-data)
export DEBIAN_FRONTEND=noninteractive

die() { echo "::error::$*" >&2; exit 1; }

cmd_build() {
	local out work dir newest patch patches=()
	out="$(realpath -m "${1:?usage: build-onboard.sh build <out-dir>}")"
	work="$(mktemp -d)"
	mkdir -p "${out}"

	apt-get update -q
	apt-get install -y -q --no-install-recommends build-essential dpkg-dev fakeroot ca-certificates

	# The newest onboard source in the configured suites must be the pinned one.
	newest="$(apt-cache showsrc onboard | awk '/^Version:/ { print $2 }' | sort -V | tail -n 1)"
	[[ -n "${newest}" ]] || die "no onboard source in the configured Devuan suites"
	dpkg --compare-versions "${newest}" le "${source_version}" \
		|| die "Devuan has onboard ${newest}, newer than ${source_version} in onboard.conf: update it"

	(cd "${work}" && apt-get source -q --only-source "onboard=${source_version}")
	dir="$(find "${work}" -mindepth 1 -maxdepth 1 -type d -name 'onboard-*' | head -n 1)"
	[[ -d "${dir}/debian" ]] || die "apt-get source onboard=${source_version} unpacked nothing"

	# Pivuan's patches, after Debian's. apt-get source has applied Debian's (recorded in .pc);
	# dpkg-buildpackage applies the rest of the series before it builds.
	for patch in "${here}"/patches/*.patch; do
		[[ -f "${patch}" ]] || continue
		(cd "${dir}" && patch -p1 --dry-run -s -f < "${patch}" > /dev/null) \
			|| die "${patch##*/} does not apply to onboard ${source_version}"
		install -Dm 0644 "${patch}" "${dir}/debian/patches/${patch##*/}"
		echo "${patch##*/}" >> "${dir}/debian/patches/series"
		patches+=("${patch##*/}")
	done

	{
		printf 'onboard (%s) excalibur; urgency=medium\n\n' "${version}"
		printf '  * Rebuilt for Pivuan (Devuan excalibur, arm64) from Devuan'"'"'s onboard %s.\n' "${source_version}"
		for patch in "${patches[@]}"; do
			printf '  * Pivuan patch: %s.\n' "${patch}"
		done
		printf '\n -- Pivuan <pivuan@users.noreply.github.com>  %s\n\n' "$(date -R)"
		cat "${dir}/debian/changelog"
	} > "${work}/changelog.new"
	mv "${work}/changelog.new" "${dir}/debian/changelog"

	apt-get build-dep -y -q --no-install-recommends "${dir}"
	(cd "${dir}" && dpkg-buildpackage -b -uc -us)

	local p f
	for p in "${PUBLISH[@]}"; do
		f="$(find "${work}" -maxdepth 1 -name "${p}_${version#*:}_*.deb" | head -n 1)"
		[[ -n "${f}" ]] || die "the build made no ${p} ${version}"
		cp "${f}" "${out}/"
	done
	echo "Built:"
	ls -l "${out}"
}

cmd_check() {
	local debs fail=0 f p
	debs="$(realpath "${1:?usage: build-onboard.sh check <deb-dir>}")"
	summary() { [[ -n "${SUMMARY:-}" ]] && echo "$*" >> "${SUMMARY}"; return 0; }

	apt-get update -q
	apt-get install -y -q --no-install-recommends "${debs}"/*.deb

	summary "## Onboard for Pivuan"
	summary ""
	for f in "${debs}"/*.deb; do
		summary "- \`$(dpkg-deb -f "${f}" Package) $(dpkg-deb -f "${f}" Version)\`"
	done
	for p in "${PUBLISH[@]}"; do
		[[ "$(dpkg-query -W -f '${Version}' "${p}" 2>/dev/null)" == "${version}" ]] \
			|| { echo "::error::${p} ${version} is not installed"; fail=1; }
	done

	# Pivuan's change is in the installed file, which compiles. (Importing Onboard's modules
	# here would set up its GSettings and GTK, which need a desktop session.)
	f="$(dpkg -L onboard | grep '/Onboard/AtspiStateTracker\.py$' | head -n 1)"
	if [[ -z "${f}" ]] || ! grep -q 'def is_chromium_omnibox' "${f}"; then
		echo "::error::onboard lacks the Chromium address bar change (${f:-no AtspiStateTracker.py})"
		fail=1
	elif ! python3 -c 'import ast, sys; ast.parse(open(sys.argv[1]).read(), sys.argv[1])' "${f}"; then
		echo "::error::${f} does not compile"
		fail=1
	fi
	# Onboard's C module finds all its libraries.
	f="$(dpkg -L onboard | grep '/Onboard/osk[^/]*\.so$' | head -n 1)"
	if [[ -z "${f}" ]]; then
		echo "::error::onboard has no osk module"
		fail=1
	elif ldd "${f}" 2>&1 | grep -q 'not found'; then
		echo "::error::${f}: $(ldd "${f}" | grep 'not found' | tr '\n' ' ')"
		fail=1
	fi
	zcat "/usr/share/doc/onboard/changelog.Debian.gz" | head -n 6

	summary ""
	summary "Checks: $([[ ${fail} == 0 ]] && echo passed || echo '**failed**')"
	return "${fail}"
}

case "${1:-}" in
	build) cmd_build "${2:-}" ;;
	check) cmd_check "${2:-}" ;;
	*) die "usage: build-onboard.sh build <out-dir> | check <deb-dir>" ;;
esac
