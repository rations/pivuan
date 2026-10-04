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
