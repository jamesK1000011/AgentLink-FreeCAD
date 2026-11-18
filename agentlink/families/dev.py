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

from .. import keep, paths, runners, testrun
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

    # ---- addon_test and gui_unstick are data (agentlink/data/tools.json): what their entries call ----

    def find_cmd():
        """(FreeCAD's command-line binary, its library folder) beside this
        FreeCAD, in FREECAD_APP or on the PATH; (None, None) when there is
        none."""
        try:
            home = FreeCAD.getHomePath()
        except Exception:  # noqa: BLE001
            home = None
        return testrun.find_cmd(home=home)

    def job_wait(job):
        """How a test job stands, waiting a while for its end (the window
        keeps painting meanwhile)."""
        return testrun.wait(testrun.find(job), testrun.STATUS_WAIT, _pump())

    def started(cmd, addon, root, mod, installed, lib, pattern, select, timeout, folder):
        """A test run started apart from this FreeCAD, with the other
        installed add-ons on its path and its log under ~/AgentLink/tests;
        its job (the result itself when it ends at once)."""
        roots = [os.path.join(mod, n) for n in sorted((installed or set()) - {"AgentLink", "AddonManager"}) if os.path.isdir(os.path.join(mod, n))]
        log = keep.path("tests", f"{addon}-{keep.stamp()}.log")
        return testrun.wait(testrun.start(cmd, addon, root, OWN_ROOT, roots, lib, log, pattern, select, timeout, folder), testrun.START_WAIT, _pump())

    def unstick(all_):
        """The menu, list or dialog in front closed (gui_link.unstick):
        what was closed and what is still open."""
        from .. import gui_link

        return gui_link.unstick(all_=all_)

    helpers = {
        "listing": lambda: testrun.listing(), "job_wait": job_wait, "fits": lambda what, text: bool(getattr(testrun, what).fullmatch(text)),
        "test_timeouts": lambda: (testrun.TIMEOUT, testrun.TIMEOUT_MAX), "mod_dir": lambda: mod_dir(), "installed_names": lambda mod: installed_names(mod),
        "test_root": lambda addon, mod, installed: testrun.root_for(addon, mod, OWN_ROOT, installed), "find_cmd": find_cmd, "started": started,
        "unstick": unstick,
    }

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
             "Send mouse and keyboard input to the widgets of the FreeCAD window, as Qt events inside FreeCAD. It never uses the system cursor or keyboard. Window "
             "only. steps: in order, each one of these. {click: T, button?: left|right|middle, double?, modifiers?: [shift, ctrl, alt, meta]}. {press: T} {move: T} "
             f"{{release: T}}: after a press, they go to the pressed widget. {{drag: {{from: T, to: T, steps?: {gi_steps}, button?, modifiers?}}}}. {{scroll: T, dy: "
             "notches}: more than 0 rolls away. {key: \"Return\"|\"Escape\"|\"F2\"|\"a\"…, modifiers?, target?: T} and {type: \"text\", target?: T}: to the focused widget or "
             f"T. {{wait: ms (≤{gi_wait})}}. {{shot: name}}: a window PNG in ~/AgentLink/gui_input; the last shows unless inline: false. Targets T follow. {{view: [x, "
             "y]}: logical pixels from the top-left of the active 3D view. {view_world: [x, y, z]}: a model point projected there. {widget: {objectName?, text?, "
             "toolTip?, class?, under?: dock or dialog title}, at?: [dx, dy]}: the first visible match. at is from its top-left (centre by default). {tab: {text, "
             "under?}}. {item: {text, under?, column?}, check?: true}: a row of a list, tree or table (check: its box). {menu_item: \"text\"}: an item of the open "
             "menu. {window: [x, y]}: main-window pixels. While a dialog or menu is in front, the tool takes only targets inside it. For each step, the answer gives "
             "what it hit (class, name, text, where). It also gives a dialog or menu that it opened; later steps run inside it. open: what still "
             "holds the window at the end. Close it with Escape, dialog_answer or gui_unstick. Also new Report problems. {shortcut: \"Shift+V\"}: runs "
             "the enabled command with that shortcut ({key} does not). The proof that a step worked is what the tools read back after it, not the shot. Use session_state, selection { clear: false }, object_get. "
             "Face and edge names change with the model. Aim view_world at a point on the face, after cmd_run Std_ViewIsometric and Std_ViewFitAll.",
             obj({"steps": {"type": "array", "items": {"type": "object"}}, "inline": {"type": "boolean"},
                  "as": {"type": "string", "enum": ["person"],
                         "description": "Dev, testing an add-on that follows the person: this call's input counts as the person's, not the agent's."}},
                 ["steps"]), gui_input),
        Tool("live_run",
             "Replay a live window script (scripts/live, the format of its README) and check the answers of every step. First reset the test document, every time. "
             "live_run { script: \"reset\" } closes what earlier runs left, builds the WindowTest document again and brings it to the front. Every other script must "
             "start from exactly that. Without it, a script acts on the document in front. Then its checks fail for reasons that are not the tools'. script: a name "
             "(reset, agentlink, or another found in the scripts/live folders of the installed add-ons). The tool refuses a wrong name, and gives the names there "
             "are. Or the path of a .json file. steps: only these (names or numbers from 0; all by default). A later step run alone acts on the document in front. "
             "What the steps before it would make is then missing. The calls of each step go to batch (rollback: false, stopOnError: false). When the step is "
             "direct, they go one by one. vars { name: value } and earlier answers fill in $names. A $name that the script declares is kept from the latest answer "
             "that has that key: $next. The tool skips a step that needs a $name not known yet, and tells which. The tool skips two-role steps (role: student, "
             "parallel): they need two agents (ROLES.md). The tool checks every expect: equals, contains, atLeast, atMost, exists, noneContain with ignoreLinesWith. "
             "Paths have dots; [*] is any item, [-1] the last. A call with allow: [codes] can be refused with one of them, and its step does not fail "
             "(allowedRefusals). reset closes documents that are possibly not open. A gui_input that opens a dialog does not end the replay. Inside the dialog's "
             "loop, the step's calls after it and the next steps' calls run one at a time. They run only while the dialog is still open, so the step that answers it "
             "runs. When the dialog closes, the replay returns, the dialog's loop ends, and the rest runs after it. The tool runs a step answered busy once again "
             "after a short wait. At the end, the tool closes anything left open (gui_unstick) and tells it in leftOpen. budget: seconds that the replay can hold "
             f"the window ({ls.BUDGET:g} by default, at most {ls.BUDGET_MAX:g}). No call starts after it, and the answer names the steps not run (notRun). live_run {{ "
             "steps: [...] } runs them, so you can split a long script across calls. A nested event loop that still holds the window after the budget gets closed. "
             "Then the call answers with what ran so far, and the watchdog starts FreeCAD again. The answer is always the summary of live_run itself. Answer: total "
             "{ passed, failed, skipped, run } and steps. Each step has result pass, fail or skipped. It also has a failing check's call, path, wanted and got, and "
             "refused calls. It also has the step's shot (a window picture, in the window) and look (what it must show). Also the totals. stopOnFail: true stops at "
             "the first failing step. It changes the document as the script does.",
             obj({"script": st, "steps": {"type": "array", "items": {}}, "vars": {"type": "object"}, "stopOnFail": {"type": "boolean"}, "budget": {"type": "number"}}, ["script"]), live_run),
    ] + runners.tools(GROUP, s, helpers)
