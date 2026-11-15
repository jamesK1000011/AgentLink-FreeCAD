# SPDX-License-Identifier: LGPL-2.1-or-later
# This add-on's own copy; it was AddonKit's addonkit.materials, retired 14 Nov 2026.
"""Printing filaments: one table Agent Link reads (data/filaments.json). The person's own filaments
go in ~/.config/freecad-agentlink/filaments.json and win over ours. The usual stock that is not
printed (metals, woods, plastic sheet and rod) is a second table, densities only (data/stock.json).
No FreeCAD here."""

import os

from . import datafiles as data

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SOURCE = "Typical FDM filament figures, along the layers"


def filaments():
    """{key: {name, density, E, nu, yield, uts, k, softens, source, date}}"""
    return data.load(_DATA, "filaments", package="freecad-agentlink")["entries"]


FILAMENTS = filaments()
DENSITY = {k: v["density"] for k, v in FILAMENTS.items()}


def stock():
    """{key: {name, density, source, date}}: metals, woods, plastic stock."""
    return data.load(_DATA, "stock", package="freecad-agentlink")["entries"]


STOCK = stock()
# g/cm³ of everything a part may be made of: the filaments, then the stock.
MASS_DENSITY = {**DENSITY, **{k: v["density"] for k, v in STOCK.items() if k not in DENSITY}}


def density(key, default=None):
    return DENSITY.get(str(key).lower(), default)


def card(key):
    """A filament as a material card (the shape FreeCAD's library cards are
    read into), or None."""
    f = FILAMENTS.get(str(key).lower())
    if f is None:
        return None
    k = str(key).lower()
    return {"id": k, "name": f["name"], "category": "Printing filament", "density": f["density"], "E": f.get("E"), "nu": f.get("nu"),
            "yield": f.get("yield"), "uts": f.get("uts"), "k": f.get("k"), "softens": f.get("softens"), "source": SOURCE}
