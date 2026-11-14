#!/bin/bash
#
# Run a command (default: a shell) as root in the SonicDE build root made by make-root.sh.
#
# Usage (as root): enter-root.sh <work-dir> [command...]
#
# Inside the root:
#   /src      this repository (read-only)
#   /qt-src   ~/third_party/qt: the Qt tarballs (read-only)
#   /third_party  ~/third_party: SonicDE's repos and the rebuilt libraries' (read-only)
#   /work     <work-dir>/work: build trees and logs
#   /opt/sonicde  the installed stack (what the .debs are made from)
# ccache keeps its cache in <work-dir>/ccache, so rebuilds after a point release are quick. Qt
# compiles with precompiled headers, which ccache skips even with this sloppiness (it caches the
# rest); most SonicDE repos do not use them.
#
set -euo pipefail

work="$(realpath -m "${1:?usage: enter-root.sh <work-dir> [command...]}")"
shift
root="${work}/root"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
user_home="$(getent passwd "${SUDO_USER:-${USER}}" | cut -d: -f6)"
qt_src="${user_home}/third_party/qt"

[[ ${EUID} -eq 0 ]] || { echo "run as root" >&2; exit 1; }
[[ -e "${root}/etc/os-release" ]] || { echo "no root in ${work}: run make-root.sh" >&2; exit 1; }
[[ -e /proc/sys/fs/binfmt_misc/qemu-aarch64 ]] || { echo "run binfmt-arm64.sh first" >&2; exit 1; }

mounted=()
cleanup() {
	local i
	for (( i = ${#mounted[@]} - 1; i >= 0; i-- )); do
		umount -l "${mounted[i]}" || true
	done
}
trap cleanup EXIT

# bind <from> <to-in-root> [ro]
bind() {
	mkdir -p "$1" "${root}$2"
	mount --bind "$1" "${root}$2"
	mounted+=("${root}$2")
	if [[ "${3:-}" == ro ]]; then
		mount -o remount,bind,ro "${root}$2"
	fi
}

mkdir -p "${root}/proc" "${root}/sys" "${root}/dev"
mount -t proc proc "${root}/proc"; mounted+=("${root}/proc")
mount -t sysfs sys "${root}/sys"; mounted+=("${root}/sys")
bind /dev /dev
bind /dev/pts /dev/pts
bind "${here}" /src ro
bind "${qt_src}" /qt-src ro
bind "${user_home}/third_party" /third_party ro
bind "${work}/work" /work
bind "${work}/ccache" /var/cache/ccache
cp /etc/resolv.conf "${root}/etc/resolv.conf"

env -i HOME=/root TERM="${TERM:-xterm}" PATH=/usr/sbin:/usr/bin:/sbin:/bin \
	CCACHE_DIR=/var/cache/ccache CCACHE_SLOPPINESS=pch_defines,time_macros CCACHE_MAXSIZE=40G \
	LANG=C.UTF-8 \
	chroot "${root}" "${@:-/bin/bash}"
