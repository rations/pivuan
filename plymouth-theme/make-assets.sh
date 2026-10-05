#!/bin/bash
# Make the images of the Pivuan boot splash from the project logo (../pivuan-logo.png).
#
#   make-assets.sh <logo.png> <output dir> <canvas width>
#
# Every logo image is a "canvas": the logo with a BORDER of empty space around it (room for the
# glow), scaled to <canvas width>. pivuan.script places them all at the same spot and draws the
# sparks along the traces in logo pixels (the 1774x887 PNG), so BORDER and the trace corners in
# the script must match this file and the logo.
#
# Needs ImageMagick 6 (convert) or 7 (magick).
set -euo pipefail

logo="$1"
out="$2"
canvas_w="$3"

BORDER=60

if command -v magick > /dev/null; then
	im() { magick "$@"; }
else
	im() { convert "$@"; }
fi

read -r logo_w logo_h < <(im identify -format '%w %h\n' "${logo}" 2> /dev/null ||
	identify -format '%w %h\n' "${logo}")
if [[ "${logo_w}x${logo_h}" != 1774x887 ]]; then
	echo "${logo}: ${logo_w}x${logo_h}; pivuan.script's trace corners are for the 1774x887 logo" >&2
	exit 1
fi

tmp="$(mktemp -d)"
trap 'rm -rf "${tmp}"' EXIT
mkdir -p "${out}"

# Masks are grey; color drawn on a grey image can stay grey (ImageMagick 6), so make them RGB first
RGB="-colorspace sRGB -type TrueColor"

# A mask (white on black) as a shape in <color>: a layer of the color, the mask as its alpha.
# (Works the same in ImageMagick 6 and 7, unlike -alpha shape on a grey image.)
shape() { # <mask> <color> <output>
	im -size "$(im "$1" -format '%wx%h' info:)" "xc:$2" \( "$1" -alpha off \) \
		-compose CopyOpacity -composite "$3"
}

# Logo pixels -> canvas, scaled to the canvas width
to_canvas() { im "$1" -background none -gravity center -extent $((logo_w + 2 * BORDER))x$((logo_h + 2 * BORDER)) \
	-filter Lanczos -resize "${canvas_w}x" -define png:color-type=6 "$2"; }

# Masks (white on black) of the logo's red and grey parts. Edge pixels blended with the
# background are left out; the glow covers them.
im "${logo}" -fx '(a > 0.5 && r > 0.7 && g < 0.25) ? 1 : 0' -alpha off -colorspace gray "${tmp}/red.png"
im "${logo}" -fx '(a > 0.5 && abs(r-g) < 0.05 && abs(g-b) < 0.05 && r > 0.45 && r < 0.72) ? 1 : 0' \
	-alpha off -colorspace gray "${tmp}/grey.png"

# One trace with its ring: the part of a mask connected to a point on the trace.
# The top trace grows out of the "v", so its mask holds the whole "v" too.
trace_mask() { # <mask> <x,y> <output>
	im "$1" ${RGB} -fill red -draw "color $2 floodfill" \
		-fill black +opaque red -fill white -opaque red \
		-morphology Dilate Disk:1 -colorspace gray "$3"
}
trace_mask "${tmp}/grey.png" 1100,272 "${tmp}/top.png"
trace_mask "${tmp}/red.png" 1000,383 "${tmp}/mid.png"
trace_mask "${tmp}/grey.png" 1050,446 "${tmp}/bot.png"

# A shape lit up: the mask in <core> color over a blurred <glow> of it
lit() { # <mask> <core color> <glow color> <glow blur> <output, logo pixels>
	im "$1" -blur 0x"$4" -level 0,60% "${tmp}/glowmask.png"
	shape "${tmp}/glowmask.png" "$3" "${tmp}/glow.png"
	shape "$1" "$2" "${tmp}/core.png"
	im "${tmp}/glow.png" "${tmp}/core.png" -compose over -composite "$5"
}

# The logo
to_canvas "${logo}" "${out}/logo.png"

# The light that sweeps over the logo at startup: the whole logo white, with a red halo
im "${logo}" -alpha extract -threshold 50% "${tmp}/all.png"
lit "${tmp}/all.png" white '#ff1a3c' 16 "${tmp}/sweep.png"
to_canvas "${tmp}/sweep.png" "${out}/sweep.png"

# Each trace lit up (electricity has reached its pad)
lit "${tmp}/top.png" white '#d8e4ff' 12 "${tmp}/top-lit.png"
lit "${tmp}/mid.png" '#ff6276' '#ff1030' 12 "${tmp}/mid-lit.png"
lit "${tmp}/bot.png" white '#d8e4ff' 12 "${tmp}/bot-lit.png"
for t in top mid bot; do
	to_canvas "${tmp}/${t}-lit.png" "${out}/trace-${t}.png"
done

# Sprites in logo pixels, scaled like the canvas. Canvas width in logo pixels:
src_w=$((logo_w + 2 * BORDER))
scale() { im "$1" -filter Lanczos -resize "$(awk -v c="${canvas_w}" -v s="${src_w}" 'BEGIN { printf "%.4f", 100 * c / s }')%" \
	-define png:color-type=6 "$2"; }

# Spark: a small white-hot core in a soft glow (100x100 logo pixels; a trace is 29 wide)
spark() { # <glow color> <output>
	im -size 100x100 radial-gradient:white-black -evaluate pow 2.2 "${tmp}/falloff.png"
	shape "${tmp}/falloff.png" "$1" "${tmp}/sglow.png"
	im -size 100x100 xc:black -fill white -draw "circle 50,50 50,40" -blur 0x2.5 "${tmp}/coremask.png"
	shape "${tmp}/coremask.png" white "${tmp}/score.png"
	im "${tmp}/sglow.png" "${tmp}/score.png" -compose over -composite "${tmp}/spark.png"
	scale "${tmp}/spark.png" "$2"
}
spark '#dfe8ff' "${out}/spark.png"
spark '#ff2040' "${out}/spark-red.png"

# Ring flash: the pad ring lit up (outer radius 55, inner 27 in the logo: center line r=41)
flash() { # <core color> <glow color> <output>
	im -size 180x180 xc:black -fill none -stroke white -strokewidth 30 -draw "circle 90,90 90,49" \
		-colorspace gray "${tmp}/ring.png"
	lit "${tmp}/ring.png" "$1" "$2" 10 "${tmp}/flash.png"
	scale "${tmp}/flash.png" "$3"
}
flash white '#d8e4ff' "${out}/flash.png"
flash '#ff6276' '#ff1030' "${out}/flash-red.png"

# Password and question prompt (1080p pixels; the script scales them with the screen)
im -size 400x44 xc:none -fill '#101010' -stroke '#808080' -strokewidth 2 \
	-draw "roundrectangle 1,1 398,42 8,8" -define png:color-type=6 "${out}/entry.png"
im -size 14x14 xc:none -fill white -draw "circle 7,7 7,2" -define png:color-type=6 "${out}/bullet.png"
