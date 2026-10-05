#!/usr/bin/env python3
"""Render the boot splash as an animated GIF, to look at it without booting.

    preview.py <assets dir> <output.gif> [--size 1280x720] [--rounds 2] [--fps 25] [--mode boot]

It reads the settings and the trace corners from theme/pivuan.script and draws, frame by frame,
what the script draws (the sweep, the brightening, the sparks), with ImageMagick and the images
from make-assets.sh. It is a close copy of the script, not plymouth itself: check the real thing
with plymouth-x11 or on a Pi.
"""
import argparse
import concurrent.futures
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
IM = shutil.which("magick") or "convert"


def read_script(path):
    text = open(path).read()
    settings = {m[1]: float(m[2]) for m in re.finditer(r"^([A-Z_]+) = ([0-9.]+);", text, re.M)}
    traces = {}
    for m in re.finditer(r"trace\[(\d)\]\.(\w+)(?:\[(\d)\])? = ([^;]+);", text):
        t, key, idx, value = int(m[1]), m[2], m[3], m[4].strip().strip('"')
        tr = traces.setdefault(t, {"x": {}, "y": {}})
        if idx is not None:
            tr[key][int(idx)] = float(value)
        else:
            tr[key] = value if key == "name" else float(value)
    out = []
    for t in sorted(traces):
        tr = traces[t]
        n = int(tr["n"])
        pts = [(tr["x"][k], tr["y"][k]) for k in range(n)]
        at = [0.0]
        for k in range(1, n):
            at.append(at[-1] + math.dist(pts[k - 1], pts[k]))
        out.append(dict(name=tr["name"], pts=pts, at=at, length=at[-1], red=int(tr["red"]),
                        delay=tr["delay"], ring=(tr["ring_x"], tr["ring_y"])))
    return settings, out


def identify(path):
    w, h = subprocess.check_output([IM, "identify", "-format", "%w %h", path] if IM.endswith("magick")
                                   else ["identify", "-format", "%w %h", path]).split()
    return int(w), int(h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("assets")
    ap.add_argument("output")
    ap.add_argument("--size", default="1280x720")
    ap.add_argument("--rounds", type=float, default=2)
    ap.add_argument("--fps", type=int, default=25)
    ap.add_argument("--mode", default="boot")
    a = ap.parse_args()

    S, traces = read_script(os.path.join(HERE, "theme", "pivuan.script"))
    sw, sh = map(int, a.size.split("x"))

    # Same canvas arithmetic as the script
    src_w = S["LOGO_W"] + 2 * S["BORDER"]
    src_h = S["LOGO_H"] + 2 * S["BORDER"]
    cw = sw * S["SIZE"]
    if cw * src_h / src_w > sh * 0.6:
        cw = sh * 0.6 * src_w / src_h
    cw = int(cw)
    ch = int(cw * src_h / src_w)
    scale = cw / src_w
    cx = (sw - cw) // 2
    cy = (sh - ch) // 2
    at_x = lambda x: cx + (x + S["BORDER"]) * scale
    at_y = lambda y: cy + (y + S["BORDER"]) * scale

    tmp = tempfile.mkdtemp(prefix="pivuan-splash-")
    try:
        # Images scaled to the screen once, as the script does
        asset_scale = cw / identify(os.path.join(a.assets, "logo.png"))[0]
        img = {}
        for name in ["logo", "sweep", "trace-top", "trace-mid", "trace-bot"]:
            img[name] = os.path.join(tmp, name + ".png")
            subprocess.check_call([IM, os.path.join(a.assets, name + ".png"), "-resize", f"{cw}x{ch}!", img[name]])
        size = {}
        for name in ["spark", "spark-red", "flash", "flash-red"]:
            src = os.path.join(a.assets, name + ".png")
            w, h = identify(src)
            w, h = int(w * asset_scale + 0.5), int(h * asset_scale + 0.5)
            img[name] = os.path.join(tmp, name + ".png")
            size[name] = (w, h)
            subprocess.check_call([IM, src, "-resize", f"{w}x{h}!", img[name]])

        def layer(path, x, y, opacity, crop=None):
            if opacity <= 0.003:
                return []
            cmd = ["(", path]
            if crop:
                cmd += ["-crop", f"{crop[1] - crop[0]}x{ch}+{crop[0]}+0", "+repage"]
            if opacity < 0.999:
                cmd += ["-channel", "A", "-evaluate", "multiply", f"{opacity:.4f}", "+channel"]
            return cmd + [")", "-geometry", f"+{int(x)}+{int(y)}", "-composite"]

        band_w = cw * S["SWEEP_BAND"]
        slices = int(S["SWEEP_SLICES"])
        slice_w = int(band_w / slices) + 1
        trail = int(S["TRAIL"])
        trail_op = [(1 - j / (trail + 1)) ** 2 for j in range(trail + 1)]

        def trace_layers(tr, time):
            out = []
            run = time - tr["delay"]
            head = run * S["SPEED"]
            glow = flash = 0.0
            if run >= 0 and head <= tr["length"]:
                glow = S["TRACE_GLOW"]
            after = run - tr["length"] / S["SPEED"]
            if 0 <= after < S["FLASH_TIME"]:
                flash = (1 - after / S["FLASH_TIME"]) ** 2
                glow = max(glow, flash)
            out += layer(img["trace-" + tr["name"]], cx, cy, glow)
            f = "flash-red" if tr["red"] else "flash"
            out += layer(img[f], at_x(tr["ring"][0]) - size[f][0] / 2, at_y(tr["ring"][1]) - size[f][1] / 2, flash)
            s = "spark-red" if tr["red"] else "spark"
            for j in reversed(range(trail + 1)):
                d = head - j * S["TRAIL_GAP"]
                if run >= 0 and 0 <= d <= tr["length"]:
                    k = 1
                    while k < len(tr["pts"]) - 1 and tr["at"][k] < d:
                        k += 1
                    part = (d - tr["at"][k - 1]) / (tr["at"][k] - tr["at"][k - 1])
                    (x0, y0), (x1, y1) = tr["pts"][k - 1], tr["pts"][k]
                    x, y = x0 + (x1 - x0) * part, y0 + (y1 - y0) * part
                    out += layer(img[s], at_x(x) - size[s][0] / 2, at_y(y) - size[s][1] / 2, trail_op[j])
            return out

        sweep_start = 0 if a.mode in ("boot", "resume") else S["SWEEP_TIME"] + S["BRIGHTEN_TIME"]
        total = (S["SWEEP_TIME"] + S["BRIGHTEN_TIME"] + a.rounds * S["CYCLE"]) if sweep_start == 0 \
            else a.rounds * S["CYCLE"]
        frames = int(total * a.fps)

        def frame_cmd(i):
            time = i / a.fps + sweep_start
            cmd = [IM, "-size", f"{sw}x{sh}", "xc:black", "-colorspace", "sRGB", "-type", "TrueColor"]
            if time < S["SWEEP_TIME"]:
                p = min(max(time / S["SWEEP_TIME"], 0), 1)
                p = p * p * (3 - 2 * p)
                edge = -band_w / 2 + p * (cw + band_w)
                cut = min(max(int(edge), 0), cw)
                if cut > 0:
                    cmd += layer(img["logo"], cx, cy, S["DIM"], (0, cut))
                for j in range(slices):
                    x0 = int(edge - band_w / 2 + j * slice_w)
                    x1 = min(x0 + slice_w, cw)
                    x0 = max(x0, 0)
                    if x1 > x0:
                        op = 1 - abs(j - (slices - 1) / 2) / (slices / 2)
                        cmd += layer(img["sweep"], cx + x0, cy, op, (x0, x1))
            elif time < S["SWEEP_TIME"] + S["BRIGHTEN_TIME"]:
                cmd += layer(img["logo"], cx, cy, S["DIM"] + (1 - S["DIM"]) * (time - S["SWEEP_TIME"]) / S["BRIGHTEN_TIME"])
            else:
                cmd += layer(img["logo"], cx, cy, 1)
                t = time - S["SWEEP_TIME"] - S["BRIGHTEN_TIME"]
                rnd = t - int(t / S["CYCLE"]) * S["CYCLE"]
                for tr in traces:
                    cmd += trace_layers(tr, rnd)
            return cmd + ["-alpha", "off", "-type", "TrueColor", os.path.join(tmp, f"frame-{i:05d}.png")]

        with concurrent.futures.ThreadPoolExecutor(os.cpu_count()) as ex:
            list(ex.map(lambda i: subprocess.check_call(frame_cmd(i)), range(frames)))

        # One palette for all frames; "-layers Optimize" would turn the GIF grey
        subprocess.check_call([IM, "-delay", f"{100 / a.fps:.2f}", "-loop", "0",
                               *sorted(os.path.join(tmp, f) for f in os.listdir(tmp) if f.startswith("frame-")),
                               "-colorspace", "sRGB", "+remap", "-layers", "OptimizeFrame", a.output])
        print(f"{a.output}: {frames} frames, {sw}x{sh}, {a.fps} fps")
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    sys.exit(main())
