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
        if line and MARK.search(line):
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
        if dock.objectName() in ("Report view", "ReportView") or dock.windowTitle() in ("Report view", "Report View"):
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
    the block count; colour from each block's first character."""
    doc = w.document()
    n = doc.blockCount()
    if start > n:
        start = 0
    rows = []
    b = doc.findBlockByNumber(start)
    while b.isValid():
        colour = None
        try:
            it = b.begin()
            if not it.atEnd():
                colour = it.fragment().charFormat().foreground().color().name()
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
    out = coloured(rows, _problem_colours())
    if len(out) > MAX_LINES:
        out = out[:MAX_LINES - 1] + [f"… and {len(out) - MAX_LINES + 1} more lines (report_read problems: true)"]
    return out
