#!/usr/bin/python3
#
# Checks Screenshot without showing its window (needs an X display; CI uses Xvfb): scrot's
# options for each mode, then the window's two pages with a made-up shot: saving it with a
# typed name, discarding it, and no shot (Escape during a click or a drag).
#
#   python3 test-window.py [path/to/pivuan-screenshot]
#
import importlib.machinery
import importlib.util
import os
import re
import sys
import tempfile

# The pictures and the shot go to a scratch folder, set before the program reads where they are.
scratch = tempfile.mkdtemp(prefix="screenshot-test-")
os.environ["XDG_PICTURES_DIR"] = os.path.join(scratch, "Pictures")
os.environ["XDG_CACHE_HOME"] = os.path.join(scratch, "cache")

program = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "pivuan-screenshot")
loader = importlib.machinery.SourceFileLoader("screenshot", program)
spec = importlib.util.spec_from_loader("screenshot", loader)
ss = importlib.util.module_from_spec(spec)
loader.exec_module(ss)

failures = []


def check(what, ok):
    print(("ok    " if ok else "FAIL  ") + what)
    if not ok:
        failures.append(what)


# scrot's options: --freeze only without a delay, and then the outline is a window of its own.
check("the screen: no options",
      ss.scrot_command("screen", "/x.png") == ["scrot", "--overwrite", "/x.png"])
check("a window: a click, with its frame",
      ss.scrot_command("window", "/x.png") == ["scrot", "--overwrite", "--select", "--border",
                                               "/x.png"])
check("an area: a drag over the frozen screen",
      ss.scrot_command("area", "/x.png") == ["scrot", "--overwrite", "--select", "--freeze",
                                             "/x.png"])
check("an area after a delay: not frozen, the outline a window",
      ss.scrot_command("area", "/x.png", 3) == ["scrot", "--overwrite", "--select", "--line",
                                                "mode=edge", "--delay", "3", "/x.png"])
check("a window after a delay",
      ss.scrot_command("window", "/x.png", 2) == ["scrot", "--overwrite", "--select",
                                                  "--border", "--delay", "2", "/x.png"])
for mode, start in (("screen", "screenshot"), ("window", "window"), ("area", "area")):
    check("%s: named %s_<date>_<time>.png" % (mode, start),
          re.fullmatch(start + r"_\d{8}_\d{6}\.png", ss.file_name(mode)) is not None)
check("the shot is kept in the cache", ss.SHOT.startswith(os.environ["XDG_CACHE_HOME"]))

# The window, never shown: taken() would show it again after a shot.
window = ss.Screenshot(None)
window.show = window.present = lambda: None


def page():
    return window.pages.get_visible_child_name()


def take_a_shot(mode):
    """What scrot leaves behind, and its end."""
    window.mode = mode
    os.makedirs(os.path.dirname(ss.SHOT), exist_ok=True)
    pixbuf = ss.GdkPixbuf.Pixbuf.new(ss.GdkPixbuf.Colorspace.RGB, False, 8, 1280, 800)
    pixbuf.fill(0x202020ff)
    pixbuf.savev(ss.SHOT, "png", [], [])
    window.taken(None, 0, None)


check("it opens on the first page", page() == "take")
check("the whole screen is chosen first", window.modes["screen"].get_active())
check("no delay at first", window.delay.get_value() == 0)

take_a_shot("screen")
check("a shot opens the second page", page() == "save")
name = window.name.get_text()
check("the name is screenshot_<date>_<time>.png",
      re.fullmatch(r"screenshot_\d{8}_\d{6}\.png", name) is not None)
check("the preview fits", window.preview.get_pixbuf().get_width() <= ss.PREVIEW_WIDTH
      and window.preview.get_pixbuf().get_height() <= ss.PREVIEW_HEIGHT)
check("it saves in ~/Pictures at first", window.folder == ss.PICTURES)
check("~/Pictures is made", os.path.isdir(ss.PICTURES))

window.name.set_text("my shot")
window.save(None)
saved = os.path.join(ss.PICTURES, "my shot.png")
check("a typed name is saved, with .png added", os.path.isfile(saved))
check("the shot is gone once saved", not os.path.exists(ss.SHOT))
check("back on the first page", page() == "take")
check("it says where", window.status.get_text() == "Saved as " + saved)

take_a_shot("area")
check("an area is named area_<date>_<time>.png",
      window.name.get_text().startswith("area_"))
window.discard(None)
check("Discard throws the shot away", not os.path.exists(ss.SHOT))
check("Discard goes back to the first page", page() == "take")
check("nothing more is saved", os.listdir(ss.PICTURES) == ["my shot.png"])

window.taken(None, 1, None)
check("no shot: the first page says so",
      page() == "take" and window.status.get_text() == "No screenshot was taken.")

window.destroy()
if failures:
    print("%d failed" % len(failures))
    sys.exit(1)
print("all passed")
