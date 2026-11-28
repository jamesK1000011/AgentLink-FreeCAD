# SPDX-License-Identifier: LGPL-2.1-or-later
# The link in the FreeCAD window: the same six tools, served on a local port
# (127.0.0.1 only) to the stdio relay an MCP client starts
# (agentlink_headless.py --connect). A thread reads the socket; every call
# runs on the GUI's own thread, from a timer, because FreeCAD's documents
# and the 3D view must not be touched from another — so the person sees
# each body arrive in the document they have open.

import json
import os
import queue
import socket
import sys
import threading
import time

import FreeCAD

from .protocol import FRONT_CALLS as _FRONT_CALLS
from .protocol import WIRE_ERRORS, compact, front_call, retry_once_ok, set_kind
from .tools import Session, build_server

PORT = 7318
# Calls that go on when the agent's pinned document was closed: they choose
# another, or read where things stand.
# Tools that act on the document in front of the window, not the agent's
# own: refused when the person has another in front (K), rather than acting
# on theirs.
FRONT_TOOLS = {"cmd_run", "menu_run", "view_snapshot"}
# A call not taken off the inbox this long while a menu or dialog holds the
# window (or past the call in hand's own time) is answered "busy" from the
# socket thread, not left waiting for ever.
BUSY_AFTER = 10.0
# A queued call due to be answered busy (it was not started) is tried once
# more after this many seconds: the menu or dialog that held the window may
# have closed by then (E10). Its answer then carries _meta.retried: 1.
RETRY_DELAY = 1.5
# The clock the busy watch reads (a test puts a fake one here).
_clock = time.time
# A call answered early whose menu or dialog closed: calls wait this long for
# the rest of it before they are answered busy.
ENDING_WAIT = 30.0
# A call that answers the dialog in front (dialog_answer, gui_input, a batch
# of them: front_call) waits this long for the dialog's loop to take it
# before it is answered busy: it is the way out of the dialog.
FRONT_WAIT = 60.0
# Calls answered after the person closed the document the agent worked in:
# Agent Link's own, and those add-ons declare (a family's PINNED_FREE,
# families.PINNED_FREE). The recovery tool's name stays here only until its
# add-on declares it.
PINNED_FREE = {"doc_open", "doc_new", "doc_switch", "session_state", "tool_groups", "guide_read", "app_recover", "dialog_answer", "usage_report", "doc_close", "report_read",
               "tool_find", "job_status", "crash_collect", "app_extensions", "queue_go"}
# Of those, the reads of the catalogue, the guides and the session that need
# no document at all (live, 18 Nov: tool_find was refused "AgentLink was
# closed"): they leave the word that the document was closed for the next
# call that works on one.
CATALOGUE_READS = {"tool_find", "tool_groups", "guide_read", "usage_report", "report_read", "job_status", "crash_collect", "app_extensions"}


def _batch_calls(line):
    """The tool names of a batch call's calls, or None for another call."""
    try:
        m = json.loads(line)
        p = m.get("params") or {}
        if p.get("name") != "batch":
            return None
        calls = (p.get("arguments") or {}).get("calls")
        if not isinstance(calls, list) or not calls:
            return None
        return [c.get("tool") if isinstance(c, dict) else None for c in calls]
    except (ValueError, AttributeError):
        return None


def pinned_free_call(line, name):
    """True when this call is answered without the pinned document: a
    pinned-free tool, or a batch of nothing else."""
    if name is None or pinned_free(name):
        return True
    names = _batch_calls(line) if name == "batch" else None
    return bool(names) and all(isinstance(n, str) and pinned_free(n) for n in names)


def catalogue_call(line, name):
    """A read of the catalogue, a guide or the session (or a batch of
    nothing else): it leaves the closed document's word for the next call."""
    if name in CATALOGUE_READS:
        return True
    names = _batch_calls(line) if name == "batch" else None
    return bool(names) and all(n in CATALOGUE_READS for n in names)


def pinned_free(name):
    """True when name is answered without the pinned document: core's own
    list or an add-on's declaration."""
    if name in PINNED_FREE:
        return True
    try:
        from . import families

        return name in families.PINNED_FREE
    except Exception:  # noqa: BLE001
        return False


def _tool_name(line):
    try:
        m = json.loads(line)
        return (m.get("params") or {}).get("name") if m.get("method") == "tools/call" else None
    except (ValueError, AttributeError):
        return None


def _dialog_call(line, read_ok=None, declared=None):
    """True for a call that runs while a modal dialog or a menu holds the
    window (protocol.front_call): dialog_answer, gui_input, gui_unstick, or
    a batch of those with reads beside them (window_snapshot, and the
    dialog reads: sketch_state, session_state and the like, live 56b). A
    client that lists only the lean groups reaches them through batch, and
    a refused batch left a dialog that the person-input path opened a dead
    end (live 56: a batch whose calls came as a string of JSON was not
    read). read_ok(tool, arguments): the window's check of each read;
    declared(tool, arguments): a read its tool's data declares (frontReads,
    live 56c: an add-on tool's status action)."""
    name = _tool_name(line)
    if name is None:
        return False
    try:
        args = (json.loads(line).get("params") or {}).get("arguments")
    except (ValueError, AttributeError):
        return False
    return front_call(name, args, read_ok, declared)


# What runs while a dialog or menu holds the window: it answers it.
FRONT_CALLS = _FRONT_CALLS


# batch arguments the socket thread's light batch does not do.
LIGHT_NOT = ("writeTo", "lines", "path", "start", "build")


def _thread_batch(line, tools):
    """The calls of a batch made only of socket-thread tools (a client lists
    tools only when it starts, so it reaches a new one through batch), or
    None."""
    try:
        m = json.loads(line)
        args = ((m.get("params") or {}).get("arguments") or {})
    except (ValueError, AttributeError):
        return None
    if _tool_name(line) != "batch":
        return None
    # A batch that asks for its answer written (writeTo), cut (lines), read
    # from a file (path) or started part way (start) goes the
    # whole batch's way: the light answer here knows none of those, and a
    # batch { calls: [job_status], writeTo, lines: "counts" } came back as the
    # job's whole answer (live, round 3).
    if any(args.get(k) is not None for k in LIGHT_NOT):
        return None
    calls = args.get("calls")
    if isinstance(calls, str):
        try:
            calls = json.loads(calls)
        except ValueError:
            return None
    if not isinstance(calls, list) or not calls or not all(isinstance(c, dict) and c.get("tool") in tools for c in calls):
        return None
    # A step with a loop, a file, or an old key goes the whole batch's way,
    # which reads it (and refuses an old form with the new form in its words).
    from .callshape import OLD_KEYS

    if any(k in ("each", "writeTo") or k in OLD_KEYS for c in calls for k in c):
        return None
    return calls


# ---- what the window shows: a modal dialog, and the heartbeat (unattended use, E and F) ----

def _qt():
    from PySide import QtGui

    try:
        from PySide import QtWidgets
    except ImportError:
        QtWidgets = QtGui
    return QtGui, QtWidgets


def shown_in(d, x):
    """True when the widget x, a child of the dialog d, shows now: visible,
    with a size, in d's own window or in a window of its own that shows
    (an expression editor open on one of d's fields). A popup that closed
    (FreeCAD keeps the expression editors it hid) lists nothing (live 85:
    two editors' Result and OK, Reset where one showed)."""
    try:
        if not x.isVisible():
            return False
        if hasattr(x, "width") and (x.width() <= 0 or x.height() <= 0):
            return False
        win = x.window() if hasattr(x, "window") else d
        if win is d or win is None:
            return True
        return bool(win.isVisible()) and not (hasattr(win, "isHidden") and win.isHidden())
    except Exception:  # noqa: BLE001
        return False


def modal_info():
    """The modal dialog in front, if any: { class, title, text, buttons,
    widget }. Qt keeps timers running inside a dialog's own loop, so this is
    read even while the dialog blocks the window."""
    try:
        QtGui, QtWidgets = _qt()
        app = QtWidgets.QApplication.instance()
        w = app.activeModalWidget() if app is not None else None
    except Exception:
        return None
    if w is None:
        return None
    parts = []
    for getter in ("text", "informativeText"):
        try:
            v = getattr(w, getter)()
            if v:
                parts.append(v)
        except Exception:
            pass
    if not parts:
        try:
            for lab in w.findChildren(QtWidgets.QLabel):
                if shown_in(w, lab) and lab.text():
                    parts.append(lab.text())
        except Exception:
            pass
    buttons = []
    try:
        for b in w.findChildren(QtWidgets.QAbstractButton):
            if shown_in(w, b) and b.isEnabled() and b.text() and not b.isCheckable():
                buttons.append(b.text().replace("&", ""))
    except Exception:
        pass
    import re as _re

    text = _re.sub(r"<[^>]+>", " ", " ".join(parts))
    try:
        oname = str(w.objectName() or "")
    except Exception:
        oname = ""
    return {"class": w.metaObject().className(), "title": w.windowTitle(), "text": " ".join(text.split())[:600], "buttons": buttons, "widget": w,
            **({"name": oname} if oname else {})}


def is_close_confirm(d):
    """FreeCAD's "Unsaved Document" box (MainWindow::confirmSave, object
    name confirmSave): "Save all changes to document … before closing?"."""
    if not isinstance(d, dict):
        return False
    text = str(d.get("text") or "").lower()
    return d.get("name") == "confirmSave" or (str(d.get("title") or "") == "Unsaved Document") or ("before closing" in text and "save" in text)


def unsafe_close_press(d, button, in_hand):
    """Finding 62: Save or Don't Save pressed on FreeCAD's close confirm
    while a call (in_hand: its tool names) closes the document under it.
    The close then goes on inside the box's own loop under the call's
    feet, and FreeCAD crashed (live, 18 Nov). The refusal's words, or None
    when the press is safe (Cancel, or the box came with no call in hand)."""
    if not is_close_confirm(d):
        return None
    b = str(button or "").lower().replace("&", "")
    if b in BACK_OUT or b in ("cancel", "escape"):
        return None
    under = [t for t in in_hand or () if t not in ("dialog_answer", "batch", "gui_unstick")]
    if not under:
        return None
    return (f"button: {button} is not pressed here. FreeCAD asks this while {under[0]} closes the document, and a Save or Don't Save "
            "inside that close crashed FreeCAD before. dialog_answer { button: \"Cancel\" } presses Cancel. doc_close { documents, discard: true } "
            "closes a document without a dialog, and doc_save keeps the changes.")


FILE_PRESS = ("save", "don't save", "dont save", "discard", "save all", "discard all", "yes", "yes to all", "replace", "overwrite", "ok")


def file_dialog_press(d, button):
    """A press on a file-level dialog that needs the person's approval
    (approve_file, agentlink/approvals.py): FreeCAD's close confirm (Save,
    Don't Save: one writes over the file, the other loses the changes) or
    a "replace the file" box. (title, text, button) for the approval, or
    None for any other press (Cancel always passes)."""
    if not isinstance(d, dict):
        return None
    b = str(button or "").lower().replace("&", "").strip()
    if b in BACK_OUT or b in ("cancel", "no", "no to all"):
        return None
    text = str(d.get("text") or "")
    low = text.lower()
    replace_box = ("already exists" in low or "exists already" in low) and ("replace" in low or "overwrite" in low)
    if not (is_close_confirm(d) or replace_box):
        return None
    if b not in FILE_PRESS:
        return None
    return str(d.get("title") or ""), " ".join(text.split())[:300], str(button)


def is_file_picker(d):
    """True for a file dialog: Qt's own QFileDialog, or FreeCAD's
    Gui::FileDialog or FileOptionsDialog (gui_input.FILE_DIALOG_CLASSES)."""
    from .gui_input import FILE_DIALOG_CLASSES, file_dialog_of

    if not isinstance(d, dict):
        return False
    if str(d.get("class") or "").split("::")[-1] in FILE_DIALOG_CLASSES:
        return True
    w = d.get("widget")
    try:
        return w is not None and file_dialog_of(w) is not None
    except Exception:  # noqa: BLE001
        return False


def file_picker_press(d, button):
    """Red team 4, R4-2: a press that accepts a file dialog (Save, Open …)
    takes a path that no tool checked. The refusal's words, or None (Cancel
    and the other back-out presses pass)."""
    if not is_file_picker(d):
        return None
    b = str(button or "").lower().replace("&", "").strip()
    if b in BACK_OUT or b in ("no",):
        return None
    return (f"button: {button} is not pressed in a file dialog: the path there is not checked. dialog_answer {{ button: \"Cancel\" }} "
            "presses Cancel. These tools take a path: doc_open { path }, doc_save { path }, "
            "import_file { path }, export { path }. cmd_run names the tool for each command that opens a file dialog.")


def calls_in_hand():
    """The tool names of the calls in hand in the window's link, outermost
    first. Never raises."""
    try:
        import agentlink_state

        link = getattr(agentlink_state, "link", None)
        return [c.get("name") for c in list(getattr(link, "calls", []) or []) if isinstance(c, dict)]
    except Exception:  # noqa: BLE001
        return []


def popup_info():
    """A menu open in front (a context menu's own event loop), as
    modal_info answers for a dialog; None when there is none."""
    try:
        QtGui, QtWidgets = _qt()
        app = QtWidgets.QApplication.instance()
        w = app.activePopupWidget() if app is not None else None
    except Exception:
        return None
    if w is None:
        return None
    try:
        items = [a.text().replace("&", "") for a in w.actions() if a.text() and a.isVisible()]
    except Exception:
        items = []
    return {"class": w.metaObject().className(), "kind": "menu", "title": "a menu", "text": "items: " + ", ".join(items[:20]),
            "items": items[:20], "buttons": [], "widget": w}


# ---- queued calls onto the GUI thread, from any thread ----
# A queued signal is a posted event: Qt delivers it inside whatever event
# loop runs, a menu's or a dialog's nested one included, and with none of
# Agent Link's own timers needed (a timer whose handler is on the stack is
# not fired again until it returns).

_POSTER = [None]


def make_poster():
    """An object living on the GUI thread (make it there) whose post(fn)
    runs fn there through a queued signal; safe to call from any thread."""
    from PySide import QtCore

    class Poster(QtCore.QObject):
        go = QtCore.Signal(object)

        def __init__(self):
            super().__init__()
            self.go.connect(self._run, QtCore.Qt.QueuedConnection)

        def _run(self, fn):
            try:
                fn()
            except Exception as e:  # noqa: BLE001
                try:
                    FreeCAD.Console.PrintLog(f"Agent Link: a queued call failed: {type(e).__name__}: {e}\n")
                except Exception:
                    pass

        def post(self, fn):
            self.go.emit(fn)

    return Poster()


def poster():
    """The GUI thread's poster: the link's, else one made now (call it on
    the GUI thread the first time)."""
    import agentlink_state

    link = getattr(agentlink_state, "link", None)
    p = getattr(link, "_poster", None) if link is not None else None
    if p is None:
        if _POSTER[0] is None:
            _POSTER[0] = make_poster()
        p = _POSTER[0]
    return p


def ticker(fn, ms=100):
    """fn called on the GUI thread every ms through queued calls from a
    thread of its own, until the function it answers is called (gui_input's
    watch: it runs inside a step's nested loop even where timers do not)."""
    p = poster()
    stop = threading.Event()

    def beat():
        while not stop.wait(ms / 1000.0):
            p.post(fn)

    threading.Thread(target=beat, name="agentlink-gui-ticker", daemon=True).start()
    return stop.set


def front_seen(info):
    """What the GUI thread last saw open in front (gui_input's steps, the
    heartbeat), for the socket thread's busy answers."""
    import agentlink_state

    link = getattr(agentlink_state, "link", None)
    if link is not None:
        link.front = info


def expect(tool, seconds):
    """The call in hand (tool, not in a batch) should be done within
    seconds: past that, unanswered, the link answers it busy from the
    socket thread (a step's menu or dialog that holds the window)."""
    import agentlink_state

    link = getattr(agentlink_state, "link", None)
    if link is not None and hasattr(link, "expect") and not _live_now():
        link.expect(tool, seconds)


def expect_done(tool):
    """The call (tool) that set a deadline with expect returned on its own:
    the deadline is lifted, so a batch going on after it (or a live_run) is
    not answered busy when it runs past it. A live add-on replay was
    answered busy twice, nothing open, from a shot's gui_input inside it."""
    import agentlink_state

    link = getattr(agentlink_state, "link", None)
    calls = getattr(link, "calls", None) if link is not None else None
    if calls:
        c = calls[-1]
        if c.get("expected") == tool and not c.get("answered"):
            c.pop("deadline", None)
            c.pop("expected", None)


def close_front(all_=False):
    """On the GUI thread: the menus (and drop-down lists) in front closed,
    else the modal dialog in front cancelled; all_: every one in front.
    { closed: [...], open: what is left }."""
    from . import gui_input as gi

    QtGui, QtWidgets = _qt()
    app = QtWidgets.QApplication.instance()
    closed = []
    for _ in range(12):
        p = app.activePopupWidget()
        if p is not None:
            closed.append(gi.describe_popup(p))
            p.close()
            if app.activePopupWidget() is p:
                p.hide()
            continue
        if closed and not all_:
            break
        m = app.activeModalWidget()
        if m is None:
            break
        closed.append({"kind": "dialog", "title": m.windowTitle()})
        if hasattr(m, "reject"):
            m.reject()
        else:
            m.close()
        if not all_:
            break
    left = gi.describe_front(app, modal_info)
    front_seen(left)
    return {"closed": closed, "open": left}


def unstick(all_=False, wait=3.0):
    """gui_unstick, on the socket thread: close_front run on the GUI thread
    through a queued call (a nested loop delivers it), waited for."""
    import agentlink_state

    from .protocol import ToolError

    link = getattr(agentlink_state, "link", None)
    p = getattr(link, "_poster", None) if link is not None else None
    if p is None:
        raise ToolError("unavailable", "gui_unstick closes what holds the FreeCAD window, through the window's link (Agent Link > Start Link); this FreeCAD has none.")
    if threading.current_thread() is threading.main_thread():
        # Run on the GUI thread itself (a batch inside the menu's loop): a
        # queued call it waited for could never run.
        return close_front(all_)
    done, box = threading.Event(), {}

    def on_gui():
        try:
            box["out"] = close_front(all_)
        except Exception as e:  # noqa: BLE001
            box["err"] = f"{type(e).__name__}: {e}"
        finally:
            done.set()

    p.post(on_gui)
    if not done.wait(wait):
        raise ToolError("busy", f"The window took no queued call in {wait:g} s: something other than a menu or dialog holds it. app_force_restart starts it again.")
    if "err" in box:
        raise ToolError("failed", "gui_unstick: " + box["err"])
    return box["out"]


def _meter_dialog(link, d):
    """The usage log's dialog record (usage.Meter.dialog_seen): told each
    heartbeat which dialog is in front, or None. Never raises."""
    try:
        m = getattr(getattr(link, "server", None), "meter", None)
        if m is not None:
            m.dialog_seen(d)
    except Exception:  # noqa: BLE001 - the log only
        pass



def _new_start_doc():
    """Agent Link's own empty start document (tools.new_start_doc), read
    late: the tests put a stand-in tools module in its place."""
    from . import tools as _t

    make = getattr(_t, "new_start_doc", None)
    return make() if make else FreeCAD.newDocument("AgentLink")


class _Line(str):
    """A line read off a connection, with its ticket: queued, taken (by the
    GUI thread) or busy (answered from the socket thread instead)."""

    ticket = None


def blocked_words(d):
    """The refusal for a call that came while d (modal_info, popup_info)
    holds the window."""
    if not d:
        return "The window is busy with a call that is waiting on a dialog: this call was not run."
    if d.get("kind") == "menu" or d.get("title") == "a menu":
        items = d.get("items") or []
        return (f"Blocked by a menu in the FreeCAD window" + (f" (items: {', '.join(items[:12])})" if items else "") + ". "
                "gui_input { steps: [{ menu_item: \"…\" }] } picks an item; gui_input { steps: [{ key: \"Escape\" }] } or gui_unstick closes it. This call was not run.")
    return (f"Blocked by a dialog in the FreeCAD window: \"{d['title']}\" — {d['text'][:300]} (buttons: {', '.join(d['buttons']) or 'none'}). "
            "dialog_answer { button } presses one of its buttons: read it and press what the job needs (Cancel backs out); gui_unstick cancels it; app_force_restart if the window is stuck. This call was not run.")


# Who takes a held gui_input's answer instead of the client: live_run's
# replay (livescript.run's live.push), which then runs the step's calls
# after it, and the steps after, inside the dialog's own loop. Innermost last.
CONTINUE = []


def _job_alive(entry):
    """A heavy queue entry still running as far as this FreeCAD can tell: a
    job of this process only while it runs here (agentlink/jobs.py); any
    other entry (the supervisor's, another FreeCAD's) is taken as running."""
    from . import jobs

    if not isinstance(entry, dict) or entry.get("job") is None or entry.get("pid") not in (os.getpid(),):
        return True
    return any(j.get("job") == entry["job"] for j in jobs.running())


def _settle_own_jobs():
    """This process's ended jobs taken out of the heavy queue, and its
    "is running" notice settled (keep.settled_notice). Never raises."""
    try:
        from . import keep

        def drop(q):
            before = list(q.get("running") or [])
            q["running"] = [r for r in before if _job_alive(r)]
            if q["running"] == before:
                return False
            keep.settled_notice(q)
            return None

        keep.update_queue(drop)
    except Exception:  # noqa: BLE001
        pass


def _modified(d):
    """A document changed since it was opened or saved (the window's own
    flag), for the heartbeat: a recovered copy nobody changed is not
    recovered again after the next restart."""
    try:
        import FreeCADGui

        g = FreeCADGui.getDocument(d.Name)
        if g is not None and hasattr(g, "Modified"):
            return bool(g.Modified)
    except Exception:
        pass
    try:
        return bool(d.isTouched()) or bool(getattr(d, "UndoCount", 0))
    except Exception:
        return False


def answer_now(tool, body):
    """The answer to the call in hand, sent before it returns (gui_input,
    whose step opened a dialog that holds it): True when it went out. Only
    for that tool called on its own (not in a batch) through the link — or
    taken by a live_run replay in hand (CONTINUE), which goes on inside the
    dialog's loop."""
    if CONTINUE:
        try:
            return bool(CONTINUE[-1](tool, body))
        except Exception:
            return False
    import agentlink_state

    link = getattr(agentlink_state, "link", None)
    return bool(link is not None and link.answer_now(tool, body))


def front_open():
    """A dialog or menu is open in front (not a progress dialog): a batch's
    calls after a gui_input that opened it run inside its loop only while
    this holds (tools.py batch, cont)."""
    try:
        d = modal_info() or popup_info()
    except Exception:  # noqa: BLE001
        return False
    return d is not None and d.get("kind") != "progress" and d.get("class") != "TaskPanel"


def nested_work(on):
    """A batch runs its calls inside the loop of a menu or dialog that its
    gui_input opened (on), or no longer (off). Said in the heartbeat
    (working), so the supervisor's watchdog does not close that menu or
    dialog as one that holds the call."""
    import agentlink_state

    link = getattr(agentlink_state, "link", None)
    if link is not None:
        link.nested_since = time.time() if on else None


def loop_level():
    """How many event loops the GUI thread is inside (1: the main loop
    alone; more: a dialog's or menu's own, nested), or None when not known."""
    try:
        from PySide import QtCore

        return int(QtCore.QThread.currentThread().loopLevel())
    except Exception:
        return None


def wake():
    """The GUI thread's event loop interrupted and woken: a nested loop
    whose dialog closed while calls ran inside it sees that it is done and
    ends. A dialog's exec() ends only when its loop's processEvents returns,
    and on macOS that one keeps waiting in the modal session when a deeper
    processEvents (a gui_input step's pump) took the interrupt that the
    dialog's close sent (live 70: the window stayed busy for 20-50 s after
    gui_input pressed OK). Safe from any thread (Qt's interrupt and wakeUp
    are), and harmless to a loop that goes on: it only runs its check again."""
    try:
        from PySide import QtCore

        app = QtCore.QCoreApplication.instance()
        th = app.thread() if app is not None else None
        d = QtCore.QAbstractEventDispatcher.instance(th) if th is not None else QtCore.QAbstractEventDispatcher.instance()
        if d is not None:
            d.interrupt()
            d.wakeUp()
    except Exception:
        pass


def _closed_since(d):
    """True when the dialog or menu d (modal_info, popup_info) is no longer
    the one in front."""
    try:
        now = modal_info() or popup_info()
    except Exception:  # noqa: BLE001
        return False
    if now is None:
        return True
    w = d.get("widget")
    return w is not None and now.get("widget") is not w


def until(t):
    """The call in hand says it is done by t (time.time(); None: no longer
    said), for the heartbeat: past it, still inside a nested event loop,
    the supervisor's watchdog takes the window as hung (live_run)."""
    import agentlink_state

    link = getattr(agentlink_state, "link", None)
    if link is not None:
        link.until = t


def held_stuck(why):
    """The call in hand was answered by its own guard while a nested event
    loop still holds the window (live_run): said in the heartbeat, so the
    supervisor's watchdog starts FreeCAD again; calls meanwhile are answered
    busy rather than waiting."""
    import agentlink_state

    link = getattr(agentlink_state, "link", None)
    if link is not None:
        link.stuck = {"t": time.time(), "why": str(why)[:300]}


def answer_call(call, tool, body, bn=None):
    """Answer call (an entry of Link.calls: the client's call in hand when
    tool started) now with tool's answer body: as tool's own when the call
    is tool, else as its batch's (bn: the batch's batch_now when tool
    started), with what ran before it. True when it went out."""
    import agentlink_state

    link = getattr(agentlink_state, "link", None)
    if link is None or not isinstance(call, dict) or call.get("answered") or call.get("finished"):
        return False
    if call.get("name") != tool:
        if call.get("name") != "batch" or not isinstance(bn, dict) or bn.get("answered"):
            return False
        i, n = bn.get("i", 0), bn.get("n", 0)
        body = {"results": list(bn.get("results") or []) + [{"tool": tool, "ok": True, "result": body}], "ran": i + 1,
                **({"not_run": n - i - 1, "note": f"Answered by {tool}'s guard while a nested event loop held the window: the {n - i - 1} call(s) after it were not run."} if n - i - 1 > 0 else {})}
        bn["answered"] = True
    reply = {"jsonrpc": "2.0", "id": call.get("id"), "result": {"content": [{"type": "text", "text": compact(body)}]}}
    with link._writes():
        if call.get("answered"):
            return False
        try:
            call["f"].write(compact(reply) + "\n")
            call["f"].flush()
        except (OSError, ValueError, KeyError, AttributeError):
            return False
        call["answered"] = True
    return True


def _live_now():
    """A live_run replay is in hand: its own calls are not the client's
    (no client deadline, no early batch answer from them)."""
    import agentlink_state

    link = getattr(agentlink_state, "link", None)
    return bool(getattr(getattr(link, "session", None), "live_now", None)) or bool(CONTINUE)


def mark_agent_opened(d):
    """Note on the dialog itself that it came up during an agent's call (the
    call is still in hand): Cancel on it is then the agent's to press."""
    try:
        d["widget"].setProperty("agentlink_opened", True)
    except Exception:
        pass


def agent_opened(d):
    try:
        return bool(d["widget"].property("agentlink_opened"))
    except Exception:
        return False


BACK_OUT = ("cancel", "close", "escape", "esc", "dismiss")


def fill(d, text=None, item=None):
    """Type into a dialog before a button is pressed: a QInputDialog's value
    (text, or item for its list), else the one visible line or text field
    of a message box or dialog. Answers what was set; raises ValueError when
    there is no single field to take it."""
    w = d["widget"]
    done = {}
    if _persons(d):
        raise ValueError("this is the person's OK dialog: only the person reads and presses it")
    if is_file_picker(d):
        raise ValueError("text and item do not fill a file dialog: the path there is not checked. These tools "
                         "take a path: doc_open { path }, doc_save { path }, import_file { path }, export { path }.")
    if hasattr(w, "setTextValue") and hasattr(w, "textValue"):
        if item is not None:
            items = list(w.comboBoxItems()) if hasattr(w, "comboBoxItems") else []
            if items and item not in items:
                hit = [x for x in items if x.lower() == item.lower()]
                if not hit:
                    raise ValueError(f"item: one of {', '.join(items[:20])}.")
                item = hit[0]
            w.setTextValue(item)
            done["item"] = item
        if text is not None:
            w.setTextValue(text)
            done["text"] = text
        return done
    if item is not None:
        raise ValueError("item: this dialog has no list to pick from (a QInputDialog's); text fills its one field.")
    if text is None:
        return done
    QtGui, QtWidgets = _qt()
    fields = [f for cls in (QtWidgets.QLineEdit, QtWidgets.QPlainTextEdit) for f in w.findChildren(cls)
              if shown_in(w, f) and f.isEnabled() and not (hasattr(f, "isReadOnly") and f.isReadOnly())]
    if len(fields) != 1:
        title = ""
        try:
            title = w.windowTitle()
        except Exception:
            pass
        how = (f" gui_input {{ steps: [{{ click: {{ widget: {{ class: \"QLineEdit\", under: \"{title}\" }} }} }}, {{ type: \"…\" }}] }} (add at, or an objectName, for the second field),"
               " alone or in a batch of gui_input and dialog_answer only: it runs while the dialog is up.") if fields else ""
        raise ValueError(f"text: the dialog has {len(fields) or 'no'} text fields — text fills a dialog with one; gui_input types into one of several.{how}")
    f = fields[0]
    if hasattr(f, "setPlainText") and not hasattr(f, "setText"):
        f.setPlainText(text)
    else:
        f.setText(text)
    done["text"] = text
    return done


def _persons(d):
    """True for the person's OK dialog (agentlink/person_ok.py): no tool
    presses it or types in it."""
    try:
        from . import person_ok

        return person_ok.is_person_ok_widget((d or {}).get("widget"))
    except Exception:  # noqa: BLE001
        return False


def press(d, label):
    """Press a dialog's button by its text (never by where it is). Cancel,
    Close or Escape on a dialog with no such button (a file picker, which on
    macOS is the system's own panel with no Qt buttons) rejects it."""
    if _persons(d):
        return False
    try:
        QtGui, QtWidgets = _qt()
        want = label.lower().replace("&", "")
        dw = d["widget"]
        hits = [b for b in dw.findChildren(QtWidgets.QAbstractButton)
                if shown_in(dw, b) and b.isEnabled() and b.text().lower().replace("&", "") == want]
        # The dialog's own button before one of an editor open over it (live 85).
        hits.sort(key=lambda b: 0 if not hasattr(b, "window") or b.window() is dw else 1)
        if hits:
            hits[0].click()
            return True
        if want in BACK_OUT:
            w = d["widget"]
            if hasattr(w, "reject"):
                w.reject()
            else:
                w.close()
            return True
    except Exception:
        pass
    return False


# A dialog pressed by its set answer and still in front this long is pressed
# again (gui_link _press_and_verify), at most PRESS_TRIES times in all.
PRESS_RETRY = 4.0
PRESS_TRIES = 4


def press_hard(d, label, tries):
    """press, harder at each try: the button or reject (tries 0 and 1),
    then QDialog.done(Rejected), then hide and close."""
    if tries < 2:
        return press(d, label)
    w = d.get("widget")
    if w is None or _persons(d):
        return False
    try:
        if tries == 2 and hasattr(w, "done"):
            w.done(0)
        else:
            w.hide()
            w.close()
        return True
    except Exception:
        return False


EXPRESSION_CLASS = "Gui::Dialog::DlgExpressionInput"


def _in_expression(w, stop=None):
    """True when w sits in FreeCAD's Expression Editor (or is it)."""
    n = 0
    while w is not None and w is not stop and n < 40:
        n += 1
        try:
            if w.metaObject().className() == EXPRESSION_CLASS:
                return True
            w = w.parentWidget()
        except Exception:
            return False
    return False


def _expression_editor(view):
    """FreeCAD's Expression Editor open over the task panel, or None. "=" in
    a quantity field opens it; its own OK binds the expression (live 98, 102)."""
    try:
        QtGui, QtWidgets = _qt()
        import FreeCADGui

        for w in FreeCADGui.getMainWindow().findChildren(QtWidgets.QWidget):
            if w.metaObject().className() == EXPRESSION_CLASS and w.isVisible():
                return w
        if view is not None:
            for w in QtWidgets.QApplication.topLevelWidgets():
                if w.metaObject().className() == EXPRESSION_CLASS and w.isVisible():
                    return w
    except Exception:
        pass
    return None


def task_info():
    """The task panel open in the window (Combo View's Tasks), if any:
    { title, buttons, widget } — FreeCAD's task dialogs are not modal, so
    modal_info does not see them. When the Expression Editor is open over
    it, its buttons are apart: expression { buttons } (live 102: two OK
    buttons, and OK pressed the first)."""
    try:
        import FreeCADGui

        if not FreeCADGui.Control.activeDialog():
            return None
        QtGui, QtWidgets = _qt()
        mw = FreeCADGui.getMainWindow()
        view = None
        for w in mw.findChildren(QtWidgets.QWidget):
            if w.metaObject().className() == "Gui::TaskView::TaskView" and w.isVisible():
                view = w
                break
        buttons, titles = [], []
        if view is not None:
            for b in view.findChildren(QtWidgets.QAbstractButton):
                if b.isVisible() and b.isEnabled() and b.text() and not b.isCheckable() and not _in_expression(b, view):
                    buttons.append(b.text().replace("&", ""))
            for g in view.findChildren(QtWidgets.QWidget):
                t = g.windowTitle() if hasattr(g, "windowTitle") else ""
                if t and g.isVisible() and t not in titles and not _in_expression(g, view):
                    titles.append(t)
        out = {"class": "TaskPanel", "title": titles[0] if titles else "Task", "text": ", ".join(titles[:6]), "buttons": buttons or ["OK", "Cancel"], "widget": view}
        ed = _expression_editor(view)
        if ed is not None:
            eb = [b.text().replace("&", "") for b in ed.findChildren(QtWidgets.QAbstractButton) if b.isVisible() and b.isEnabled() and b.text()]
            out["expression"] = {"buttons": ["Expression " + t for t in eb],
                                 "note": "The Expression Editor is open. OK accepts its expression first, then presses the task's OK. "
                                         "\"Expression OK\" accepts the expression only; Cancel closes the editor and the task."}
            out["expressionWidget"] = ed
        return out
    except Exception:
        return None


def _press_in(w, want, skip_expression=None):
    QtGui, QtWidgets = _qt()
    for b in w.findChildren(QtWidgets.QAbstractButton):
        if not (b.isVisible() and b.isEnabled() and b.text().lower().replace("&", "") == want):
            continue
        if skip_expression is not None and _in_expression(b, skip_expression):
            continue
        b.click()
        return True
    return False


def press_task(d, label):
    """A task panel's button by its text; Cancel/Close with none found
    closes the task as FreeCAD's Cancel does. With the Expression Editor
    open: "Expression <button>" presses the editor's own button; OK (or
    Apply) accepts the expression first, then presses the task's button."""
    want = label.lower().replace("&", "").strip()
    try:
        ed = d.get("expressionWidget")
        if ed is not None:
            try:
                ed.metaObject()
            except Exception:
                ed = None
        if want.startswith("expression "):
            return ed is not None and _press_in(ed, want[len("expression "):])
        if ed is not None and want in ("ok", "apply"):
            _press_in(ed, "ok")
            try:
                QtGui, QtWidgets = _qt()
                QtWidgets.QApplication.processEvents()
            except Exception:
                pass
        if d.get("widget") is not None and _press_in(d["widget"], want, skip_expression=d["widget"]):
            return True
        if want in BACK_OUT:
            import FreeCADGui

            FreeCADGui.Control.closeDialog()
            return True
    except Exception:
        pass
    return False


def _bundle():
    exe = sys.executable
    return exe.split(".app/")[0] + ".app" if ".app/" in exe else exe


def looks_like_call(line):
    """A JSON-RPC 2.0 message: an object with jsonrpc "2.0" and a method."""
    if len(line) > 8_000_000 or not line.lstrip().startswith("{"):
        return False
    try:
        m = json.loads(line)
    except ValueError:
        return False
    return isinstance(m, dict) and m.get("jsonrpc") == "2.0" and isinstance(m.get("method"), str)


class Link:
    def __init__(self, port=PORT):
        self.port = port
        self.inbox = queue.Queue()
        # One reply written at a time: socket-thread tools answer beside the
        # GUI thread's replies on the same connection.
        self._write_lock = threading.Lock()
        self.sock = None
        self.timer = None
        self.session = None
        self.server = None
        self.going = False
        self.token = None  # made by start() (agentlink/link_token.py)
        self._pending, self._pending_lock = [], threading.Lock()
        # The calls in hand, innermost last: { id, name, f, answered }.
        self.calls = []
        # What the GUI thread last saw in front (gui_input, the heartbeat).
        self.front = None
        self._poster = None

    def _ready(self):
        """The session, made at the first call (so a link turned on as the
        window opens leaves the start page alone) on the document in front
        then, and kept on it: the person bringing another to the front does
        not move the agent (doc_switch does)."""
        active = FreeCAD.ActiveDocument
        if self.session is None:
            out = os.path.expanduser("~/AgentLink")
            os.makedirs(out, exist_ok=True)
            self.session = Session(doc=active or _new_start_doc(), out_dir=out)
            # session_state says which FreeCAD answered: this window, not the hidden one.
            self.session.where = "window"
            from .server import VERSION

            self.server = build_server(self.session, version=VERSION)
            # Each call shown in the window as it runs (agentlink/echo.py).
            from . import echo

            echo.wrap(self.server, self.session)
        elif getattr(self.session, "keep_doc", False):
            # An extension holds the session on a document of its own
            # (agentlink/ext.py): kept whatever the person brings to the front.
            if self.session.doc.Name not in FreeCAD.listDocuments():
                self.session.keep_doc = False
                self.session.doc = active or _new_start_doc()
        else:
            # Pinned (unattended use, K): the session keeps its document
            # whatever the person brings to the front. Switching is the
            # agent's own call: doc_new, doc_open, doc_switch. A pinned
            # document that was closed is said at the next call.
            s = self.session
            try:
                alive = s.doc is not None and s.doc.Name in FreeCAD.listDocuments()
            except Exception:
                alive = False
            if not alive:
                gone = getattr(s, "pinned_label", None) or "The agent's document"
                s.closed_doc = gone
                s.doc = active or _new_start_doc()
                from .store import undo_on

                undo_on(s.doc)
                # Its steps, calls and undo count are the new document's own
                # (the session's doc property: agentlink/docstates.py).
        try:
            self.session.pinned_label = self.session.doc.Label
        except Exception:
            pass

    def start(self):
        from PySide import QtCore

        from . import link_token

        self.token = link_token.ensure()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", self.port))
        self.sock.listen(2)
        threading.Thread(target=self._accept, daemon=True).start()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._drain)
        self.timer.start(30)
        # Each call read also pokes the GUI thread through a queued call: it
        # is taken inside a menu's or dialog's nested loop even where no
        # timer of ours fires there.
        try:
            self._poster = make_poster()
        except Exception:
            self._poster = None
        # Qt never fires a timer again while its own handler is still on the
        # stack: a call that opened a modal dialog sits inside _drain until
        # the dialog closes, so _drain cannot take the dialog_answer that
        # would close it (FreeCAD's Preferences, opened by a command, held
        # the window this way). A second timer takes calls while that is so.
        self._draining = False
        self.nested = QtCore.QTimer()
        self.nested.timeout.connect(self._drain_nested)
        self.nested.start(60)
        # The heartbeat: written from the GUI's own thread every 2 s, so a
        # stuck event loop shows as a stale file to the supervisor's
        # watchdog; it also reads (and, where the rule says, answers) a modal
        # dialog in front.
        self.busy = None
        self.in_call = False
        self._dialog = None
        self.beat = QtCore.QTimer()
        self.beat.timeout.connect(self._beat)
        self.beat.start(2000)
        self._beat()
        FreeCAD.Console.PrintMessage(f"Agent Link: listening on 127.0.0.1:{self.port}\n")

    def _beat(self):
        try:
            from . import keep, restart_mark

            d = modal_info()
            if d is not None:
                key = (d["class"], d["title"], d["text"])
                if self._dialog is None or self._dialog[0] != key:
                    self._dialog = (key, time.time())
                d["since"] = self._dialog[1]
                s = self.session
                restarting = restart_mark.read() is not None
                # Agent Link started this FreeCAD: the supervisor's relaunch or
                # app_restart (launch mark), or a restart still reopening.
                act = keep.dialog_answer_for(d, ours=keep.launched_by_us() or restarting, restarting=restarting,
                                             save_rule=getattr(s, "restart_save", "agent") if s else "agent", agent_docs=sorted(getattr(s, "agent_docs", ()) or ()) if s else [])
                if act[0] == "press":
                    self._press_and_verify(d, key, act[1])
            else:
                self._dialog = None
                pr = getattr(self, "_press", None)
                if pr is not None:
                    # Verified: the dialog it pressed is gone.
                    self._press = None
                    keep.log_watchdog({"event": "dialog", "title": pr[0][1], "gone": True, "tries": pr[2]})
            _meter_dialog(self, d)
            self._wake_ended_loop(d)
            # A menu or drop-down list in front (a popup, which no modal
            # check sees): in the heartbeat too, with how long it has been
            # open, so the supervisor can tell a call held by it.
            pop = None
            try:
                from . import gui_input as gi

                QtGui, QtWidgets = _qt()
                app = QtWidgets.QApplication.instance()
                self.front = gi.describe_front(app, modal_info)
                w = app.activePopupWidget() if app is not None else None
                if w is not None:
                    pop = {"class": w.metaObject().className(), **gi.describe_popup(w)}
            except Exception:
                pass
            pkey = (pop["class"], pop.get("title"), tuple(pop.get("items") or ())) if pop else None
            if pkey is None:
                self._popup = None
            elif getattr(self, "_popup", None) is None or self._popup[0] != pkey:
                self._popup = (pkey, time.time())
            if pop:
                pop["since"] = self._popup[1]
            if d is not None or pop is not None:
                # The last beat that saw a dialog or menu in front: the
                # supervisor times a nested loop from there, not from the
                # call's start (live 87: a forced restart after OK).
                self._front_at = time.time()
            # A heavy job held for the person's go (N): said in the status bar
            # while a heavy job runs (keep.status_line); with none running the
            # line is not said again and goes after its 3 s (round 7: it
            # stayed for the rest of the run).
            q = keep._load(keep.path("queue.json"), {}) or {}
            line = keep.status_line(q)
            if line and keep.status_line(q, alive=_job_alive) is None:
                # Its own job ended but the queue still names it (round 8,
                # 00-042: fea_buckle's lock stayed): not said, taken out, the
                # notice settled.
                line = None
                _settle_own_jobs()
            if line:
                try:
                    import FreeCADGui

                    FreeCADGui.getMainWindow().statusBar().showMessage(line, 3000)
                except Exception:
                    pass
            # A batch runs its calls inside this menu's or dialog's loop
            # (nested_work): the watchdog must not close it as one that holds
            # the call.
            work = {"working": self.nested_since} if self.busy and getattr(self, "nested_since", None) else {}
            docs = [{"name": x.Name, "label": x.Label, "file": x.FileName or "", **({"modified": True} if _modified(x) else {})} for x in FreeCAD.listDocuments().values()]
            keep._save(keep.path("heartbeat.json"), {
                "pid": os.getpid(), "t": time.time(), "pairing": 1, "app": _bundle(), "freecad": ".".join(FreeCAD.Version()[:3]), "port": self.port,
                "docs": docs, "busy": self.busy, **self._busy_beat(), "pinned": getattr(self.session, "doc", None).Name if self.session and getattr(self.session, "doc", None) else None,
                "dialog": {**{k: v for k, v in d.items() if k != "widget"}, **work} if d else None,
                "popup": {**pop, **work} if pop else None,
            })
        except Exception:
            pass

    def _wake_ended_loop(self, d):
        """From the heartbeat: a call answered early (its step's dialog held
        it) is still in hand, nothing is in front any more, and the GUI
        thread is still inside a nested event loop: that loop's dialog
        closed, and the loop missed the word (wake). It is woken, so the
        call in hand returns and the calls that wait are served."""
        try:
            if d is not None or not any(c.get("answered") for c in list(getattr(self, "calls", []) or [])):
                return
            if popup_info() is not None:
                return
            n = loop_level()
            if n is not None and n >= 2:
                wake()
        except Exception:  # noqa: BLE001
            pass

    def _press_and_verify(self, d, key, label):
        """Press a dialog's set answer, and verify it on the next beats: the
        same dialog still in front PRESS_RETRY s after a press is pressed
        again, harder each time (press_hard), up to PRESS_TRIES. The
        heartbeat says "pressed" only while a press may still work; after
        the last try it says pressFailed, so the supervisor answers the call
        "blocked" rather than wait on a press that did not take (live, 18
        Nov: the log said pressed: cancel and Document Recovery stayed up
        about 5 min)."""
        from . import keep

        now = time.time()
        pr = getattr(self, "_press", None)
        if pr is None or pr[0] != key:
            pr = (key, 0.0, 0)
        tries = pr[2]
        if tries < PRESS_TRIES and (tries == 0 or now - pr[1] >= PRESS_RETRY):
            ok = press_hard(d, label, tries)
            tries += 1
            pr = (key, now, tries)
            if ok:
                keep.log_watchdog({"event": "dialog", "title": d["title"], "pressed": label, **({"try": tries} if tries > 1 else {})})
                m = getattr(getattr(self, "server", None), "meter", None)
                if m is not None:
                    m.dialog_seen(d)
                    m.dialog_pressed("agentlink")
        self._press = pr
        if tries < PRESS_TRIES or now - pr[1] < PRESS_RETRY:
            d["pressed"] = label
            d["pressTries"] = tries
        else:
            d["pressFailed"] = tries
            if not getattr(self, "_press_failed_said", None) == key:
                self._press_failed_said = key
                keep.log_watchdog({"event": "dialog", "title": d["title"], "pressFailed": tries})

    def _busy_beat(self):
        """For the heartbeat, while a call is in hand: since when (busySince),
        how many event loops the GUI thread is inside as it beats (loops: 1
        the main one; more, a nested one such as a dialog's), the time the
        call said it would be done by (until) and a call's guard that gave
        up on a nested loop (stuck). The watchdog takes a call held past its
        deadline inside a nested loop, with nothing open, as a hang. frontAt:
        the last beat that saw a dialog or menu in front during the call (the
        watchdog times the nested loop from there)."""
        if not self.busy:
            return {}
        out = {"busySince": getattr(self, "busy_since", None), "loops": loop_level()}
        fa = getattr(self, "_front_at", None)
        if fa is not None and out["busySince"] is not None and fa > out["busySince"]:
            out["frontAt"] = fa
        if getattr(self, "until", None):
            out["until"] = self.until
        if getattr(self, "stuck", None):
            out["stuck"] = self.stuck
        return out

    def stop(self):
        if getattr(self, "beat", None):
            self.beat.stop()
        if self.timer:
            self.timer.stop()
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        FreeCAD.Console.PrintMessage("Agent Link: stopped\n")

    def _accept(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._read, args=(conn,), daemon=True).start()

    def _read(self, conn):
        """Lines of JSON-RPC, one object each. Anything else ends the
        connection at once: a web page can reach 127.0.0.1 too, and a
        browser's request starts with an HTTP line ("POST / HTTP/1.1") and
        headers, so its body — a tool call — was run once the lines that
        were not JSON had been skipped. Only a client speaking the protocol
        from its first line is served, and only after that line presented
        the pairing token (agentlink/link_token.py): any other program on
        the computer could reach the port as well."""
        from . import link_token

        f = conn.makefile("rw", encoding="utf-8", errors=WIRE_ERRORS, newline="\n")
        # Pairing has 5 s in all and short lines only; at most four
        # connections wait unpaired, and a fifth pushes out the one that has
        # waited longest, so nothing holding connections open can lock the
        # person's agent out.
        with self._pending_lock:
            if len(self._pending) >= 4:
                old = self._pending.pop(0)
                try:
                    old.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            self._pending.append(conn)
        waiting, paired, w = True, False, None
        deadline = time.time() + 5
        try:
            while not paired:
                left = deadline - time.time()
                if left <= 0:
                    raise OSError("pairing took too long")
                conn.settimeout(left)
                line = f.readline(1024)
                if not line or not line.endswith("\n") or not line.strip():
                    self._refused()
                    raise OSError("not a pairing line")
                if w is None:
                    reply, w = link_token.window_greet(line, self.token)
                    if reply is None:
                        self._refused()
                        raise OSError("bad hello")
                    f.write(reply)
                    f.flush()
                    continue
                if not link_token.window_check(line, self.token, w):
                    self._refused()
                    raise OSError("bad proof")
                paired = True
            with self._pending_lock:
                if conn in self._pending:
                    self._pending.remove(conn)
            waiting = False
            conn.settimeout(None)
            for line in f:
                if not line.strip():
                    continue
                if not looks_like_call(line):
                    break
                if self._thread_call(line, f):
                    continue  # answered on a thread of its own
                line = _Line(line)
                line.ticket = {"state": "queued", "t": _clock()}
                self.inbox.put((line, f, conn))
                self._poke()
                self._arm_busy(line, f)
                continue
            else:
                return
        except (OSError, UnicodeDecodeError):
            pass
        finally:
            if waiting:
                with self._pending_lock:
                    if conn in self._pending:
                        self._pending.remove(conn)
        try:
            conn.shutdown(socket.SHUT_RDWR)
            conn.close()
        except OSError:
            pass

    def _writes(self):
        """The lock replies are written under (made on first use: a Link
        made without __init__, as the tests do, has none yet)."""
        lock = getattr(self, "_write_lock", None)
        if lock is None:
            lock = self._write_lock = threading.Lock()
        return lock

    # ---- the GUI thread poked, and calls answered "busy" when it cannot take them ----

    def _poke(self):
        p = getattr(self, "_poster", None)
        if p is not None:
            try:
                p.post(self._poked)
            except Exception:
                pass

    def _poked(self):
        """On the GUI thread, from a queued call: the inbox drained as the
        timers would (nested while a call is in hand inside a loop)."""
        if self.inbox.empty():
            return
        self._drain()

    def _claims(self):
        lock = getattr(self, "_claim_lock", None)
        if lock is None:
            lock = self._claim_lock = threading.Lock()
        return lock

    def _claim(self, line, state="taken"):
        """True when this thread may answer line (moving its ticket on from
        queued); a line with no ticket is always ours."""
        t = getattr(line, "ticket", None)
        if t is None:
            return True
        with self._claims():
            if t["state"] != "queued":
                return False
            t["state"] = state
            return True

    def _stuck(self):
        """Why the GUI thread cannot take calls now, in words, or None when
        it is only busy with a long call (that one is waited for)."""
        from . import gui_input as gi

        calls = list(getattr(self, "calls", []) or [])
        front = getattr(self, "front", None)
        if isinstance(front, dict) and front.get("kind") == "progress":
            # A progress dialog (a job's own, closing by itself) holds
            # nothing: waited for, never answered busy for.
            front = None
        answered = any(c.get("answered") for c in calls)
        if not front and answered and not getattr(self, "stuck", None):
            # The call in hand was answered early and what held it is closed:
            # its own loop is ending (woken here, from this thread too) and
            # the rest of the call returns. Calls wait for it, as for any
            # call in hand, for ENDING_WAIT s (live 70: they were answered
            # "a menu or dialog is open" with nothing open).
            now = time.time()
            t = getattr(self, "_ending_since", None)
            if t is None:
                t = self._ending_since = now
            wake()
            if now - t < ENDING_WAIT:
                return None
            return ("no menu or dialog is open, but the call answered early is still inside a nested event loop that did not end ("
                    + f"{now - t:.0f} s)")
        self._ending_since = None
        if front or answered:
            return gi.front_words(front)
        if getattr(self, "stuck", None):
            return "a nested event loop that did not end (" + str(self.stuck.get("why") or "")[:160] + ")"
        now = time.time()
        # c.get once: expect_done (another thread) can pop the deadline
        # between a test and a read.
        if any((c.get("deadline") or now + 1) < now and not c.get("finished") for c in calls):
            return gi.front_words(front)
        return None

    @staticmethod
    def busy_reply(mid, why, ran=False, outcome=None, retried=0):
        """The busy answer. outcome: not_started (it was not run), unknown
        (a changing call in hand: some of it may have run). retried: the
        link sent it again once first (_meta.retried)."""
        msg = (f"FreeCAD's window has a menu or dialog open: {why}. Its own event loop holds the window, so "
               + ("this call's steps after the one that opened it may not have run" if ran else "this call was not run")
               + ". gui_unstick closes it (or gui_input { steps: [{ key: \"Escape\" }] }); app_force_restart if that does not help.")
        if ran and mid is not None:
            msg += f" When the call ends, job_status {{ job: {json.dumps(str(mid))} }} gives its late answer."
        err = set_kind({"code": "busy", "message": msg})
        if outcome:
            err["status"] = outcome
        if retried:
            err["retried"] = int(retried)  # in the answer itself, so every model sees it (owner, 22 Nov)
        result = {"content": [{"type": "text", "text": compact({"error": err})}], "isError": True}
        if retried:
            result["_meta"] = {"retried": int(retried)}
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def _line_changes(self, line):
        """True when the call on line may change something (its tool's own
        changes_for with its arguments); True when that cannot be told."""
        try:
            msg = json.loads(line)
            params = msg.get("params") or {}
            srv = getattr(self, "server", None)
            tool = getattr(srv, "tools", {}).get(params.get("name")) if srv is not None else None
            if tool is None:
                return True
            return bool(tool.changes_for(params.get("arguments") or {}))
        except Exception:  # noqa: BLE001
            return True

    def _keep_late(self, call, reply, how):
        """A call's own answer that came after it was already answered (busy,
        or early by its dialog), or whose connection was gone: kept in the
        link's ring of late answers (jobs.keep_late), which job_status reads."""
        try:
            from . import jobs

            jobs.keep_late(self, call.get("id"), call.get("name"), reply, how)
        except Exception:  # noqa: BLE001 - the record only
            pass

    def _meter_refused(self, line, reply):
        """A refusal this window wrote itself, before the call ran, counted
        by usage_report as an erred call (usage.Meter.refused): the meter
        sits in the server's call, which these never reach."""
        try:
            meter = getattr(getattr(self, "server", None), "meter", None)
            name = _tool_name(line)
            if meter is None or name is None:
                return
            from .protocol import compact
            from .usage import err_code

            result = reply.get("result") or {}
            args = (json.loads(line).get("params") or {}).get("arguments") or {}
            text = "".join(c.get("text", "") for c in result.get("content") or [] if c.get("type") == "text")
            meter.refused(name, compact(args), text, err_code(result))
        except Exception:  # noqa: BLE001 - the count only
            pass

    def _meter_amend(self, name):
        """A call answered busy while it ran: counted as erred, as the agent saw it."""
        try:
            meter = getattr(getattr(self, "server", None), "meter", None)
            if meter is not None and name:
                meter.amend(name, "busy")
        except Exception:  # noqa: BLE001
            pass

    def _write(self, f, reply):
        with self._writes():
            try:
                f.write(compact(reply) + "\n")
                f.flush()
                return True
            except (OSError, ValueError):
                return False

    def _arm_busy(self, line, f, after=None, tick=0.25):
        """A thread that answers line busy if, BUSY_AFTER s on, the GUI
        thread has not taken it and is held by a menu or dialog."""
        try:
            mid = json.loads(line).get("id")
        except (ValueError, AttributeError):
            return None
        if mid is None:
            return None
        after = BUSY_AFTER if after is None else after
        answers = _dialog_call(line)

        def watch():
            # The busy time is counted from when the hold began, not from
            # when the call was queued (E3): a call queued behind a long
            # call, then held by a dialog, still gets its full time.
            t0 = (line.ticket or {}).get("t") or _clock()
            held = None
            retry_at = None
            while True:
                time.sleep(tick)
                if line.ticket["state"] != "queued" or getattr(self, "going", False):
                    return
                now = _clock()
                why = self._stuck()
                if why is None:
                    held = None
                    retry_at = None
                    continue
                if held is None:
                    held = now
                start = max(t0, held)
                if now - start < after:
                    continue
                front = getattr(self, "front", None)
                if answers and isinstance(front, dict) and front.get("kind") == "dialog" and now - start < max(after, FRONT_WAIT):
                    # Only a dialog is up, and this call answers it: the
                    # dialog's own loop takes it (live 70).
                    continue
                if retry_at is None and not getattr(line, "retried", 0) and retry_once_ok(self._line_changes(line), {"code": "busy", "status": "not_started"}):
                    # Not started: tried once more after a short wait (E10).
                    line.retried = 1
                    retry_at = now + RETRY_DELAY
                    continue
                if retry_at is not None and now < retry_at:
                    continue
                if self._claim(line, "busy"):
                    reply = self.busy_reply(mid, why, outcome="not_started", retried=getattr(line, "retried", 0))
                    self._write(f, reply)
                    self._meter_refused(line, reply)
                    return

        th = threading.Thread(target=watch, name="agentlink-busy", daemon=True)
        th.start()
        return th

    def expect(self, tool, seconds, tick=0.25):
        """The call in hand (tool) has seconds: past them, not answered yet,
        it is answered busy from a thread of its own (its steps' menu or
        dialog holds the window and nothing in it answered)."""
        call = self.calls[-1] if self.calls else None
        if call is None or call["name"] not in (tool, "batch"):
            return None
        call["deadline"] = time.time() + seconds
        call["expected"] = tool

        def watch():
            while not call.get("finished"):
                time.sleep(tick)
                if call.get("finished") or call.get("answered"):
                    return
                # expect_done (the GUI thread) pops the deadline when the
                # call returned on its own: lifted, so this watch ends. A
                # plain call["deadline"] raised KeyError here (Report view,
                # thread agentlink-busy-call) when the pop came between ticks.
                deadline = call.get("deadline")
                if deadline is None:
                    return
                if time.time() > deadline:
                    from . import gui_input as gi

                    with self._writes():
                        if call.get("answered") or call.get("finished") or call.get("deadline") is None:
                            return
                        reply = self.busy_reply(call["id"], gi.front_words(getattr(self, "front", None)), ran=True,
                                                outcome="unknown" if call.get("changes", True) else None)
                        try:
                            call["f"].write(compact(reply) + "\n")
                            call["f"].flush()
                        except (OSError, ValueError):
                            pass
                        call["answered"] = True
                        call["answeredAs"] = "busy"
                    return

        th = threading.Thread(target=watch, name="agentlink-busy-call", daemon=True)
        th.start()
        return th

    def _thread_call(self, line, f):
        """A socket-thread tool (hooks.THREAD_TOOLS, such as a long poll):
        answered on a thread of its own, never through the GUI thread's
        inbox and never holding in_call. False for any other line, or before
        the server is made (it goes to the inbox then)."""
        from . import hooks

        name = _tool_name(line)
        srv = getattr(self, "server", None)
        if name is None or srv is None or not hasattr(srv, "handle_light"):
            return False
        calls = _thread_batch(line, hooks.THREAD_TOOLS) if name == "batch" else None
        if name not in hooks.THREAD_TOOLS and calls is None:
            return False

        def run():
            try:
                msg = json.loads(line)
                reply = srv.handle_light(msg) if calls is None else self._light_batch(srv, msg, calls)
            except ValueError:
                reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "not JSON"}}
            if reply is None:
                return
            with self._writes():
                try:
                    f.write(compact(reply) + "\n")
                    f.flush()
                except (OSError, ValueError):
                    pass

        threading.Thread(target=run, name=f"agentlink-{name}", daemon=True).start()
        return True

    @staticmethod
    def _light_batch(srv, msg, calls):
        """A batch of socket-thread tools, answered here as batch answers:
        { results: [{ tool, ok, result | error }], ran }, stopping at the
        first refusal."""
        results = []
        for i, c in enumerate(calls):
            r = srv.handle_light({"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": c["tool"], "arguments": {k: v for k, v in c.items() if k != "tool"}}})
            res = (r or {}).get("result") or {}
            try:
                body = json.loads(res["content"][0]["text"])
            except (KeyError, IndexError, TypeError, ValueError):
                body = {}
            ok = not res.get("isError")
            results.append({"tool": c["tool"], "ok": ok, **({"result": body} if ok else {"error": body.get("error")})})
            if not ok:
                return {"jsonrpc": "2.0", "id": msg.get("id"), "result": {"content": [{"type": "text", "text": compact({"results": results, "stopped": i})}]}}
        return {"jsonrpc": "2.0", "id": msg.get("id"), "result": {"content": [{"type": "text", "text": compact({"results": results, "ran": len(results)})}]}}

    @staticmethod
    def _refused():
        try:
            FreeCAD.Console.PrintWarning("Agent Link: a connection that could not pair was refused (it did not prove it knows the link's token)\n")
        except Exception:
            pass

    def _back(self):
        """After app_restart: False while the documents it is reopening are
        not all open yet (the calls wait in the inbox); then the one that was
        in front is put in front again and the mark taken away."""
        from . import restart_mark

        m = restart_mark.read()
        if m is None:
            return True
        if restart_mark.going(m):
            self.going = True
            # This window is quitting to start again (app_restart): no more
            # calls here. Each connection dropped, so the caller waits for
            # the new window instead of this one answering from no document.
            if self.sock:
                try:
                    self.sock.close()
                except OSError:
                    pass
                self.sock = None
            while True:
                try:
                    _line, _f, conn = self.inbox.get_nowait()
                except queue.Empty:
                    break
                try:
                    import socket as _s

                    conn.shutdown(_s.SHUT_RDWR)
                    conn.close()
                except OSError:
                    pass
            return False
        open_ = {os.path.abspath(d.FileName) for d in FreeCAD.listDocuments().values() if d.FileName}
        if any(os.path.abspath(p) not in open_ for p in m.get("reopens") or [] if os.path.isfile(p)):
            return False
        want = m.get("active")
        d = next((d for d in FreeCAD.listDocuments().values() if want and d.FileName and os.path.abspath(d.FileName) == os.path.abspath(want)), None)
        if d is not None:
            try:
                FreeCAD.setActiveDocument(d.Name)
                if FreeCAD.GuiUp:
                    import FreeCADGui

                    FreeCADGui.setActiveDocument(d.Name)
            except Exception:
                pass
        restart_mark.clear()
        return True

    def answer_now(self, tool, body):
        """Send the innermost call's answer now (answer_now above); its
        own reply, when it returns, is then dropped."""
        call = self.calls[-1] if self.calls else None
        if call is None or call["answered"]:
            return False
        if call["name"] != tool:
            # Inside a batch (a lean client's way to gui_input): the calls
            # after it run here, inside the loop of what it opened, and the
            # batch is answered once with all of them (fault 81b; tools.py
            # batch, cont). A batch with no such hook is answered with what
            # ran so far, and the calls after it are not run.
            cont = self._batch_cont(call, tool)
            if cont is not None:
                got = cont(tool, body)
                if got is True:
                    return True  # a deeper gui_input of the batch answered it
                if not isinstance(got, dict):
                    return False  # closed meanwhile: the batch goes on by itself
                body = got
            else:
                body = self._batch_body(call, tool, body)
            if body is None:
                return False
        reply = {"jsonrpc": "2.0", "id": call["id"], "result": {"content": [{"type": "text", "text": compact(body)}]}}
        try:
            from . import report_watch
            from .protocol import add_report

            add_report(reply, report_watch.take())
        except Exception:
            pass
        with self._writes():  # the socket thread may answer it busy meanwhile
            if call["answered"]:
                return False
            try:
                call["f"].write(compact(reply) + "\n")
                call["f"].flush()
            except OSError:
                return False
            call["answered"] = True
        return True

    def _batch_cont(self, call, tool):
        """The client's batch in hand runs its later calls inside the loop
        of what tool opened: its hook (session.batch_now's cont), or None."""
        s = getattr(self, "session", None)
        bn = getattr(s, "batch_now", None)
        if getattr(s, "live_now", None) or call["name"] != "batch" or not isinstance(bn, dict):
            return None
        if bn.get("answered") or bn.get("tool") != tool or not callable(bn.get("cont")):
            return None
        return bn["cont"]

    def _batch_body(self, call, tool, body):
        """A batch's early answer, from the batch in hand (session.batch_now:
        its results so far, the index and count) with tool running in it."""
        bn = getattr(getattr(self, "session", None), "batch_now", None)
        if getattr(getattr(self, "session", None), "live_now", None):
            return None  # a live_run's own batch, not the client's: its replay goes on
        if call["name"] != "batch" or not isinstance(bn, dict) or bn.get("answered") or bn.get("tool") != tool:
            return None
        i, n = bn.get("i", 0), bn.get("n", 0)
        out = {"results": list(bn.get("results") or []) + [{"tool": tool, "ok": True, "result": body}], "ran": i + 1}
        if n - i - 1 > 0:
            out["not_run"] = n - i - 1
            out["note"] = f"Answered while what {tool} opened holds the window: the {n - i - 1} call(s) after it in the batch were not run."
        bn["answered"] = True
        return out

    def _declared_read(self, tool, args):
        """A call its tool's data declares a front read (frontReads): it may
        share a batch with gui_input while a dialog or menu is open."""
        srv = getattr(self, "server", None)
        t = getattr(srv, "tools", {}).get(tool) if srv is not None else None
        return bool(t is not None and hasattr(t, "front_read") and t.front_read(args))

    def _read_ok(self, tool, args):
        """A read that may run inside a dialog's loop beside gui_input: a
        tool of this server that changes nothing with these arguments and
        is not a heavy read (that one goes to a job and waits)."""
        srv = getattr(self, "server", None)
        t = getattr(srv, "tools", {}).get(tool) if srv is not None else None
        if t is None or t.changes_for(args):
            return False
        try:
            from . import keep

            return not keep.is_heavy(tool)
        except Exception:  # noqa: BLE001
            return True

    def _blocked(self, line, f, d):
        """A call that came while a modal dialog holds the window: answered
        at once, not run inside the dialog's loop."""
        if not self._claim(line):
            return  # answered busy already
        try:
            mid = json.loads(line).get("id")
        except ValueError:
            mid = None
        msg = blocked_words(d)
        text = compact({"error": {"code": "invalid_state", "message": msg}})
        reply = {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": text}], "isError": True}}
        self._write(f, reply)
        if d and d.get("kind") != "menu" and d.get("title"):
            _meter_dialog(self, d)  # before the heartbeat sees it: the call it blocked is counted to it
        self._meter_refused(line, reply)

    def _drain_nested(self):
        """Only while _drain is on the stack (a call in hand inside a dialog's
        loop): the same handling as there, so dialog_answer runs."""
        if self._draining and not self.inbox.empty():
            self._drain(nested=True)

    def _drain(self, nested=False):
        # Entered again while on the stack (a queued poke or the timer inside
        # a call's nested loop): handled as nested, and the outer entry keeps
        # the flag until it returns.
        if nested or getattr(self, "_draining", False):
            self._handle_inbox()
            return
        self._draining = True
        try:
            self._handle_inbox()
        finally:
            self._draining = False

    def _handle_inbox(self):
        if self.inbox.empty():
            return
        d = modal_info()
        # A menu opened by a call answered early (gui_input) holds that call
        # as a dialog would: the same handling, or every call would wait.
        # So does a menu open while a call is in hand: that call is inside the
        # menu's loop (a batch's gui_input, a command's menu), and a call
        # that waited for it would wait for ever.
        if d is None and (any(c["answered"] for c in self.calls) or self.in_call):
            d = popup_info()
        if d is not None and d.get("class") != "TaskPanel":
            self.front = {"kind": d.get("kind") or "dialog", "title": d.get("title"), **({"items": d["items"]} if d.get("items") else {}), **({"buttons": d["buttons"]} if d.get("buttons") else {})}
        # While documents reopen after a restart, calls wait — except with a
        # dialog up: FreeCAD's Document Recovery comes up at start and holds
        # the reopening, so the dialog_answer that clears it must not wait
        # behind it (a deadlock seen live after an update).
        if d is None and not self._back():
            return
        if d is not None and self.in_call:
            mark_agent_opened(d)
        if d is not None or self.in_call:
            # Inside a dialog's own loop (Qt runs timers there): no tool call
            # runs nested in it but dialog_answer; the rest are answered
            # "blocked" at once. With no dialog (a call still in hand), they
            # wait their turn.
            items = []
            while True:
                try:
                    items.append(self.inbox.get_nowait())
                except queue.Empty:
                    break
            wait = []
            for it in items:
                name = _tool_name(it[0])
                if d is not None and _dialog_call(it[0], self._read_ok, self._declared_read):
                    self._run_one(*it)
                elif d is not None and name is not None:
                    self._blocked(it[0], it[1], d)
                elif d is not None and not self.in_call:
                    self._run_one(*it)
                else:
                    wait.append(it)
            for it in wait:
                self.inbox.put(it)
            if d is not None and _closed_since(d):
                # A call run inside the dialog's (or menu's) loop closed it:
                # the loop is woken so it ends now, not at some later event
                # (live 70: the window stayed busy for 20-50 s after OK).
                wake()
            return
        while True:
            try:
                line, f, conn = self.inbox.get_nowait()
            except queue.Empty:
                return
            self._run_one(line, f, conn)
            if self.going:
                continue

    def _client_of(self, conn):
        """A number for each paired connection, the same while it stays
        open: an approval is bound to the connection that asked (red team
        4, R4-11)."""
        import itertools
        import weakref

        ids = getattr(self, "_client_ids", None)
        if ids is None:
            ids = self._client_ids = weakref.WeakKeyDictionary()
            self._client_next = itertools.count(1)
        if conn is None:
            return None
        try:
            got = ids.get(conn)
            if got is None:
                got = ids[conn] = f"link-{next(self._client_next)}"
            return got
        except TypeError:  # an object with no weak reference (a test's stand-in)
            return f"link-{id(conn)}"

    def _run_one(self, line, f, conn):
        if self.going:
            # Quitting (app_restart answered just before): dropped, so the
            # caller sends it to the window that comes up next.
            try:
                import socket as _s

                conn.shutdown(_s.SHUT_RDWR)
                conn.close()
            except OSError:
                pass
            return
        if not self._claim(line):
            return  # answered busy from the socket thread while it waited
        prev = (self.busy, self.in_call, getattr(self, "busy_since", None))
        try:
            self._ready()
            name = _tool_name(line)
            gone = getattr(self.session, "closed_doc", None) if self.session else None
            if gone and not pinned_free_call(line, name):
                self.session.closed_doc = None
                try:
                    mid = json.loads(line).get("id")
                except ValueError:
                    mid = None
                text = compact({"error": {"code": "invalid_state", "message": f"{gone} was closed — doc_open it again, or doc_switch to another open document (doc_new for a fresh one). This call was not run."}})
                reply = {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": text}], "isError": True}}
                self._write(f, reply)
                self._meter_refused(line, reply)
                return
            if self.session and not catalogue_call(line, name):
                self.session.closed_doc = None
            if name in FRONT_TOOLS and self.session is not None:
                front = FreeCAD.ActiveDocument
                mine = self.session.doc
                if front is not None and mine is not None and front.Name != mine.Name:
                    try:
                        mid = json.loads(line).get("id")
                    except ValueError:
                        mid = None
                    text = compact({"error": {"code": "invalid_state", "message": f"{name} acts on the window's front document, and the person has {front.Label} in front while the agent is on {mine.Label}: doc_switch {{ document: \"{mine.Label}\", front: true }} brings the agent's back (their view moves), or ask them. This call was not run."}})
                    reply = {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": text}], "isError": True}}
                    self._write(f, reply)
                    self._meter_refused(line, reply)
                    return
            if name is not None and name != "dialog_answer":
                if not prev[0]:
                    self.busy_since = time.time()
                self.busy, self.in_call = name, True
            msg = json.loads(line)
            call = {"id": msg.get("id") if isinstance(msg, dict) else None, "name": name, "f": f, "answered": False, "changes": self._line_changes(line)}
            self.calls.append(call)
            # Progress notifications (protocol.progress) for this call go to its own connection, until it is answered.
            self.server.notify = lambda m, f=f, call=call: None if call["answered"] else self._write(f, m)
            try:
                try:
                    reply = self.server.handle(msg, client=self._client_of(conn))
                except (SystemExit, KeyboardInterrupt):
                    # Code run for the call called sys.exit (or raised
                    # KeyboardInterrupt) outside the tool's own guard: the
                    # window stays up and the call is refused.
                    text = compact({"error": {"code": "failed", "message": f"{name}: code run for this call called exit; the window and Agent Link go on.", "outcome": "unknown"}})
                    reply = {"jsonrpc": "2.0", "id": call["id"], "result": {"content": [{"type": "text", "text": text}], "isError": True}}
            finally:
                call["finished"] = True
                self.busy, self.in_call, self.busy_since = prev
                if not self.busy:
                    self.until = self.stuck = self.nested_since = None
                self.calls = [c for c in self.calls if c is not call]
            if call["answered"]:
                if not ((reply or {}).get("result") or {}).get("isError"):
                    self._meter_amend(name)  # counted as answered; the agent was told busy
                if reply is not None:
                    self._keep_late(call, reply, call.get("answeredAs") or "early")  # job_status gives it (E6)
                reply = None  # sent already, while a dialog held the call
            elif reply is not None and getattr(line, "retried", 0) and isinstance(reply.get("result"), dict):
                reply["result"].setdefault("_meta", {})["retried"] = 1
                mark_retried(reply["result"])
        except ValueError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "not JSON"}}
        if not self.going and _tool_name(line) == "app_restart":
            from . import restart_mark

            self.going = restart_mark.going(restart_mark.read())
            if self.going and self.sock:
                try:
                    self.sock.close()
                except OSError:
                    pass
                self.sock = None
        if reply is not None and FreeCAD.GuiUp and _tool_name(line) is not None:
            try:
                from . import report_watch
                from .protocol import add_report

                add_report(reply, report_watch.take())
            except Exception:
                pass
        try:
            with self._writes():  # a socket-thread tool may answer on the same connection
                if reply is not None:
                    f.write(compact(reply) + "\n")
                while self.server is not None and self.server.outbox:
                    f.write(compact(self.server.outbox.pop(0)) + "\n")
                f.flush()
        except (OSError, ValueError):
            # The connection went first (the relay or the supervisor let go
            # of it): the answer is kept for job_status (E6).
            if reply is not None and _tool_name(line) is not None:
                try:
                    mid = json.loads(line).get("id")
                except ValueError:
                    mid = None
                if mid is not None:
                    self._keep_late({"id": mid, "name": _tool_name(line)}, reply, "lost")
        if FreeCAD.GuiUp and not self.in_call:
            import FreeCADGui

            FreeCADGui.updateGui()


def mark_retried(result):
    """E10: put retried: 1 in the answer's own JSON text, so every model sees
    it (a client can hide _meta). Text that is not a JSON object stays."""
    from .protocol import compact

    for c in result.get("content") or []:
        if c.get("type") != "text":
            continue
        try:
            body = json.loads(c.get("text") or "")
        except ValueError:
            continue
        if isinstance(body, dict):
            body["retried"] = 1
            c["text"] = compact(body)
    return result
