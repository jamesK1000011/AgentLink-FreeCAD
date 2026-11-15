# SPDX-License-Identifier: LGPL-2.1-or-later
# For add-on developers: an installed add-on's own tests, run in a separate
# FreeCAD command-line process on this computer (agentlink/testrun.py), so
# a suite runs in the real FreeCAD without CI and without touching the
# window, the hidden FreeCAD or their documents. Not in the lean list.

import os

import FreeCAD

from .. import keep, testrun
from ..protocol import Tool, ToolError, bad
from ..tools import obj
from .unattended import installed_names, mod_dir

GROUP = "dev"
INFO = "For add-on developers: an installed add-on's own test suite run in a separate FreeCAD process (addon_test)."

OWN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _pump():
    if not getattr(FreeCAD, "GuiUp", False):
        return None
    from .. import echo

    def pump():
        echo._paint(200)  # the window keeps painting while the call waits

    return pump


def tools(s):
    def addon_test(a):
        job, addon = a.get("job"), a.get("addon")
        if job is not None and addon is not None:
            raise bad("addon starts a run, job reads one: give one of them.")
        if job is not None:
            return testrun.wait(testrun.find(job), testrun.STATUS_WAIT, _pump())
        if addon is None:
            return testrun.listing()
        pattern = a.get("pattern") or "test_*.py"
        select = a.get("select") or None
        timeout = a.get("timeout", testrun.TIMEOUT)
        if not testrun.PATTERN.fullmatch(str(pattern)):
            raise bad("pattern: a file name glob ending in .py, no folders (test_*.py by default).")
        if select is not None and not testrun.SELECT.fullmatch(str(select)):
            raise bad("select: letters, digits and _ (part of a test's name).")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= testrun.TIMEOUT_MAX:
            raise bad(f"timeout: seconds, over 0 and at most {testrun.TIMEOUT_MAX:g} ({testrun.TIMEOUT:g} by default).")
        mod = mod_dir()
        installed = installed_names(mod)
        root = testrun.root_for(addon, mod, OWN_ROOT, installed)
        try:
            home = FreeCAD.getHomePath()
        except Exception:  # noqa: BLE001
            home = None
        cmd, lib = testrun.find_cmd(home=home)
        if cmd is None:
            raise ToolError("unavailable", "No FreeCAD command-line binary (freecadcmd) beside this FreeCAD, in FREECAD_APP or on the PATH.")
        roots = [os.path.join(mod, n) for n in sorted((installed or set()) - {"AgentLink", "AddonManager"}) if os.path.isdir(os.path.join(mod, n))]
        log = keep.path("tests", f"{addon}-{keep.stamp()}.log")
        return testrun.wait(testrun.start(cmd, addon, root, OWN_ROOT, roots, lib, log, pattern, select, float(timeout)), testrun.START_WAIT, _pump())

    st = {"type": "string"}
    return [
        Tool("addon_test",
             "An installed add-on's own tests (its tests/ folder) run in the background in a separate FreeCAD command-line process, never this "
             "FreeCAD: documents, the window and settings are untouched, and the tests get a fresh ~/AgentLink. addon starts a run: its folder "
             "in FreeCAD's Mod folder (one the launcher installed) or AgentLink; pattern: test files (test_*.py); select: only tests whose id "
             f"holds it; timeout: seconds ({testrun.TIMEOUT:g}, at most {testrun.TIMEOUT_MAX:g}). It answers at once with the job (the result "
             f"itself when it finishes within {testrun.START_WAIT:g} s); job answers how it stands (counts so far, or the counts, the time and each "
             f"failure's last traceback lines), waiting up to {testrun.STATUS_WAIT:g} s for the end. Neither: the recent jobs. The full log is "
             "under ~/AgentLink/tests; a run is stopped at its timeout or when FreeCAD quits.",
             obj({"addon": st, "job": st, "pattern": st, "select": st, "timeout": {"type": "number"}}), addon_test),
    ]
