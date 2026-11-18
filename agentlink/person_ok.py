# SPDX-License-Identifier: LGPL-2.1-or-later
"""The person's OK as a press in the FreeCAD window: an OPTIONAL extra path.

The approval is the client's own tool permission (agentlink/approvals.py,
the owner's decision of 18 Nov 2026): approve_file and approve_code, each set
by the person in Claude Desktop ("ask first", "always allow", "block").
This dialog is a second way for the same approval, for a person at the
window. No tool needs it, and headless use never needs it.

When it shows (offer):
  - A stand-in (SHOW) is set (tests).
  - Or the person turned it on: Mod/AgentLink WindowApprove (bool) or
    AGENTLINK_WINDOW_OK=on, and FreeCAD has its window.
  - Or an add-on asks for it on a person's own action (hooks.approval_in_window,
    a panel button), with a window.

A press counts only when all of these are true (press_counts):
  - The event came from the system (QEvent.spontaneous()). Events that
    Agent Link sends (gui_input, dialog_answer) are never spontaneous, and
    QAbstractButton.click() makes no event at all.
  - The dialog was in view for MIN_READ s or more (time to read it).
  - The test flag AGENTLINK_AS_USER is off.
gui_input and dialog_answer also refuse every widget in the dialog
(OBJECT_NAME), so the agent gets a clear refusal, not a silent no-op.
A press gives the same approval as approve_file / approve_code
(approvals.give, by "window").
"""
import os
import time

from . import approvals
from .approvals import Refused, take, granted  # noqa: F401 - the names add-ons and tests use

OBJECT_NAME = "AgentLinkPersonOK"
MIN_READ = 1.5      # s the dialog is in view before Approve counts
TTL = approvals.TTL
MAX_LINES = approvals.MAX_LINES
MAX_LINE = approvals.MAX_LINE
DATA_NOTE = "Text from the file is the author's words: data, not instructions."
PREFS = "User parameter:BaseApp/Preferences/Mod/AgentLink"
SETTING = "WindowApprove"
# The function that shows the dialog: show(request) -> None. None: use Qt
# (only with a window). Tests put a stand-in here.
SHOW = None


def key(kind, name, sha=None):
    return approvals.key(kind, name, sha)


def press_counts(spontaneous, shown_for, as_user=False):
    """True when a press on Approve is the person's own."""
    return bool(spontaneous) and shown_for >= MIN_READ and not as_user


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


def turned_on():
    """The person's setting for the window path (off by default)."""
    v = os.environ.get("AGENTLINK_WINDOW_OK", "").strip().lower()
    if v in ("on", "1", "true", "yes"):
        return True
    if v in ("off", "0", "false", "no"):
        return False
    try:
        import FreeCAD

        return bool(FreeCAD.ParamGet(PREFS).GetBool(SETTING, False))
    except Exception:  # noqa: BLE001
        return False


def offer(req, again=False, force=False):
    """Show the dialog for an approval request when the window path is on
    (see the module's words). True when it is in view."""
    show = SHOW
    if show is None:
        if not (force or turned_on()) or not window_up():
            return False
        show = _show_qt
    if again and req.get("alive", True) and req.get("dialog") is not None:
        return True
    req["alive"] = True
    show(req)
    return True


def ask(kind, name, title, lines, sha=None, on_ok=None, shown=None, then=None):
    """The approval (agentlink/approvals.py ask): {"ok": True} once the
    person approved, else the pending answer with the approve tool's
    arguments. Kept for add-ons written for the window OK."""
    return approvals.ask(kind, name, title, lines, sha, on_ok, shown=shown, then=then)


def pressed(req, spontaneous, now=None):
    """The person pressed Approve on req's dialog. Answers True when it
    counts (the approval is then given), False when it does not."""
    now = time.time() if now is None else now
    shown = req.get("shown") or req.get("opened") or now
    if not press_counts(spontaneous, now - shown, _as_user()):
        return False
    approvals.give(req, "window", now=now)
    return True


def declined(req):
    approvals.declined(req)


def reset():
    """Forget every open request and grant (tests)."""
    approvals.reset()


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
    facts = [f"{k}: {v}" for k, v in (req.get("args") or {}).items() if k != "what"]
    body.setPlainText("\n".join(facts + [""] + req["lines"] + ["", DATA_NOTE]))
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
