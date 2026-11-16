# SPDX-License-Identifier: LGPL-2.1-or-later
# The Report view, watched for the agent: after each call in the window, any
# new warning, error or traceback line (since the call before, or since
# FreeCAD started for the first call) comes back with that call's answer as
# "report", so the agent sees a problem when it happens instead of the person
# finding it at the bottom of the window.

import re

# Case does not matter: FreeCAD writes "Cannot find icon", Qt "(qt.qpa.fonts)
# … missing font family", and both were missed with a case-sensitive list
# (live on the Mac).
MARK = re.compile(r"(traceback|error|exception|warning|failed|cannot|could not|not found|missing|\(qt\.[a-z.]+\)|^qt\.[a-z.]+:)", re.I)
MAX_LINES, MAX_CHARS = 6, 300
# Qt's own start-up line about font aliases ("Populating font family aliases
# took 147 ms. Replace uses of missing font family …"): written at every
# start, nothing anyone can act on from here. It is left off the answers
# (problems(), take()) and stays readable through report_read (read()).
QUIET = re.compile(r"(populating font family aliases took|replace uses of missing font family)", re.I)


def quiet(line):
    """Whether a problem-looking line is start-up noise kept off the answers."""
    return bool(QUIET.search(line or ""))
_state = {"seen": 0}


def problems(text, start):
    """(the lines that look like problems in text[start:], the new offset).
    Text shorter than start means the view was cleared: read it from 0."""
    if start > len(text):
        start = 0
    new = text[start:]
    out = []
    for line in new.splitlines():
        line = line.strip()
        if line and MARK.search(line) and not quiet(line):
            out.append(line[:MAX_CHARS])
    if len(out) > MAX_LINES:
        out = out[:MAX_LINES - 1] + [f"… and {len(out) - MAX_LINES + 1} more lines (window_snapshot part: \"Report view\")"]
    return out, len(text)


def _report_widget():
    """FreeCAD's Report view: the text edit inside the dock named
    "Report view" (its object name), else one whose class says Report."""
    import FreeCADGui
    from PySide import QtWidgets

    mw = FreeCADGui.getMainWindow()
    for dock in mw.findChildren(QtWidgets.QDockWidget):
        if dock.objectName() in ("Std_ReportView", "Report view", "ReportView") or dock.windowTitle() in ("Report view", "Report View"):
            for w in [dock.widget()] + dock.findChildren(QtWidgets.QWidget):
                if w is not None and hasattr(w, "toPlainText"):
                    return w
    for w in mw.findChildren(QtWidgets.QWidget):
        if "Report" in w.metaObject().className() and hasattr(w, "toPlainText"):
            return w
    return None


def _report_text():
    try:
        w = _report_widget()
        return w.toPlainText() if w is not None else None
    except Exception:
        return None


def read(last=40, problems_only=False):
    """The Report view's last lines (for report_read): what is there, whether
    it could be found at all, and the problem lines among them."""
    text = _report_text()
    if text is None:
        return {"found": False, "lines": [], "note": "The Report view could not be found in this window."}
    lines = [l for l in text.splitlines() if l.strip()]
    try:
        rows, _n = _blocks(_report_widget(), 0)
        probs = coloured(rows, _problem_colours())
    except Exception:
        probs = [l for l in lines if MARK.search(l)]
    pick = probs if problems_only else lines
    return {"found": True, "count": len(lines), "problems": len(probs), "lines": pick[-max(1, min(int(last), 200)):]}


PARAM = "User parameter:BaseApp/Preferences/OutputWindow"


def _problem_colours():
    """FreeCAD's own warning and error colours for the Report view (#rrggbb),
    with its defaults: a line in one of them is a warning or an error
    whatever its words say ("Pauses: … is in no print setup" is red)."""
    out = {"#ffaa00", "#ff0000"}
    try:
        import FreeCAD

        g = FreeCAD.ParamGet(PARAM)
        for name in ("colorWarning", "colorError", "colorCritical"):
            v = g.GetUnsigned(name, 0)
            if v:
                out.add("#%06x" % ((v >> 8) & 0xFFFFFF))
    except Exception:
        pass
    return out


def coloured(lines_with_colour, colours):
    """The lines whose colour is a warning or error colour, or whose words
    say so (MARK): lines_with_colour is [(text, "#rrggbb" or None)]."""
    out = []
    for text, colour in lines_with_colour:
        t = text.strip()
        if t and ((colour or "").lower() in colours or MARK.search(t)):
            out.append(t[:MAX_CHARS])
    return out


def _blocks(w, start):
    """[(text, colour)] for the Report view's blocks from number start, and
    the block count. A line's colour is the first problem colour among its
    runs of text: FreeCAD writes the time stamp in the normal colour and the
    message after it in the warning or error colour, so the first run alone
    missed every orange and red line live."""
    doc = w.document()
    n = doc.blockCount()
    if start > n:
        start = 0
    colours = _problem_colours()
    rows = []
    b = doc.findBlockByNumber(start)
    while b.isValid():
        colour = None
        try:
            from PySide import QtGui

            cur = QtGui.QTextCursor(b)
            start_pos, length = b.position(), max(0, b.length() - 1)
            step = max(1, length // 24)
            for off in range(1, length + 1, step):
                cur.setPosition(start_pos + off)
                c = cur.charFormat().foreground().color().name()
                if colour is None or c.lower() in colours:
                    colour = c
                if c.lower() in colours:
                    break
        except Exception:
            pass
        rows.append((b.text(), colour))
        b = b.next()
    return rows, n


def take():
    """New problem lines in the Report view since the last take(), by
    colour and by words; [] when there are none or it cannot be read."""
    try:
        w = _report_widget()
    except Exception:
        w = None
    if w is None:
        return []
    try:
        rows, _state["seen"] = _blocks(w, _state["seen"])
    except Exception:
        return []
    out = [t for t in coloured(rows, _problem_colours()) if not quiet(t)]
    if len(out) > MAX_LINES:
        out = out[:MAX_LINES - 1] + [f"… and {len(out) - MAX_LINES + 1} more lines (report_read problems: true)"]
    return out


# ---- the Report view kept out of the way -------------------------------------
# The Report view is hidden by default: it took a quarter of the window's
# height to say "listening".
# It opens itself when a warning or error line arrives (by FreeCAD's colours
# or the words, as above). ReportAuto (on by default) turns this off; then
# the Report view is shown or hidden again as the person last had it.
# FreeCAD's own Report view preferences are not touched.

AL_PARAMS = "User parameter:BaseApp/Preferences/Mod/AgentLink"
AUTO, TAKEN, WAS = "ReportAuto", "ReportTaken", "ReportWasShown"
AUTO_MS = 700


def auto_on(params):
    """Whether the Report view is kept hidden until a problem: ReportAuto
    on (the default, with or without a PanelLayout setting)."""
    return params.GetBool(AUTO, True)


def _report_dock():
    import FreeCADGui
    from PySide import QtWidgets

    for dock in FreeCADGui.getMainWindow().findChildren(QtWidgets.QDockWidget):
        if dock.objectName() in ("Std_ReportView", "Report view", "ReportView") or dock.windowTitle() in ("Report view", "Report View"):
            return dock
    return None


# Lines that are noise at start-up, not a problem for the person: Qt's font
# and platform chatter and FreeCAD's missing icons. They still ride on the
# agent's answers (MARK), bar the font-alias line (QUIET); they do not open
# the Report view.
NOISE = re.compile(r"(\(qt\.qpa|^qt\.qpa|font famil|cannot find icon)", re.I)
# FreeCAD shows the Report view again as it starts and at a workbench switch
# (its saved dock layout): for this long after either, a Report view that
# shows without a problem line is hidden again.
GRACE = 6.0


def problems_to_open(rows, colours):
    """The problem lines (coloured()) that open the Report view: noise left
    out."""
    return [t for t in coloured(rows, colours) if not NOISE.search(t)]


class AutoOpen:
    """One tick() per AUTO_MS: take the Report view over (hide it, the
    person's state kept in TAKEN/WAS), give it back when turned off, and
    open it when a new block of the Report view is a problem line. Within
    GRACE seconds of the start or a workbench switch (switched()), FreeCAD
    showing it again is undone. The window, the parameters, the colours
    and the clock are handed in for the tests."""

    def __init__(self, params=None, dock=_report_dock, widget=_report_widget, colours=_problem_colours, blocks=None, clock=None):
        import time

        self.params = params
        self.dock, self.widget, self.colours = dock, widget, colours
        self.blocks = blocks or _blocks
        self.clock = clock or time.monotonic
        self.taken = False
        self.opened = False
        self.seen = None
        self.grace = self.clock() + GRACE

    def _p(self):
        if self.params is None:
            import FreeCAD

            self.params = FreeCAD.ParamGet(AL_PARAMS)
        return self.params

    def switched(self, *_):
        """A workbench switch: FreeCAD may show the Report view again."""
        self.grace = self.clock() + GRACE

    def tick(self):
        """What it did: "hidden", "restored", "opened" or None."""
        p = self._p()
        dock = self.dock()
        if dock is None:
            return None
        if not auto_on(p):
            if p.GetBool(TAKEN, False):
                dock.setVisible(p.GetBool(WAS, True))
                p.SetBool(TAKEN, False)
                self.taken = False
                return "restored"
            return None
        w = self.widget()
        if not self.taken:
            if not p.GetBool(TAKEN, False):
                p.SetBool(WAS, bool(dock.isVisible()))
                p.SetBool(TAKEN, True)
            self.taken = True
            self.seen = w.document().blockCount() if w is not None else None
            self.grace = self.clock() + GRACE
            dock.hide()
            return "hidden"
        if self.opened and not dock.isVisible():
            self.opened = False  # the person closed it after a problem
        n = w.document().blockCount() if w is not None else self.seen
        if w is not None and not (self.seen is not None and n == self.seen):
            # From the block that was last: FreeCAD writes into the empty
            # block its last line left.
            rows, self.seen = self.blocks(w, max(0, (self.seen or n) - 1))
            if problems_to_open(rows, self.colours()):
                self.opened = True
                if not dock.isVisible():
                    dock.show()
                    dock.raise_()
                    return "opened"
                return None
        if dock.isVisible() and not self.opened and self.clock() < self.grace:
            dock.hide()  # FreeCAD's start-up or switch showed it again
            return "hidden"
        return None


_auto = {}


def start_auto():
    """The Report view's watch, on FreeCAD's GUI timer (once)."""
    if _auto:
        return _auto["it"]
    import FreeCADGui
    from PySide import QtCore

    it = _auto["it"] = AutoOpen()
    t = _auto["timer"] = QtCore.QTimer(FreeCADGui.getMainWindow())
    t.setInterval(AUTO_MS)

    def tick():
        try:
            it.tick()
        except Exception as e:  # noqa: BLE001 — never stop the GUI timer
            import FreeCAD

            FreeCAD.Console.PrintLog(f"Agent Link Report view watch: {e}\n")

    t.timeout.connect(tick)
    t.start()
    try:
        FreeCADGui.getMainWindow().workbenchActivated.connect(it.switched)
    except Exception:  # noqa: BLE001
        pass
    tick()  # hidden at once, not after the first interval
    return it
