# SPDX-License-Identifier: LGPL-2.1-or-later
# The cases tests/test_datamesh_data.py runs through the old handlers and
# the new data entries on the stand-in FreeCAD (tests/_datamesh_standin.py):
# for each converted tool its normal paths and each of its refusals. A case
# is (tool, case name, prepare(session), arguments); prepare furnishes the
# document and sets the stand-in's flags for the run.

FILES = ("meshobj", "points")

# tool -> its group
CONVERTED = {
    **{k: "mesh" for k in (
        "meshobj_unwrap", "meshobj_from_shape", "meshobj_info", "meshobj_repair", "meshobj_decimate", "meshobj_refine", "meshobj_smooth",
        "meshobj_edit", "meshobj_trim", "meshobj_transform", "meshobj_boolean", "meshobj_sections", "meshobj_split", "meshobj_segments",
        "meshobj_curvature", "meshobj_project", "meshobj_primitive", "meshobj_merge", "meshobj_boundary", "meshobj_export")},
    **{k: "points" for k in ("points_import", "points_sample", "points_info", "points_crop", "points_fit", "points_merge", "points_mesh", "points_export")},
}

# tool -> why it is still code
KEPT = {}

# Refusals written in an entry that no case reaches, each with its reason.
UNREACHED = [
    # The stand-in's child process is a Python, so one is always found to run the unwrapping in.
    "meshobj_unwrap: " + "No Python to run the unwrapping in apart from FreeCAD here (none beside FreeCAD's program"[:70],
    # A five-minute run is not made here.
    "meshobj_unwrap: " + "The unwrapping ran over 5 minutes: a coarser tolerance, or a smaller surface."[:70],
    # Over two million triangles need a cloud of millions of points: not built here.
    "points_mesh: " + "A {cell:g} mm cell makes {len(T)} triangles: a larger cell (2000000 at most)."[:70],
]

# What some cases must have answered (so that two empty runs alike do not pass).
EXPECT = {
    ("meshobj_info", "clean"): {"mesh": "Cube", "facets": 12, "solid": True, "verdict": "clean"},
    ("meshobj_decimate", "half"): {"reduced": "12 → 6 triangles", "before": {"facets": 12}},
    ("meshobj_repair", "a tear undone"): {"did": ["normals", "duplicates", "nonmanifolds", "degenerate", "folds", "indices", "pointsonedges"]},
    ("meshobj_trim", "preview"): {"preview": True, "wouldRemove": 2, "wouldCut": 8},
    ("meshobj_boundary", "open cube"): {"loops": 1, "openEdges": 4, "wires": "Open boundary"},
    ("meshobj_boolean", "union"): {"op": "union", "mesh": "Cube union Other"},
    ("meshobj_edit", "use"): {"mesh": "Cube", "used": True},
    ("meshobj_primitive", "box"): {"mesh": "Mesh box", "kind": "box"},
    ("meshobj_split", "two pieces"): {"from": "Cube", "pieces": ["Cube 1", "Cube 2"]},
    ("points_info", "a grid"): {"object": "Scan", "points": 100, "box": [9.0, 9.0, 0.9]},
    ("points_crop", "box"): {"from": 100, "kept": 25},
    ("points_fit", "plane"): {"shape": "plane", "rms": 0.0},
    ("points_fit", "sphere, made"): {"shape": "sphere", "radius": 10.0, "body": "Ball sphere"},
    ("points_merge", "two, removed"): {"points": "Both", "count": 200, "removed": True},
    ("points_mesh", "hull"): {"method": "hull", "mesh": "Ball mesh"},
    ("points_import", "text"): {"object": "scan", "points": 2, "read": 4},
}


def cases(fc, tmp):
    out = []

    def C(tool, case, args, prep=None, **flags):
        def prepare(s):
            fc.state["flags"].update(flags)
            (prep or one)(s)

        out.append((tool, case, prepare, args))

    def none(s):
        pass

    def one(s):
        s.mesh("Cube")

    def two(s):
        s.mesh("Cube")
        s.mesh("Other", fc.cube(at=(5, 5, 5)))

    def opened(s):
        s.mesh("Open", fc.open_cube())

    def body(s):
        s.shape("Body")

    def with_problems(*problems, **kw):
        def prep(s):
            m = fc.cube(**kw)
            m.problems.update(problems)
            s.mesh("Cube", m)

        return prep

    # ---- finding the mesh (through every tool's first step) ----
    C("meshobj_info", "clean", {})
    C("meshobj_info", "by name", {"mesh": "Other"}, two)
    C("meshobj_info", "no mesh", {}, none)
    C("meshobj_info", "which", {}, two)
    C("meshobj_info", "not found", {"mesh": "Nope"}, two)
    C("meshobj_info", "problems", {}, with_problems("nonManifolds", "selfIntersections", "flippedNormals"))
    C("meshobj_info", "open", {}, opened)
    C("meshobj_info", "a check this build lacks", {}, no_invalid_points_check=True)

    # ---- from a shape ----
    C("meshobj_from_shape", "standard", {}, body)
    C("meshobj_from_shape", "named", {"body": "Body", "name": "Shell", "deflection": 0.2, "angle": 30}, body)
    C("meshobj_from_shape", "no body", {}, none)
    C("meshobj_from_shape", "two bodies, none named", {}, lambda s: (s.shape("A"), s.shape("B")))
    C("meshobj_from_shape", "not that body", {"body": "Nope"}, body)
    C("meshobj_from_shape", "no faces", {"body": "Wire"}, lambda s: s.shape("Wire", fc.wire_shape()))
    C("meshobj_from_shape", "bad deflection", {"deflection": 0}, body)
    C("meshobj_from_shape", "bad angle", {"angle": 120}, body)
    C("meshobj_from_shape", "deflection not a number", {"deflection": "fine"}, body)
    C("meshobj_from_shape", "mefisto", {"method": "mefisto", "maxLength": 3}, body)
    C("meshobj_from_shape", "mefisto bad length", {"method": "mefisto", "maxLength": -1}, body)
    C("meshobj_from_shape", "netgen", {"method": "netgen", "fineness": "fine"}, body)
    C("meshobj_from_shape", "netgen bad fineness", {"method": "netgen", "fineness": "finest"}, body)
    C("meshobj_from_shape", "bad method", {"method": "magic"}, body)
    C("meshobj_from_shape", "mesher fails", {}, body, meshing="raises")
    C("meshobj_from_shape", "netgen missing", {"method": "netgen"}, body, meshing="raises")
    C("meshobj_from_shape", "meshed open", {"method": "mefisto"}, body, meshing="open")
    C("meshobj_from_shape", "meshed non-manifold", {"method": "mefisto"}, body, meshing="nonmanifold")
    C("meshobj_from_shape", "dense", {}, body, meshing="dense")

    # ---- repair ----
    C("meshobj_repair", "default", {}, with_problems("nonManifolds", "flippedNormals"))
    C("meshobj_repair", "chosen", {"fix": ["holes", "islands", "normals"], "maxHoleEdges": 9, "minFacets": 3}, opened)
    C("meshobj_repair", "copy", {"fix": ["degenerate"], "tolerance": 0.001, "copy": True, "name": "Mended"}, with_problems("corruptedFacets"))
    C("meshobj_repair", "unknown fix", {"fix": ["normals", "magic"]})
    C("meshobj_repair", "fix not a list", {"fix": "normals"})
    C("meshobj_repair", "a tear undone", {}, with_problems("selfIntersections"), tears=("fixSelfIntersections",))
    C("meshobj_repair", "a step fails", {}, None, raises=("removeNonManifoldPoints",))
    C("meshobj_repair", "nothing kept", {"fix": ["folds"]}, None, empties=("removeFoldsOnSurface",))
    C("meshobj_repair", "inside out", {"fix": ["normals"]}, lambda s: s.mesh("Cube", fc.cube(volume=-1000.0)))

    # ---- decimate, refine, smooth, offset (already data) ----
    C("meshobj_decimate", "half", {})
    C("meshobj_decimate", "facets", {"facets": 8, "copy": True})
    C("meshobj_decimate", "facets too many", {"facets": 12})
    C("meshobj_decimate", "facets too few", {"facets": 3})
    C("meshobj_decimate", "bad reduction", {"reduction": 1})
    C("meshobj_decimate", "reduction not a number", {"reduction": "half"})
    C("meshobj_decimate", "bad tolerance", {"tolerance": 0})
    C("meshobj_decimate", "stops short", {"reduction": 0.5, "tolerance": 0.02}, None, decimate_stops=True)
    C("meshobj_refine", "once", {})
    C("meshobj_refine", "three, optimized, copy", {"rounds": 3, "optimize": True, "copy": True})
    C("meshobj_refine", "bad rounds", {"rounds": 4})
    C("meshobj_refine", "rounds true", {"rounds": True})
    C("meshobj_refine", "too many", {"rounds": 3}, lambda s: s.mesh("Big", fc.Mesh([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)] * 80000)))
    C("meshobj_smooth", "taubin", {})
    C("meshobj_smooth", "laplace", {"method": "laplace", "iterations": 5, "lambda": 0.5})
    C("meshobj_smooth", "taubin with mu", {"lambda": 0.5, "mu": 0.1, "copy": True, "name": "Smooth"})
    C("meshobj_smooth", "bad iterations", {"iterations": 0})
    C("meshobj_smooth", "iterations not whole", {"iterations": 2.5})
    C("meshobj_smooth", "bad method", {"method": "magic"})
    C("meshobj_smooth", "shrinks", {}, None, shrinks=0.8)
    C("meshobj_smooth", "shrinks a little", {}, None, shrinks=0.99)
    C("meshobj_smooth", "open mesh", {}, opened)

    # ---- edit on a copy ----
    def editing(s):
        s.mesh("Cube")
        s.mesh("Cube (editing)", fc.open_cube())
        s.doc.records["meshEdit"] = '{"Cube": "Cube (editing)"}'

    C("meshobj_edit", "state, none", {})
    C("meshobj_edit", "state", {"action": "state"}, editing)
    C("meshobj_edit", "begin", {"action": "begin"})
    C("meshobj_edit", "begin, in the window", {"action": "begin", "mesh": "Cube"}, None, views=True)
    C("meshobj_edit", "begin twice", {"action": "begin", "mesh": "Cube"}, editing)
    C("meshobj_edit", "use", {"action": "use"}, editing)
    C("meshobj_edit", "use by name", {"action": "use", "mesh": "Cube"}, editing, views=True)
    C("meshobj_edit", "discard", {"action": "discard", "mesh": "Cube (editing)"}, editing)
    C("meshobj_edit", "no edit of that", {"action": "use", "mesh": "Other"}, editing)
    C("meshobj_edit", "no edit at all", {"action": "discard"})
    C("meshobj_edit", "copy gone", {"action": "use"}, lambda s: (s.mesh("Cube"), s.doc.records.update(meshEdit='{"Cube": "Cube (editing)"}')))
    C("meshobj_edit", "copy gone, discard", {"action": "discard"}, lambda s: (s.mesh("Cube"), s.doc.records.update(meshEdit='{"Cube": "Cube (editing)"}')))
    C("meshobj_edit", "bad action", {"action": "magic"}, editing)
    C("meshobj_decimate", "on the copy being edited", {"mesh": "Cube"}, editing)

    # ---- trim ----
    C("meshobj_trim", "default", {"at": [0, 0, 5]})
    C("meshobj_trim", "preview", {"at": [0, 0, 5], "preview": True})
    C("meshobj_trim", "closed", {"at": [0, 0, 5], "close": True, "maxHoleEdges": 40})
    C("meshobj_trim", "does not close", {"at": [0, 0, 5], "close": True, "copy": True}, None, stays_open=True)
    C("meshobj_trim", "bad at", {"at": [0, 0]})
    C("meshobj_trim", "bad normal", {"normal": "up"})
    C("meshobj_trim", "zero normal", {"normal": [0, 0, 0]})
    C("meshobj_trim", "nothing left", {"at": [0, 0, -5]}, None, trim_leaves_nothing=True)

    # ---- transform ----
    C("meshobj_transform", "nothing asked", {})
    C("meshobj_transform", "scale", {"scale": 2})
    C("meshobj_transform", "scale three ways, one negative", {"scale": [1, -2, 3]})
    C("meshobj_transform", "scale zero", {"scale": [1, 0, 1]})
    C("meshobj_transform", "scale true", {"scale": True})
    C("meshobj_transform", "rotate", {"rotate": {"angle": 90}})
    C("meshobj_transform", "rotate about x", {"rotate": {"axis": [1, 0, 0], "angle": 45}})
    C("meshobj_transform", "rotate not an object", {"rotate": 90})
    C("meshobj_transform", "rotate angle not a number", {"rotate": {"angle": "90"}})
    C("meshobj_transform", "rotate zero axis", {"rotate": {"axis": [0, 0, 0], "angle": 10}})
    C("meshobj_transform", "rotate bad axis", {"rotate": {"axis": "z", "angle": 10}})
    C("meshobj_transform", "move", {"move": [1, 2, 3]})
    C("meshobj_transform", "bad move", {"move": [1, 2]})
    C("meshobj_transform", "mirror", {"mirror": "y"})
    C("meshobj_transform", "bad mirror", {"mirror": "w"})
    C("meshobj_transform", "all, copied", {"scale": -1, "rotate": {"angle": 30}, "move": [0, 0, 5], "mirror": "z", "copy": True})
    C("meshobj_transform", "a placed mesh", {"move": [1, 0, 0]}, lambda s: s.mesh("Placed", fc.cube(placement=fc.Placement(fc.Vec(5, 0, 0)))))

    # ---- boolean ----
    C("meshobj_boolean", "union", {"a": "Cube", "b": "Other"}, two)
    C("meshobj_boolean", "difference, named", {"a": "Cube", "b": "Other", "op": "difference", "name": "Cut"}, two)
    C("meshobj_boolean", "intersection", {"a": "Cube", "b": "Other", "op": "intersection"}, two)
    C("meshobj_boolean", "not closed", {"a": "Cube", "b": "Open"}, lambda s: (s.mesh("Cube"), s.mesh("Open", fc.open_cube())))
    C("meshobj_boolean", "bad op", {"a": "Cube", "b": "Other", "op": "xor"}, two)
    C("meshobj_boolean", "no such mesh", {"a": "Cube", "b": "Nope"}, two)
    C("meshobj_boolean", "nothing left", {"a": "Cube", "b": "Other", "op": "intersection"}, two, own_bool="empty")
    C("meshobj_boolean", "reads back open", {"a": "Cube", "b": "Other"}, two, reads_back_open=True)
    C("meshobj_boolean", "points and facets not taken", {"a": "Cube", "b": "Other"}, two, no_indexed_facets=True)
    C("meshobj_boolean", "own refuses, FreeCAD's works", {"a": "Cube", "b": "Other"}, two, own_bool="refuses")
    for how in ("raises", "empty", "open", "problems"):
        C("meshobj_boolean", f"FreeCAD's {how}, through solids", {"a": "Cube", "b": "Other", "op": "difference", "deflection": 0.1}, two, own_bool="refuses", fc_bool=how)
    C("meshobj_boolean", "too dense for solids", {"a": "Cube", "b": "Other", "maxFacets": 10}, two, own_bool="refuses", fc_bool="open")
    C("meshobj_boolean", "solids fail", {"a": "Cube", "b": "Other"}, two, own_bool="refuses", fc_bool="open", solid_bool="raises")
    C("meshobj_boolean", "solids leave nothing", {"a": "Cube", "b": "Other"}, two, own_bool="refuses", fc_bool="open", solid_bool="empty")

    # ---- sections ----
    C("meshobj_sections", "five", {})
    C("meshobj_sections", "at", {"at": [2, 5.5], "normal": [0, 0, 2], "name": "Cuts", "tolerance": 0.1})
    C("meshobj_sections", "count along x, down", {"count": 2, "normal": [-1, 0, 0]})
    C("meshobj_sections", "answered twice", {"count": 1}, None, sections_twice=True)
    C("meshobj_sections", "zero normal", {"normal": [0, 0, 0]})
    C("meshobj_sections", "bad at", {"at": []})
    C("meshobj_sections", "at not numbers", {"at": [1, "2"]})
    C("meshobj_sections", "bad count", {"count": 0})
    C("meshobj_sections", "count true", {"count": True})
    C("meshobj_sections", "bad tolerance", {"tolerance": 0})
    C("meshobj_sections", "none met", {"at": [50]}, None, no_sections=True)
    C("meshobj_sections", "a loop makes no wire", {"count": 1}, None, polygon_raises=True)

    # ---- split ----
    def pieces(n):
        def prep(s):
            parts = [fc.Mesh(fc.cube().pts, fc.cube().tris[:(2 + i % 3)]) for i in range(n)]
            o = s.mesh("Cube", fc.cube(parts=parts))
            o.__dict__["Visibility"] = True

        return prep

    C("meshobj_split", "two pieces", {}, pieces(2))
    C("meshobj_split", "one piece", {})
    C("meshobj_split", "least", {"minFacets": 3}, pieces(5))
    C("meshobj_split", "bad least", {"minFacets": 0}, pieces(2))
    C("meshobj_split", "least true", {"minFacets": True}, pieces(2))
    C("meshobj_split", "none that large", {"minFacets": 50}, pieces(3))
    C("meshobj_split", "crumbs", {}, pieces(120))

    # ---- segments ----
    C("meshobj_segments", "planar", {})
    C("meshobj_segments", "planar kept", {"keep": True, "top": 2, "deviation": 0.1, "minFacets": 2})
    C("meshobj_segments", "curvature", {"kind": "curvature", "tolerance": 0.02})
    C("meshobj_segments", "bad kind", {"kind": "magic"})
    C("meshobj_segments", "bad minFacets", {"minFacets": 0})
    C("meshobj_segments", "bad top", {"top": 1.5})
    C("meshobj_segments", "bad deviation", {"deviation": 0})
    C("meshobj_segments", "bad tolerance", {"kind": "curvature", "tolerance": -1})
    C("meshobj_segments", "curvature fails", {"kind": "curvature"}, None, curvature_fails=True)
    C("meshobj_segments", "none, planar", {"keep": True}, None, no_segments=True)
    C("meshobj_segments", "none, curvature", {"kind": "curvature"}, None, no_segments=True)

    # ---- curvature, projection ----
    C("meshobj_curvature", "default", {})
    C("meshobj_curvature", "flat", {"flat": 0.5}, None, flat=True)
    C("meshobj_curvature", "no triangles", {}, lambda s: s.mesh("Empty", fc.Mesh()))

    def under(s):
        s.mesh("Cube")
        s.shape("Line", fc.wire_shape())

    C("meshobj_project", "down", {"shape": "Line"}, under)
    C("meshobj_project", "named, sideways", {"shape": "Line", "direction": [1, 0, 0], "name": "Trace", "mesh": "Cube"}, under)
    C("meshobj_project", "no such shape", {"shape": "Nope"}, under)
    C("meshobj_project", "no edges", {"shape": "Dot"}, lambda s: (s.mesh("Cube"), s.shape("Dot", fc.Shape("Vertex"))))
    C("meshobj_project", "zero direction", {"shape": "Line", "direction": [0, 0, 0]}, under)
    C("meshobj_project", "bad direction", {"shape": "Line", "direction": "down"}, under)
    C("meshobj_project", "fails", {"shape": "Line"}, under, projection="raises")
    C("meshobj_project", "nothing lands", {"shape": "Line"}, under, projection="none")

    # ---- primitives ----
    C("meshobj_primitive", "box", {}, none)
    C("meshobj_primitive", "box sized, placed, named", {"size": [1, 2, 3], "at": [5, 5, 5], "name": "Brick"}, none)
    C("meshobj_primitive", "bad size", {"size": [1, 2, 0]}, none)
    C("meshobj_primitive", "bad at", {"at": "here"}, none)
    C("meshobj_primitive", "bad segments", {"segments": 2}, none)
    C("meshobj_primitive", "sphere", {"kind": "sphere", "radius": 3, "segments": 24}, none)
    C("meshobj_primitive", "sphere bad radius", {"kind": "sphere", "radius": 0}, none)
    C("meshobj_primitive", "sphere radius not a number", {"kind": "sphere", "radius": "3"}, none)
    C("meshobj_primitive", "cylinder", {"kind": "cylinder", "radius": 4, "height": 1000}, none)
    C("meshobj_primitive", "cylinder bad radius", {"kind": "cylinder", "radius": 0}, none)
    C("meshobj_primitive", "cylinder bad height", {"kind": "cylinder", "height": -1}, none)
    C("meshobj_primitive", "cone", {"kind": "cone", "radius2": 2}, none)
    C("meshobj_primitive", "cone to a point", {"kind": "cone"}, none)
    C("meshobj_primitive", "cone bad radius2", {"kind": "cone", "radius2": -1}, none)
    C("meshobj_primitive", "torus", {"kind": "torus"}, none)
    C("meshobj_primitive", "torus on its side", {"kind": "torus", "radius": 20, "radius2": 5}, none, torus_on_side=True)
    C("meshobj_primitive", "torus bad ring", {"kind": "torus", "radius": 0}, none)
    C("meshobj_primitive", "torus bad tube", {"kind": "torus", "radius2": 0}, none)
    C("meshobj_primitive", "torus tube too wide", {"kind": "torus", "radius": 2, "radius2": 2}, none)
    C("meshobj_primitive", "bad kind", {"kind": "teapot"}, none)
    for k in ("box", "sphere", "cylinder", "cone", "torus"):
        C("meshobj_primitive", f"{k}: FreeCAD cannot build it", {"kind": k}, none, create_raises=True)

    # ---- merge, boundary, export ----
    C("meshobj_merge", "two", {"meshes": ["Cube", "Other"]}, two)
    C("meshobj_merge", "removed, named, placed", {"meshes": ["Cube", "Placed"], "remove": True, "name": "Both"},
      lambda s: (s.mesh("Cube"), s.mesh("Placed", fc.cube(placement=fc.Placement(fc.Vec(20, 0, 0))))))
    C("meshobj_merge", "one", {"meshes": ["Cube"]}, two)
    C("meshobj_merge", "not a list", {"meshes": "Cube"}, two)
    C("meshobj_merge", "twice", {"meshes": ["Cube", "Cube"]}, two)
    C("meshobj_merge", "not found", {"meshes": ["Cube", "Nope"]}, two)
    C("meshobj_boundary", "open cube", {}, opened)
    C("meshobj_boundary", "not kept", {"keep": False}, opened)
    C("meshobj_boundary", "named", {"name": "Rim", "mesh": "Open"}, opened)
    C("meshobj_boundary", "closed", {})
    C("meshobj_boundary", "no triangles", {}, lambda s: s.mesh("Empty", fc.Mesh()))
    C("meshobj_boundary", "a loop makes no face", {}, opened, face_raises=True)
    C("meshobj_boundary", "a strip", {}, lambda s: s.mesh("Strip", fc.Mesh([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (5, 5, 5), (6, 5, 5), (5, 6, 5)], [(0, 1, 2), (0, 2, 3), (4, 5, 6)])))
    C("meshobj_export", "default", {})
    C("meshobj_export", "obj", {"path": "part.OBJ"})
    C("meshobj_export", "bad format", {"path": "part.step"})
    C("meshobj_export", "no extension", {"path": "part"})
    C("meshobj_export", "no triangles", {}, lambda s: s.mesh("Empty", fc.Mesh()))
    C("meshobj_export", "write fails", {}, None, write_raises=True)
    C("meshobj_export", "nothing written", {"path": "part.amf"}, None, writes_nothing=True)

    # ---- unwrap ----
    def patch(s):
        s.mesh("Patch", fc.open_cube())

    C("meshobj_unwrap", "no flatmesh", {"of": "Patch"}, patch, no_flatmesh=True)
    C("meshobj_unwrap", "of not a name", {"of": 3}, patch)
    C("meshobj_unwrap", "a mesh", {"of": "Patch"}, patch)
    C("meshobj_unwrap", "a mesh, written, not made", {"of": "Patch", "path": "patch.svg", "make": False, "iterations": 3, "weight": 0.5}, patch)
    C("meshobj_unwrap", "a mesh, dxf, stretched", {"of": "Patch", "path": "patch.dxf", "name": "Flat"}, patch, unwrap="stretched")
    C("meshobj_unwrap", "closed mesh", {"of": "Cube"})
    C("meshobj_unwrap", "pieces", {"of": "Bits"}, lambda s: s.mesh("Bits", fc.open_cube(comps=3)))
    C("meshobj_unwrap", "too dense", {"of": "Big"}, lambda s: s.mesh("Big", fc.Mesh([(0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)], [(0, 1, 2)] * 50001, solid=False)))
    C("meshobj_unwrap", "no area", {"of": "Tri"}, lambda s: s.mesh("Tri", fc.Mesh([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])))
    C("meshobj_unwrap", "flatmesh stops", {"of": "Patch"}, patch, unwrap="stops")
    C("meshobj_unwrap", "a whole body", {"of": "Body"}, lambda s: s.shape("Body", fc.faced("Cylinder")))
    C("meshobj_unwrap", "no such object", {"of": "Nope.Face1"}, patch)
    for kind in ("Plane", "Cylinder", "Cone"):
        C("meshobj_unwrap", f"a {kind} face", {"of": "Body.Face1"}, lambda s, kind=kind: s.shape("Body", fc.faced(kind)))
    C("meshobj_unwrap", "a cone face, written and named", {"of": "Body.Face1", "path": "cone.dxf", "name": "Cone flat"}, lambda s: s.shape("Body", fc.faced("Cone")))
    C("meshobj_unwrap", "a plane face, svg, not made", {"of": "Body.Face1", "path": "plane.svg", "make": False, "tolerance": 0.5}, lambda s: s.shape("Body", fc.faced("Plane")))
    C("meshobj_unwrap", "a curved face", {"of": "Body.Face1", "tolerance": 0.2}, lambda s: s.shape("Body", fc.faced("BSplineSurface")))
    # ================= point clouds =================
    import math
    import os

    def grid(n=10, z=lambda i, j: 0.1 * i):
        return [(float(i), float(j), z(i, j)) for i in range(n) for j in range(n)]

    def ball(n=12, r=10.0):
        return [(r * math.sin(math.pi * (i + 0.5) / n) * math.cos(2 * math.pi * j / n), r * math.sin(math.pi * (i + 0.5) / n) * math.sin(2 * math.pi * j / n),
                 r * math.cos(math.pi * (i + 0.5) / n)) for i in range(n) for j in range(n)]

    def tube(n=16, r=5.0, h=20.0):
        return [(r * math.cos(2 * math.pi * j / n), r * math.sin(2 * math.pi * j / n), h * i / 9) for i in range(10) for j in range(n)]

    def ring(n=40, r=10.0):
        return [(r * math.cos(2 * math.pi * j / n), r * math.sin(2 * math.pi * j / n), 0.0) for j in range(n)]

    def line(n=30):
        return [(float(i), 0.05 * (i % 2), 0.0) for i in range(n)]

    def scan(s):
        s.cloud("Scan", grid())

    def cloud_of(label, pts, more=None):
        def prep(s):
            s.cloud(label, pts)
            if more:
                more(s)

        return prep

    def files(s):
        with open(os.path.join(s.out_dir, "scan.xyz"), "w") as f:
            f.write("x y z\n0 0 0\n1,0,0\n0;1;0\n1 1 nan\n2 2 2 255\n3 3\n")
        with open(os.path.join(s.out_dir, "empty.csv"), "w") as f:
            f.write("x,y,z\n")
        with open(os.path.join(s.out_dir, "nan.asc"), "w") as f:
            f.write("nan nan nan\ninf 0 0\n")
        with open(os.path.join(s.out_dir, "bad.ply"), "wb") as f:
            f.write(b"not a ply")
        for n in ("scan.e57", "scan.stl"):
            with open(os.path.join(s.out_dir, n), "wb") as f:
                f.write(b"x")

    C("points_import", "text", {"path": "scan.xyz", "every": 2}, files)
    C("points_import", "scaled, named", {"path": "scan.xyz", "scale": 1000, "name": "Metres"}, files)
    C("points_import", "no path", {}, files)
    C("points_import", "no such file", {"path": "nope.xyz"}, files)
    C("points_import", "not a format", {"path": "scan.stl"}, files)
    C("points_import", "bad every", {"path": "scan.xyz", "every": 0}, files)
    C("points_import", "bad scale", {"path": "scan.xyz", "scale": 0}, files)
    C("points_import", "scale not a number", {"path": "scan.xyz", "scale": "m"}, files)
    C("points_import", "unreadable", {"path": "bad.ply"}, files)
    C("points_import", "no points", {"path": "empty.csv"}, files)
    C("points_import", "all nan", {"path": "nan.asc"}, files)
    C("points_import", "e57", {"path": "scan.e57"}, files)
    C("points_import", "e57 with a nan", {"path": "scan.e57"}, files, e57="nan")
    C("points_import", "e57 without the library", {"path": "scan.e57"}, files, e57="raises")
    C("points_import", "e57 empty", {"path": "scan.e57"}, files, e57="empty")

    C("points_sample", "a body", {"object": "Body", "count": 50}, body)
    C("points_sample", "a mesh, noisy, named", {"object": "Cube", "count": 20, "noise": 0.1, "seed": 7, "name": "Dots"})
    C("points_sample", "no object", {}, body)
    C("points_sample", "not found", {"object": "Nope"}, body)
    C("points_sample", "bad count", {"object": "Body", "count": 2}, body)
    C("points_sample", "bad noise", {"object": "Body", "noise": -1}, body)
    C("points_sample", "no faces", {"object": "Wire"}, lambda s: s.shape("Wire", fc.wire_shape()))
    C("points_sample", "not a shape", {"object": "Scan"}, scan)
    C("points_sample", "bad tolerance", {"object": "Body", "tolerance": 0}, body)
    C("points_sample", "tolerance not a number", {"object": "Body", "tolerance": "fine"}, body)
    C("points_sample", "no triangles", {"object": "Body"}, body, no_triangles=True)
    C("points_sample", "no area", {"object": "Flat"}, lambda s: s.mesh("Flat", fc.Mesh([(0, 0, 0), (1, 0, 0), (2, 0, 0)], [(0, 1, 2)])))

    C("points_info", "a grid", {}, scan)
    C("points_info", "by name", {"points": "Ball"}, cloud_of("Ball", ball(), scan))
    C("points_info", "none", {}, none)
    C("points_info", "which", {}, cloud_of("Ball", ball(), scan))
    C("points_info", "not a cloud", {"points": "Cube"}, lambda s: (s.mesh("Cube"), scan(s)))
    C("points_info", "not a cloud, no clouds", {"points": "Cube"})
    C("points_info", "not found", {"points": "Nope"}, scan)
    C("points_info", "one point", {}, cloud_of("Dot", [(1, 2, 3)]))
    C("points_info", "no points", {}, cloud_of("Empty", []))

    C("points_crop", "box", {"box": [[4, 4, -1], [0, 0, 5]]}, scan)
    C("points_crop", "bad box", {"box": [[0, 0, 0]]}, scan)
    C("points_crop", "near", {"near": [5, 5, 0.5], "radius": 2, "replace": False}, scan)
    C("points_crop", "near, no radius", {"near": [5, 5, 0.5]}, scan)
    C("points_crop", "near, bad radius", {"near": [5, 5, 0.5], "radius": 0}, scan)
    C("points_crop", "near, radius not a number", {"near": [5, 5, 0.5], "radius": "2"}, scan)
    C("points_crop", "bad near", {"near": "here", "radius": 2}, scan)
    C("points_crop", "plane", {"plane": {"at": [5, 0, 0], "normal": [1, 0, 0]}, "replace": False, "name": "Half"}, scan)
    C("points_crop", "plane, defaults", {"plane": {}}, scan)
    C("points_crop", "plane not an object", {"plane": [0, 0, 1]}, scan)
    C("points_crop", "plane zero normal", {"plane": {"normal": [0, 0, 0]}}, scan)
    C("points_crop", "plane normal not a direction", {"plane": {"normal": "up"}}, scan)
    C("points_crop", "plane bad at", {"plane": {"at": [1]}}, scan)
    C("points_crop", "nothing to do", {}, scan)
    C("points_crop", "outside of nothing", {"outside": True, "thin": 2}, scan)
    C("points_crop", "outside", {"box": [[0, 0, -1], [4, 4, 5]], "outside": True}, scan)
    C("points_crop", "thin", {"thin": 3}, scan)
    C("points_crop", "bad thin", {"thin": -1}, scan)
    C("points_crop", "thin not a number", {"thin": "coarse"}, scan)
    C("points_crop", "specks", {"specks": {"radius": 1.5, "least": 3}}, cloud_of("Scan", grid() + [(50.0, 50.0, 50.0)]))
    C("points_crop", "specks, defaults, with a box", {"specks": {}, "box": [[0, 0, -1], [9, 9, 5]]}, cloud_of("Scan", grid() + [(50.0, 50.0, 50.0)]))
    C("points_crop", "bad specks", {"specks": {"radius": 0}}, scan)
    C("points_crop", "nothing left", {"box": [[100, 100, 100], [200, 200, 200]]}, scan)
    C("points_crop", "all three", {"box": [[0, 0, -1], [8, 8, 5]], "near": [4, 4, 0.4], "radius": 4, "plane": {"at": [2, 0, 0], "normal": [1, 0, 0]}, "thin": 2}, scan)

    C("points_fit", "plane", {}, cloud_of("Flat", grid(z=lambda i, j: 0.0)))
    C("points_fit", "plane, made, named, toleranced", {"make": True, "name": "Datum", "tolerance": 0.5}, scan)
    C("points_fit", "plane, does not fit", {"tolerance": 0.001}, cloud_of("Bumpy", grid(z=lambda i, j: (i * j) % 3)))
    C("points_fit", "bad shape", {"shape": "torus"}, scan)
    C("points_fit", "bad tolerance", {"tolerance": 0}, scan)
    C("points_fit", "too few points", {}, cloud_of("Two", [(0, 0, 0), (1, 1, 1)]))
    C("points_fit", "sphere", {"shape": "sphere"}, cloud_of("Ball", ball()))
    C("points_fit", "sphere, made", {"shape": "sphere", "make": True}, cloud_of("Ball", ball()))
    C("points_fit", "cylinder", {"shape": "cylinder"}, cloud_of("Tube", tube()))
    C("points_fit", "cylinder, hinted, made", {"shape": "cylinder", "axis": [0, 0, 1], "make": True, "tolerance": 1}, cloud_of("Tube", tube()))
    C("points_fit", "cylinder, zero axis", {"shape": "cylinder", "axis": [0, 0, 0]}, cloud_of("Tube", tube()))
    C("points_fit", "cylinder, bad axis", {"shape": "cylinder", "axis": "up"}, cloud_of("Tube", tube()))
    C("points_fit", "surface", {"shape": "surface"}, scan)
    C("points_fit", "surface, set, toleranced", {"shape": "surface", "degree": 2, "poles": 4, "smooth": False, "weight": 0.5, "iterations": 2, "name": "Sheet", "tolerance": 0.01}, scan)
    C("points_fit", "surface, no Reverse Engineering", {"shape": "surface"}, scan, missing=("ReverseEngineering",))
    C("points_fit", "surface, bad degree", {"shape": "surface", "degree": 0}, scan)
    C("points_fit", "surface, too few poles", {"shape": "surface", "poles": 3}, scan)
    C("points_fit", "surface, too few points", {"shape": "surface", "poles": 11}, scan)
    C("points_fit", "surface, too many points", {"shape": "surface"}, cloud_of("Dense", [(float(i % 500), float(i // 500), 0.0) for i in range(200001)]))
    C("points_fit", "surface, fails", {"shape": "surface"}, scan, no_surface=True)
    C("points_fit", "curve, a loop", {"shape": "curve"}, cloud_of("Ring", ring()))
    C("points_fit", "curve, open", {"shape": "curve", "degree": 4, "tolerance": 0.2, "name": "Path"}, cloud_of("Line", line()))
    C("points_fit", "curve, a loop left open", {"shape": "curve", "closed": False}, cloud_of("Ring", ring()))
    C("points_fit", "curve, closed asked of a line", {"shape": "curve", "closed": True}, cloud_of("Line", line()))
    C("points_fit", "curve, too few", {"shape": "curve"}, cloud_of("Three", line(3)))
    C("points_fit", "curve, fails", {"shape": "curve"}, cloud_of("Line", line()), no_curve=True)

    def two_clouds(s):
        s.cloud("Scan", grid())
        s.cloud("More", grid(z=lambda i, j: 5.0))

    C("points_merge", "two, removed", {"points": ["Scan", "More"], "remove": True, "name": "Both"}, two_clouds)
    C("points_merge", "two", {"points": ["Scan", "More"]}, two_clouds)
    C("points_merge", "one", {"points": ["Scan"]}, two_clouds)
    C("points_merge", "not a list", {"points": "Scan"}, two_clouds)
    C("points_merge", "twice", {"points": ["Scan", "Scan"]}, two_clouds)
    C("points_merge", "not found", {"points": ["Scan", "Nope"]}, two_clouds)

    C("points_mesh", "height", {}, scan)
    C("points_mesh", "height, cell, named", {"cell": 2.5, "name": "Terrain"}, scan)
    C("points_mesh", "bad method", {"method": "magic"}, scan)
    C("points_mesh", "too few", {}, cloud_of("Three", line(3)))
    C("points_mesh", "bad cell", {"cell": 0}, scan)
    C("points_mesh", "no triangles", {"cell": 0.01}, scan)
    C("points_mesh", "hull", {"method": "hull"}, cloud_of("Ball", ball()), mesh_closed=True)
    C("points_mesh", "poisson", {"method": "poisson", "depth": 6}, cloud_of("Ball", ball()))
    C("points_mesh", "poisson, an older build", {"method": "poisson"}, cloud_of("Ball", ball()), poisson="old")
    C("points_mesh", "poisson, open", {"method": "poisson"}, cloud_of("Ball", ball()), poisson="open")
    C("points_mesh", "poisson, no PCL", {"method": "poisson"}, cloud_of("Ball", ball()), poisson="raises")
    C("points_mesh", "poisson, no Reverse Engineering", {"method": "poisson"}, cloud_of("Ball", ball()), missing=("ReverseEngineering",))

    C("points_export", "default", {}, cloud_of("My scan", grid()))
    for ext in ("pcd", "asc", "xyz", "csv"):
        C("points_export", ext, {"path": f"sub/out.{ext}"}, scan)
    C("points_export", "bad format", {"path": "out.stl"}, scan)
    C("points_export", "no ending", {"path": "out"}, scan)
    C("points_export", "no points", {}, cloud_of("Empty", []))
    return out
