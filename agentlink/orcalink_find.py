# SPDX-License-Identifier: LGPL-2.1-or-later
# Agent Link for OrcaSlicer (jamesK1000011/AgentLink-OrcaSlicer, the orcalink
# package) is a separate add-on: OrcaSlicer's tools with no FreeCAD in them.
# Found where it is installed — importable already, AGENTLINK_ORCALINK, or a
# folder beside this add-on (FreeCAD's Mod folder, the launcher's add-ons).
import importlib
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES = ("OrcaLink", "AgentLink-OrcaSlicer", "agentlink-orcaslicer", "OrcaSlicer-AgentLink", "orcaslicer-agentlink", "OrcaSlicerAgentLink")


def places():
    out = []
    if os.environ.get("AGENTLINK_ORCALINK"):
        out.append(os.path.expanduser(os.environ["AGENTLINK_ORCALINK"]))
    parent = os.path.dirname(HERE)
    out += [os.path.join(parent, n) for n in NAMES]
    return out


def find():
    """The orcalink package, or None when it is not installed."""
    try:
        return importlib.import_module("orcalink")
    except ImportError:
        pass
    for p in places():
        if os.path.isfile(os.path.join(p, "orcalink", "__init__.py")):
            if p not in sys.path:
                sys.path.append(p)
            try:
                return importlib.import_module("orcalink")
            except ImportError:
                continue
    return None


def module(name):
    """One of its modules (orca3mf, gcode_view, calibrate, draco,
    printstrength, meshgen …), or an ImportError saying where to get it."""
    if find() is None:
        raise ImportError("Agent Link for OrcaSlicer is not installed: github.com/jamesK1000011/AgentLink-OrcaSlicer (agentlink_update installs it beside this add-on).")
    return importlib.import_module("orcalink." + name)
