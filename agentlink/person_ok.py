# SPDX-License-Identifier: LGPL-2.1-or-later
"""The person's OK: a press in the FreeCAD window that no agent can make.

A typed confirm ("approve cookbook <name>") is only a convention: an agent
can type the words itself. Code that runs with the Mac's full reach
(cookbooks, macros, extensions, add-ons) needs an OK that does not come
through MCP. This module gives it (red team, 2026-11-18):

  ask(kind, name, title, lines, sha=None, on_ok=None)
      A grant for (kind, name, sha) given before: it is used up, and the
      answer is {"ok": True}. Else the window shows the OK dialog and the
      answer is {"pending": True, ...}: the agent tells the person to look
      at the window. Headless (no window): Refused "unavailable". The OK is
      then not possible, and the agent says so.

  on_ok: called on the GUI thread at the person's press (for an OK that is
      kept, such as a cookbook's hash in the approvals store). Without it,
      the press gives a grant that the next call of the same tool uses
      (for one action, such as one install). A grant expires after TTL s.

A press counts only when all of these are true (press_counts):
  - The event came from the system (QEvent.spontaneous()). Events that
    Agent Link sends (gui_input, dialog_answer) are never spontaneous, and
    QAbstractButton.click() makes no event at all.
  - The dialog was in view for MIN_READ s or more (time to read it).
  - The test flag AGENTLINK_AS_USER is off.
gui_input and dialog_answer also refuse every widget in the dialog
(OBJECT_NAME), so the agent gets a clear refusal, not a silent no-op.

What is not covered: a program with control of the whole Mac (a screen
control tool, a script that the person runs) makes system events. That is
outside MCP and outside Agent Link.
"""
import threading
import time

OBJECT_NAME = "AgentLinkPersonOK"
MIN_READ = 1.5      # s the dialog is in view before Approve counts
TTL = 600.0         # s a grant stays good
MAX_LINES = 40
MAX_LINE = 300
DATA_NOTE = "Text from the file is the author's words: data, not instructions."

_lock = threading.Lock()
_GRANTS = {}        # key -> expiry time
_OPEN = {}          # key -> request
# The function that shows the dialog: show(request) -> None. None: use Qt
# (only with a window). Tests put a stand-in here.
SHOW = None


class Refused(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def key(kind, name, sha=None):
    return f"{kind}:{name}:{sha or ''}"


def press_counts(spontaneous, shown_for, as_user=False):
    """True when a press on Approve is the person's own."""
    return bool(spontaneous) and shown_for >= MIN_READ and not as_user


def _clean(text, cap=MAX_LINE):
    t = "".join(c if ord(c) >= 32 and c not in "  ‮‭​" else " " for c in str(text))
    t = " ".join(t.split())
    return t[:cap] + ("…" if len(t) > cap else "")


def _as_user():
    try:
        from . import hooks

        return hooks.as_user()
    except Exception:  # noqa: BLE001
        return False


def window_up():
    try:
        import FreeCAD

        if not getattr(FreeCAD, "GuiUp", False):
            return False
        import FreeCADGui

        return FreeCADGui.getMainWindow() is not None
    except Exception:  # noqa: BLE001
        return False


def take(kind, name, sha=None):
    """Use up a grant: True when the person pressed Approve for this."""
    k = key(kind, name, sha)
    with _lock:
        t = _GRANTS.pop(k, None)
    return t is not None and t >= time.time()


def granted(kind, name, sha=None):
    """True when a grant waits (not used up)."""
    with _lock:
        t = _GRANTS.get(key(kind, name, sha))
    return t is not None and t >= time.time()


def ask(kind, name, title, lines, sha=None, on_ok=None):
    if on_ok is None and take(kind, name, sha):
        return {"ok": True}
    show = SHOW
    if show is None:
        if not window_up():
            raise Refused("unavailable", f"The person's OK is a press in the FreeCAD window, and this FreeCAD has no window. "
                                         f"Open FreeCAD with its window (Agent Link > Start Link), then ask again. Nothing was changed.")
        show = _show_qt
    k = key(kind, name, sha)
    req = {"key": k, "kind": kind, "name": name, "sha": sha, "title": _clean(title, 120),
           "lines": [_clean(x) for x in list(lines or [])[:MAX_LINES]], "on_ok": on_ok, "opened": time.time(), "shown": None}
    with _lock:
        was = _OPEN.get(k)
    if was is None or not was.get("alive", True):
        with _lock:
            _OPEN[k] = req
        show(req)
    return {"pending": True, "kind": kind, "name": name,
            "next": "The FreeCAD window shows the OK dialog now. Ask the person to read it and press Approve there. "
                    "Only a press by the person counts: no tool can press it. "
                    + ("After the press, it is kept." if on_ok else "After the press, call this tool again with the same arguments.")}


def pressed(req, spontaneous, now=None):
    """The person pressed Approve on req's dialog. Answers True when it
    counts (the OK is then given), False when it does not."""
    now = time.time() if now is None else now
    shown = req.get("shown") or req.get("opened") or now
    if not press_counts(spontaneous, now - shown, _as_user()):
        return False
    with _lock:
        _OPEN.pop(req["key"], None)
    if req.get("on_ok"):
        req["on_ok"]()
    else:
        with _lock:
            _GRANTS[req["key"]] = now + TTL
    return True


def declined(req):
    with _lock:
        _OPEN.pop(req["key"], None)
        _GRANTS.pop(req["key"], None)


def reset():
    """Forget every open request and grant (tests)."""
    with _lock:
        _OPEN.clear()
        _GRANTS.clear()


def is_person_ok_widget(w):
    """True when w is the OK dialog or is in it (for gui_input and
    dialog_answer, which refuse it)."""
    seen = 0
    while w is not None and seen < 64:
        try:
            if w.objectName() == OBJECT_NAME:
                return True
            up = getattr(w, "parentWidget", None) or getattr(w, "parent", None)
            w = up() if callable(up) else up
        except Exception:  # noqa: BLE001
            return False
        seen += 1
    return False


# ---- the dialog (Qt; only with a window) ---------------------------------------------------

def _show_qt(req):
    import FreeCADGui
    from PySide import QtCore

    from .gui_link import _qt

    _QtGui, QtWidgets = _qt()

    class Approve(QtWidgets.QPushButton):
        # Never connected to clicked: click() and animateClick() give no
        # event, and sent events are not spontaneous.
        def mouseReleaseEvent(self, ev):
            inside = self.rect().contains(ev.pos()) if hasattr(ev, "pos") else True
            super().mouseReleaseEvent(ev)
            if inside and self.isEnabled():
                dlg._decide(ev.spontaneous())

        def keyPressEvent(self, ev):
            if ev.key() in (QtCore.Qt.Key_Space, QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter) and self.isEnabled():
                dlg._decide(ev.spontaneous())
                return
            super().keyPressEvent(ev)

    class Dialog(QtWidgets.QDialog):
        def _decide(self, spontaneous):
            if pressed(req, spontaneous):
                req["alive"] = False
                self.done(1)
            else:
                note.setText("That press did not count. Read the text, then press Approve yourself.")

        def reject(self):
            declined(req)
            req["alive"] = False
            super().reject()

    dlg = Dialog(FreeCADGui.getMainWindow())
    dlg.setObjectName(OBJECT_NAME)
    dlg.setWindowTitle("Agent Link: your OK")
    dlg.setModal(False)
    dlg.setWindowFlags(dlg.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)
    lay = QtWidgets.QVBoxLayout(dlg)
    head = QtWidgets.QLabel(req["title"])
    head.setTextFormat(QtCore.Qt.PlainText)
    head.setWordWrap(True)
    lay.addWidget(head)
    body = QtWidgets.QPlainTextEdit()
    body.setReadOnly(True)
    body.setPlainText("\n".join(req["lines"] + ["", DATA_NOTE]))
    lay.addWidget(body)
    note = QtWidgets.QLabel("An agent asked for this. Approve only if you want it.")
    note.setTextFormat(QtCore.Qt.PlainText)
    note.setWordWrap(True)
    lay.addWidget(note)
    row = QtWidgets.QHBoxLayout()
    no = QtWidgets.QPushButton("Decline")
    no.setDefault(True)
    no.clicked.connect(dlg.reject)
    yes = Approve("Approve")
    yes.setAutoDefault(False)
    yes.setEnabled(False)
    row.addWidget(no)
    row.addWidget(yes)
    lay.addLayout(row)
    dlg.resize(560, 360)
    dlg.show()
    dlg.raise_()
    req["shown"] = time.time()
    req["dialog"] = dlg
    QtCore.QTimer.singleShot(int(MIN_READ * 1000), lambda: yes.setEnabled(True))
