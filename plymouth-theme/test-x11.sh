#!/bin/sh
# Run the installed theme in real plymouth, on a virtual X screen, and take screenshots.
#
#   test-x11.sh <output dir> [boot|shutdown]
#
# Needs the theme installed and chosen (the package does both), plymouth-x11 (plymouth's X11
# renderer, made for testing themes), xvfb and imagemagick. Run as root. Fails if plymouth
# reports an error in the script or the screen stays black; the screenshots and plymouthd's
# log are left in <output dir>.
set -eu

out="$1"
mode="${2:-boot}"
mkdir -p "${out}"

Xvfb :99 -screen 0 1280x720x24 -nolisten tcp > "${out}/xvfb.log" 2>&1 &
xvfb=$!
export DISPLAY=:99
sleep 2

# No udev in a container or chroot: plymouth.ignore-udev makes plymouthd use its fallback
# renderers, of which x11 comes first.
plymouthd --no-daemon --debug --debug-file="${out}/plymouthd.log" --mode="${mode}" \
	--kernel-command-line="splash plymouth.ignore-udev" > "${out}/plymouthd.out" 2>&1 &
plymouthd=$!
sleep 2
plymouth --ping
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

plymouth quit
wait "${plymouthd}" || true
kill "${xvfb}" || true

status=0
if grep -iE "parse error|parser error|script error|undefined function" "${out}/plymouthd.log" "${out}/plymouthd.out"; then
	echo "plymouth reports an error in the script" >&2
	status=1
fi
if ! grep -q "script" "${out}/plymouthd.log"; then
	echo "plymouthd did not load the script module (see ${out}/plymouthd.log)" >&2
	status=1
fi
# The logo is up after the sweep: some of the last screenshot is bright, and some of it is red
# (the i-dot and the middle trace).
last="${out}/shot-3.5.png"
bright=$(convert "${last}" -colorspace gray -threshold 50% -format '%[fx:mean]' info:)
red=$(convert "${last}" -fx 'r > 0.6 && g < 0.25 && b < 0.3' -format '%[fx:mean]' info:)
echo "last screenshot: ${bright} bright, ${red} red"
if [ "$(echo "${bright} < 0.003" | bc)" = 1 ] || [ "$(echo "${red} < 0.0003" | bc)" = 1 ]; then
	echo "the logo is not on the screen" >&2
	status=1
fi
exit "${status}"
