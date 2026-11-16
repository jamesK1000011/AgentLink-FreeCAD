# SPDX-License-Identifier: LGPL-2.1-or-later
# CAM's remaining commands, headless: path objects (area, from a shape, path
# from edges, compound, array), program flow (stop, fixture offset, custom
# G-code), the property bag, and the job template export; Draft's dimension
# flip and heal; Assembly's rigid groups and a new empty part. The ops CAM
# makes like any other (3D pocket, tapping, mill facing, probe, flute) are
# cam_op kinds.

import json
import os

import FreeCAD

from .. import paths
from ..protocol import Tool, ToolError, bad
from ..tools import obj
from . import picks

GROUP = "cam_more"
INFO = "CAM paths from areas and shapes, compound, array, stop, fixture offsets, property bags, job templates."


def _cam(what):
    try:
        import Path  # noqa: F401

        return True
    except ImportError:
        raise ToolError("unavailable", f"{what} needs FreeCAD's CAM workbench, not in this build.")


def tools(s):
    def d():
        if s.doc is None:
            raise ToolError("invalid_state", "No document open: doc_new first.")
        return s.doc

    def job_of(ref):
        from .cam import _job

        return _job(d(), ref)

    def into_job(o, job):
        if job is not None:
            job.Operations.addObject(o)

    def set_props(o, props):
        for k, v in (props or {}).items():
            if k not in o.PropertiesList:
                raise bad(f"props.{k}: {o.Label} has no such property (object_get lists them).")
            try:
                setattr(o, k, v)
            except Exception as e:
                raise bad(f"props.{k} = {v!r}: {e}") from None

    def ops_of(refs, why):
        got = [picks.find(d(), r, "ops") for r in (refs or [])]
        if not got:
            raise bad(f"ops: {why}")
        nopath = [o.Label for o in got if getattr(o, "Path", None) is None]
        if nopath:
            raise bad(f"ops: {', '.join(nopath)} {'is' if len(nopath) == 1 else 'are'} not CAM paths (cam_list lists a job's operations).")
        return got

    def gcode(o):
        p = getattr(o, "Path", None)
        return [c.toGCode() for c in p.Commands] if p is not None else []

    def cam_path(a):
        _cam("A CAM path")
        kind = a.get("kind")
        job = job_of(a["job"]) if a.get("job") else None
        name = a.get("name")
        if kind == "area":
            # Path::FeatureArea: sections and offsets of shapes, the engine CAM's ops use.
            srcs = [picks.shaped(d(), r, "sources") for r in (a.get("sources") or [])]
            if not srcs:
                raise bad("sources: the shapes to work from (labels), one or more.")
            o = d().addObject("Path::FeatureArea", "Area")
            o.Sources = srcs
            if a.get("workplane"):
                label, sub, sh = picks.resolve(s, a["workplane"])
                if sub is None or not sub.startswith("Face"):
                    raise bad("workplane: \"Body.Face3\", a flat face the sections are taken parallel to.")
                o.WorkPlane = sh
            set_props(o, a.get("props"))
        elif kind == "from_shape":
            srcs = [picks.shaped(d(), r, "sources") for r in (a.get("sources") or [])]
            if not srcs:
                raise bad("sources: wires or edges to turn into a path (labels), one or more.")
            o = d().addObject("Path::FeatureShape", "PathShape")
            o.Sources = srcs
            into_job(o, job)
        elif kind == "edges":
            try:
                from Path.Op.Gui.PathShape import ObjectPathShape
            except ImportError:
                raise ToolError("unavailable", f"Path from Shape with a tool controller cannot be made here on FreeCAD {'.'.join(FreeCAD.Version()[:3])} (there it is a command of the CAM workbench's window): kind from_shape makes the same path without a tool controller, and cam_op {{ kind: \"engrave\", base }} follows edges with the job's tool.") from None
            o = d().addObject("Path::FeaturePython", "PathShape")
            ObjectPathShape(o, job)
            o.Base = [(picks.shaped(d(), r, "sources"), []) for r in (a.get("sources") or [])]
            into_job(o, job)
        elif kind == "compound":
            members = ops_of(a.get("ops"), "the paths to run as one, in order.")
            o = d().addObject("Path::FeatureCompound", "Compound")
            o.Group = members
            into_job(o, job)
        elif kind == "array":
            from Path.Op.Gui.Array import ObjectArray

            members = ops_of(a.get("ops"), "the operations to repeat.")
            if getattr(members[0], "ToolController", None) is None:
                raise bad(f"ops: {members[0].Label} has no tool controller; give operations made by cam_op.")
            o = d().addObject("Path::FeaturePython", "Array")
            ObjectArray(o)
            o.Base = members
            o.ToolController = members[0].ToolController
            set_props(o, a.get("props"))
            into_job(o, job)
        elif kind == "stop":
            from Path.Op.Gui.Stop import Stop

            o = d().addObject("Path::FeaturePython", "Stop")
            Stop(o)
            o.Stop = "Mandatory" if a.get("mandatory") else "Optional"
            into_job(o, job)
        elif kind == "fixture":
            from Path.Main.Gui.Fixture import Fixture

            o = d().addObject("Path::FeaturePython", "Fixture")
            Fixture(o)
            allowed = list(o.getEnumerationsOfProperty("Fixture") or [])
            want = str(a.get("fixture", "G54")).upper()
            if want not in allowed:
                d().removeObject(o.Name)
                raise bad(f"fixture {a.get('fixture')!r}: one of {', '.join(allowed)}.")
            o.Fixture = want
            o.Active = True
            into_job(o, job)
        else:
            raise bad("kind: area { sources, workplane, props } | from_shape { sources } | edges { sources, job } | compound { ops } | array { ops, props: { Type, Copies, Offset … } } | stop { mandatory } | fixture { fixture: G54…G59.9 }.")
        if name:
            o.Label = s.unique(name, o)
        d().recompute()
        s.snapshot("cam_path")
        out = {"object": o.Label, "kind": kind, **({"job": job.Label} if job is not None else {})}
        g = gcode(o)
        if g:
            out["commands"] = len(g)
            out["first"] = g[:6]
        sh = getattr(o, "Shape", None)
        if kind == "area" and sh is not None and not sh.isNull():
            out["wires"] = len(sh.Wires)
            out["area"] = round(sum(f.Area for f in sh.Faces), 3) if sh.Faces else None
        return out

    def cam_property_bag(a):
        _cam("A property bag")
        from Path.Base import PropertyBag

        kinds = ("Float", "Length", "Distance", "Angle", "Integer", "String", "Bool", "Percent", "Speed")
        props = a.get("properties") or []
        for p in props:
            if not isinstance(p, dict) or not p.get("name") or not str(p["name"]).isidentifier():
                raise bad("properties: [{ name (letters and digits, no spaces), type (Float, Length, Angle, Integer, String, Bool), value, group }].")
            if p.get("type", "Float") not in kinds:
                raise bad(f"properties.{p['name']}.type {p.get('type')!r}: one of {', '.join(kinds)}.")
        if len({p["name"] for p in props}) < len(props):
            raise bad("properties: each name once.")
        bag = PropertyBag.Create(a.get("name") or "PropertyBag")
        if a.get("name"):
            bag.Label = s.unique(a["name"], bag)
        for p in props:
            nm, kind = p["name"], p.get("type", "Float")
            bag.Proxy.addCustomProperty(f"App::Property{kind}", nm, p.get("group", "Custom"), p.get("info", ""))
            if "value" in p:
                try:
                    setattr(bag, nm, p["value"])
                except Exception as e:
                    raise bad(f"properties.{nm}.value {p['value']!r} does not fit a {kind}: {e}") from None
        d().recompute()
        s.snapshot("cam_property_bag")
        return {"bag": bag.Label, "name": bag.Name, "properties": [p["name"] for p in props],
                "use": f"In an operation's expression it is {bag.Name}.<property>."}

    def cam_template_export(a):
        _cam("A job template")
        import Path.Main.Job as PathJob
        import Path.Main.Stock as PathStock

        job = job_of(a.get("job"))
        attrs = job.Proxy.templateAttrs(job)
        if a.get("description"):
            attrs[PathJob.JobTemplate.Description] = a["description"]
        attrs[PathJob.JobTemplate.ToolController] = [tc.Proxy.templateAttrs(tc) for tc in job.Tools.Group]
        attrs[PathJob.JobTemplate.Stock] = PathStock.TemplateAttributes(job.Stock)
        attrs[PathJob.JobTemplate.SetupSheet] = job.Proxy.setupSheet.templateAttributes(True, True, True)
        enc = job.Proxy.setupSheet.encodeTemplateAttributes(attrs)
        path = os.path.expanduser(a.get("path") or os.path.join(s.out_dir, f"job_{job.Label}.json"))
        if not os.path.basename(path).startswith("job_"):
            path = os.path.join(os.path.dirname(path), "job_" + os.path.basename(path))
        if not path.endswith(".json"):
            path += ".json"
        paths.made(s, path)
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as fp:
            json.dump(enc, fp, sort_keys=True, indent=2)
        return {"template": path, "bytes": os.path.getsize(path), "tools": len(job.Tools.Group),
                "note": "FreeCAD's New Job dialog offers a job_*.json that lies in its CAM template folder (CAM preferences); cam_job does not read templates."}

    # ---- Draft ---------------------------------------------------------------------------

    def draft_fix(a):
        act = a.get("action")
        if act == "flip_dimension":
            o = picks.find(d(), a.get("dimension"), "dimension")
            if "Normal" not in o.PropertiesList or "Dimline" not in o.PropertiesList:
                raise bad(f"dimension: {o.Label} is not a Draft dimension (draft_dimension makes them; a drawing's dimensions are td_dim's).")
            # What Draft's Flip Dimension command does: the normal turned round.
            o.Normal = o.Normal.negative() if o.Normal.Length else FreeCAD.Vector(0, 0, -1)
            d().recompute()
            s.snapshot("draft_fix")
            return {"dimension": o.Label, "normal": [round(x, 6) for x in o.Normal], "note": "Its text now reads from the other side; the measured value is the same."}
        if act == "heal":
            import Draft

            if FreeCAD.ActiveDocument is not d():
                FreeCAD.setActiveDocument(d().Name)  # heal works on the active document
            targets = [picks.find(d(), r) for r in a["objects"]] if a.get("objects") else None
            # Named objects are rebuilt whatever their state (a copy takes the
            # place of each, the original removed), so their labels are read first.
            asked = [o.Label for o in targets] if targets else None
            before = {o.Name for o in d().Objects}
            Draft.heal(targets)
            d().recompute()
            s.snapshot("draft_fix")
            after = {o.Name: o.Label for o in d().Objects}
            made = [lab for n, lab in after.items() if n not in before]
            gone = len(before - set(after))
            out = {"healed": asked if asked else "all Draft objects", "rebuilt": len(made), "removed": gone}
            if made:
                out["now"] = made[:30]
                out["note"] = "Each rebuilt object is a new copy with a new name; the old one was removed, and what pointed at it was moved over."
            else:
                out["note"] = "Nothing needed healing." if not asked else "None of them is a kind Draft can rebuild (dimension, rectangle, wire, B-spline, circle, polygon)."
            return out
        raise bad("action: flip_dimension { dimension } | heal { objects }.")

    # ---- Assembly ------------------------------------------------------------------------

    def asm_rigid_group(a):
        from .assembly import _assembly, _joints, _part

        asm = _assembly(d(), a.get("assembly"))
        parts = [_part(asm, r) for r in (a.get("parts") or [])]
        if len(parts) < 2:
            raise bad(f"parts: two or more parts of {asm.Label}, held fixed to each other (asm_list lists them).")
        import JointObject

        if not hasattr(JointObject, "RigidGroupJoint"):
            raise ToolError("unavailable", f"Rigid groups came in FreeCAD 1.2; this is {'.'.join(FreeCAD.Version()[:3])}. asm_joint kind fixed between each pair does the same.")
        rg = _joints(asm).newObject("App::FeaturePython", "RigidGroupJoint")
        JointObject.RigidGroupJoint(rg, parts)
        if a.get("name"):
            rg.Label = s.unique(a["name"], rg)
        d().recompute()
        s.snapshot("asm_rigid_group")
        return {"joint": rg.Label, "parts": [p.Label for p in parts]}

    def asm_new_part(a):
        from .assembly import _assembly

        asm = _assembly(d(), a.get("assembly"))
        name = a.get("name") or "Part"
        part = d().addObject("App::Part", "Part")
        part.Label = s.unique(name, part)
        body = part.newObject("PartDesign::Body", "Body")
        body.Label = s.unique(f"{part.Label} body", body)
        lk = asm.newObject("App::Link", "Link")
        lk.LinkedObject = part
        lk.Label = s.unique(part.Label, lk)
        if picks.placed(a):
            lk.Placement = picks.placement(a)
        d().recompute()
        s.snapshot("asm_new_part")
        return {"part": part.Label, "body": body.Label, "inAssembly": lk.Label,
                "note": "An empty part in the assembly: sketch_new and pd_pad in its body build it in place. asm_joint and asm_ground do not take this link as a part; a body put in with asm_add they do."}

    st = {"type": "string"}
    arr = {"type": "array", "items": {"type": "string"}}
    num = {"type": "number"}
    v3 = {"type": "array", "items": num}
    return [
        Tool("cam_path", "Other CAM path objects (job puts one in a job). kind: area { sources, workplane \"Body.Face3\", props } | from_shape { sources } (a path along wires, no tool controller) | edges { sources, job } (with one: not on 1.1 without its window) | compound { ops } | array { ops, props: Type, Copies, Offset … } | stop { mandatory } (M0, else M1) | fixture { fixture: G54 … }. Answers object, commands, first (G-code lines).",
             obj({"kind": {"type": "string", "enum": ["area", "from_shape", "edges", "compound", "array", "stop", "fixture"]}, "job": st, "sources": arr, "workplane": st, "ops": arr, "props": {"type": "object"},
                  "mandatory": {"type": "boolean"}, "fixture": st, "name": st}, ["kind"]), cam_path, changes=True),
        Tool("cam_property_bag", "A CAM property bag of named values for operations' expressions: properties [{ name (no spaces), type Float | Length | Angle | Integer | String | Bool, value, group }]. Answers bag, name (expressions call it <name>.<property>).",
             obj({"name": st, "properties": {"type": "array", "items": {"type": "object"}}}), cam_property_bag, changes=True),
        Tool("cam_template_export", "Write a CAM job as a template (job_<name>.json in the output folder unless path): tool controllers, stock, setup sheet, post settings; description. For FreeCAD's New Job dialog (cam_job does not read templates). Changes nothing in the document.", obj({"job": st, "path": st, "description": st}), cam_template_export),
        Tool("draft_fix", "Draft fixes: action flip_dimension { dimension } (text to the other side) | heal { objects } (old Draft objects rebuilt as new copies; left out: only those that need it, named ones regardless). Reply: normal; or healed, rebuilt, removed, now.",
             obj({"action": {"type": "string", "enum": ["flip_dimension", "heal"]}, "dimension": st, "objects": arr}, ["action"]), draft_fix, changes=True),
        Tool("asm_rigid_group", "Hold two or more parts of an assembly fixed to each other as one group (Assembly's rigid group joint, FreeCAD 1.2 and newer): parts by label, name. On FreeCAD 1.1 it answers unavailable — asm_joint kind fixed between each pair does the same there. Reply: joint, parts.", obj({"assembly": st, "parts": arr, "name": st}, ["parts"]), asm_rigid_group, changes=True),
        Tool("asm_new_part", "A new empty part to build in place (Assembly's New Part): an App::Part holding an empty PartDesign body, put in the assembly through an App::Link; name; at [x, y, z], axis and angle degrees place the link. Reply: part, body (sketch_new { body } and pd_pad build in it), inAssembly (the link's label). asm_check checks it where the link stands; asm_joint and asm_ground take bodies put in with asm_new or asm_add, not this link — to joint a part, build the body first and asm_add it.", obj({"assembly": st, "name": st, "at": v3, "axis": v3, "angle": num}), asm_new_part, changes=True),
    ]
