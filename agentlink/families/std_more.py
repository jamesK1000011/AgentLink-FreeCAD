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
        lk = d().addObject("App::Link", "Link")
        if sub:
            lk.LinkedObject = (src, [sub])
        else:
            lk.LinkedObject = src
        lk.Label = s.unique(a.get("name") or f"{src.Label} link", lk)
        if picks.placed(a):
            lk.Placement = picks.placement(a)
        if a.get("count"):
            lk.ElementCount = int(a["count"])
        return done("link_make", {"link": lk.Label, "to": src.Label, **({"element": sub} if sub else {}),
                                  **({"count": int(a["count"])} if a.get("count") else {}),
                                  "note": "A link shows the object again without a copy: change the original and every link follows."})

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
            raise bad(f"{lk.Label} is not a link ({lk.TypeId}).")
        if act == "replace":
            to = picks.find(d(), a.get("to"), "to")
            lk.LinkedObject = to
            return done("link_edit", {"link": lk.Label, "now": to.Label})
        if act == "unlink":
            # A real copy in the link's place, keeping its placement.
            src = lk.LinkedObject[0] if isinstance(lk.LinkedObject, tuple) else lk.LinkedObject
            if src is None:
                raise ToolError("invalid_state", f"{lk.Label} links to nothing.")
            o = d().addObject("Part::Feature", "Body")
            sh = Part.getShape(lk)
            o.Shape = sh
            o.Label = s.unique(a.get("name") or src.Label, o)
            # Everything that used the link (groups, features, joints,
            # expressions) now uses the copy: nothing left dangling.
            moved = picks.repoint(d(), lk, o)
            d().removeObject(lk.Name)
            d().recompute()
            return done("link_edit", {"copy": o.Label, "from": src.Label, "volume": round(sh.Volume, 3) if sh.Solids else None, **({"repointed": moved} if moved else {})})
        raise bad("action: replace { link, to } | unlink { link } | import { links } | import_all.")

    def part_container(a):
        p = d().addObject("App::Part", "Part")
        p.Label = s.unique(a.get("name") or "Part", p)
        members = objs(a["objects"]) if a.get("objects") else []
        for m in members:
            for g in [x for x in m.InList if x.TypeId == "App::Part"]:
                g.removeObject(m)
            p.addObject(m)
        if picks.placed(a):
            p.Placement = picks.placement(a)
        return done("part_container", {"part": p.Label, "objects": [m.Label for m in members], "note": "An App::Part moves everything in it together, by its placement."})

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
        p = os.path.expanduser(a.get("path") or "")
        if not os.path.isfile(p):
            raise ToolError("not_found", f"path {p!r}: no such file — an .FCStd to bring in.")
        before = {o.Name for o in d().Objects}
        d().mergeProject(p)
        d().recompute()
        new = [o.Label for o in d().Objects if o.Name not in before]
        s.snapshot("doc_merge")
        return {"merged": os.path.basename(p), "objects": new}

    INFO_PROPS = {"author": "CreatedBy", "company": "Company", "comment": "Comment", "license": "License", "licenseUrl": "LicenseURL", "lastModifiedBy": "LastModifiedBy", "id": "Id", "uid": "Uid", "label": "Label"}

    def doc_info(a):
        dd = d()
        for k, prop in INFO_PROPS.items():
            if k in a and k not in ("id", "uid"):
                setattr(dd, prop, str(a[k]))
        return {"document": dd.Name, "file": dd.FileName or None, **{k: str(getattr(dd, p, "")) for k, p in INFO_PROPS.items()},
                "created": str(getattr(dd, "CreationDate", "")), "modified": str(getattr(dd, "LastModifiedDate", "")),
                "objects": len(dd.Objects), "bytes": os.path.getsize(dd.FileName) if dd.FileName and os.path.isfile(dd.FileName) else None}

    def doc_revert(a):
        dd = d()
        if not dd.FileName or not os.path.isfile(dd.FileName):
            raise ToolError("invalid_state", f"{dd.Label} was never saved: nothing to go back to.")
        path, label = dd.FileName, dd.Label
        FreeCAD.closeDocument(dd.Name)
        nd = FreeCAD.openDocument(path)
        s.switch(nd)
        return {"document": nd.Name, "label": label, "reverted": path, "objects": len(nd.Objects), "note": "Back to the saved file: unsaved changes are gone."}

    def doc_save_all(a):
        saved, unsaved = [], []
        for name, dd in FreeCAD.listDocuments().items():
            if dd.FileName:
                dd.save()
                from .doc import _gui_saved

                _gui_saved(dd)
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
            if a.get("transparency") is not None:
                t = int(a["transparency"])
                if not 0 <= t <= 100:
                    raise bad("transparency: 0 (solid) to 100 (clear).")
                keep_colour(o, "AgentLinkTransparency", "App::PropertyInteger", t)
                if vo is not None and hasattr(vo, "Transparency"):
                    vo.Transparency = t
                e["transparency"] = t
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
            e["shown"] = vo is not None
            out.append(e)
        d().recompute()
        return {"set": out, **({"note": "No window here: the colours are kept on the objects and show when the file opens in FreeCAD."} if not any(x["shown"] for x in out) else {})}

    # ---- Part: compounds, joins, curve networks ------------------------------------------

    def compound_explode(a):
        import CompoundTools.Explode as X

        o = picks.shaped(d(), a.get("compound"), "compound")
        if len(o.Shape.childShapes()) < 2:
            raise ToolError("invalid_state", f"compound: {o.Label} is one {o.Shape.ShapeType.lower()}, nothing to explode — a compound of several pieces is (part_compound makes one; a part_split result is one).")
        g, children = X.explodeCompound(o)
        if hasattr(o, "Visibility"):
            # As Part's Explode compound command: the pieces stand in for it.
            o.Visibility = False
        d().recompute()
        s.snapshot("compound_explode")
        return {"group": g.Label, "pieces": [{"name": c.Label, "volume": round(c.Shape.Volume, 3) if c.Shape.Solids else None} for c in children]}

    def compound_filter(a):
        import CompoundTools.CompoundFilter as CF

        o = picks.shaped(d(), a.get("compound"), "compound")
        n = len(o.Shape.childShapes())
        how = a.get("keep", "items")
        # FreeCAD's FilterType: bypass, specific items, collision-pass,
        # window-volume, window-area, window-length, window-distance.
        # collision-fail is collision-pass with Invert; window-distribution
        # was this tool's old word for window-distance.
        kinds = {"collision-pass": ("collision-pass", False), "collision-fail": ("collision-pass", True), "window-volume": ("window-volume", False),
                 "window-area": ("window-area", False), "window-length": ("window-length", False), "window-distance": ("window-distance", False),
                 "window-distribution": ("window-distance", False)}
        if how != "items" and how not in kinds:
            raise bad("keep: items { items: [0, 2] } | collision-pass / collision-fail { stencil } | window-volume / window-area / window-length { from, to } | window-distance { stencil, from, to }.")
        stencil = picks.shaped(d(), a["stencil"], "stencil") if a.get("stencil") else None
        if how != "items" and kinds[how][0] in ("collision-pass", "window-distance") and stencil is None:
            raise bad(f"stencil: {how} needs one — the object the pieces are tested against (touching it, or their distance from it).")
        items = a.get("items")
        if how == "items":
            items = [0] if items is None else items
            wrong = [i for i in items if isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < n]
            if wrong or not items:
                raise bad(f"items: the pieces to keep by number from 0 — {o.Label} has {n} (0 … {n - 1})" + (f"; {wrong[0]!r} is not one of them." if wrong else "."))
        # In the session's document (makeCompoundFilter alone adds to FreeCAD.ActiveDocument).
        f = CF.makeCompoundFilter("CompoundFilter", d())
        f.Label = s.unique(a.get("name") or f"{o.Label} filtered", f)
        f.Base = o
        if how == "items":
            f.FilterType = "specific items"
            f.items = ";".join(str(i) for i in items)
        else:
            f.FilterType, f.Invert = kinds[how]
            if stencil is not None:
                f.Stencil = stencil
            if a.get("from") is not None:
                f.WindowFrom = float(a["from"])
            if a.get("to") is not None:
                f.WindowTo = float(a["to"])
        d().recompute()
        if f.Shape.isNull() or "Invalid" in (getattr(f, "State", None) or []):
            why = "no piece touches the stencil" if how == "collision-pass" else "every piece touches the stencil" if how == "collision-fail" else \
                f"no piece lies within {f.WindowFrom:g} … {f.WindowTo:g}% of the largest (or of the stencil's)" if how.startswith("window") else "nothing passed"
            raise ToolError("failed", f"The filter keeps nothing of {o.Label} ({how}): {why} — nothing was made.")
        if getattr(o, "ViewObject", None) is not None:
            o.ViewObject.Visibility = False
        s.snapshot("compound_filter")
        return {"filter": f.Label, "kept": len(f.Shape.childShapes()) if f.Shape.ShapeType == "Compound" else 1}

    def part_join(a):
        import BOPTools.JoinFeatures as J

        kind = a.get("kind")

        def feature(proxy, view, default):
            # In the session's document: BOPTools' make* add to
            # FreeCAD.ActiveDocument, which is not always this one.
            j = d().addObject("Part::FeaturePython", default)
            proxy(j)
            if FreeCAD.GuiUp and getattr(j, "ViewObject", None) is not None:
                view(j.ViewObject)
            j.Label = s.unique(a.get("name") or default, j)
            return j

        if kind == "connect":
            members = [picks.shaped(d(), r, "objects") for r in picks.ref_list(a.get("objects"), "objects: two or more walled objects (pipes, shells) by name.")]
            if len(members) < 2:
                raise bad("objects: two or more walled objects (pipes, shells) by name.")
            j = feature(J.FeatureConnect, J.ViewProviderConnect, "Connect")
            j.Objects = members
        elif kind in ("embed", "cutout"):
            base, tool = picks.shaped(d(), a.get("base"), "base"), picks.shaped(d(), a.get("tool"), "tool")
            if base is tool:
                raise bad("base and tool: two different objects.")
            j = feature(J.FeatureEmbed, J.ViewProviderEmbed, "Embed") if kind == "embed" else feature(J.FeatureCutout, J.ViewProviderCutout, "Cutout")
            j.Base, j.Tool = base, tool
            members = [base, tool]
        else:
            raise bad("kind: connect { objects } (walls fused, insides kept) | embed { base, tool } (tool's wall set into base) | cutout { base, tool } (base cut to fit tool's wall).")
        d().recompute()
        sh = j.Shape
        if sh.isNull() or "Invalid" in (getattr(j, "State", None) or []):
            raise ToolError("failed", f"The {kind} failed: {j.getStatusString()} — nothing was made. The objects' walls must cross one another (part_section {{ body, with }} shows whether they meet).")
        for m in members:
            # As Part's join commands: the inputs are hidden under the result.
            if hasattr(m, "Visibility"):
                m.Visibility = False
        s.snapshot("part_join")
        return {"join": j.Label, "kind": kind, "valid": sh.isValid(), "solids": len(sh.Solids), "volume": round(sh.Volume, 3) if sh.Solids else None}

    def part_import_curves(a):
        if not isinstance(a.get("path"), str) or not a["path"].strip():
            raise bad("path: a STEP, IGES or BREP file with curves (a relative path is in the session's folder).")
        # As every other reader: a relative path is in the session's folder.
        p = paths.in_file(s, "part_import_curves", a["path"])
        if not os.path.isfile(p):
            raise ToolError("not_found", f"path {p!r}: no such file — a STEP, IGES or BREP with curves; a relative path is looked for in the session's folder.")
        try:
            sh = Part.read(p)
        except Exception as e:
            raise ToolError("failed", f"FreeCAD could not read {os.path.basename(p)} ({e}): a .step / .stp, .iges / .igs or .brep file. Nothing was added.")
        edges = sh.Edges
        if not edges:
            raise ToolError("invalid_input", f"{os.path.basename(p)} has no curves: nothing was added.")
        o = d().addObject("Part::Feature", "CurveNet")
        o.Shape = Part.Compound(edges)
        o.Label = s.unique(a.get("name") or os.path.splitext(os.path.basename(p))[0], o)
        return done("part_import_curves", {"curves": o.Label, "edges": len(edges), "note": "Edges only (faces are left out): surface_fill or surface_sections builds faces from them."})

    # ---- PartDesign ------------------------------------------------------------------------

    def pd_move_feature(a):
        f = picks.find(d(), a.get("feature"), "feature")
        if not f.TypeId.startswith(("PartDesign::", "Sketcher::", "Part::Part2DObject")) or f.TypeId == "PartDesign::Body":
            raise bad(f"feature: {f.Label} is a {f.TypeId.split('::')[-1]}, not a PartDesign feature or sketch — a whole solid goes into a body with pd_clone.")
        src = pdc.body_of(f)
        to = pdc.pd_body(d(), a.get("to"))
        if src is to:
            raise bad(f"{f.Label} is in {to.Label} already: to takes another body (pd_reorder moves it within this one).")
        broken0 = {x["object"] for x in pdc.broken(d())}
        moved = [f]
        # A sketch's feature takes its sketch along, as the GUI's Move does.
        prof = getattr(f, "Profile", None)
        sk = prof[0] if isinstance(prof, tuple) else prof
        if sk is not None and sk.TypeId == "Sketcher::SketchObject" and src is not None and src.hasObject(sk):
            moved.insert(0, sk)
        for o in moved:
            if src is not None:
                src.removeObject(o)
            to.addObject(o)
            sp = pdc.support_prop(o)
            sup = getattr(o, sp, None)
            if o.TypeId == "Sketcher::SketchObject" and src is not None and sup:
                # Origin planes are per body: re-attach to the same plane of the new body.
                ref = sup[0][0] if isinstance(sup, list) else None
                if ref is not None and src.Origin.hasObject(ref):
                    role = ref.Role if hasattr(ref, "Role") else ref.Label
                    new = next((x for x in to.Origin.OriginFeatures if getattr(x, "Role", x.Label) == role), None)
                    if new is not None:
                        setattr(o, sp, [(new, "")])
        d().recompute()
        new_broken = [x["object"] for x in pdc.broken(d()) if x["object"] not in broken0]
        if new_broken:
            # Raised inside the tool's transaction: the move is taken back.
            raise ToolError("invalid_state", f"Moving {f.Label} to {to.Label} breaks {', '.join(map(str, new_broken))} — nothing was moved. A pocket, hole or fillet needs the solid it works on: move the features before it first (the first pad first), or rebuild it in {to.Label}.")
        s.snapshot("pd_move_feature")
        return {"moved": [o.Label for o in moved], "from": src.Label if src else None, "to": to.Label, "tip": to.Tip.Label if to.Tip else None}

    def pd_reorder(a):
        f = picks.find(d(), a.get("feature"), "feature")
        b = pdc.body_of(f)
        if b is None:
            raise ToolError("invalid_state", f"{f.Label} is not in a PartDesign body: pd_reorder moves a body's own features and sketches (feature_list names them).")
        if a.get("after") and a.get("before"):
            raise bad("after or before, one of them: the feature to put it next to.")
        where = "after" if a.get("after") else "before"
        target = pdc.in_body(b, a.get(where), what=where) if a.get(where) else None
        if target is None:
            raise bad("after or before: the feature of the same body to put it next to (feature_list gives the order).")
        if target is f:
            raise bad(f"{where}: another feature than {f.Label} itself.")
        broken0 = {x["object"] for x in pdc.broken(d())}
        tip_was = b.Tip
        b.removeObject(f)
        b.insertObject(f, target, where == "after")
        # Put after the tip, a feature would drop out of the body's shape
        # with nothing said: the tip goes with it, as in the window.
        moved_tip = False
        if where == "after" and tip_was is target:
            b.Tip = f
            moved_tip = True
        elif tip_was is f:
            b.Tip = f
        d().recompute()
        new_broken = [x["object"] for x in pdc.broken(d()) if x["object"] not in broken0]
        if new_broken:
            raise ToolError("invalid_state", f"{f.Label} {where} {target.Label} breaks {', '.join(map(str, new_broken))} — nothing was moved: a feature may only use what comes before it (its sketch, the faces and edges it names).")
        s.snapshot("pd_reorder")
        order = [o.Label for o in b.Group if not o.TypeId.startswith("App::Origin")]
        return {"body": b.Label, "order": order, "tip": b.Tip.Label if b.Tip else None, **({"tipMoved": True} if moved_tip else {}), **after_tip(b),
                "volume": round(b.Shape.Volume, 3) if not b.Shape.isNull() and b.Shape.Solids else None}

    def solid_feature(o):
        """What a body's tip may be: a feature with a solid of its own — not
        a sketch, a datum or a binder (Body::execute refuses those: "Linked
        object is not a PartDesign feature"), nor a MultiTransform's step."""
        if not o.isDerivedFrom("PartDesign::Feature"):
            return False
        return not any(x.TypeId == "PartDesign::MultiTransform" and o in x.Transformations for x in o.InList)

    def after_tip(b):
        """The solid features past the tip: kept, but not in the body's shape."""
        g = list(b.Group)
        if b.Tip is None or b.Tip not in g:
            return {}
        left = [o.Label for o in g[g.index(b.Tip) + 1:] if solid_feature(o)]
        return {"afterTip": left} if left else {}

    def pd_tip(a):
        b = pdc.pd_body(d(), a.get("body"))
        out = {}
        if a.get("feature"):
            f = pdc.in_body(b, a["feature"])
            was = b.Tip
            if not solid_feature(f):
                # As the window's Set tip does for a sketch or a datum: the
                # solid feature before it.
                g = list(b.Group)
                prev = next((o for o in reversed(g[:g.index(f)]) if solid_feature(o)), None)
                if prev is None:
                    raise bad(f"feature: {f.Label} is a {f.TypeId.split('::')[-1]} with no solid feature before it — the tip is a pad, pocket or other solid feature: "
                              f"{', '.join(o.Label for o in g if solid_feature(o)) or 'none yet'}.")
                out["note"] = f"{f.Label} is not a solid feature: the tip went to {prev.Label}, the one before it."
                f = prev
            broken0 = {x["object"] for x in pdc.broken(d())}
            b.Tip = f
            d().recompute()
            new_broken = [x["object"] for x in pdc.broken(d()) if x["object"] not in broken0]
            if new_broken:
                # Raised inside the tool's transaction: the tip goes back.
                raise ToolError("failed", f"With the tip at {f.Label}, {', '.join(map(str, new_broken))} failed — the tip stays at {was.Label if was else 'none'}.")
            s.snapshot("pd_tip")
            out["tipWas"] = was.Label if was else None
        return {"body": b.Label, "tip": b.Tip.Label if b.Tip else None, "volume": round(b.Shape.Volume, 3) if not b.Shape.isNull() and b.Shape.Solids else None, **after_tip(b), **out,
                "use": "The body's shape stops at the tip and new features go in right after it; features past it (afterTip) are kept but left out until the tip moves past them."}

    def pd_shaft(a):
        segs = a.get("segments") or []
        if not segs:
            raise bad("segments: [{ length, diameter }, …] in mm, from one end; a segment may also give diameterEnd for a taper.")
        pts, x = [V(0, 0, 0)], 0.0
        for i, sg in enumerate(segs):
            if not isinstance(sg, dict):
                raise bad(f"segment {i + 1}: {{ length, diameter }} in mm (diameterEnd for a taper).")
            L, D = float(sg.get("length", 0)), float(sg.get("diameter", 0))
            D2 = float(sg.get("diameterEnd", D))
            if L <= 0 or D <= 0 or D2 <= 0:
                raise bad(f"segment {i + 1}: length and diameter (and diameterEnd) in mm, over 0.")
            pts += [V(x, D / 2, 0), V(x + L, D2 / 2, 0)]
            x += L
        pts.append(V(x, 0, 0))
        clean = [pts[0]]
        for p in pts[1:]:
            if (p - clean[-1]).Length > 1e-9:
                clean.append(p)
        clean.append(pts[0])
        face = Part.Face(Part.makePolygon(clean))
        solid = face.revolve(V(0, 0, 0), V(1, 0, 0), 360)
        solid = Part.Solid(Part.Shell(solid.Faces)) if solid.ShapeType != "Solid" else solid
        if a.get("axis", "x") != "x":
            solid.rotate(V(0, 0, 0), V(0, 1, 0), -90) if a["axis"] == "z" else solid.rotate(V(0, 0, 0), V(0, 0, 1), 90)
        o = d().addObject("Part::Feature", "Shaft")
        o.Shape = solid.removeSplitter()
        o.Label = s.unique(a.get("name") or "Shaft", o)
        if picks.placed(a):
            o.Placement = picks.placement(a)
        return done("pd_shaft", {"shaft": o.Label, "length": round(x, 3), "segments": len(segs), "volume": round(o.Shape.Volume, 3),
                                 "note": "A plain Part solid, not in a PartDesign body: part_fillet or part_chamfer its sharp shoulders; pd_clone brings it into a body for pd_ features."})

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
                keep_colour(o, COLOR_PROP, "App::PropertyColor", c[:3])
                vo = getattr(o, "ViewObject", None)
                if vo is not None and hasattr(vo, "ShapeColor"):
                    vo.ShapeColor = c[:3]
                rows.append({"object": o.Label, "is": kind, "color": pal[kind]})
            return {"coloured": rows, "key": pal}
        if act == "explode":
            out = []
            for o in targets:
                if not (o.isDerivedFrom("Part::Fuse") or o.isDerivedFrom("Part::MultiFuse") or o.isDerivedFrom("Part::Compound")):
                    raise bad(f"{o.Label} is not a fusion or compound ({o.TypeId}).")
                if o.InList:
                    raise bad(f"{o.Label} is used by {o.InList[0].Label}: only a top-level one explodes.")
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
            replaceobj.replaceobj(parent, old, new)
            return done("scad_tidy", {"parent": parent.Label, "replaced": old.Label, "with": new.Label})
        raise bad("action: color_code | explode | expand_placements | tolerance { vertex, edge, face } | remove_subtree | replace { parent, old, new }.")

    def points_structure(a):
        o = picks.find(d(), a.get("points"), "points")
        if not o.isDerivedFrom("Points::Feature"):
            raise bad(f"{o.Label} is not a point cloud.")
        n = o.Points.CountPoints
        w = int(a.get("width") or 0)
        h = int(a.get("height") or (n // w if w else 0))
        if w <= 0 or w * h != n:
            raise bad(f"width × height must be the point count ({n}): a scanner's rows × columns.")
        st_ = d().addObject("Points::Structured", "Structured")
        st_.Points = o.Points
        st_.Width, st_.Height = w, h
        st_.Label = s.unique(a.get("name") or f"{o.Label} structured", st_)
        return done("points_structure", {"points": st_.Label, "width": w, "height": h})

    def surface_polynomial(a):
        import numpy as np

        o = picks.find(d(), a.get("from"), "from")
        if hasattr(o, "Mesh"):
            P = np.array([[p.x, p.y, p.z] for p in o.Mesh.Points])
        elif o.isDerivedFrom("Points::Feature"):
            P = np.array([[p.x, p.y, p.z] for p in o.Points.Points])
        else:
            raise bad(f"{o.Label}: a mesh or a point cloud.")
        if len(P) < 9:
            raise bad("At least 9 points.")
        # As Reen's Polynomial Surface: a quadric z(u, v) over the points'
        # best plane, made a 3×3 Bézier patch over their box.
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
        sp = d().addObject("Part::Spline", "Bezier")
        sp.Shape = bz.toShape()
        sp.Label = s.unique(a.get("name") or f"{o.Label} polynomial", sp)
        res = z - f(u, v)
        return done("surface_polynomial", {"surface": sp.Label, "points": len(P), "rms": round(float(np.sqrt((res ** 2).mean())), 4), "max": round(float(np.abs(res).max()), 4)})

    def robot_tool(a):
        r = picks.find(d(), a.get("robot"), "robot")
        if not r.isDerivedFrom("Robot::RobotObject"):
            raise bad(f"{r.Label} is not a robot.")
        t = picks.shaped(d(), a.get("tool"), "tool")
        r.ToolShape = t
        if picks.placed(a):
            r.ToolBase = picks.placement(a)
        return done("robot_tool", {"robot": r.Label, "tool": t.Label, "note": "The tool shape follows the robot's flange (its ToolBase offset)."})

    def sheet_cells(a):
        sh = picks.find(d(), a.get("sheet"), "sheet")
        if not sh.isDerivedFrom("Spreadsheet::Sheet"):
            raise bad(f"{sh.Label} is not a spreadsheet.")
        if a.get("merge"):
            sh.mergeCells(str(a["merge"]))
        if a.get("split"):
            sh.splitCell(str(a["split"]))
        if not a.get("merge") and not a.get("split"):
            raise bad("merge: \"A1:C1\" (one cell across them) or split: \"A1\" (a merged cell back apart).")
        cell = str(a.get("merge") or a.get("split")).split(":")[0]
        return done("sheet_cells", {"sheet": sh.Label, "merged": bool(a.get("merge")), "span": list(sh.getCellSpan(cell)) if hasattr(sh, "getCellSpan") else None})

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
                raise ToolError("unavailable", "Freezing objects works only through the FreeCAD window (FreeCAD gives no headless way): the window's link does it when it answers. skipRecompute works here.")
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
            out["note"] = "A frozen object keeps its shape through recomputes until unfrozen." if want else "Unfrozen: recompute brings them up to date."
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
            raise bad(f"{q!r} or {to!r} is not a quantity FreeCAD reads: {e}")
        if Q.Unit != U.Unit:
            raise bad(f"{q} and {to} measure different things ({Q.Unit} vs {U.Unit}).")
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
            raise bad("object, pairs [[from xyz on it, to xyz where it goes] …]: one pair moves it; three or more set its turn too.")
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
        o.Placement = FreeCAD.Placement(M).multiply(o.Placement)
        pl = o.Placement
        out = {"object": o.Label, "pairs": len(pairs), "rms": round(float(np.sqrt((miss ** 2).mean())), 4), "worst": round(float(miss.max()), 4),
               "placement": {"at": [round(x, 4) for x in pl.Base], "axis": [round(x, 5) for x in pl.Rotation.Axis], "angle": round(math.degrees(pl.Rotation.Angle), 4)}}
        if len(pairs) < 3:
            out["note"] = "Moved only: three or more pairs (not in a line) set its turn too."
        return done("object_align", out)

    # The wrappers kept as data (agentlink/data/tools.json) run on these.
    helpers = {"doc": d, "done": done, "unique": s.unique, "placed": picks.placed, "placement": picks.placement,
               "shaped": lambda ref, what: picks.shaped(d(), ref, what)}

    st = {"type": "string"}
    arr = {"type": "array", "items": {"type": "string"}}
    num = {"type": "number"}
    v3 = {"type": "array", "items": num}
    return runners.tools(GROUP, s, helpers) + [
        Tool("doc_graph", "What is built from what in the document (Std Dependency graph): roots and each object's inputs; path writes a GraphViz .dot (svg: true draws it when GraphViz is here). Changes nothing.",
             obj({"path": st, "svg": {"type": "boolean"}}), doc_graph),
        Tool("object_freeze", "Freeze objects (frozen: false thaws) so recomputes leave their shapes as they are (Std Toggle freeze); skipRecompute: true | false for the document (Std Toggle skip recompute).",
             obj({"objects": arr, "frozen": {"type": "boolean"}, "skipRecompute": {"type": "boolean"}}), object_freeze, changes=True),
        Tool("units_convert", "A quantity in other units (the Units calculator): value \"2.5 in\", to \"mm\". Changes nothing.",
             obj({"value": {}, "to": st}, ["value", "to"]), units_convert),
        Tool("object_align", "Place an object by point pairs (Std Alignment): pairs [[from on it, to where it goes] …] in mm; one pair moves it, three or more (not in a line) turn it too — the best fit, with its rms and worst miss.",
             obj({"object": st, "pairs": {"type": "array", "items": {"type": "array"}}}, ["object", "pairs"]), object_align, changes=True),
        Tool("link_make", "A link (App::Link): to an object (or \"Box.Face3\" for one element), at a placement, count for an array of links; kind: group makes an App::LinkGroup of objects. Shows the object again without copying it.",
             obj({"to": st, "kind": {"type": "string", "enum": ["link", "group"]}, "objects": arr, "at": v3, "axis": v3, "angle": num, "count": {"type": "integer"}, "name": st}), link_make, changes=True),
        Tool("link_edit", "Change links: action replace { link, to } | unlink { link } (a real copy in its place) | import { links } / import_all (objects linked from another document copied in).",
             obj({"action": {"type": "string", "enum": ["replace", "unlink", "import", "import_all"]}, "link": st, "links": arr, "to": st, "name": st}, ["action"]), link_edit, changes=True),
        Tool("part_container", "An App::Part container holding objects, moved together by its placement (Std Part): objects [names], at, axis + angle. Not a solid: booleans take the bodies inside it.",
             obj({"objects": arr, "at": v3, "axis": v3, "angle": num, "name": st}), part_container, changes=True),
        Tool("object_duplicate", "Copy objects in the document; dependencies: true copies what each is built from too; simple: true copies the shape alone (no history).",
             obj({"objects": arr, "dependencies": {"type": "boolean"}, "simple": {"type": "boolean"}, "name": st}, ["objects"]), object_duplicate, changes=True),
        Tool("doc_merge", "Bring another .FCStd's objects into this document (Merge document).", obj({"path": st}, ["path"]), doc_merge, changes=True),
        Tool("doc_info", "The document's information: author, company, comment, license, licenseUrl, label — given ones are set; created and modified dates, file, size.",
             obj({k: st for k in ("author", "company", "comment", "license", "licenseUrl", "lastModifiedBy", "label")}), doc_info),
        Tool("doc_revert", "Go back to the document's saved file, dropping unsaved changes.", obj({}), doc_revert),
        Tool("doc_save_all", "Save every open document that has a file.", obj({}), doc_save_all),
        Tool("text_document", "A text document in the file (App::TextDocument): name, text (append: true adds to it). Notes that travel with the model.",
             obj({"name": st, "text": st, "append": {"type": "boolean"}}), text_document, changes=True),
        Tool("object_appearance", "Colour objects: color \"#rrggbb\" or random: true, transparency 0–100, faces { \"Face3\": \"#ff0000\" } for a colour per face. Kept on the object, shown in the window.",
             obj({"objects": arr, "color": {}, "random": {"type": "boolean"}, "transparency": {"type": "integer"}, "faces": {"type": "object"}}, ["objects"]), object_appearance, changes=True),
        Tool("compound_explode", "Split a compound into its pieces (Part Explode compound): each a filter object that follows the compound, in a group; the compound is hidden. part_compound { explode } gives plain bodies instead.", obj({"compound": st}, ["compound"]), compound_explode, changes=True),
        Tool("compound_filter", "Keep some pieces of a compound (Part Compound filter): keep items { items: [0, 2], from 0 } | collision-pass / collision-fail { stencil: touching it or not } | window-volume / -area / -length { from, to as percents of the largest piece } | window-distance { stencil, from, to }. Refused when nothing passes; the compound is hidden. Reply: filter, kept.",
             obj({"compound": st, "keep": st, "items": {"type": "array", "items": {"type": "integer"}}, "stencil": st, "from": num, "to": num, "name": st}, ["compound"]), compound_filter, changes=True),
        Tool("part_join", "Join walled objects (Part join features; inputs hidden): kind connect { objects } fuses walls keeping the insides; embed { base, tool } sets tool into base; cutout { base, tool } cuts base to fit tool's wall. Pipes and tanks. Reply: valid, solids, volume.",
             obj({"kind": {"type": "string", "enum": ["connect", "embed", "cutout"]}, "objects": arr, "base": st, "tool": st, "name": st}, ["kind"]), part_join, changes=True),
        Tool("part_import_curves", "Import a curve network (the edges of a STEP, IGES or BREP; faces left out) as one object, for surface_fill or surface_sections: path (relative: in the session's folder).", obj({"path": st, "name": st}, ["path"]), part_import_curves, changes=True),
        Tool("pd_move_feature", "Move a PartDesign feature (with its sketch, re-attached to the same origin plane) to another body: feature, to. It goes after that body's tip. Refused, with nothing moved, when it or what is left behind then fails (a pocket needs a solid to cut). Reply: moved, from, to, tip.",
             obj({"feature": st, "to": st}, ["feature", "to"]), pd_move_feature, changes=True),
        Tool("pd_reorder", "Move a feature or sketch in its body's history: after or before another one of the same body. Refused, with nothing moved, when something would then use what comes after it. Put after the tip, it becomes the tip. Reply: order, tip, afterTip (solid features past the tip, left out of the shape), volume.",
             obj({"feature": st, "after": st, "before": st}, ["feature"]), pd_reorder, changes=True),
        Tool("pd_tip", "Read (no feature) or set a body's tip: the solid feature its shape stops at, and after which new features go in. A sketch or datum given: the solid feature before it. Features past the tip are kept but left out (afterTip) — set it back to the last one when done. Reply: tip, tipWas, afterTip, volume.",
             obj({"body": st, "feature": st}), pd_tip, changes=True),
        Tool("scad_tidy", "OpenSCAD workbench's tree tools: action color_code (shapes coloured by validity and type) | explode (a fusion or compound back into its pieces) | expand_placements | tolerance { vertex, edge, face mm } (a looser-tolerance copy) | remove_subtree (objects and children nothing else uses) | replace { parent, old, new }.",
             obj({"action": {"type": "string", "enum": ["color_code", "explode", "expand_placements", "tolerance", "remove_subtree", "replace"]}, "objects": arr, "vertex": num, "edge": num, "face": num, "parent": st, "old": st, "new": st}, ["action"]), scad_tidy, changes=True),
        Tool("points_structure", "Make a point cloud structured (rows × columns, as a scanner's grid): width, height.", obj({"points": st, "width": {"type": "integer"}, "height": {"type": "integer"}, "name": st}, ["points", "width"]), points_structure, changes=True),
        Tool("surface_polynomial", "A polynomial (quadric) surface fitted to a mesh or point cloud, as a Bézier patch (Reverse Engineering's Polynomial Surface): its rms and max distance from the points.",
             obj({"from": st, "name": st}, ["from"]), surface_polynomial, changes=True),
        Tool("robot_tool", "Put a tool shape on a robot's flange (Robot's Add tool shape): tool, at for its offset.", obj({"robot": st, "tool": st, "at": v3, "axis": v3, "angle": num}, ["robot", "tool"]), robot_tool, changes=True),
        Tool("sheet_cells", "Merge spreadsheet cells (merge \"A1:C1\") or split a merged one (split \"A1\").", obj({"sheet": st, "merge": st, "split": st}, ["sheet"]), sheet_cells, changes=True),
        Tool("pd_shaft", "A stepped shaft (the shaft wizard's geometry) as one plain Part solid, not in a PartDesign body: segments [{ length, diameter, diameterEnd (a taper) }] mm, from one end along axis x (or y, z); at, name. Reply: shaft, length, volume. part_fillet its shoulders; pd_clone brings it into a body.",
             obj({"segments": {"type": "array", "items": {"type": "object"}}, "axis": {"type": "string", "enum": ["x", "y", "z"]}, "at": v3, "name": st}, ["segments"]), pd_shaft, changes=True),
    ]
