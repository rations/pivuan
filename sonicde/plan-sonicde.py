#!/usr/bin/env python3
"""Write sonicde.lock: every repo SonicDE is built from, in build order, at a fixed commit.

Usage (on the PC as yourself, not in the build root): sonicde/plan-sonicde.py

Reads sonicde.conf and the SonicDE builder in ~/third_party/sonic-de/sonicde-builder (checked out
at the conf's builder commit, sources fetched with its ./fetch-all). Clones the conf's extra
libraries into ~/third_party/sonicde-extra. Then writes sonicde.lock, which build-sonicde.sh
builds from inside the root (~/third_party is /third_party there):

    os    <Devuan package>...
    repo  <group> <name> <dir under ~/third_party> <commit> <ref> [CMake option...]

group is frameworks, workspace or apps: the .deb the repo goes into. Commit sonicde.lock with a
release, so the same sources can be built again.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
third_party = Path.home() / "third_party"
builder = third_party / "sonic-de" / "sonicde-builder"
extra_root = third_party / "sonicde-extra"
lock_path = here / "sonicde.lock"

# The builder's Devuan names that excalibur spells differently, and OS packages Pivuan builds
# itself (they link to Devuan's Qt 6.8) or leaves out
OS_RENAME = {"libnl-3.0-dev": "libnl-3-dev libnl-route-3-dev"}
OS_REPLACED = {"qtkeychain-qt6-dev", "libkdsoapwsdiscoveryclient-qt6-dev", "libkpmcore-dev"}


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, text=True,
                          capture_output=True).stdout.strip()


def read_conf():
    conf = {"extra": [], "skip": set(), "os": []}
    for line in (here / "sonicde.conf").read_text().splitlines():
        line = line.split("#", 1)[0].split()
        if not line:
            continue
        key, values = line[0], line[1:]
        if key == "extra":
            conf["extra"].append(values)
        elif key == "skip":
            conf["skip"].add(values[0])
        elif key == "os":
            conf["os"] += values
        else:
            conf[key] = values[0]
    return conf


def newest_tag(repo, series):
    """The newest origin tag in a release series: 6.8.0 matches 6.8.0 and 6.8.0.2, not 6.8.01."""
    pattern = re.compile(r"origin/" + re.escape(series) + r"(\.\d+)*$")
    tags = [t for t in git(repo, "tag", "-l", "origin/*").splitlines() if pattern.match(t)]
    if not tags:
        return None
    return sorted(tags, key=lambda t: [int(x) for x in t.split("/", 1)[1].split(".")])[-1]


CMAKE_KEYWORDS = {"REQUIRED", "OPTIONAL", "COMPONENTS", "OPTIONAL_COMPONENTS", "CONFIG", "MODULE",
                  "QUIET", "NO_MODULE", "EXACT", "GLOBAL", "NAMES", "HINTS", "PATHS"}


def cmake_packages(repo, commit):
    """What a repo's CMake files provide (its *Config.cmake.in) and look for (find_package and
    find_dependency, KF6/Qt6 components expanded), at a commit. Tests and examples are left out."""
    listing = git(repo, "ls-tree", "-r", commit).splitlines()
    provides, blobs = set(), []
    for line in listing:
        meta, path = line.split("\t", 1)
        name = path.rsplit("/", 1)[-1]
        for suffix in ("Config.cmake.in", "-config.cmake.in"):
            if name.endswith(suffix) and len(name) > len(suffix):
                provides.add(name[:-len(suffix)])
        if re.search(r"(^|/)(autotests|tests|examples)/", path):
            continue
        if name == "CMakeLists.txt" or name.endswith((".cmake", ".cmake.in")):
            blobs.append(meta.split()[2])
    text = subprocess.run(["git", "-C", str(repo), "cat-file", "--batch"], input="\n".join(blobs),
                          check=True, text=True, capture_output=True, errors="replace").stdout
    wants = set()
    for call in re.finditer(r"\b(?:find_package|find_dependency)\s*\(([^)]*)\)", text, re.I):
        words = [w for w in call.group(1).split() if not w.startswith("$") and not w[0].isdigit()]
        if not words:
            continue
        name, rest = words[0], words[1:]
        if name in ("KF6", "Qt6") and any(w in rest for w in ("COMPONENTS", "OPTIONAL_COMPONENTS")):
            wants.update(name + w for w in rest if w not in CMAKE_KEYWORDS)
        else:
            wants.add(name)
    return provides, wants


def build_order(names, edges):
    """names in an order where each comes after what it needs; ties keep the given order, and a
    dependency cycle is broken at the earliest name (reported)."""
    index = {n: i for i, n in enumerate(names)}
    needs = {n: {d for d in edges.get(n, ()) if d in index and d != n} for n in names}
    order, placed = [], set()
    while len(order) < len(names):
        ready = [n for n in names if n not in placed and needs[n] <= placed]
        if not ready:
            stuck = min((n for n in names if n not in placed), key=index.get)
            print(f"note: dependency cycle at {stuck.split('/')[-1]} (needs "
                  f"{', '.join(sorted(d.split('/')[-1] for d in needs[stuck] - placed))})",
                  file=sys.stderr)
            ready = [stuck]
        order.append(ready[0])
        placed.add(ready[0])
    return order


def main():
    conf = read_conf()
    head = git(builder, "rev-parse", "HEAD")
    if head != conf["builder"]:
        sys.exit(f"{builder} is at {head[:12]}, sonicde.conf pins {conf['builder'][:12]}:\n"
                 f"  git -C {builder} checkout {conf['builder']}")

    model_path = third_party / "sonic-de" / "model.json"
    subprocess.run([sys.executable, "scripts/config.py", "-root", ".", "-solution",
                    "config/sonicde/solutions/sonicde.yaml", "-out", str(model_path)],
                   cwd=builder, check=True, stdout=subprocess.DEVNULL)
    model = json.loads(model_path.read_text())
    packages = model["packages"]
    # Dependencies name a package or something it provides (sys/libdrm)
    for name, p in list(packages.items()):
        for alias in p.get("provides", []):
            packages.setdefault(alias, p)

    lists = {}
    for group, name in (("workspace", "plasma"), ("frameworks", "frameworks"), ("apps", "system")):
        for line in (builder / "scripts" / f"version-repos-{name}.list").read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                lists[line.split("/")[-1]] = group
    series = {"workspace": conf["core"], "frameworks": conf["frameworks"], "apps": conf["system"]}

    def base(name):
        return name.split("/")[-1]

    for name in conf["skip"]:
        if "sonicde/" + name not in packages:
            sys.exit(f"skip {name}: not in the builder's solution")

    # The repos to build: everything the solution builds, less the skipped ones. A kept repo
    # that needs a skipped one is reported (the pyside build dependencies are expected).
    kept = [n for n in model["topo_order"]
            if packages[n].get("type") != "system" and base(n) not in conf["skip"]
            and packages[n].get("buildsystem") == "cmake"]
    for n in kept:
        p = packages[n]
        lost = [base(d) for d in p.get("depends", []) + p.get("build_depends", [])
                if base(d) in conf["skip"] and base(d) != "sonic-pyside"]
        if lost:
            print(f"note: {base(n)} uses skipped {', '.join(lost)}", file=sys.stderr)

    lines = ["# Written by plan-sonicde.py from sonicde.conf; do not edit by hand.", ""]

    os_packages = []
    for n in kept:
        for d in packages[n].get("depends", []) + packages[n].get("build_depends", []):
            p = packages.get(d, {})
            if p.get("type") != "system":
                continue
            pp = p.get("platform_packages", {})
            name = pp.get("devuan") or pp.get("debian")
            if name and name not in OS_REPLACED:
                os_packages += OS_RENAME.get(name, name).split()
    os_packages = sorted(set(os_packages) | set(conf["os"]))
    for i in range(0, len(os_packages), 8):
        lines.append("os  " + " ".join(os_packages[i:i + 8]))
    lines.append("")

    # Every repo: group, checkout, ref, commit, CMake options
    repos = {}
    missing = []
    for n in kept:
        name = base(n)
        path = builder / "src" / n
        group = lists.get(name)
        if group:
            ref = newest_tag(path, series[group])
            if not ref:
                missing.append(f"{name} (no {series[group]} tag)")
                continue
        else:
            ref = packages[n]["git"]["ref"]
            group = "frameworks" if ("frameworks" in name or "library" in name
                                     or name in ("qcoro6", "sonic-polkit")) else "apps"
        repos[name] = (group, path, ref, packages[n].get("cmake_extra_args", []))
    if missing:
        sys.exit("No tag in the release series for:\n  " + "\n  ".join(missing))

    # The rebuilt libraries need only Qt and the CMake modules: build them straight after
    names = [base(n) for n in kept if base(n) in repos]
    at = names.index("sonic-frameworks-cmake-modules") + 1
    for extra_name, url, tag, *args in conf["extra"]:
        path = extra_root / extra_name
        if not path.exists():
            extra_root.mkdir(exist_ok=True)
            subprocess.run(["git", "clone", "--quiet", url, str(path)], check=True)
        elif subprocess.run(["git", "-C", str(path), "rev-parse", "-q", "--verify",
                             f"refs/tags/{tag}"], capture_output=True).returncode:
            git(path, "fetch", "--quiet", "--tags", "origin")
        # Submodules (KDSoap's libkode): build-sonicde.sh takes them from the checkout
        if subprocess.run(["git", "-C", str(path), "cat-file", "-e", f"refs/tags/{tag}:.gitmodules"],
                          capture_output=True).returncode == 0:
            git(path, "checkout", "--quiet", "--detach", f"refs/tags/{tag}")
            git(path, "submodule", "--quiet", "update", "--init", "--recursive")
        repos[extra_name] = ("frameworks", path, f"refs/tags/{tag}", args)
        names.insert(at, extra_name)
        at += 1
    commits = {name: git(path, "rev-parse", ref + "^{commit}")
               for name, (_, path, ref, _) in repos.items()}

    # Build order: the builder's dependencies are incomplete (sonic-activities needs KConfig but
    # does not say so), so add what each repo's CMake files look for from another repo
    edges = {name: set() for name in names}
    for n in kept:
        if base(n) in edges:
            edges[base(n)].update(base(d) for d in packages[n].get("depends", [])
                                  + packages[n].get("build_depends", []))
    provider, wants = {}, {}
    for name in names:
        provides, wants[name] = cmake_packages(repos[name][1], commits[name])
        for package in provides:
            provider.setdefault(package, name)
    for name in names:
        edges[name].update(provider[w] for w in wants[name] if w in provider)
    order = build_order(names, edges)

    for name in order:
        group, path, ref, args = repos[name]
        lines.append("  ".join(["repo", group, name, str(path.relative_to(third_party)),
                                commits[name], ref, *args]).rstrip())

    lock_path.write_text("\n".join(lines) + "\n")
    print(f"{lock_path}: {len(order)} repos, {len(os_packages)} OS packages")


if __name__ == "__main__":
    main()
