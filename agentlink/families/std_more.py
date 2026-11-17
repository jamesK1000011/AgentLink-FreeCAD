# SPDX-License-Identifier: LGPL-2.1-or-later
# The document-level commands still left to the window, done headless: links
# (make, group, to an element, replace, unlink, import), App::Part
# containers, duplicates, merging another file in, the document's
# information, revert and save all, appearance (colour, transparency, a
# colour per face, random colours) and text documents; Part's compound
# tools, join features and curve-network import; PartDesign's clone, moving
# features between bodies and in the tree, the tip, and a stepped shaft.

import math
import os
import random

import FreeCAD
import Part

from .. import runners
from .. import paths
from ..protocol import Tool, ToolError, bad
from ..tools import obj
from . import pd_common as pdc
from . import picks
from .doc import colour

GROUP = "std_more"
INFO = "Links, App::Part, the dependency graph, freeze, units, point-pair alignment, duplicates, merge files, document info, revert, save all, appearance and face colours, text documents; compounds, join features; PartDesign clone, move feature, reorder, tip."

V = FreeCAD.Vector
# Kept on the object itself, so a colour set headless survives the save and
# shows when the file opens in the window (and export colours can read it).
COLOR_PROP = "AgentLinkColor"
FACE_PROP = "AgentLinkFaceColors"


def solid_feature(o):
    """What a body's tip may be: a feature with a solid of its own — not
    a sketch, a datum or a binder (Body::execute refuses those: "Linked
    object is not a PartDesign feature"), nor a MultiTransform's step."""
    if not o.isDerivedFrom("PartDesign::Feature"):
        return False
    return not any(x.TypeId == "PartDesign::MultiTransform" and o in x.Transformations for x in o.InList)


def after_tip(b):
    """The solid features past the tip: kept, but not in the body's shape
    ({ afterTip: [labels] }, or nothing)."""
    g = list(b.Group)
    if b.Tip is None or b.Tip not in g:
        return {}
    left = [o.Label for o in g[g.index(b.Tip) + 1:] if solid_feature(o)]
    return {"afterTip": left} if left else {}


def profile_sketch(f):
    """The sketch a feature is built on: its Profile, which FreeCAD keeps as
    the sketch or as (sketch, [sub-elements]). None when it has none."""
    prof = getattr(f, "Profile", None)
    return prof[0] if isinstance(prof, tuple) else prof


def reattach(o, src, to):
    """A sketch moved from body src to body to, put on the same origin plane
    of its new body: origin planes are per body. Anything else (a sketch on
    a face, a feature) is left as it is."""
    sp = pdc.support_prop(o)
    sup = getattr(o, sp, None)
    if o.TypeId == "Sketcher::SketchObject" and src is not None and sup:
        ref = sup[0][0] if isinstance(sup, list) else None
        if ref is not None and src.Origin.hasObject(ref):
            role = ref.Role if hasattr(ref, "Role") else ref.Label
            new = next((x for x in to.Origin.OriginFeatures if getattr(x, "Role", x.Label) == role), None)
            if new is not None:
                setattr(o, sp, [(new, "")])


def shaft_solid(pts, axis="x"):
    """A stepped shaft's solid from its half outline (points [x, radius, 0]
    along x, the first and last on the axis): the outline closed, points
    that repeat dropped, turned once about x, and laid along y or z when
    asked."""
    clean = [pts[0]]
    for p in pts[1:]:
        if (p - clean[-1]).Length > 1e-9:
            clean.append(p)
    clean.append(pts[0])
    face = Part.Face(Part.makePolygon(clean))
    solid = face.revolve(V(0, 0, 0), V(1, 0, 0), 360)
    solid = Part.Solid(Part.Shell(solid.Faces)) if solid.ShapeType != "Solid" else solid
    if axis != "x":
        solid.rotate(V(0, 0, 0), V(0, 1, 0), -90) if axis == "z" else solid.rotate(V(0, 0, 0), V(0, 0, 1), 90)
    return solid


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

    # ---- links ---------------------------------------------------------------------------

    def link_make(a):
        kind = a.get("kind", "link")
        if kind not in ("link", "group"):
            raise bad("kind: link (to: one object, or \"Box.Face3\" for one element of it) | group (objects: an App::LinkGroup of them).")
        count = a.get("count")
        if count is not None and (isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 1000):
            raise bad("count: how many elements the link shows as an array, 0 (a plain link) … 1000.")
        if kind == "group":
            g = d().addObject("App::LinkGroup", "LinkGroup")
            g.Label = s.unique(a.get("name") or "Link group", g)
            members = objs(a.get("objects") or [], "objects") if a.get("objects") else []
            g.setLink(members) if members else None
            return done("link_make", {"link": g.Label, "kind": "group", "elements": [m.Label for m in members]})
        target = a.get("to")
        if not target:
            raise bad("to: the object to link — or \"Box.Face3\" for a link to one element (kind: element).")
        head, sub = picks.split_ref(target) if isinstance(target, str) else (None, None)
        src = picks.find(d(), head or target, "to")
        if sub:
            sh = getattr(src, "Shape", None)
            if sh is None or sh.isNull():
                raise bad(f"to: {src.Label} has no shape, so no {sub} to link to — leave the element out to link the whole object.")
            picks.element(sh, sub, src.Label)  # refused here when it is not on the shape
        lk = d().addObject("App::Link", "Link")
        if sub:
            lk.LinkedObject = (src, [sub])
        else:
            lk.LinkedObject = src
        lk.Label = s.unique(a.get("name") or f"{src.Label} link", lk)
        if picks.placed(a):
            lk.Placement = picks.placement(a)
        if count:
            lk.ElementCount = count
        return done("link_make", lambda: {"link": lk.Label, "name": lk.Name, "to": src.Label, **({"element": sub} if sub else {}),
                                  "placement": picks.placement_json(lk.Placement),
                                  **({"count": count, "elements": [e.Name for e in (getattr(lk, "ElementList", None) or [])][:20],
                                      "countNote": "The elements start on top of one another: each is an object of its own (elements), placed with object_set { object, values: { Placement } }."} if count else {}),
                                  "note": "A link shows the object again without a copy: change the original and every link follows. Its placement stands in for the original's own (LinkTransform false)."})

    def link_edit(a):
        act = a.get("action")
        if act in ("import", "import_all"):
            links = [o for o in d().Objects if o.TypeId.startswith("App::Link")] if act == "import_all" else objs(a.get("links"), "links")

            def target(o):
                t = getattr(o, "LinkedObject", None)
                return t[0] if isinstance(t, tuple) else t

            outside = [o for o in links if target(o) is not None and target(o).Document is not d()]
            if not outside:
                return {"imported": [], "note": "No link here points into another document."}
            got = d().importLinks(outside)
            d().recompute()
            s.snapshot("link_edit")
            return {"imported": [o.Label for o in got or []], "links": [o.Label for o in outside], "note": "The other documents' objects are copied in; the links now point at the copies."}
        lk = objs(a.get("link"), "link")[0]
        if not lk.TypeId.startswith("App::Link"):
            raise bad(f"link: {lk.Label} is not a link ({lk.TypeId}) — object_group {{ action: \"list\" }} names the links there are.")
        if act == "replace":
            to = picks.find(d(), a.get("to"), "to")
            if to is lk or lk in getattr(to, "OutListRecursive", []):
                raise bad(f"to: {to.Label} is {lk.Label} itself or built from it — a link cannot point at itself.")
            lk.LinkedObject = to
            return done("link_edit", {"link": lk.Label, "now": to.Label})
        if act == "unlink":
            # A real copy in the link's place, keeping its placement.
            src = lk.LinkedObject[0] if isinstance(lk.LinkedObject, tuple) else lk.LinkedObject
            if src is None:
                raise ToolError("invalid_state", f"{lk.Label} links to nothing.")
            sh = Part.getShape(lk)
            if sh.isNull():
                raise ToolError("invalid_state", f"{lk.Label} links to {src.Label}, which has no shape to copy: unlink makes a shape copy only (object_duplicate copies other objects).")
            o = d().addObject("Part::Feature", "Body")
            o.Shape = sh
            o.Label = s.unique(a.get("name") or src.Label, o)
            # Everything that used the link (groups, features, joints,
            # expressions) now uses the copy: nothing left dangling.
            moved = picks.repoint(d(), lk, o)
            d().removeObject(lk.Name)
            d().recompute()
            return done("link_edit", {"copy": o.Label, "from": src.Label, "volume": round(sh.Volume, 3) if sh.Solids else None, **({"repointed": moved} if moved else {})})
        raise bad("action: replace { link, to } | unlink { link } | import { links } | import_all — object_group { action: \"list\" } names the links.")

    def object_duplicate(a):
        out = []
        for o in objs(a.get("objects")):
            if a.get("simple"):
                # Part's Simple copy: the shape alone, no history.
                c = d().addObject("Part::Feature", "Copy")
                c.Shape = Part.getShape(o)
                c.Label = s.unique(a.get("name") or f"{o.Label} copy", c)
                out.append({"from": o.Label, "copy": c.Label, "simple": True})
                continue
            c = d().copyObject(o, bool(a.get("dependencies")))
            c.Label = s.unique(a.get("name") or f"{o.Label} copy", c)
            out.append({"from": o.Label, "copy": c.Label})
        return done("object_duplicate", {"duplicated": out})

    # ---- the document --------------------------------------------------------------------

    def doc_merge(a):
        if not isinstance(a.get("path"), str) or not a["path"].strip():
            raise bad("path: the .FCStd whose objects to bring in (a relative path is in the session's folder).")
        # As every other reader: a relative path is in the session's folder.
        p = paths.local(s, a["path"])
        if not os.path.isfile(p):
            raise ToolError("not_found", f"path {p!r}: no such file — an .FCStd to bring in.")
        if not p.lower().endswith(".fcstd"):
            raise bad(f"path: {os.path.basename(p)} is not a FreeCAD document — doc_merge takes .FCStd; import_file brings STEP, STL and the rest in.")
        before = {o.Name for o in d().Objects}
        try:
            d().mergeProject(p)
        except Exception as e:  # noqa: BLE001 - not a document FreeCAD reads
            raise ToolError("failed", f"FreeCAD could not merge {os.path.basename(p)}: {e} — doc_open {{ path }} shows whether the file opens at all.") from None
        # The other file's own hidden records object (its steps, materials and
        # setups) is not part of the model: left in, it showed as an object that
        # came in ("Agent Link records001"), or stood in as this document's records.
        from ..store import HOLDER

        for o in [o for o in d().Objects if o.Name not in before and o.Name.startswith(HOLDER)]:
            d().removeObject(o.Name)
        d().recompute()
        new = [o for o in d().Objects if o.Name not in before]
        if not new:
            raise ToolError("failed", f"{os.path.basename(p)}: nothing came in (an empty document, or one FreeCAD could not read).")
        s.snapshot("doc_merge")
        from .doc import errors

        out = {"merged": os.path.basename(p), "count": len(new), "objects": [o.Label for o in new[:40]], "errors": errors(d())}
        if len(new) > 40:
            out["more"] = len(new) - 40
        return out

    INFO_PROPS = {"author": "CreatedBy", "company": "Company", "comment": "Comment", "license": "License", "licenseUrl": "LicenseURL", "lastModifiedBy": "LastModifiedBy", "id": "Id", "uid": "Uid", "label": "Label"}

    def doc_info(a):
        dd = d()
        for k in a:
            if k in ("id", "uid"):
                raise bad(f"{k}: read-only (FreeCAD's own identifier of the document).")
        for k, prop in INFO_PROPS.items():
            if k in a and k not in ("id", "uid"):
                if not isinstance(a[k], str):
                    raise bad(f"{k}: text.")
                setattr(dd, prop, a[k])
        return {"document": dd.Name, "file": dd.FileName or None, **{k: str(getattr(dd, p, "")) for k, p in INFO_PROPS.items()},
                "created": str(getattr(dd, "CreationDate", "")), "modified": str(getattr(dd, "LastModifiedDate", "")),
                "objects": len(dd.Objects), "bytes": os.path.getsize(dd.FileName) if dd.FileName and os.path.isfile(dd.FileName) else None}

    def doc_revert(a):
        dd = d()
        if not dd.FileName or not os.path.isfile(dd.FileName):
            raise ToolError("invalid_state", f"{dd.Label} was never saved: there is no file to go back to — history_undo steps back through this session's changes instead.")
        path = dd.FileName
        FreeCAD.closeDocument(dd.Name)
        nd = FreeCAD.openDocument(path)
        # As doc_open: a document just read is as its file, though FreeCAD
        # 1.1 marks it touched on opening (doc_close then asked to discard).
        try:
            from ..store import _unchanged

            nd.recompute()
            _unchanged(nd)
        except Exception:  # noqa: BLE001
            pass
        s.switch(nd)
        return {"document": nd.Name, "label": nd.Label, "reverted": path, "objects": len(nd.Objects),
                "note": "Back to the saved file: unsaved changes are gone, and this session's undo steps with them (the document was closed and opened again)."}

    def doc_save_all(a):
        saved, unsaved = [], []
        for name, dd in FreeCAD.listDocuments().items():
            if dd.FileName:
                dd.save()
                # (named apart from the list: imported as "saved" it replaced
                # the list, and every doc_save_all with a saved document
                # failed "'function' object has no attribute 'append'")
                from .doc import saved as _mark_saved

                _mark_saved(dd)
                saved.append(dd.FileName)
            else:
                unsaved.append(dd.Label)
        return {"saved": saved, **({"neverSaved": unsaved, "note": "Never saved, so no file to save to: doc_save { path } for each."} if unsaved else {})}

    def text_document(a):
        name = a.get("name") or "Notes"
        t = next((o for o in d().Objects if o.TypeId == "App::TextDocument" and o.Label == name), None)
        if t is None:
            t = d().addObject("App::TextDocument", "Text")
            t.Label = s.unique(name, t)
        if "text" in a:
            t.Text = (t.Text + "\n" if a.get("append") and t.Text else "") + str(a["text"])
        return done("text_document", {"text": t.Label, "chars": len(t.Text), "lines": t.Text.count("\n") + 1 if t.Text else 0})

    # ---- appearance ----------------------------------------------------------------------

    def keep_colour(o, prop, kind, value):
        if prop not in o.PropertiesList:
            o.addProperty(kind, prop, "Agent Link", "Colour set by Agent Link")
        setattr(o, prop, value)

    def object_appearance(a):
        targets = objs(a.get("objects"))
        if a.get("color") is None and not a.get("random") and a.get("transparency") is None and not a.get("faces"):
            raise bad("color \"#rrggbb\" (or random: true), transparency 0 … 100, and/or faces { \"Face3\": \"#ff0000\" }: give at least one.")
        tr = a.get("transparency")
        if tr is not None and (isinstance(tr, bool) or not isinstance(tr, (int, float)) or not 0 <= tr <= 100):
            raise bad("transparency: 0 (solid) to 100 (clear).")
        if a.get("faces") is not None and not isinstance(a["faces"], dict):
            raise bad("faces: { \"Face3\": \"#ff0000\", … } — a colour for each face named (shape_query finds faces).")
        out = []
        for o in targets:
            c = colour(a.get("color"))
            if a.get("random"):
                c = (random.random() * 0.8 + 0.1, random.random() * 0.8 + 0.1, random.random() * 0.8 + 0.1, 1.0)
            vo = getattr(o, "ViewObject", None)
            e = {"object": o.Label}
            if c is not None:
                keep_colour(o, COLOR_PROP, "App::PropertyColor", c[:3])
                if vo is not None and hasattr(vo, "ShapeColor"):
                    vo.ShapeColor = c[:3]
                e["color"] = "#" + "".join(f"{int(round(x * 255)):02x}" for x in c[:3])
            faces = a.get("faces")
            if faces:
                sh = getattr(o, "Shape", None)
                if sh is None or not sh.Faces:
                    raise ToolError("invalid_state", f"{o.Label} has no faces to colour.")
                base = c or (getattr(vo, "ShapeColor", None) if vo is not None else None) or (0.8, 0.8, 0.8)
                cols = [tuple(base[:3]) + (1.0,)] * len(sh.Faces)
                for f, v in faces.items():
                    i = int(str(f).replace("Face", "")) if str(f).replace("Face", "").isdigit() else None
                    if i is None or not 1 <= i <= len(sh.Faces):
                        raise bad(f"faces: {f!r} — {o.Label} has Face1…Face{len(sh.Faces)}.")
                    cols[i - 1] = colour(v)
                keep_colour(o, FACE_PROP, "App::PropertyStringList", ["#" + "".join(f"{int(round(x * 255)):02x}" for x in col[:3]) for col in cols])
                if vo is not None and hasattr(vo, "DiffuseColor"):
                    vo.DiffuseColor = cols
                e["faces"] = len(faces)
            if tr is not None:
                # After the face colours: in FreeCAD 1.x setting DiffuseColor
                # resets every face's transparency to what the colours carry.
                t = int(tr)
                keep_colour(o, "AgentLinkTransparency", "App::PropertyInteger", t)
                if vo is not None and hasattr(vo, "Transparency"):
                    vo.Transparency = t
                e["transparency"] = t
            e["shown"] = vo is not None
            out.append(e)
        d().recompute()
        return {"set": out, **({"note": "No window here: the colours are kept on the objects and show when the file opens in FreeCAD."} if not any(x["shown"] for x in out) else {})}

    # ---- PartDesign ------------------------------------------------------------------------

    # ---- other workbenches' leftovers ---------------------------------------------------

    def scad_tidy(a):
        act = a.get("action")
        targets = objs(a.get("objects")) if a.get("objects") else []
        if act == "color_code":
            # OpenSCAD's Color Shapes: by validity and what the shape most is.
            pal = {"invalid": "#ff0000", "Solid": "#cccccc", "Shell": "#ffaa00", "Face": "#ffff00", "Wire": "#00ccff", "Edge": "#0066ff", "Vertex": "#aa00ff", "empty": "#555555"}
            rows = []
            for o in targets or [x for x in d().Objects if getattr(x, "Shape", None) is not None]:
                sh = o.Shape
                kind = "empty" if sh.isNull() else ("invalid" if not sh.isValid() else next((k for k, lst in (("Solid", sh.Solids), ("Shell", sh.Shells), ("Face", sh.Faces), ("Wire", sh.Wires), ("Edge", sh.Edges), ("Vertex", sh.Vertexes)) if lst), "empty"))
                c = colour(pal[kind])
                # FreeCAD's own Color Shapes sets the view's colour only
                # (FreeCAD 1.1: src/Mod/OpenSCAD/colorcodeshapes.py), which
                # touches nothing and recomputes nothing. The colour kept on
                # the object here (so it survives a file opened without a
                # window) is a property write, which marks the object
                # touched though its shape does not depend on it: an object
                # that was clean before is marked clean again, one already
                # waiting for a recompute keeps waiting.
                try:
                    was_touched = "Touched" in o.State
                except Exception:  # noqa: BLE001
                    was_touched = True
                keep_colour(o, COLOR_PROP, "App::PropertyColor", c[:3])
                if not was_touched:
                    try:
                        o.purgeTouched()
                    except Exception:  # noqa: BLE001 - left touched: recompute clears it
                        pass
                vo = getattr(o, "ViewObject", None)
                if vo is not None and hasattr(vo, "ShapeColor"):
                    vo.ShapeColor = c[:3]
                rows.append({"object": o.Label, "is": kind, "color": pal[kind]})
            return {"coloured": rows, "key": pal}
        if act in ("explode", "expand_placements", "tolerance", "remove_subtree") and not targets:
            raise bad(f"objects: the objects to {act.replace('_', ' ')} (names or labels).")
        if act == "tolerance":
            for k in ("vertex", "edge", "face"):
                if a.get(k) is not None and (isinstance(a[k], bool) or not isinstance(a[k], (int, float)) or a[k] < 0):
                    raise bad(f"{k}: a tolerance in mm, 0 or more (0 leaves that kind as it is).")
            for o in targets:
                if getattr(o, "Shape", None) is None or o.Shape.isNull():
                    raise bad(f"objects: {o.Label} has no shape to copy with looser tolerances.")
        if act == "explode":
            out = []
            for o in targets:
                if not (o.isDerivedFrom("Part::Fuse") or o.isDerivedFrom("Part::MultiFuse") or o.isDerivedFrom("Part::Compound")):
                    raise bad(f"objects: {o.Label} is not a fusion or compound ({o.TypeId}) — explode takes a Part::Fuse, Part::MultiFuse or Part::Compound (compound_explode splits any compound shape).")
                if o.InList:
                    raise bad(f"objects: {o.Label} is used by {o.InList[0].Label}: only a top-level one explodes — explode that one, or scad_tidy {{ action: \"replace\" }} takes it out of its parent first.")
                plm, kids = o.Placement, list(o.OutList)
                d().removeObject(o.Name)
                for k in kids:
                    if not plm.isNull():
                        k.Placement = plm.multiply(k.Placement)
                    if getattr(k, "ViewObject", None) is not None:
                        k.ViewObject.Visibility = True
                out.append({"from": o.Label, "pieces": [k.Label for k in kids]})
            return done("scad_tidy", {"exploded": out})
        if act == "expand_placements":
            import expandplacements

            for o in targets:
                expandplacements.expandplacements(o, FreeCAD.Placement())
            return done("scad_tidy", {"expanded": [o.Label for o in targets], "note": "Placements pushed down to the leaves of the tree."})
        if act == "tolerance":
            import OpenSCADFeatures

            out = []
            for o in targets:
                n = d().addObject("Part::FeaturePython", "tolerance")
                OpenSCADFeatures.IncreaseTolerance(n, o)
                for k in ("vertex", "edge", "face"):
                    if a.get(k) is not None:
                        setattr(n, k.title(), float(a[k]))
                n.Label = s.unique(f"tolerance_{o.Label}", n)
                if getattr(o, "ViewObject", None) is not None:
                    o.ViewObject.Visibility = False
                out.append(n.Label)
            return done("scad_tidy", {"made": out})
        if act == "remove_subtree":
            import OpenSCADUtils

            before = {o.Label for o in d().Objects}
            OpenSCADUtils.removesubtree(targets)
            return done("scad_tidy", {"removed": sorted(before - {o.Label for o in d().Objects})})
        if act == "replace":
            import replaceobj

            parent, old, new = (picks.find(d(), a.get(k), k) for k in ("parent", "old", "new"))
            if old not in parent.OutList:
                raise bad(f"old: {parent.Label} does not use {old.Label} (it uses {', '.join(x.Label for x in parent.OutList) or 'nothing'}).")
            if new is parent or parent in getattr(new, "OutListRecursive", []):
                raise bad(f"new: {new.Label} is {parent.Label} or built from it — that would be a loop.")
            replaceobj.replaceobj(parent, old, new)
            return done("scad_tidy", {"parent": parent.Label, "replaced": old.Label, "with": new.Label})
        raise bad("action: color_code | explode | expand_placements | tolerance { vertex, edge, face } | remove_subtree | replace { parent, old, new }.")

    def robot_tool(a):
        r = picks.find(d(), a.get("robot"), "robot")
        if not r.isDerivedFrom("Robot::RobotObject"):
            raise bad(f"robot: {r.Label} is not a robot ({r.TypeId}) — robot_new makes one.")
        t = picks.shaped(d(), a.get("tool"), "tool")
        r.ToolShape = t
        if picks.placed(a):
            r.ToolBase = picks.placement(a)
        return done("robot_tool", {"robot": r.Label, "tool": t.Label, "note": "The tool shape is drawn on the robot's flange (ToolBase is where on the shape the flange sits). Drawing only, and only in the window: it does not move the tool point robot_move tcp works with (robot_new tool sets that)."})

    def sheet_cells(a):
        sh = picks.find(d(), a.get("sheet"), "sheet")
        if not sh.isDerivedFrom("Spreadsheet::Sheet"):
            raise bad(f"{sh.Label} is not a spreadsheet.")
        from .. import cells as C

        if not a.get("merge") and not a.get("split"):
            raise bad("merge: \"A1:C1\" (one cell across them) or split: \"A1\" (a merged cell back apart).")
        try:
            # FreeCAD's addresses are capitals only ("a1:c1" is an invalid cell specifier there)
            rng = C.range_text(*C.parse_range(a["merge"])) if a.get("merge") else None
            cell = C.range_text(*C.parse_range(a["split"])) if a.get("split") else None
        except C.AddressError as e:
            raise bad(f"{e} — merge takes a range, \"A1:C1\"; split one cell, \"A1\".")
        if rng is not None and ":" not in rng:
            raise bad(f"merge {rng}: a range of more than one cell, \"A1:C1\" (split: \"{rng}\" takes a merged cell apart).")
        if cell is not None and ":" in cell:
            raise bad(f"split {cell}: one cell of the merged one, \"{cell.split(':')[0]}\".")
        if rng:
            sh.mergeCells(rng)
        if cell:
            sh.splitCell(cell)
        first = (rng or cell).split(":")[0]
        out = {"sheet": sh.Label, "merged": bool(rng), "cell": first}
        if rng:
            out["range"] = rng
            out["note"] = f"{first} holds the merged cell; the other cells' contents and aliases were cleared, as FreeCAD does."
        return done("sheet_cells", out)

    # ---- from the window-only re-sort (unattended use, O) -------------------------------

    def doc_graph(a):
        """What is built from what (Std_DependencyGraph): each object and
        the ones it uses, as text and a GraphViz file (SVG too when dot is
        on this computer)."""
        import shutil
        import subprocess

        dd = d()
        edges, nodes = [], []
        for o in dd.Objects:
            nodes.append(o)
            for u in o.OutList:
                edges.append((o, u))
        uses = {o.Label: sorted({u.Label for (x, u) in edges if x is o}) for o in nodes}
        roots = sorted(o.Label for o in nodes if not o.InList)
        out = {"objects": len(nodes), "links": len(edges), "roots": roots,
               "uses": {k: v for k, v in uses.items() if v}}
        if a.get("path") is not None or a.get("svg"):
            def q(t):
                return '"' + str(t).replace("\\", "\\\\").replace('"', '\\"') + '"'
            dot = ["digraph G {", "  rankdir=BT;", "  node [shape=box, fontsize=10];"]
            dot += [f"  {q(o.Name)} [label={q(o.Label)}];" for o in nodes]
            dot += [f"  {q(x.Name)} -> {q(u.Name)};" for x, u in edges]
            dot.append("}")
            p = paths.local(s, a.get("path") or f"{dd.Label}_graph.dot")
            if not p.lower().endswith(".dot"):
                p += ".dot"
                paths.made(s, p)
            os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
            with open(p, "w") as f:
                f.write("\n".join(dot) + "\n")
            out["path"] = p
            exe = shutil.which("dot")
            if a.get("svg"):
                if exe:
                    svg = p[:-4] + ".svg"
                    r = subprocess.run([exe, "-Tsvg", p, "-o", svg], capture_output=True, timeout=60)
                    if r.returncode == 0:
                        out["svg"] = svg
                    else:
                        out["note"] = "GraphViz could not draw it: " + r.stderr.decode(errors="replace")[-200:]
                else:
                    out["note"] = "GraphViz's dot is not on this computer: the .dot file opens in any GraphViz viewer."
        return out

    def object_freeze(a):
        dd = d()
        out = {}
        if "skipRecompute" in a:
            if not hasattr(dd, "RecomputesFrozen"):
                raise ToolError("unavailable", "This FreeCAD has no skip-recompute switch on documents.")
            dd.RecomputesFrozen = bool(a["skipRecompute"])
            out["skipRecompute"] = bool(dd.RecomputesFrozen)
        if a.get("objects"):
            want = bool(a.get("frozen", True))
            targets = objs(a["objects"])
            # FreeCAD has no Python door to freezing: only the window's
            # command (Std_ToggleFreeze) sets it, on the selection.
            if not getattr(FreeCAD, "GuiUp", False):
                raise ToolError("unavailable", "Freezing objects works only through the FreeCAD window (FreeCAD 1.1 has no Python call for it, only the Std_ToggleFreeze command): session_state says where calls go (where: window). skipRecompute: true | false works here, for the whole document.")
            import FreeCADGui

            def frozen(o):
                try:
                    return o.getStatusString() == "Freezed"
                except Exception:
                    return False

            flip = [o for o in targets if frozen(o) != want]
            if flip:
                FreeCADGui.Selection.clearSelection()
                for o in flip:
                    FreeCADGui.Selection.addSelection(o)
                FreeCADGui.runCommand("Std_ToggleFreeze", 0)
                FreeCADGui.Selection.clearSelection()
            out["frozen" if want else "unfrozen"] = [o.Label for o in targets if frozen(o) == want]
            miss = [o.Label for o in targets if frozen(o) != want]
            if miss:
                out["not"] = miss
            out["note"] = ("A frozen object keeps its shape through recomputes until unfrozen (object_set on it changes its properties but not its shape); FreeCAD's wiki says the frozen state is not saved with the file."
                           if want else "Unfrozen: recompute { force: true } brings them up to date.")
        if not out:
            raise bad("objects (frozen: true | false) and/or skipRecompute: true | false.")
        s.snapshot("object_freeze")
        return out

    def units_convert(a):
        q = a.get("value")
        to = a.get("to")
        if q in (None, "") or not to:
            raise bad("value: a quantity with its unit (\"2.5 in\", \"300 N*m\", \"45 deg\"); to: the unit wanted (\"mm\", \"lbf*ft\", \"rad\").")
        try:
            Q = FreeCAD.Units.Quantity(str(q))
            U = FreeCAD.Units.Quantity(f"1 {to}")
        except Exception as e:
            raise bad(f"{q!r} or {to!r} is not a quantity FreeCAD reads ({e}): value is a number with its unit (\"2.5 in\", \"300 N*m\", \"45 deg\"), to a unit alone (\"mm\", \"lbf*ft\", \"rad\"); * and / join units, ^ raises one (\"mm^2\").") from None
        if Q.Unit != U.Unit:
            raise bad(f"{q} and {to} measure different things ({Q.Unit} vs {U.Unit}): to must be a unit of the same kind as value's.")
        if not U.Value:
            raise bad(f"to: {to!r} is not a unit FreeCAD can divide by.")
        v = Q.Value / U.Value
        return {"value": str(q), "to": to, "result": float(f"{v:.10g}"), "text": f"{v:.6g} {to}"}

    def object_align(a):
        """Place an object so its points land on another's (Std_Alignment):
        pairs [[from, to] …] (three or more for a full turn, one moves only),
        the best fit's rms and largest miss."""
        import numpy as np

        o = objs([a.get("object")], "object")[0] if a.get("object") else None
        pairs = a.get("pairs") or []
        if o is None or len(pairs) < 1:
            raise bad("object, pairs [[from xyz on it, to xyz where it goes] …] in mm, document coordinates (measure or shape_query give points): one pair moves it; three or more set its turn too.")
        try:
            P = np.array([[float(c) for c in p[0]] for p in pairs])
            Q = np.array([[float(c) for c in p[1]] for p in pairs])
        except Exception:
            raise bad("pairs: [[[x, y, z], [x, y, z]] …] in mm.")
        if P.shape[1:] != (3,) or Q.shape != P.shape:
            raise bad("pairs: each [[x, y, z], [x, y, z]].")
        cp, cq = P.mean(0), Q.mean(0)
        if len(pairs) >= 3:
            H = (P - cp).T @ (Q - cq)
            U, S, Vt = np.linalg.svd(H)
            if S[1] < 1e-9 * max(1.0, S[0]):
                raise bad("pairs: the from-points lie on one line; three that are not in a line set the turn.")
            dsign = np.sign(np.linalg.det(Vt.T @ U.T)) or 1.0
            R = Vt.T @ np.diag([1, 1, dsign]) @ U.T
        else:
            R = np.eye(3)
        t = cq - R @ cp
        fit = (R @ P.T).T + t
        miss = np.linalg.norm(fit - Q, axis=1)
        M = FreeCAD.Matrix(*[float(x) for x in (*R[0], t[0], *R[1], t[1], *R[2], t[2], 0, 0, 0, 1)])
        if not hasattr(o, "Placement"):
            raise bad(f"object: {o.Label} ({o.TypeId}) has no Placement to move.")
        o.Placement = FreeCAD.Placement(M).multiply(o.Placement)
        pl = o.Placement
        out = {"object": o.Label, "pairs": len(pairs), "rms": round(float(np.sqrt((miss ** 2).mean())), 4), "worst": round(float(miss.max()), 4),
               "placement": {"at": [round(x, 4) for x in pl.Base], "axis": [round(x, 5) for x in pl.Rotation.Axis], "angle": round(math.degrees(pl.Rotation.Angle), 4)}}
        if len(pairs) < 3:
            out["note"] = "Moved only: three or more pairs (not in a line) set its turn too."
        return done("object_align", out)

    # ---- what the Part, compound and Surface entries call by name ---------------------------
    # (their tools are data: agentlink/data/tools.json, docs/data-tools.md)

    def join_feature(proxy, view, default, name):
        """A BOPTools join feature (Connect, Embed, Cutout) made in the
        session's document: BOPTools' own make* add to FreeCAD.ActiveDocument,
        which is not always this one. Its view provider only in the window."""
        j = d().addObject("Part::FeaturePython", default)
        proxy(j)
        if FreeCAD.GuiUp and getattr(j, "ViewObject", None) is not None:
            view(j.ViewObject)
        j.Label = s.unique(name or default, j)
        return j

    def cloud_points(o):
        """A mesh's or a point cloud's points as an n × 3 array; None for any other object."""
        import numpy as np

        if hasattr(o, "Mesh"):
            return np.array([[p.x, p.y, p.z] for p in o.Mesh.Points])
        if o.isDerivedFrom("Points::Feature"):
            return np.array([[p.x, p.y, p.z] for p in o.Points.Points])
        return None

    def quadric_patch(P):
        """A quadric fitted to points by least squares, as Reen's Polynomial
        Surface: z(u, v) over the points' best plane, made a 3 × 3 Bézier
        patch over their box. One algorithm: (the patch's shape, the rms and
        the largest miss of the points along the plane's normal)."""
        import numpy as np

        c = P.mean(0)
        _, _, vt = np.linalg.svd(P - c)
        ex, ey, ez = vt[0], vt[1], vt[2]
        L = (P - c) @ np.array([ex, ey, ez]).T
        u, v, z = L[:, 0], L[:, 1], L[:, 2]
        A = np.c_[np.ones_like(u), u, v, u * u, u * v, v * v]
        k, *_ = np.linalg.lstsq(A, z, rcond=None)
        u0, u1, v0, v1 = u.min(), u.max(), v.min(), v.max()
        f = lambda x, y: k[0] + k[1] * x + k[2] * y + k[3] * x * x + k[4] * x * y + k[5] * y * y  # noqa: E731
        # A quadric over a box is a degree-2 Bézier patch: its 9 poles by least squares on a grid.
        B = lambda t: np.array([(1 - t) ** 2, 2 * t * (1 - t), t * t])  # noqa: E731
        ts = np.linspace(0, 1, 7)
        rows, rhs = [], []
        for tu in ts:
            for tv in ts:
                bu, bv = B(tu), B(tv)
                rows.append(np.outer(bu, bv).ravel())
                rhs.append(f(u0 + (u1 - u0) * tu, v0 + (v1 - v0) * tv))
        zp, *_ = np.linalg.lstsq(np.array(rows), np.array(rhs), rcond=None)
        poles = []
        for i in range(3):
            row = []
            for j in range(3):
                uu = u0 + (u1 - u0) * i / 2
                vv = v0 + (v1 - v0) * j / 2
                w = c + ex * uu + ey * vv + ez * zp[i * 3 + j]
                row.append(V(*w))
            poles.append(row)
        bz = Part.BezierSurface()
        bz.increase(2, 2)
        for i in range(3):
            for j in range(3):
                bz.setPole(i + 1, j + 1, poles[i][j])
        res = z - f(u, v)
        return bz.toShape(), round(float(np.sqrt((res ** 2).mean())), 4), round(float(np.abs(res).max()), 4)

    def tool_module(name):
        """One of FreeCAD's Python modules by name (CompoundTools.Explode), loaded when the tool runs."""
        import importlib

        return importlib.import_module(name)

    # FreeCAD's CompoundFilter FilterType for each way of keeping, and
    # whether it is inverted: collision-fail is collision-pass with Invert;
    # window-distribution was compound_filter's old word for window-distance.
    FILTER_KINDS = {"collision-pass": ("collision-pass", False), "collision-fail": ("collision-pass", True), "window-volume": ("window-volume", False),
                    "window-area": ("window-area", False), "window-length": ("window-length", False), "window-distance": ("window-distance", False),
                    "window-distribution": ("window-distance", False)}
    part_helpers = {"objs": objs, "find": lambda ref, what="object": picks.find(d(), ref, what), "ref_list": picks.ref_list, "snapshot": lambda tool: s.snapshot(tool),
                    "tool_module": tool_module, "FILTER_KINDS": FILTER_KINDS, "join_feature": join_feature,
                    "in_file": lambda tool, path: paths.in_file(s, tool, path), "isfile": os.path.isfile, "basename": os.path.basename,
                    "stem": lambda p: os.path.splitext(os.path.basename(p))[0], "read_shape": lambda *a, **k: Part.read(*a, **k), "compound": lambda *a, **k: Part.Compound(*a, **k),
                    "cloud_points": cloud_points, "quadric_patch": quadric_patch}

    # The wrappers kept as data (agentlink/data/tools.json) run on these.
    helpers = {"doc": d, "done": done, "unique": s.unique, "placed": picks.placed, "placement": picks.placement,
               "shaped": lambda ref, what: picks.shaped(d(), ref, what),
               "find": lambda ref, what="object": picks.find(d(), ref, what), "snapshot": lambda tool: s.snapshot(tool), "V": V,
               # PartDesign: bodies, their features and their tip
               "pd_body": lambda ref: pdc.pd_body(d(), ref), "body_of": pdc.body_of, "in_body": pdc.in_body, "broken": lambda: pdc.newly_broken(d()),
               "solid_feature": solid_feature, "after_tip": after_tip, "profile_sketch": profile_sketch, "reattach": reattach, "shaft_solid": shaft_solid}

    st = {"type": "string"}
    arr = {"type": "array", "items": {"type": "string"}}
    num = {"type": "number"}
    v3 = {"type": "array", "items": num}
    helpers.update(part_helpers)
    return runners.tools(GROUP, s, helpers) + [
        Tool("doc_graph", "What is built from what in the document (Std Dependency graph): roots (objects nothing uses), uses { label: [its inputs] }, counts; path writes a GraphViz .dot (svg: true also draws it when GraphViz's dot is on this computer; the note says when it is not). Changes nothing.",
             obj({"path": st, "svg": {"type": "boolean"}}), doc_graph),
        Tool("object_freeze", "Freeze objects (objects; frozen: false thaws) so recomputes leave their shapes as they are (Std Toggle freeze) — window only: FreeCAD 1.1 has no headless call for it, and the frozen state is not saved with the file. skipRecompute: true | false switches the whole document's recomputes off or on (works headless; recompute { force: true } still runs). Reply: frozen / unfrozen, not (those that did not take), skipRecompute. After thawing: recompute { force: true }.",
             obj({"objects": arr, "frozen": {"type": "boolean"}, "skipRecompute": {"type": "boolean"}}), object_freeze, changes=True),
        Tool("units_convert", "A quantity in other units (FreeCAD's units calculator): value a number with its unit (\"2.5 in\", \"300 N*m\", \"45 deg\"), to a unit of the same kind (\"mm\", \"lbf*ft\", \"rad\"; * / ^ join units). Different kinds are refused. Reply: result (a number), text. Changes nothing.",
             obj({"value": {}, "to": st}, ["value", "to"]), units_convert),
        Tool("object_align", "Place an object by point pairs (what Std Alignment does by clicking): pairs [[from: a point on it now, to: where that point should be] …] in mm, document coordinates. One or two pairs move it only; three or more (not in a line) turn it too, the least-squares rigid fit — no scaling. Reply: rms and worst miss in mm (near 0 when the pairs agree), placement. Changes Placement only.",
             obj({"object": st, "pairs": {"type": "array", "items": {"type": "array"}}}, ["object", "pairs"]), object_align, changes=True),
        Tool("link_make", "A link (App::Link) to an object: it shows the object again without copying it and follows every change. to: the object (or \"Box.Face3\" for one element); at, axis + angle: the link's placement, which stands in for the original's own, not added to it; count: an array of that many elements, all starting at the same place, each its own object to place with object_set (reply: elements). kind: group makes an App::LinkGroup of objects. Reply: link, name, to, placement.",
             obj({"to": st, "kind": {"type": "string", "enum": ["link", "group"]}, "objects": arr, "at": v3, "axis": v3, "angle": num, "count": {"type": "integer"}, "name": st}), link_make, changes=True),
        Tool("link_edit", "Change links: action replace { link, to } (point it at another object) | unlink { link, name } (a plain shape copy in its place, same placement; what used the link now uses the copy) | import { links } / import_all (objects linked from another document copied into this one). object_group { action: \"list\" } names the links.",
             obj({"action": {"type": "string", "enum": ["replace", "unlink", "import", "import_all"]}, "link": st, "links": arr, "to": st, "name": st}, ["action"]), link_edit, changes=True),
        Tool("object_duplicate", "Copy objects in the document (Std Duplicate): each copy is independent but still built from the same inputs (a copied Pad uses the original's sketch); dependencies: true copies what each is built from too; simple: true copies the shape alone as a plain Part::Feature (no history, placement baked in). name: the copy's label (\"<label> copy\" by default). Reply: duplicated [{ from, copy }].",
             obj({"objects": arr, "dependencies": {"type": "boolean"}, "simple": {"type": "boolean"}, "name": st}, ["objects"]), object_duplicate, changes=True),
        Tool("doc_merge", "Bring every object of another .FCStd into this document (File > Merge document): path (relative: the session's folder). Internal names that clash get a number (labels too, unless FreeCAD's duplicate-labels preference is on). Recomputes. Reply: count, objects, errors. import_file is for STEP, STL and other formats.", obj({"path": st}, ["path"]), doc_merge, changes=True),
        Tool("doc_info", "The document's information (File > Document information): author, company, comment, license, licenseUrl, lastModifiedBy, label — the ones given are set (text), nothing given just reads. Reply: those, id, uid, created and modified dates, file, objects, bytes. Setting label renames the document as the person sees it; its internal name stays.",
             obj({k: st for k in ("author", "company", "comment", "license", "licenseUrl", "lastModifiedBy", "label")}), doc_info),
        Tool("doc_revert", "Go back to the document's saved file, dropping every unsaved change (Std Revert): the document is closed and opened again, so the session's undo steps go too. Refused for a document never saved. Ask the person first unless the changes are only the agent's. Reply: document, reverted (the file), objects.", obj({}), doc_revert),
        Tool("doc_save_all", "Save every open document that has a file (Std Save all), each to its own file. Documents never saved are not touched and are listed in neverSaved: doc_save { path } for each. Reply: saved [paths].", obj({}), doc_save_all),
        Tool("text_document", "A text document kept in the file (App::TextDocument), for notes that travel with the model: name (found by label, made if new; \"Notes\" by default), text replaces what it holds, append: true adds a line instead; with no text it only reads the size. Reply: text (its label), chars, lines. It shows in the tree; the person reads it by double-clicking.",
             obj({"name": st, "text": st, "append": {"type": "boolean"}}), text_document, changes=True),
        Tool("object_appearance", "Colour objects: color \"#rrggbb\" or [r,g,b] 0–1 (or random: true), transparency 0 (solid) – 100, faces { \"Face3\": \"#ff0000\" } a colour per face (the rest keep the object's colour; face numbers change after a modelling step: shape_query again). Shown at once in the window; headless they are kept on the object (AgentLinkColor …) and exports read them. Reply: set [{ object, color, transparency, faces, shown }].",
             obj({"objects": arr, "color": {}, "random": {"type": "boolean"}, "transparency": {"type": "integer"}, "faces": {"type": "object"}}, ["objects"]), object_appearance, changes=True),
        Tool("scad_tidy", "OpenSCAD workbench's tree tools on objects: action color_code (all shapes when no objects: coloured by validity and kind — the reply's key; as FreeCAD's own Color Shapes it recomputes nothing and leaves no object touched that was not before) | explode (a top-level Part::Fuse / MultiFuse / Compound deleted, its inputs kept, shown and moved by its placement) | expand_placements (placements pushed down to the leaves) | tolerance { vertex, edge, face mm } (a copy with tolerances raised to at least these, never lowered; the original hidden) | remove_subtree (objects and everything under them that nothing else uses — deleted for good) | replace { parent, old, new } (parent uses new where it used old). Reply by action: coloured, exploded, expanded, made, removed, replaced.",
             obj({"action": {"type": "string", "enum": ["color_code", "explode", "expand_placements", "tolerance", "remove_subtree", "replace"]}, "objects": arr, "vertex": num, "edge": num, "face": num, "parent": st, "old": st, "new": st}, ["action"]), scad_tidy, changes=True),
        Tool("robot_tool", "Draw a tool shape on a robot's flange (Robot's Add tool shape): robot, tool (an object with a shape), at / axis + angle where on the shape the flange sits (ToolBase). Shown in the window only; it does not change the kinematics or the tool point (robot_new tool does).", obj({"robot": st, "tool": st, "at": v3, "axis": v3, "angle": num}, ["robot", "tool"]), robot_tool, changes=True),
        Tool("sheet_cells", "Merge spreadsheet cells (merge \"A1:C1\": the top-left cell stays, the others are cleared with their aliases) or split a merged one (split \"A1\", any of its cells). sheet_format { merge } does the same and first checks for aliases in use.", obj({"sheet": st, "merge": st, "split": st}, ["sheet"]), sheet_cells, changes=True),
    ]
