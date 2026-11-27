# SPDX-License-Identifier: LGPL-2.1-or-later
# Facts only (owner, 27 Nov): the hub does what FreeCAD does and says what was
# measured. These tests pin each new fact of the branch `factsonly`:
#   - a feature that changed nothing and a dress-up that FreeCAD kept are
#     answered, with the measured fact, and not refused;
#   - FreeCAD's own defaults, and "<input> not given, so <input> is <value>";
#   - the values FreeCAD stored, under FreeCAD's property names;
#   - no word of advice in the texts that these tests read.
# The FreeCAD-facing code runs on stand-ins here (child processes). What must
# be seen on a real FreeCAD 1.1 is in the build report.
import json
import os
import subprocess
import sys
import textwrap
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from agentlink import resultline as rl  # noqa: E402

CHILD = '''
import json, sys, types
sys.path.insert(0, %r); sys.path.insert(0, %r)
import _datapd_standin
fc = _datapd_standin.install()
fc.patch()
from agentlink.families import pd_common as pc
''' % (ROOT, HERE)


def child(body):
    r = subprocess.run([sys.executable, "-c", CHILD + textwrap.dedent(body)], capture_output=True, text=True, timeout=120, cwd=HERE)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


def entries():
    with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
        return json.load(f)["entries"]


def source(*path):
    with open(os.path.join(ROOT, "agentlink", *path), encoding="utf-8") as f:
        return f.read()


SETTLE = '''
        class BB:
            def __init__(s, b): s.XMin, s.XMax, s.YMin, s.YMax, s.ZMin, s.ZMax = b; s.DiagonalLength = 100.0
        class Shp:
            def __init__(s, valid=True, faces=6): s.ok, s.Faces, s.BoundBox, s.Solids = valid, [0] * faces, BB((0, 60, 0, 30, 0, 5)), [0]
            def isNull(s): return False
            def isValid(s): return s.ok
            def countElement(s, k): return len(s.Faces)
            def optimalBoundingBox(s, a, b): return types.SimpleNamespace(isValid=lambda: True, **s.BoundBox.__dict__)
        class Doc:
            Objects = []
            def recompute(s): pass
        vol = [100.0]
        pc.newly_broken = lambda d: []
        pc.body_reading = lambda b: {"volume": vol[0]}
        pc.picks.finish = lambda s, tool, out, recompute=False: out
        sess = types.SimpleNamespace(doc=Doc())
        def feat(kind, **kw):
            return types.SimpleNamespace(Label=kind, Name=kind, TypeId="PartDesign::" + kind, PropertiesList=list(kw), BaseFeature=None, **kw)
'''


class NothingRefusedThatFreeCADKept(unittest.TestCase):
    def test_a_feature_that_changes_no_volume_is_answered(self):
        got = child(SETTLE + '''
        body = types.SimpleNamespace(Label="Body", Shape=Shp())
        out = {}
        for kind, tool, must in (("Pad", "pd_pad", "add"), ("Pocket", "pd_pocket", "cut"), ("Fillet", "pd_fillet", "changed"), ("Thickness", "pd_thickness", "cut")):
            r = pc.settle(sess, body, feat(kind), tool, 100.0, must)
            out[kind] = [r["volumeChange"], r["result"], r.get("valid")]
        print(json.dumps(out))
        ''')
        for kind in ("Pad", "Pocket", "Fillet", "Thickness"):
            self.assertEqual(got[kind][0], 0.0, kind)
            self.assertEqual(got[kind][2], True, kind)
        self.assertTrue(got["Pad"][1].startswith("Pad: volume change 0 mm³."), got["Pad"][1])
        self.assertTrue(got["Pocket"][1].startswith("Pocket: volume change 0 mm³."), got["Pocket"][1])

    def test_a_dress_up_with_a_shape_that_is_not_valid_is_answered_with_the_fact(self):
        got = child(SETTLE + '''
        body = types.SimpleNamespace(Label="Body", Shape=Shp(valid=False))
        vol[0] = 97.0
        r = pc.settle(sess, body, feat("Fillet", Radius=2.0), "pd_fillet", 100.0, "changed")
        big = pc.shape_valid(types.SimpleNamespace(Shape=Shp(valid=False, faces=5000)))
        print(json.dumps([r["valid"], r["result"], big, pc.shape_valid(types.SimpleNamespace(Shape=None))]))
        ''')
        self.assertIs(got[0], False)
        self.assertTrue(got[1].endswith("FreeCAD's shape check (isValid) says that the body's shape is not valid. FreeCAD gave no error."), got[1])
        self.assertEqual(got[2], "not checked: the shape has 5000 faces, and the check runs for 3000 at most")  # a limit that is used is said
        self.assertIsNone(got[3])

    def test_freecads_error_is_passed_with_measured_facts_only(self):
        got = child(SETTLE + '''
        from agentlink.protocol import ToolError
        body = types.SimpleNamespace(Label="Body", Shape=Shp())
        out = []
        for err in ("BRep_API: command not done", "Result has multiple solids"):
            pc.newly_broken = lambda d, err=err: [{"object": "Pad", "type": "Pad", "error": err}]
            try:
                pc.settle(sess, body, feat("Pad"), "pd_pad", 100.0, "add", hint="Try a smaller size.")
            except ToolError as e:
                out.append(e.message)
        print(json.dumps(out))
        ''')
        self.assertEqual(got[0], "Pad (Pad) failed: BRep_API: command not done — nothing was kept.")
        self.assertEqual(got[1], "Pad (Pad) failed: Result has multiple solids — nothing was kept. AllowCompound is false on Body.")

    def test_no_text_of_a_refused_result_is_left(self):
        pd = source("families", "pd_common.py")
        for gone in ("added no material", "cut nothing — the profile", "removed no material", "left the body as it was", "Try a smaller size", "needs a sketch of its own",
                     "Nothing was kept. {hint}", "Move the outline over the body"):
            self.assertNotIn(gone, pd, gone)
        e = entries()
        for name, gone in (("pd_pad", "a pad inside the body"), ("pd_pocket", "refuses a pocket that cuts nothing"), ("pd_groove", "refuses a groove"),
                           ("pd_chamfer", "refuses only a chamfer"), ("pd_hole", "modelThread makes nothing"), ("doc_save", "saved only after"),
                           ("doc_new", "saves only after")):
            self.assertNotIn(gone, e[name]["description"], name)

    def test_the_save_gate_is_gone(self):
        self.assertFalse(os.path.exists(os.path.join(ROOT, "agentlink", "measured.py")))
        for path in (("protocol.py",), ("tools.py",), ("fastpath.py",)):
            self.assertNotIn("measure_refusal", source(*path), path)

    def test_a_sketch_state_has_facts_and_no_verdict(self):
        src = source("families", "sketch.py")
        for gone in ("readyForFeature", "no profile yet", "close the open wires", "make one outline", "use an arc there", "fix the constraints named"):
            self.assertNotIn(gone, src, gone)
        for fact in ('out["wiresMeet"]', 'out["selfCrossing"] = "not tested"', 'out["points"]', 'out["openVerticesCount"]'):
            self.assertIn(fact, src, fact)


class WhatFreeCADStored(unittest.TestCase):
    def test_stored_values_by_freecads_names(self):
        got = child('''
        ax = types.SimpleNamespace(Label="X_Axis", Name="X_Axis")
        f = types.SimpleNamespace(TypeId="PartDesign::LinearPattern", PropertiesList=["Direction", "Reversed", "Mode", "Length", "Offset", "Occurrences", "Refine", "Label"],
                                  Direction=(ax, [""]), Reversed=False, Mode="Extent", Length=types.SimpleNamespace(Value=100.0), Offset=10.0, Occurrences=2, Refine=True, Label="LP")
        h = types.SimpleNamespace(TypeId="PartDesign::Hole", PropertiesList=["DepthType", "Depth", "DrillPoint", "DrillPointAngle", "ThreadFit", "Threaded"],
                                  DepthType="Dimension", Depth=25.0, DrillPoint="Angled", DrillPointAngle=118.0, ThreadFit="Medium", Threaded=False)
        print(json.dumps([pc.stored_values(f), pc.stored_values(h), pc.stored_values(None), pc.stored_values(types.SimpleNamespace(TypeId="Part::Box", PropertiesList=[]))]))
        ''')
        self.assertEqual(got[0]["Direction"], "X_Axis")
        self.assertEqual({k: got[0][k] for k in ("Reversed", "Mode", "Offset", "Occurrences", "Refine")},
                         {"Reversed": False, "Mode": "Extent", "Offset": 10.0, "Occurrences": 2, "Refine": True})
        self.assertNotIn("Direction2", got[0])  # only what this FreeCAD's feature has
        self.assertEqual(got[1], {"DepthType": "Dimension", "Depth": 25.0, "DrillPoint": "Angled", "DrillPointAngle": 118.0, "ThreadFit": "Medium", "Threaded": False})
        self.assertEqual(got[2:], [{}, {}])

    def test_not_given_in_the_form_of_sketch_add(self):
        got = child('''
        a = {"radius": None, "sides": "two"}
        out = pc.not_given({}, a, {"radius": 1, "sides": "one", "reversed": False, "angle": 1.5, "length": None, "extent": "length"})
        print(json.dumps([out, pc.not_given({}, {"radius": 2}, {"radius": 1})]))
        ''')
        self.assertEqual(got[0], {"notGiven": "radius not given, so radius is 1; reversed not given, so reversed is false; angle not given, so angle is 1.5; "
                                              "extent not given, so extent is length"})
        self.assertEqual(got[1], {})

    def test_every_core_feature_tool_says_what_was_not_given(self):
        e = entries()
        for name in ("pd_pad", "pd_pocket", "pd_revolution", "pd_groove", "pd_hole", "pd_fillet", "pd_chamfer", "pd_draft", "pd_thickness",
                     "pd_mirrored", "pd_linear_pattern", "pd_polar_pattern"):
            self.assertIn("=not_given(out, a, {", json.dumps(e[name]["answer"]), name)
            self.assertEqual(len(e[name]["answer"]["with"]), 7 if name in ("pd_fillet", "pd_chamfer") else 4, name)  # no must_change, no hint


class FreeCADsDefaults(unittest.TestCase):
    """FreeCAD 1.1 source (src/Mod/PartDesign/App): Hole DepthType Dimension,
    Depth 25, DrillPoint Angled, Threaded false; Pad Length 10; Pocket Length 5;
    LinearPattern Occurrences 2, Length 100; PolarPattern Occurrences 3."""

    def test_the_hole_sets_depth_and_drill_point_only_when_given(self):
        s = json.dumps(entries()["pd_hole"]["steps"])
        self.assertIn('{"set": {"f.DepthType": "ThroughAll"}, "when": "=depth == \'through\'"}', s)
        self.assertIn('"when": "=depth is not None and depth != \'through\'"', s)
        self.assertIn('"when": "=point is not None"', s)
        self.assertIn("a.get('threaded', False)", s)
        self.assertNotIn("a.get('depth', 'through')", s)
        self.assertNotIn("a.get('drillPoint', 'flat')", s)

    def test_a_length_or_a_count_left_out_is_freecads(self):
        e = entries()
        for name in ("pd_pad", "pd_pocket"):
            s = json.dumps(e[name]["steps"])
            self.assertIn('{"set": {"f.Length": "=float(L)"}, "when": "=L is not None"}', s, name)
            self.assertIn("L is not None and (not is_num(L) or L <= 0)", s, name)
        for name in ("pd_linear_pattern", "pd_polar_pattern"):
            s = json.dumps(e[name]["steps"])
            self.assertIn('{"set": {"f.Occurrences": "=n"}, "when": "=n is not None"}', s, name)
            self.assertIn("n < 1", s, name)  # FreeCAD's Occurrences takes 1
        self.assertIn("FreeCAD's default: 3", e["pd_polar_pattern"]["description"])

    def test_two_sides_keeps_freecads_second_side(self):
        got = child('''
        from agentlink.families import feature as F
        f = types.SimpleNamespace(PropertiesList=["SideType", "Type2", "Type", "Length2"], SideType="One side", Type="ThroughAll", Type2="Length", Length2=5.0)
        F.set_sides(f, "two")
        g = types.SimpleNamespace(PropertiesList=["Refine"], Refine=True)
        F.pipe_options(g, {})
        print(json.dumps([f.SideType, f.Type2, f.Length2, g.Refine]))
        ''')
        self.assertEqual(got, ["Two sides", "Length", 5.0, True])

    def test_the_fit_words_are_mapped_in_the_card(self):
        d = entries()["pd_hole"]["description"]
        self.assertIn("fit: close|normal|loose is FreeCAD's ThreadFit Fine|Medium|Coarse for ISO metric", d)
        self.assertIn("LinearPattern also has Direction2 and Occurrences2", entries()["pd_linear_pattern"]["description"])


class SketchAddDefaults(unittest.TestCase):
    def test_every_value_the_builder_filled_is_said(self):
        got = child('''
        from agentlink.families import sketch
        print(json.dumps([sketch.by_default({"kind": "arc", "center": [1, 1], "radius": 2}),
                          sketch.by_default({"kind": "polygon", "radius": 5, "construction": True}),
                          sketch.by_default({"kind": "bspline", "points": [], "interpolate": False}),
                          sketch.by_default({"kind": "line", "from": [0, 0], "to": [1, 1], "construction": False})]))
        ''')
        self.assertEqual(got[0], {"start": 0, "end": 90, "construction": False})
        self.assertEqual(got[1], {"center": [0, 0], "sides": 6, "rotation": 0})
        self.assertEqual(got[2], {"closed": False, "degree": 3, "construction": False})
        self.assertIsNone(got[3])
        self.assertEqual(rl.default_text({"center": [0, 0], "sides": 6, "closed": False, "rotation": 0}),
                         "center not given, so center is [0, 0]; sides not given, so sides is 6; closed not given, so closed is false; rotation not given, so rotation is 0")


class Sentences(unittest.TestCase):
    def test_a_volume_change_is_its_rounded_number(self):
        self.assertEqual(rl.feature_head("Pad", "pd_pad", 0.004), "Pad: volume change 0 mm³.")
        self.assertEqual(rl.feature_head("Pad", "pd_pad", 0.006), "Pad added material, volume change +0.01 mm³.")
        self.assertEqual(rl.feature_head("Pocket", "pd_pocket", -0.006), "Pocket removed material, volume change -0.01 mm³.")
        self.assertEqual(rl.body_change_text("Body", 72.0, 72.0), "After this call the volume of Body is 72 mm³: volume change 0 mm³.")

    def test_a_dress_up_says_edges_given_and_edges_changed(self):
        got = rl.dressup_result("Fillet", "pd_fillet", -3.4, 12, "radius 2 mm", [], 1, 1, changed=4, body_box=(0, 60, 0, 30, 0, 5))
        self.assertEqual(got, "Fillet: FreeCAD was given 12 edges; the result changed 4 of them, radius 2 mm, volume change -3.4 mm³. "
                              "The body now is x 0..60, y 0..30, z 0..5. The body is 1 solid (was 1).")

    def test_edges_changed_is_measured_on_the_new_shape(self):
        got = child('''
        class E:
            def __init__(s, mid): s.mid = mid; s.FirstParameter, s.LastParameter = 0.0, 1.0
            def valueAt(s, u): return s.mid
        class Skin:
            def distToShape(s, v): return (0.0 if v == "on" else 1.5, [], [])
        pc.Part = types.SimpleNamespace(Compound=lambda faces: Skin(), Vertex=lambda p: p)
        old = types.SimpleNamespace(Edges=[E("on"), E("off"), E("off")])
        new = types.SimpleNamespace(Faces=[])
        print(json.dumps([pc.edges_changed(old, new, ["Edge1", "Edge2", "Edge3"]), pc.edges_changed(old, new, ["Edge9"])]))
        ''')
        self.assertEqual(got, [2, None])


if __name__ == "__main__":
    unittest.main()
