# SPDX-License-Identifier: LGPL-2.1-or-later
# AddonKit for FreeCAD, the library Agent Link and the add-ons share, at a
# version this Agent Link accepts.
ACCEPTS = ">=1.4,<2"

try:
    import addonkit
except ImportError as e:
    raise ImportError("Agent Link for FreeCAD needs AddonKit for FreeCAD (github.com/jamesK1000011/AddonKit-FreeCAD): "
                      "install it from the Addon Manager, or let agentlink_update fetch it.") from e

addonkit.require(ACCEPTS, "Agent Link for FreeCAD")
