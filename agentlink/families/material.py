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

from .. import store
from ..protocol import Tool, ToolError
from .. import materials as _fil
from ..materials import DENSITY

from ..tools import obj


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
    if "mm" not in _cache:
        try:
            import Materials

            _cache["mm"] = Materials.MaterialManager()
        except Exception:  # an old FreeCAD: the filament table alone
            _cache["mm"] = None
    return _cache["mm"]


def _q(m, name, unit):
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
    c = _fil.card(key)
    if c is None:
        c = {"id": key, "name": key.upper(), "category": "Printing filament", "density": DENSITY.get(key), "E": None, "nu": None, "yield": None, "uts": None, "k": None, "softens": None}
    c["source"] = FILAMENT_SOURCE
    return c


def defs(doc):
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
    return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in c.items() if k in ("id", "name", "category", "density", "E", "yield") and v is not None}


def tools(session):
    s = session

    def material_list(a):
        words = [w for w in re.split(r"\s+", (a.get("words") or "").lower()) if w]
        cat = (a.get("category") or "").lower()
        cards = [filament_card(k) for k in DENSITY] + sorted(_library().values(), key=lambda c: (c["category"], c["name"]))
        cards += [dict(v) for v in defs(s.doc).values()]
        hits = []
        for c in cards:
            hay = " ".join(str(x) for x in (c["id"], c["name"], c["category"], " ".join(c.get("tags", [])), c.get("about", ""))).lower()
            if cat and cat not in c["category"].lower():
                continue
            if all(w in hay for w in words):
                hits.append(c)
        # Those named by the words first, then those that only mention them.
        hits.sort(key=lambda c: not all(w in (c["id"] + " " + c["name"]).lower() for w in words))
        limit = a.get("limit", 20)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ToolError("invalid_input", "limit: how many to list, 1 … 500 (20 by default).")
        cats = sorted({c["category"] for c in cards})
        out = {"found": len(hits), "materials": [_brief(c) for c in hits[:limit]], "categories": cats}
        if len(hits) > limit:
            out["more"] = len(hits) - limit
        if _manager() is None:
            out["note"] = "FreeCAD's material library is not in this build: the printing filaments only."
        if not hits:
            out["note"] = "Nothing matches: fewer words (every word must be found), or a category from categories." + (" FreeCAD's library is not in this build: the printing filaments only." if _manager() is None else "")
        return out

    def material_get(a):
        c = card(s.doc, a.get("id"))
        if c is None:
            raise ToolError("not_found", f"material {a.get('id')!r}: no such id or name — material_list {{ words }} finds one (a filament key such as pla, a library card's id or exact name, or custom:<name>).")
        out = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in c.items() if v not in (None, "", [])}
        out["units"] = "density g/cm³; E, yield, uts MPa"
        missing = [k for k in ("density", "E", "nu", "yield") if c.get(k) is None]
        if missing:
            out["missing"] = missing
        out["note"] = TYPICAL
        return out

    def material_set(a):
        if a.get("bodies") is not None and not (isinstance(a["bodies"], list) and all(isinstance(b, str) for b in a["bodies"])):
            raise ToolError("invalid_input", "bodies: a list of body names or labels (the one body when left out).")
        bodies = [s.body(b).Label for b in (a.get("bodies") or [None])]
        custom = a.get("custom")
        if custom is not None and not isinstance(custom, dict):
            raise ToolError("invalid_input", "custom: { name, density g/cm³, youngsMPa, yieldMPa, utsMPa, poisson, conductivity, softensC, source }.")
        if custom and a.get("id"):
            raise ToolError("invalid_input", "id or custom, not both: id names a material there is, custom gives a new one's figures.")
        if custom:
            name = str(custom.get("name") or "").strip()
            if not name:
                raise ToolError("invalid_input", "custom.name: required — what the material is called.")
            rho = custom.get("density")
            if not isinstance(rho, (int, float)) or not 0.01 < rho < 25:
                raise ToolError("invalid_input", "custom.density: g/cm³, 0.01 to 25.")
            for k in ("youngsMPa", "yieldMPa", "utsMPa", "poisson", "conductivity", "softensC"):
                if k in custom and (isinstance(custom[k], bool) or not isinstance(custom[k], (int, float))):
                    raise ToolError("invalid_input", f"custom.{k}: a number (youngsMPa, yieldMPa, utsMPa in MPa; conductivity W/(m·K); softensC °C).")
            known = {"name", "density", "youngsMPa", "yieldMPa", "utsMPa", "poisson", "conductivity", "softensC", "source"}
            odd = sorted(k for k in custom if k not in known)
            if odd:
                raise ToolError("invalid_input", f"custom.{odd[0]}: not a figure kept here — custom takes {', '.join(sorted(known))}.")
            mid = "custom:" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            c = {"id": mid, "name": name, "category": "Custom", "density": float(rho), "E": custom.get("youngsMPa"), "nu": custom.get("poisson", 0.35 if custom.get("youngsMPa") else None), "yield": custom.get("yieldMPa"), "uts": custom.get("utsMPa"),
                 "k": custom.get("conductivity"), "softens": custom.get("softensC"), "source": custom.get("source") or "given by the person"}
            d = defs(s.doc)
            d[mid] = c
            store.write(s.doc, "materialDefs", d)
        else:
            mid = a.get("id")
            if not mid:
                raise ToolError("invalid_input", "id (from material_list: a filament key, a library card's id or name) or custom { name, density g/cm³, youngsMPa, yieldMPa }.")
            if str(mid).lower() in DENSITY:
                mid = str(mid).lower()
            c = card(s.doc, mid)
            if c is None:
                raise ToolError("not_found", f"material {mid!r}: no such id or name — material_list {{ words }} finds one; custom {{ name, density }} gives one of your own.")
        # The add-on that owns materials (its "material_set" service) keeps
        # the record and FreeCAD's material for what it knows (printing
        # filaments); a library card or a custom one stays here.
        if not custom:
            got = _owner(s.doc, bodies, c["id"])
            if got is not None:
                s.snapshot("material_set")
                return {"bodies": bodies, "material": _brief(c), **got}
        mats = store.materials(s.doc)
        shape_mat = {}
        lib_uuid = c["id"] if c["id"] in _library() else next((u for u, x in _library().items() if x["name"] == LIB_NAME.get(c["id"])), None)
        for b in bodies:
            mats[b] = c["id"]
            o = s.body(b)
            if lib_uuid and hasattr(o, "ShapeMaterial") and _manager() is not None:
                try:
                    o.ShapeMaterial = _manager().getMaterial(lib_uuid)
                    shape_mat[b] = True
                except Exception:
                    shape_mat[b] = False
            else:
                shape_mat[b] = False
        store.write(s.doc, "materials", mats)
        if any(shape_mat.values()):
            # A new ShapeMaterial leaves the object marked for recompute (the next
            # call's health said "not recomputed yet"): brought up to date here.
            s.doc.recompute()
        s.snapshot("material_set")
        out = {"bodies": bodies, "material": _brief(c), "shapeMaterial": shape_mat}
        if c.get("density"):
            # Volume × density, as measure_mass will answer (solid through).
            mass = {}
            for b in bodies:
                try:
                    mass[b] = round(sum(x.Volume for x in s.body(b).Shape.Solids) * float(c["density"]) / 1000.0, 3)
                except Exception:  # noqa: BLE001
                    pass
            if mass:
                out["mass_g"] = mass
        if not all(shape_mat.values()):
            out["shapeMaterialNote"] = "Not every body's ShapeMaterial was set: only FreeCAD library cards go there; the material is kept with the document either way."
        if c["id"] not in DENSITY:
            out["note"] = "Add-ons for printing read the filament keys only (pla, petg, abs, asa, pa6-cf, tpu-95a); measure_mass and fea_* read this material."
        missing = [k for k in ("E", "yield") if c.get(k) is None]
        if missing:
            out["missing"] = missing
        return out

    def material_clear(a):
        mats = store.materials(s.doc)
        if a.get("bodies") is not None and not (isinstance(a["bodies"], list) and all(isinstance(b, str) for b in a["bodies"])):
            raise ToolError("invalid_input", "bodies: a list of body names or labels (every body with a material when left out).")
        bodies = [s.body(b).Label for b in a["bodies"]] if a.get("bodies") else list(mats)
        got = _owner(s.doc, bodies, None)
        if got is not None:
            s.snapshot("material_clear")
            return {"cleared": bodies, **got}
        cleared = [b for b in bodies if mats.pop(b, None) is not None]
        store.write(s.doc, "materials", mats)
        s.snapshot("material_clear")
        return {"cleared": cleared, "materials": mats, **({"hadNone": [b for b in bodies if b not in cleared]} if len(cleared) != len(bodies) else {}),
                "note": "The objects' ShapeMaterial (what FreeCAD's own Material panel shows) is left as it was; custom materials stay listed for material_set."}

    return [
        Tool(
            "material_list",
            "Find materials: words (every word must be in the id, name, category, tags or description) and category (part of one: \"Printing filament\", \"Metal/Steel\", \"Thermoplast\" …; the reply's categories lists them). The printing filaments (pla, petg, abs, asa, pa6-cf, tpu-95a) come first, then FreeCAD's material library (its cards with a density or stiffness; appearance-only, fluid and pattern cards left out), then this document's custom ones. Reply: found, materials [{ id, name, category, density g/cm³, E and yield MPa where the card has them }] (limit 20), more. A library card's id is its UUID; its exact name works wherever an id is asked. Changes nothing.",
            obj({"words": {"type": "string"}, "category": {"type": "string"}, "limit": {"type": "integer"}}),
            material_list,
        ),
        Tool(
            "material_get",
            "One material's figures by id (a filament key, a library card's UUID or exact name, custom:<name>): density g/cm³, E (Young's modulus) MPa, nu (Poisson's ratio), yield and uts MPa, k W/(m·K) where the card has them, source, and missing (which of density, E, nu, yield the card lacks — fea needs E and yield, mass needs density). Library and filament figures are typical — a part that must not fail needs the supplier's. Changes nothing.",
            obj({"id": {"type": "string"}}, ["id"]),
            material_get,
        ),
        Tool(
            "material_set",
            "Say what bodies are made of: id from material_list (or a library card's exact name), or custom { name, density g/cm³ (required), youngsMPa, yieldMPa, utsMPa, poisson, conductivity W/(m·K), softensC, source } for the supplier's figures (kept as custom:<name>). Kept with the document by the body's label (measure_mass, fea_* and drawings read it there); a library card also goes on the object's ShapeMaterial, which FreeCAD's own Material panel shows (shapeMaterial says per body). An installed add-on that owns materials keeps those it knows (printing filaments), marked from. bodies: the one body when left out. Reply: material, mass_g (volume × density, solid through), missing (E / yield the card lacks). Trap: object_rename does not carry it to the new label.",
            obj({"bodies": {"type": "array", "items": {"type": "string"}}, "id": {"type": "string"}, "custom": {"type": "object"}}),
            material_set,
            changes=True,
        ),
        Tool(
            "material_clear",
            "Forget what bodies are made of (bodies; every body with a material when left out). measure_mass then asks for a material again (a printed part is taken as PLA and says so); strength studies assume PLA and say so. FreeCAD's own ShapeMaterial on the object is left as it was. Reply: cleared, materials (what is still recorded).",
            obj({"bodies": {"type": "array", "items": {"type": "string"}}}),
            material_clear,
            changes=True,
        ),
    ]
