# SPDX-License-Identifier: LGPL-2.1-or-later
# The hub's findings of the test drive of 20 Nov 2026 and the README
# screenshot pass of 19 Nov, without FreeCAD (plain numpy, or the data tests'
# stand-in FreeCAD in a child process):
#   1  object_delete: a Body (or a group) that only holds an object is not a
#      user of it — an unused sketch, the tip feature;
#   2  asm_joint gap: mm across the joint, positive apart, whichever way
#      FreeCAD's offset runs; gap and offset not both;
#   3  asm_joint near: in document coordinates; nearLocal in the part's own
#      frame; at: where each element was picked;
#   4  view_render maps: the map's own reading has a time budget (blend_fit
#      thins before blending), the expected time and the log include it;
#   6  view_render draws meshes;
#   9  material_set takes measure_mass's short ids (steel …);
#   11 asm_bom: the mass of a part in a print setup is as printed, or marked
#      solid;
#   12 object_get filter "A|B"; object_set { property, value };
#   screenshot 1: subdivide by edge length (a long thin triangle becomes a
#      row of small ones, not ever thinner slivers).
import json
import math
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

import numpy as np

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)
sys.path.insert(0, ROOT)
sys.path.insert(0, TESTS)

from agentlink import render  # noqa: E402


def entries():
    with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
        return json.load(f)["entries"]


def child(standin, body):
    """body run in a Python of its own after the stand-in FreeCAD is in;
    what it prints last, as JSON."""
    code = textwrap.dedent(f'''
        import json, sys, tempfile
        sys.path[:0] = [{ROOT!r}, {TESTS!r}]
        import {standin}
        fc = {standin}.install()
    ''') + "\n".join(textwrap.dedent(part) for part in body.split("\n#BODY\n"))  # each part dedented on its own
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


CALL = '''
    from agentlink.protocol import ToolError
    def run(mod, s, name, args):
        t = next(t for t in mod.tools(s) if t.name == name)
        try:
            return ["ok", t.fn(json.loads(json.dumps(args)))]
        except ToolError as e:
            return ["refused", e.code, e.message]
#BODY
'''


# ---- screenshot pass 1: subdivide by edge length ----------------------------------------------

def _edges(V, F):
    T = np.asarray(V, float)[np.asarray(F)]
    return np.stack([np.linalg.norm(T[:, 1] - T[:, 0], axis=1), np.linalg.norm(T[:, 2] - T[:, 1], axis=1), np.linalg.norm(T[:, 0] - T[:, 2], axis=1)], 1)


def _area(V, F):
    T = np.asarray(V, float)[np.asarray(F)]
    return float(np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1).sum() / 2)


def _box(x, y, z):
    V = np.array([[0, 0, 0], [x, 0, 0], [x, y, 0], [0, y, 0], [0, 0, z], [x, 0, z], [x, y, z], [0, y, z]], float)
    F = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]])
    return V, F


class SubdivideByLength(unittest.TestCase):
    def test_a_long_thin_triangle_becomes_a_row_not_slivers(self):
        V = np.array([[0, 0, 0], [100, 0, 0], [0, 1, 0]], float)
        F = np.array([[0, 1, 2]])
        SV, SF = render.subdivide(V, F, 2.0, cap=100000)
        self.assertLessEqual(float(_edges(SV, SF).max()), 2.0 + 1e-9)
        # By length: a row of small triangles, not 4^7 slivers (16,384 by the old split).
        self.assertLess(len(SF), 1000)
        self.assertAlmostEqual(_area(SV, SF), 50.0, places=6)
        # The winding is kept: every small triangle faces the way the big one did.
        T = SV[SF]
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        self.assertTrue(bool((n[:, 2] > 0).all()))

    def test_the_cap_holds_and_the_longest_go_first(self):
        V, F = _box(80, 50, 2)
        SV, SF = render.subdivide(V, F, 0.5, cap=3000)
        self.assertLessEqual(len(SF), 3000)
        self.assertAlmostEqual(_area(SV, SF), _area(V, F), places=4)
        self.assertLess(float(_edges(SV, SF).max()), 0.5 * float(_edges(V, F).max()))

    def test_a_shelled_walls_long_side_triangles_are_split_evenly(self):
        # A thin slab's long side faces are two triangles 80 x 2 mm each: at the
        # wall map's default count no triangle may stay long beside them.
        V, F = _box(80, 50, 2)
        cap = 16000
        L = render.even_length(V, F, cap)
        SV, SF, vals = render.wall_map(V, F, reach=12, cap=cap)
        self.assertLessEqual(len(SF), cap)
        self.assertLessEqual(float(_edges(SV, SF).max()), 1.1 * L)
        # The wall reads its 2 mm on the big faces (not reach, not nan).
        fin = vals[np.isfinite(vals)]
        self.assertGreater(len(fin), 0.9 * len(vals))
        self.assertAlmostEqual(float(np.median(fin)), 2.0, places=2)


# ---- finding 4: a map's blend within its time --------------------------------------------------

class BlendInTime(unittest.TestCase):
    def setUp(self):
        V, F = _box(40, 30, 20)
        self.V, self.F = render.subdivide(V, F, render.even_length(V, F, 20000), cap=20000)
        rng = np.random.default_rng(1)
        self.S = rng.uniform([0, 0, 0], [40, 30, 20], (3000, 3))
        self.vals = self.S[:, 0] * 2.0

    def test_without_a_budget_it_is_smooth_values_on_every_point(self):
        V, F, vals, info = render.blend_fit(self.V, self.F, self.S, self.vals)
        self.assertIsNone(info)
        self.assertEqual(len(F), len(self.F))
        want = render.smooth_values(self.V, self.S, self.vals)
        self.assertTrue(np.allclose(vals, want, equal_nan=True))

    def test_over_its_budget_the_layer_is_thinned_before_the_blend(self):
        # A budget already spent: the timing of the probe cannot make it fit (other tests may stand in for the blend).
        V, F, vals, info = render.blend_fit(self.V, self.F, self.S, self.vals, budget=-1.0)
        self.assertIsNotNone(info)
        self.assertEqual(info["from"], len(self.F))
        self.assertLess(info["to"], len(self.F))
        self.assertEqual(len(F), info["to"])
        self.assertGreaterEqual(info["estimate"], 0.0)
        self.assertEqual(len(vals), len(V))
        self.assertTrue(bool(np.isfinite(vals).all()))

    def test_the_budget_is_what_view_render_leaves_the_map(self):
        import time

        class S:
            pass

        s = S()
        self.assertIsNone(render.map_budget(s))
        s.render_deadline = time.time() + 30
        self.assertTrue(25 < render.map_budget(s) <= 30)
        s.render_deadline = time.time() - 5
        self.assertEqual(render.map_budget(s), 2.0)  # past it: the floor, not nothing

    def test_view_render_gives_the_map_its_deadline_and_says_the_thinning(self):
        got = child("_datacore_standin", CALL + '''
            import numpy as np
            from agentlink import render
            from agentlink.families import view
            seen = {}
            def probe(s, a):
                seen["budget"] = render.map_budget(s)
                V = np.array([[0, 0, 0], [10, 0, 0], [0, 10, 0]], float)
                return {"layers": [{"name": "Part", "V": V, "F": np.array([[0, 1, 2]]), "values": np.array([1.0, 2.0, 3.0]), "creases": True}],
                        "unit": "MPa", "label": "PROBE", "blendThinned": {"from": 90000, "to": 4000, "estimate": 300.0, "budget": 38.0, "nodes": 120000}}
            render.register_map("probe", probe, "a test map")
            s = fc.Session(tempfile.mkdtemp())
            r = run(view, s, "view_render", {"map": "probe", "detail": 30000, "inline": False})
            print(json.dumps({"r": r, "budget": seen.get("budget"), "after": getattr(s, "render_deadline", "gone"), "work": list(s.heavy_work)}, default=str))
        ''')
        self.assertEqual(got["r"][0], "ok", got["r"])
        out = got["r"][1]
        self.assertTrue(0 < got["budget"] <= 40.0, got["budget"])
        self.assertIsNone(got["after"])  # taken off after the map
        self.assertIn("map", out["time"])
        cap = out["detailCapped"]
        self.assertEqual((cap["asked"], cap["used"]), (30000, 4000))
        self.assertIn("120,000 nodes", cap["why"])
        self.assertIn("thinned from 90,000 to 4,000 triangles before blending", cap["why"])

    def test_the_expected_time_and_the_log_count_the_map(self):
        src = open(os.path.join(ROOT, "agentlink", "families", "view.py"), encoding="utf-8").read()
        self.assertIn("expected = tuple(x + map_took for x in expected)", src)
        self.assertIn("s.heavy_work = (RENDER_KEY, work + int(map_took / max(rate, 1e-12)))", src)
        self.assertIn("render.blend_fit(V, F, SP, SV, budget=render.map_budget(s))", src)  # stress
        self.assertIn("render.blend_fit(V, F, P, T, budget=render.map_budget(s))", src)  # heat


# ---- finding 6: meshes drawn ------------------------------------------------------------------

class MeshesDrawn(unittest.TestCase):
    def test_a_mesh_is_a_layer(self):
        class P:
            def __init__(self, x, y, z):
                self.x, self.y, self.z = x, y, z

        class M:
            Topology = ([P(0, 0, 0), P(10, 0, 0), P(0, 10, 0), P(0, 0, 10)], [(0, 1, 2), (0, 1, 3)])

        class O:
            Label, TypeId, Mesh = "Textured", "Mesh::Feature", M()

            def isDerivedFrom(self, t):
                return t == "Mesh::Feature"

        self.assertTrue(render.is_mesh(O()))
        l = render.mesh_layer(O(), 0)
        self.assertEqual((l["V"].shape, l["F"].shape, l["name"]), ((4, 3), (2, 3), "Textured"))

    def test_view_render_draws_a_shown_mesh_and_a_named_one(self):
        got = child("_datacore_standin", CALL + '''
            from agentlink.families import view
            class P:
                def __init__(self, x, y, z):
                    self.x, self.y, self.z = x, y, z
            class M:
                Topology = ([P(0, 0, 0), P(10, 0, 0), P(0, 10, 0), P(0, 0, 10)], [(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)])
                CountFacets = 4
            def knob(s, **kw):
                o = s.doc.new("Mesh::Feature", "Knob", Mesh=M(), **kw)
                o.__dict__["Label"] = "Knob knurled"
                return o
            out = {}
            s = fc.Session(tempfile.mkdtemp())
            knob(s)
            out["shown"] = run(view, s, "view_render", {"inline": False})
            s = fc.Session(tempfile.mkdtemp())
            knob(s, Visibility=False)
            out["named"] = run(view, s, "view_render", {"objects": ["Knob knurled"], "inline": False})
            out["hidden"] = run(view, s, "view_render", {"inline": False})
            # An add-on that draws the same mesh as a layer of its own (a scan, edited): not drawn twice.
            import numpy as np
            from agentlink import render
            render.register_layer("scanlike", lambda s, a: [{"name": "scan", "V": np.array([[0, 0, 0], [10, 0, 0], [0, 10, 0], [0, 0, 10], [5, 5, 0]], float),
                                                             "F": np.array([[0, 1, 2], [0, 1, 3], [4, 1, 2]]), "color": (0.7, 0.7, 0.7), "mapped": True}], "a test layer")
            s = fc.Session(tempfile.mkdtemp())
            knob(s)
            out["twice"] = run(view, s, "view_render", {"inline": False})
            print(json.dumps(out, default=str))
        ''')
        for k in ("shown", "named"):
            self.assertEqual(got[k][0], "ok", got[k])
            self.assertEqual(got[k][1]["layers"], [{"layer": "Knob knurled", "triangles": 4, "mesh": True}], k)
            self.assertNotIn("notDrawn", got[k][1])
        # A hidden mesh is not drawn unless named.
        self.assertIn("empty", got["hidden"][1])
        self.assertEqual(got["twice"][1]["layers"], [{"layer": "scan", "triangles": 3}])


# ---- finding 1: a container is not a user ------------------------------------------------------

class DeleteInABody(unittest.TestCase):
    BODY = CALL + '''
        from agentlink.families import doc
        def housing(s):
            b = s.doc.new("PartDesign::Body", "Body", Group=[], Tip=None)
            b.__dict__["Label"] = "Base"
            pad = s.doc.new("PartDesign::Pad", "Pad")
            sk = s.doc.new("Sketcher::SketchObject", "Sketch")
            spare = s.doc.new("Sketcher::SketchObject", "Sketch001")
            for o in (sk, pad, spare):
                b.__dict__["Group"].append(o)
                o.InList.append(b)
            sk.InList.append(pad)  # the pad is built on the sketch
            b.__dict__["Tip"] = pad
            return b
#BODY
'''

    def test_an_unused_sketch_and_the_tip_go_without_force_a_used_one_does_not(self):
        got = child("_datacore_standin", self.BODY + '''
            out = {}
            s = fc.Session(tempfile.mkdtemp())
            b = housing(s)
            out["spare"] = run(doc, s, "object_delete", {"objects": ["Sketch001"]})
            out["group"] = [o.Name for o in b.Group]
            out["used"] = run(doc, s, "object_delete", {"objects": ["Sketch"]})
            out["tip"] = run(doc, s, "object_delete", {"objects": ["Pad"]})
            out["left"] = [o.Name for o in s.doc.Objects]
            print(json.dumps(out, default=str))
        ''')
        self.assertEqual(got["spare"][0], "ok", got["spare"])
        self.assertEqual(got["spare"][1]["deleted"], ["Sketch001"])
        self.assertEqual(got["group"], ["Sketch", "Pad"])  # taken out of the Body first
        # A real user is still named, and the Body is not.
        self.assertEqual(got["used"][:2], ["refused", "invalid_state"])
        self.assertTrue(got["used"][2].startswith("Sketch is used by Pad: name those in objects too"), got["used"])
        self.assertEqual(got["tip"][0], "ok", got["tip"])
        self.assertEqual(got["left"], ["Body", "Sketch"])

    def test_the_entry_skips_holders_and_lets_go_first(self):
        e = entries()["object_delete"]
        text = json.dumps(e["steps"])
        self.assertIn("not holds(p, o)", text)
        self.assertIn("=let_go(objs)", text)
        self.assertIn("A container that only holds the object is not a user", e["description"])


# ---- finding 12: object_get "A|B", object_set { property, value } ----------------------------

class GetAndSet(unittest.TestCase):
    BLOCK = CALL + '''
        from agentlink.families import doc
        def block(s):
            return fc.body("Block", fc.solid("block", (0, 0, 0), (10, 10, 10), volume=1000.0), ViewObject=fc.ns(Visibility=True),
                           Length=10.0, Width=5.0, Mode="Solid", types={"Length": "App::PropertyLength", "Width": "App::PropertyLength", "Mode": "App::PropertyEnumeration",
                                                                      "Placement": "App::PropertyPlacement", "Visibility": "App::PropertyBool", "Shape": "Part::PropertyPartShape"},
                           choices={"Mode": ["Solid", "Shell"]}, groups={"Length": "Box", "Width": "Box"})
#BODY
'''

    def test_a_filter_of_several_words(self):
        got = child("_datacore_standin", self.BLOCK + '''
            s = fc.Session(tempfile.mkdtemp())
            block(s)
            out = {k: run(doc, s, "object_get", {"object": "Block", "filter": f}) for k, f in
                   (("two", "Length|Mode"), ("spaced", " length | width "), ("one", "Mode"), ("none", "Nope|Gone"))}
            print(json.dumps(out, default=str))
        ''')
        self.assertEqual(sorted(got["two"][1]["properties"]), ["Length", "Mode"])
        self.assertEqual(sorted(got["spaced"][1]["properties"]), ["Length", "Width"])
        self.assertEqual(sorted(got["one"][1]["properties"]), ["Mode"])
        self.assertEqual(got["none"][:2], ["refused", "not_found"])

    def test_one_property_by_property_and_value(self):
        got = child("_datacore_standin", self.BLOCK + '''
            s = fc.Session(tempfile.mkdtemp())
            block(s)
            out = {"pv": run(doc, s, "object_set", {"object": "Block", "property": "Length", "value": 20}),
                   "both": run(doc, s, "object_set", {"object": "Block", "values": {"Length": 5}, "property": "Length", "value": 20}),
                   "no value": run(doc, s, "object_set", {"object": "Block", "property": "Length"}),
                   "no property": run(doc, s, "object_set", {"object": "Block", "value": 3}),
                   "neither": run(doc, s, "object_set", {"object": "Block"}),
                   "values": run(doc, s, "object_set", {"object": "Block", "values": {"Length": 12}})}
            print(json.dumps(out, default=str))
        ''')
        self.assertEqual(got["pv"][0], "ok", got["pv"])
        self.assertEqual(got["pv"][1]["set"]["Length"]["to"], 20.0)
        self.assertEqual(got["values"][0], "ok", got["values"])
        self.assertEqual(got["both"], ["refused", "invalid_input", "values or property with value, not both: values { Property: value, … } sets several, property and value set one."])
        self.assertEqual(got["no value"], ["refused", "invalid_input", "value: the new value of property (property and value go together; values { Property: value } is the other way)."])
        self.assertEqual(got["no property"], ["refused", "invalid_input", "property: the name of the property that value sets (property and value go together; values { Property: value } is the other way)."])
        self.assertEqual(got["neither"], ["refused", "invalid_input", "values: { Property: value, … } — object_get gives the names and types."])

    def test_the_schema_takes_both(self):
        sch = entries()["object_set"]["inputSchema"]
        self.assertEqual(sch["required"], ["object"])
        self.assertEqual(list(sch["properties"]), ["object", "values", "property", "value"])


# ---- findings 2, 3: asm_joint gap and near ----------------------------------------------------

class JointGap(unittest.TestCase):
    def test_gap_set_finds_the_offset_whichever_way_it_runs(self):
        got = child("_dataasm_standin", '''
            from agentlink.families import assembly as A
            V = fc.fc.Vector
            class J:
                def __init__(self):
                    self.Offset2 = fc.fc.Placement(V(0, 0, 0), fc.fc.Rotation())
            class Asm:
                def solve(self):
                    return 0
            class D:
                def recompute(self):
                    pass
            out = {}
            for sign in (1, -1):
                j = J()
                # the gap FreeCAD gives: 0.5 mm overlap at offset 0, each mm of offset moving it sign mm
                A.joint_gap = lambda ends, j=j, sign=sign: round(-0.5 + sign * j.Offset2.Base.z, 4)
                code, said, gap, off = A.gap_set(D(), Asm(), j, [None, None], 0.3)
                out[str(sign)] = [code, gap, off]
            # a gap the joint cannot reach (another joint holds the part): the nearest kept
            j = J()
            A.joint_gap = lambda ends, j=j: round(min(0.1, -0.5 + j.Offset2.Base.z), 4)
            out["held"] = list(A.gap_set(D(), Asm(), j, [None, None], 0.3))
            # no outward side on either element: nothing to set
            A.joint_gap = lambda ends: None
            out["none"] = list(A.gap_set(D(), Asm(), J(), [None, None], 0.3))
            print(json.dumps(out, default=str))
        ''')
        self.assertEqual(got["1"], [0, 0.3, 0.8])
        self.assertEqual(got["-1"], [0, 0.3, -0.8])
        self.assertEqual(got["held"][2], 0.1)
        self.assertEqual(got["none"][2:], [None, None])

    def test_asm_joint_answers_the_gap_and_where_it_picked(self):
        got = child("_dataasm_standin", CALL + '''
            from agentlink.families import assembly as A
            fc.fc.GuiUp = False
            fc.state["solves"] = 0
            fc.state.setdefault("flags", {})
            s = fc.Session(tempfile.mkdtemp())
            fc.a_part("Base", (0, 0, 0), (10, 10, 10), name="Base")
            fc.a_part("Lid", (0, 0, 10), (10, 10, 12), name="Lid")
            a = fc.an_object("Assembly::AssemblyObject", "Assembly", "Assembly")
            a.__dict__["Type"] = "Assembly"
            jg = fc.into(a, fc.an_object("Assembly::JointGroup", "Joints"))
            for p in ("Base", "Lid"):
                fc.into(a, fc.doc().getObject(p))
            g = fc.into(jg, fc.an_object("App::FeaturePython", "GroundedJoint"))
            g.__dict__["ObjectToGround"] = fc.doc().getObject("Base")
            J = {"kind": "fixed", "a": {"part": "Base", "element": "Face1"}, "b": {"part": "Lid", "element": "Face2"}}
            out = {"plain": run(A, s, "asm_joint", J),
                   "both": run(A, s, "asm_joint", dict(J, gap=0.2, offset=0.2)),
                   "near both": run(A, s, "asm_joint", dict(J, a={"part": "Base", "kind": "face", "near": [0, 0, 0], "nearLocal": [0, 0, 0]}))}
            print(json.dumps(out, default=str))
        ''')
        ok = got["plain"]
        self.assertEqual(ok[0], "ok", ok)
        self.assertIn("gap", ok[1])
        self.assertEqual(ok[1]["gapIs"], "mm between the two joined elements across the joint: positive apart, negative overlapping.")
        self.assertEqual(set(ok[1]["at"]), {"a", "b"})
        self.assertEqual(got["both"], ["refused", "invalid_input", "gap or offset, not both: gap is the mm between the two joined faces after the solve (positive apart, negative "
                                                                   "overlapping), and the tool finds the offset for it."])
        self.assertEqual(got["near both"][:2], ["refused", "invalid_input"])
        self.assertIn("near or nearLocal, not both", got["near both"][2])

    def test_near_local_is_the_parts_own_frame(self):
        got = child("_dataasm_standin", '''
            from agentlink.families import assembly as A
            V = fc.fc.Vector
            class Sh:
                Placement = fc.fc.Placement(V(0, 0, 50), fc.fc.Rotation())
            class Part:
                Shape = Sh()
            w = A.local_to_world(Part(), [1, 2, 3])
            print(json.dumps([w.x, w.y, w.z]))
        ''')
        self.assertEqual(got, [1.0, 2.0, 53.0])

    def test_the_entry_unreached_refusal_and_the_card(self):
        e = entries()["asm_joint"]
        self.assertIn("gap", e["inputSchema"]["properties"])
        self.assertIn("nearLocal", e["inputSchema"]["properties"]["a"]["description"])
        steps = json.dumps(e["steps"])
        self.assertIn("gap: the gap across this joint cannot be measured", steps)
        for words in ("near in a query uses document coordinates", "nearLocal uses the part's own frame", "its direction depends on which part moves",
                      "gap: mm between the joined faces after the solve (negative: overlap)", "Not with offset", "at: each element's centre when picked, in document coordinates"):
            self.assertIn(words, e["description"])


# ---- finding 9: one material list -------------------------------------------------------------

class ShortIds(unittest.TestCase):
    def test_material_set_takes_measure_masss_short_ids(self):
        got = child("_datapart_standin", '''
            from agentlink.families import material as M
            out = {"short": [M.short_id(x) for x in ("Steel", "pla", "Steel-1C22", None, "brass")]}
            M._cache["lib"] = {}
            c = M.card(None, "steel")
            out["stock"] = [c["id"], c["name"], c["density"], c["source"]]
            M._cache["lib"] = {"u-1": {"id": "u-1", "name": "Steel-Generic", "density": 7.9, "source": "FreeCAD material library"},
                               "u-2": {"id": "u-2", "name": "Steel-1C22", "density": 7.85, "source": "FreeCAD material library"}}
            c = M.card(None, "STEEL")
            out["library"] = [c["id"], c["name"]]
            out["by name"] = M.card(None, "Steel-1C22")["id"]
            print(json.dumps(out))
        ''')
        self.assertEqual(got["short"], ["steel", None, None, None, "brass"])
        self.assertEqual(got["stock"], ["steel", "Steel (carbon)", 7.85, "Agent Link's stock table (typical density only)"])
        self.assertEqual(got["library"], ["u-1", "Steel-Generic"])
        self.assertEqual(got["by name"], "u-2")

    def test_the_entry_says_which(self):
        e = entries()["material_set"]
        self.assertIn("The short ids of measure_mass also work", e["description"])
        self.assertIn("mapped", e["answer"]["fields"])
        # measure_mass still takes material_set's ids (library ids and names) through card.
        self.assertIn("=card(raw)", json.dumps(entries()["measure_mass"]["steps"]))


# ---- finding 11: asm_bom mass of a printed part -----------------------------------------------

class BomPrinted(unittest.TestCase):
    def test_a_printed_part_is_as_printed_or_marked_solid(self):
        got = child("_dataasm_standin", '''
            from agentlink import hooks, store
            from agentlink.families import assembly_more as AM
            s = fc.Session(tempfile.mkdtemp())
            b = fc.a_part("Base", (0, 0, 0), (10, 10, 10), name="Base")
            store.write(s.doc, "setups", [{"id": "s1", "name": "Print", "type": "print", "bodies": ["Base"]}])
            mats = {"Base": "pla"}
            out = {"none": AM.bom_row(b, mats, s)}
            hooks.provide("mass_properties", lambda session, args: {"bodies": [{"body": args["body"], "mass": 0.512, "as": "printed: 2 walls, 15% infill"}]})
            out["service"] = AM.bom_row(b, mats, s)
            store.write(s.doc, "setups", [])
            out["not printed"] = AM.bom_row(b, mats, s)
            hooks.provide("mass_properties", None)
            print(json.dumps(out, default=str))
        ''')
        none = got["none"]
        self.assertEqual(none["massAs"], AM_SOLID)
        self.assertNotIn("solidMass", none)
        svc = got["service"]
        self.assertEqual((svc["mass"], svc["massAs"]), (0.51, "printed: 2 walls, 15% infill"))
        self.assertEqual(svc["solidMass"], none["mass"])
        self.assertNotIn("massAs", got["not printed"])

    def test_a_library_material_has_a_mass_too(self):
        got = child("_dataasm_standin", '''
            from agentlink.families import assembly_more as AM, material as M
            M._cache["lib"] = {"u-9": {"id": "u-9", "name": "Steel-Generic", "density": 8.0, "source": "FreeCAD material library"}}
            s = fc.Session(tempfile.mkdtemp())
            b = fc.a_part("Plate", (0, 0, 0), (10, 10, 10), name="Plate")
            print(json.dumps({"lib": AM.bom_row(b, {"Plate": "u-9"}, s), "short": AM.bom_row(b, {"Plate": "steel"}, s)}, default=str))
        ''')
        self.assertEqual(got["lib"]["mass"], round(got["lib"]["volume"] * 8.0, 2))
        self.assertEqual(got["short"]["mass"], round(got["short"]["volume"] * 8.0, 2))  # steel: the library's card here

    def test_the_card_says_which(self):
        e = entries()["asm_bom"]
        self.assertIn("massAs", e["description"])
        self.assertIn("massNote", e["answer"]["fields"])


AM_SOLID = ("solid, not as printed: the part is in a print setup. An installed add-on that owns mass gives the printed estimate "
            "(walls and infill); slice gives the slicer's own figure.")


if __name__ == "__main__":
    unittest.main()
