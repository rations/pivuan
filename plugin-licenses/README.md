# Plugin Licenses (Pivuan Audio)

Starts the license service of Windows plugins, such as iLok's, and says when it answers, so
that plugins find their licenses. Audio > **Plugin Licenses** in the Pivuan menu.

Windows plugins protected by iLok ask PACE License Services for their license once, when they
load. If it doesn't answer, they say they have no license and don't load. Windows starts the
service at boot, long before anyone opens a DAW. Wine starts it only with its first Windows
program, which is then the plugin itself, and under FEX the service needs about half a minute
before it answers, so that plugin always asks too early. Keeping it running all the time would
cost about 1 GB of memory, so it runs only when wanted:

1. Open **Plugin Licenses**. It starts the services and shows "Ready: open your DAW" once they
   answer (about half a minute).
2. Open the DAW and load the plugins.
3. Close the window once they have loaded. The services stop by themselves when the DAW closes:
   Wine stops them once its last Windows program, the DAW's plugin host, has exited.

Closing the window before loading plugins stops the services too, unless a Windows program is
still running. Without any such service, the window says so and doesn't start Wine.

## How it works

- `pivuan-plugin-licenses`: the window (Python, GTK 3). It looks in Wine's registry file
  (`system.reg` of `$WINEPREFIX`, normally `~/.wine`) for services of Windows programs that
  start automatically, and runs the helper in Wine if there are any.
- `plugin-license-wait.exe`: the helper, a small x86-64 Windows program (it runs through FEX).
  Through Windows' service manager it finds the automatic services that aren't Wine's own,
  starts them, and waits until each answers. A service that Windows starts on a named pipe
  (a trigger start: its `TriggerInfo` registry key, as iLok's `PaceLicenseDServices` has for
  `com_paceap_eden_licensed_authorization`) answers once that pipe opens; any other once it is
  running. The service manager's "running" can't be used for this: PACE's service reports it
  at once and opens its pipe about 17 seconds later. Then the helper keeps Wine running until
  its standard input closes, which is the window closing. It prints one line per event (see the
  top of the source).

Nothing in it names iLok or PACE: it uses what each service told Windows when it was installed.

## Build

Needs `x86_64-w64-mingw32-gcc` (Debian's `gcc-mingw-w64-x86-64`), `make`, Python 3, and
`dpkg-deb` for the package.

```
make             # build/plugin-license-wait.exe
make check       # it builds, the window's program compiles, the desktop file is valid
make test        # the window with stand-in helpers (needs an X display)
make deb         # build/pivuan-plugin-licenses_<version>_arm64.deb
```

Settings and the package version are in `config.mk`. The package is arm64 only, for Pivuan's
`wine-fex`. The "Pivuan Plugin Licenses" workflow (`.github/workflows/plugin-licenses.yml`, run
by hand) builds it, checks it, and publishes it to the Pivuan apt repository.

## License

GPL-3.0 (`packaging/deb/copyright`).
