# SPDX-License-Identifier: LGPL-2.1-or-later
# What parts are made of: FreeCAD's material library (the Materials
# module's MaterialManager) searched by words and category, the add-on's
# own printing filaments, and custom materials given by their figures.
# A body's material is kept in the document (store "materials",
# {body: id}) and, where this FreeCAD has it, on the object's ShapeMaterial.
#
# Ids: a filament key (pla, petg …), a library card's UUID, or
# custom:<name> for one given here (its figures kept under materialDefs).

import re

from .. import runners
from .. import store
from .. import materials as _fil
from ..materials import DENSITY


def _owner(doc, bodies, material):
    """The materials owner's answer (an add-on's "material_set" service,
    hooks): {"materials", "freecadMaterial", "from"}; None when no add-on
    offers it or it does not know this material (Agent Link sets it then)."""
    from .. import hooks

    fn = hooks.service("material_set")
    if fn is None:
        return None
    try:
        out = fn(doc, list(bodies), material)
    except Exception:  # noqa: BLE001 - not a material it keeps: set here
        return None
    if not isinstance(out, dict):
        return None
    return {**out, "from": "the material_set service of an installed add-on (it keeps the materials record)"}


GROUP = "material"
INFO = "Materials: search FreeCAD's library and the printing filaments, read a card's figures, set what each body is made of."

# Typical figures for FDM-printed filament, along the layers (MPa, g/cm³).
# Data sheets vary a good deal between brands; these are middling ones.
# The printing filaments: one table (agentlink/data/filaments.json).
FILAMENT = {k: {f: v.get(f) for f in ("name", "E", "nu", "yield", "uts", "k", "softens")} for k, v in _fil.FILAMENTS.items()}
FILAMENT_SOURCE = "Agent Link's typical FDM filament figures, along the layers"
TYPICAL = "Library and filament figures are typical: for a part that must not fail, use the supplier's data sheet (material_set custom)."
# Library folders that hold no solid's mechanics.
SKIP_DIRS = ("Appearance", "Patterns", "Test", "Fluid")
# The library's cards for filament keys, by name, for ShapeMaterial.
LIB_NAME = {"pla": "PLA", "abs": "ABS"}

_cache = {}


def _manager():
    """FreeCAD's MaterialManager, made once; None on a FreeCAD without the Materials module."""
    if "mm" not in _cache:
        try:
            import Materials

            _cache["mm"] = Materials.MaterialManager()
        except Exception:  # an old FreeCAD: the filament table alone
            _cache["mm"] = None
    return _cache["mm"]


def _q(m, name, unit):
    """A library card's physical property as a number in unit, or None."""
    try:
        if not m.hasPhysicalProperty(name):
            return None
        v = m.getPhysicalValue(name)
    except Exception:
        return None
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(v.getValueAs(unit))
    except Exception:
        return None


def _library():
    """{uuid: card} of the solids in FreeCAD's library, read once."""
    if "lib" in _cache:
        return _cache["lib"]
    out = {}
    mm = _manager()
    if mm is not None:
        try:
            mats = mm.Materials
        except Exception:
            mats = {}
        for uid, m in mats.items():
            try:
                d = str(getattr(m, "Directory", "") or "")
                if any(d.startswith(s) or f"/{s}" in d for s in SKIP_DIRS):
                    continue
                rho = _q(m, "Density", "g/cm^3")
                E = _q(m, "YoungsModulus", "MPa")
                if rho is None and E is None:
                    continue
                out[uid] = {
                    "id": uid,
                    "name": m.Name,
                    "category": d.replace("Standard/", "").strip("/") or "Library",
                    "library": getattr(m, "LibraryName", ""),
                    "density": rho,
                    "E": E,
                    "nu": _q(m, "PoissonRatio", ""),
                    "yield": _q(m, "YieldStrength", "MPa"),
                    "uts": _q(m, "UltimateTensileStrength", "MPa"),
                    "k": _q(m, "ThermalConductivity", "W/m/K"),
                    "tags": list(getattr(m, "Tags", []) or []),
                    "about": (getattr(m, "Description", "") or "")[:160],
                    "source": "FreeCAD material library" + (f" ({getattr(m, 'URL', '')})" if getattr(m, "URL", "") else ""),
                }
            except Exception:
                continue
    _cache["lib"] = out
    return out


def filament_card(key):
    """A printing filament's card by its key."""
    c = _fil.card(key)
    if c is None:
        c = {"id": key, "name": key.upper(), "category": "Printing filament", "density": DENSITY.get(key), "E": None, "nu": None, "yield": None, "uts": None, "k": None, "softens": None}
    c["source"] = FILAMENT_SOURCE
    return c


def defs(doc):
    """The document's custom materials, by id."""
    return store.read(doc, "materialDefs", {})


def card(doc, mid):
    """A material's figures by id, or None."""
    if mid is None:
        return None
    key = str(mid)
    if key.lower() in DENSITY:
        return filament_card(key.lower())
    if key.startswith("custom:"):
        d = defs(doc).get(key)
        return dict(d) if d else None
    lib = _library()
    if key in lib:
        return lib[key]
    # A card's name works as well as its id ("Aluminum-6061-T6"), case and
    # spaces aside, as material_set and the drawings take it.
    norm = key.strip().lower().replace(" ", "")
    for c in lib.values():
        if str(c.get("name", "")).lower().replace(" ", "") == norm:
            return c
    for k, d in defs(doc).items():
        if str(d.get("name", "")).lower().replace(" ", "") == norm:
            return dict(d)
    return None


def of_body(doc, label, default="pla"):
    """The body's material card, and whether it was set or assumed."""
    mid = store.materials(doc).get(label)
    c = card(doc, mid)
    if c:
        return c, True
    return (filament_card(default), False) if default else (None, False)


def _brief(c):
    """A card as a list shows it: id, name, category, density, E and yield where it has them."""
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in c.items() if k in ("id", "name", "category", "density", "E", "yield") and v is not None}


def search_words(text):
    """The words of a search, lower case: every one must be found."""
    return [w for w in re.split(r"\s+", (text or "").lower()) if w]


def all_cards(doc):
    """Every material there is to choose from, in the order they are listed:
    the printing filaments, FreeCAD's library by category and name, then the
    document's custom ones."""
    cards = [filament_card(k) for k in DENSITY] + sorted(_library().values(), key=lambda c: (c["category"], c["name"]))
    return cards + [dict(v) for v in defs(doc).values()]


def haystack(c):
    """What a search looks through on a card: its id, name, category, tags and description."""
    return " ".join(str(x) for x in (c["id"], c["name"], c["category"], " ".join(c.get("tags", [])), c.get("about", ""))).lower()


def custom_id(name):
    """A custom material's id from its name: custom:<name>, lower case, dashes for what is neither letter nor digit."""
    return "custom:" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def library_id(mid):
    """The library card that goes on an object's ShapeMaterial for a material:
    the card itself, the library's card of a filament's name (pla, abs), or None."""
    lib = _library()
    return mid if mid in lib else next((u for u, x in lib.items() if x["name"] == LIB_NAME.get(mid)), None)


def shape_material(o, lib_uuid):
    """FreeCAD's library card put on the object's ShapeMaterial (what its own
    Material panel shows), where there is a card and this FreeCAD has the
    property: whether it was set."""
    if lib_uuid and hasattr(o, "ShapeMaterial") and _manager() is not None:
        try:
            o.ShapeMaterial = _manager().getMaterial(lib_uuid)
            return True
        except Exception:
            return False
    return False


def masses(session, bodies, density):
    """{body: grams}: volume × density (g/cm³), as measure_mass will answer
    (solid through). A body whose solids cannot be read is left out."""
    mass = {}
    for b in bodies:
        try:
            mass[b] = round(sum(x.Volume for x in session.body(b).Shape.Solids) * float(density) / 1000.0, 3)
        except Exception:  # noqa: BLE001
            pass
    return mass


def tools(session):
    """The material tools are data (agentlink/data/tools.json, group
    "material"): what their entries call by name is here (docs/data-tools.md)."""
    s = session
    helpers = {"doc": lambda: s.doc, "snapshot": lambda tool: s.snapshot(tool), "body": lambda ref: s.body(ref),
               "read_materials": lambda: store.materials(s.doc), "write": lambda name, value: store.write(s.doc, name, value),
               # the cards
               "card": lambda mid: card(s.doc, mid), "defs": lambda: defs(s.doc), "brief": _brief, "all_cards": lambda: all_cards(s.doc), "haystack": haystack,
               "search_words": search_words, "custom_id": custom_id, "has_library": lambda: _manager() is not None, "DENSITY": DENSITY,
               # FreeCAD's ShapeMaterial, the add-on that owns materials, the mass
               "library_id": library_id, "shape_material": shape_material, "owner": lambda bodies, material: _owner(s.doc, bodies, material),
               "masses": lambda bodies, density: masses(s, bodies, density)}
    return runners.tools(GROUP, s, helpers)
