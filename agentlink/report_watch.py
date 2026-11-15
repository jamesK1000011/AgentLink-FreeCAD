# SPDX-License-Identifier: LGPL-2.1-or-later
# The Report view, watched for the agent: after each call in the window, any
# new warning, error or traceback line (since the call before, or since
# FreeCAD started for the first call) comes back with that call's answer as
# "report", so the agent sees a problem when it happens instead of the person
# finding it at the bottom of the window.

import re

MARK = re.compile(r"(Traceback|Error|error:|Exception|Warning|warning:|failed|Failed|cannot|could not|Could not)")
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


def _report_text():
    try:
        import FreeCADGui
        from PySide import QtWidgets

        mw = FreeCADGui.getMainWindow()
        for w in mw.findChildren(QtWidgets.QTextEdit):
            if w.metaObject().className() == "Gui::DockWnd::ReportOutput":
                return w.toPlainText()
    except Exception:
        return None
    return None


def take():
    """New problem lines in the Report view since the last take(); [] when
    there are none or the view cannot be read."""
    text = _report_text()
    if text is None:
        return []
    out, _state["seen"] = problems(text, _state["seen"])
    return out
