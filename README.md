<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="pivuan-logo.png">
    <img src="pivuan-background.png" alt="Pivuan" width="520">
  </picture>
</p>

<p align="center"><b>Devuan with sysvinit for the Raspberry Pi.</b></p>

---

Pivuan is a minimal [Devuan](https://www.devuan.org/) 6 "excalibur" image for the Raspberry Pi,
built with the [Armbian](https://www.armbian.com/) build framework. It boots with **sysvinit**
instead of systemd, feels like an Armbian minimal image (fast boot, first-boot setup wizard,
configuration tool), and gets its updates from Devuan and from its own apt repository.

- **Minimal**: a small console system (about 850 MB used) with networking, SSH and the
  `pivuan-config` tool. Add only what you need.
- **sysvinit, no systemd**: `init` is PID 1, with elogind, eudev and ifupdown. Packages that
  would pull in systemd are left out.
- **Desktop in one command**: XFCE or MATE with a LightDM login screen, installed from the
  Devuan archive by `pivuan-config`, or **Pivuan Audio** for music production (JWM and JACK),
  which also runs Windows plugins.
- **Kept up to date**: Devuan's security updates through apt, and the Raspberry Pi kernel,
  firmware, board support and `pivuan-config` through the Pivuan apt repository.

Pivuan is built for the **Raspberry Pi 5** and uses the Raspberry Pi Foundation's kernel. The
same image is built for the other 64-bit boards it supports (Raspberry Pi 3 and 4), which are
less tested.

## Download

Get the latest image from **[Releases](https://github.com/rations/pivuan/releases)**: the
`Pivuan_<version>_Rpi4b_excalibur_current_<kernel>_minimal.img.xz` file and its `.sha` file.

Check the download (optional):

```sh
sha256sum -c Pivuan_*.img.xz.sha
```

## Install

Write the image to a microSD card (8 GB or larger). Any of these works:

- **balenaEtcher**: pick the `.img.xz` file and the card, then Flash.
- **Raspberry Pi Imager**: *Choose OS* → *Use custom* → the `.img.xz` file. Don't use its
  "OS customisation" settings; Pivuan's first-boot wizard does that.
- **Linux command line** (replace `/dev/sdX` with your card; check with `lsblk`, this erases it):

  ```sh
  xzcat Pivuan_*.img.xz | sudo dd of=/dev/sdX bs=4M conv=fsync status=progress
  ```

The image is `xz`-compressed, not a tar archive: use `xzcat`, `unxz` or `xz -d`, not `tar`.

## First boot

1. Put the card in the Pi, connect a screen and keyboard (or Ethernet), and power on.
2. The filesystem grows to fill the card and the **Pivuan setup wizard** starts on the screen.
   It asks for:
   - a new **root password**,
   - your **user name and password** (this user can use `sudo`, and always with a password;
     there is no automatic login),
   - Wi-Fi, if no network cable is plugged in.

   It also sets your time zone and language.
3. You end up at a shell with a welcome screen showing the system's state and tips.

Without a screen, connect Ethernet, find the Pi's address on your router and log in with
`ssh root@<address>` using the password **`1234`**; the same wizard then starts and makes you
change it.

## Desktop

The image is minimal on purpose. To add a desktop, log in and run one of:

```sh
sudo pivuan-config --cmd XFCE01    # XFCE
sudo pivuan-config --cmd MATE01    # MATE
```

This installs, from the Devuan archive:

- **XFCE** with `xfce4-terminal` and the Pivuan menu icon, or **MATE** with `mate-terminal`,
  both with the Pivuan background,
- the **LightDM** login screen (no automatic login),
- **NetworkManager** with its tray applet (your wired and Wi-Fi settings are moved over),
- **PulseAudio** for sound and Bluetooth audio,
- **Brave Origin** as the web browser, from [Brave's apt repository](https://brave.com/linux/).

When it finishes, the login screen appears. Log in with the user you created in the wizard.

### Pivuan Audio

A desktop for audio production on the Raspberry Pi 5, with JACK and PulseAudio and without
PipeWire:

```sh
sudo pivuan-config --cmd AUDI01    # Pivuan Audio
```

It installs:

- **JWM** on the **XLibre** X server, built for Devuan excalibur (no backports) and installed
  from the Pivuan apt repository, with the **picom** compositor for smooth window moves,
- the **xlogin** login screen on tty1 instead of a display manager (it appears as soon as the
  install finishes; tty2 to tty6 keep their text login),
- **JACK** with realtime scheduling for the `audio` group, and the Pivuan audio applications
  from the Pivuan apt repository: Jack Graph, JackDAW, NAMp, NAMix, lvtuner, DRUMix and
  CPU Power,
- **vstbridge** for Windows VST2, VST3 and CLAP plugins in the audio programs ("vstbridge"
  in the Audio menu), with **Wine** and **FEX** for Windows programs, such as plugin
  installers and licence managers: they open from a right-click in pcmanfm ("Wine Windows
  Program Loader"). Everything uses the Wine prefix `~/.wine`. How this works without DXVK:
  [wine-fex-info.md](wine-fex-info.md),
- **PulseAudio** for everything else: HDMI, Bluetooth speakers and headphones, the browser and
  media player. The speaker in the tray opens Volume Control (pavucontrol); its scroll wheel
  changes the volume. A USB audio interface is an output as soon as it is plugged in (if
  PulseAudio leaves it at the profile Off, it is given its best output profile; if it could
  not open the interface, it is switched off and on again). While JACK
  runs, PulseAudio lets it have the sound card and plays into JACK instead ("JACK (audio
  interface)" in Volume Control); when JACK stops, it takes the card back,
- lxterminal, pcmanfm, mousepad, Celluloid, lxrandr and lxappearance, with the Numix icons.
  Screen settings saved in lxrandr are applied at each login, as are other programs in
  `~/.config/autostart` meant for LXDE or any desktop,
- the folders Downloads, Documents, Music, Videos, NAM, Impulse Responses, `.vst3` and `.lv2`
  in each home, bookmarked in pcmanfm,
- **NetworkManager** and **blueman** in the tray, and **Brave Origin**,
- **Desktop Settings** (System in the menu): the desktop background (the Pivuan backgrounds
  or any picture), program icons on the panel (all drawn at the same size), the panel's
  size, the icons' size and the panel's colour, and hiding the panel until the mouse reaches
  the bottom edge. It saves to `~/.config/pivuan/desktop.conf`.

The menu is on the Pivuan button in the tray, and on a click on the desktop. Each user's
`~/.jwmrc` includes `/etc/jwm/pivuan.jwmrc`; add your own settings to
`~/.jwmrc`. `sudo pivuan-config --cmd AUDI02` removes it and brings back the text login.

## pivuan-config

`pivuan-config` is the configuration tool: Armbian's `armbian-config` adapted for sysvinit.
Run it with a menu, or give it a command:

```sh
sudo pivuan-config                 # menu: system, network, localisation, software, desktops
sudo pivuan-config --cmd help      # list the commands
pivuan-config --help
pivuan-config --doc                # this README
```

Network settings: with a desktop installed, NetworkManager runs the network. Use the
network icon in the panel, or **Network → Network connections** in `pivuan-config` (the
same as `sudo nmtui`). On a console-only system, **Network → Switch to NetworkManager**
moves your wired and Wi-Fi settings over to it first.

## Updates

```sh
sudo apt update && sudo apt full-upgrade
```

- Everything from Devuan (the base system, the desktop, security fixes) comes from
  `deb.devuan.org`.
- The kernel, device trees, board support and `pivuan-config` come from the **Pivuan apt
  repository**, `https://rations.github.io/pivuan`, which Pivuan images already use. So do
  Pivuan Audio's XLibre, audio applications, vstbridge and Wine. The repository is
  signed with the key `34EA 4F11 5D83 793B 6C80  3155 4769 929F 204B 18CD`.

The kernel follows the Foundation's `rpi-6.18.y` long-term branch. Each week the build checks
for a new kernel point release (they carry the security fixes); when there is one, a new
image is released here and the kernel packages reach installed systems through `apt`.

## How Pivuan is made

Pivuan is a fork of the Armbian build framework that builds Devuan with sysvinit:

| Repository | What it is |
|---|---|
| [rations/build](https://github.com/rations/build) (branch `pivuan`) | Armbian build framework fork: Devuan excalibur support, sysvinit init scripts for Armbian's first-boot and board services, the image and apt-repository workflows |
| [rations/configng](https://github.com/rations/configng) | `armbian-config` (configng) fork, packaged as `pivuan-config`: a sysvinit service backend and the Devuan desktop install |
| [raspberrypi/linux](https://github.com/raspberrypi/linux) | The Raspberry Pi Foundation's kernel, pinned to a tested `rpi-6.18.y` commit |
| [rations/pivuan](https://github.com/rations/pivuan) (this repository) | Project page, releases (images), the apt repository (`gh-pages` branch), and the XLibre and vstbridge package builds |
| [rations/vstbridge](https://github.com/rations/vstbridge) (branch `arm64`) | vstbridge, the Windows plugin bridge, and the build of its Wine with FEX ([wine-fex-info.md](wine-fex-info.md)) |

Images are built by GitHub Actions in `rations/build`, from Devuan packages checked against
Devuan's signing keys.

## Thanks

Pivuan exists because of the work of two projects:

- **[Armbian](https://www.armbian.com/)**: the build framework, board support, first-boot
  wizard, `armbian-config` and the kernel packaging are theirs. Pivuan is their work, adapted
  to boot without systemd. Please support them: <https://www.armbian.com/donate/>
- **[Devuan](https://www.devuan.org/)**: the whole operating system, init freedom, and years
  of keeping Debian usable without systemd. Please support them: <https://www.devuan.org/os/donate>

Also thanks to the [Raspberry Pi Foundation](https://www.raspberrypi.com/) for the kernel and
firmware, and to [Debian](https://www.debian.org/), which Devuan is based on.

Pivuan is an independent personal project. It is not affiliated with or endorsed by Armbian,
Devuan, Debian or Raspberry Pi Ltd.

## License

The contents of this repository are licensed under the
[GNU General Public License, version 2](LICENSE), the license of the Armbian build framework
Pivuan is built with, **except the Pivuan artwork**.

**Pivuan artwork.** The Pivuan logo and backgrounds (`pivuan-logo.png`,
`backgrounds/background-*.png`, and the copies of them in Pivuan images and in
[rations/configng](https://github.com/rations/configng)) are © 2026 rations, all rights
reserved. They are not covered by the GPL or any other license in these repositories, and may
only be used with permission. Please ask by
[opening an issue](https://github.com/rations/pivuan/issues).

The images contain software under many licenses (the Linux kernel is GPL-2.0; Devuan and
Debian packages keep their own licenses, listed in `/usr/share/doc/*/copyright` on the
system). Source code: the build framework in [rations/build](https://github.com/rations/build)
(GPL-2.0), `pivuan-config` in [rations/configng](https://github.com/rations/configng)
(GPL-3.0), the kernel in [raspberrypi/linux](https://github.com/raspberrypi/linux), vstbridge
(GPL-3.0) and the build of its Wine (LGPL-2.1-or-later) and FEX (MIT) in
[rations/vstbridge](https://github.com/rations/vstbridge), and every Devuan package from Devuan's
source archive (`apt source <package>`).
