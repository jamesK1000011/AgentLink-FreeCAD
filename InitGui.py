# SPDX-License-Identifier: LGPL-2.1-or-later
# The Agent Link workbench: Start link, Stop link, the panel, a screenshot
# for the agent, and Setup check and Updates in its menu. While the link is on,
# an agent's calls arrive in the document open in this window.

import os

import FreeCADGui
import agentlink

# The add-on's own SVGs, found by name ("AgentLink_Start", ...) by its commands.
_ICONS = os.path.join(os.path.dirname(agentlink.__file__), "icons")
FreeCADGui.addIconPath(_ICONS)


class AgentLinkWorkbench(FreeCADGui.Workbench):
    MenuText = "Agent Link"
    ToolTip = "Drive FreeCAD from an agent"
    Icon = os.path.join(_ICONS, "AgentLink_Workbench.svg")

    def Initialize(self):
        from agentlink.commands import COMMANDS

        for name, cls in COMMANDS:
            FreeCADGui.addCommand(name, cls())
        link = ["AgentLink_Start", "AgentLink_Stop", "AgentLink_Panel", "AgentLink_Shot"]
        setup = ["AgentLink_Check", "AgentLink_Update"]
        self.appendToolbar("Agent Link", link)
        self.appendMenu("Agent Link", link + ["Separator"] + setup)

    def GetClassName(self):
        return "Gui::PythonWorkbench"


FreeCADGui.addWorkbench(AgentLinkWorkbench())


def _agentlink_autostart():
    from agentlink.commands import autostart

    autostart()


try:
    from PySide import QtCore

    # After the window is up: the link needs a document and the GUI's timer.
    QtCore.QTimer.singleShot(1500, _agentlink_autostart)
except Exception:
    pass
