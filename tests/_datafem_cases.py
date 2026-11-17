# SPDX-License-Identifier: LGPL-2.1-or-later
# The cases tests/test_datafem_data.py runs through the old handler and the
# new data entry of each converted tool of families/material.py, fem_more.py
# and strength.py, on the stand-in FreeCAD (tests/_datafem_standin.py): its
# normal paths and each of its refusals.

# The family files whose tools were converted.
FILES = ("material", "fem_more", "strength")
STRENGTH = ("fea_setup", "fea_hold", "fea_load", "fea_results", "fea_clear", "fea_refine", "fea_export", "fea_probe", "fea_chart", "fea_modes", "fea_buckle", "fea_heat", "fea_shell", "fea_parts", "fea_native", "fea_solve")
# Each converted tool and its group.
CONVERTED = {**{k: "material" for k in ("material_list", "material_get", "material_set", "material_clear")},
             **{k: "fem_more" for k in ("fem_add", "fem_mesh", "fem_linearize")},
             **{k: "strength" for k in STRENGTH}}
# Tools of those files kept as code, and why: none.
KEPT = {}
# What some cases must have answered (not two empty runs alike): fields of an answer, or the whole refusal.
EXPECT = {
    ("material_list", "steel"): {"found": 1, "materials": [{"id": "uuid-steel", "name": "Steel-S235", "category": "Metal/Steel", "density": 7.85, "E": 210000.0, "yield": 235.0}]},
    ("material_list", "no library, nothing matches"): {"found": 0, "note": "Nothing matches: fewer words (every word must be found), or a category from categories. FreeCAD's library is not in this build: the printing filaments only."},
    ("material_get", "unknown"): ["refused", "not_found", "material 'unobtainium': no such id or name — material_list { words } finds one (a filament key such as pla, a library card's id or exact name, or custom:<name>)."],
    ("material_set", "a library card on two bodies"): {"bodies": ["Block", "Pin"], "shapeMaterial": {"Block": True, "Pin": False}, "mass_g": {"Block": 7.85, "Pin": 3.925},
                                                      "shapeMaterialNote": "Not every body's ShapeMaterial was set: only FreeCAD library cards go there; the material is kept with the document either way."},
    ("material_set", "custom, full"): {"material": {"id": "custom:acme-pa12-gf", "name": "Acme PA12 GF", "category": "Custom", "density": 1.2, "E": 4200, "yield": 60}},
    ("material_set", "custom, an odd figure"): ["refused", "invalid_input", "custom.colour: not a figure kept here — custom takes conductivity, density, name, poisson, softensC, source, utsMPa, yieldMPa, youngsMPa."],
    ("material_clear", "two named, one had none"): {"cleared": ["Block"], "materials": {}, "hadNone": ["Pin"]},
    ("fem_add", "a displacement on two faces, with props"): {"added": "Push", "kind": "displacement", "analysis": "Analysis", "type": "Fem::ConstraintDisplacement", "refs": ["Block.Face1", "Block.Face2"]},
    ("fem_add", "a bare number for a quantity"): ["refused", "invalid_input", "props.xDisplacement = 2: FreeCAD refuses it (props.xDisplacement: a value with its unit, as text — e.g. \"2 mm\" (now 0 mm).) — now '0 mm'; "
                                                  "a value of that kind (an enumeration takes one of its own words)."],
    ("fem_add", "not in this FreeCAD"): ["refused", "unavailable", "tie is not in FreeCAD 1.1.3's FEM."],
    ("fem_mesh", "netgen says why"): ["refused", "unavailable", "Netgen did not mesh here (Error: surface 2 | Error: no mesh): it needs Netgen installed with this FreeCAD's Python. fea_native makes a Gmsh mesh instead."],
    ("fem_mesh", "to_mesh, deformed, named"): {"mesh": "Skin", "facets": 12, "deformed": "CCX_Results"},
    ("fem_mesh", "clear_groups"): {"mesh": "Mesh", "cleared": 2, "groups": 0},
    ("fem_linearize", "a pipeline"): {"result": "Pipeline", "field": "von Mises Stress", "thickness": 4.0, "membrane": 20.0, "bending": 0.0, "membranePlusBending": 20.0, "peak": 30.0, "points": 5},
    ("fem_linearize", "von Mises across a wall"): {"result": "CCX_Results", "thickness": 9.0, "membrane": 54.875, "bending": 45.6446, "membranePlusBending": 100.5196, "peak": 100.0, "points": 41},
    ("fem_linearize", "leaves the part"): ["refused", "invalid_input", "The line runs 90.01 mm from any node of the mesh: it leaves the part. from and to go across the wall, on its two faces."],
    ("fea_setup", "a mesh too fine to solve"): ["refused", "invalid_input", "mesh 0.1 mm makes some 7,999,999 elements: too many to solve here — 0.3 mm or more."],
    ("fea_setup", "a solid of a one-solid body"): ["refused", "invalid_state", "solid: 1 to 1 — Block has 1 solid: study the body itself (leave solid out)."],
    ("fea_hold", "pin"): {"kind": "pin", "holds": 2, "note": "Held in x, z only."},
    ("fea_load", "gravity, 2 g"): {"load": {"kind": "gravity", "gravity": [0.0, 0.0, -2.0]}, "loads": 2},
    ("fea_refine", "not finer"): ["refused", "invalid_input", "size 2 is not finer than the study's mesh (2 mm)."],
    ("fea_clear", "a study and its results"): {"cleared": True},
    ("fea_results", "the body gone"): {"stale": True, "staleWhy": ["the body is gone"], "next": "fea_solve again."},
    ("fea_export", "the csv, named"): {"files": {"csv": "<out>/bracket-run-2.csv"}, "nodes": 6, "elements": 1},
    ("fea_probe", "nothing asked"): ["refused", "invalid_input", "points [[x,y,z] …], line { from, to, samples }, and/or faces (a query as fea_hold takes)."],
    ("fea_chart", "one bin"): ["refused", "invalid_input", "bins: 2 … 200."],
    ("fea_modes", "free, two modes"): {"held": "free (no holds: the six rigid motions left out)", "modes": [{"mode": 1, "hz": 120.5, "moves": {"at": [5.0, 0.0, 10.0], "face": "Face1", "along": [0.0, 1.0, 0.0]}},
                                                                                                         {"mode": 2, "hz": 340.25, "moves": {"at": [5.0, 0.0, 10.0], "face": "Face1", "along": [0.0, 1.0, 0.0]}}]},
    ("fea_buckle", "little margin"): {"lowest": 2.25, "verdict": "Buckles at 2.25× these loads — under 3×: little margin; thin walls and columns want more.",
                                      "note": "Linear (eigenvalue) buckling: an upper bound — real parts, imperfect and printed, go sooner; keep a margin of 3 or more."},
    ("fea_heat", "heat on no element"): ["refused", "failed", "heat.0: no element faces on ['Face2'] — another mesh size."],
    ("fea_shell", "a plate under pressure, simply supported"): {"object": "Plate", "held": 5, "deflectionMaxMm": 0.1, "vonMisesMaxMPa": 40.0, "safety": 1.25},
    ("fea_parts", "a part of two solids"): ["refused", "invalid_state", "Twin has 2 solids: one solid a part (part_compound explode splits it)."],
    ("fea_native", "a solver unknown"): ["refused", "invalid_input", "solver: calculix or elmer."],
    ("fea_solve", "FreeCAD's FEM: a fixed hold and a force"): {"held": ["Face1"], "vonMisesMax": {"MPa": 40.0, "at": [5.0, 0.0, 10.0], "face": "Face1"}, "safety": 1.25,
                                                               "solvedBy": "FreeCAD's FEM (Block strength (fea_solve): CalculiX solver, Gmsh mesh, its constraints; results in the analysis)",
                                                               "warnings": ["Library and filament figures are typical: for a part that must not fail, use the supplier's data sheet (material_set custom)."]},
    ("fea_solve", "parts tied"): {"joined": {"how": "tie", "interfaces": 1}, "safety": None,
                                  "solvedBy": "Agent Link's own CalculiX deck — several parts tied or in contact (fea_parts) are solved by its own deck"},
    ("fea_solve", "two solids, one held by nothing"): ["refused", "invalid_state", "Twin is 2 separate solids and solid 2 (at [5.0, 5.0, 5.0]) touches no held face: a part held by nothing has no static answer, "
                                                       "and solids that only touch are not joined in the study. Hold each solid too (fea_hold its faces), study one alone (fea_setup { solid: n }), or fuse them for a check of the whole."],
    ("fea_solve", "nothing holds it"): ["refused", "invalid_state", "Nothing holds the part: fea_hold the faces it is mounted by — a free body has no static answer."],
}
# Refusals written in the data that no case here reaches.
UNREACHED = []


def cases(fc, tmp, old, new):
    from agentlink import store

    def prep(*fns, **flags):
        def prepare(s):
            fc.fc.GuiUp = False
            fc.state["flags"].update(flags)
            for fn in fns:
                fn(s)
        return prepare

    def block(s):
        fc.body("Block", fc.solid("block", (0, 0, 0), (10, 10, 10)), ShapeMaterial=None)

    def pin(s):
        fc.body("Pin", fc.solid("pin", (20, 0, 0), (25, 10, 10)))

    def custom_kept(s):
        store.write(s.doc, "materialDefs", {"custom:acme": {"id": "custom:acme", "name": "Acme", "category": "Custom", "density": 1.1, "E": 2000, "nu": 0.35, "yield": None, "uts": None, "k": None,
                                                           "softens": None, "source": "given by the person"}})

    def recorded(**mats):
        return lambda s: store.write(s.doc, "materials", mats)

    def service(fn):
        return lambda s: fc.hooks._SERVICES.update(material_set=fn)

    def raises(*a):
        raise KeyError("not one of mine")

    out = []

    def case(tool, name, prepare, args):
        out.append((tool, name, prepare, args))

    # ---- material_list ----
    t = "material_list"
    case(t, "everything", prep(), {})
    case(t, "steel", prep(), {"words": "steel"})
    case(t, "two words, spaced", prep(), {"words": "  Structural \t steel "})
    case(t, "a word in a description", prep(), {"words": "alloy"})
    case(t, "a category", prep(), {"category": "Metal"})
    case(t, "a category and a word", prep(), {"category": "printing", "words": "pla"})
    case(t, "named first", prep(), {"words": "pla"})
    case(t, "nothing matches", prep(), {"words": "unobtainium"})
    case(t, "limit 2", prep(), {"limit": 2})
    for i, bad in enumerate([0, 501, "5", True, 2.0]):
        case(t, f"limit bad {i}", prep(), {"limit": bad})
    case(t, "no library", prep(missing=("Materials",)), {})
    case(t, "no library, nothing matches", prep(missing=("Materials",)), {"words": "steel"})
    case(t, "a manager that fails", prep(fail=("MaterialManager",)), {"words": "pla"})
    case(t, "custom ones too", prep(custom_kept), {"words": "acme"})
    # ---- material_get ----
    t = "material_get"
    case(t, "a filament", prep(), {"id": "PLA"})
    case(t, "a library card", prep(), {"id": "uuid-steel"})
    case(t, "by name", prep(), {"id": "aluminum-6061-t6"})
    case(t, "a card that lacks figures", prep(), {"id": "uuid-foam"})
    case(t, "custom", prep(custom_kept), {"id": "custom:acme"})
    case(t, "custom by name", prep(custom_kept), {"id": "ACME"})
    case(t, "unknown", prep(), {"id": "unobtainium"})
    case(t, "no id", prep(), {})
    # ---- material_set ----
    t = "material_set"
    case(t, "a filament on the one body", prep(block), {"id": "PETG"})
    case(t, "pla, which the library has", prep(block), {"id": "pla"})
    case(t, "a library card on two bodies", prep(block, pin), {"bodies": ["Block", "Pin"], "id": "uuid-steel"})
    case(t, "a library card by name", prep(block), {"id": "Steel-S235"})
    case(t, "a card with no stiffness", prep(block), {"id": "uuid-foam"})
    case(t, "a card FreeCAD will not give", prep(block, fail=("getMaterial",)), {"id": "uuid-steel"})
    case(t, "no library", prep(block, missing=("Materials",)), {"id": "pla"})
    case(t, "custom, full", prep(block), {"custom": {"name": "Acme PA12 GF", "density": 1.2, "youngsMPa": 4200, "yieldMPa": 60, "utsMPa": 75, "poisson": 0.38, "conductivity": 0.3, "softensC": 150,
                                                      "source": "Acme data sheet"}})
    case(t, "custom, the least", prep(block), {"custom": {"name": "Mystery", "density": 2}})
    case(t, "custom again over one kept", prep(block, custom_kept), {"custom": {"name": "Acme", "density": 1.3, "youngsMPa": 2500}})
    case(t, "custom not an object", prep(block), {"custom": "steel"})
    case(t, "custom, empty", prep(block), {"custom": {}})
    case(t, "id and custom", prep(block), {"id": "pla", "custom": {"name": "X", "density": 1}})
    case(t, "custom, no name", prep(block), {"custom": {"name": "  ", "density": 1}})
    for i, rho in enumerate([None, "1.2", 0.01, 25, 30]):
        case(t, f"custom, density bad {i}", prep(block), {"custom": {"name": "X", "density": rho}})
    case(t, "custom, a figure not a number", prep(block), {"custom": {"name": "X", "density": 1, "yieldMPa": "60"}})
    case(t, "custom, a figure true", prep(block), {"custom": {"name": "X", "density": 1, "softensC": True}})
    case(t, "custom, an odd figure", prep(block), {"custom": {"name": "X", "density": 1, "colour": "red", "zeta": 1}})
    case(t, "neither", prep(block), {})
    case(t, "unknown", prep(block), {"id": "unobtainium"})
    case(t, "bodies not a list", prep(block), {"bodies": "Block", "id": "pla"})
    case(t, "bodies of numbers", prep(block), {"bodies": [1], "id": "pla"})
    case(t, "a body not here", prep(block), {"bodies": ["Gone"], "id": "pla"})
    case(t, "no body", prep(), {"id": "pla"})
    case(t, "two bodies, none named", prep(block, pin), {"id": "pla"})
    case(t, "an add-on owns it", prep(block, service(lambda doc, bodies, m: {"materials": {b: m for b in bodies}, "freecadMaterial": True})), {"id": "pla"})
    case(t, "an add-on that does not know it", prep(block, service(raises)), {"id": "uuid-steel"})
    case(t, "an add-on that answers nothing", prep(block, service(lambda doc, bodies, m: None)), {"id": "pla"})
    case(t, "custom is not the add-on's", prep(block, service(lambda doc, bodies, m: {"materials": {}})), {"custom": {"name": "Mine", "density": 1}})
    # ---- material_clear ----
    t = "material_clear"
    case(t, "every one", prep(block, pin, recorded(Block="pla", Pin="petg")), {})
    case(t, "one named", prep(block, pin, recorded(Block="pla", Pin="petg")), {"bodies": ["Pin"]})
    case(t, "two named, one had none", prep(block, pin, recorded(Block="pla")), {"bodies": ["Block", "Pin"]})
    case(t, "none recorded", prep(block), {})
    case(t, "bodies not a list", prep(block), {"bodies": "Block"})
    case(t, "a body not here", prep(block), {"bodies": ["Gone"]})
    case(t, "an add-on owns it", prep(block, recorded(Block="pla"), service(lambda doc, bodies, m: {"materials": {}, "freecadMaterial": False})), {"bodies": ["Block"]})
    case(t, "an add-on that fails", prep(block, recorded(Block="pla"), service(raises)), {})
    # ---- fem_add ----
    F = fc.objects_fem

    def analysis(s):
        F.makeAnalysis(s.doc, "Analysis")

    def member(maker, *more):
        def add(s):
            an = s.doc.getObject("Analysis")
            base = [s.doc.getObject(m) for m in more]
            an.addObject(getattr(F, maker)(s.doc, *base) if base else getattr(F, maker)(s.doc))
        return add

    t = "fem_add"
    case(t, "a displacement on two faces, with props", prep(block, analysis), {"kind": "displacement", "refs": ["Block.Face1", "Block.Face2"], "props": {"xFree": False, "xDisplacement": "2 mm", "Offset": [1, 2, 3]},
                                                                             "name": "Push"})
    case(t, "refs by query", prep(block, analysis, picks=["Face3", "Face4"]), {"kind": "displacement", "refs": {"body": "Block", "faces": [{"faces": ["Face1"]}, "Face2", {"normal": [0, 0, 1]}, "Face1"]}})
    case(t, "refs by one query", prep(block, analysis), {"kind": "fluid_boundary" if False else "contact", "refs": {"body": "Block", "faces": {"z": 0}}})
    case(t, "refs, no body", prep(block, analysis), {"kind": "contact", "refs": {"faces": "Face1"}})
    case(t, "a solid and a face of two bodies", prep(block, pin, analysis), {"kind": "spring", "refs": ["Block.Solid1", "Pin.Face2", "Block.Edge3"], "props": {"NormalStiffness": "1000 N/mm"}})
    case(t, "a solid it has not", prep(block, analysis), {"kind": "contact", "refs": ["Block.Solid2"]})
    case(t, "a whole object as a ref", prep(block, analysis), {"kind": "contact", "refs": ["Block"]})
    case(t, "a bare face", prep(block, analysis), {"kind": "contact", "refs": ["Face1"]})
    case(t, "a face it has not", prep(block, analysis), {"kind": "contact", "refs": ["Block.Face9"]})
    case(t, "a ref to nothing", prep(block, analysis), {"kind": "contact", "refs": ["Gone.Face1"]})
    case(t, "kind unknown", prep(block, analysis), {"kind": "glue"})
    case(t, "no kind", prep(block, analysis), {})
    case(t, "not in this FreeCAD", prep(block, analysis, missing=("ObjectsFem.makeConstraintTie",)), {"kind": "tie"})
    case(t, "a kind the stand-in FEM lacks", prep(block, analysis), {"kind": "gear"})
    case(t, "no FEM", prep(block, missing=("ObjectsFem",)), {"kind": "tie"})
    case(t, "no analysis", prep(block), {"kind": "tie"})
    case(t, "two analyses", prep(block, analysis, analysis), {"kind": "tie"})
    case(t, "two analyses, one named", prep(block, analysis, analysis), {"kind": "tie", "analysis": "Analysis001"})
    case(t, "an analysis not here", prep(block, analysis), {"kind": "tie", "analysis": "Other"})
    case(t, "a solver in a new analysis", prep(block, analysis), {"kind": "solver_elmer", "new": True, "name": "Thermal"})
    case(t, "a solver in a new analysis, unnamed", prep(block, analysis), {"kind": "solver_z88", "new": True})
    case(t, "new without a solver", prep(block), {"kind": "tie", "new": True})
    case(t, "a refinement on the analysis's Gmsh mesh", prep(block, analysis, member("makeMeshNetgen"), member("makeMeshGmsh")), {"kind": "mesh_region", "refs": ["Block.Face1"], "props": {"CharacteristicLength": "0.5 mm"}})
    case(t, "a refinement, only a Netgen mesh", prep(block, analysis, member("makeMeshNetgen")), {"kind": "mesh_group"})
    case(t, "a refinement on a named mesh", prep(block, analysis, lambda s: F.makeMeshGmsh(s.doc, "Loose")), {"kind": "mesh_region", "mesh": "Loose"})
    case(t, "a refinement, no mesh", prep(block, analysis), {"kind": "mesh_region"})
    case(t, "a refinement, mesh not here", prep(block, analysis), {"kind": "mesh_region", "mesh": "Gone"})
    case(t, "an equation on the Elmer solver", prep(block, analysis, member("makeSolverZ88"), member("makeSolverElmer")), {"kind": "eq_heat"})
    case(t, "an equation, solver named", prep(block, analysis, member("makeSolverElmer")), {"kind": "eq_flow", "solver": "SolverElmer"})
    case(t, "an equation, no Elmer", prep(block, analysis, member("makeSolverZ88")), {"kind": "eq_heat"})
    case(t, "a nonlinear material", prep(block, analysis, member("makeMaterialFluid"), member("makeMaterialSolid")), {"kind": "material_nonlinear"})
    case(t, "a nonlinear material, only a fluid", prep(block, analysis, member("makeMaterialFluid")), {"kind": "material_nonlinear"})
    case(t, "a nonlinear material, named", prep(block, analysis, member("makeMaterialFluid")), {"kind": "material_nonlinear", "material": "Material"})
    case(t, "refs on what takes none", prep(block, analysis), {"kind": "solver_z88", "refs": ["Block.Face1"]})
    case(t, "a property it has not", prep(block, analysis), {"kind": "displacement", "props": {"Speed": 3}})
    case(t, "a bare number for a quantity", prep(block, analysis), {"kind": "displacement", "props": {"xDisplacement": 2}})
    case(t, "zero for a quantity", prep(block, analysis), {"kind": "displacement", "props": {"xDisplacement": 0}})
    case(t, "the wrong unit", prep(block, analysis), {"kind": "displacement", "props": {"xDisplacement": "2 N"}})
    case(t, "text with no unit", prep(block, analysis), {"kind": "displacement", "props": {"xDisplacement": "5"}})
    case(t, "text that is no quantity", prep(block, analysis), {"kind": "displacement", "props": {"xDisplacement": "a lot"}})
    case(t, "an enumeration's other word", prep(block, analysis, refuses=("Mode",)), {"kind": "displacement", "props": {"Mode": "Sideways"}})
    case(t, "crash: a maker that fails", prep(block, analysis, fail=("makeConstraintTie",)), {"kind": "tie"})
    case(t, "no document", prep(lambda s: setattr(s, "doc", None)), {"kind": "tie"})
    # ---- fem_mesh ----
    t = "fem_mesh"

    def fem_mesh_obj(groups=()):
        def make(s):
            m = F.makeMeshGmsh(s.doc, "Mesh")
            m.__dict__["FemMesh"] = fc.FemMesh(10, 1, groups)
        return make

    def result(s):
        m = s.doc.getObject("Mesh") or F.makeMeshGmsh(s.doc, "Mesh")
        m.__dict__["FemMesh"] = fc.FemMesh(10, 1)
        fc.fem_object(s.doc, "Fem::FemResultObjectPython", "CCX_Results", vonMises=[float(10 * i) for i in range(1, 11)], NodeStressXX=[float(i) for i in range(1, 11)], Peeq=[],
                      NodeNumbers=list(range(1, 11)), Mesh=m, Time=1.0)

    case(t, "netgen", prep(block), {"action": "netgen", "body": "Block"})
    case(t, "netgen into the analysis there is", prep(block, analysis), {"action": "netgen", "body": "Block", "props": {"ElementOrder": "2nd"}})
    case(t, "netgen, two analyses", prep(block, analysis, analysis), {"action": "netgen", "body": "Block"})
    case(t, "netgen, an analysis named", prep(block, analysis, analysis), {"action": "netgen", "body": "Block", "analysis": "Analysis001"})
    case(t, "netgen, an analysis named, none here", prep(block), {"action": "netgen", "body": "Block", "analysis": "Analysis"})
    case(t, "netgen fails", prep(block, fail=("Netgen",)), {"action": "netgen", "body": "Block"})
    case(t, "netgen says why", prep(block, nodes_made=0, mesher_said="Meshing\nError: surface 2\n\nError: no mesh\n"), {"action": "netgen", "body": "Block"})
    case(t, "netgen gives nothing back", prep(block, nodes_made=0), {"action": "netgen", "body": "Block"})
    case(t, "netgen is not here", prep(block, missing=("femmesh",)), {"action": "netgen", "body": "Block"})
    case(t, "netgen, a recompute that fails", prep(block, fail=("recompute",)), {"action": "netgen", "body": "Block"})
    case(t, "netgen, no body", prep(block), {"action": "netgen"})
    case(t, "netgen, a property it has not", prep(block), {"action": "netgen", "body": "Block", "props": {"Fineness": "Fine"}})
    case(t, "to_mesh", prep(fem_mesh_obj()), {"action": "to_mesh", "mesh": "Mesh"})
    case(t, "to_mesh, deformed, named", prep(result), {"action": "to_mesh", "mesh": "Mesh", "result": "CCX_Results", "name": "Skin"})
    case(t, "to_mesh, a result not here", prep(fem_mesh_obj()), {"action": "to_mesh", "mesh": "Mesh", "result": "Gone"})
    case(t, "crash: to_mesh without FreeCAD's converter", prep(fem_mesh_obj(), missing=("femmesh",)), {"action": "to_mesh", "mesh": "Mesh"})
    case(t, "clear_groups", prep(fem_mesh_obj((3, 7))), {"action": "clear_groups", "mesh": "Mesh"})
    case(t, "clear_groups, none", prep(fem_mesh_obj()), {"action": "clear_groups", "mesh": "Mesh"})
    case(t, "a mesh not here", prep(block), {"action": "to_mesh", "mesh": "Gone"})
    case(t, "no mesh named", prep(block), {"action": "clear_groups"})
    case(t, "not a FEM mesh", prep(block), {"action": "clear_groups", "mesh": "Block"})
    case(t, "an action unknown", prep(fem_mesh_obj()), {"action": "refine", "mesh": "Mesh"})
    case(t, "no action", prep(fem_mesh_obj()), {"mesh": "Mesh"})
    case(t, "no FEM", prep(block, missing=("ObjectsFem",)), {"action": "netgen", "body": "Block"})
    # ---- fem_linearize ----
    t = "fem_linearize"

    def pipeline(s):
        fc.fem_object(s.doc, "Fem::FemPostPipeline", "Pipeline")

    wall = {i: (0.0, 0.0, float(i)) for i in range(1, 11)}
    case(t, "von Mises across a wall", prep(result, nodes=wall), {"result": "CCX_Results", "from": [0, 0, 1], "to": [0, 0, 10]})
    case(t, "a component, 7 points", prep(result, nodes=wall), {"result": "CCX_Results", "from": [0, 0, 1], "to": [0, 0, 10], "points": 7, "field": "NodeStressXX"})
    case(t, "a field it has not", prep(result), {"result": "CCX_Results", "from": [0, 0, 1], "to": [0, 0, 10], "field": "Shear"})
    case(t, "a field that is no list", prep(result), {"result": "CCX_Results", "from": [0, 0, 1], "to": [0, 0, 10], "field": "Time"})
    case(t, "a field with no values", prep(result), {"result": "CCX_Results", "from": [0, 0, 1], "to": [0, 0, 10], "field": "Peeq"})
    case(t, "leaves the part", prep(result), {"result": "CCX_Results", "from": [100, 0, 1], "to": [100, 0, 2]})
    case(t, "a pipeline", prep(pipeline), {"result": "Pipeline", "from": [0, 0, 0], "to": [0, 0, 4]})
    case(t, "a pipeline, a field named", prep(pipeline, line_values=[5.0, 6.0, 9.0]), {"result": "Pipeline", "from": "+x", "to": [0, 3], "field": "Major Principal Stress", "points": 5})
    case(t, "a pipeline with nothing along the line", prep(pipeline, line_values=[]), {"result": "Pipeline", "from": [0, 0, 0], "to": [0, 0, 4]})
    case(t, "from and to the same", prep(result), {"result": "CCX_Results", "from": [0, 0, 1], "to": [0, 0, 1]})
    case(t, "too few points", prep(result), {"result": "CCX_Results", "from": [0, 0, 1], "to": [0, 0, 10], "points": 4})
    case(t, "no from", prep(result), {"result": "CCX_Results", "to": [0, 0, 10]})
    case(t, "to not a point", prep(result), {"result": "CCX_Results", "from": [0, 0, 1], "to": "up"})
    case(t, "no result named", prep(result), {"from": [0, 0, 1], "to": [0, 0, 10]})
    case(t, "not a result", prep(block), {"result": "Block", "from": [0, 0, 1], "to": [0, 0, 10]})
    # ---- the strength study: fea_setup, fea_hold, fea_load, fea_refine, fea_clear ----
    from agentlink import geometry as geo

    def twin(s):
        fc.body("Twin", fc.solid("twin", (0, 0, 0), (10, 10, 10), solids=2))

    def study(body="Block", material="pla", mesh=2.0, holds=None, loads=None, **more):
        def write(s):
            store.write(s.doc, "fea", {"body": body, "material": material, "mesh": mesh, "holds": [{"faces": {"faces": ["Face1"]}, "kind": "fixed"}] if holds is None else holds,
                                       "loads": [{"kind": "force", "faces": {"faces": ["Face2"]}, "force": [0.0, 0.0, -100.0]}] if loads is None else loads, **more})
        return write

    def body_material(**mats):
        return lambda s: store.write(s.doc, "materials", mats)

    FIELD = {"points": [[0.0, 0.0, float(i)] for i in range(6)], "vonMises": [1.0, 2.0, 4.0, 8.0, 16.0, 32.0], "displacement": [[0.0, 0.0, 0.01 * i] for i in range(6)],
             "stress": [[float(i)] * 6 for i in range(6)], "elements": [[0, 1, 2, 3]]}

    def solved(field=FIELD, body="Block", **more):
        def keep(s):
            o = next((x for x in s.doc.Objects if x.Label == body), None)
            st = store.read(s.doc, "fea", None)
            s._agentlink_fea = {"body": body, "stats": geo.stats(o.Shape) if o is not None else {}, "study": st, "result": {"body": body, "vonMisesMax": {"MPa": 32.0}, "safety": 1.56, "mesh": {"size": 2.0}}, **more}
            if field is not None:
                s._agentlink_fea["field"] = field
        return keep

    def grown(s):
        s.doc.getObject("Body").__dict__["Shape"] = fc.solid("block", (0, 0, 0), (10, 10, 20))

    def gone(s):
        s.doc.removeObject("Body")

    t = "fea_setup"
    case(t, "the one body", prep(block), {})
    case(t, "a mesh size and a filament", prep(block), {"body": "Block", "mesh": 1.5, "material": "PETG"})
    case(t, "a library card by name", prep(block), {"material": "steel-s235"})
    case(t, "the body's own material", prep(block, body_material(Block="uuid-alu")), {})
    case(t, "a coarse mesh", prep(block), {"mesh": 6})
    case(t, "mesh 0", prep(block), {"mesh": 0})
    case(t, "a mesh too fine to solve", prep(block), {"mesh": 0.1})
    case(t, "a material not here", prep(block), {"material": "unobtainium"})
    case(t, "a material with no stiffness", prep(block), {"material": "uuid-foam"})
    case(t, "again: holds and loads kept", prep(block, study()), {"mesh": 1})
    case(t, "again: a hold that fits no face now", prep(block, study(holds=[{"faces": {"faces": ["Face9"]}, "kind": "fixed"}])), {})
    case(t, "again, reset", prep(block, study()), {"reset": True})
    case(t, "another body before", prep(block, pin, study(body="Pin")), {"body": "Block"})
    case(t, "an empty study before", prep(block, study(holds=[], loads=[])), {})
    case(t, "one solid of two", prep(twin), {"solid": 2})
    case(t, "one solid of two, its material the body's", prep(twin, body_material(Twin="petg")), {"solid": 1, "mesh": 2})
    case(t, "a solid it has not", prep(twin), {"solid": 3})
    case(t, "a solid of a one-solid body", prep(block), {"solid": 2})
    case(t, "solid 1 of a one-solid body", prep(block), {"solid": 1})
    case(t, "solid as text", prep(twin), {"solid": "1"})
    case(t, "solid true", prep(twin), {"solid": True})
    case(t, "two solids, none chosen", prep(twin), {})
    case(t, "no body", prep(), {})
    t = "fea_hold"
    case(t, "fixed, by faces", prep(block, study(holds=[])), {"faces": {"faces": ["Face1", "Face3"]}})
    case(t, "added to one there is", prep(block, study()), {"faces": "Face4"})
    case(t, "the same again", prep(block, study()), {"faces": {"faces": ["Face1"]}})
    case(t, "the same again, replacing", prep(block, study()), {"faces": {"faces": ["Face1"]}, "replace": True})
    case(t, "clear", prep(block, study()), {"clear": True})
    case(t, "slide", prep(block, study()), {"faces": "Face2", "kind": "slide"})
    case(t, "slide, faces that face each other", prep(block, study()), {"faces": ["Face1", "Face2"], "kind": "slide"})
    case(t, "slide, askew", prep(block, study(), normals={"Face3": [1, 1, 0]}), {"faces": "Face3", "kind": "slide"})
    case(t, "pin", prep(block, study()), {"faces": "Face3", "kind": "pin", "dofs": ["z", "x", "z"]})
    case(t, "pin, no dofs", prep(block, study()), {"faces": "Face3", "kind": "pin"})
    case(t, "pin, a dof unknown", prep(block, study()), {"faces": "Face3", "kind": "pin", "dofs": ["x", "w"]})
    case(t, "move", prep(block, study()), {"faces": "Face3", "kind": "move", "move": [0.5, None, -1]})
    case(t, "move, every direction free", prep(block, study()), {"faces": "Face3", "kind": "move", "move": [None, None, None]})
    case(t, "move, not three", prep(block, study()), {"faces": "Face3", "kind": "move", "move": [1, 2]})
    case(t, "a kind unknown", prep(block, study()), {"faces": "Face3", "kind": "glued"})
    case(t, "a face it has not", prep(block, study()), {"faces": "Face9"})
    case(t, "no faces", prep(block, study()), {})
    case(t, "no study", prep(block), {"faces": "Face1"})
    case(t, "one solid studied alone", prep(twin, study(body="Twin solid 2 (study)", of={"body": "Twin", "solid": 2}, holds=[])), {"faces": "Face1"})
    case(t, "the study's body gone", prep(block, study(body="Other")), {"faces": "Face1"})
    t = "fea_load"
    case(t, "a force", prep(block, study(loads=[])), {"faces": "Face2", "force": [0, 0, -50]})
    case(t, "a force pushing in", prep(block, study()), {"faces": ["Face1", "Face3"], "force": 80})
    case(t, "a force pushing in, no one direction", prep(block, study()), {"faces": ["Face1", "Face2"], "force": 80})
    case(t, "a force of two numbers", prep(block, study()), {"faces": "Face2", "force": [1, 2]})
    case(t, "a force of nothing", prep(block, study()), {"faces": "Face2", "force": [0, 0, 0]})
    case(t, "the same force again", prep(block, study()), {"faces": {"faces": ["Face2"]}, "force": [0, 0, -100]})
    case(t, "the same force again, replacing", prep(block, study()), {"faces": {"faces": ["Face2"]}, "force": [0, 0, -100], "replace": True})
    case(t, "a pressure", prep(block, study()), {"faces": "Face2", "pressure": 0.2})
    case(t, "a pressure in words", prep(block, study()), {"faces": "Face2", "pressure": "high"})
    case(t, "a pressure on a face it has not", prep(block, study()), {"faces": "Face9", "pressure": 1})
    case(t, "gravity", prep(block, study()), {"gravity": True})
    case(t, "gravity, 2 g", prep(block, study()), {"gravity": 2})
    case(t, "gravity sideways", prep(block, study()), {"gravity": [1, 0, 0]})
    case(t, "gravity false", prep(block, study()), {"gravity": False})
    case(t, "gravity of nothing", prep(block, study()), {"gravity": 0})
    case(t, "warmer, the material's expansion by its name", prep(block, study()), {"temperature": 40})
    case(t, "cooler, alpha given", prep(block, study(material="custom:acme")), {"temperature": -20, "alpha": 2e-5})
    case(t, "warmer, no expansion known", prep(block, study(material="custom:acme")), {"temperature": 40})
    case(t, "temperature true", prep(block, study()), {"temperature": True})
    case(t, "spin", prep(block, study()), {"spin": {"rpm": 3000, "axis": [0, 0, 2], "at": [5, 5, 0]}})
    case(t, "spin, the least", prep(block, study()), {"spin": {"rpm": 60}})
    case(t, "spin, no rpm", prep(block, study()), {"spin": {"axis": [0, 0, 1]}})
    case(t, "spin, no axis", prep(block, study()), {"spin": {"rpm": 60, "axis": [0, 0, 0]}})
    case(t, "two kinds", prep(block, study()), {"faces": "Face2", "force": [1, 0, 0], "pressure": 1})
    case(t, "no kind", prep(block, study()), {"faces": "Face2"})
    case(t, "clear", prep(block, study()), {"clear": True})
    case(t, "no study", prep(block), {"gravity": True})
    t = "fea_refine"
    case(t, "near a face", prep(block, study()), {"faces": "Face3", "size": 0.5})
    case(t, "a second region", prep(block, study(refine=[{"faces": "Face3", "size": 0.5}])), {"faces": {"faces": ["Face4"]}, "size": 1})
    case(t, "clear", prep(block, study(refine=[{"faces": "Face3", "size": 0.5}])), {"clear": True})
    case(t, "size 0", prep(block, study()), {"faces": "Face3", "size": 0})
    case(t, "size in words", prep(block, study()), {"faces": "Face3", "size": "fine"})
    case(t, "not finer", prep(block, study()), {"faces": "Face3", "size": 2})
    case(t, "a face it has not", prep(block, study()), {"faces": "Face9", "size": 1})
    case(t, "no study", prep(block), {"faces": "Face3", "size": 1})
    t = "fea_clear"
    case(t, "a study and its results", prep(block, study(), solved()), {})
    case(t, "nothing to drop", prep(block), {})
    # ---- the last solve: fea_results, fea_export ----
    t = "fea_results"
    case(t, "fresh", prep(block, study(), solved()), {})
    case(t, "the body changed", prep(block, study(), solved(), grown), {})
    case(t, "the body gone", prep(block, study(), solved(), gone), {})
    case(t, "the study changed", prep(block, study(), solved(), study(mesh=1.0)), {})
    case(t, "the body and the study changed", prep(block, study(), solved(), grown, study(mesh=1.0)), {})
    case(t, "none", prep(block, study()), {})
    t = "fea_export"
    case(t, "both", prep(block, study(), solved()), {})
    case(t, "the csv, named", prep(block, study(), solved()), {"formats": ["csv"], "name": "bracket run 2"})
    case(t, "a solve that kept no elements", prep(block, study(), solved({**FIELD, "elements": []})), {})
    case(t, "the csv of a solve that kept no elements", prep(block, study(), solved({**FIELD, "elements": []})), {"formats": ["csv"]})
    case(t, "no solve", prep(block, study()), {})
    case(t, "a solve with no field", prep(block, study(), solved(None)), {})
    t = "fea_probe"
    case(t, "at points", prep(block, study(), solved()), {"points": [[0, 0, 2], [0, 0.5, 3.5]]})
    case(t, "along a line", prep(block, study(), solved()), {"line": {"from": [0, 0, 0], "to": [0, 0, 5], "samples": 6}})
    case(t, "a line that leaves the part", prep(block, study(), solved()), {"line": {"from": [0, 0, 0], "to": [0, 0, 50], "samples": 3}})
    case(t, "one sample", prep(block, study(), solved()), {"line": {"from": [0, 0, 0], "to": [0, 0, 5], "samples": 1}})
    case(t, "over faces", prep(block, study(), solved()), {"faces": ["Face1", "Face2"]})
    case(t, "points, a line and faces, stale", prep(block, study(), solved(stale=True)), {"points": [[0, 0, 2]], "line": {"from": [0, 0, 0], "to": [0, 0, 5]}, "faces": "Face1"})
    case(t, "faces with no node on them", prep(block, study(), solved({**FIELD, "points": [[50.0, 50.0, float(i)] for i in range(6)]})), {"faces": "Face1"})
    case(t, "faces, the body gone", prep(block, study(), solved(), gone), {"faces": "Face1"})
    case(t, "faces it has not", prep(block, study(), solved()), {"faces": "Face9"})
    case(t, "nothing asked", prep(block, study(), solved()), {})
    case(t, "no solve", prep(block, study()), {"points": [[0, 0, 0]]})
    case(t, "crash: a line from nowhere", prep(block, study(), solved()), {"line": {"from": "here", "to": [0, 0, 5]}})
    t = "fea_chart"
    case(t, "a histogram", prep(block, study(), solved()), {})
    case(t, "a histogram of displacement, 4 bins, named", prep(block, study(), solved()), {"field": "displacement", "bins": 4, "name": "run 2: sag", "title": "Sag"})
    case(t, "one bin", prep(block, study(), solved()), {"bins": 1})
    case(t, "a line", prep(block, study(), solved()), {"kind": "line", "line": {"from": [0, 0, 0], "to": [0, 0, 5], "samples": 6}})
    case(t, "a line that leaves the part", prep(block, study(), solved()), {"kind": "line", "field": "displacement", "line": {"from": [0, 0, 0], "to": [0, 0, 50], "samples": 3}})
    case(t, "a line, none given", prep(block, study(), solved()), {"kind": "line", "points": [[0, 0, 1]]})
    case(t, "a line of 600 samples", prep(block, study(), solved()), {"kind": "line", "line": {"from": [0, 0, 0], "to": [0, 0, 5], "samples": 600}})
    case(t, "a table at points", prep(block, study(), solved()), {"kind": "table", "points": [[0, 0, 1], [0, 0, 4]]})
    case(t, "a table along a line, plotted too", prep(block, study(), solved()), {"kind": "table", "line": {"from": [0, 0, 0], "to": [0, 0, 5], "samples": 30}, "points": [[0, 0, 1]]})
    case(t, "a table of nothing", prep(block, study(), solved()), {"kind": "table"})
    case(t, "a kind unknown", prep(block, study(), solved()), {"kind": "pie"})
    case(t, "a field unknown", prep(block, study(), solved()), {"field": "strain"})
    case(t, "no solve", prep(block, study()), {})
    # ---- the solver's other steps: fea_modes, fea_buckle, fea_heat ----
    stiff = {**fc.LIBRARY, "uuid-stiff": {"Name": "Stiff", "Directory": "Standard/Odd", "LibraryName": "System", "Tags": [], "Description": "", "YoungsModulus": 1000.0}}
    pinned = [{"faces": "Face3", "kind": "pin", "dofs": [1, 3], "values": [0.0, 0.0]}]
    t = "fea_modes"
    case(t, "held", prep(block, study()), {})
    case(t, "free, two modes", prep(block, study(holds=[])), {"count": 2})
    case(t, "pinned and fixed, a custom material", prep(block, custom_kept, study(material="custom:acme", holds=pinned + [{"faces": "Face1", "kind": "fixed"}]), freqs=[55.123, 80.0]), {"count": 4, "timeout": 60})
    case(t, "pinned only, a refined region", prep(block, study(holds=pinned, refine=[{"faces": "Face2", "size": 0.5}]), shapes=1), {})
    case(t, "count 0", prep(block, study()), {"count": 0})
    case(t, "count 31", prep(block, study()), {"count": 31})
    case(t, "a material with no density", prep(block, study(material="uuid-stiff"), library=stiff), {})
    case(t, "a material gone", prep(block, study(material="custom:gone")), {})
    case(t, "no frequencies", prep(block, study(), freqs=[]), {})
    case(t, "no CalculiX", prep(block, study(), no_binary=("ccx",)), {})
    case(t, "neither program", prep(block, study(), no_binary=("ccx", "gmsh")), {})
    case(t, "no FEM module", prep(block, study(), missing=("Fem",)), {})
    case(t, "Gmsh fails", prep(block, study(), gmsh_fails=True), {})
    case(t, "Gmsh slow", prep(block, study(), slow=("gmsh",)), {"timeout": 5})
    case(t, "no volume elements", prep(block, study(), volumes_made=0), {})
    case(t, "no tetrahedra", prep(block, study(), no_tets=True), {})
    case(t, "CalculiX slow", prep(block, study(), slow=("ccx",)), {})
    case(t, "CalculiX refuses", prep(block, study(), ccx_out="reading the input\n *ERROR in frequency: singular matrix\n stopped\n"), {})
    case(t, "CalculiX writes nothing", prep(block, study(), no_frd=True, ccx_out="started\nnonpositive jacobian in element 3\n"), {})
    case(t, "no study", prep(block), {})
    t = "fea_buckle"
    every = [{"kind": "force", "faces": "Face2", "force": [0.0, 0.0, -100.0]}, {"kind": "pressure", "faces": ["Face3", "Face4"], "pressure": 0.5}, {"kind": "gravity", "gravity": [0.0, 0.0, -1.0]},
             {"kind": "gravity", "gravity": [1.0, 0.0, 0.0]}, {"kind": "temperature", "delta": 30.0}, {"kind": "spin", "spin": {"rpm": 100.0, "axis": [0.0, 0.0, 1.0], "at": [0.0, 0.0, 0.0]}}]
    case(t, "a column", prep(block, study()), {})
    case(t, "every kind of load, a pinned hold", prep(block, study(loads=every, holds=pinned + [{"faces": "Face1", "kind": "fixed"}])), {"count": 2, "timeout": 100})
    case(t, "buckles as loaded", prep(block, study(), factors=[0.5, 2.0]), {})
    case(t, "little margin", prep(block, study(), factors=[2.25]), {})
    case(t, "loads reversed", prep(block, study(), factors=[-1.5, 3.0], shapes=1), {})
    case(t, "no holds", prep(block, study(holds=[])), {})
    case(t, "no loads", prep(block, study(loads=[])), {})
    case(t, "a material with no stiffness", prep(block, study(material="uuid-foam")), {})
    case(t, "count 11", prep(block, study()), {"count": 11})
    case(t, "no factors", prep(block, study(), factors=[]), {})
    case(t, "too few nodes held", prep(block, study(), face_nodes={"Face1": [1, 2]}), {})
    case(t, "a load on no element", prep(block, study(), face_elems={"Face2": []}), {})
    case(t, "CalculiX refuses", prep(block, study(), ccx_out=" *ERROR: zero pivot\n"), {})
    case(t, "no study", prep(block), {})
    t = "fea_heat"
    hot_face = [{"faces": "Face1", "celsius": 90}]
    case(t, "a face held hot, still air", prep(block, study()), {"temperatures": hot_face})
    case(t, "heat in, a face held, no air", prep(block, study()), {"temperatures": [{"faces": "Face1", "celsius": 20}], "heat": [{"faces": ["Face2", "Face3"], "watts": 5}], "air": False})
    case(t, "heat in, air on chosen faces, a fan", prep(block, study(), hottest=52.0), {"heat": [{"faces": "Face2", "watts": 2}], "air": {"h": 40, "celsius": 30, "faces": ["Face5", "Face6"]}, "timeout": 30})
    case(t, "air true, cool enough", prep(block, study(), hottest=40.0), {"temperatures": hot_face, "air": True})
    case(t, "a material with no softening point", prep(block, study(material="uuid-steel")), {"temperatures": hot_face})
    case(t, "conductivity given for a card without", prep(block, custom_kept, study(material="custom:acme")), {"temperatures": hot_face, "conductivity": 0.25})
    case(t, "no conductivity", prep(block, custom_kept, study(material="custom:acme")), {"temperatures": hot_face})
    case(t, "no conductivity, the material gone", prep(block, study(material="custom:gone")), {"temperatures": hot_face})
    case(t, "nothing drives it", prep(block, study()), {})
    case(t, "heat in, nothing takes it away", prep(block, study()), {"heat": [{"faces": "Face2", "watts": 2}], "air": False})
    case(t, "a temperature with no figure", prep(block, study()), {"temperatures": [{"faces": "Face1", "celsius": 20}, {"faces": "Face2"}]})
    case(t, "a temperature on no face", prep(block, study()), {"temperatures": [{"celsius": 20}]})
    case(t, "heat with no figure", prep(block, study()), {"heat": ["Face2"]})
    case(t, "heat on a face it has not", prep(block, study()), {"heat": [{"faces": "Face9", "watts": 1}]})
    case(t, "heat on no element", prep(block, study(), face_elems={"Face2": []}), {"heat": [{"faces": "Face2", "watts": 1}]})
    case(t, "no temperatures read", prep(block, study(), no_results=True), {"temperatures": hot_face})
    case(t, "Gmsh fails", prep(block, study(), gmsh_fails=True), {"temperatures": hot_face})
    case(t, "no study", prep(block), {"temperatures": hot_face})
    # ---- fea_shell ----
    t = "fea_shell"
    S6 = "*Node, NSET=Nall\n1, 0, 0, 0\n*Element, TYPE=S6, ELSET=Efaces\n1, 1, 2, 3, 4, 5, 6\n"

    def plate(s):
        fc.body("Plate", fc.Shape("plate", "Face", (0, 0, 0), (100, 50, 0), area=5000.0, faces=1, edges=4, wires=1, solids=0, shells=0))

    def folded(s):
        fc.body("Folded", fc.Shape("folded", "Shell", (0, 0, 0), (100, 50, 20), area=7000.0, faces=3, edges=10, solids=0))

    def outline(s):
        fc.body("Outline", fc.wire("outline", [(0, 0, 0), (10, 0, 0), (10, 10, 0)]))

    ok = {"object": "Plate", "thickness": 2, "holds": [{}], "pressure": 0.01}
    case(t, "a plate under pressure, simply supported", prep(plate, mesh_text=S6), ok)
    case(t, "clamped, its own weight too, a material and a mesh", prep(plate, mesh_text=S6), {**ok, "holds": [{"edges": "boundary", "kind": "fixed"}], "gravity": True, "material": "uuid-steel", "mesh": 5, "timeout": 60})
    case(t, "two of three faces, held near points", prep(folded, mesh_text=S6), {"object": "Folded", "faces": ["Folded.Face1", "Face3"], "thickness": 1.5, "gravity": True,
                                                                              "holds": [{"edges": [{"near": [0, 0, 0]}, {"near": [100, 50, 0]}]}, {"kind": "fixed"}]})
    case(t, "a deflection over half the thickness", prep(plate, mesh_text=S6, moves=200.0), ok)
    case(t, "a material with no yield", prep(plate, body_material(Plate="uuid-pla"), mesh_text=S6), ok)
    case(t, "no programs", prep(plate, no_binary=("gmsh",)), ok)
    case(t, "crash: no FEM module", prep(plate, missing=("Fem",)), ok)
    case(t, "no object", prep(plate), {"thickness": 2})
    case(t, "an object with no faces", prep(outline), {**ok, "object": "Outline"})
    case(t, "a face it has not", prep(plate), {**ok, "faces": ["Face4"]})
    case(t, "no thickness", prep(plate), {"object": "Plate", "holds": [{}], "pressure": 1})
    case(t, "a material with no stiffness", prep(plate), {**ok, "material": "uuid-foam"})
    case(t, "a material not here", prep(plate), {**ok, "material": "unobtainium"})
    case(t, "Gmsh fails", prep(plate, gmsh_fails=True), ok)
    case(t, "crash: Gmsh slow", prep(plate, slow=("gmsh",)), ok)
    case(t, "a mesh with no elements named", prep(plate, mesh_text="*Node\n1, 0, 0, 0\n"), ok)
    case(t, "a mesh of volumes", prep(plate), ok)
    case(t, "no holds", prep(plate, mesh_text=S6), {"object": "Plate", "thickness": 2, "pressure": 0.01})
    case(t, "a hold of a kind unknown", prep(plate, mesh_text=S6), {**ok, "holds": [{"kind": "glued"}]})
    case(t, "holds that catch two nodes", prep(plate, mesh_text=S6, edge_nodes={"Edge1": [1, 2], "Edge2": [2], "Edge3": [], "Edge4": [1]}), ok)
    case(t, "no load", prep(plate, mesh_text=S6), {"object": "Plate", "thickness": 2, "holds": [{}]})
    case(t, "CalculiX refuses", prep(plate, mesh_text=S6, ccx_out=" *ERROR in shell: zero pivot\n"), ok)
    case(t, "no displacements", prep(plate, mesh_text=S6, no_results=True), ok)
    # ---- fea_parts ----
    t = "fea_parts"

    def lid(s):
        fc.body("Lid", fc.solid("lid", (0, 0, 10), (10, 10, 12)))

    case(t, "two parts tied", prep(block, lid), {"bodies": ["Block", "Lid"]})
    case(t, "contact with friction, their materials, named", prep(block, lid, body_material(Lid="petg")), {"bodies": ["Block", "Lid"], "join": "contact", "friction": 0.2, "materials": {"Block": "Steel-S235"},
                                                                                                          "name": "Stack", "mesh": 1.5, "tolerance": 0.1})
    case(t, "apart, joined by nothing", prep(block, pin), {"bodies": ["Block", "Pin"], "join": "none"})
    case(t, "apart, to be tied", prep(block, pin), {"bodies": ["Block", "Pin"]})
    case(t, "three, two of them crossing", prep(block, lid, pin, overlap=4.0), {"bodies": ["Block", "Lid", "Pin"], "join": "none"})
    case(t, "crossing and nothing touching", prep(block, pin, overlap=4.0), {"bodies": ["Block", "Pin"]})
    case(t, "again over the study's body", prep(block, lid, lambda s: fc.body("FEA parts", fc.solid("old", (0, 0, 0), (1, 1, 1)), name="FeaParts")), {"bodies": ["Block", "Lid"]})
    case(t, "one body", prep(block), {"bodies": ["Block"]})
    case(t, "bodies not a list", prep(block), {"bodies": "Block"})
    case(t, "a join unknown", prep(block, lid), {"bodies": ["Block", "Lid"], "join": "weld"})
    case(t, "a material not here", prep(block, lid), {"bodies": ["Block", "Lid"], "materials": {"Lid": "unobtainium"}})
    case(t, "a material with no stiffness", prep(block, lid, body_material(Block="uuid-foam")), {"bodies": ["Block", "Lid"]})
    case(t, "a part of two solids", prep(block, twin), {"bodies": ["Block", "Twin"]})
    case(t, "a body not here", prep(block), {"bodies": ["Block", "Gone"]})
    # ---- fea_native ----
    t = "fea_native"
    case(t, "CalculiX, a fixed hold and a force", prep(block, study()), {})
    case(t, "every kind of hold and load, named", prep(block, study(holds=pinned + [{"faces": "Face1", "kind": "fixed"}], loads=every)), {"name": "Bracket study", "solver": "CalculiX"})
    case(t, "before FreeCAD 1.1", prep(block, study(loads=every), old_gravity=True, old_mesh_link=True), {})
    case(t, "a temperature this FEM does not take", prep(block, study(loads=every), fail=("makeConstraintTemperature",)), {})
    case(t, "a direction it will not take, an element order it will not take", prep(block, study(), refuses=("Direction", "ElementOrder")), {})
    case(t, "a material gone", prep(block, study(material="custom:gone")), {})
    case(t, "a material with every figure", prep(block, study(material="uuid-steel")), {})
    case(t, "no CalculiX solver object", prep(block, study(), missing=("ObjectsFem.makeSolverCalculiX",)), {})
    case(t, "Elmer, elasticity", prep(block, study(loads=every)), {"solver": "elmer"})
    case(t, "Elmer, heat and electrostatics", prep(block, study(), enums={"ConstraintType": ["Convection", "Flux"]}),
         {"solver": "elmer", "equations": ["Heat", "electrostatic"], "temperatures": [{"faces": "Face1", "celsius": 80}], "heat": [{"faces": ["Face2", "Face3"], "watts": 3}],
          "potentials": [{"faces": "Face4", "volts": 12}]})
    case(t, "Elmer, flow in water, heat", prep(block, study(), enums={"ConstraintType": ["DFlux"]}), {"solver": "elmer", "equations": ["flow", "heat"], "fluid": "Water", "heat": [{"faces": "Face2", "watts": 3}]})
    case(t, "Elmer, written", prep(block, study()), {"solver": "elmer", "write": True})
    case(t, "Elmer, written and run", prep(block, study()), {"solver": "elmer", "run": True, "timeout": 30})
    case(t, "Elmer, no ElmerGrid", prep(block, study(), no_binary=("ElmerGrid",)), {"solver": "elmer", "run": True})
    case(t, "Elmer, no ElmerSolver", prep(block, study(), no_binary=("ElmerSolver",)), {"solver": "elmer", "run": True})
    case(t, "Elmer, ElmerGrid refuses", prep(block, study(), grid_fails=True), {"solver": "elmer", "write": True})
    case(t, "Elmer stops", prep(block, study(), elmer_out="start\nERROR:: Solver: no convergence\n"), {"solver": "elmer", "run": True})
    case(t, "Elmer, the writer refuses", prep(block, study(), fail=("elmer writer",)), {"solver": "elmer", "write": True})
    case(t, "Elmer, no Gmsh", prep(block, study(), no_binary=("gmsh",)), {"solver": "elmer", "write": True})
    case(t, "Elmer, Gmsh says no", prep(block, study(), mesher_said="Error: no mesh"), {"solver": "elmer", "write": True})
    case(t, "Elmer, an equation unknown", prep(block, study()), {"solver": "elmer", "equations": ["heat", "plasma"]})
    case(t, "Elmer, an equation this FEM lacks", prep(block, study()), {"solver": "elmer", "equations": ["flux"]})
    case(t, "Elmer, a fluid unknown", prep(block, study()), {"solver": "elmer", "fluid": "oil"})
    case(t, "Elmer, temperatures without heat", prep(block, study()), {"solver": "elmer", "temperatures": [{"faces": "Face1", "celsius": 80}]})
    case(t, "Elmer, potentials without electrostatics", prep(block, study()), {"solver": "elmer", "equations": ["heat"], "potentials": [{"faces": "Face1", "volts": 5}]})
    case(t, "no Elmer solver object", prep(block, study(), missing=("ObjectsFem.makeSolverElmer",)), {"solver": "elmer"})
    case(t, "a solver unknown", prep(block, study()), {"solver": "ansys"})
    case(t, "equations for CalculiX", prep(block, study()), {"equations": ["heat"]})
    case(t, "no FEM", prep(block, study(), missing=("ObjectsFem",)), {})
    case(t, "no study", prep(block), {})
    # ---- fea_solve ----
    t = "fea_solve"
    F2 = fc.objects_fem

    def solved_before(s):
        an = F2.makeAnalysis(s.doc, "Analysis")
        an.__dict__["Label"] = "Block strength (fea_solve)"
        mesh = F2.makeMeshGmsh(s.doc, "Mesh")
        F2.makeMeshRegion(s.doc, mesh)
        res = fc.fem_object(s.doc, "Fem::FemResultObjectPython", "CCX_Results", kinds=("Fem::FemResultObject",), Mesh=fc.fem_object(s.doc, "Fem::FemMeshObject", "ResultMesh"))
        an.addObject(mesh)
        an.addObject(res)
        fc.body("Block force direction", fc.wire("line", [(0, 0, 0), (0, 0, 1)], closed=False), name="ForceDirection")

    def parts_study(join="tie"):
        def write(s):
            fc.body("FEA parts", fc.solid("parts", (0, 0, 0), (10, 10, 12), solids=2), name="FeaParts")
            study(body="FEA parts", parts=[{"body": "Block", "material": "pla"}, {"body": "Lid", "material": "uuid-steel"}], join=join, friction=0.2, tolerance=0.05)(s)
        return write

    two = {1: (1, 2, 3, 4, 5, 6, 7, 8, 9, 10), 2: (7, 8, 9, 10, 1, 2, 3, 4, 5, 6)}
    case(t, "FreeCAD's FEM: a fixed hold and a force", prep(block, study()), {})
    case(t, "FreeCAD's FEM: pressure and gravity, a longer wait", prep(block, study(loads=every[1:4])), {"timeout": 600})
    case(t, "FreeCAD's FEM: before 1.1", prep(block, study(loads=every[:3]), old_gravity=True, old_mesh_link=True), {})
    case(t, "FreeCAD's FEM: the analysis of the solve before replaced", prep(block, study(), solved_before), {})
    case(t, "FreeCAD's FEM: results that will not load, CalculiX warns", prep(block, study(), fail=("load_results",), ccx_out="*WARNING: small pivot\nJob finished\n"), {})
    case(t, "FreeCAD's FEM: no CalculiX", prep(block, study(), no_binary=("ccx",)), {})
    case(t, "FreeCAD's FEM: Gmsh makes no volumes", prep(block, study(), volumes_made=0, mesher_said="Info: meshing\nError: surface 4 self-intersects\n"), {})
    case(t, "its prerequisites fail: the own deck", prep(block, study(), prerequisites="No material object\n"), {})
    case(t, "its deck writer fails: the own deck", prep(block, study(), fail=("write_inp_file",)), {})
    case(t, "FEM's tools are not here: the own deck", prep(block, study(), missing=("femtools",)), {})
    case(t, "a pinned hold: the own deck", prep(block, study(holds=pinned + [{"faces": "Face1", "kind": "fixed"}])), {})
    case(t, "warmth and spin: the own deck", prep(block, study(loads=every)), {})
    case(t, "a refined region: the own deck", prep(block, study(refine=[{"faces": "Face2", "size": 0.5}, {"faces": ["Face3"], "size": 1}])), {})
    case(t, "nonlinear, it yields", prep(block, study(), plastic=0.0213), {"nonlinear": True})
    case(t, "nonlinear, elastic only", prep(block, study()), {"nonlinear": True, "elasticOnly": True})
    case(t, "parts tied", prep(parts_study(), elems=two, split_z=5.0, face_elems={"Face1": [(1, 1), (2, 1)], "Face2": [(2, 3)]}), {})
    case(t, "parts in contact, nonlinear", prep(parts_study("contact"), elems=two, split_z=5.0, face_elems={"Face1": [(1, 1), (2, 1)], "Face2": [(2, 3)]}), {"nonlinear": True})
    case(t, "parts with no touching faces in the mesh", prep(parts_study(), elems=two, split_z=5.0), {})
    case(t, "parts, one with no elements", prep(parts_study()), {})
    case(t, "past yield", prep(block, study(), peak=400.0), {})
    case(t, "no stress at all", prep(block, study(), peak=0.0), {})
    case(t, "a material with no yield, a coarse mesh", prep(block, study(material="uuid-pla", mesh=4.0)), {})
    case(t, "a custom material, the peak on a held face, a large displacement", prep(block, custom_kept, study(material="custom:acme"), face_nodes={"Face1": [8, 9, 10]}, moves=100.0), {})
    case(t, "two solids, both held", prep(twin, study(body="Twin")), {})
    case(t, "one solid studied alone", prep(twin, study(body="Twin solid 2 (study)", of={"body": "Twin", "solid": 2})), {})
    case(t, "two solids, one held by nothing", prep(twin, study(body="Twin"), apart=("Solid2",)), {})
    case(t, "three solids, two held by nothing", prep(lambda s: fc.body("Trio", fc.solid("trio", (0, 0, 0), (10, 10, 10), solids=3)), study(body="Trio"), apart=("Solid2", "Solid3")), {})
    case(t, "no results from either route", prep(block, study(), no_results=True, ccx_out="started\n*WARNING: singular matrix\n"), {})
    case(t, "no results, two solids, nothing said", prep(twin, study(body="Twin", holds=pinned), no_results=True, ccx_out=""), {})
    case(t, "the own deck: no programs", prep(block, study(holds=pinned), no_binary=("gmsh",)), {})
    case(t, "the own deck: CalculiX slow", prep(block, study(holds=pinned), slow=("ccx",)), {"timeout": 20})
    case(t, "the own deck: CalculiX refuses", prep(block, study(holds=pinned), ccx_out=" *ERROR in e_c3d: nonpositive jacobian\n"), {})
    case(t, "the own deck: nonlinear, it gives way", prep(block, study(holds=pinned), ccx_out=" *ERROR: increment size smaller than minimum\n best solution\n"), {"nonlinear": True})
    case(t, "the own deck: nothing written", prep(block, study(holds=pinned), no_frd=True, ccx_out="started\nstopped\n"), {})
    case(t, "nothing holds it", prep(block, study(holds=[])), {})
    case(t, "nothing loads it", prep(block, study(loads=[])), {})
    case(t, "a hold that fits no face now", prep(block, study(holds=[{"faces": "Face9", "kind": "fixed"}], loads=every[:1] + [{"kind": "pressure", "faces": {"z": 3}, "pressure": 1.0}]), picks=[]), {})
    case(t, "the material gone", prep(block, study(material="custom:gone")), {})
    case(t, "no study", prep(block), {})
    return out
