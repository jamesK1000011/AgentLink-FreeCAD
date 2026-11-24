# SPDX-License-Identifier: LGPL-2.1-or-later
# Meant changes to tool descriptions since the data tests' snapshots were taken
# (private records: famfix-findings.md): each tool's old words and the true facts
# added or changed. The data tests apply them to the snapshot before comparing
# byte for byte, so any other change to a description still fails.

DESCRIPTIONS = {
    'bim_import': ('Type, read (which reader)',
        "Type, read (which reader), and a note when what was read lies over the document's own model: the file is read in its own coordinates into this document (doc_new first for a document of its own)"),
    'bim_rebar': (', totalLength_m, mass_kg.',
        ", totalLength_m, mass_kg. FreeCAD's rebar is laid on a hidden Draft wire (its base, from which FreeCAD reads the bar's length)."),
    'fea_buckle': ('nd gmsh (timeout s, 300).',
        "nd gmsh (timeout s, 300). Its results are the answer and files in the out folder (files): it makes no FEM objects in the document's tree."),
    'fea_heat': ('300); needs ccx and gmsh.',
        "300); needs ccx and gmsh. Its results are the answer and files in the out folder (files): it makes no FEM objects in the document's tree."),
    'fea_modes': ('nd gmsh (timeout s, 300).',
        "nd gmsh (timeout s, 300). Its results are the answer and files in the out folder (files): it makes no FEM objects in the document's tree."),
    'fea_native': ('ElmerSolver is installed.',
        'ElmerSolver is installed. Refused, with nothing made, in a FreeCAD session that can no longer draw a FEM mesh ("Cannot add static property", FreeCAD\'s own fault): restart FreeCAD.'),
    'fea_results': (' (kept with the session, not the file), with stale: true and staleWhy when the body or the study changed since.',
        " (kept with the session, not the file), with solvedFor { document, body } and stale: true and staleWhy when the body or the study changed since. Only the solve of this document's study: one kept from another study or document is refused, named (fea_solve first)."),
    'fea_export': (' (both by default), name.',
        " (both by default), name. Only the solve of this document's study (solvedFor names it; another study's is refused)."),
    'fea_setup': ('rary figures are typical.',
        "rary figures are typical. The study is Agent Link's, kept with the document: fea_setup, fea_hold and fea_load add no FEM objects to the tree (fea_native builds it as FreeCAD's own analysis, fea_solve where its FEM route runs)."),
    'fea_solve': ('s ccx and gmsh installed.',
        's ccx and gmsh installed. When FreeCAD\'s FEM route fails, what it had made is taken out again and the own deck\'s results are the answer and files only (solvedBy says so). In a FreeCAD session where FreeCAD can no longer draw a FEM mesh ("Cannot add static property", a FreeCAD fault left by the first FEM mesh made while a window observer listened) the route fails until FreeCAD is restarted.'),
    'meshobj_segments': (': true makes those meshes',
        ": true makes those meshes, each in a colour of its own in the window (as FreeCAD's Mesh_Segmentation colours its segments)"),
    'pd_multitransform': ('t: stepOf) and go with it',
        "t: stepOf) and go with it; as FreeCAD's own command leaves them, the steps are hidden and listed after the MultiTransform, which is the tip and the one shown"),
    'td_balloon': ("ext number), at [dx, dy] from the view's centre",
        "ext number), at [dx, dy] paper mm from the view's centre. Its tip and bubble are kept as FreeCAD keeps them, in the view's own unscaled frame (OriginX/Y, X/Y over the view's scale)"),
    'td_centermarks': (' only. Drawn by td_export, not in the window',
        " only. Drawn by td_export; in the window the same chain lines are drawn as FreeCAD's own cosmetic centre lines on those circles only, and FreeCAD's own crosses of the view (its ArcCenterMarks, which mark every arc's centre, a slot's ends too) are switched off"),
    'td_export': ("notes says what was skipped.",
        "notes says what was skipped; stacked names dimensions whose texts lie on one spot (td_dim_align or object_set X, Y moves one)."),
    'td_hatch': ('Drawn by td_export, not in the window;',
        "Drawn by td_export, and in the window as FreeCAD's own hatch (TechDraw::DrawHatch, its default pattern) on the view's face that shows each (window says which, or why none);"),
    'td_table': ('an empty sheet is refused.',
        "an empty sheet is refused. size: the text's height on the paper, mm (3.5): the table's scale is set for it (reply: scale)."),
    'td_weld': ('page), drawn by td_export (the window shows the leader only',
        "page), drawn by td_export, and in the window as FreeCAD's own weld symbol on the leader (TechDraw::DrawWeldSymbol, with FreeCAD's own symbol for fillet, square, v, plug and surfacing; the other kinds show their words only, and window says which"),
    # 18 Nov live build, 18 Nov: heavy changes estimated first, a big export a job.
    'part_from_mesh': ('omes the solid (note says so).',
        'omes the solid (note says so). refine about doubles the time; an estimate over a minute: the first call answers with the time and runs nothing, the same call again runs it.'),
    'insp_run': ('st [{ at, distance }], health.',
        'st [{ at, distance }], health. An estimate over a minute: the first call answers with the time and runs nothing, the same call again runs it.'),
    'export': ('nce: the chord error, 0.01 mm.',
        'nce: the chord error, 0.01 mm. Meshing B-spline faces can be slow: an estimate over 20 s runs as a job (job_status); in a batch an estimate over a minute answers with the time first, the same call again runs it.'),
    # Test drive of 20 Nov (findings 1, 2, 3, 9, 11, 12).
    'object_delete': ('Again, renamed). Reply: deleted, errors, health.',
        "Again, renamed). Reply: deleted, errors, health. A container that only holds the object is not a user (a Body, an App::Part, a group): an unused sketch or the tip feature of a Body deletes without force, and the Body's tip moves back."),
    'object_get': ('— use it, a feature has dozens. Changes nothing.',
        '— use it, a feature has dozens. Changes nothing. Several words go in one filter with | between them ("Length|Width"): a property that has one of them matches.'),
    'object_set': ('only Placement; Label is set with object_rename.',
        'only Placement; Label is set with object_rename. For one property, property and value also work: { property: "Length", value: 20 }.'),
    'asm_joint': [
        # Test drive of 20 Nov (bicycle, findings 4, 3, 5): no flip by itself, keep, chain by teeth.
        ("gears and belt (radius1, radius2 — read off round edges when left out).",
         "gears and belt (radius1, radius2 — read off round edges when left out); chain, FreeCAD's belt joint with the ratio teeth1 / teeth2 (50 / 16 = 3.125): "
         "the teeth given, or read from a PartDesign Sprocket (NumberOfTeeth) in each part, pitch the chain pitch mm (12.7); gears and belt take teeth1, teeth2 too; "
         "reply ratio and ratioFrom."),
        ("(false keeps FreeCAD's way; left out, it is turned over when that stops parts overlapping).",
         "(false keeps FreeCAD's way; left out, no part is turned over by itself: parts that overlap after the solve get a warning naming them, with how to flip; "
         "autoFlip: true turns the moved part over when that stops the overlap, the old way, and flipWarning says when the flip put a part's centre on the other "
         "side of the joint's plane). keep: true, for parts already placed: the offset (and the turn about the joint) that holds them where they stand, so nothing "
         "moves — reply kept { property, at, axis, angle, moved }; not with offset, rotate, gap, reverse or autoFlip."),
        (': asm_check and asm_sweep show what still moves.',
        ": asm_check and asm_sweep show what still moves. near in a query is in document coordinates (where the part is now); nearLocal is a point in the part's own frame, as modelled. offset's direction depends on which part moves; gap: mm between the two joined faces after the solve, positive apart, negative overlapping — the tool finds the offset for it (gap or offset, not both). Reply also: gap (the result across the joint, mm, negative for overlap) and at (the centre of each element when picked, in document coordinates)."
         # asm2, 20 Nov: joints on datums (LCS) and the stored query's re-pick
         ' a or b may be a datum inside the part — an LCS, datum plane, line or point (element: its name or label, or { datum }): the joint sits on its origin along its z axis, and stays on through booleans and edits; put joints on LCS markers, not on faces a boolean makes. An end picked by a query keeps the query (queryKept): when a later change renumbers that face, the health check runs it again and re-points the joint ("re-picked Face12 -> Face15"), or leaves it broken and says why (nothing found, or two equal matches).'),
    ],
    'asm_sweep': ("Each step cuts every pair of parts (a call is dropped after about 80 s): with many parts, fewer steps or a shorter range, not a job.",
        "Each step cuts every pair of parts (a call is dropped after about 80 s): the sweep stops in time (about 60 s), and then answers the steps done with "
        "partial: true, stepsDone and continueWith { joint, from, to, steps } for the next call; with many parts, fewer steps or a shorter range, not a job. "
        "Overlaps there at the first step with the same volume at every step are static (a press fit, parts modelled into each other): staticOverlaps lists "
        "them with their volume, and verdict, collidesAt and clearFromStart count only the contacts the motion makes."),
    'asm_bom': (' volume }]; a part with no material has no mass.',
        " volume }]; a part with no material has no mass. A part can be in a print setup: then mass is the printed estimate (walls and infill) of an installed add-on that owns mass, massAs tells how and solidMass is the solid mass; without that add-on, massAs marks the mass as solid, not as printed. slice gives the slicer's own figure."),
    'material_set': ('bject_rename does not carry it to the new label.',
        "bject_rename does not carry it to the new label. The short ids of measure_mass also work (steel, stainless, aluminium, brass …): the tool sets a FreeCAD library card for one, or Agent Link's stock figures; mapped tells which."),
    # pipe 20 Nov (bicycle, skeleton build): pd_pipe on edges of any object and a tube profile; shape_query of wires; sheet_table makes a named sheet; object_list by label.
    'pd_pipe': ('Sweep a closed profile sketch along a path sketch (all its edges, joined end to end); subtractive: true cuts it. The profile should sit across the path\'s start. Orientation, corners: feature_edit { Mode: "Frenet", Transition: "Round corner" }. Reply: feature, volume mm³',
        'Sweep a closed profile along a path: a sketch in the body, a pd_binder of a skeleton or a wire; edges ["Edge3"] sweeps along those only, joined end to end (all its edges by default; shape_query { body: path, kind: "edge" } names them); subtractive: true cuts it. profile: a sketch across the path\'s start, or { circle: { d: 28.6, wall: 0.9 } } — a sketch made square to the path at its start with two circles, a tube (no wall: a rod); d and wall mm or an expression ("Geo.tt_od"). mode Standard | Fixed | Frenet | Auxiliary | Binormal, transition Transformed | Right corner | Round corner. Reply: feature, profile, path, edges, volume mm³'),
    'object_list': ('type: part of the type to keep ("Part::", "Sketch").',
        'type: part of the type to keep ("Part::", "Sketch"); a full type ("PartDesign::Body") also keeps the types derived from it. label: part of the label to keep, any case. Nothing kept: typesHere lists the types there are.'),
    'shape_query': ('Reply items: ref, type, area / length, centroid / mid, normal, radius, axis, center.',
        "Reply items: ref, type, area / length, centroid / mid, normal, radius, axis, center. body may also be an object of edges and no solid (a pd_binder of a skeleton, a sketch, a wire): kind is edge by default, each edge also has from and to [x,y,z], dir a line's direction."),
    'sheet_table': ('sheet (else a new one)',
        'sheet (made with that label when no sheet has it; else a new one)'),
}



# Branch explore/full-ste: every hub tool's description is rewritten in ASD-STE100, in place. A snapshot's
# words (with the meant changes above) must still be main's original word for word (scripts/ste_originals.json);
# the tool's words are then the STE text, which tests/test_ste_lint.py checks against that original: every
# number, unit, input name, other tool's name and guard word kept, every sentence 20 words at most.
_STE = {}


def _ste():
    if not _STE:
        import json
        import os

        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "scripts", "ste_originals.json"), encoding="utf-8") as f:
            _STE["orig"] = json.load(f)["tools"]
        with open(os.path.join(root, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            _STE["now"] = {n: e["description"] for n, e in json.load(f)["entries"].items()}
    return _STE


def _meant_only(name, old):
    if name not in DESCRIPTIONS:
        return old
    pairs = DESCRIPTIONS[name]
    for was, now in (pairs if isinstance(pairs, list) else [pairs]):
        assert old.count(was) == 1, (name, was)
        old = old.replace(was, now)
    return old


def description(name, old):
    """The snapshot's description of a tool with its meant change made, and
    then the STE rewrite when the result is main's original word for word."""
    text = _meant_only(name, old)
    s = _ste()
    if name in s["now"] and s["orig"].get(name, {}).get("description") == text:
        return s["now"][name]
    return text


# Meant changes to what a converted tool does on the stand-in FreeCAD since
# its handler (the trace line at BASE, the line now, why). The data tests put
# the new line in place of the old one before they compare the traces.
TRACES = [
    (", 0.0873, False)", ", 0.5, False)",
     "Live 65: an exported mesh is made with an angular deflection of 0.5 rad (geometry.EXPORT_ANGULAR), not 0.0873: one loft face made 3.77 M triangles."),
    (".newObject('PartDesign::CoordinateSystem', 'LCS')", ".newObject('Part::LocalCoordinateSystem', 'LCS')",
     "20 Nov, skeleton workflow: pd_datum kind lcs makes FreeCAD 1.1's Part::LocalCoordinateSystem (an App::LocalCoordinateSystem, which a Body "
     "takes and Assembly joints read with its own origin, axes and planes); PartDesign::CoordinateSystem only where that type is not there."),
]


def trace_as_meant(lines):
    """A trace from BASE with the meant changes (TRACES) made."""
    out = []
    for ln in lines:
        if isinstance(ln, str):
            for old, new, _why in TRACES:
                ln = ln.replace(old, new)
        out.append(ln)
    return out


# Meant changes to a converted tool's inputSchema since its snapshot (test
# drive of 20 Nov): per tool, new descriptions of inputs, inputs put
# in after a named one (in that order), and the required list.
# a: near's frame said, nearLocal (20 Nov); b said as a, so the card holds at 900 tokens (bicycle drive).
_NEAR_A = "{ part, element }: \"Face6\", a datum (\"LCS\", { datum }), or a shape_query query (near picks the closest; nearLocal)."
_UPTO = "The face to go up to: { side: \"+z\" } (also of, largest; one face only), { at, normal }, \"Face8\", or shape_query's filters."
_EDGES = ("edges: [{ near: [x,y,z] } the edge nearest a point | { face: { side: \"+z\" } or { at, normal } } every edge of a face | { all: true }, "
          "kind: line|circle], a reference shape_query gives (\"Edge3\", \"Body.Edge3\"; a face's: its edges) or a list of them, "
          "or shape_query's filters ({ type: circle, radius, axis, near, \u2026 })")
_FACES = ("faces: [{ side: \"+z\" } | { at, normal }] by where they are, a reference shape_query gives (\"Face8\", \"Body.Face8\") "
          "or a list of them, or shape_query's filters ({ type, normal, near, x, y, z, \u2026 })")
_PLANE_FACE = "XY | XZ | YZ, a datum plane's name, or a face { side: \"+z\" } | { at, normal }"
SCHEMAS = {
    "asm_joint": {"why": "findings 2, 3: gap across the joint; near's frame said, nearLocal. Bicycle 3, 4, 5: keep, autoFlip, chain by teeth. asm2: a datum (LCS) as an end",
                  "describe": {"a": _NEAR_A, "b": "As a."},
                  "enum_add": {"kind": ["chain"]},
                  # asm2: gap's own words left to the card (the card stays at 900 tokens)
                  "after": [("offset", "gap", {"type": "number"}),
                            ("reverse", "autoFlip", {"type": "boolean"}), ("autoFlip", "keep", {"type": "boolean"}), ("keep", "teeth1", {"type": "integer"}),
                            ("teeth1", "teeth2", {"type": "integer"})]},
    "object_set": {"why": "finding 12: { property, value } as well as { values }",
                   "after": [("values", "property", {"type": "string", "description": "One property's name, with value: the same as values { property: value }."}),
                             ("property", "value", {})],
                   "required": ["object"]},
    # 20 Nov, the skeleton workflow of the design kickoff: a datum on several references of any object,
    # its mode, its AttachmentOffset, and (part_datum) the Body or App::Part that holds it.
    "pd_datum": {"why": "skeleton workflow: refs, mode, offset",
                 "after": [("rotate", "refs", {"type": "array", "items": {"type": "string"},
                                               "description": "One to four references in order, any object: \"Binder.Vertex1\", \"Skeleton.Edge2\", a whole \"Skeleton\". Not with on."}),
                           ("refs", "mode", {"type": "string", "description": "With refs: a FreeCAD MapMode (OZX, ObjectXY, Translate, Concentric, NormalToEdge …)."}),
                           ("mode", "offset", {"type": "object", "description": "With refs: { at: [x,y,z], rotate: { axis, angle } }, the AttachmentOffset in the frame that the references give."})]},
    "part_datum": {"why": "skeleton workflow: refs, offset, body, part",
                   "after": [("to", "refs", {"type": "array", "items": {"type": "string"},
                                             "description": "One to four references in order, any object: \"Binder.Vertex3\", \"Skeleton.Edge2\", a whole \"LCS\". Not with to."}),
                             ("mode", "offset", {"type": "object", "description": "{ at: [x,y,z], rotate: { axis, angle } }: the AttachmentOffset, in the frame that the references give."}),
                             ("offset", "body", {"type": "string", "description": "A PartDesign Body to hold the datum."}),
                             ("body", "part", {"type": "string", "description": "An App::Part to hold the datum."})]},
    # pipe 20 Nov: pd_pipe's profile is a sketch or { circle }, its path any object with edges, and edges, mode, transition; object_list's label.
    "pd_pipe": {"why": "bicycle skeleton build: a tube along one edge of a binder",
                "replace": {"profile": {"description": "A sketch in the body, or { circle: { d, wall } }."}},
                "describe": {"path": "A sketch in the body, a binder, or another object with edges."},
                "after": [("path", "edges", {"description": "Edges of the path to sweep along, joined end to end: [\"Edge3\"]."}),
                          ("edges", "mode", {"type": "string"}), ("mode", "transition", {"type": "string"}),
                          # bicycle L5 build (21 Nov, finding 4): Refine off by default on a pipe
                          ("subtractive", "refine", {"type": "boolean", "description": "FreeCAD's Refine on the pipe; false by default."})]},
    # bicycle L5 build (21 Nov, finding 3): a sketch hung on an edge again in place, or its lost element re-pointed
    "sketch_attach": {"why": "bicycle L5 finding 3: edge, mode, at, repair",
                      "after": [("flip", "edge", {"type": "string", "description": "An object's edge, \"Binder.Edge1\": the sketch hangs on it."}),
                                ("edge", "mode", {"type": "string", "description": "On an edge: NormalToEdge (default), FrenetNB, FrenetTN, FrenetTB, Concentric, RevolutionSection."}),
                                ("mode", "at", {"type": "number", "description": "On an edge: where, 0 (its start) to 1 (its end)."}),
                                ("at", "repair", {"type": "boolean"})]},
    # later bicycle runs, finding 1: a sweep of 25 parts checks only the pairs asked
    "asm_sweep": {"why": "bicycle runs finding 1: parts and skip",
                  "after": [("turn", "parts", {"type": "array", "items": {"type": "string"}}), ("parts", "skip", {"type": "array", "items": {"type": "string"}})]},
    "object_list": {"why": "bicycle skeleton build: a label filter", "after": [("type", "label", {"type": "string"})]},
    # bicycle drive of 20 Nov, finding 5: pd_gear on a plane (body, datum, LCS), turned on it
    "pd_gear": {"why": "bicycle finding 5: a gear on any plane",
                "after": [("at", "rotate", {"type": "object", "description": "{ axis: [x,y,z], angle: degrees }, on the plane."}),
                          ("rotate", "plane", {"type": "string", "description": "XY, XZ, YZ, a datum plane, \"LCS.XZ_Plane\" or an LCS."})]},
    # bicycle runs of 20 Nov, finding 5: relative: true keeps FreeCAD's default on a binder of a document-level source
    "pd_binder": {"why": "bicycle finding 5: Relative false for a source at document level", "after": [("frozen", "relative", {"type": "boolean"})]},
    # 21 Nov, one file for each part: link_make links an object of another .FCStd
    "link_make": {"why": "parts in other files: file", "after": [("to", "file", {"type": "string"})]},
    # 22 Nov efficiency design D1: pictures go to the file by default; width makes the window's picture smaller
    "window_snapshot": {"why": "efficiency design D1: width", "after": [("path", "width", {"type": "integer"})]},
    # 22 Nov co-work design E5 item 7b: the command's selection for its run only, the person's put back
    "cmd_run": {"why": "co-work E5 7b: select",
                "after": [("index", "select", {"type": "array", "items": {"type": "string"},
                                               "description": "Objects (\"Block\") or faces and edges (\"Block.Face6\") selected for this run only. The person's selection comes back after the run."})]},
    # 22 Nov (owner-approved): face selectors { side: "+z", of, largest } beside { at, normal }; one face only (agentlink/facesel.py)
    # 24 Nov, audit top 10 #1: length has a description (small models guessed height or depth)
    "pd_pad": {"why": "face selectors; length described", "describe": {"upToFace": _UPTO, "length": "The pad's depth in mm, along the sketch's normal (type length)."}},
    "pd_pocket": {"why": "face selectors; length described", "describe": {"upToFace": _UPTO, "length": "The cut's depth in mm (type length)."}},
    **{n: {"why": "face selectors", "describe": {"edges": _EDGES}} for n in ("pd_fillet", "pd_chamfer")},
    "pd_draft": {"why": "face selectors", "describe": {"faces": _FACES, "neutral": _PLANE_FACE}},
    "pd_thickness": {"why": "face selectors", "describe": {"faces": _FACES}},
    "pd_mirrored": {"why": "face selectors", "describe": {"plane": _PLANE_FACE}},
    "pd_datum_plane": {"why": "face selectors", "describe": {"on": _PLANE_FACE}},
    "sketch_new": {"why": "face selectors", "replace": {"face": {
        "type": "object",
        "description": "{ side: \"+z\" | \"-z\" | \"+x\" | \"-x\" | \"+y\" | \"-y\", of: the feature that made it, largest: true } (one face only), "
                       "or { at: [x,y,z] a point on the face, normal: [x,y,z] its outward normal }",
        "properties": {"side": {"type": "string", "enum": ["+z", "-z", "+x", "-x", "+y", "-y"]}, "of": {"type": "string"}, "largest": {"type": "boolean"},
                       "at": {"type": "array", "items": {"type": "number"}}, "normal": {"type": "array", "items": {"type": "number"}},
                       "tol": {"type": "number"}},
        "additionalProperties": False}}},
}


def schema(name, old):
    """The snapshot's inputSchema of a tool with its meant change made."""
    import copy

    m = SCHEMAS.get(name)
    if not m:
        return old
    new = copy.deepcopy(old)
    props = new["properties"]
    for k, text in m.get("describe", {}).items():
        props[k]["description"] = text
    for k, val in m.get("replace", {}).items():
        props[k] = val
    for k, more in m.get("enum_add", {}).items():
        props[k]["enum"] = list(props[k]["enum"]) + list(more)
    for at, key, val in m.get("after", []):
        out = {}
        for k, v in props.items():
            out[k] = v
            if k == at:
                out[key] = val
        props = out
    new["properties"] = props
    if "required" in m:
        new["required"] = list(m["required"])
    # the keys in the order the entry keeps them
    return {k: new[k] for k in old}


# Answer fields a converted tool now adds to what its handler answered (the
# data tests take them out of the new answer before they compare): per tool,
# the field names and why.
RESULTS = {
    "asm_joint": (("gap", "gapIs", "gapWarning", "offset", "at", "flipWarning", "crossedPlane", "kept", "keepWarning", "ratio", "ratioFrom", "teeth", "queryKept", "sideCheck", "sideWarning"),
                  "findings 2, 3: the gap across the joint and where each element was picked; bicycle 3, 4, 5: keep, the flip's plane, a coupling's ratio; asm2: the ends whose query is kept"),
    "asm_sweep": (("staticOverlaps", "staticNote", "partial", "stepsDone", "continueWith", "partialNote", "pairsChecked", "pairsSkipped"), "bicycle 6, 7: a sweep in time, static overlaps apart; runs finding 1: the pairs counted"),
    "asm_bom": ((), "finding 11: rows of parts in a print setup carry massAs and solidMass (none in the stand-in's cases)"),
    "pd_datum": (("refs", "mode", "offset", "world", "type"), "skeleton workflow (20 Nov): a datum attached by refs says them, its mode, offset and world placement"),
    "part_datum": (("refs", "offset", "in", "world"), "skeleton workflow (20 Nov): refs, the container and the world placement"),
    "pd_pipe": (("profile", "path", "edges", "profileIs"), "pipe 20 Nov: a made tube profile, a path of a binder or chosen edges are named"),
    "sheet_table": (("newSheet",), "pipe 20 Nov: a sheet made with the label given"),
    "shape_query": (("shapeIs",), "pipe 20 Nov: an object of edges only"),
    "object_list": (("typesHere",), "pipe 20 Nov: the types there are when nothing is kept"),
    "pd_gear": (("on", "stored"), "bicycle finding 5: the plane used and the properties that keep the teeth"),
    "sketch_add": (("dimsNote",), "bicycle finding 6: dims asked of a kind with no size"),
}


def result_as_meant(tool, new):
    """A case's new run with the fields RESULTS names taken out of its answer."""
    names = RESULTS.get(tool, ((),))[0]
    res = new.get("result")
    if not names or not (isinstance(res, list) and res and res[0] == "ok" and isinstance(res[1], dict)):
        return new
    return {**new, "result": [res[0], {k: v for k, v in res[1].items() if k not in names}] + res[2:]}


# Trace lines a converted tool now adds to what its handler did on the
# stand-in FreeCAD (the data tests take them out of the new trace before
# they compare): per tool, the lines' starts and why.
TRACE_ADDED = {
    "asm_joint": (("{j}.addProperty('App::PropertyString', 'AgentLinkQuery')", "{j}.AgentLinkQuery = "),
                  "asm2 20 Nov: an end picked by a query keeps the query on the joint (AgentLinkQuery) for the re-pick"),
}


def trace_added_out(tool, new):
    """A case's new run with the trace lines TRACE_ADDED names taken out."""
    starts = TRACE_ADDED.get(tool, ((),))[0]
    if not starts or not isinstance(new.get("trace"), list):
        return new
    import re

    pats = [re.compile(re.escape(s_).replace(re.escape("{j}"), r"[^.]+")) for s_ in starts]
    return {**new, "trace": [ln for ln in new["trace"] if not (isinstance(ln, str) and any(p.match(ln) for p in pats))]}


# Trace lines and objects a converted tool now adds on the stand-in FreeCAD
# (taken out of the new run before the compare, as TRACE_ADDED): per tool,
# the line starts, the object labels, and why.
TRACE_ADDED["draft_clone"] = (("addObject('App::FeaturePython', 'AgentLinkRecords')", "AgentLinkRecords."),
                              "7a8477d, bicycle finding 11: a clone keeps its source's material; the record (materialFrom) is written to the document's records object")
TRACE_ADDED["pd_gear"] = (("{j}.addProperty('App::PropertyInteger', 'AgentLinkTeeth'", "{j}.addProperty('App::PropertyLength', 'AgentLinkPitch'",
                            "{j}.addProperty('App::PropertyString', 'AgentLinkKind'", "{j}.AgentLinkTeeth = ", "{j}.AgentLinkPitch = ", "{j}.AgentLinkKind = "),
                           "bicycle finding 5: a sprocket's profile keeps its teeth and chain pitch for asm_joint kind chain")
OBJECTS_ADDED = {
    "draft_clone": (("Agent Link records",), "7a8477d: the records object that holds materialFrom"),
}


def objects_added_out(tool, new):
    """A case's new run with the objects OBJECTS_ADDED names taken out."""
    labels = OBJECTS_ADDED.get(tool, ((),))[0]
    if not labels or not isinstance(new.get("objects"), list):
        return new
    return {**new, "objects": [o for o in new["objects"] if o not in labels]}


# Meant changes to one case's run since the handler at BASE: the handler's
# old way is no longer the tool's way (a test drive found it wrong). The
# data tests make these changes to the old run before the compare, so any
# other change still fails. Per (tool, case): why, and the changes:
#   message: (old words, new words) in a refusal's message, once
#   set: answer fields with their new value; drop: answer fields gone
#   result: the whole new result (a refusal where the handler answered)
#   trace: [(old lines, new lines)]: a run of trace lines put in place of another
#   objects: the document's labels after the call
_KINDS = ("gears, belt (got", "gears, belt, chain (got")
_TURN_OVER = [  # the old way's flip on an overlap, gone (bicycle finding 4)
    "common(Solid<Base>, [Solid<Lid>])", "flipOnePart(<Fixed>)"]
_SLIDE_STEPS = [{"at": 0.0}, {"at": 5.0}, {"at": 10.0}]
CASES = {
    ("asm_joint", "a kind not offered"): {"why": "bicycle finding 5: kind chain", "message": _KINDS},
    ("asm_joint", "no kind"): {"why": "bicycle finding 5: kind chain", "message": _KINDS},
    ("asm_joint", "kept as FreeCAD put it, overlapping"): {
        "why": "bicycle finding 4: the warning names each overlap and its volume",
        "set": {"warning": "Parts overlap after the solve: Base/Lid 100 mm³ — a face picked the wrong way round, or the parts do not fit. "
                           "reverse: true flips the second part, or check the sizes."}},
    ("asm_joint", "a ball joint is not turned over"): {
        "why": "bicycle finding 4: the warning names each overlap and its volume",
        "set": {"warning": "Parts overlap after the solve: Base/Lid 100 mm³ — a face picked the wrong way round, or the parts do not fit. "
                           "reverse: true flips the second part, or check the sizes."}},
    ("asm_joint", "turned over to stop an overlap"): {
        "why": "bicycle finding 4: only autoFlip: true turns a part over; it reads the solve's state again first (one more solve)",
        "set": {"flipped": "turned over to stop the parts overlapping (autoFlip: true; leave autoFlip out to keep it as FreeCAD first put it)"},
        "trace": [(["solve(<Assembly>)", "common(Solid<Base>, [Solid<Lid>])", "flipOnePart(<Fixed>)"],
                   ["solve(<Assembly>)", "solve(<Assembly>)", "common(Solid<Base>, [Solid<Lid>])", "flipOnePart(<Fixed>)"])]},
    ("asm_joint", "turning over does not help"): {
        "why": "bicycle finding 4: no part is turned over by itself; the warning says how to flip",
        "set": {"warning": "Parts overlap after the solve: Base/Lid 100 mm³. The tool did not turn a part over. reverse: true turns the moved part over "
                           "on the joint; autoFlip: true lets the tool try it; else check the sizes."},
        "trace": [(_TURN_OVER + ["recompute()", "solve(<Assembly>)", "common(Solid<Base>, [Solid<Lid>])",
                                 "Base.Placement = Placement(V(0, 0, 0), Rotation(V(0, 0, 1), 0))",
                                 "Lid.Placement = Placement(V(0, 0, -5), Rotation(V(0, 0, 1), 0))", "recompute()", "solve(<Assembly>)"], [])]},
    ("asm_joint", "turned over, it no longer solves"): {
        "why": "bicycle finding 4: no part is turned over by itself; the warning says how to flip",
        "set": {"warning": "Parts overlap after the solve: Base/Lid 100 mm³. The tool did not turn a part over. reverse: true turns the moved part over "
                           "on the joint; autoFlip: true lets the tool try it; else check the sizes."},
        "trace": [(_TURN_OVER + ["Lid.Placement = Placement(V(0, 0, 0), Rotation(V(0, 0, 1), 0))", "recompute()", "solve(<Assembly>)",
                                 "Base.Placement = Placement(V(0, 0, 0), Rotation(V(0, 0, 1), 0))",
                                 "Lid.Placement = Placement(V(0, 0, -5), Rotation(V(0, 0, 1), 0))", "recompute()", "solve(<Assembly>)"], [])]},
    ("asm_sweep", "a slider that collides from the start"): {
        "why": "bicycle finding 7: the same overlap at every step is static (staticOverlaps); steps, verdict and collidesAt count motion contacts only",
        "set": {"steps": _SLIDE_STEPS, "verdict": "clear"}, "drop": ("collidesAt", "clearFromStart")},
    ("sketch_new", "plane wrong"): {
        "why": "bicycle finding 3: a plane may be an LCS's, a whole LCS or a Part datum plane; the refusal names what there is",
        "message": ("datum plane 'XW': not in Body — there: none.", "plane 'XW': no datum plane, coordinate system or plane of that name — there: XY, XZ, YZ.")},
    ("part_refine", "a PartDesign body's tip, made worse"): {
        "why": "7a8477d, bicycle finding 10: a tip's Refine that makes the body worse is set back and refused",
        "result": ["refused", "failed", "Refine made Housing worse: the volume went from 1000.000 to 500.000 mm³ (-50.00 %). Refine of Pad is set back, "
                                        "so Housing is as it was. body_check Housing says what is wrong with it now; leave the faces as they are, "
                                        "or rebuild the step that left them."],
        "trace": [(["Pad.Refine = True"], ["copy(Solid<housing>)", "Pad.Refine = True"]),
                  (["soundness(Solid<refined housing>)", "snapshot('part_refine')"], ["Pad.Refine = False", "recompute()"])]},
}


def case_as_meant(tool, case, old):
    """A case's run at BASE with the meant changes CASES names for it."""
    import copy

    m = CASES.get((tool, case))
    if not m:
        return old
    old = copy.deepcopy(old)
    res = old["result"]
    if "result" in m:
        res = old["result"] = copy.deepcopy(m["result"])
    if "message" in m:
        was, now = m["message"]
        assert res[0] == "refused" and res[2].count(was) == 1, (tool, case, res)
        res[2] = res[2].replace(was, now)
    if m.get("set") or m.get("drop"):
        assert res[0] == "ok", (tool, case, res)
        for k, v in m.get("set", {}).items():
            assert k in res[1], (tool, case, k)
            res[1][k] = copy.deepcopy(v)
        for k in m.get("drop", ()):
            del res[1][k]
    for was, now in m.get("trace", []):
        t = old["trace"]
        at = [i for i in range(len(t) - len(was) + 1) if t[i:i + len(was)] == was]
        assert len(at) == 1, (tool, case, was, at)
        old["trace"] = t[:at[0]] + list(now) + t[at[0] + len(was):]
    if "objects" in m:
        old["objects"] = list(m["objects"])
    return old
