# Wine with FEX on Pivuan

Pivuan Audio runs Windows plugins with [vstbridge](https://github.com/rations/vstbridge). On the
Raspberry Pi 5 that needs a Windows compatibility layer for ARM, so Pivuan ships its own Wine
build: the `wine-fex` packages.

## What it is

- **Wine**: wine-staging 11.18, built natively for 64-bit ARM with ARM64EC support.
- **FEX**: `libarm64ecfex.dll` and `libwow64fex.dll` from [FEX](https://github.com/FEX-Emu/FEX)
  (FEX-2609), which translate x86 code to ARM.

Wine itself runs as native ARM code. FEX translates only the Windows program's own x86 code, inside
the same process. The other approach, running a whole x86 Wine under an emulator such as box64, also
emulates all of Wine and was too slow for realtime audio.

vstbridge's plugin host is an ARM64EC program: its own code runs natively, and the x86_64 plugin it
loads runs through FEX. The host talks to the plugin in your DAW through a small native Linux
library instead of Wine's sockets. On the Pi 5 a round trip takes 13.7 µs, the same as between two
Linux programs (13.6 µs). Through Wine's sockets it took about 123 µs.

## Why DXVK isn't needed

On x86 Linux, many plugin editors only work with DXVK installed: they draw one frame and then
freeze. The cause is a Wine function that isn't implemented. JUCE 8 plugins pace their drawing on
`IDXGIOutput::WaitForVBlank()`, which Wine returns from at once with an error. Their drawing thread
spins on it at full speed, and the editor stops updating and stops responding. DXVK only hides this,
because its own version of that function waits.

This build fixes the function itself: it waits for the screen's next refresh. Plugin editors then
draw through Wine's own Direct3D on the Pi 5's OpenGL driver, with nothing else to install.

That matters because DXVK can't run on the Pi 5 at all: its Vulkan driver (Mesa v3dv) lacks features
DXVK requires, such as BC texture compression and 64-bit shader integers.

## What's different from upstream Wine

Six patches, all in
[vstbridge's `aarch64/wine/patches`](https://github.com/rations/vstbridge/tree/arm64/aarch64/wine/patches):

1. `IDXGIOutput::WaitForVBlank()` waits for a refresh interval (the fix above).
2. New Wine prefixes use FEX for x86_64 and 32-bit x86 programs, as Proton's Wine does. Upstream
   Wine points these at stubs that don't run anything.
3. A shortcut an installer puts on your desktop shows once, as its launcher. Wine's Desktop folder
   is the Linux desktop, so the Windows shortcut file would otherwise show next to it. The file
   moves to Wine's Public Desktop, where Windows programs still find it.
4. Windows' service manager reports a service's failure actions. Installers that set them, such as
   iLok's, read them first and stopped when Wine couldn't answer.
5. Wine's installer programs (`msiexec`, and `rundll32` for .NET installer steps) say they support
   Windows 10, as Windows' own do. Without that, installers checking for Windows 10 saw Windows 8.
6. Windows programs are told the computer has the x86-64 processor FEX emulates. Installers that
   find an ARM processor install ARM files, which the x86-64 programs and plugins run here can't
   load. iLok's did.

Patches 4 to 6 are what iLok (PACE License Support) needs to install.

## Packages

| Package | Contents |
|---|---|
| `wine-fex` | Wine and FEX in `/opt/vstbridge/wine`, the `wine` commands in `/usr/bin`, and the "Wine Windows Program Loader" for opening `.exe` and `.msi` files from pcmanfm |
| `wine-fex-i386` | 32-bit Windows support, for programs such as many plugin installers |
| `wine-fex-mono` | Wine's .NET runtime, so a new Wine prefix is set up without a download |

- `vstbridge` depends on all three, and Pivuan Audio installs them.
- They replace Debian's `wine` packages. Both install `/usr/bin/wine`, so only one can be installed.
- Everything uses the usual Wine prefix, `~/.wine`.

## Limits

- 32-bit Windows programs run, but 32-bit plugins can't be bridged yet: vstbridge has only a
  64-bit plugin host on ARM.
- Emulated plugins use more CPU than on an x86 computer. FEX translates code the first time it
  runs, so a plugin can be slower for a moment just after it loads.

## Source

- Build scripts, pinned versions and patches:
  [rations/vstbridge, `aarch64/`](https://github.com/rations/vstbridge/tree/arm64/aarch64).
- The packages are built and published by the "vstbridge for Pivuan" workflow in this repository
  (`.github/workflows/vstbridge.yml`).
- Licences: Wine is LGPL-2.1-or-later, FEX is MIT, and vstbridge is GPL-3.0.
