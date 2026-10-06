#!/bin/sh
# Check /etc/init.d/pivuan-splash with real plymouth: at the end of the boot it ends a running
# splash (so the console gets the screen back), unless a display manager starts in the runlevel.
#
#   test-quit.sh
#
# Needs the package installed (the script and plymouth). Run as root, in a container or chroot:
# it writes /etc/X11/default-display-manager and an /etc/rc2.d link for a pretend LightDM.
set -eu

pid=""
cleanup() {
	[ -z "${pid}" ] || kill "${pid}" 2> /dev/null || true
	rm -f /etc/X11/default-display-manager /etc/rc2.d/S03lightdm
}
trap cleanup EXIT

# A splash that is up, on no screen (enough to answer and quit)
start() {
	plymouthd --no-daemon --mode=boot \
		--kernel-command-line="splash plymouth.ignore-udev plymouth.ignore-serial-consoles" &
	pid=$!
	tries=0
	until plymouth --ping; do
		tries=$((tries + 1))
		[ "${tries}" -le 30 ] || { echo "plymouthd does not answer" >&2; exit 1; }
		sleep 0.2
	done
}

# Running after a second, or not
running() {
	sleep 1
	plymouth --ping
}

ls /etc/rc2.d/S*pivuan-splash > /dev/null || { echo "pivuan-splash is not started in runlevel 2" >&2; exit 1; }

start
RUNLEVEL=2 /etc/init.d/pivuan-splash start
if running; then echo "console only: the splash was not ended" >&2; exit 1; fi
echo "console only: the splash ended"
wait "${pid}" || true

mkdir -p /etc/X11 /etc/rc2.d
echo /usr/sbin/lightdm > /etc/X11/default-display-manager
ln -sf ../init.d/lightdm /etc/rc2.d/S03lightdm
start
RUNLEVEL=2 /etc/init.d/pivuan-splash start
running || { echo "display manager: the splash was ended" >&2; exit 1; }
echo "display manager: the splash stays for it"
plymouth quit
wait "${pid}" || true
pid=""
