# SPDX-License-Identifier: LGPL-2.1-or-later
# The cases tests/test_datapart_data.py runs through the old handler and the
# new data entry of each converted Part tool, on the stand-in FreeCAD
# (tests/_datapart_standin.py): its normal paths and each of its refusals.
# (The live models under docs/hardening/models are run on FreeCAD, not here: datapart-findings.md lists which of their calls reach each tool.)

# The family files whose tools were converted.
FILES = ("model", "std_more", "surface")
# Each converted tool and its group.
CONVERTED = {k: "model" for k in ("part_primitive", "part_boolean", "part_transform", "part_fillet", "part_chamfer", "part_offset", "part_thickness",
                                  "part_extrude", "part_revolve", "part_loft", "part_sweep")}
CONVERTED.update({k: "std_more" for k in ("part_container", "compound_explode", "compound_filter", "part_join", "part_import_curves", "surface_polynomial")})
CONVERTED.update({k: "surface" for k in ("surface_sections", "surface_boundary", "surface_extend", "surface_sew", "surface_cut", "surface_blend")})
# Each Part, Draft or Surface tool of those files kept as code, and why: none in model.py, none of std_more.py's
# (its other tools are other families': not in this test).
KEPT = {}
# What some cases must have answered (not two empty runs alike): fields of an answer, or the whole refusal.
EXPECT = {
    ("part_primitive", "a box, named"): {"body": "Block", "volume": 24000.0, "kind": "box", "type": "Part::Box", "sound": True, "step": 1},
    ("part_primitive", "a tube where FreeCAD has no BasicShapes"): {"body": "Tube", "type": "Part::Feature", "kind": "tube"},
    ("part_primitive", "kind wrong"): ["refused", "invalid_input", "kind: one of box, cylinder, sphere, cone, torus, wedge, prism, tube."],
    ("part_primitive", "a torus that cuts itself"): ["refused", "invalid_input", "radius2: the tube's radius (12), under radius, the ring's (10) — else the torus cuts through itself."],
    ("part_boolean", "a cut"): {"body": "Block", "op": "cut", "volumeChange": -500.0, "removed": ["Pin"], "step": 1},
    ("part_boolean", "keep"): {"kept": ["Pin"], "hidden": ["Pin"]},
    ("part_boolean", "apart"): ["refused", "failed", "cut changed nothing in Block: they do not touch (least distance 155.885 mm). Move a tool into the base (part_transform), then again."],
    ("part_transform", "move"): {"body": "Block", "op": "move", "placement": {"at": [5.0, 0.0, 0.0], "axis": [0.0, 0.0, 1.0], "angle": 0.0}},
    ("part_transform", "polar apart"): {"op": "polar", "count": 4, "note": "4 separate solids: the copies do not touch — one body holding them."},
    ("part_boolean", "a cut that only touches"): ["refused", "failed", "cut changed nothing in Block: they only touch it (least distance 0.000 mm). Move a tool into the base (part_transform), then again."],
    ("part_loft", "rebuilt"): {"route": ["profiles rebuilt as B-splines through the same 48 points each (arc length, seams lined up, one set of knots): OCC refused them as given (OCC could not build it (BRepOffsetAPI_ThruSections: not done))"], "maxDegree": 5},
    ("part_loft", "twisted every way, span by span kept"): {"route": ["segments: lofted span by span and joined — 1–2 ruled (they bulged smooth: profiles 1–2 by 40% along y), the rest smooth at maxDegree 5"]},
    ("part_loft", "kept late, not checked"): {"sound": None, "unchecked": "Not checked for soundness: the call was out of time (4 faces). body_check Loft checks it (it is timed and given its own deadline).", "strays": None},
    ("part_loft", "mended by OCC's fix"): {"route": ["OCC's shape fix repaired the loft"]},
    ("part_transform", "op wrong"): ["refused", "invalid_input", "op: move { by }, rotate { axis, angle, about }, mirror { normal, about, fuse }, scale { factor, about }, linear { count, step }, polar { count, axis, about, angle }."],
    ("part_fillet", "edges by name"): {"body": "Block", "edges": 2, "volumeChange": -4.0},
    ("part_chamfer", "all"): {"edges": 12, "volumeChange": -12.0},
    ("part_offset", "out"): {"distance": 1.0, "volume": 1600.0},
    ("part_thickness", "a face opened"): {"thickness": 1.5, "inward": True, "opened": 1},
    ("part_extrude", "a sketch"): {"body": "Extrude", "volume": 1000.0, "sound": True},
    ("part_extrude", "a surface"): {"surface": True, "closed": True},
    ("part_extrude", "into, a pocket"): {"op": "cut", "body": "Block"},
    ("part_revolve", "all the way round"): {"body": "Revolve", "volume": 36000.0},
    ("part_sweep", "along points"): {"body": "Sweep", "volume": 250.0},
    ("part_loft", "smooth as given"): {"body": "Loft", "maxDegree": 5, "volume": 900.0, "aligned": None, "route": None},
    ("part_loft", "ruled"): {"route": ["ruled: each profile as it was, a polygon of 48 corners, seams lined up"], "maxDegree": None},
    ("part_loft", "rebuilt at a lower degree"): {"maxDegree": 3, "route": ["maxDegree lowered to 3: at 5 the loft bulged 30% beyond its profiles"]},
    ("part_container", "holding objects taken from another, placed, named"): {"part": "Rig", "objects": ["Block", "Pin"], "step": None},
    ("compound_explode", "three pieces"): {"group": "GroupExplode", "pieces": [{"name": "Parts.0", "volume": 1000.0}, {"name": "Parts.1", "volume": 1000.0}, {"name": "Parts.2", "volume": 1000.0}]},
    ("compound_filter", "two items, named, in the window"): {"filter": "Ends", "kept": 2},
    ("compound_filter", "none in the window"): ["refused", "failed", "The filter keeps nothing of Parts (window-area): no piece lies within 10 … 20% of the largest (or of the stencil's) — nothing was made."],
    ("part_join", "connect in the window, named"): {"join": "Tee", "kind": "connect", "valid": True, "solids": 1, "volume": 7000.0},
    ("part_join", "cutout, open"): {"join": "Saddle", "solids": 0, "volume": None},
    ("part_import_curves", "a file in the session's folder"): {"curves": "net", "edges": 5},
    ("surface_polynomial", "a mesh"): {"surface": "Scan polynomial", "points": 25, "rms": 0.0122, "max": 0.0242},
    ("surface_sections", "a wire whole, named"): {"object": "Skin", "type": "Sections", "sections": 2, "step": 1},
    ("surface_boundary", "four going round, one backwards"): {"object": "Boundary surface", "type": "GeomFillSurface", "fill": "stretched", "sides": 4},
    ("surface_boundary", "coons refused as disjoint: a filling"): {"object": "Patch", "type": "Filling", "note": "Made as Surface Filling (smooth through the edges): FreeCAD's coons fill refused these curves."},
    ("surface_boundary", "coons refused and the filling too"): ["refused", "failed", "GeomFillSurface failed: Curves are disjoint. — nothing was kept. The curves must meet at their ends within FreeCAD's tolerance; "
                                                                "fill stretched is the most forgiving, and surface_fill takes any closed boundary. — and a filling through the edges failed too; fill: stretched joins them."],
    ("surface_extend", "by u and v, named"): {"object": "Run on", "u": 0.5, "v": -0.1},
    ("surface_sew", "faces of a body, closed, a solid, named"): {"object": "Skin", "faces": 8, "closed": True, "solid": {"body": "Skin solid", "volume": 500.0}},
    ("surface_sew", "open, no solid"): {"solid": "not made: the shell is open — a gap wider than tolerance, or a face missing (2 edge(s) with a face on one side only)", "warning": None},
    ("surface_cut", "nothing cut"): {"note": "Nothing was cut: Wall does not cross Sheet."},
    ("surface_blend", "set, named"): {"object": "Bridge", "type": "FeatureBlendCurve", "edges": 1, "length": 5.0},
    ("part_loft", "out of time"): ["refused", "failed", "The loft is not kept: out of time: OCC's loft (4 faces) took 0 s of the 0 s a loft has (a window that stops answering is taken for hung). "
                                   "Lighter: split it into lofts of about 2 profiles (each run starting on the profile the last ended on) and part_boolean fuse them; "
                                   "or fewer points a profile (samples: 33); or fewer profiles where the shape changes slowly. Nothing was added."],
}
# Refusals written in the data that no case here reaches: none.
UNREACHED = []

SQ = [[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0]]


def ring(z, r=5):
    return {"points": [[r, 0, z], [0, r, z], [-r, 0, z], [0, -r, z]]}


def cases(fc, tmp, old, new):
    mods = [old["model"], new["model"]]
    real = {m: {k: getattr(m, k) for k in ("LOFT_BUDGET", "align_profiles", "sample_count", "as_polygons", "as_matching_bsplines", "loft_problem",
                                           "loft_overshoot", "loft_spans", "strays")} for m in mods}
    flag, log = fc.flag, fc.log

    # The loft's own geometry (lining profiles up, rebuilding them, measuring a bulge) is model.py's
    # module-level code, unchanged by the conversion: here it answers what a case says, so the order
    # of tries, the words and the answer are what is compared.
    import time

    clock = {"real": time.monotonic, "ahead": 0.0}
    time.monotonic = lambda: clock["real"]() + clock["ahead"]  # a case may make the loft's check take long (slow_check: seconds)

    def problem(r, ws, solid):
        log("loft_problem", r)
        clock["ahead"] += flag("slow_check", 0.0)
        if "[twist]" in r.tag:
            return "profiles twist: the loft bulges 30% beyond its profiles along x"
        if "[open]" in r.tag and not (r.tag.startswith("copy of") and flag("fix_mends")):
            return "it is open"
        return None

    def rebuilt(wires, n):
        log("as_matching_bsplines", [w.tag for w in wires], n)
        if flag("no_rebuild"):
            raise RuntimeError("no curve through them")
        return [fc.wire(f"rebuilt {w.tag}", w.pts or [(0, 0, 0), (1, 1, 0)], closed=w.closed) for w in wires]

    stubs = {"align_profiles": lambda wires: (log("align_profiles", [w.tag for w in wires]), (wires, list(flag("aligned", []))))[1],
             "sample_count": lambda wires, asked=None: asked or 48,
             "as_polygons": lambda wires, n: (log("as_polygons", [w.tag for w in wires], n), (wires, flag("polygons_kept", True), n))[1],
             "as_matching_bsplines": rebuilt, "loft_problem": problem,
             "loft_overshoot": lambda r, ws: (flag("share", {}).get(r.tag, 0.3), "x"),
             "loft_spans": lambda r, ws: [dict(x) for x in flag("spans", [{"span": [0, 1], "share": 0.3, "axis": "x"}])],
             "strays": lambda res, given: (log("strays", res, len(given)), dict(flag("strays")) if flag("strays") else None)[1]}

    def prep(*fns, budget=None, **flags):
        def prepare(s):
            for m in mods:
                for k, v in stubs.items():
                    setattr(m, k, v)
                m.LOFT_BUDGET = real[m]["LOFT_BUDGET"] if budget is None else budget
            clock["ahead"] = 0.0
            fc.fc.GuiUp = False
            fc.state["flags"].update(flags)
            for fn in fns:
                fn(s)
        return prepare

    def block(s):
        fc.body("Block", fc.solid("block", (0, 0, 0), (10, 10, 10)))

    def pin(s):
        fc.body("Pin", fc.solid("pin", (5, 5, 5), (15, 15, 15)))

    def far(s):
        fc.body("Far", fc.solid("far", (100, 100, 100), (110, 110, 110)))

    def sketch(s):
        fc.body("Sketch", fc.wire("sketch outline", SQ), type_="Sketcher::SketchObject", name="Sketch")

    def open_sketch(s):
        fc.body("Open", fc.wire("open line", SQ[:3], closed=False), type_="Sketcher::SketchObject", name="Open")

    def two_wires(s):
        w = fc.wire("two outlines", SQ, kind="Compound", wires=2)
        fc.body("Two", w, name="Two")

    def path(s):
        fc.body("Path", fc.wire("path line", [(0, 0, 0), (0, 0, 50)], closed=False), name="Path")

    def broken(s):
        fc.body("Bad", fc.solid("bad", (5, 5, 5), (15, 15, 15), valid=False))

    def pieces(s):
        fc.body("Pieces", fc.solid("pieces", (0, 0, 0), (10, 10, 10), solids=2))

    none = prep()
    T = "part_primitive"
    yield T, "a box, named", none, {"kind": "box", "size": [40, 30, 20], "name": "Block"}
    yield T, "a box as it comes", none, {"kind": "box"}
    yield T, "kind wrong", none, {"kind": "cube"}
    yield T, "kind left out", none, {}
    yield T, "crash: a kind that is a list", none, {"kind": ["box"]}
    yield T, "size wrong", none, {"kind": "box", "size": [10, 0, 5]}
    yield T, "size not three", none, {"kind": "box", "size": [10, 5]}
    yield T, "a cylinder placed and turned", none, {"kind": "cylinder", "radius": 4, "height": 30, "at": [0, 0, 5], "direction": [1, 0, 0], "rotate": {"axis": [0, 0, 1], "angle": 30}, "name": "Pin"}
    yield T, "a cylinder with no radius above 0", none, {"kind": "cylinder", "radius": 0}
    yield T, "direction on a box", none, {"kind": "box", "direction": [1, 0, 0]}
    yield T, "direction of no length", none, {"kind": "cone", "direction": [0, 0, 0]}
    yield T, "a sphere", none, {"kind": "sphere", "radius": 8}
    yield T, "a cone", none, {"kind": "cone", "radius": 6, "radius2": 2, "height": 12}
    yield T, "a cone to a point at its base", none, {"kind": "cone", "radius": 0, "radius2": 3}
    yield T, "a cone's base under 0", none, {"kind": "cone", "radius": -1}
    yield T, "a cone's radius not a number", none, {"kind": "cone", "radius": "big"}
    yield T, "a cone of equal radii", none, {"kind": "cone", "radius": 4, "radius2": 4}
    yield T, "a cone's height wrong", none, {"kind": "cone", "height": -3}
    yield T, "a torus", none, {"kind": "torus"}
    yield T, "a torus that cuts itself", none, {"kind": "torus", "radius": 10, "radius2": 12}
    yield T, "a wedge", none, {"kind": "wedge", "wedge": {"xmax": 20, "x2max": 12}}
    yield T, "a wedge as it comes", none, {"kind": "wedge"}
    yield T, "a wedge key unknown", none, {"kind": "wedge", "wedge": {"xmid": 3}}
    yield T, "a wedge value not a number", none, {"kind": "wedge", "wedge": {"xmax": "wide"}}
    yield T, "a wedge inside out", none, {"kind": "wedge", "wedge": {"xmax": -1}}
    yield T, "a prism", none, {"kind": "prism", "sides": 5, "radius": 6, "height": 4}
    yield T, "a prism of two sides", none, {"kind": "prism", "sides": 2}
    yield T, "a tube", none, {"kind": "tube", "radius": 6, "radius2": 4, "height": 20}
    yield T, "a tube's bore too wide", none, {"kind": "tube", "radius": 3, "radius2": 4}
    yield T, "a tube where FreeCAD has no BasicShapes", prep(missing=("BasicShapes",)), {"kind": "tube"}
    yield T, "a tube FreeCAD's maker leaves half made", prep(tube_fails=True), {"kind": "tube"}
    yield T, "empty", prep(empty_primitive=True), {"kind": "box"}
    yield T, "empty and FreeCAD says why", prep(empty_primitive=True, objects_invalid=True), {"kind": "cylinder"}
    yield T, "a name taken", prep(block), {"kind": "box", "name": "Block"}

    T = "part_boolean"
    yield T, "a cut", prep(block, pin), {"op": "cut", "base": "Block", "tools": "Pin"}
    yield T, "a fuse of two, named", prep(block, pin, lambda s: fc.body("Peg", fc.solid("peg", (8, 8, 8), (12, 12, 20)))), {"op": "fuse", "base": "Block", "tools": ["Pin", "Peg"], "name": "Joined"}
    yield T, "a fuse of pieces that do not all touch", prep(block, pin, far), {"op": "fuse", "base": "Block", "tools": ["Pin", "Far"]}
    yield T, "common", prep(block, pin), {"op": "common", "base": "Block", "tools": ["Pin"]}
    yield T, "keep", prep(block, pin), {"op": "cut", "base": "Block", "tools": "Pin", "keep": True}
    yield T, "op wrong", prep(block, pin), {"op": "join", "base": "Block", "tools": "Pin"}
    yield T, "no tools", prep(block), {"op": "cut", "base": "Block", "tools": []}
    yield T, "tools left out", prep(block), {"op": "cut"}
    yield T, "base among the tools", prep(block, pin), {"op": "cut", "base": "Block", "tools": ["Pin", "Block"]}
    yield T, "a tool not here", prep(block), {"op": "cut", "base": "Block", "tools": "Nope"}
    yield T, "base left out with two bodies", prep(block, pin), {"op": "cut", "tools": "Pin"}
    yield T, "a tool that is not sound", prep(block, broken), {"op": "cut", "base": "Block", "tools": "Bad"}
    yield T, "an invalid result", prep(block, pin, bool_invalid=True), {"op": "fuse", "base": "Block", "tools": "Pin"}
    yield T, "a fuse that drops its tool", prep(block, pin, fuse_adds_nothing=True), {"op": "fuse", "base": "Block", "tools": "Pin"}
    yield T, "common without overlap", prep(block, far), {"op": "common", "base": "Block", "tools": "Far"}
    yield T, "apart", prep(block, far), {"op": "cut", "base": "Block", "tools": "Far"}
    yield T, "a cut that only touches", prep(block, pin, cut_share=0.0, cut_same_faces=True), {"op": "cut", "base": "Block", "tools": "Pin"}
    yield T, "a fuse of a tool inside", prep(block, lambda s: fc.body("In", fc.solid("in", (2, 2, 2), (4, 4, 4))), fuse_adds_nothing=True), {"op": "fuse", "base": "Block", "tools": "In"}

    T = "part_transform"
    yield T, "move", prep(block), {"op": "move", "by": [5, 0, 0]}
    yield T, "move without by", prep(block), {"op": "move"}
    yield T, "a moved copy", prep(block), {"op": "move", "by": [0, 20, 0], "copy": True}
    yield T, "a named copy turned", prep(block), {"op": "rotate", "axis": "+x", "angle": 90, "copy": True, "name": "Turned"}
    yield T, "rotate about a point", prep(block), {"op": "rotate", "angle": 45, "about": [1, 2, 3]}
    yield T, "rotate without an angle", prep(block), {"op": "rotate"}
    yield T, "about wrong", prep(block), {"op": "move", "by": [1, 1, 1], "about": [1]}
    yield T, "mirror", prep(block), {"op": "mirror", "normal": [0, 1, 0]}
    yield T, "mirror fused", prep(block), {"op": "mirror", "about": [10, 0, 0], "fuse": True}
    yield T, "scale", prep(block), {"op": "scale", "factor": 2, "name": "Big"}
    yield T, "scale each way", prep(block), {"op": "scale", "factor": [1, 2], "about": [5, 5, 5]}
    yield T, "scale by 0", prep(block), {"op": "scale", "factor": 0}
    yield T, "scale each way by 0", prep(block), {"op": "scale", "factor": [1, 0, 1]}
    yield T, "scale with no factor", prep(block), {"op": "scale"}
    yield T, "linear", prep(block), {"op": "linear", "count": 3, "step": [5, 0, 0]}
    yield T, "linear apart, not fused", prep(block), {"op": "linear", "count": 2, "step": [50, 0, 0], "fuse": False}
    yield T, "linear of one", prep(block), {"op": "linear", "count": 1, "step": [5, 0, 0]}
    yield T, "linear without a step", prep(block), {"op": "linear"}
    yield T, "polar", prep(block), {"op": "polar", "count": 4, "axis": [0, 0, 1], "about": [20, 0, 0]}
    yield T, "polar apart", prep(block, fuse_solids=4), {"op": "polar", "count": 4, "angle": 90}
    yield T, "polar of one", prep(block), {"op": "polar", "count": 0}
    yield T, "op wrong", prep(block), {"op": "shear"}
    yield T, "op left out", prep(block), {}
    yield T, "no body", none, {"op": "move", "by": [1, 0, 0]}

    for T, key in (("part_fillet", "radius"), ("part_chamfer", "size")):
        meth = "makeFillet" if T == "part_fillet" else "makeChamfer"
        yield T, "edges by name", prep(block), {key: 2, "edges": ["Edge3", "Block.Edge7"]}
        yield T, "all", prep(block), {key: 1, "edges": "all"}
        yield T, "a face's edges and a query", prep(block, query_hits=[2, 9]), {key: 1, "edges": ["Face6"], "query": {"type": "line"}, "name": "Soft"}
        yield T, "no size above 0", prep(block), {key: 0, "edges": "all"}
        yield T, "no edge", prep(block), {key: 1}
        yield T, "an edge of another body", prep(block, pin), {"body": "Block", key: 1, "edges": ["Pin.Edge1"]}
        yield T, "OCC fails", prep(block, fail=(meth,)), {key: 20, "edges": "all"}
        yield T, "a broken shape", prep(block, broken=(meth,)), {key: 4, "edges": ["Edge1"]}
        yield T, "no solid left", prep(block, broken=(meth + ":nosolid",)), {key: 4, "edges": ["Edge1"]}

    T = "part_offset"
    yield T, "out", prep(block), {"distance": 1}
    yield T, "in, sharp, named", prep(block), {"distance": -1, "join": "intersection", "name": "Core"}
    yield T, "distance 0", prep(block), {"distance": 0}
    yield T, "distance left out", prep(block), {}
    yield T, "join wrong", prep(block), {"distance": 1, "join": "round"}
    yield T, "OCC fails", prep(block, fail=("makeOffsetShape",)), {"distance": -8}
    yield T, "faces only, made a solid", prep(block, offset="faces"), {"distance": 1}
    yield T, "faces that make no solid", prep(block, offset="faces", fail=("Solid",)), {"distance": 1}
    yield T, "nothing left", prep(block, offset="none"), {"distance": -6}

    T = "part_thickness"
    yield T, "a face opened", prep(block), {"thickness": 1.5, "open": ["Face6"]}
    yield T, "by query, outward, arc, named", prep(block, query_hits=[5]), {"thickness": 2, "query": {"normal": "+z"}, "inward": False, "join": "arc", "name": "Cup"}
    yield T, "several solids", prep(pieces), {"thickness": 1, "open": ["Face1"]}
    yield T, "too thin", prep(block), {"thickness": 0.001, "open": ["Face1"]}
    yield T, "thickness under 0", prep(block), {"thickness": -1}
    yield T, "open is no face", prep(block), {"thickness": 1, "open": ["Edge3"]}
    yield T, "open is a body's name", prep(block), {"thickness": 1, "open": ["Block"]}
    yield T, "a face of another body", prep(block, pin), {"body": "Block", "thickness": 1, "open": ["Pin.Face1"]}
    yield T, "a face not there", prep(block), {"thickness": 1, "open": ["Face9"]}
    yield T, "nothing opened", prep(block), {"thickness": 1}
    yield T, "OCC fails", prep(block, fail=("makeThickness",)), {"thickness": 1, "open": ["Face6"]}
    yield T, "no solid left", prep(block, shell="empty"), {"thickness": 6, "open": ["Face6"]}
    yield T, "not valid", prep(block, shell="invalid"), {"thickness": 3, "open": ["Face6"]}

    T = "part_extrude"
    yield T, "a sketch", prep(sketch), {"profile": "Sketch", "length": 10}
    yield T, "as it comes, from points", none, {"profile": {"points": SQ}}
    yield T, "along a direction", prep(sketch), {"profile": "Sketch", "direction": [0, 3, 4]}
    yield T, "along a direction by a length, both ways, named", prep(sketch), {"profile": "Sketch", "direction": [0, 0, 2], "length": 30, "symmetric": True, "name": "Bar"}
    yield T, "a surface", prep(open_sketch), {"profile": "Open", "length": 5, "solid": False}
    yield T, "an open outline for a solid", prep(open_sketch), {"profile": "Open", "length": 5}
    yield T, "length 0", prep(sketch), {"profile": "Sketch", "length": 0}
    yield T, "length not a number", prep(sketch), {"profile": "Sketch", "length": "long"}
    yield T, "no profile", none, {}
    yield T, "OCC fails", prep(sketch, fail=("extrude",)), {"profile": "Sketch", "direction": [1, 0, 0]}
    yield T, "no solid", prep(sketch, extrude_no_solid=True), {"profile": "Sketch"}
    yield T, "into, a boss", prep(block, sketch), {"profile": "Sketch", "length": 20, "into": "Block"}
    yield T, "into, a pocket", prep(block, sketch), {"profile": "Sketch", "length": 5, "into": "Block", "op": "cut"}
    yield T, "op without into", prep(sketch), {"profile": "Sketch", "op": "cut"}
    yield T, "into, missed", prep(far, sketch), {"profile": "Sketch", "length": 5, "into": "Far", "op": "cut"}

    T = "part_revolve"
    yield T, "all the way round", prep(sketch), {"profile": "Sketch"}
    yield T, "part of the way about an axis, named", prep(sketch), {"profile": "Sketch", "angle": -90, "axis": [0, 1, 0], "at": [20, 0, 0], "name": "Bend"}
    yield T, "angle 0", prep(sketch), {"profile": "Sketch", "angle": 0}
    yield T, "angle past a turn", prep(sketch), {"profile": "Sketch", "angle": 400}
    yield T, "axis of no length", prep(sketch), {"profile": "Sketch", "axis": [0, 0, 0]}
    yield T, "OCC fails", prep(sketch, fail=("revolve",)), {"profile": "Sketch"}
    yield T, "a shell made a solid", prep(sketch, revolve="shell"), {"profile": "Sketch"}
    yield T, "no solid", prep(sketch, revolve="shell", fail=("Solid",)), {"profile": "Sketch"}
    yield T, "inside out, turned", prep(sketch, revolve_sign=-1.0), {"profile": "Sketch"}
    yield T, "a surface", prep(open_sketch), {"profile": "Open", "solid": False}

    T = "part_sweep"
    yield T, "along points", prep(sketch), {"profile": "Sketch", "path": {"points": [[0, 0, 0], [0, 0, 40], [0, 20, 60]]}}
    yield T, "along a wire, frenet, round, named", prep(sketch, path), {"profile": "Sketch", "path": "Path", "frenet": True, "corners": "round", "name": "Rail"}
    yield T, "a face's outline along an edge", prep(block, path), {"profile": "Block.Face1", "path": "Block.Edge2", "corners": "sharp"}
    yield T, "two outlines", prep(two_wires, path), {"profile": "Two", "path": "Path"}
    yield T, "open for a solid", prep(open_sketch, path), {"profile": "Open", "path": "Path"}
    yield T, "a surface from an open profile", prep(open_sketch, path), {"profile": "Open", "path": "Path", "solid": False}
    yield T, "no path", prep(sketch), {"profile": "Sketch"}
    yield T, "OCC fails", prep(sketch, path, fail=("makePipeShell",)), {"profile": "Sketch", "path": "Path"}
    yield T, "no solid", prep(sketch, path, sweep_no_solid=True), {"profile": "Sketch", "path": "Path"}

    def pieces3(s):
        fc.body("Parts", fc.solid("parts", (0, 0, 0), (30, 10, 10), kind="Compound", solids=3), name="Parts")

    def lone(s):
        fc.body("Lone", fc.solid("lone", (0, 0, 0), (10, 10, 10)), name="Lone")

    def held(s):
        g = fc.doc().new("App::Part", "Old", Group=[])
        g.addObject(fc.doc().getObject("Body"))

    def pipes(s):
        fc.body("Pipe", fc.solid("pipe", (0, 0, 0), (10, 10, 40)), name="Pipe")
        fc.body("Branch", fc.solid("branch", (0, 0, 10), (30, 10, 20)), name="Branch")

    def window(s):
        fc.fc.GuiUp = True

    def no_window(s):
        fc.fc.GuiUp = False

    T = "part_container"
    yield T, "empty", none, {}
    yield T, "holding objects taken from another, placed, named", prep(block, pin, held), {"objects": ["Block", "Pin"], "at": [5, 0, 0], "axis": [0, 0, 1], "angle": 90, "name": "Rig"}
    yield T, "one object by name", prep(block), {"objects": "Block"}
    yield T, "an object not here", prep(block), {"objects": ["Nope"]}
    yield T, "a name taken", prep(lambda s: fc.body("Part", fc.solid("p", (0, 0, 0), (1, 1, 1)))), {}

    T = "compound_explode"
    yield T, "three pieces", prep(pieces3), {"compound": "Parts"}
    yield T, "one solid", prep(lone), {"compound": "Lone"}
    yield T, "not here", none, {"compound": "Parts"}
    yield T, "no name", prep(pieces3), {}

    T = "compound_filter"
    yield T, "items as they come", prep(pieces3), {"compound": "Parts"}
    yield T, "two items, named, in the window", prep(pieces3, lambda s: fc.doc().getObject("Parts").__dict__.update(ViewObject=fc.View("Parts"))), {"compound": "Parts", "keep": "items", "items": [0, 2], "name": "Ends"}
    yield T, "touching a stencil", prep(pieces3, block), {"compound": "Parts", "keep": "collision-pass", "stencil": "Block"}
    yield T, "not touching a stencil", prep(pieces3, block), {"compound": "Parts", "keep": "collision-fail", "stencil": "Block"}
    yield T, "by volume", prep(pieces3), {"compound": "Parts", "keep": "window-volume", "from": 50, "to": 100}
    yield T, "by distance, the old word", prep(pieces3, block), {"compound": "Parts", "keep": "window-distribution", "stencil": "Block", "from": 0}
    yield T, "keep wrong", prep(pieces3), {"compound": "Parts", "keep": "largest"}
    yield T, "no stencil", prep(pieces3), {"compound": "Parts", "keep": "collision-fail"}
    yield T, "a stencil not here", prep(pieces3), {"compound": "Parts", "keep": "window-distance", "stencil": "Nope"}
    yield T, "an item out of range", prep(pieces3), {"compound": "Parts", "items": [0, 3]}
    yield T, "an item that is true", prep(pieces3), {"compound": "Parts", "items": [True]}
    yield T, "no items", prep(pieces3), {"compound": "Parts", "items": []}
    yield T, "nothing passes", prep(pieces3, filter_keeps="none"), {"compound": "Parts", "items": [1]}
    yield T, "no piece touches", prep(pieces3, block, filter_keeps="none"), {"compound": "Parts", "keep": "collision-pass", "stencil": "Block"}
    yield T, "every piece touches", prep(pieces3, block, filter_keeps="invalid"), {"compound": "Parts", "keep": "collision-fail", "stencil": "Block"}
    yield T, "none in the window", prep(pieces3, filter_keeps="none"), {"compound": "Parts", "keep": "window-area", "from": 10, "to": 20}
    yield T, "crash: from not a number", prep(pieces3), {"compound": "Parts", "keep": "window-length", "from": "low"}

    T = "part_join"
    yield T, "connect", prep(pipes), {"kind": "connect", "objects": ["Pipe", "Branch"]}
    yield T, "connect in the window, named", prep(pipes, window), {"kind": "connect", "objects": ["Pipe", "Branch"], "name": "Tee"}
    yield T, "embed", prep(pipes, no_window), {"kind": "embed", "base": "Pipe", "tool": "Branch"}
    yield T, "cutout, open", prep(pipes, join_open=True), {"kind": "cutout", "base": "Pipe", "tool": "Branch", "name": "Saddle"}
    yield T, "kind wrong", prep(pipes), {"kind": "weld"}
    yield T, "kind left out", prep(pipes), {}
    yield T, "connect with no objects", prep(pipes), {"kind": "connect"}
    yield T, "connect with one", prep(pipes), {"kind": "connect", "objects": "Pipe"}
    yield T, "an object not here", prep(pipes), {"kind": "connect", "objects": ["Pipe", "Nope"]}
    yield T, "embed in itself", prep(pipes), {"kind": "embed", "base": "Pipe", "tool": "Pipe"}
    yield T, "cutout with no tool", prep(pipes), {"kind": "cutout", "base": "Pipe"}
    yield T, "failed", prep(pipes, join_fails=True), {"kind": "connect", "objects": ["Pipe", "Branch"]}
    yield T, "invalid", prep(pipes, join_invalid=True, objects_invalid=True), {"kind": "embed", "base": "Pipe", "tool": "Branch"}

    T = "part_import_curves"

    def a_file(name):
        import os

        def make(s):
            with open(os.path.join(s.out_dir, name), "w") as f:
                f.write("ISO-10303-21;")
        return make

    yield T, "a file in the session's folder", prep(a_file("net.step")), {"path": "net.step"}
    yield T, "named", prep(a_file("net.step")), {"path": "net.step", "name": "Rails"}
    yield T, "no path", none, {}
    yield T, "a path of spaces", none, {"path": "  "}
    yield T, "no such file", none, {"path": "gone.step"}
    yield T, "not read", prep(a_file("bad.step"), fail=("read",)), {"path": "bad.step"}
    yield T, "no curves", prep(a_file("solid.brep"), file_edges=0), {"path": "solid.brep"}

    T = "surface_polynomial"

    def scan(n=5, kind="mesh"):
        def make(s):
            pts = [fc.Vec(x, y, 0.1 * x * x - 0.05 * x * y + 0.2 * y + 1) for x in range(n) for y in range(n)]
            if kind == "mesh":
                o = fc.doc().new("Mesh::Feature", "Scan", Mesh=fc.ns(Points=pts))
            else:
                o = fc.doc().new("Points::Feature", "Scan", Points=fc.ns(Points=pts))
        return make

    yield T, "a mesh", prep(scan()), {"from": "Scan"}
    yield T, "a point cloud, named", prep(scan(4, "points")), {"from": "Scan", "name": "Bowl"}
    yield T, "a body", prep(block), {"from": "Block"}
    yield T, "too few points", prep(scan(2)), {"from": "Scan"}
    yield T, "not here", none, {"from": "Scan"}
    yield T, "from left out", none, {}

    def rails(s):
        # a square's four sides going round, the third listed backwards; and two more apart from them
        fc.body("Rails", fc.curves("rails", [((0, 0, 0), (10, 0, 0)), ((10, 0, 0), (10, 10, 0)), ((0, 10, 0), (10, 10, 0)), ((0, 10, 0), (0, 0, 0)),
                                             ((50, 0, 0), (60, 0, 0)), ((10, 10, 0), (5, 20, 0))]), name="Rails")

    def two_rails(s):
        fc.body("Pair", fc.curves("pair", [((0, 0, 0), (10, 0, 0)), ((0, 0, 5), (10, 0, 5))]), name="Pair")

    def sheet(s):
        fc.body("Sheet", fc.Shape("sheet", "Face", (0, 0, 0), (10, 10, 0), area=100.0, faces=1, edges=4, solids=0, shells=0), name="Sheet")
        fc.body("Wall", fc.Shape("wall", "Face", (5, 0, -5), (5, 10, 5), area=100.0, faces=1, edges=4, solids=0, shells=0), name="Wall")

    def no_edges(s):
        fc.body("Dot", fc.Shape("dot", "Compound", (0, 0, 0), (0, 0, 0), solids=0), name="Dot")

    T = "surface_sections"
    yield T, "two edges", prep(two_rails), {"sections": ["Pair.Edge1", "Pair.Edge2"]}
    yield T, "a wire whole, named", prep(two_rails), {"sections": ["Pair"], "name": "Skin"}
    yield T, "one", prep(two_rails), {"sections": ["Pair.Edge1"]}
    yield T, "none", none, {}
    yield T, "not a list", prep(two_rails), {"sections": "Pair"}
    yield T, "a face", prep(block), {"sections": ["Block.Face1", "Block.Edge1"]}
    yield T, "no edges", prep(no_edges), {"sections": ["Dot"]}
    yield T, "not a name", none, {"sections": [3]}
    yield T, "the feature fails", prep(two_rails, invalid_types=("Surface::Sections",), status="Not enough sections"), {"sections": ["Pair"]}

    T = "surface_boundary"
    four = ["Rails.Edge1", "Rails.Edge2", "Rails.Edge3", "Rails.Edge4"]
    yield T, "four going round, one backwards", prep(rails), {"edges": four}
    yield T, "two at a corner, coons, named", prep(rails), {"edges": ["Rails.Edge2", "Rails.Edge1"], "fill": "coons", "name": "Corner"}
    yield T, "fill wrong", prep(rails), {"edges": four, "fill": "flat"}
    yield T, "one edge", prep(rails), {"edges": ["Rails.Edge1"]}
    yield T, "six, a wire whole", prep(rails), {"edges": ["Rails"]}
    yield T, "does not close", prep(rails), {"edges": ["Rails.Edge1", "Rails.Edge2", "Rails.Edge6"]}
    yield T, "two that share no end", prep(rails), {"edges": ["Rails.Edge1", "Rails.Edge5"]}
    yield T, "out of order", prep(rails), {"edges": ["Rails.Edge1", "Rails.Edge3", "Rails.Edge2", "Rails.Edge4"]}
    yield T, "stretched refused", prep(rails, invalid_types=("Surface::GeomFillSurface",)), {"edges": four}
    yield T, "coons refused for another reason", prep(rails, invalid_types=("Surface::GeomFillSurface",), status="Curve too short"), {"edges": four, "fill": "coons"}
    yield T, "curved refused as disjoint, two curves", prep(rails, invalid_types=("Surface::GeomFillSurface",)), {"edges": ["Rails.Edge1", "Rails.Edge2"], "fill": "curved"}
    yield T, "coons refused as disjoint: a filling", prep(rails, invalid_types=("Surface::GeomFillSurface",)), {"edges": four, "fill": "coons", "name": "Patch"}
    yield T, "coons refused and the filling too", prep(rails, invalid_types=("Surface::GeomFillSurface", "Surface::Filling")), {"edges": four, "fill": "curved"}

    T = "surface_extend"
    yield T, "as it comes", prep(block), {"face": "Block.Face2"}
    yield T, "by u and v, named", prep(block), {"face": "Block.Face6", "u": 0.5, "v": -0.1, "name": "Run on"}
    yield T, "an edge", prep(block), {"face": "Block.Edge2"}
    yield T, "no face", prep(block), {}
    yield T, "u too far", prep(block), {"face": "Block.Face2", "u": 11}
    yield T, "v not a number", prep(block), {"face": "Block.Face2", "v": "far"}
    yield T, "the feature fails", prep(block, null_types=("Extend",)), {"face": "Block.Face2"}

    T = "surface_sew"
    yield T, "two surfaces, open", prep(sheet), {"faces": ["Sheet", "Wall"]}
    yield T, "faces of a body, closed, a solid, named", prep(block, sewn="closed"), {"faces": ["Block.Face1", "Block.Face2", "Block"], "solid": True, "name": "Skin", "tolerance": 0.1}
    yield T, "closed, a solid", prep(sheet, sewn="closed"), {"faces": ["Sheet", "Wall"], "solid": True}
    yield T, "open, no solid", prep(sheet), {"faces": ["Sheet", "Wall"], "solid": True}
    yield T, "nothing joined, no solid", prep(sheet, sewn="none"), {"faces": ["Sheet", "Wall"], "solid": True}
    yield T, "one face", prep(sheet), {"faces": ["Sheet"]}
    yield T, "none", none, {}
    yield T, "not a name", prep(sheet), {"faces": ["Sheet", 4]}
    yield T, "no faces", prep(sheet, two_rails), {"faces": ["Sheet", "Pair"]}
    yield T, "tolerance 0", prep(sheet), {"faces": ["Sheet", "Wall"], "tolerance": 0}

    T = "surface_cut"
    yield T, "cut", prep(sheet), {"surface": "Sheet", "by": "Wall"}
    yield T, "split, not cut, named", prep(sheet, cut="split"), {"surface": "Sheet", "by": "Wall", "name": "Halves"}
    yield T, "nothing cut", prep(sheet, cut="none"), {"surface": "Sheet", "by": "Wall"}
    yield T, "by itself", prep(sheet), {"surface": "Sheet", "by": "Sheet"}
    yield T, "by left out", prep(sheet), {"surface": "Sheet"}
    yield T, "the feature fails", prep(sheet, invalid_types=("Surface::Cut",), status="Cut failed"), {"surface": "Sheet", "by": "Wall"}

    T = "surface_blend"
    yield T, "as it comes", prep(rails), {"start": {"edge": "Rails.Edge1"}, "end": {"edge": "Rails.Edge5"}}
    yield T, "set, named", prep(rails), {"start": {"edge": "Rails.Edge1", "at": 1, "continuity": 1, "size": -2}, "end": {"edge": "Rails", "at": 0.5, "continuity": 3, "size": 5}, "name": "Bridge"}
    yield T, "no end", prep(rails), {"start": {"edge": "Rails.Edge1"}}
    yield T, "no edge", prep(rails), {"start": {}, "end": {"edge": "Rails.Edge5"}}
    yield T, "continuity wrong", prep(rails), {"start": {"edge": "Rails.Edge1", "continuity": 5}, "end": {"edge": "Rails.Edge5"}}
    yield T, "at wrong", prep(rails), {"start": {"edge": "Rails.Edge1"}, "end": {"edge": "Rails.Edge5", "at": 2}}
    yield T, "size 0", prep(rails), {"start": {"edge": "Rails.Edge1", "size": 0}, "end": {"edge": "Rails.Edge5"}}
    yield T, "the feature fails", prep(rails, null_types=("FeatureBlendCurve",)), {"start": {"edge": "Rails.Edge1"}, "end": {"edge": "Rails.Edge5"}}

    T = "part_loft"
    three = [ring(0), ring(10, 8), ring(20)]
    yield T, "smooth as given", none, {"profiles": three}
    yield T, "ruled", none, {"profiles": three, "ruled": True}
    yield T, "ruled, rebuilt as polygons, lined up, named, with strays", prep(polygons_kept=False, aligned=["profiles.1: reversed"], strays={"maxDistance": 0.2, "meanDistance": 0.1, "profile": 1, "points": 12}), \
        {"profiles": three, "ruled": True, "samples": 32, "name": "Hull"}
    yield T, "strays with no profile, many lined up", prep(aligned=[f"profiles.{i}: seam moved" for i in range(6)], strays={"maxDistance": 0.0, "meanDistance": 0.0, "profile": None, "points": 12}), {"profiles": three}
    yield T, "sketches and a face, a surface", prep(open_sketch, lambda s: fc.body("Open2", fc.wire("open line 2", [(0, 0, 9), (5, 0, 9)], closed=False), name="Open2")), {"profiles": ["Open", "Open2"], "solid": False}
    yield T, "a face and a sketch into a body", prep(block, sketch), {"profiles": ["Block.Face6", "Sketch", ring(30)], "into": "Block"}
    yield T, "profiles and a file", none, {"profiles": three, "profiles_file": "x.json"}
    yield T, "a file's name wrong", none, {"profiles_file": " "}
    yield T, "a file not there", none, {"profiles_file": "nowhere.json"}
    yield T, "one profile", none, {"profiles": [ring(0)]}
    yield T, "none", none, {}
    yield T, "profiles not a list", none, {"profiles": "Sketch"}
    yield T, "two wires in one", prep(two_wires), {"profiles": ["Two", ring(5)]}
    yield T, "open for a solid", prep(open_sketch), {"profiles": [ring(0), "Open"]}
    yield T, "open and closed", prep(open_sketch), {"profiles": [ring(0), "Open"], "solid": False}
    yield T, "maxDegree wrong", none, {"profiles": three, "maxDegree": 9}
    yield T, "maxDegree true", none, {"profiles": three, "maxDegree": True}
    yield T, "samples wrong", none, {"profiles": three, "samples": 4}
    yield T, "samples not whole", none, {"profiles": three, "samples": 16.5}
    yield T, "segments with closed", none, {"profiles": three, "segments": True, "closed": True}
    yield T, "closed", none, {"profiles": three, "closed": True}
    yield T, "rebuilt", prep(loft={"given": "raise"}), {"profiles": three}
    yield T, "rebuilt after a bulge", prep(loft={"given": "twist"}), {"profiles": three}
    yield T, "refused at 5, kept at 3", prep(loft={"smooth5": "raise"}), {"profiles": three}
    yield T, "rebuilt at a lower degree", prep(loft={"smooth5": "twist"}), {"profiles": three}
    yield T, "inside out, turned", prep(loft={"all": "inside out"}), {"profiles": three}
    yield T, "mended by OCC's fix", prep(loft={"smooth5": "open"}, fix_mends=True), {"profiles": three}
    yield T, "twisted every way, then span by span", prep(loft={"smooth": "twist"}, spans=[{"span": [1, 2], "share": 0.4, "axis": "y"}]), {"profiles": three}
    yield T, "twisted every way, span by span kept", prep(loft={"smooth": "twist"}, spans=[{"span": [1, 2], "share": 0.4, "axis": "y"}], sews=True), {"profiles": three + [ring(30)]}
    yield T, "twisted every way, a surface span by span", prep(loft={"smooth": "twist"}, sews=True), {"profiles": three, "solid": False}
    yield T, "twisted every way, segments off", prep(loft={"smooth": "twist"}), {"profiles": three, "segments": False}
    yield T, "twisted, two profiles", prep(loft={"smooth": "twist"}, spans=[]), {"profiles": three[:2], "maxDegree": 2}
    yield T, "ruled and twisted", prep(loft={"ruled": "twist"}), {"profiles": three, "ruled": True}
    yield T, "refused smooth, two profiles ruled", prep(loft={"smooth": "raise"}), {"profiles": three[:2]}
    yield T, "refused every way", prep(loft={"all": "raise"}), {"profiles": three}
    yield T, "refused, and no rebuild", prep(loft={"all": "raise"}, no_rebuild=True), {"profiles": three}
    yield T, "open every way", prep(loft={"all": "open"}), {"profiles": three, "maxDegree": 2}
    yield T, "kept late, not checked", prep(slow_check=100.0), {"profiles": three}
    yield T, "late and not fit to keep", prep(slow_check=100.0, loft={"all": "twist"}), {"profiles": three}
    yield T, "out of time", prep(budget=-1), {"profiles": three, "samples": 48}
