# Pivuan package lists

The packages Pivuan installs, by what installs them. The lists name the packages Pivuan asks
for; apt adds their dependencies. Packages come from the Devuan archive unless marked
**Pivuan** (the [Pivuan apt repository](https://rations.github.io/pivuan)) or **Brave**
([Brave's apt repository](https://brave.com/linux/)).

| List | What it covers |
|---|---|
| [image.md](image.md) | The Pivuan image: base system, system tools, networking, Raspberry Pi firmware, kernel, board support and `pivuan-config` |
| [pivuan-audio.md](pivuan-audio.md) | Pivuan Audio (`pivuan-config --cmd AUDI01`) |
| [xfce.md](xfce.md) | XFCE, minimal, mid and full (`XFCE01`, `XFCE05`, `XFCE06`) |
| [mate.md](mate.md) | MATE, minimal, mid and full (`MATE01`, `MATE05`, `MATE06`) |
| [apt-repository.md](apt-repository.md) | Every package in the Pivuan apt repository, its version and what uses it |

## Updating the lists

The lists are generated, so don't edit them by hand. After a change to the image (rations/build),
the desktops (rations/configng) or the apt repository, run this from this repository, with
`../build` and `../configng` checked out next to it:

```sh
packages/update-lists.py
```

The script reads:
- the image's packages from the build's own package aggregation, for the settings of the
  "Pivuan image build" workflow;
- the desktops' packages from configng's `parse_desktop_yaml.py`, as `pivuan-config` reads them;
- the apt repository's packages from its index on the `gh-pages` branch.

It needs `python3-yaml`, and `apt-cache` on a Devuan excalibur or Debian trixie machine for the
package descriptions.
