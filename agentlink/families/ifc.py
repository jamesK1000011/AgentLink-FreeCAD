# SPDX-License-Identifier: LGPL-2.1-or-later
# IFC files edited in place, as BIM's native IFC mode does it: the file is
# the model. Open one, find elements by class, name, storey or property,
# change their attributes, property sets, materials, containment and
# classification, remove them, compare two files, and save — every change
# made through IfcOpenShell's own API, so GlobalIds, relationships and
# everything not touched stay as they were. The agent never needs the
# FreeCAD objects for this; bim_import brings a file in to look at.

import os

from .. import paths
from .. import runners
from ..protocol import ToolError, bad

try:
    import ifcopenshell
    import ifcopenshell.api
    import ifcopenshell.util.element as uel
except ImportError:  # the family is left out without IfcOpenShell
    raise

GROUP = "bim"
INFO = "IFC edited in place: open, find, change attributes / property sets / materials / storeys / classification, remove, diff, save."


def run(f, usage, **kw):
    """One of IfcOpenShell's API usages ("pset.edit_pset") on the open file."""
    return ifcopenshell.api.run(usage, f, **kw)


def storey_of(el):
    """The name of the storey (or other container) an element is in, or None."""
    c = uel.get_container(el)
    return c.Name if c is not None else None


def psets_of(el, qto=False):
    """An element's property sets (qto: its quantity sets instead), { set: { property: value } }."""
    try:
        d = uel.get_psets(el, qtos_only=qto, psets_only=not qto)
    except TypeError:
        d = uel.get_psets(el)
    return {k: {kk: vv for kk, vv in v.items() if kk != "id"} for k, v in d.items()}


def material_of(el):
    """An element's material as the tools answer it: a name, or a layer set's "name thickness" list."""
    m = uel.get_material(el)
    if m is None:
        return None
    if m.is_a("IfcMaterial"):
        return m.Name
    if m.is_a("IfcMaterialLayerSetUsage"):
        m = m.ForLayerSet
    if m.is_a("IfcMaterialLayerSet"):
        return [f"{ly.Material.Name} {ly.LayerThickness:g}" for ly in m.MaterialLayers]
    return getattr(m, "Name", None) or m.is_a()


def row(el, full=False):
    """An element as the tools answer it: id, class, name, type, storey; full: description, material, psets, quantities and classification too."""
    r = {"id": el.GlobalId, "class": el.is_a(), "name": el.Name}
    if getattr(el, "ObjectType", None):
        r["type"] = el.ObjectType
    st = storey_of(el)
    if st:
        r["storey"] = st
    if full:
        r["description"] = getattr(el, "Description", None)
        r["material"] = material_of(el)
        r["psets"] = psets_of(el)
        q = psets_of(el, qto=True)
        if q:
            r["quantities"] = q
        cl = classifications(el)
        if cl:
            r["classification"] = cl
    return r


def real_classification(f, el, c):
    """An IfcClassificationReference on the element (the system made once):
    True if IfcOpenShell's API took it."""
    system = str(c.get("system") or "Classification")
    cl = next((x for x in f.by_type("IfcClassification") if x.Name == system), None)
    try:
        if cl is None:
            cl = run(f, "classification.add_classification", classification=system)
        try:
            run(f, "classification.add_reference", products=[el], identification=str(c.get("code", "")), name=str(c.get("title", "")), classification=cl)
        except TypeError:
            run(f, "classification.add_reference", product=el, identification=str(c.get("code", "")), name=str(c.get("title", "")), classification=cl)
        return True
    except Exception:
        return False


def classifications(el):
    """The classification references on an element: [{ system, code, title }]."""
    out = []
    for rel in getattr(el, "HasAssociations", []) or []:
        if rel.is_a("IfcRelAssociatesClassification"):
            r = rel.RelatingClassification
            src = getattr(r, "ReferencedSource", None)
            out.append({"system": getattr(src, "Name", None), "code": getattr(r, "Identification", None) or getattr(r, "ItemReference", None), "title": r.Name})
    return out


def differences(ea, eb):
    """What differs between an element in two files: { what: [old, new] }
    over its attributes (Name, Description, ObjectType, Tag), each
    property of each set, its material and its storey."""
    d = {}
    for attr in ("Name", "Description", "ObjectType", "Tag"):
        va, vb = getattr(ea, attr, None), getattr(eb, attr, None)
        if va != vb:
            d[attr] = [va, vb]
    pa_, pb_ = psets_of(ea), psets_of(eb)
    for ps in set(pa_) | set(pb_):
        for k in set(pa_.get(ps, {})) | set(pb_.get(ps, {})):
            va, vb = pa_.get(ps, {}).get(k), pb_.get(ps, {}).get(k)
            if va != vb:
                d[f"{ps}.{k}"] = [va, vb]
    if material_of(ea) != material_of(eb):
        d["material"] = [material_of(ea), material_of(eb)]
    if storey_of(ea) != storey_of(eb):
        d["storey"] = [storey_of(ea), storey_of(eb)]
    return d


def tools(session):
    """The ifc_ tools are data (agentlink/data/tools.json, "family": "ifc";
    run by agentlink/runners.py's steps runner): each entry has the tool's
    words, its checks with their refusals, the order of its steps and its
    answer. What is here is what those entries call by name
    (docs/data-tools.md)."""
    s = session

    def model():
        """The IFC file open in this session: { file, path, edits }."""
        m = getattr(s, "_agentlink_ifc", None)
        if not m:
            raise ToolError("invalid_state", "No IFC file is open in this session: ifc_open { path } first (bim_export writes one from the model).")
        return m

    def where(p):
        """A path, in the session's output folder when relative."""
        return paths.local(s, p)

    def select(f, a):
        """The elements a call's filters choose, as ifc_find takes them:
        ids (GlobalIds), or class (every product when left out) narrowed by
        name (contains), storey (exact) and where { "Pset.Property": value }."""
        if a.get("ids"):
            out = []
            for g in a["ids"]:
                try:
                    out.append(f.by_guid(g))
                except Exception:
                    raise ToolError("not_found", f"ids: {g!r} is no element's GlobalId in the open file (ifc_find lists them as id; they are 22 characters, not names).") from None
            return out
        cls = a.get("class") or "IfcProduct"
        try:
            els = f.by_type(cls)
        except Exception:
            raise bad(f"class {cls!r}: not an IFC class in {f.schema}. Classes are written IfcWall, IfcSlab, IfcBeam, IfcWindow, IfcSpace …; ifc_open lists those in the file.") from None
        if a.get("name"):
            n = str(a["name"]).lower()
            els = [e for e in els if n in str(e.Name or "").lower()]
        if a.get("storey"):
            els = [e for e in els if (storey_of(e) or "").lower() == str(a["storey"]).lower()]
        for k, v in (a.get("where") or {}).items():
            if "." not in k:
                raise bad(f"where.{k}: \"Pset_WallCommon.IsExternal\" — a property set, a dot, a property.")
            ps, pn = k.split(".", 1)
            els = [e for e in els if str(psets_of(e).get(ps, {}).get(pn)) == str(v)]
        return els

    def opened(f, path):
        """The file kept as the one open in this session, no edits yet."""
        s._agentlink_ifc = {"file": f, "path": path, "edits": 0}

    # What the tools' entries (agentlink/data/tools.json, "family": "ifc") call by name.
    # IfcOpenShell's own are reached when called, not here.
    helpers = {"where": where, "isfile": lambda p: os.path.isfile(p), "dirname": lambda p: os.path.dirname(p), "make_folder": lambda p: os.makedirs(p, exist_ok=True),
               "file_stem": lambda p: os.path.splitext(os.path.basename(p))[0], "file_size": lambda p: os.path.getsize(p),
               # IfcOpenShell's own
               "ifc_file": lambda path: ifcopenshell.open(path), "api": lambda f, usage, **kw: run(f, usage, **kw), "get_pset": lambda el, name: uel.get_pset(el, name),
               # the family's
               "model": model, "opened": opened, "select": select, "row": row, "real_classification": real_classification, "differences": differences,
               "both": lambda ia, ib: ia.keys() & ib.keys()}
    return runners.tools(GROUP, s, helpers, family="ifc")
