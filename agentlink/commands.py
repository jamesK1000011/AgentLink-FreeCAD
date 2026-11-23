# SPDX-License-Identifier: LGPL-2.1-or-later
# The Agent Link workbench's commands. They live in a module of their own:
# FreeCAD runs InitGui.py so that its top-level names are gone by the time
# the workbench's Initialize runs.


class _StartLink:
    def GetResources(self):
        return {"Pixmap": "AgentLink_Start", "MenuText": "Start Link", "ToolTip": "Let an agent drive this window (local only)"}

    def IsActive(self):
        import agentlink_state

        return agentlink_state.link is None

    def Activated(self):
        import agentlink_state
        from agentlink.gui_link import Link

        agentlink_state.link = Link()
        agentlink_state.link.start()


class _StopLink:
    def GetResources(self):
        return {"Pixmap": "AgentLink_Stop", "MenuText": "Stop Link", "ToolTip": "Close the agent's link"}

    def IsActive(self):
        import agentlink_state

        return agentlink_state.link is not None

    def Activated(self):
        import agentlink_state

        agentlink_state.link.stop()
        agentlink_state.link = None


class _Panel:
    def GetResources(self):
        return {"Pixmap": "AgentLink_Panel", "MenuText": "Agent Link Panel", "ToolTip": "Notes pinned to the parts, the build played step by step, the part's review and what the agent did"}

    def IsActive(self):
        return True

    def Activated(self):
        from agentlink import layout, panel

        # Slid out over the 3D view (PanelLayout left-slide): this button
        # opens and closes it.
        if panel._panel is not None and layout.read() == layout.LEFT_SLIDE:
            layout.own().toggle()
            return
        panel.show()


class _Shot:
    def GetResources(self):
        return {"Pixmap": "AgentLink_Shot", "MenuText": "Screenshot for Agent", "ToolTip": "Take the window as you see it, mark it up and leave it for the agent (Alt+Shift+S)", "Accel": "Alt+Shift+S"}

    def IsActive(self):
        return True

    def Activated(self):
        from agentlink import shots

        shots.take()


def _widgets():
    """FreeCAD's PySide widgets module (QtWidgets on Qt 6 builds, QtGui on Qt 5)."""
    try:
        from PySide import QtWidgets
    except ImportError:
        from PySide import QtGui as QtWidgets
    return QtWidgets


class _Check:
    def GetResources(self):
        return {"Pixmap": "AgentLink_Check", "MenuText": "Setup Check", "ToolTip": "Check the setup: FreeCAD, the add-on, uv and, if you use it, the Claude Desktop extension's launcher and its log's last lines"}

    def IsActive(self):
        return True

    def Activated(self):
        import FreeCADGui

        from agentlink import launcher_check

        QtWidgets = _widgets()
        r = launcher_check.report()
        box = QtWidgets.QMessageBox(FreeCADGui.getMainWindow())
        box.setWindowTitle("Agent Link Setup Check")
        set_box_text(box, "Agent Link Setup Check", launcher_check.summary(r))
        mend = box.addButton("Mend", QtWidgets.QMessageBox.AcceptRole) if launcher_check.can_mend(r) else None
        box.addButton(QtWidgets.QMessageBox.Close)
        box.exec_() if hasattr(box, "exec_") else box.exec()
        if mend is not None and box.clickedButton() is mend:
            done = launcher_check.mend()
            info(box.parent(), "Agent Link", f"Mended: {done}." if done else "Nothing was changed.")


def _here():
    import os

    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def installed_version(root=None):
    """(version from package.xml, short commit or None) of this copy."""
    import os
    import re

    root = root or _here()
    ver = "?"
    try:
        with open(os.path.join(root, "package.xml"), encoding="utf-8") as f:
            m = re.search(r"<version>([^<]+)</version>", f.read())
            ver = m.group(1).strip() if m else ver
    except OSError:
        pass
    sha = None
    try:
        with open(os.path.join(root, ".git", "HEAD"), encoding="utf-8") as f:
            head = f.read().strip()
        if head.startswith("ref: "):
            with open(os.path.join(root, ".git", *head[5:].split("/")), encoding="utf-8") as f:
                head = f.read().strip()
        sha = head[:7] if re.fullmatch(r"[0-9a-f]{40}", head) else None
    except OSError:
        pass
    return ver, sha


def updates_text(version, sha=None):
    """The Updates command's words: which Agent Link this is and how it is
    kept up to date."""
    this = f"Agent Link {version}" + (f" (commit {sha})" if sha else "")
    return "\n".join((
        f"This is {this}.",
        "",
        "With the Claude Desktop extension, Agent Link updates each time it starts. With any AI client, ask the agent to run agentlink_update to update now; this window runs the new code once FreeCAD restarts.",
        "Other add-ons update from Tools ▸ Addon Manager, or ask the agent.",
    ))


class _Updates:
    def GetResources(self):
        return {"Pixmap": "AgentLink_Update", "MenuText": "Updates", "ToolTip": "Which Agent Link this is, and how it is kept up to date"}

    def IsActive(self):
        return True

    def Activated(self):
        import FreeCADGui

        QtWidgets = _widgets()
        info(FreeCADGui.getMainWindow(), "Agent Link Updates", updates_text(*installed_version()))


# Every command of the workbench, by name, in toolbar order.
COMMANDS = (("AgentLink_Start", _StartLink), ("AgentLink_Stop", _StopLink), ("AgentLink_Panel", _Panel),
            ("AgentLink_Shot", _Shot), ("AgentLink_Check", _Check), ("AgentLink_Update", _Updates))


def autostart():
    """Turn the link on when the FreeCAD window opens, so an agent's calls
    land in it without a click (Preferences: Mod/AgentLink AutoStart, on by
    default). Quietly does nothing if the port is taken."""
    import FreeCAD

    if not FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/AgentLink").GetBool("AutoStart", True):
        return
    import agentlink_state

    try:
        import FreeCADGui

        FreeCADGui.addCommand("AgentLink_Shot", _Shot())
    except Exception:
        pass
    if agentlink_state.link is not None:
        return
    try:
        from agentlink.gui_link import Link

        link = Link()
        link.start()
        agentlink_state.link = link
        # The Agent Link panel up with it: notes, steps and what the agent does.
        if FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/AgentLink").GetBool("ShowPanel", True):
            from agentlink import panel

            panel.show()
    except OSError as e:
        FreeCAD.Console.PrintLog(f"Agent Link: link not started ({e})\n")


def split_text(text):
    """(the lines a person reads, the log lines): a launcher log line starts
    with a [time stamp] and belongs under Show Details, not in the box."""
    lines = (text or "").splitlines()
    log = [l for l in lines if l.lstrip().startswith("[") and "]" in l[:40]]
    rest = [l for l in lines if l not in log]
    return "\n".join(rest).strip(), "\n".join(log).strip()


def set_box_text(box, title, text):
    """A message box that reads on macOS too, where a box has no title bar:
    the title as its bold first line, the message under it, the log lines
    under Show Details."""
    body, log = split_text(text)
    box.setWindowTitle(title)
    box.setText(f"<b>{title}</b>")
    box.setInformativeText(body)
    if log:
        box.setDetailedText(log)


def info(parent, title, text):
    QtWidgets = _widgets()
    box = QtWidgets.QMessageBox(parent)
    set_box_text(box, title, text)
    box.addButton(QtWidgets.QMessageBox.Ok)
    box.exec_() if hasattr(box, "exec_") else box.exec()
