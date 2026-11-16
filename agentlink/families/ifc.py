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
from ..protocol import Tool, ToolError, bad
from ..tools import obj

try:
    import ifcopenshell
    import ifcopenshell.api
    import ifcopenshell.util.element as uel
except ImportError:  # the family is left out without IfcOpenShell
    raise

GROUP = "bim"
INFO = "IFC edited in place: open, find, change attributes / property sets / materials / storeys / classification, remove, diff, save."


def run(f, usage, **kw):
    return ifcopenshell.api.run(usage, f, **kw)


def storey_of(el):
    c = uel.get_container(el)
    return c.Name if c is not None else None


def psets_of(el, qto=False):
    try:
        d = uel.get_psets(el, qtos_only=qto, psets_only=not qto)
    except TypeError:
        d = uel.get_psets(el)
    return {k: {kk: vv for kk, vv in v.items() if kk != "id"} for k, v in d.items()}


def material_of(el):
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
    out = []
    for rel in getattr(el, "HasAssociations", []) or []:
        if rel.is_a("IfcRelAssociatesClassification"):
            r = rel.RelatingClassification
            src = getattr(r, "ReferencedSource", None)
            out.append({"system": getattr(src, "Name", None), "code": getattr(r, "Identification", None) or getattr(r, "ItemReference", None), "title": r.Name})
    return out


def tools(session):
    s = session

    def model():
        m = getattr(s, "_agentlink_ifc", None)
        if not m:
            raise ToolError("invalid_state", "No IFC file is open in this session: ifc_open { path } first (bim_export writes one from the model).")
        return m

    def where(p):
        return paths.local(s, p)

    def ifc_open(a):
        p = a.get("path")
        if not p:
            raise bad("path: an .ifc file.")
        path = where(p)
        if not os.path.isfile(path):
            raise ToolError("not_found", f"path {p!r}: no such file (a relative path is looked for in the session's output folder, where bim_export writes).")
        try:
            f = ifcopenshell.open(path)
        except Exception as e:
            raise bad(f"{p}: not an IFC file IfcOpenShell can read ({e}).")
        s._agentlink_ifc = {"file": f, "path": path, "edits": 0}
        counts = {}
        for el in f.by_type("IfcProduct"):
            counts[el.is_a()] = counts.get(el.is_a(), 0) + 1
        proj = (f.by_type("IfcProject") or [None])[0]
        return {"path": path, "schema": f.schema, "project": proj.Name if proj else None,
                "storeys": [{"name": x.Name, "elevation": getattr(x, "Elevation", None), "id": x.GlobalId} for x in f.by_type("IfcBuildingStorey")],
                "classes": dict(sorted(counts.items(), key=lambda kv: -kv[1])), "elements": sum(counts.values()),
                "next": "ifc_find to list elements; ifc_edit to change them; ifc_save writes the file (a copy unless overwrite)."}

    def select(f, a):
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

    def ifc_find(a):
        m = model()
        els = select(m["file"], a)
        lim = int(a.get("limit", 50))
        return {"count": len(els), "elements": [row(e, a.get("detail")) for e in els[:lim]], **({"more": len(els) - lim} if len(els) > lim else {})}

    def ifc_edit(a):
        m = model()
        f = m["file"]
        els = select(f, a)
        if not els:
            raise ToolError("not_found", "No element matches: ifc_find with the same filters shows what is there.")
        if not any(a.get(k) for k in ("attributes", "properties", "material", "storey_to", "classification")):
            raise bad("Nothing to change: give attributes, properties, material, storey_to or classification (ifc_find only looks).")
        if not (a.get("ids") or a.get("class") or a.get("name") or a.get("storey") or a.get("where")):
            raise bad("Say which elements: ids, class, name, storey or where (as ifc_find takes them); with none of them every product in the file would be changed.")
        if len(els) > int(a.get("max", 200)):
            raise bad(f"{len(els)} elements match: narrow it, or max: {len(els)} to change them all.")
        if a.get("classification") is not None and not (isinstance(a["classification"], dict) and a["classification"].get("code")):
            raise bad("classification: { system (e.g. \"Uniclass 2015\"), code (e.g. \"Ss_25_10\"), title }; code is needed.")
        done = {"attributes": 0, "properties": 0, "material": 0, "storey": 0, "classification": 0}
        attrs = a.get("attributes") or {}
        props = a.get("properties") or {}
        grouped = {}
        for k, v in props.items():
            if "." not in k:
                raise bad(f"properties.{k}: \"Pset_WallCommon.FireRating\" — a set, a dot, a property.")
            ps, pn = k.split(".", 1)
            grouped.setdefault(ps, {})[pn] = v
        mat = None
        if a.get("material"):
            mat = next((x for x in f.by_type("IfcMaterial") if x.Name == a["material"]), None) or run(f, "material.add_material", name=str(a["material"]))
        storey = None
        if a.get("storey_to"):
            storey = next((x for x in f.by_type("IfcBuildingStorey") if x.Name == a["storey_to"]), None)
            if storey is None:
                raise ToolError("not_found", f"storey_to {a['storey_to']!r}: the file's storeys are {', '.join(str(x.Name) for x in f.by_type('IfcBuildingStorey')) or 'none'} (by name, exactly).")
        for el in els:
            if attrs:
                try:
                    run(f, "attribute.edit_attributes", product=el, attributes=attrs)
                except Exception as e:
                    raise bad(f"attributes on {el.is_a()}: {e}. Attribute names are IFC's own (Name, Description, ObjectType, Tag …); anything else is a property: properties {{ \"Pset.Name\": value }}.") from None
                done["attributes"] += 1
            for ps, vals in grouped.items():
                existing = uel.get_pset(el, ps)
                if existing:
                    pset = f.by_id(existing["id"])
                else:
                    pset = run(f, "pset.add_pset", product=el, name=ps)
                run(f, "pset.edit_pset", pset=pset, properties=vals)
                done["properties"] += 1
            if mat is not None:
                try:
                    run(f, "material.unassign_material", products=[el])
                except Exception:
                    pass
                try:
                    run(f, "material.assign_material", products=[el], material=mat)
                except TypeError:
                    run(f, "material.assign_material", product=el, material=mat)
                done["material"] += 1
            if storey is not None:
                try:
                    run(f, "spatial.assign_container", products=[el], relating_structure=storey)
                except TypeError:
                    run(f, "spatial.assign_container", product=el, relating_structure=storey)
                done["storey"] += 1
            if a.get("classification"):
                c = a["classification"]
                if real_classification(f, el, c):
                    done["classification"] += 1
                else:
                    got = uel.get_pset(el, "AgentLink_Classification")
                    pset = f.by_id(got["id"]) if got else run(f, "pset.add_pset", product=el, name="AgentLink_Classification")
                    run(f, "pset.edit_pset", pset=pset, properties={"System": str(c.get("system", "")), "Code": str(c.get("code", "")), "Title": str(c.get("title", ""))})
                    done["classification"] += 1
                    done["classificationAs"] = "property set (this IfcOpenShell could not add a classification reference)"
        m["edits"] += 1
        return {"changed": len(els), "done": {k: v for k, v in done.items() if v}, "elements": [row(e) for e in els[:20]],
                "note": "In the open file only: ifc_save writes it."}

    def ifc_remove(a):
        m = model()
        f = m["file"]
        if not a.get("ids"):
            raise bad("ids: the GlobalIds to remove (ifc_find lists them as id); removal goes by id only, never by class or name.")
        els = select(f, {"ids": a["ids"]})
        names = [row(e) for e in els]
        for e in els:
            run(f, "root.remove_product", product=e)
        m["edits"] += 1
        return {"removed": names, "note": "Its openings, relationships and representation went with it; ifc_save writes the file."}

    def ifc_save(a):
        m = model()
        src = m["path"]
        if a.get("overwrite"):
            dst = src
        else:
            stem = os.path.splitext(os.path.basename(src))[0]
            dst = where(a.get("path") or f"{stem}_edited.ifc")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        m["file"].write(dst)
        return {"path": dst, "bytes": os.path.getsize(dst), "edits": m["edits"], "overwrote": dst == src}

    def ifc_diff(a):
        pa, pb = a.get("a"), a.get("b")
        if not (pa and pb):
            raise bad("a and b: two IFC files (paths), the old and the new.")
        files = []
        for key, p in (("a", pa), ("b", pb)):
            path = where(p)
            if not os.path.isfile(path):
                raise ToolError("not_found", f"{key} {p!r}: no such file (a relative path is looked for in the session's output folder).")
            try:
                files.append(ifcopenshell.open(path))
            except Exception as e:
                raise bad(f"{key} {p!r}: not an IFC file IfcOpenShell can read ({e}).") from None
        fa, fb = files
        ia = {e.GlobalId: e for e in fa.by_type("IfcProduct")}
        ib = {e.GlobalId: e for e in fb.by_type("IfcProduct")}
        added = [row(ib[g]) for g in ib.keys() - ia.keys()]
        gone = [row(ia[g]) for g in ia.keys() - ib.keys()]
        changed = []
        for g in ia.keys() & ib.keys():
            ea, eb = ia[g], ib[g]
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
            if d:
                changed.append({"id": g, "class": eb.is_a(), "name": eb.Name, "changes": d})
        lim = int(a.get("limit", 60))
        return {"added": added[:lim], "removed": gone[:lim], "changed": changed[:lim],
                "counts": {"added": len(added), "removed": len(gone), "changed": len(changed), "same": len(ia.keys() & ib.keys()) - len(changed)},
                "note": "Geometry changes are not compared, only data: bim_import both and view_render to see shapes."}

    s_ = {"type": "string"}
    sel = {"ids": {"type": "array", "items": s_}, "class": s_, "name": s_, "storey": s_, "where": {"type": "object"}}
    return [
        Tool("ifc_open", "Open an IFC file (path) to edit in place with IfcOpenShell: nothing is added to the FreeCAD document, and GlobalIds and all that is untouched stay as they are. One file at a time. Answers schema, storeys (elevation in the file's unit), classes (counts). The ifc_ tools exist only when FreeCAD has IfcOpenShell.",
             obj({"path": s_}, ["path"]), ifc_open),
        Tool("ifc_find", "Find elements in the open IFC, filters combined: class (IfcWall …; every product when left out), name (contains), storey (exact name), where { \"Pset_WallCommon.IsExternal\": true }, or ids (GlobalIds). limit (50); detail: true adds psets, quantities, material. Answers elements [{ id, class, name, storey }].",
             obj({**sel, "detail": {"type": "boolean"}, "limit": {"type": "integer"}}), ifc_find),
        Tool("ifc_edit", "Change elements of the open IFC, chosen by ifc_find's filters (one at least): attributes { Name, Description, ObjectType, Tag }, properties { \"Pset_WallCommon.FireRating\": \"REI60\" }, material (by name), storey_to (a storey's name), classification { system, code, title }. Over max (200) matches is refused. In memory until ifc_save.",
             obj({**sel, "attributes": {"type": "object"}, "properties": {"type": "object"}, "material": s_, "storey_to": s_, "classification": {"type": "object"}, "max": {"type": "integer"}}), ifc_edit),
        Tool("ifc_remove", "Remove elements from the open IFC by GlobalId (ids, from ifc_find), with their openings and relationships. In memory until ifc_save; outside undo.", obj({"ids": {"type": "array", "items": s_}}, ["ids"]), ifc_remove),
        Tool("ifc_save", "Write the open IFC with its edits: path (default <name>_edited.ifc in the output folder), or overwrite: true to write over the file it came from.",
             obj({"path": s_, "overwrite": {"type": "boolean"}}), ifc_save),
        Tool("ifc_diff", "Compare two IFC files (a old, b new) by GlobalId: elements added, removed and changed (attributes, property sets, material, storey; not geometry). limit (60). Changes nothing.",
             obj({"a": s_, "b": s_, "limit": {"type": "integer"}}, ["a", "b"]), ifc_diff),
    ]
