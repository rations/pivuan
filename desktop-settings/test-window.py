#!/usr/bin/python3
#
# Checks Desktop Settings' window without showing it (needs an X display; CI uses Xvfb):
# the defaults, and that Apply is highlighted only while something differs from what is
# saved, and no longer once it has been applied.
#
#   python3 test-window.py [path/to/pivuan-desktop-settings]
#
import importlib.machinery
import importlib.util
import os
import sys
import tempfile

# The settings go to a scratch folder, set before the program reads where they are.
config_home = tempfile.mkdtemp(prefix="desktop-settings-test-")
os.environ["XDG_CONFIG_HOME"] = config_home

program = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "pivuan-desktop-settings")
loader = importlib.machinery.SourceFileLoader("desktop_settings", program)
spec = importlib.util.spec_from_loader("desktop_settings", loader)
ds = importlib.util.module_from_spec(spec)
loader.exec_module(ds)

# Apply restarts JWM: not here.
restarts = []
real_run = ds.subprocess.run
ds.subprocess.run = lambda *args, **kwargs: restarts.append(args)

failures = []


def check(what, ok):
    print(("ok    " if ok else "FAIL  ") + what)
    if not ok:
        failures.append(what)


def highlighted(window):
    button = window.apply_button
    return button.get_sensitive() and \
        button.get_style_context().has_class("suggested-action")


def plain(window):
    button = window.apply_button
    return not button.get_sensitive() and \
        not button.get_style_context().has_class("suggested-action")


check("default background is black",
      ds.DEFAULT_BACKGROUND.endswith("/background-black.png"))
check("default panel color is #959597", ds.PANEL_COLOUR_DEFAULT == "#959597")
check("desktop icons are on by default", ds.load_settings()["desktop_icons"] is True)
check("the screen stays on by default", ds.load_settings()["screen_off"] is False)
check("the brightness is not set by default", ds.load_settings()["brightness"] is None)
check("the brightness button is on by default", ds.load_settings()["brightness_button"] is True)
check("long press is on by default", ds.load_settings()["long_press"] is True)
touch = ds.touchscreen()
check("the default panel size suits the screen (%s)" % ("touch" if touch else "mouse"),
      ds.load_settings()["panel_size"] == (48 if touch else 30))

window = ds.DesktopSettings()
check("Apply is plain when the window opens", plain(window))

# Each kind of change highlights it; changing it back does not leave it highlighted.
window.autohide.set_active(True)
check("hiding the panel highlights Apply", highlighted(window))
window.autohide.set_active(False)
check("changing it back makes Apply plain again", plain(window))

window.panel_size.set_text("48")
check("typing a panel size (no Enter) highlights Apply", highlighted(window))
window.panel_size.set_text(str(ds.load_settings()["panel_size"]))
check("typing the saved size makes Apply plain again", plain(window))

window.colour.set_rgba(window.rgba("#E8E4D8"))
window.colour.emit("color-set")
check("choosing a panel color highlights Apply", highlighted(window))
window.default_colour(None)
check("Default makes Apply plain again", plain(window))

window.keyboard["yes"].set_active(True)
check("the on-screen keyboard setting highlights Apply", highlighted(window))
window.keyboard["auto"].set_active(True)
check("setting it back makes Apply plain again", plain(window))

window.brightness_button.set_active(False)
check("turning the brightness button off highlights Apply", highlighted(window))
window.brightness_button.set_active(True)

window.long_press.set_active(False)
check("turning long press off highlights Apply", highlighted(window))
window.long_press.set_active(True)
check("turning it on again makes Apply plain again", plain(window))

window.desktop_icons.set_active(False)
check("turning the desktop icons off highlights Apply", highlighted(window))
window.desktop_icons.set_active(True)
check("turning them on again makes Apply plain again", plain(window))

window.screen_off.set_active(True)
check("turning the screen off after a while highlights Apply", highlighted(window))
window.screen_off.set_active(False)
check("leaving the screen on again makes Apply plain again", plain(window))

window.settings["launchers"].append("example.desktop")
window.fill_launchers()
check("adding a program icon highlights Apply", highlighted(window))

# Applying saves, restarts JWM and makes Apply plain.
window.apply(window.apply_button)
check("Apply is plain after applying", plain(window))
check("Apply restarted JWM", len(restarts) == 1)
saved = ds.load_settings()
check("the program icon was saved", saved["launchers"] == ["example.desktop"])

# Turning the desktop icons off saves it and restarts them (pcmanfm's desktop goes away).
window.desktop_icons.set_active(False)
window.apply(window.apply_button)
check("the desktop icons setting was saved", ds.load_settings()["desktop_icons"] is False)
check("Apply restarted the desktop icons",
      any(args and args[0] == [ds.DESKTOP_ICONS, "restart"] for args in restarts))

# Turning the screen off after a while is saved (jwm-desktop sets it when JWM restarts).
window.screen_off.set_active(True)
window.apply(window.apply_button)
check("the screen setting was saved", ds.load_settings()["screen_off"] is True)

# The brightness: a fake /usr/lib/pivuan/brightness (DDC/CI, the screen at 70), as the window
# would find it; the slider shows the screen's own, and counts only once moved.
fake = os.path.join(config_home, "brightness")
with open(fake, "w") as f:
    f.write("#!/bin/sh\ncase \"$1\" in method) echo ddc ;; get) echo 70 ;; esac\n")
os.chmod(fake, 0o755)
ds.BRIGHTNESS = fake
ds.subprocess.run = real_run
lit = ds.DesktopSettings()
check("the brightness slider is shown", lit.brightness is not None)
check("it shows the screen's own brightness", int(lit.brightness.get_value()) == 70)
check("Apply is plain before the brightness is moved", plain(lit))
lit.brightness.set_value(40)
check("moving the brightness highlights Apply", highlighted(lit))
lit.brightness.set_value(70)
check("moving it back makes Apply plain again", plain(lit))
lit.brightness.set_value(55)
ds.subprocess.run = lambda *args, **kwargs: restarts.append(args)
lit.apply(lit.apply_button)
check("the brightness was saved", ds.load_settings()["brightness"] == 55)
ds.subprocess.run = real_run

# A window opened on the saved settings starts plain too.
again = ds.DesktopSettings()
check("Apply is plain in a new window on saved settings", plain(again))

if failures:
    print("%d check(s) failed" % len(failures))
    sys.exit(1)
print("all checks passed")
