#!/usr/bin/python3
#
# Tests Plugin Licenses' window with stand-in helpers (shell scripts that print what
# plugin-license-wait.exe prints): it says "Ready" once all services answer, closing it closes
# the helper's input (so that Wine can stop the services), and a helper that finds nothing or
# fails is reported. Needs an X display (CI: xvfb-run).
#
# Usage: test-window.py <path to pivuan-plugin-licenses>

import importlib.machinery
import importlib.util
import os
import sys
import tempfile

from gi.repository import GLib

program = sys.argv[1]
loader = importlib.machinery.SourceFileLoader("plugin_licenses", program)
spec = importlib.util.spec_from_loader("plugin_licenses", loader)
pl = importlib.util.module_from_spec(spec)
loader.exec_module(pl)

tmp = tempfile.mkdtemp()
failures = []


def helper(name, body):
    path = os.path.join(tmp, name)
    with open(path, "w") as f:
        f.write("#!/bin/sh\n" + body)
    os.chmod(path, 0o755)
    return path


def run(command, until, then=None, timeout=10):
    """Opens the window with this helper, waits until the heading is `until`, runs `then`,
    and returns the heading."""
    os.environ["PIVUAN_PLUGIN_LICENSES_COMMAND"] = command
    app = pl.App()
    state = {"heading": None}

    def poll():
        window = app.window
        if window and window.heading.get_text() == until:
            state["heading"] = until
            if then:
                then(window)
            window.close()
            return False
        return True

    def give_up():
        if app.window:
            state["heading"] = app.window.heading.get_text()
            app.window.close()
        return False

    GLib.timeout_add(100, poll)
    GLib.timeout_add_seconds(timeout, give_up)
    app.run([program])
    return state["heading"]


def check(what, ok):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


# All services answer: "Ready", and the window's closing ends the helper (its input closes)
closed = os.path.join(tmp, "closed")
ready = helper("ready.sh",
               'printf "service\\tTest Service\\n"; sleep 0.3\n'
               'printf "ready\\tTest Service\\nready-all\\n"\n'
               'cat > /dev/null; touch "%s"\n' % closed)
rows = {}
heading = run(ready, "Ready: open your DAW or iLok License Manager", then=lambda w: rows.update(w.rows))
check("ready: heading %r" % heading, heading == "Ready: open your DAW or iLok License Manager")
check("ready: the service is listed with a check mark",
      "Test Service" in rows and rows["Test Service"].get_text() == "✓")
for _ in range(50):
    if os.path.exists(closed):
        break
    GLib.usleep(100000)
check("closing the window closes the helper's input", os.path.exists(closed))

# No service installed
heading = run(helper("none.sh", 'printf "none\\n"; exit 3\n'), "No license service is installed")
check("none: heading %r" % heading, heading == "No license service is installed")

# The helper ends before the services answer
heading = run(helper("fails.sh", 'printf "service\\tTest Service\\n"; exit 1\n'),
              "The license service did not start")
check("helper fails: heading %r" % heading, heading == "The license service did not start")

sys.exit(1 if failures else 0)
