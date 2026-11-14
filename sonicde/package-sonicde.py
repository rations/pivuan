#!/usr/bin/env python3
"""Make SonicDE's .debs from /opt/sonicde, as build-qt.sh and build-sonicde.sh installed it.

Usage (inside the build root: enter-root.sh <work-dir> /src/sonicde/package-sonicde.py):
writes /work/debs/<version>/ (<work-dir>/work/debs/<version> on the PC), with the dpkg-shlibdeps
logs in its logs/.

Each installed file goes into a package by the install manifest of the Qt module or repo that
installed it (its group in sonicde.lock), except the big kinds of files that are the same on every
release, which have packages of their own:

    sonicde-qt          Qt
    sonicde-frameworks  SonicDE's frameworks and the libraries rebuilt for its Qt
    sonicde-workspace   the desktop: window manager, shell, settings, themes
    sonicde-apps        file manager, terminal, system log, image editor
    sonicde-icons       icon and cursor themes (share/icons)
    sonicde-l10n        translations (share/locale)
    sonicde-wallpapers  wallpapers (share/wallpapers)
    sonicde             the session (files in session/): LightDM's session entry, links for the
                        system D-Bus and polkit, the screen locker's PAM service; depends on all

Headers, CMake and pkg-config files, static libraries (Highway and libei are only that), Qt's and
the frameworks' developer tools, and systemd units are left out. Generated caches are made on the
Pi instead (the MIME database: session/postinst).

Every package has the version <newest Core tag in sonicde.lock>-pivuan<revision> and depends on
the others at exactly that version: a rebuild with the same Core tag needs a new revision in
sonicde.conf. Depends on Devuan's libraries come from dpkg-shlibdeps, which is why this runs in
the build root, where they are installed.
"""

import collections
import gzip
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
prefix = "/opt/sonicde"
work = Path("/work")
# publish-apt.sh leaves out larger packages (GitHub's file size limit)
MAX_BYTES = 95 * 1024 * 1024
MAINTAINER = "Pivuan <https://github.com/rations/pivuan>"

# Package: section, architecture, the other SonicDE packages it needs, Devuan packages it needs
# that dpkg-shlibdeps cannot see, summary, description
PACKAGES = {
    "sonicde-qt": ("libs", "arm64", [], "",
                   "Qt for SonicDE",
                   "The Qt release SonicDE needs, in /opt/sonicde: Devuan's own Qt in /usr is\n"
                   "left as it is."),
    # kio-fuse runs fusermount3
    "sonicde-frameworks": ("libs", "arm64", ["sonicde-qt", "sonicde-icons"],
                           "fuse3, shared-mime-info",
                           "SonicDE's frameworks",
                           "SonicDE's fork of the KDE Frameworks, and the libraries Pivuan rebuilds\n"
                           "for SonicDE's Qt, in /opt/sonicde."),
    # From SonicDE's Debian packaging (startup, window manager, screen locker) and Pivuan's notes:
    # sonic-screenies reads text with Tesseract, sonic-gtk-theme-bridge hands the theme to GTK
    # programs through xsettingsd and GSettings
    "sonicde-workspace": ("x11", "arm64", ["sonicde-frameworks"],
                          "x11-xserver-utils, x11-utils, xauth, xkb-data, hwdata, iso-codes, psmisc, "
                          "python3, udisks2, upower, accountsservice, polkitd, hicolor-icon-theme, "
                          "xdg-utils, xsettingsd, gsettings-desktop-schemas, tesseract-ocr-eng",
                          "SonicDE desktop",
                          "The SonicDE desktop for X11: window manager, panel and desktop shell,\n"
                          "system settings, screen locker, network, sound, bluetooth and power\n"
                          "applets, and the Silver and Breeze themes."),
    # The file manager's activities and recent-files plugins link Plasma's activity libraries
    "sonicde-apps": ("x11", "arm64", ["sonicde-frameworks", "sonicde-workspace"], "",
                     "SonicDE applications",
                     "SonicDE's file manager (Ecco), terminal, system log viewer and image editor."),
    "sonicde-icons": ("x11", "all", [], "",
                      "SonicDE icon and cursor themes",
                      "The Silver and Breeze icon and cursor themes, in /opt/sonicde."),
    "sonicde-l10n": ("localization", "all", [], "",
                     "SonicDE translations",
                     "Translations of SonicDE's frameworks, desktop and applications."),
    "sonicde-wallpapers": ("x11", "all", [], "",
                           "SonicDE wallpapers",
                           "SonicDE's wallpapers, in /opt/sonicde."),
    # dbus-run-session is in dbus-daemon; Plasma's logout, shutdown and suspend go through logind
    "sonicde": ("x11", "arm64",
                ["sonicde-qt", "sonicde-frameworks", "sonicde-workspace", "sonicde-apps",
                 "sonicde-icons", "sonicde-l10n", "sonicde-wallpapers"],
                "dbus, dbus-daemon, default-logind | logind",
                "SonicDE desktop session",
                "SonicDE, an X11 desktop forked from KDE Plasma, built by Pivuan with its own Qt in\n"
                "/opt/sonicde. This package adds the session to the login screen and installs\n"
                "the whole desktop."),
}

# Qt's programs that are used at run time (scripts call qdbus and qtpaths); the rest are tools
# for building Qt programs
QT_PROGRAMS = {"qdbus", "qtpaths", "qtpaths6", "qtdiag", "qtdiag6", "qml", "qtplugininfo"}
# The same for the frameworks and the rebuilt libraries
DEV_PROGRAMS = {"kdwsdl2cpp-qt6", "meinproc6", "checkXML6", "kconfig_compiler_kf6",
                "ktexteditor-script-tester6", "parsetrigrams6", "ei-debug-events"}
# Libraries released with SonicDE's Apps (their group in the lock picks that release series)
# that the desktop links too
GROUP_OVERRIDE = {"sonic-quick-image-editor": "frameworks", "sonic-exiv2-library": "frameworks"}
# Repos that install only static libraries and headers
STATIC_REPOS = {"highway", "libei"}
DEV_DIRS = ("include/", "lib/cmake/", "lib/pkgconfig/", "lib/aarch64-linux-gnu/pkgconfig/",
            "share/pkgconfig/", "mkspecs/", "metatypes/", "modules/", "sbom/", "doc/",
            "lib/objects-Release/", "lib/systemd/", "lib/tmpfiles.d/", "share/ECM/",
            "share/kdevappwizard/", "share/qt6/", "qml/Qt/test/")


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kwargs).stdout


def git(repo, *args):
    return run("git", "-c", "safe.directory=*", "-C", str(repo), *args)


def read_conf():
    conf = {}
    for line in (here / "sonicde.conf").read_text().splitlines():
        line = line.split("#", 1)[0].split()
        if len(line) == 2:
            conf[line[0]] = line[1]
    return conf


def read_lock():
    """The lock's repos: name -> (group, dir under /third_party, commit, ref)."""
    repos = {}
    for line in (here / "sonicde.lock").read_text().splitlines():
        w = line.split()
        if w and w[0] == "repo":
            repos[w[2]] = (w[1], w[3], w[4], w[5])
    return repos


def excluded(rel, source):
    """Whether a file (path under /opt/sonicde) stays out of the packages."""
    name = rel.rsplit("/", 1)[-1]
    if source in STATIC_REPOS or rel.startswith(DEV_DIRS) or "/objects-Release/" in rel \
            or name.endswith((".a", ".prl", ".la", ".o")):
        return True
    if rel.startswith(("bin/", "libexec/")) and source in qt_modules:
        return name not in QT_PROGRAMS
    if name in DEV_PROGRAMS:
        return True
    # A library's link for the linker (libfoo.so -> libfoo.so.6)
    path = prefix + "/" + rel
    if re.fullmatch(r"lib.*\.so", name) and os.path.islink(path) \
            and os.path.dirname(os.path.realpath(path)) == os.path.dirname(path):
        return True
    return False


def generated(rel):
    """Caches made while installing, not by any one repo; made on the Pi instead."""
    return ((rel.startswith("share/mime/") and not rel.startswith("share/mime/packages/"))
            or rel.endswith("/icon-theme.cache"))


def package_for(rel, group):
    if rel.startswith("share/icons/"):
        return "sonicde-icons"
    if rel.startswith("share/locale/"):
        return "sonicde-l10n"
    if rel.startswith("share/wallpapers/"):
        return "sonicde-wallpapers"
    return "sonicde-" + group


def assign(repos):
    """Every file to package: {package: {rel: source}}, from the manifests."""
    owner = {}
    for module in qt_modules:
        for p in (work / "qt-build" / module / "install_manifest.txt").read_text().splitlines():
            owner[os.path.normpath(p)] = ("qt", module)
    for name, (group, *_rest) in repos.items():
        group = GROUP_OVERRIDE.get(name, group)
        for p in (work / "sonic-build" / name / "install_manifest.txt").read_text().splitlines():
            owner[os.path.normpath(p)] = (group, name)

    files = collections.defaultdict(dict)
    unknown = []
    for d, _dirs, names in os.walk(prefix):
        for n in names:
            path = os.path.join(d, n)
            rel = path[len(prefix) + 1:]
            if path in owner:
                group, source = owner[path]
            elif rel.startswith("sbom/") or generated(rel):
                continue
            elif os.path.islink(path) and os.path.normpath(
                    os.path.join(d, os.readlink(path))) in owner:
                # Links made by an install script (kglobalaccel's to menu entries): the target's
                group, source = owner[os.path.normpath(os.path.join(d, os.readlink(path)))]
            elif rel.startswith("bin/") and n.endswith("6") and prefix + "/" + rel[:-1] in owner:
                # Qt's versioned names for its programs (qtpaths6)
                group, source = owner[prefix + "/" + rel[:-1]]
            else:
                unknown.append(rel)
                continue
            if not excluded(rel, source):
                files[package_for(rel, group)][rel] = source
    if unknown:
        sys.exit("Files no manifest lists (add a rule):\n  " + "\n  ".join(sorted(unknown)[:50]))
    return files


def is_elf(path):
    if os.path.islink(path):
        return False
    with open(path, "rb") as f:
        head = f.read(20)
    if head[:4] != b"\x7fELF":
        return False
    if head[4] != 2 or int.from_bytes(head[18:20], "little") != 183:
        sys.exit(f"{path} is not a 64-bit Arm ELF file")
    return True


def needed(elfs):
    """{elf: [NEEDED sonames]}, from readelf in batches."""
    result = {}
    for i in range(0, len(elfs), 200):
        batch = elfs[i:i + 200]
        # With more than one file, readelf names each (/bin/true makes sure there are two);
        # a file without a dynamic section makes it fail, harmlessly
        out = subprocess.run(["readelf", "-dW", *batch, "/bin/true"], text=True,
                             capture_output=True).stdout
        current = None
        for line in out.splitlines():
            if line.startswith("File: "):
                current = line[6:].strip()
                result.setdefault(current, [])
            m = re.search(r"\(NEEDED\)\s+Shared library: \[(.+)\]", line)
            if m and current:
                result[current].append(m.group(1))
    return {e: result.get(e, []) for e in elfs}


def closure(pkg):
    seen, todo = set(), [pkg]
    while todo:
        for d in PACKAGES[todo.pop()][2]:
            if d not in seen:
                seen.add(d)
                todo.append(d)
    return seen


def licenses_for(sources, repos, qt_version):
    """The copyright file's list of sources and their license texts (each text once)."""
    lines, texts = [], {}
    for source in sorted(sources):
        if source in qt_modules:
            tarball = f"{source}-everywhere-src-{qt_version}.tar.xz"
            cache = work / "qt-licenses" / source
            if not cache.exists():
                tmp = cache.with_name(source + ".tmp")
                shutil.rmtree(tmp, ignore_errors=True)
                tmp.mkdir(parents=True)
                run("tar", "--no-same-owner", "-xJf", f"/qt-src/{qt_version}/{tarball}", "-C", str(tmp),
                    "--strip-components=2", "--wildcards",
                    f"{source}-everywhere-src-{qt_version}/LICENSES/*")
                tmp.rename(cache)
            found = {p.name: p.read_text(errors="replace") for p in sorted(cache.iterdir())}
            major_minor = ".".join(qt_version.split(".")[:2])
            where = (f"https://download.qt.io/official_releases/qt/{major_minor}/{qt_version}/"
                     f"submodules/{tarball}")
        else:
            _group, d, commit, ref = repos[source]
            repo = Path("/third_party") / d
            names = [n for n in git(repo, "ls-tree", "--name-only", commit, "LICENSES/").splitlines()
                     if n.endswith(".txt")]
            names += [n for n in git(repo, "ls-tree", "--name-only", commit).splitlines()
                      if re.fullmatch(r"(COPYING|LICEN[CS]E)([-._].*)?", n, re.I)]
            found = {n.rsplit("/", 1)[-1]: git(repo, "show", f"{commit}:{n}") for n in names}
            ref = ref.removeprefix("origin/").removeprefix("refs/tags/")
            where = f"{git(repo, 'remote', 'get-url', 'origin').strip()} {commit} ({ref})"
        if not found:
            sys.exit(f"{source}: no license files")
        lines.append(f"{source}: {where}\n  {', '.join(found)}")
        for name, text in found.items():
            texts.setdefault(hashlib.sha256(text.encode()).hexdigest(), (name, text))
    return lines, sorted(texts.values())


def build(pkg, version, files, repos, conf, out, logs, intra):
    section, arch, internal, extra, summary, description = PACKAGES[pkg]
    stage = work / "pkg" / pkg
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)

    for rel in files:
        src, dst = f"{prefix}/{rel}", stage / prefix.lstrip("/") / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if os.path.islink(src):
            os.symlink(os.readlink(src), dst)
        else:
            shutil.copy2(src, dst)
    if pkg == "sonicde":
        session = here / "session"
        for src, dst, mode in ((session / "startsonicde", "usr/lib/sonicde/startsonicde", 0o755),
                               (session / "sonicde.desktop", "usr/share/xsessions/sonicde.desktop", 0o644),
                               (session / "pam-kde", "etc/pam.d/kde", 0o644)):
            (stage / dst).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, stage / dst)
            os.chmod(stage / dst, mode)
        # The system bus and polkit read only /usr/share: link SonicDE's helpers' files there
        for d in ("dbus-1/system.d", "dbus-1/system-services", "polkit-1/actions"):
            for f in sorted(os.listdir(f"{prefix}/share/{d}")):
                (stage / "usr/share" / d).mkdir(parents=True, exist_ok=True)
                os.symlink(f"{prefix}/share/{d}/{f}", stage / "usr/share" / d / f)

    elfs = [str(stage / prefix.lstrip("/") / rel) for rel in files
            if is_elf(f"{prefix}/{rel}")]
    if arch == "all" and elfs:
        sys.exit(f"{pkg} is Architecture: all but has ELF files: {elfs[:5]}")

    depends = [f"{d} (= {version})" for d in internal]
    if elfs:
        subprocess.run(["strip", "--strip-unneeded", *elfs], check=False,
                       stderr=subprocess.DEVNULL)
        # Each library from /opt/sonicde must come from this package or one it depends on
        allowed = {pkg} | closure(pkg)
        problems = set()
        for elf, sonames in needed(elfs).items():
            for soname in sonames:
                where = intra.get(soname)
                if where and where not in allowed:
                    problems.add(f"{elf.split(prefix, 1)[1]} needs {soname} from {where}")
                elif not where and any(os.path.exists(f"{prefix}/{d}/{soname}")
                                       for d in ("lib", "lib/aarch64-linux-gnu")):
                    problems.add(f"{elf.split(prefix, 1)[1]} needs {soname}, left out")
        if problems:
            sys.exit(f"{pkg}:\n  " + "\n  ".join(sorted(problems)))
        # Depends on Devuan's libraries. /opt/sonicde's are no package's, which
        # --ignore-missing-info lets through (checked above instead); -l finds them for Qt's
        # binaries, whose RPATH is relative ($ORIGIN/../lib)
        shlibs_dir = work / "pkg" / f"{pkg}.shlibs"
        (shlibs_dir / "debian").mkdir(parents=True, exist_ok=True)
        (shlibs_dir / "debian" / "control").write_text(
            f"Source: {pkg}\n\nPackage: {pkg}\nArchitecture: any\n")
        print(f"   dpkg-shlibdeps on {len(elfs)} ELF files", flush=True)
        with open(logs / f"{pkg}-shlibdeps.log", "w") as log:
            result = subprocess.run(["dpkg-shlibdeps", "-O", "--ignore-missing-info",
                                     f"-l{prefix}/lib", f"-l{prefix}/lib/aarch64-linux-gnu",
                                     *("-e" + e for e in elfs)],
                                    cwd=shlibs_dir, text=True, stdout=subprocess.PIPE, stderr=log)
        if result.returncode:
            sys.exit(f"{pkg}: dpkg-shlibdeps failed, see {logs}/{pkg}-shlibdeps.log")
        shlibs = re.search(r"^shlibs:Depends=(.*)$", result.stdout, re.M)
        shlibs = shlibs.group(1).split(", ") if shlibs else []
        bad = [d for d in shlibs if re.match(r"(libqt6|libkf6|qt6-|libsystemd|systemd)", d)]
        if bad:
            sys.exit(f"{pkg} would depend on {', '.join(bad)}")
        depends += shlibs
    if extra:
        depends.append(extra)

    # Copyright: every source a file of this package came from, and their license texts
    doc = stage / "usr/share/doc" / pkg
    doc.mkdir(parents=True)
    sources = set(files.values())
    lines, texts = licenses_for(sources, repos, conf["qt"]) if sources else ([], [])
    with open(doc / "copyright", "w") as f:
        f.write(f"{pkg} {version}, built by Pivuan (https://github.com/rations/pivuan, sonicde/)\n"
                "from the sources below at the commits or releases given, with the patches in\n"
                "sonicde/patches/ of that repository. The license files each source has are\n"
                "named after it; their texts follow.\n\n")
        f.write("\n".join(lines) + "\n")
        if pkg == "sonicde":
            f.write("\nThe session files (usr/lib/sonicde, usr/share/xsessions, etc/pam.d/kde) are\n"
                    "Pivuan's: GNU General Public License version 2, below.\n")
            texts.append(("Pivuan: GPL-2.0", Path("/src/LICENSE").read_text()))
        for name, text in texts:
            f.write(f"\n==> {name} <==\n\n{text.rstrip()}\n")
    _group, d, commit, _ref = repos["sonic-workspace"]
    date = git(Path("/third_party") / d, "log", "-1", "--format=%cD", commit).strip()
    with gzip.GzipFile(doc / "changelog.Debian.gz", "wb", mtime=0) as f:
        f.write(f"{pkg} ({version}) excalibur; urgency=medium\n\n"
                f"  * SonicDE Core {version.rsplit('-', 1)[0]}, Frameworks {conf['frameworks']}, "
                f"Apps {conf['system']}, Qt {conf['qt']}.\n\n"
                f" -- {MAINTAINER}  {date}\n".encode())

    debian = stage / "DEBIAN"
    debian.mkdir()
    if pkg == "sonicde":
        for script in ("postinst", "postrm"):
            shutil.copyfile(here / "session" / script, debian / script)
            os.chmod(debian / script, 0o755)
        (debian / "conffiles").write_text("/etc/pam.d/kde\n")
    size = int(run("du", "-sk", "--exclude=DEBIAN", str(stage)).split()[0])
    with open(debian / "md5sums", "w") as f:
        for path in sorted(stage.rglob("*")):
            if path.is_file() and not path.is_symlink() and debian not in path.parents:
                digest = hashlib.md5(path.read_bytes()).hexdigest()
                f.write(f"{digest}  {path.relative_to(stage)}\n")
    body = "\n".join(" " + (line if line else ".") for line in description.split("\n"))
    (debian / "control").write_text(
        f"Package: {pkg}\nVersion: {version}\nArchitecture: {arch}\nMaintainer: {MAINTAINER}\n"
        f"Installed-Size: {size}\n" + (f"Depends: {', '.join(depends)}\n" if depends else "")
        + f"Section: {section}\n"
        f"Priority: optional\nHomepage: https://github.com/Sonic-DE\n"
        f"Description: {summary}\n{body}\n")

    deb = out / f"{pkg}_{version}_{arch}.deb"
    run("dpkg-deb", "--root-owner-group", "-Zxz", "--build", str(stage), str(deb))
    shutil.rmtree(stage)
    if deb.stat().st_size > MAX_BYTES:
        sys.exit(f"{deb.name} is {deb.stat().st_size >> 20} MB, over the 95 MB publish-apt.sh takes")
    count = len(run("dpkg-deb", "--contents", str(deb)).splitlines())
    print(f"== {deb.name}: {deb.stat().st_size >> 20} MB, {count} entries", flush=True)


def main():
    global qt_modules
    if not os.path.exists(prefix + "/bin/startplasma-x11"):
        sys.exit("run this in the build root, after build-sonicde.sh")
    conf = read_conf()
    repos = read_lock()
    qt_modules = sorted(m for m in os.listdir(work / "qt-build")
                        if (work / "qt-build" / m / ".installed").exists())
    missing = [n for n in repos if not (work / "sonic-build" / n / ".installed").exists()]
    if missing:
        sys.exit(f"not built yet: {', '.join(missing)}")

    core = max((ref.removeprefix("origin/") for group, _d, _c, ref in repos.values()
                if group == "workspace" and ref.startswith("origin/" + conf["core"])),
               key=lambda t: [int(x) for x in t.split(".")])
    version = f"{core}-pivuan{conf['revision']}"
    out = work / "debs" / version
    logs = out / "logs"
    shutil.rmtree(out, ignore_errors=True)
    logs.mkdir(parents=True)

    files = assign(repos)
    files["sonicde"] = {}
    # Which package has each library in /opt/sonicde, by the name programs ask for
    intra = {}
    for pkg, rels in files.items():
        for rel in rels:
            d, name = os.path.split(rel)
            if d in ("lib", "lib/aarch64-linux-gnu") and re.match(r"lib.*\.so", name):
                intra[name] = pkg
    # Links must point at a packaged file
    packaged = {f"{prefix}/{rel}" for rels in files.values() for rel in rels}
    dangling = [rel for rels in files.values() for rel in rels
                if os.path.islink(f"{prefix}/{rel}")
                and os.path.realpath(f"{prefix}/{rel}") not in packaged
                and os.path.realpath(f"{prefix}/{rel}").startswith(prefix + "/")]
    if dangling:
        sys.exit("Links to files left out:\n  " + "\n  ".join(sorted(dangling)[:50]))

    print(f"== SonicDE {version} into {out}", flush=True)
    for pkg in PACKAGES:
        print(f"== {pkg}", flush=True)
        build(pkg, version, files[pkg], repos, conf, out, logs, intra)
    shutil.rmtree(work / "pkg", ignore_errors=True)
    total = sum(p.stat().st_size for p in out.glob("*.deb"))
    print(f"== {len(PACKAGES)} packages, {total >> 20} MB in {out}")


if __name__ == "__main__":
    main()
