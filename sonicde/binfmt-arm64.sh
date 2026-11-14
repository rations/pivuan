#!/bin/bash
#
# Let this amd64 PC run arm64 programs through qemu, for the SonicDE build root.
#
# Usage (as root, once after each boot): binfmt-arm64.sh
#
# qemu-user ships the registration as /usr/lib/binfmt.d/qemu-aarch64.conf, which only
# systemd-binfmt reads; Devuan has no systemd and /usr/share/binfmts has no qemu entry, so this
# writes the same line to the kernel. Its F flag loads the (static) qemu now, so it also works
# inside the build root.
#
set -euo pipefail

conf=/usr/lib/binfmt.d/qemu-aarch64.conf
misc=/proc/sys/fs/binfmt_misc

[[ -e "${conf}" ]] || { echo "${conf} is missing: apt install qemu-user-binfmt" >&2; exit 1; }
[[ -e "${misc}/register" ]] || mount -t binfmt_misc binfmt_misc "${misc}"
if [[ -e "${misc}/qemu-aarch64" ]]; then
	echo "qemu-aarch64 is already registered"
else
	grep -v '^#' "${conf}" > "${misc}/register"
	echo "qemu-aarch64 registered"
fi
grep -E '^(enabled|interpreter|flags)' "${misc}/qemu-aarch64"
