#!/bin/sh
# Run the installed theme in real plymouth, on a virtual X screen, and take screenshots.
#
#   test-x11.sh <output dir> [boot|shutdown]
#
# Needs the theme installed and chosen (the package does both), plymouth-x11 (plymouth's X11
# renderer, made for testing themes), xvfb, x11-utils, imagemagick and bc. Run as root. Fails if
# plymouth reports an error in the script or the logo is not on the screen; the screenshots and
# the logs are left in <output dir>, and on failure the logs' important lines are printed.
set -eu

out="$1"
mode="${2:-boot}"
mkdir -p "${out}"
export DISPLAY=:99
xvfb=""
plymouthd=""

# What went wrong, in the job's own output (the files may never be uploaded).
report() {
	echo "--- Xvfb (${out}/xvfb.log)" >&2
	tail -n 20 "${out}/xvfb.log" >&2 2> /dev/null || true
	echo "--- plymouthd output (${out}/plymouthd.out)" >&2
	tail -n 20 "${out}/plymouthd.out" >&2 2> /dev/null || true
	echo "--- plymouthd: renderers, displays and the theme (${out}/plymouthd.log)" >&2
	grep -iE "renderer|display|terminal|theme|splash|script|plugin|could not|fail|error" \
		"${out}/plymouthd.log" 2> /dev/null | cut -c 1-220 | head -n 60 >&2 || true
}

# Leave nothing running, whatever happens.
cleanup() {
	[ -z "${plymouthd}" ] || kill "${plymouthd}" 2> /dev/null || true
	[ -z "${xvfb}" ] || kill "${xvfb}" 2> /dev/null || true
}
trap cleanup EXIT

fail() {
	echo "$1" >&2
	report
	exit 1
}

rm -f /tmp/.X99-lock
Xvfb :99 -screen 0 1280x720x24 -nolisten tcp > "${out}/xvfb.log" 2>&1 &
xvfb=$!
# Up to 15 s for the X server to answer.
tries=0
until xdpyinfo > /dev/null 2>&1; do
	kill -0 "${xvfb}" 2> /dev/null || fail "Xvfb did not start"
	tries=$((tries + 1))
	[ "${tries}" -le 30 ] || fail "Xvfb does not answer"
	sleep 0.5
done

# No udev in a container or chroot: plymouth.ignore-udev makes plymouthd use its fallback
# renderers, of which x11 comes first.
plymouthd --no-daemon --debug --debug-file="${out}/plymouthd.log" --mode="${mode}" \
	--kernel-command-line="splash plymouth.ignore-udev" > "${out}/plymouthd.out" 2>&1 &
plymouthd=$!
tries=0
until plymouth --ping; do
	kill -0 "${plymouthd}" 2> /dev/null || fail "plymouthd exited"
	tries=$((tries + 1))
	[ "${tries}" -le 30 ] || fail "plymouthd does not answer"
	sleep 0.5
done
plymouth show-splash
start=$(date +%s.%N)

# Screenshots at about these seconds after show-splash: the sweep, the dim logo brightening,
# then sparks (they start at 1.8 s and repeat every 2.6 s).
for at in 0.5 1.3 2.1 2.5 2.9 3.5; do
	now=$(date +%s.%N)
	wait=$(echo "${start} + ${at} - ${now}" | bc)
	case "${wait}" in -*) ;; *) sleep "${wait}" ;; esac
	import -window root "${out}/shot-${at}.png"
done
# plymouth's window (the x11 renderer draws in one, "Plymouth") while it is up
xwininfo -root -tree > "${out}/windows.txt" 2>&1 || true

plymouth quit
wait "${plymouthd}" || true
plymouthd=""

status=0
if grep -iE "parse error|parser error|script error|undefined function" "${out}/plymouthd.log" "${out}/plymouthd.out"; then
	echo "plymouth reports an error in the script" >&2
	status=1
fi
if ! grep -q "plugins/splash/script" "${out}/plymouthd.log"; then
	echo "plymouthd did not load the script module" >&2
	status=1
fi
# The logo is up after the sweep: some of the last screenshot is bright, and some of it is the
# logo's red (the i-dot and the middle trace, #D0001E).
last="${out}/shot-3.5.png"
bright=$(convert "${last}" -alpha off -colorspace gray -threshold 50% -format '%[fx:mean]' info:)
red=$(convert "${last}" -alpha off -fuzz 25% -fill black +opaque '#D0001E' -fill white \
	-opaque '#D0001E' -colorspace gray -format '%[fx:mean]' info:)
echo "last screenshot: ${bright} bright, ${red} red"
if [ "$(echo "${bright} < 0.003" | bc)" = 1 ] || [ "$(echo "${red} < 0.0003" | bc)" = 1 ]; then
	echo "the logo is not on the screen" >&2
	echo "--- X windows (${out}/windows.txt)" >&2
	head -n 20 "${out}/windows.txt" >&2
	status=1
fi
[ "${status}" = 0 ] || report
exit "${status}"
