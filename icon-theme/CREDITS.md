# Credits

## Icons: the Haiku project

All icons in this theme were drawn by the artists of the
[Haiku](https://www.haiku-os.org) project and are released under the MIT
license (see `LICENSE`). They are converted unchanged from the Haiku source tree:

- `data/artwork/icons/`: the Icon-O-Matic source files
- the `.rdef` resource files of Haiku's applications, preferences and servers
- the MIME database, `src/data/mime_db/`

The `SOURCES` file next to this one names the Haiku commit used and, for every
icon, the file it comes from. Haiku's git history records who drew each one.

"HAIKU" and the HAIKU logo and leaf are trademarks of Haiku, Inc. This is an
unofficial theme, not made or endorsed by Haiku, Inc. Icons showing the HAIKU
logo or leaf, the Be logo, or other companies' logos are left out
(`mapping/exclude.txt` in the build repository).

## Conversion: hvif-tools

The icons are converted to SVG and PNG with `icon2icon` from
[hvif-tools](https://github.com/threedeyes/hvif-tools) by Gerasim Troeglazov
(3dEyes), MIT license. The build adds a small patch to it
(`patches/hvif-tools/`) so that each PNG size shows the same shapes Haiku draws
at that size.
