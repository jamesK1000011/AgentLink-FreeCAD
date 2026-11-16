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
from .. import livescript as ls

GROUP = "dev"
INFO = "For add-on developers: an installed add-on's own test suite run in a separate FreeCAD process (addon_test); live window scripts replayed and checked (live_run); mouse and keyboard input to the window's own widgets for GUI checks (gui_input), and closing a menu or dialog that holds the window (gui_unstick)."

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
            raise bad("addon starts a run, job reads one: give one of them (neither lists the recent jobs).")
        if job is not None:
            return testrun.wait(testrun.find(job), testrun.STATUS_WAIT, _pump())
        if addon is None:
            return testrun.listing()
        pattern = a.get("pattern") or "test_*.py"
        select = a.get("select") or None
        timeout = a.get("timeout", testrun.TIMEOUT)
        folder = a.get("folder") or None
        if not testrun.PATTERN.fullmatch(str(pattern)):
            raise bad("pattern: a file name glob ending in .py, no folders (test_*.py by default).")
        if select is not None and not testrun.SELECT.fullmatch(str(select)):
            raise bad("select: letters, digits and _ (part of a test's name).")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= testrun.TIMEOUT_MAX:
            raise bad(f"timeout: seconds, over 0 and at most {testrun.TIMEOUT_MAX:g} ({testrun.TIMEOUT:g} by default).")
        if folder is not None and not testrun.FOLDER.fullmatch(str(folder)):
            raise bad('folder: a subfolder of tests/, such as "make" (names joined by /; no "..").')
        mod = mod_dir()
        installed = installed_names(mod)
        root = testrun.root_for(addon, mod, OWN_ROOT, installed)
        try:
            home = FreeCAD.getHomePath()
        except Exception:  # noqa: BLE001
            home = None
        cmd, lib = testrun.find_cmd(home=home)
        if cmd is None:
            raise ToolError("unavailable", "No FreeCAD command-line binary (freecadcmd) beside this FreeCAD, in FREECAD_APP or on the PATH: the tests need it to run apart from this FreeCAD. Nothing was started.")
        roots = [os.path.join(mod, n) for n in sorted((installed or set()) - {"AgentLink", "AddonManager"}) if os.path.isdir(os.path.join(mod, n))]
        log = keep.path("tests", f"{addon}-{keep.stamp()}.log")
        return testrun.wait(testrun.start(cmd, addon, root, OWN_ROOT, roots, lib, log, pattern, select, float(timeout), folder), testrun.START_WAIT, _pump())

    def gui_input(a):
        from .. import gui_input as gi

        if not getattr(FreeCAD, "GuiUp", False):
            raise ToolError("unavailable", "gui_input sends mouse and keyboard input to the FreeCAD window, and this FreeCAD has none (headless): it runs through the window's link (Agent Link > Start Link). session_state says where calls go (where: window).")
        steps = gi.parse_steps(a.get("steps"))
        as_ = a.get("as")
        if as_ is not None and as_ != "person":
            raise bad('as: "person" (the steps\' input counts as the person\'s), or leave it out.')
        import FreeCADGui

        from .. import gui_link, report_watch
        from ..grab import grab_window

        QtGui, QtWidgets = gui_link._qt()
        from PySide import QtCore

        qt = types.SimpleNamespace(QtCore=QtCore, QtGui=QtGui, QtWidgets=QtWidgets)
        shot_dir = os.path.join(s.out_dir, "gui_input")
        run = gi.Run(qt, FreeCADGui, FreeCAD.Vector, gui_link.modal_info, report_watch.take, grab_window,
                     lambda body: gui_link.answer_now("gui_input", body), shot_dir,
                     ticker=gui_link.ticker, seen=gui_link.front_seen)
        # How long the call may take: past it, the link answers it "busy" from
        # its socket thread (a step's menu or dialog that nothing could see).
        gui_link.expect("gui_input", sum(st.get("ms", 0) for st in steps) / 1000.0 + gi.BUSY_AFTER)
        # Its shots noted as the call's outputs (agentlink/outputs.py).
        for st in steps:
            if st.get("do") == "shot":
                for n in (st["name"] + ".png", st["name"] + "-front.png"):
                    paths.made(s, os.path.join(shot_dir, n), "shot")
        from .. import hooks

        if as_ == "person":
            # Dev only: a student agent standing in for the person. The steps'
            # window events are the person's (hooks.person_input), and so is
            # this call's call_done (session.done_by); nothing else changes.
            run.as_ = "person"
            with hooks.person_input() as p:
                run.person = p
                try:
                    out = run.run(steps)
                finally:
                    s.done_by = hooks.PERSON
        else:
            out = run.run(steps)
        if not run.answered:
            # Done on its own: its deadline no longer stands over a batch
            # (or a live_run) that goes on after it.
            gui_link.expect_done("gui_input")
        if run.shots and a.get("inline", True) and not run.answered:
            try:
                with open(run.shots[-1], "rb") as f:
                    out["_png"] = f.read()
            except OSError:
                pass
        return out

    def gui_unstick(a):
        from .. import gui_link

        return gui_link.unstick(all_=bool(a.get("all", False)))

    # Answered on the link's socket thread: it works while a menu's or a
    # dialog's own event loop holds the GUI thread (agentlink/hooks.py).
    from .. import hooks

    hooks.register_thread_tool("gui_unstick")

    def live_run(a):
        import json as _json

        from .. import livescript as ls

        name = a.get("script")
        if not isinstance(name, str) or not name.strip():
            raise bad("script: a live script's name (reset, agentlink, or one an installed add-on ships in its scripts/live folder) or a .json file's path.")
        roots = [OWN_ROOT]
        try:
            md = mod_dir()
            roots += [os.path.join(md, d) for d in sorted(os.listdir(md)) if os.path.isdir(os.path.join(md, d))]
        except Exception:
            pass
        p = None
        if not any(c in name for c in "/\\") and not name.startswith("~"):
            p = ls.find_script(name, roots)
        if p is None:
            q = paths.in_file(s, "live_run", name, "script")
            if os.path.isfile(q):
                p = q
        if p is None:
            have = sorted({f[:-5] for r in roots for f in (os.listdir(os.path.join(r, "scripts", "live")) if os.path.isdir(os.path.join(r, "scripts", "live")) else []) if f.endswith(".json")})
            raise ToolError("not_found", f"script: {name} — no such live script. Installed: {', '.join(have) or 'none'}; or a .json file's path. Start with live_run {{ script: \"reset\" }}.")
        script = ls.load(p)
        chosen = ls.pick_steps(script["steps"], a.get("steps"))

        def call(tool, args):
            r = s.server.call({"name": tool, "arguments": args})
            try:
                body = _json.loads(r["content"][0]["text"])
            except (KeyError, IndexError, ValueError):
                body = {}
            ok = not r.get("isError")
            return {"tool": tool, "ok": ok, **({"result": body} if ok else {"error": body.get("error", body)})}

        def shot(n):
            r = call("gui_input", {"steps": [{"shot": n}], "inline": False})
            f = os.path.join(s.out_dir, "gui_input", n + ".png")
            return f if r.get("ok") and os.path.isfile(f) else None

        vars_ = a.get("vars") or {}
        if not isinstance(vars_, dict):
            raise bad("vars: { name: value } for the script's $names (without the $).")
        budget = a.get("budget", ls.BUDGET)
        if budget is not None and (isinstance(budget, bool) or not isinstance(budget, (int, float)) or budget <= 0):
            raise bad(f"budget: seconds the replay may hold the window ({ls.BUDGET:g} by default, at most {ls.BUDGET_MAX:g}).")
        budget = min(float(budget), ls.BUDGET_MAX) if budget is not None else ls.BUDGET
        gui = bool(getattr(FreeCAD, "GuiUp", False))
        live = None
        if gui:
            import time as _t

            from .. import gui_input as gi
            from .. import gui_link

            def front():
                QtGui, QtWidgets = gui_link._qt()
                f = gi.describe_front(QtWidgets.QApplication.instance(), gui_link.modal_info)
                return None if not f or f.get("kind") == "progress" else f

            def sleep(sec):
                # The window's own events go on meanwhile (a progress
                # dialog closing, a job finishing).
                QtGui, QtWidgets = gui_link._qt()
                end = _t.time() + sec
                while _t.time() < end:
                    QtWidgets.QApplication.processEvents()
                    _t.sleep(0.05)

            import agentlink_state

            link = getattr(agentlink_state, "link", None)
            # The client's call in hand (live_run itself, or the batch it is
            # in, with that batch's progress): the guard's answer goes there.
            mine = (getattr(link, "calls", None) or [None])[-1] if link is not None else None
            outer_bn = getattr(s, "batch_now", None)

            def watch(summary):
                # Ticked from inside whatever event loop holds the window:
                # past the budget, a nested loop that never ended is closed,
                # woken, and at last answered for (livescript.Guard).
                g = ls.Guard(budget, _t.time, gui_link.loop_level,
                             unstick=lambda: (gui_link.close_front(True), gui_link.wake()),
                             answer=lambda body: gui_link.answer_call(mine, "live_run", body, outer_bn),
                             stuck=lambda body: gui_link.held_stuck(body.get("note")))
                g.summary = summary
                return gui_link.ticker(g.tick, 1000)

            live = types.SimpleNamespace(push=gui_link.CONTINUE.append, pop=gui_link.CONTINUE.pop,
                                         batch_now=lambda: getattr(s, "batch_now", None), front=front,
                                         unstick=lambda: call("gui_unstick", {"all": True}), sleep=sleep,
                                         wake=gui_link.wake, watch=watch)
            # For the heartbeat: done by then (its budget, a call's grace and
            # the guard's), or the watchdog takes a nested loop as a hang.
            gui_link.until(_t.time() + budget + ls.LAST_CALL_GRACE + 2 * ls.GUARD_GRACE)
        prev = getattr(s, "live_now", None)
        s.live_now = True
        try:
            out = ls.run(script, chosen, call, vars_, bool(a.get("stopOnFail", False)), shot if gui else None, live, budget=budget)
        finally:
            s.live_now = prev
            if gui:
                gui_link.until(None)
        out["file"] = p
        return out

    st = {"type": "string"}
    return [
        Tool("gui_input",
             "Mouse and keyboard input to the FreeCAD window's own widgets as Qt events inside FreeCAD, never the system cursor or keyboard. "
             "Window only. steps, in order, each: {click: T, button?: left|right|middle, double?, modifiers?: [shift, ctrl, alt, meta]}; "
             "{press: T} {move: T} {release: T} (after a press they go to the pressed widget); "
             f"{{drag: {{from: T, to: T, steps?: {gi_steps}, button?, modifiers?}}}}; {{scroll: T, dy: notches (over 0 rolls away)}}; "
             "{key: \"Return\"|\"Escape\"|\"F2\"|\"a\"…, modifiers?, target?: T} and {type: \"text\", target?: T} to the focused widget or T; "
             f"{{wait: ms (≤{gi_wait})}}; {{shot: name}} (a window PNG in ~/AgentLink/gui_input; the last shown unless inline: false). "
             "Targets T: {view: [x, y]} logical pixels from the active 3D view's top-left; {view_world: [x, y, z]} a model point projected there; "
             "{widget: {objectName?, text?, toolTip?, class?, under?: dock or dialog title}, at?: [dx, dy] from its top-left (centre by default)} "
             "the first visible match; {tab: {text, under?}}; {item: {text, under?, column?}, check?: true} a list, tree or table row "
             "(check: its box); {menu_item: \"text\"} an item of the open menu; {window: [x, y]} main-window pixels. While a dialog or menu is in front only targets inside it are taken. "
             "Answers per step what it hit (class, name, text, where), a dialog or menu it opened (later steps run inside it), "
             "open: what still holds the window at the end (close it: Escape, dialog_answer or gui_unstick), new Report problems. Shortcuts are not triggered (cmd_run). Proof that a step worked is what the tools read back afterwards (session_state, selection { clear: false }, object_get), not the shot. Face and edge names change with the model: aim view_world at a point on the face, after cmd_run Std_ViewIsometric and Std_ViewFitAll.",
             obj({"steps": {"type": "array", "items": {"type": "object"}}, "inline": {"type": "boolean"},
                  "as": {"type": "string", "enum": ["person"],
                         "description": "Dev, testing an add-on that follows the person: this call's input counts as the person's, not the agent's."}},
                 ["steps"]), gui_input),
        Tool("gui_unstick",
             "Close the menu, drop-down list or dialog that holds the FreeCAD window (Escape's effect: a menu closes, a dialog is cancelled, nothing in it is accepted), "
             "even while it holds every other call (it is answered off the GUI thread). all: true closes each one in front, dialogs under a menu too. Reply: what was closed and "
             "what is still open (dialog_answer presses a named button instead; a window that stays stuck: app_force_restart). Window only.",
             obj({"all": {"type": "boolean"}}), gui_unstick),
        Tool("live_run",
             "Replay a live window script (scripts/live, its README's format) and check it: script is a name (reset, agentlink, or another found in the installed add-ons' scripts/live folders; a wrong name lists them) or a .json file's path; "
             "Every script starts from live_run { script: \"reset\" } (it rebuilds the WindowTest document and brings it to the front): run that first, each time. "
             "steps: only these (names or numbers from 0; all by default) — a later step run alone acts on whatever document is in front, with what the steps before it would have made missing. Each step's calls go to batch (rollback: false, stopOnError: false), or one by one when the step is direct; "
             "$names are filled in from vars { name: value } and from earlier answers (a $name the script declares, kept from the latest answer that has that key: $next); a step that needs one not known yet is skipped and says which. "
             "Two-role steps (role: student, parallel) are skipped: they need two agents (ROLES.md). Every expect is checked (equals, contains, atLeast, atMost, exists, noneContain with ignoreLinesWith; paths with dots, [*] any item, [-1] the last). "
             "A call with allow: [codes] may be refused with one of them without failing its step (allowedRefusals; reset closes documents that may not be open). A gui_input that opens a dialog does not end the replay: inside the dialog's loop, the step's calls after it and the next steps' calls run one at a time only while the dialog is still open (so the step that answers it runs); once it closes the replay returns, the dialog's loop ends, and the rest runs after it; a step answered busy is run again once after a short wait; anything left open at the end is closed (gui_unstick) and said in leftOpen. "
             f"budget: seconds the replay may hold the window ({ls.BUDGET:g} by default, at most {ls.BUDGET_MAX:g}): no call starts past it, and the answer names the steps not run (notRun) — live_run {{ steps: [...] }} runs them, so a long script is split across calls. A nested event loop still holding the window past the budget is closed, then the call is answered with what ran so far and FreeCAD is started again by the watchdog. The answer is always live_run's own summary. "
             "Reply: total { passed, failed, skipped, run } and steps, each with result pass, fail or skipped, a failing check's call, path, wanted and got, refused calls, the step's shot (a window picture, in the window) and look (what it should show), and the totals. stopOnFail: true stops at the first failing step. It changes the document as the script does.",
             obj({"script": st, "steps": {"type": "array", "items": {}}, "vars": {"type": "object"}, "stopOnFail": {"type": "boolean"}, "budget": {"type": "number"}}, ["script"]), live_run),
        Tool("addon_test",
             "An installed add-on's own tests (its tests/ folder) run in the background in a separate FreeCAD command-line process, never this "
             "FreeCAD: documents, the window and settings are untouched, and the tests get a fresh ~/AgentLink. addon starts a run: its folder "
             "in FreeCAD's Mod folder (one the launcher installed) or AgentLink; folder: only this subfolder of tests/ (e.g. make); pattern: test files (test_*.py); select: only tests whose id "
             f"holds it; timeout: seconds ({testrun.TIMEOUT:g}, at most {testrun.TIMEOUT_MAX:g}). It answers at once with the job (the result "
             f"itself when it finishes within {testrun.START_WAIT:g} s); job answers how it stands (counts so far, or the counts, the time and each "
             f"failure's last traceback lines), waiting up to {testrun.STATUS_WAIT:g} s for the end — call it again while state is running. Neither: the recent jobs. The full log is "
             "under ~/AgentLink/tests; a run is stopped at its timeout or when FreeCAD quits.",
             obj({"addon": st, "job": st, "folder": st, "pattern": st, "select": st, "timeout": {"type": "number"}}), addon_test),
    ]
