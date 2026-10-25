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

    def repo_line(group, name, path, ref, args):
        commit = git(path, "rev-parse", ref + "^{commit}")
        rel = path.relative_to(third_party)
        return "  ".join(["repo", group, name, str(rel), commit, ref, *args]).rstrip()

    missing = []
    for n in kept:
        name = base(n)
        p = packages[n]
        path = builder / "src" / n
        group = lists.get(name)
        if group:
            ref = newest_tag(path, series[group])
            if not ref:
                missing.append(f"{name} (no {series[group]} tag)")
                continue
        else:
            ref = p["git"]["ref"]
            group = "frameworks" if ("frameworks" in name or "library" in name
                                     or name in ("qcoro6", "sonic-polkit")) else "apps"
        lines.append(repo_line(group, name, path, ref, p.get("cmake_extra_args", [])))

        # The rebuilt libraries need only Qt and the CMake modules: build them straight after
        if name == "sonic-frameworks-cmake-modules":
            for extra_name, url, tag, *args in conf["extra"]:
                path = extra_root / extra_name
                if not path.exists():
                    extra_root.mkdir(exist_ok=True)
                    subprocess.run(["git", "clone", "--quiet", url, str(path)], check=True)
                elif subprocess.run(["git", "-C", str(path), "rev-parse", "-q", "--verify",
                                     f"refs/tags/{tag}"], capture_output=True).returncode:
                    git(path, "fetch", "--quiet", "--tags", "origin")
                # Submodules (KDSoap's libkode): build-sonicde.sh takes them from the checkout
                if (path / ".gitmodules").exists() or subprocess.run(
                        ["git", "-C", str(path), "cat-file", "-e", f"refs/tags/{tag}:.gitmodules"],
                        capture_output=True).returncode == 0:
                    git(path, "checkout", "--quiet", "--detach", f"refs/tags/{tag}")
                    git(path, "submodule", "--quiet", "update", "--init", "--recursive")
                lines.append(repo_line("frameworks", extra_name, path, f"refs/tags/{tag}", args))

    if missing:
        sys.exit("No tag in the release series for:\n  " + "\n  ".join(missing))

    lock_path.write_text("\n".join(lines) + "\n")
    repos = sum(1 for line in lines if line.startswith("repo"))
    print(f"{lock_path}: {repos} repos, {len(os_packages)} OS packages")


if __name__ == "__main__":
    main()
