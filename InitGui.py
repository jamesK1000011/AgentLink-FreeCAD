# SPDX-License-Identifier: LGPL-2.1-or-later
# The Agent Link workbench: Start link, Stop link, the panel, a screenshot
# for the agent, and Setup check and Updates in its menu. While the link is on,
# an agent's calls arrive in the document open in this window. The workbench
# is built in agentlink/workbench.py; FreeCAD runs this file at start.

import FreeCADGui

from agentlink import workbench as _agentlink_workbench

_agentlink_workbench.add(FreeCADGui)
