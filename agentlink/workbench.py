# SPDX-License-Identifier: LGPL-2.1-or-later
# The Agent Link workbench: Start link, Stop link, the panel, a screenshot
# for the agent, and Setup check and Updates in its menu. InitGui.py adds it.
#
# It is built here, in a real module, because FreeCAD runs InitGui.py with
# exec() and a separate locals dict: a class body or a method body there sees
# only FreeCAD's own globals, never the names InitGui.py itself defines.

import os

ICONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")

LINK = ["AgentLink_Start", "AgentLink_Stop", "AgentLink_Panel", "AgentLink_Shot"]
SETUP = ["AgentLink_Check", "AgentLink_Update"]


def make_class(Gui):
    """AgentLinkWorkbench on this FreeCADGui's Workbench base."""

    class AgentLinkWorkbench(Gui.Workbench):
        MenuText = "Agent Link"
        ToolTip = "Drive FreeCAD from an agent"
        Icon = os.path.join(ICONS, "AgentLink_Workbench.svg")

        def Initialize(self):
            from .commands import COMMANDS

            for name, cls in COMMANDS:
                Gui.addCommand(name, cls())
            self.appendToolbar("Agent Link", LINK)
            self.appendMenu("Agent Link", LINK + ["Separator"] + SETUP)

        def GetClassName(self):
            return "Gui::PythonWorkbench"

    return AgentLinkWorkbench


def _autostart():
    from .commands import autostart

    autostart()


def add(Gui=None):
    """The icons, the workbench, and the link's autostart once the window is
    up (it needs a document and the GUI's timer): what InitGui.py calls."""
    if Gui is None:
        import FreeCADGui as Gui
    # The add-on's own SVGs, found by name ("AgentLink_Start", ...) by its commands.
    Gui.addIconPath(ICONS)
    cls = make_class(Gui)
    Gui.addWorkbench(cls())
    # One place for every add-on's panel (the PanelLayout setting): add-ons
    # place theirs through this placer when Agent Link is installed.
    from . import hooks, layout

    hooks.provide(layout.SERVICE, layout.own())
    try:
        from PySide import QtCore

        QtCore.QTimer.singleShot(1500, _autostart)
        QtCore.QTimer.singleShot(1500, _report_auto)
        # macOS: quitting crashed in PySide's teardown (quit_guard.py).
        from . import quit_guard

        QtCore.QTimer.singleShot(1500, quit_guard.install)
    except Exception:
        pass
    return cls


def _report_auto():
    from . import report_watch

    report_watch.start_auto()
