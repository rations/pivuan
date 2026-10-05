#!/usr/bin/env python3
"""Build the freedesktop icon theme from Haiku's icons.

Reads mapping/icons.toml (freedesktop name -> Haiku source icon) and
mapping/exclude.txt, converts every source used with icon2icon (one SVG for
scalable/, one PNG per fixed size, drawn with the shapes Haiku draws at that
size), and lays out <build>/theme/<name>/ with index.theme, symlinks for names
that share an icon, and the license and credit files.

Usage: build_theme.py --haiku-src DIR --build DIR --icon2icon PATH
                      --name NAME [--comment TEXT] [--sizes "16 22 ..."]
                      [--inherits Numix,Adwaita,hicolor]
"""

import argparse
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tomllib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONTEXTS = {
    "actions": "Actions",
    "apps": "Applications",
    "categories": "Categories",
    "devices": "Devices",
    "emblems": "Emblems",
    "mimetypes": "MimeTypes",
    "places": "Places",
    "status": "Status",
}
ARTWORK = "data/artwork/icons"


class Sources:
    """Where each source id ("artwork:X", "rdef:X", "mime:X") lives."""

    def __init__(self, haiku_src, build):
        self.haiku_src = Path(haiku_src)
        self.extracted = Path(build) / "src"
        manifest = json.loads((self.extracted / "manifest.json").read_text())
        self.origin = {}  # id -> path in the Haiku tree (for exclusions and credits)
        self.resource = {}  # id -> resource name inside a file holding several icons
        for key, info in manifest.items():
            kind, name = key.split("/", 1)
            self.origin[f"{kind}:{name}"] = info["source"]
            if info["resource"]:
                self.resource[f"{kind}:{name}"] = info["resource"]
        for path in (self.haiku_src / ARTWORK).rglob("*"):
            if path.is_file():
                rel = path.relative_to(self.haiku_src / ARTWORK).as_posix()
                self.origin["artwork:" + rel] = f"{ARTWORK}/{rel}"

    def path(self, source):
        kind, name = source.split(":", 1)
        if kind == "artwork":
            return self.haiku_src / ARTWORK / name
        return self.extracted / kind / (name + ".hvif")


def load_exclusions(path):
    lines = path.read_text().splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def is_excluded(source, origin, patterns):
    return any(fnmatch.fnmatchcase(source, p) or fnmatch.fnmatchcase(origin, p) for p in patterns)


def mime_icon_name(source):
    """mime:text-plain -> text-plain; a supertype (mime:image) -> image-x-generic."""
    name = source.split(":", 1)[1]
    return name if "-" in name else name + "-x-generic"


def load_mapping(sources, mapping_file):
    """Return {context: {name: source}}, the mapping plus the MIME database icons."""
    mapping = tomllib.loads(Path(mapping_file).read_text())
    unknown = sorted(set(mapping) - set(CONTEXTS))
    if unknown:
        sys.exit(f"{mapping_file}: unknown context(s): {', '.join(unknown)}")
    mimetypes = mapping.setdefault("mimetypes", {})
    for source in sorted(s for s in sources.origin if s.startswith("mime:")):
        name = mime_icon_name(source)
        if "x-vnd." not in name:
            mimetypes.setdefault(name, source)
    return mapping


def check_sources(mapping, sources, patterns):
    errors = []
    for context, names in mapping.items():
        for name, source in names.items():
            where = f"[{context}] {name} = {source!r}"
            if source not in sources.origin:
                errors.append(f"{where}: no such source icon")
            elif is_excluded(source, sources.origin[source], patterns):
                errors.append(f"{where}: excluded by mapping/exclude.txt")
    if errors:
        sys.exit("mapping errors:\n  " + "\n  ".join(errors))


def convert_all(jobs, icon2icon, workers):
    """Run icon2icon for (input, output, args) jobs whose output is out of date."""
    tool_time = Path(icon2icon).stat().st_mtime

    def run(job):
        src, out, args = job
        if out.exists() and out.stat().st_mtime >= max(src.stat().st_mtime, tool_time):
            return None
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(out.name + ".tmp")
        result = subprocess.run([icon2icon, str(src), str(tmp), *args],
                                capture_output=True, text=True)
        if result.returncode != 0 or not tmp.exists():
            return f"{src}: {(result.stderr or result.stdout).strip()}"
        tmp.replace(out)
        return None

    with ThreadPoolExecutor(workers) as pool:
        failures = [f for f in pool.map(run, jobs) if f]
    if failures:
        sys.exit("conversion failed:\n  " + "\n  ".join(failures))


def cache_name(source):
    return source.replace(":", "/")


def haiku_commit(haiku_src):
    result = subprocess.run(["git", "-C", str(haiku_src), "rev-parse", "HEAD"],
                            capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def write_index(theme, name, comment, inherits, dirs):
    def key(d):
        size = d.split("/")[0]
        # Fixed sizes first, small to large, then scalable: GTK keeps the first
        # directory among equally good matches, so an exact size wins over scalable.
        return (size == "scalable", int(size.split("x")[0]) if size != "scalable" else 0, d)

    dirs = sorted(dirs, key=key)
    lines = [
        "[Icon Theme]",
        f"Name={name}",
        f"Comment={comment}",
        f"Inherits={inherits}",
        "Example=folder",
        "Directories=" + ",".join(dirs),
        "",
    ]
    for d in dirs:
        size, context = d.split("/")
        lines.append(f"[{d}]")
        if size == "scalable":
            lines += ["Size=64", "MinSize=8", "MaxSize=512", "Type=Scalable"]
        else:
            lines += [f"Size={size.split('x')[0]}", "Type=Fixed"]
        lines += [f"Context={CONTEXTS[context]}", ""]
    (theme / "index.theme").write_text("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--haiku-src", required=True)
    ap.add_argument("--build", required=True)
    ap.add_argument("--icon2icon", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--comment", default="Haiku's vector icons (unofficial)")
    ap.add_argument("--sizes", default="16 22 24 32 48 64 128 256")
    ap.add_argument("--inherits", default="Numix,Adwaita,hicolor")
    ap.add_argument("--mapping", default=str(REPO / "mapping/icons.toml"))
    ap.add_argument("--exclude", default=str(REPO / "mapping/exclude.txt"))
    args = ap.parse_args()

    build = Path(args.build)
    sizes = [int(s) for s in args.sizes.split()]
    sources = Sources(args.haiku_src, build)
    mapping = load_mapping(sources, args.mapping)
    check_sources(mapping, sources, load_exclusions(Path(args.exclude)))

    used = sorted({s for names in mapping.values() for s in names.values()})
    cache = build / "cache"
    jobs = []
    for source in used:
        src = sources.path(source)
        jobs.append((src, cache / "svg" / (cache_name(source) + ".svg"), ["-f", "svg"]))
        for n in sizes:
            jobs.append((src, cache / "png" / str(n) / (cache_name(source) + ".png"),
                         ["-f", "png", "--width", str(n), "--height", str(n),
                          "--lod-scale", f"{n / 64:g}"]))
    convert_all(jobs, args.icon2icon, os.cpu_count() or 2)

    theme = build / "theme" / args.name
    if theme.exists():
        shutil.rmtree(theme)
    dirs, real, lines = set(), {}, []
    for size_dir, ext, sub in [("scalable", "svg", "svg")] + [
            (f"{n}x{n}", "png", f"png/{n}") for n in sizes]:
        real.clear()  # source -> (context, file name) of its real file in this size
        for context in sorted(mapping):
            for name, source in sorted(mapping[context].items()):
                target_dir = theme / size_dir / context
                target_dir.mkdir(parents=True, exist_ok=True)
                target = target_dir / f"{name}.{ext}"
                if source in real:
                    ctx, file = real[source]
                    target.symlink_to(file if ctx == context else f"../{ctx}/{file}")
                else:
                    shutil.copyfile(cache / sub / (cache_name(source) + "." + ext), target)
                    real[source] = (context, target.name)
                    if size_dir == "scalable":
                        where = sources.origin[source]
                        if source in sources.resource:
                            where += f" (resource {sources.resource[source]})"
                        lines.append(f"{context}/{name}\t{where}")
                dirs.add(f"{size_dir}/{context}")

    write_index(theme, args.name, args.comment, args.inherits, dirs)
    commit = haiku_commit(args.haiku_src)
    (theme / "SOURCES").write_text(
        f"Icons converted from Haiku (https://www.haiku-os.org), commit {commit}.\n"
        "Each icon below is listed with the file of the Haiku source tree it comes from;\n"
        "names that share an icon are symlinks to it.\n\n" + "\n".join(lines) + "\n")
    for f in ("LICENSE", "CREDITS.md"):
        shutil.copyfile(REPO / f, theme / f)

    names = sum(len(n) for n in mapping.values())
    print(f"{theme}: {names} names, {len(used)} icons, {len(dirs)} directories")


if __name__ == "__main__":
    main()
