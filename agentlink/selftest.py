# SPDX-License-Identifier: LGPL-2.1-or-later
"""A self-test tool for live checks of the hub's guards, off by default.

selftest_exit calls sys.exit(0) inside a tool, so a live check can prove
that FreeCAD stays up and the call is answered failed with its outcome
(efficiency design E8). It is there only while the marker file
.selftest-exit is in the Agent Link folder when FreeCAD starts; remove the
file and restart to take the tool away. It changes nothing."""
import os
import sys

MARK = ".selftest-exit"


def _home():
    return os.environ.get("AGENTLINK_HOME") or os.path.expanduser("~/AgentLink")


def enabled(home=None):
    return os.path.isfile(os.path.join(home or _home(), MARK))


def selftest_exit(a):
    sys.exit(0)


def tools(home=None):
    if not enabled(home):
        return []
    from .protocol import Tool

    t = Tool("selftest_exit", "A test tool for a live check: it calls sys.exit(0) in a tool. FreeCAD stays up, and the call is refused with failed. "
                              "It is there only while the marker file .selftest-exit is in the Agent Link folder. Changes nothing.",
             {"type": "object", "properties": {}, "additionalProperties": False}, selftest_exit, group="selftest")
    return [t]
