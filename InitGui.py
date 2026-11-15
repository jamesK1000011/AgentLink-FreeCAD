# SPDX-License-Identifier: LGPL-2.1-or-later
# The Agent Link workbench: Start link and Stop link. While the link is on,
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
        from agentlink.commands import _Panel, _Shot, _StartLink, _StopLink

        FreeCADGui.addCommand("AgentLink_Start", _StartLink())
        FreeCADGui.addCommand("AgentLink_Stop", _StopLink())
        FreeCADGui.addCommand("AgentLink_Panel", _Panel())
        FreeCADGui.addCommand("AgentLink_Shot", _Shot())
        self.appendToolbar("Agent Link", ["AgentLink_Start", "AgentLink_Stop", "AgentLink_Panel", "AgentLink_Shot"])
        self.appendMenu("Agent Link", ["AgentLink_Start", "AgentLink_Stop", "AgentLink_Panel", "AgentLink_Shot"])

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
