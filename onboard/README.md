# Onboard for Pivuan

Onboard is the on-screen keyboard of Pivuan Audio: it comes up by itself when a text box is
tapped, and the panel's keyboard button shows and hides it (configng's
`branding/jwm/pivuan-keyboard`). This is Devuan's `onboard` package, rebuilt with Pivuan's
patches in [patches/](patches/). Its version, `<Devuan's version>+pivuan<n>`, sorts above
Devuan's, so apt installs it from the Pivuan apt repository in place of Devuan's; nothing else
changes in how Pivuan Audio installs Onboard.

## The patches

- [pivuan-chromium-omnibox-focus.patch](patches/pivuan-chromium-omnibox-focus.patch): typing in
  Brave's address bar no longer hides the keyboard once the list of suggestions opens. Brave
  (Chromium) reports the address bar losing the focus to the first suggestion while the
  keyboard focus stays in the bar. Onboard already had the same workaround for Firefox's URL
  bar; this recognizes Chromium's address bar (accessible class `...OmniboxViewViews`) and keeps
  the keyboard up while the bar still says it has the focus. Tapping the page still hides it.

## Build

[build-onboard.sh](build-onboard.sh) runs inside a Devuan excalibur arm64 root:

```sh
build-onboard.sh build <out-dir>   # apt-get source onboard=<pinned>, the patches, dpkg-buildpackage
build-onboard.sh check <deb-dir>   # install the packages in a clean root; the change is there, libraries found
```

[onboard.conf](onboard.conf) pins Devuan's source version and the Pivuan version. The build
stops when Devuan (excalibur, -updates or -security) has a newer onboard, since Pivuan's package
would otherwise hide it: then pin that version, reset the Pivuan version to `<it>+pivuan1`, and
check that the patches still apply. `../build/.github/pivuan/check-updates.sh` reports it too.

The workflow [onboard.yml](../.github/workflows/onboard.yml) ("Onboard for Pivuan", started by
hand) builds on GitHub's arm64 runner, checks, and with "publish" adds `onboard`,
`onboard-common` and `onboard-data` to the Pivuan apt repository. All three, as `onboard-data`
needs an `onboard` of its own version.

The unpacked source and Devuan's source package for reading are kept outside the repository, in
`~/third_party/onboard` on the development machine.

License: GPL-3 or later, as Onboard (Devuan's `debian/copyright`).
