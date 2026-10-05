#!/usr/bin/env python3
"""Extract the HVIF vector icons embedded in Haiku's resource definitions.

Haiku keeps many icons only inside resource files: the .rdef files of its apps,
preferences and servers, and the MIME database (src/data/mime_db, rdef syntax
without the extension). Each icon is a block like

    resource vector_icon { $"6E636966..." }
    resource(R_TrashIcon) #'VICN' array { $"6E636966..." }

whose hex strings, joined, are a plain HVIF file ("ncif").

Usage: extract_rdef.py <haiku-src> <out-dir>

Writes <out-dir>/rdef/<name>.hvif, <out-dir>/mime/<type>[-<subtype>].hvif and
<out-dir>/manifest.json (icon id -> source file and resource, for credits).
"""

import json
import re
import sys
from pathlib import Path

BLOCK = re.compile(
    r"resource\s*(?:\((?P<id>[^)]*)\))?\s*"
    r"(?:vector_icon(?:\s+array)?|#'VICN'\s+array)\s*\{(?P<body>.*?)\}",
    re.S)
HEX = re.compile(r'\$"([0-9A-Fa-f]*)"')
HVIF_MAGIC = b"ncif"
# Resource names that only say "this is the icon" and add nothing to the file name.
GENERIC_NAMES = {"BEOS:ICON", "META:ICON"}
# Macros taken as defined when resolving #ifdef. HAIKU_OFFICIAL_RELEASE and
# HAIKU_DISTRO_COMPATIBILITY_OFFICIAL stay undefined: their branches hold the
# trademarked Haiku logo icons, and the #else branches the unofficial-build ones.
DEFINED = {"HAIKU_TARGET_PLATFORM_HAIKU"}
DIRECTIVE = re.compile(r"\s*#\s*(ifdef|ifndef|else|endif)\b\s*(\w*)")


def preprocess(text):
    """Keep only the lines that the active #ifdef branches select."""
    stack, kept = [], []
    for line in text.splitlines():
        m = DIRECTIVE.match(line)
        if not m:
            if all(stack):
                kept.append(line)
            continue
        kind, macro = m.groups()
        if kind in ("ifdef", "ifndef"):
            stack.append((macro in DEFINED) == (kind == "ifdef"))
        elif kind == "else":
            stack[-1] = not stack[-1]
        else:
            stack.pop()
    return "\n".join(kept)


def resource_label(res_id):
    """A short label for a resource id: its quoted name or symbolic id."""
    if not res_id:
        return ""
    quoted = re.search(r'"([^"]*)"', res_id)
    if quoted:
        name = quoted.group(1)
        return "" if name in GENERIC_NAMES else name
    first = res_id.split(",")[0].strip()
    return "" if first.isdigit() else first


def icons_in(path):
    """Yield (label, hvif bytes) for each vector icon in a resource file."""
    text = preprocess(path.read_text(encoding="utf-8", errors="replace"))
    for m in BLOCK.finditer(text):
        data = bytes.fromhex("".join(HEX.findall(m.group("body"))))
        if data[:4] == HVIF_MAGIC:
            yield resource_label(m.group("id")), data


def safe(name):
    return re.sub(r"[^A-Za-z0-9._+-]+", "_", name).strip("_")


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    manifest = {}

    def emit(icon_id, data, source, label):
        if icon_id in manifest:
            sys.exit(f"duplicate icon id {icon_id}: {source} and {manifest[icon_id]['source']}")
        target = out / (icon_id + ".hvif")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_bytes() != data:
            target.write_bytes(data)
        manifest[icon_id] = {"source": str(source.relative_to(src)), "resource": label}

    # MIME database: the file path is the MIME type ("text/plain", "image.super").
    mime_db = src / "src/data/mime_db"
    for path in sorted(p for p in mime_db.rglob("*") if p.is_file()):
        found = list(icons_in(path))
        if not found:
            continue
        mime = path.relative_to(mime_db).as_posix()
        mime = mime[:-len(".super")] if mime.endswith(".super") else mime
        emit("mime/" + mime.replace("/", "-"), found[0][1], path, found[0][0])

    # App, preferences, server and kit resources. Tests are left out.
    rdefs = sorted(p for p in (src / "src").rglob("*.rdef")
                   if "tests" not in p.relative_to(src).parts)
    entries = []
    for path in rdefs:
        found = list(icons_in(path))
        for label, data in found:
            name = path.stem if len(found) == 1 or not label else f"{path.stem}.{label}"
            entries.append((safe(name), path, label, data))
    # The same file name in two directories (e.g. two "Icons.rdef"): prefix the directory.
    counts = {}
    for name, *_ in entries:
        counts[name] = counts.get(name, 0) + 1
    for name, path, label, data in entries:
        if counts[name] > 1:
            name = safe(path.parent.name + "_" + name)
        emit("rdef/" + name, data, path, label)

    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    kinds = {}
    for icon_id in manifest:
        kinds[icon_id.split("/")[0]] = kinds.get(icon_id.split("/")[0], 0) + 1
    print("extracted " + ", ".join(f"{n} {k}" for k, n in sorted(kinds.items())))


if __name__ == "__main__":
    main()
