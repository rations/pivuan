#!/bin/bash
#
# Make the excalibur arm64 root that SonicDE is built in, on this amd64 PC (through qemu).
#
# Usage (as root, after binfmt-arm64.sh): make-root.sh <work-dir>
#   The root goes in <work-dir>/root (about 3 GB; the build later adds tens of GB).
#   An existing root is kept: delete <work-dir>/root to make it again.
#
# Only excalibur main, signed with this PC's Devuan keyring, like the XLibre and Onboard
# workflows. The root holds the build tools and the libraries Qt and SonicDE build against,
# but no Qt, KDE Frameworks or libsystemd-dev: everything Qt-based is built into /opt/sonicde,
# and nothing may link to Devuan's Qt 6.8 (two Qt versions in one process crash).
#
set -euo pipefail

work="$(realpath -m "${1:?usage: make-root.sh <work-dir>}")"
root="${work}/root"
keyring=/usr/share/keyrings/devuan-archive-keyring.gpg
mirror=http://deb.devuan.org/merged

[[ ${EUID} -eq 0 ]] || { echo "run as root" >&2; exit 1; }
[[ -e /proc/sys/fs/binfmt_misc/qemu-aarch64 ]] || { echo "run binfmt-arm64.sh first" >&2; exit 1; }
command -v mmdebstrap > /dev/null || { echo "apt install mmdebstrap" >&2; exit 1; }
[[ -s "${keyring}" ]] || { echo "${keyring} is missing" >&2; exit 1; }
if [[ -e "${root}/etc/os-release" ]]; then
	echo "${root} exists; delete it to make it again" >&2
	exit 0
fi

packages=(
	# The Pivuan base stack, as on the image (same list as .github/workflows/xlibre.yml)
	devuan-keyring ca-certificates file sysvinit-core sysv-rc orphan-sysvinit-scripts eudev
	elogind libpam-elogind dbus
	# Build tools; dpkg-dev and fakeroot make the .debs
	build-essential cmake ninja-build pkgconf git ccache curl xz-utils python3 python3-yaml
	perl gperf bison flex dpkg-dev fakeroot
	# qtbase: Devuan's qt6-base build dependencies without the database drivers, journald
	# (libsystemd-dev), Wayland, GTK and lttng; libsm-dev gives X session management (xcb-sm), so
	# apps come back after logging in again
	libatspi2.0-dev libb2-dev libcups2-dev libdbus-1-dev libdouble-conversion-dev libdrm-dev
	libegl-dev libfontconfig-dev libfreetype-dev libgbm-dev libgl-dev libgles-dev libglib2.0-dev
	libharfbuzz-dev libicu-dev libjpeg-dev libkrb5-dev libmd4c-dev libmd4c-html0-dev
	libmtdev-dev libpcre2-dev libpng-dev libproxy-dev libsm-dev libsqlite3-dev libssl-dev libudev-dev
	libvulkan-dev libx11-dev libx11-xcb-dev libxcb1-dev libxcb-composite0-dev
	libxcb-cursor-dev libxcb-damage0-dev libxcb-dpms0-dev libxcb-dri2-0-dev libxcb-dri3-dev
	libxcb-ewmh-dev libxcb-glx0-dev libxcb-icccm4-dev libxcb-image0-dev libxcb-keysyms1-dev
	libxcb-present-dev libxcb-randr0-dev libxcb-record0-dev libxcb-render-util0-dev
	libxcb-render0-dev libxcb-res0-dev libxcb-screensaver0-dev libxcb-shape0-dev
	libxcb-shm0-dev libxcb-sync-dev libxcb-util-dev libxcb-xf86dri0-dev libxcb-xfixes0-dev
	libxcb-xinerama0-dev libxcb-xinput-dev libxcb-xkb-dev libxcb-xtest0-dev libxcb-xv0-dev
	libxext-dev libxfixes-dev libxi-dev libxkbcommon-dev libxkbcommon-x11-dev libxrender-dev
	libzstd-dev zlib1g-dev
	# qtimageformats, qtmultimedia (FFmpeg, PulseAudio, X11 screen capture: Xrandr), qtspeech
	# (speech-dispatcher)
	libtiff-dev libwebp-dev libavcodec-dev libavformat-dev libavutil-dev libswresample-dev
	libswscale-dev libva-dev libpulse-dev libxrandr-dev libspeechd-dev
)

mkdir -p "${work}"
mmdebstrap --verbose --variant=minbase --architectures=arm64 \
	--include="$(IFS=,; echo "${packages[*]}")" \
	--setup-hook="install -Dm 0644 '${keyring}' \"\$1${keyring}\"" \
	--customize-hook="echo 'deb-src [signed-by=${keyring}] ${mirror} excalibur main' >> \"\$1/etc/apt/sources.list\"" \
	excalibur "${root}" "deb [signed-by=${keyring}] ${mirror} excalibur main"

# Nothing Qt or KDE from Devuan, and no libsystemd-dev
leaks="$(chroot "${root}" dpkg-query -W -f '${Package}\n' 'libqt6*' 'qt6-*' 'libkf6*' libsystemd-dev 2>/dev/null || true)"
if [[ -n "${leaks}" ]]; then
	echo "The root has packages it must not have:" >&2
	echo "${leaks}" >&2
	exit 1
fi
echo "Root ready: ${root}"
