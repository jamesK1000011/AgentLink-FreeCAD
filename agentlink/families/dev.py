# SPDX-License-Identifier: LGPL-2.1-or-later
# For add-on developers: an installed add-on's own tests, run in a separate
# FreeCAD command-line process on this computer (agentlink/testrun.py), so
# a suite runs in the real FreeCAD without CI and without touching the
# window, the hidden FreeCAD or their documents; and gui_input, mouse and
# keyboard input for the window's own GUI checks, sent as Qt events from
# inside FreeCAD (agentlink/gui_input.py). Not in the lean list.

import os
import types

import FreeCAD

from .. import keep, paths, testrun
from ..protocol import Tool, ToolError, bad
from ..tools import obj
from .unattended import installed_names, mod_dir

GROUP = "dev"
INFO = "For add-on developers: an installed add-on's own test suite run in a separate FreeCAD process (addon_test); mouse and keyboard input to the window's own widgets for GUI checks (gui_input)."

OWN_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _pump():
    if not getattr(FreeCAD, "GuiUp", False):
        return None
    from .. import echo

    def pump():
        echo._paint(200)  # the window keeps painting while the call waits

    return pump


def tools(s):
    from ..gui_input import DRAG_STEPS as gi_steps
    from ..gui_input import MAX_WAIT as gi_wait

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

    def gui_input(a):
        from .. import gui_input as gi

        if not getattr(FreeCAD, "GuiUp", False):
            raise ToolError("unavailable", "gui_input sends mouse and keyboard input to the FreeCAD window, and this FreeCAD has none (headless): it runs through the window's link (Agent Link > Start Link).")
        steps = gi.parse_steps(a.get("steps"))
        import FreeCADGui

        from .. import gui_link, report_watch
        from ..grab import grab_window

        QtGui, QtWidgets = gui_link._qt()
        from PySide import QtCore

        qt = types.SimpleNamespace(QtCore=QtCore, QtGui=QtGui, QtWidgets=QtWidgets)
        shot_dir = os.path.join(s.out_dir, "gui_input")
        run = gi.Run(qt, FreeCADGui, FreeCAD.Vector, gui_link.modal_info, report_watch.take, grab_window,
                     lambda body: gui_link.answer_now("gui_input", body), shot_dir)
        # Its shots noted as the call's outputs (agentlink/outputs.py).
        for st in steps:
            if st.get("do") == "shot":
                for n in (st["name"] + ".png", st["name"] + "-front.png"):
                    paths.made(s, os.path.join(shot_dir, n), "shot")
        out = run.run(steps)
        if run.shots and a.get("inline", True) and not run.answered:
            try:
                with open(run.shots[-1], "rb") as f:
                    out["_png"] = f.read()
            except OSError:
                pass
        return out

    st = {"type": "string"}
    return [
        Tool("gui_input",
             "Mouse and keyboard input to the FreeCAD window's own widgets, sent as Qt events from inside FreeCAD — never the system cursor or "
             "keyboard, so the person keeps their screen. "
             "Window only. steps, in order, each: {click: T, button?: left|right|middle, double?, modifiers?: [shift, ctrl, alt, meta]}; "
             "{press: T} {move: T} {release: T} (a held button's moves and release go to the widget that took the press); "
             f"{{drag: {{from: T, to: T, steps?: {gi_steps}, button?, modifiers?}}}}; {{scroll: T, dy: notches (over 0 rolls away)}}; "
             "{key: \"Return\"|\"Escape\"|\"F2\"|\"a\"…, modifiers?, target?: T} and {type: \"text\", target?: T} to the focused widget or T; "
             f"{{wait: ms (≤{gi_wait})}}; {{shot: name}} (the window as a PNG in ~/AgentLink/gui_input; the last one shown unless inline: false). "
             "Targets T: {view: [x, y]} logical pixels from the active 3D view's top-left; {view_world: [x, y, z]} a model point projected there; "
             "{widget: {objectName?, text?, toolTip?, class?, under?: dock or dialog title}, at?: [dx, dy] from its top-left (centre by default)} "
             "the first visible match; {tab: {text, under?}}; {item: {text, under?, column?}, check?: true} a list, tree or table row "
             "(check: its box); {window: [x, y]} main-window pixels. While a dialog or menu is in front only targets inside it are taken. "
             "Answers per step what it hit (class, name, text, where), a dialog or menu it opened (the answer comes at once while it "
             "holds the window: dialog_answer or more gui_input inside it), new Report problems. Shortcuts are not triggered (cmd_run).",
             obj({"steps": {"type": "array", "items": {"type": "object"}}, "inline": {"type": "boolean"}}, ["steps"]), gui_input),
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
