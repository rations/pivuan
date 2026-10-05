# Pivuan icon theme

A freedesktop icon theme made from the vector icons of the
[Haiku](https://www.haiku-os.org) operating system: folders, drives, file
types, applications and settings, for XFCE, MATE, JWM and other desktops.

This is an unofficial theme, not made or endorsed by Haiku, Inc. The icons are
Haiku's, under the MIT license; see [LICENSE](LICENSE) and [CREDITS.md](CREDITS.md).

## What it does

- Converts Haiku's own icons with `icon2icon` from
  [hvif-tools](https://github.com/threedeyes/hvif-tools). Sources are the
  Icon-O-Matic files in `data/artwork/icons`, the icons inside apps' `.rdef`
  files, and the MIME database `src/data/mime_db`.
- Writes an SVG for every icon, plus PNGs at fixed sizes. Haiku icons can hold
  simpler shapes for small sizes, and the PNGs use the shapes Haiku itself
  draws at each size (`patches/hvif-tools/`).
- Gives the icons freedesktop names through [mapping/icons.toml](mapping/icons.toml),
  for example Tracker's home folder becomes `user-home`. Every Haiku MIME type
  icon is added under its own name (`text-plain`, `image-x-generic`, ...).
  Names the theme lacks come from the themes in `INHERITS` (Numix, then Adwaita).
- Leaves out icons that show the HAIKU logo or leaf, the Be logo, or other
  companies' logos, plus icons from directories whose code isn't MIT
  ([mapping/exclude.txt](mapping/exclude.txt)). The build stops if the
  mapping uses one of them.

## Build

Needs: `git`, `cmake`, `g++`, `python3` (3.11 or later), `make`, and
`dpkg-deb` for the package.

```sh
git clone --recursive https://github.com/rations/pivuan   # or: git submodule update --init --recursive
cd pivuan/icon-theme
make                                       # fetches Haiku's icons into build/haiku
make install                               # into ~/.local/share/icons/Pivuan
```

`make` fetches only the files it needs (about 20 MB) from the Haiku commit
`HAIKU_COMMIT` in [config.mk](config.mk). To use a full Haiku checkout of your
own instead, run `make HAIKU_SRC=/path/to/haiku`.

Then pick "Pivuan" as the icon theme: in XFCE under Settings > Appearance
> Icons, in MATE under Appearance > Customize > Icons, or with `lxappearance`.

Other targets:

| Target | What it does |
|---|---|
| `make coverage` | which standard icon names the theme has and which it lacks |
| `make deb` | `build/pivuan-icon-theme_<version>-pivuan<rev>_all.deb` for Debian/Devuan |
| `make lodscan` | Haiku icons that have shapes for some sizes only, and ones that fail to parse |
| `make uninstall` / `make clean` | remove the installed theme / the build directory |

Settings (Haiku commit, theme name, sizes, inherited themes, package version)
are in [config.mk](config.mk). Bump `VERSION` or `DEB_REVISION` before
publishing a new package.

## Publishing

The workflow "Pivuan icon theme" (`.github/workflows/icon-theme.yml`) builds and
checks the package. Run by hand with "publish", it adds the package to the
Pivuan apt repository. On Pivuan it comes with the XFCE, MATE and Pivuan Audio
desktops, and it is Pivuan Audio's default icon theme.

## Adding icons

1. Find the icon. `build/src/manifest.json` lists every icon extracted from
   `.rdef` files and the MIME database. `data/artwork/icons` (in
   `build/haiku`) holds the rest.
2. Add `freedesktop-name = "source"` to the right section of
   `mapping/icons.toml`. Keys containing `.` or `+` must be quoted.
3. Run `make && make coverage`.
