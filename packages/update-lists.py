#!/usr/bin/env python3
#
# Write the Pivuan package lists (packages/*.md) from the sources that decide them:
# - the image: the build's own package aggregation (rations/build lib/tools/aggregation.py) for
#   the "Pivuan image build" workflow's settings, the image-time extras from
#   `compile.sh config-dump-json`, and the Raspberry Pi firmware the bcm2711 family installs;
# - the desktops: configng's parse_desktop_yaml.py, as pivuan-config runs it;
# - the Pivuan apt repository: its arm64 Packages index on the gh-pages branch.
# The lists name the packages Pivuan asks for, not the dependencies apt adds.
#
# Usage, from this repository (rations/pivuan), with ../build and ../configng next to it:
#   packages/update-lists.py
# BUILD_DIR and CONFIGNG_DIR point elsewhere. Needs python3-yaml (for configng's parser) and,
# for descriptions, apt-cache (any Devuan excalibur or Debian trixie machine).
#
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILD = os.path.abspath(os.environ.get("BUILD_DIR", os.path.join(REPO, "..", "build")))
CONFIGNG = os.path.abspath(os.environ.get("CONFIGNG_DIR", os.path.join(REPO, "..", "configng")))

# The image the "Pivuan image build" workflow makes (build .github/workflows/pivuan-build.yml).
BOARD, BRANCH, RELEASE, BASE, ARCH = "rpi4b", "current", "excalibur", "trixie", "arm64"
PACKAGES_INDEX = f"origin/gh-pages:dists/{RELEASE}/main/binary-{ARCH}/Packages"

# The desktops pivuan-config offers on Pivuan, the order of the README.
DESKTOPS = [
    ("audio", "Pivuan Audio", "pivuan-audio.md", {"minimal": "AUDI01"}),
    ("xfce", "XFCE", "xfce.md", {"minimal": "XFCE01", "mid": "XFCE05", "full": "XFCE06"}),
    ("mate", "MATE", "mate.md", {"minimal": "MATE01", "mid": "MATE05", "full": "MATE06"}),
]
TIERS = ["minimal", "mid", "full"]


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, text=True, capture_output=True, **kw).stdout


def git_head(path):
    try:
        return run(["git", "-C", path, "rev-parse", "--short", "HEAD"]).strip()
    except subprocess.CalledProcessError:
        return "unknown"


# --- the Pivuan apt repository ---------------------------------------------------------------

def repo_packages():
    """Newest version of each package in the Pivuan apt repository: name -> fields."""
    subprocess.run(["git", "-C", REPO, "fetch", "-q", "origin", "gh-pages"], check=False)
    text = run(["git", "-C", REPO, "show", PACKAGES_INDEX])
    newest = {}
    for stanza in text.strip().split("\n\n"):
        fields = {}
        for line in stanza.splitlines():
            m = re.match(r"^([A-Za-z-]+): (.*)$", line)
            if m:
                fields[m.group(1)] = m.group(2)
        name = fields.get("Package")
        if not name:
            continue
        if name in newest:
            older = subprocess.run(["dpkg", "--compare-versions", newest[name]["Version"], "lt", fields["Version"]])
            if older.returncode != 0:
                continue
        newest[name] = fields
    return newest


def depends_names(field):
    """Package names in a Depends field (alternatives included, versions dropped)."""
    names = []
    for part in re.split(r"[,|]", field or ""):
        name = part.strip().split(" ")[0].split(":")[0]
        if name:
            names.append(name)
    return names


# --- the image -------------------------------------------------------------------------------

def dumped_list(value):
    """A bash array from config-dump-json ('[0]="a" [1]="b"', inside a @TODO list)."""
    text = " ".join(value) if isinstance(value, list) else str(value)
    return re.findall(r'\[\d+\]="([^"]*)"', text)


def image_packages():
    """debootstrap, rootfs and image package lists, as the image build aggregates them."""
    dump = run(["./compile.sh", "config-dump-json", f"BOARD={BOARD}", f"BRANCH={BRANCH}", f"RELEASE={RELEASE}",
                "BUILD_MINIMAL=yes", "BUILD_DESKTOP=no", "KERNEL_CONFIGURE=no", "EXPERT=yes", "PREFER_DOCKER=no"],
               cwd=BUILD)
    config = json.loads(dump)
    extra = dumped_list(config.get("EXTRA_PACKAGES_IMAGE", []))
    remove = dumped_list(config.get("REMOVE_PACKAGES", []))
    ref = "update-lists.py:config-dump-json:0"  # aggregation.py wants one file:function:line ref per package
    with tempfile.NamedTemporaryFile("r", suffix=".sh") as out:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "SRC": BUILD, "OUTPUT": out.name,
            "ARCH": ARCH, "RELEASE": RELEASE, "BUILD_MINIMAL": "yes", "BUILD_DESKTOP": "no",
            "SELECTED_CONFIGURATION": "cli_minimal", "USERPATCHES_PATH": os.path.join(BUILD, "userpatches"),
            "LINUXFAMILY": "", "BOARD": "",
            "EXTRA_PACKAGES_IMAGE": " ".join(extra), "EXTRA_PACKAGES_IMAGE_REFS": " ".join([ref] * len(extra)),
            "REMOVE_PACKAGES": " ".join(remove), "REMOVE_PACKAGES_REFS": " ".join([ref] * len(remove)),
            "PACKAGE_LIST_FAMILY": "", "PACKAGE_LIST_BOARD": "",
            "PACKAGE_LIST_FAMILY_REMOVE": "", "PACKAGE_LIST_BOARD_REMOVE": "",
        }
        run([sys.executable, os.path.join(BUILD, "lib/tools/aggregation.py")], env=env, cwd=BUILD)
        lists = run(["bash", "-c", f'. "{out.name}"; '
                     'echo "${AGGREGATED_PACKAGES_DEBOOTSTRAP[*]}"; '
                     'echo "${AGGREGATED_PACKAGES_ROOTFS[*]}"; '
                     'echo "${AGGREGATED_PACKAGES_IMAGE[*]}"']).splitlines()
    debootstrap, rootfs, image = (line.split() for line in lists)
    return debootstrap, rootfs, image


def rpi_firmware():
    """The Wi-Fi and Bluetooth firmware the bcm2711 family installs on Devuan."""
    conf = open(os.path.join(BUILD, "config/sources/families/bcm2711.conf")).read()
    m = re.search(r'"Devuan" \]\]; then.*?chroot_sdcard_apt_get_install ([^\n]+)', conf, re.S)
    return m.group(1).split() if m else []


# --- the desktops ----------------------------------------------------------------------------

def desktop(de, tier):
    out = run([sys.executable, os.path.join(CONFIGNG, "tools/modules/desktops/scripts/parse_desktop_yaml.py"),
               os.path.join(CONFIGNG, "tools/modules/desktops/yaml"), de, RELEASE, ARCH, "--tier", tier])
    values = dict(re.findall(r'^([A-Z_]+)="(.*)"$', out, re.M))
    packages = values.get("DESKTOP_PACKAGES", "").split()
    dm = values.get("DESKTOP_DM", "")
    if dm and dm != "none" and dm not in packages:
        packages.append(dm)
    return packages, values.get("DESKTOP_BRAVE_PKG", "")


# --- descriptions ----------------------------------------------------------------------------

def descriptions(names, repo):
    """Short descriptions: the Pivuan repository's, else apt-cache's (Devuan/Debian)."""
    found = {n: f["Description"] for n, f in repo.items() if n in names}
    missing = sorted(n for n in names if n not in found)
    if missing:
        out = subprocess.run(["apt-cache", "show", "--no-all-versions", *missing],
                             text=True, capture_output=True).stdout
        for stanza in out.split("\n\n"):
            p = re.search(r"^Package: (.+)$", stanza, re.M)
            d = re.search(r"^Description(?:-[a-zA-Z_]+)?: (.+)$", stanza, re.M)
            if p and d:
                found.setdefault(p.group(1), d.group(1))
    return found


# --- Markdown --------------------------------------------------------------------------------

def md_escape(text):
    return text.replace("|", "\\|")


def table(names, desc, source):
    rows = ["| Package | From | Description |", "|---|---|---|"]
    for n in names:
        rows.append(f"| `{n}` | {source(n)} | {md_escape(desc.get(n, ''))} |")
    return "\n".join(rows)


def write(name, text):
    with open(os.path.join(HERE, name), "w") as f:
        f.write(text.rstrip("\n") + "\n")
    print(f"wrote packages/{name}")


def main():
    repo = repo_packages()
    debootstrap, rootfs, image_extra = image_packages()
    firmware = rpi_firmware()
    pivuan_image = sorted(n for n in repo
                          if n == "pivuan-config"
                          or n in (f"linux-image-{BRANCH}-bcm2711", f"linux-dtb-{BRANCH}-bcm2711")
                          or n.startswith(f"armbian-bsp-cli-{BOARD}-{BRANCH}"))

    tiers = {}
    brave = {}
    for de, _, _, commands in DESKTOPS:
        for tier in commands:
            tiers[(de, tier)], brave[de] = desktop(de, tier)

    every = set(debootstrap) | set(rootfs) | set(image_extra) | set(firmware) | set(repo)
    for (de, tier), pkgs in tiers.items():
        every |= set(pkgs)
    every |= {b for b in brave.values() if b}
    desc = descriptions(every, repo)

    def source(n):
        if n in repo:
            return "Pivuan"
        if n in brave.values():
            return "Brave"
        return "Devuan"

    pages = run(["git", "-C", REPO, "rev-parse", "--short", "origin/gh-pages"]).strip()
    stamp = (f"Generated by `packages/update-lists.py` from rations/build `{git_head(BUILD)}`, "
             f"rations/configng `{git_head(CONFIGNG)}` and the apt repository (gh-pages `{pages}`). "
             "Do not edit by hand.")

    # image.md
    image_parts = [
        "# Packages in the Pivuan image",
        "",
        f"The packages the image build asks for (board `{BOARD}`, kernel branch `{BRANCH}`, Devuan "
        f"{RELEASE}, minimal image). apt adds their dependencies. Everything comes from the Devuan "
        "archive except the packages marked Pivuan, from the Pivuan apt repository.",
        "",
        stamp,
        "",
        "## Base system (debootstrap)",
        "",
        table(debootstrap, desc, source),
        "",
        "## System packages",
        "",
        table([p for p in rootfs if p not in debootstrap], desc, source),
        "",
        "## Networking and time",
        "",
        table([p for p in image_extra if p not in rootfs], desc, source),
        "",
        "## Raspberry Pi Wi-Fi and Bluetooth firmware",
        "",
        table(firmware, desc, source),
        "",
        "## Kernel, board support and pivuan-config",
        "",
        table(pivuan_image, desc, source),
    ]
    write("image.md", "\n".join(image_parts))

    # One file per desktop.
    for de, title, filename, commands in DESKTOPS:
        parts = [f"# Packages of {title}", "",
                 f"The packages `pivuan-config` installs for {title}. apt adds their dependencies.", "",
                 stamp, ""]
        before = []
        for tier in TIERS:
            if tier not in commands:
                continue
            pkgs = tiers[(de, tier)]
            added = [p for p in pkgs if p not in before]
            command = f"`sudo pivuan-config --cmd {commands[tier]}`"
            if len(commands) == 1:
                parts += [f"## {command}", ""]
            elif not before:
                parts += [f"## Minimal: {command}", ""]
            else:
                parts += [f"## {tier.capitalize()}: {command}", "",
                          f"Everything in the {TIERS[TIERS.index(tier) - 1]} tier, and:", ""]
            parts += [table(added, desc, source), ""]
            before = pkgs
        if brave.get(de):
            parts += ["## Browser", "",
                      f"From [Brave's apt repository](https://brave.com/linux/), which `pivuan-config` adds.", "",
                      table([brave[de]], desc, source), ""]
        write(filename, "\n".join(parts))

    # apt-repository.md: what each package is for.
    users = {n: [] for n in repo}
    for n in pivuan_image:
        users[n].append("the image")
    for de, title, _, commands in DESKTOPS:
        pkgs = set()
        for tier in commands:
            pkgs |= set(tiers[(de, tier)])
        for n in sorted(pkgs & set(repo)):
            users[n].append(title)
    needed_by = {n: [] for n in repo}
    for n, f in sorted(repo.items()):
        for dep in depends_names(f.get("Depends")) + depends_names(f.get("Pre-Depends")):
            if dep in repo and dep != n and n not in needed_by[dep]:
                needed_by[dep].append(n)
    rows = ["| Package | Version | Used by | Description |", "|---|---|---|---|"]
    for n, f in sorted(repo.items()):
        used = users[n] + (["needed by " + ", ".join(f"`{d}`" for d in needed_by[n])] if needed_by[n] else [])
        used = ", ".join(used) or "nothing (kept in the repository)"
        rows.append(f"| `{n}` | `{f['Version']}` | {used} | {md_escape(f.get('Description', ''))} |")
    write("apt-repository.md", "\n".join([
        "# Packages in the Pivuan apt repository",
        "",
        f"The newest version of each package at https://rations.github.io/pivuan (suite `{RELEASE}`, "
        f"`{ARCH}`). The repository keeps the last 3 versions of each.",
        "",
        stamp,
        "",
        "\n".join(rows),
    ]))


if __name__ == "__main__":
    main()
