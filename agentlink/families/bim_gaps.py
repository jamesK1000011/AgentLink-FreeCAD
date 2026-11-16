# SPDX-License-Identifier: LGPL-2.1-or-later
# BIM's remaining commands, headless: generic components, clones and
# unclones, external references, structural systems, pipe connectors, panel
# cut sheets and nesting, the IFC B-rep flag, 2D views of the levels, image
# planes, the objects library, re-extrusion from a face, rewiring, glue,
# trash and reordering a group's children.

import glob
import os

import FreeCAD
import Part

import Arch  # the family is left out without BIM

from .. import runners
from .. import geometry as geo
from ..protocol import Tool, ToolError, bad
from ..tools import obj
from . import picks
from .bim import headless_call, ifc_set

GROUP = "bim_gaps"
INFO = "BIM components, clones, references, structural systems, pipe connectors, panel cuts and sheets, nesting, IFC B-rep flag, 2D level views, image planes, library, re-extrude, rewire, glue, trash, reorder."

V = FreeCAD.Vector


def file(path):
    """The file at path (~ opened out), or None when there is none."""
    p = os.path.expanduser(path or "")
    return p if os.path.isfile(p) else None


def tools(s):
    def d():
        if s.doc is None:
            raise ToolError("invalid_state", "No document open: doc_new first.")
        return s.doc

    def objs(refs, what="objects"):
        refs = picks.ref_list(refs, f"{what}: one or more objects by label.")
        return [picks.find(d(), r, what) for r in refs]

    def done(tool, out):
        return picks.finish(s, tool, out, doc=d(), step=False)

    def named(o, name):
        if name:
            o.Label = s.unique(name, o)
        return o

    def reading(o):
        d().recompute()
        sh = getattr(o, "Shape", None)
        if sh is None or sh.isNull():
            return {}
        return {"volume": round(sh.Volume, 3) if sh.Solids else None, "box": geo.box_json(sh, 3)["size"]}

    def bim_component(a):
        kind = a.get("kind", "component")
        if kind == "component":
            base = picks.shaped(d(), a.get("from"), "from") if a.get("from") else None
            o = headless_call(Arch.makeComponent, base)
            if a.get("ifcType"):
                ifc_set(o, a["ifcType"])
        elif kind == "clone":
            src = picks.find(d(), a.get("from"), "from")
            o = headless_call(Arch.cloneComponent, src)
            if picks.placed(a):
                o.Placement = picks.placement(a)
        elif kind == "unclone":
            o = picks.find(d(), a.get("from"), "from")
            src = getattr(o, "CloneOf", None)
            if src is None:
                raise ToolError("invalid_state", f"{o.Label} is not a clone (it has no CloneOf): kind clone {{ from }} makes one.")
            pl = FreeCAD.Placement(o.Placement)
            o.CloneOf = None
            skip = {"Objects", "CloneOf", "ExpressionEngine", "HorizontalArea", "Area", "VerticalArea", "PerimeterLength", "Placement", "Proxy", "Shape", "Label", "Label2"}
            for p in src.PropertiesList:
                if p not in skip and p in o.PropertiesList:
                    try:
                        setattr(o, p, getattr(src, p))
                    except Exception:
                        pass
            o.Placement = pl
        else:
            raise bad("kind: component { from, ifcType } | clone { from, at, axis, angle } | unclone { from }.")
        named(o, a.get("name"))
        return done("bim_component", {"object": o.Label, "kind": kind, **reading(o)})

    def bim_panel_out(a):
        kind = a.get("kind", "cut")
        panels = objs(a.get("panels"), "panels")
        import Draft

        wrong = [p.Label for p in panels if Draft.getType(p) != "Panel"]
        if wrong:
            raise bad(f"panels: {', '.join(wrong)} {'is' if len(wrong) == 1 else 'are'} not BIM panels; bim_panel makes them.")
        if kind == "cut":
            outs = [named(headless_call(Arch.makePanelCut, p), None) for p in panels]
            d().recompute()
            s.snapshot("bim_panel_out")
            return {"cuts": [{"panel": p.Label, "cut": o.Label, "edges": len(o.Shape.Edges) if not o.Shape.isNull() else 0} for p, o in zip(panels, outs)],
                    "note": "Flat outlines to cut, with the panel's tag; export to DXF or SVG for the cutter."}
        if kind == "sheet":
            cuts = [headless_call(Arch.makePanelCut, p) for p in panels]
            sh = headless_call(Arch.makePanelSheet, cuts)
            if a.get("width"):
                sh.Width = float(a["width"])
            if a.get("height"):
                sh.Height = float(a["height"])
            named(sh, a.get("name"))
            return done("bim_panel_out", {"sheet": sh.Label, "panels": len(cuts), "size": [float(sh.Width), float(sh.Height)]})
        raise bad("kind: cut { panels } | sheet { panels, width, height }.")

    def bim_nest(a):
        import ArchNesting

        cont = picks.shaped(d(), a.get("container"), "container")
        pieces = objs(a.get("pieces"), "pieces")
        # FreeCAD's nester (ArchNesting.Nester.run) takes one flat face as the sheet and
        # pieces of exactly one face each, all facing the same way; it prints and stops otherwise.
        if len(cont.Shape.Faces) != 1 or cont.Shape.Solids:
            raise bad(f"container: {cont.Label} must be one flat face (the sheet), not a solid or a wire: draft_shape makes a rectangle with a face.")
        not_flat = [p.Label for p in pieces if not isinstance(getattr(p, "Shape", None), Part.Shape) or p.Shape.isNull() or len(p.Shape.Faces) != 1 or p.Shape.Solids]
        if not_flat:
            raise bad(f"pieces: each must be a single flat face (an outline with a face), not a solid: {', '.join(not_flat[:8])}. A panel's outline (its base) is such a face.")
        if len({p.Name for p in pieces}) < len(pieces) or cont in pieces:
            raise bad("pieces: each piece once, and not the container itself.")
        n = ArchNesting.Nester()
        n.container = cont.Shape.Faces[0]
        n.addObjects(pieces)
        # The nester has no settings of its own: the rotations it tries are the module's
        # ROTATIONS (0, 90, 180, 270), set for this run; it has no margin in 1.1.
        was = list(ArchNesting.ROTATIONS)
        try:
            if a.get("rotations"):
                try:
                    ArchNesting.ROTATIONS = [float(r) for r in a["rotations"]]
                except (TypeError, ValueError):
                    raise bad("rotations: degrees to try each piece at, a list such as [0, 90, 180, 270].") from None
            res = n.run()
        finally:
            ArchNesting.ROTATIONS = was
        if not res or not n.results:
            raise ToolError("failed", "The pieces would not nest: FreeCAD's nester stopped (its reason is in the report view; report_read shows it). Check each piece is a flat face lying the same way up as the sheet, and that the largest fits the sheet.")
        n.apply()
        d().recompute()
        s.snapshot("bim_nest")
        sheets = n.results[-1]
        out = {"sheets": len(sheets), "placed": sum(len(x) for x in sheets), "of": len(pieces), "rotations": list(a.get("rotations") or was)}
        if len(sheets) > 1:
            out["note"] = f"The pieces did not all fit one sheet: {len(sheets)} sheets' worth were laid out; view_render shows where."
        if a.get("margin"):
            out["margin"] = "not applied: FreeCAD 1.1's nester has no margin. Leave room by nesting into a face smaller than the sheet."
        return out

    def bim_ifc_brep(a):
        out = []
        for o in objs(a.get("objects")):
            if not hasattr(o, "IfcData"):
                raise bad(f"{o.Label} has no IFC data (not a BIM object).")
            data = dict(o.IfcData)
            on = a.get("on")
            if on is None:
                on = data.get("FlagForceBrep") != "True"
            if on:
                data["FlagForceBrep"] = "True"
            else:
                data.pop("FlagForceBrep", None)
            o.IfcData = data
            out.append({"object": o.Label, "forceBrep": bool(on)})
        return done("bim_ifc_brep", {"set": out, "note": "Forced B-rep objects export to IFC as plain geometry, not parametric extrusions."})

    def bim_views(a):
        import Draft

        levels = objs(a["levels"], "levels") if a.get("levels") else [o for o in d().Objects if getattr(o, "IfcType", "") == "Building Storey"]
        if not levels:
            raise ToolError("not_found", "No levels here: bim_level makes them, or give levels (labels).")
        cut = float(a.get("cutHeight", 1100))
        out = []
        for lv in levels:
            z = lv.Placement.Base.z + cut
            sp = headless_call(Arch.makeSectionPlane, [lv])
            sp.Placement = FreeCAD.Placement(V(0, 0, z), FreeCAD.Rotation())
            sp.Label = s.unique(f"{lv.Label} plan cut", sp)
            v = Draft.make_shape2dview(sp)
            if hasattr(v, "ProjectionMode"):
                v.ProjectionMode = "Cutfaces" if a.get("cutOnly") else "Solid"
            v.Label = s.unique(f"{lv.Label} plan", v)
            out.append({"level": lv.Label, "section": sp.Label, "view": v.Label, "at": z})
        return done("bim_views", {"views": out, "note": "2D plan views at the cut height (Draft shape views, flat on Z = 0): export { format: \"dxf\" } writes them; td_bim draws a section plane on a drawing page."})

    def bim_image_plane(a):
        p = os.path.expanduser(a.get("path") or "")
        if not os.path.isfile(p):
            raise ToolError("not_found", f"path {a.get('path')!r}: no such image file; give its full path (png, jpg, bmp, svg).")
        o = d().addObject("Image::ImagePlane", "ImagePlane")
        o.ImageFile = p
        w = a.get("width")
        h = a.get("height")
        if w or h:
            try:
                from PIL import Image  # noqa: F401  — the aspect from the file where Pillow is there

                with Image.open(p) as im:
                    ratio = im.height / im.width
            except Exception:
                ratio = None
            o.XSize = float(w or (float(h) / ratio if ratio else h))
            o.YSize = float(h or (float(w) * ratio if ratio else w))
        if picks.placed(a):
            o.Placement = picks.placement(a)
        named(o, a.get("name") or os.path.splitext(os.path.basename(p))[0])
        return done("bim_image_plane", {"image": o.Label, "size": [float(o.XSize), float(o.YSize)], "note": "A picture to trace over: a plan, an elevation, a photo with a known length."})

    def bim_library(a):
        roots = [a["folder"]] if a.get("folder") else []
        try:
            pref = FreeCAD.ParamGet("User parameter:Plugins/parts_library").GetString("destination", "")
            if pref:
                roots.append(pref)
        except Exception:
            pass
        roots.append(os.path.join(FreeCAD.getUserAppDataDir(), "Mod", "parts_library"))
        roots = [os.path.expanduser(r) for r in roots if r and os.path.isdir(os.path.expanduser(r))]
        if not roots:
            raise ToolError("not_found", "No objects library here: give folder (a clone of FreeCAD's parts library), or install parts_library from the Addon Manager.")
        q = str(a.get("search") or "").lower()
        hits = []
        for r in roots:
            for f in glob.glob(os.path.join(r, "**", "*"), recursive=True):
                if f.lower().endswith((".fcstd", ".step", ".stp", ".iges", ".igs", ".stl", ".brep")) and all(w in f.lower() for w in q.split()):
                    hits.append(f)
                    if len(hits) >= 200:
                        break
        if a.get("insert"):
            p = a["insert"] if os.path.isabs(a["insert"]) else next((h for h in hits if os.path.basename(h) == a["insert"]), None)
            if not p or not os.path.isfile(p):
                raise ToolError("not_found", f"insert {a['insert']!r}: not found — search first.")
            before = {o.Name for o in d().Objects}
            if p.lower().endswith(".fcstd"):
                d().mergeProject(p)
            else:
                Part.insert(p, d().Name)
            d().recompute()
            new = [o.Label for o in d().Objects if o.Name not in before]
            s.snapshot("bim_library")
            return {"inserted": os.path.basename(p), "objects": new}
        return {"found": [{"name": os.path.basename(h), "path": h} for h in hits[:50]], "more": max(0, len(hits) - 50), "roots": roots}

    def bim_reextrude(a):
        import Draft

        label, sub, fac = picks.resolve(s, a.get("face"))
        if sub is None or not sub.startswith("Face"):
            raise bad("face: \"Wall.Face3\", the object's label, a dot and one of its faces: the face to extrude from again.")
        o = picks.find(d(), label)
        straight = len(fac.Wires) == 1 and all(e.tangentAt(e.FirstParameter).getAngle(e.tangentAt(e.LastParameter)) < 1e-4 for e in fac.Edges)
        if straight:
            base = Draft.make_wire([v.Point for v in fac.Wires[0].OrderedVertexes], closed=True)
        else:
            base = d().addObject("Part::Feature", "Face")
            base.Shape = fac
        t = Draft.getType(o)
        new = headless_call(Arch.makeWall if t == "Wall" else Arch.makePanel if t == "Panel" else Arch.makeStructure, base)
        norm = fac.normalAt(0, 0).negative()
        new.Normal = norm
        for e in o.Shape.Edges:
            if abs(e.tangentAt(0).getAngle(norm)) < 1e-4 or abs(e.tangentAt(0).getAngle(norm) - 3.141592653589793) < 1e-4:
                if hasattr(new, "Thickness"):
                    new.Thickness = e.Length
                else:
                    new.Height = e.Length
                break
        for p in ("Material", "IfcType", "StandardCode"):
            if hasattr(o, p) and hasattr(new, p):
                setattr(new, p, getattr(o, p))
        new.Label = s.unique(a.get("name") or o.Label, new)
        if a.get("delete", True):
            for parent in o.InList:
                if hasattr(parent, "Group") and o in parent.Group:
                    parent.addObject(new)
            d().removeObject(o.Name)
        return done("bim_reextrude", {"object": new.Label, "from": label, "face": sub, "wire": straight, **reading(new)})

    def bim_rewire(a):
        import Draft
        import DraftGeomUtils

        targets = objs(a.get("objects"))
        edges = [e for o in targets for e in getattr(o.Shape, "Edges", [])]
        if not edges:
            raise bad("objects: lines or wires (objects with edges) to join; none of these has an edge.")
        made = []
        for w in DraftGeomUtils.findWires(edges):
            if DraftGeomUtils.hasCurves(w):
                n = d().addObject("Part::Feature", "Wire")
                n.Shape = w
            else:
                n = Draft.make_wire([v.Point for v in w.OrderedVertexes], closed=w.isClosed())
            made.append(n.Label)
        for o in targets:
            d().removeObject(o.Name)
        return done("bim_rewire", {"wires": made, "from": len(targets)})

    def bim_glue(a):
        targets = [o for o in objs(a.get("objects")) if o.isDerivedFrom("Part::Feature") and not o.Shape.isNull()]
        if len(targets) < 2:
            raise bad("objects: two or more objects with shapes to glue into one.")
        c = d().addObject("Part::Feature", "Glue")
        c.Shape = Part.makeCompound([o.Shape for o in targets])
        c.Label = s.unique(a.get("name") or "Glue", c)
        for o in targets:
            d().removeObject(o.Name)
        return done("bim_glue", {"object": c.Label, "of": len(targets), "note": "One plain shape of them all, no longer parametric."})

    def bim_trash(a):
        act = a.get("action", "put")
        trash = d().getObject("Trash")
        if act == "put":
            if trash is None or not trash.isDerivedFrom("App::DocumentObjectGroup"):
                trash = d().addObject("App::DocumentObjectGroup", "Trash")
            for o in objs(a.get("objects")):
                for par in list(o.InList):
                    if par is not trash and hasattr(par, "Group") and o in par.Group:
                        par.removeObject(o) if hasattr(par, "removeObject") else setattr(par, "Group", [x for x in par.Group if x is not o])
                trash.addObject(o)
                if hasattr(o, "Visibility"):
                    o.Visibility = False
            return done("bim_trash", {"trash": [o.Label for o in trash.Group]})
        if act == "empty":
            if trash is None:
                return {"emptied": []}
            gone = []

            def kids(o):
                out = []
                for c in o.OutList:
                    if len(c.InList) == 1 and c.InList[0] is o:
                        out += [c] + kids(c)
                return out

            for o in list(trash.Group):
                if len(o.InList) == 1 and o.InList[0] is trash:
                    for x in [o] + kids(o):
                        gone.append(x.Label)
                        d().removeObject(x.Name)
            return done("bim_trash", {"emptied": gone})
        if act == "list":
            return {"trash": [o.Label for o in trash.Group] if trash is not None else []}
        raise bad("action: put { objects } | list | empty.")

    def bim_reorder(a):
        g = picks.find(d(), a.get("group"), "group")
        if not hasattr(g, "Group"):
            raise bad(f"group: {g.Label} is not a group, level or building (it holds no children).")
        kids = list(g.Group)
        if a.get("sort"):
            new = sorted(kids, key=lambda o: o.Label.lower())
        else:
            order = a.get("order") or []
            pick = [picks.find(d(), r) for r in order]
            if any(o not in kids for o in pick):
                raise bad(f"order: only {g.Label}'s children — {', '.join(o.Label for o in kids)}.")
            new = pick + [o for o in kids if o not in pick]
        g.Group = new
        return done("bim_reorder", {"group": g.Label, "order": [o.Label for o in g.Group]})

    # The wrappers kept as data (agentlink/data/tools.json) run on these.
    helpers = {"doc": d, "objs": objs, "done": done, "named": named, "reading": reading, "headless_call": headless_call,
               "file": file, "basename": os.path.basename, "snapshot": lambda tool: s.snapshot(tool)}

    st = {"type": "string"}
    arr = {"type": "array", "items": {"type": "string"}}
    num = {"type": "number"}
    v3 = {"type": "array", "items": num}
    return runners.tools(GROUP, s, helpers) + [
        Tool("bim_component", "A generic BIM component: kind component { from (an object with a shape), ifcType } | clone { from, at, axis, angle } (follows the original) | unclone { from } (cut loose). Answers object, volume mm³, box.",
             obj({"kind": {"type": "string", "enum": ["component", "clone", "unclone"]}, "from": st, "ifcType": st, "at": v3, "axis": v3, "angle": num, "name": st}, ["from"]), bim_component, changes=True),
        Tool("bim_panel_out", "BIM panels for the cutter: kind cut (each panel's flat outline with its tag) | sheet { width, height } (the cuts on one stock sheet, not nested). export { format: \"dxf\" } writes them.",
             obj({"kind": {"type": "string", "enum": ["cut", "sheet"]}, "panels": arr, "width": num, "height": num, "name": st}, ["panels"]), bim_panel_out, changes=True),
        Tool("bim_nest", "Nest flat pieces into a sheet: container (one flat face), pieces (objects of exactly one flat face each, the same way up; not solids), rotations to try ([0, 90, 180, 270]). The pieces are moved. margin is not applied (FreeCAD 1.1's nester has none). Slow with many pieces: start with a few.", obj({"container": st, "pieces": arr, "rotations": {"type": "array", "items": num}, "margin": num}, ["container", "pieces"]), bim_nest, changes=True),
        Tool("bim_ifc_brep", "Set whether BIM objects go to IFC as B-rep (plain faces) instead of extrusions: on true | false, toggled when left out.", obj({"objects": arr, "on": {"type": "boolean"}}, ["objects"]), bim_ifc_brep, changes=True),
        Tool("bim_views", "2D plan views of levels (all storeys when left out): a section plane at cutHeight mm above each one's elevation (1100) and a flat Draft view of it; cutOnly: the cut faces alone. Slow on big levels.",
             obj({"levels": arr, "cutHeight": num, "cutOnly": {"type": "boolean"}}), bim_views, changes=True),
        Tool("bim_image_plane", "An image plane to trace over: path (the image's full path), width and/or height mm (one gives the other), at, axis, angle. Seen in the window only.", obj({"path": st, "width": num, "height": num, "at": v3, "axis": v3, "angle": num, "name": st}, ["path"]), bim_image_plane, changes=True),
        Tool("bim_library", "The objects library (the parts_library add-on, or folder): search words find files (answers found [{ name, path }]); insert: a found name or full path brings it into the document.", obj({"search": st, "folder": st, "insert": st}), bim_library, changes=True, reads={"insert": [None, ""]}),
        Tool("bim_reextrude", "Re-extrude a BIM object from one of its faces (\"Wall.Face3\"): a new wall, panel or structure standing on that face, as deep as the old one, with its material and IFC type; the old one is deleted unless delete: false. Face numbers change when an object is rebuilt.",
             obj({"face": st, "delete": {"type": "boolean"}, "name": st}, ["face"]), bim_reextrude, changes=True),
        Tool("bim_rewire", "Rebuild loose lines and wires (objects) as joined wires, one per connected run; the originals are deleted.", obj({"objects": arr}, ["objects"]), bim_rewire, changes=True),
        Tool("bim_glue", "Glue two or more objects' shapes into one plain compound (not fused, no longer parametric); the originals are deleted.", obj({"objects": arr, "name": st}, ["objects"]), bim_glue, changes=True),
        Tool("bim_trash", "BIM's trash: action put { objects } (moved into a hidden Trash group, still in the document) | list | empty (deleted for good, with children nothing else uses).",
             obj({"action": {"type": "string", "enum": ["put", "list", "empty"]}, "objects": arr}), bim_trash, changes=True, reads={"action": ["list"]}),
        Tool("bim_reorder", "Reorder a group's, level's or building's children in the tree: order [labels to put first], or sort: true by label.", obj({"group": st, "order": arr, "sort": {"type": "boolean"}}, ["group"]), bim_reorder, changes=True),
    ]
