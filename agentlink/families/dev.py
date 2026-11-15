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


def tools(s):
    def addon_test(a):
        addon = a.get("addon")
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
        pump = None
        if getattr(FreeCAD, "GuiUp", False):
            from .. import echo

            def pump():
                echo._paint(200)  # the window keeps painting while the tests run

        log = keep.path("tests", f"{addon}-{keep.stamp()}.log")
        return testrun.run(cmd, addon, root, OWN_ROOT, roots, lib, log, pattern, select, float(timeout), pump)

    st = {"type": "string"}
    return [
        Tool("addon_test",
             "Run an installed add-on's own tests (its tests/ folder) in a separate FreeCAD command-line process, never this FreeCAD: "
             "documents, the window and settings are untouched, and the tests get a fresh ~/AgentLink. addon: its folder in FreeCAD's Mod "
             "folder (one the launcher installed) or AgentLink; pattern: test files (test_*.py); select: only tests whose id holds it; "
             f"timeout: seconds ({testrun.TIMEOUT:g}, at most {testrun.TIMEOUT_MAX:g}). Answers the counts, the time and each failure's last "
             "traceback lines; the full log is written under ~/AgentLink/tests.",
             obj({"addon": st, "pattern": st, "select": st, "timeout": {"type": "number"}}, ["addon"]), addon_test),
    ]
