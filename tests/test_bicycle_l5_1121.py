# SPDX-License-Identifier: LGPL-2.1-or-later
# Findings of the bicycle L5 build (FreeCAD 1.1.3, 21 Nov 2026; about 35
# bodies, 32 assembly parts), on the data tests' stand-in FreeCAD in a child
# process (test_bicycle_1120.child) where an assembly is used:
#   1  asm_sweep: the parts fixed to a driven part move with it (any depth),
#      and moves names them; a grounded part fixed to a moving part is named.
#   2  an LCS that a fixed joint names, turned: the joint's frames are made
#      again from it, and a part that the solve leaves where it was is put
#      where the two frames meet (or the health check says the joint did not
#      follow).
#   3  sketch_attach { edge, mode, at } hangs a sketch on an edge again in
#      place (a feature built from it); repair: true re-points a lost element.
#   4  Refine on a pipe weldment: pd_pipe sets Refine false; body_check and
#      the health check name "Refine off" when the body is unorientable.
#   5  a recompute leaves out an assembly whose solve cannot move a part.
import json
import os
import subprocess
import sys
import textwrap
import types
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TESTS)

from test_bicycle_1120 import child  # noqa: E402

DRIVE = '''
    # Base grounded; the crank (Lid) turns on it, a chain drives the wheel; spokes on the wheel, a rim on the spokes
    fc.a_part("Wheel", (40, 0, 0), (50, 10, 2), name="Wheel")
    fc.a_part("Spokes", (41, 1, 0), (49, 9, 2), name="Spokes")   # inside the wheel: they move together
    fc.a_part("Rim", (40, 0, 2), (50, 10, 3), name="Rim")
    fc.a_part("CrankL", (0, 0, 12), (10, 10, 13), name="CrankL")
    fc.a_part("Pin", (2, 2, 13), (3, 3, 14), name="Pin")
    asm, jg = assembly("Base", "Lid", "Wheel", "Spokes", "Rim", "CrankL", "Pin")
    joint(jg, "Revolute", "Base.Face1", "Lid.Face1", "Crank")
    joint(jg, "Revolute", "Base.Face1", "Wheel.Face1", "Axle")
    joint(jg, "Belt", "Lid.Face1", "Wheel.Face1", "Chain", Distance=42.0, Distance2=16.0)
    joint(jg, "Fixed", "Wheel.Face1", "Spokes.Face1", "SpokesJ")
    joint(jg, "Fixed", "Spokes.Face1", "Rim.Face1", "RimJ")
    joint(jg, "Fixed", "Lid.Face1", "CrankL.Face1", "CrankLJ")
'''


class SweepCarriesDriven(unittest.TestCase):
    """Finding 1."""

    def test_driven_part_carries_its_fixed_parts(self):
        got = child(DRIVE, '''
            sw = run("asm_sweep", {"joint": "Crank", "steps": 2, "to": 20})
            places = {n: [round(c, 6) for c in fc.doc().getObject(n).Placement.Base] for n in ("Wheel", "Spokes", "Rim", "CrankL")}
            print(json.dumps([sw, places]))
        ''')
        sw, places = got
        self.assertEqual(sw[0], "ok", sw)
        r = sw[1]
        self.assertEqual(r["moves"], ["CrankL", "Lid", "Rim", "Spokes"])
        self.assertEqual(r["driven"], [{"part": "Wheel", "via": "Chain", "turns": "degrees", "per": 2.625, "carries": ["Rim", "Spokes"]}])
        # the spokes inside the wheel turn with it: no overlap the motion makes
        self.assertEqual(r["verdict"], "clear", r)
        self.assertNotIn("heldBack", r)
        # every part put back
        self.assertEqual(places["Spokes"], [0, 0, 0])
        self.assertEqual(places["Rim"], [0, 0, 0])

    def test_spokes_turn_by_the_ratio_with_the_wheel(self):
        got = child(DRIVE, '''
            A_first = A.sweep_run
            seen = []
            def spy(doc, asm, j, group, driven, *rest):
                for d in driven:
                    seen.append(sorted(d["carries"]))
                return A_first(doc, asm, j, group, driven, *rest)
            A.sweep_run = spy
            moved = {}
            first_shape = A._shape
            def look(o):
                if o.Name in ("Wheel", "Spokes", "Rim"):
                    moved.setdefault(o.Name, []).append(round(math.degrees(o.Placement.Rotation.Angle) * (1 if o.Placement.Rotation.Axis.z >= 0 else -1), 3))
                return first_shape(o)
            import math
            A._shape = look
            sw = run("asm_sweep", {"joint": "Crank", "steps": 2, "to": 20})
            print(json.dumps([sw[0], seen, moved]))
        ''')
        ok, seen, moved = got
        self.assertEqual(ok, "ok")
        self.assertEqual(seen, [["Rim", "Spokes"]])
        # 0, 10, 20 degrees of the crank: 0, 26.25, 52.5 of the wheel, and the spokes and rim the same
        for n in ("Wheel", "Spokes", "Rim"):
            self.assertEqual(sorted(set(moved[n])), [0.0, 26.25, 52.5], (n, moved))

    def test_a_grounded_part_fixed_to_a_moving_part_is_named(self):
        got = child(DRIVE, '''
            g = fc.into(jg, fc.an_object("App::FeaturePython", "GroundedJoint"))
            g.__dict__["ObjectToGround"] = fc.doc().getObject("Pin")
            joint(jg, "Fixed", "Lid.Face1", "Pin.Face1", "PinJ")
            print(json.dumps(run("asm_sweep", {"joint": "Crank", "steps": 1, "to": 10})))
        ''')
        self.assertEqual(got[0], "ok", got)
        self.assertEqual(got[1]["heldBack"], ["Pin"])
        self.assertIn("Pin is grounded and fixed to a part that moves", got[1]["heldBackNote"])
        self.assertNotIn("Pin", got[1]["moves"])


# A fixed joint between Base.LCS_A and Lid.LCS_B; FreeCAD's frames as
# updateJCSPlacements makes them (here: the LCS's own placement in its part);
# a solver that keeps every part where it is (the live miss), or one that
# puts Lid back (flag solve_puts).
LCS = '''
    from types import SimpleNamespace as NS
    for part, name, at in (("Base", "LCS_A", (0, 0, 10)), ("Lid", "LCS_B", (0, 0, 0))):
        l = fc.an_object("PartDesign::CoordinateSystem", name, name)
        l.Placement = P(V(*at), R(V(0, 0, 1), 0))
        fc.doc().getObject(part).__dict__["Group"] = [l]
    asm, jg = assembly("Base", "Lid")
    place("Lid", (0, 0, 10))
    j = joint(jg, "Fixed", "Base.LCS_A.", "Lid.LCS_B.", "Hold")
    lcs = {"Reference1": fc.doc().getObject("LCS_A"), "Reference2": fc.doc().getObject("LCS_B")}
    def frames(jj):
        jj.Placement1 = lcs["Reference1"].Placement.copy()
        jj.Placement2 = lcs["Reference2"].Placement.copy()
    sys.modules["JointObject"].Joint  # loaded
    type(j.Proxy).updateJCSPlacements = lambda self, jj: frames(jj)
    frames(j)
    tool = NS(group="doc", name="object_set")
'''


class FixedJointFollowsTheLcs(unittest.TestCase):
    """Finding 2."""

    def test_a_turned_lcs_moves_the_part_joined_to_it(self):
        got = child(LCS, '''
            a = fc.doc().getObject("LCS_A")
            a.Placement = P(V(0, 0, 10), R(V(0, 0, 1), 90))
            lines = A._health(s, tool, [a])
            lid = fc.doc().getObject("Lid").Placement
            b = fc.doc().getObject("LCS_B")
            b.Placement = P(V(5, 0, 0), R(V(0, 0, 1), 0))
            lines2 = A._health(s, tool, [b])
            lid2 = fc.doc().getObject("Lid").Placement
            print(json.dumps([lines, [list(lid.Base), math.degrees(lid.Rotation.Angle)], lines2, [list(lid2.Base), math.degrees(lid2.Rotation.Angle)]]))
        '''.replace("math.", "__import__('math')."))
        lines, lid, lines2, lid2 = got
        self.assertEqual(len(lines), 1, lines)
        self.assertNotIn("red", lines[0])
        self.assertIn("the parts joined to LCS_A follow it (moved: Lid)", lines[0]["line"])
        self.assertEqual([round(c, 6) for c in lid[0]], [0, 0, 10])
        self.assertAlmostEqual(lid[1], 90.0, 6)
        # the moving part's own LCS: the part moves so that its LCS meets the other one
        self.assertIn("the parts joined to LCS_B follow it (moved: Lid)", lines2[0]["line"])
        # Lid·LCS_B = Base·LCS_A: Lid at (0, 0, 10) turned 90°, less (5, 0, 0) turned 90° = (0, -5, 10)
        self.assertEqual([round(c, 6) for c in lid2[0]], [0, -5, 10])

    def test_a_part_the_solver_puts_back_is_said(self):
        got = child(LCS, '''
            fc.state["flags"].update(solve_puts={"Lid": [0, 0, 10, 0]})
            a = fc.doc().getObject("LCS_A")
            a.Placement = P(V(0, 0, 10), R(V(0, 0, 1), 90))
            lines = A._health(s, tool, [a])
            print(json.dumps(lines))
        ''')
        self.assertEqual(len(got), 1, got)
        self.assertTrue(got[0]["red"])
        self.assertIn("but the fixed joint Hold on LCS_A did not follow: Hold frames 0.0 mm, 90.0 degrees apart", got[0]["line"])
        self.assertIn("asm_joint_remove Hold, then asm_joint again", got[0]["todo"])

    def test_frames_that_meet_move_nothing(self):
        got = child(LCS, '''
            a = fc.doc().getObject("LCS_A")
            n = fc.state["solves"]
            lines = A._health(s, tool, [a])
            print(json.dumps([lines, fc.state["solves"] - n]))
        ''')
        lines, solves = got
        self.assertIn("follow it (no part moved)", lines[0]["line"])
        self.assertEqual(solves, 1)


ROOT = os.path.join(TESTS, "..")


def sk2(*bodies):
    """body run in a child process on the stand-in of the Sketcher data tests; what it prints last."""
    code = textwrap.dedent(f'''
        import json, sys, tempfile
        sys.path[:0] = [{ROOT!r}, {TESTS!r}]
        import _datask2_standin
        fc = _datask2_standin.install()
        from agentlink.protocol import ToolError
        s = fc.Session(tempfile.mkdtemp())
        V = fc.Vec
    ''') + "\n".join(textwrap.dedent(b) for b in bodies)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


PROFILE = '''
    from agentlink.families import sketch_more as SM
    b = fc.body(s)
    binder = fc.feature(s, b, "SubShapeBinder", "Binder010")
    binder.__dict__["Shape"] = fc.Shape("wire", [V(0, 0, 0), V(0, 0, 100)], edges=[fc.edge(V(0, 0, 0), V(0, 0, 100)), fc.edge(V(0, 0, 100), V(50, 0, 100))])
    sk = fc.drawing(s, b, "TubeProfile018")
    # the support as FreeCAD keeps it after the VarSet change: a mapped name it cannot find
    sk.__dict__.update(AttachmentSupport=[(binder, ";Edge1;:H10f,E")], MapMode="NormalToEdge", MapReversed=False, MapPathParameter=0.0)
    pipe = fc.feature(s, b, "AdditivePipe", "Pipe", Profile=sk, Spine=(binder, ["Edge1"]))
    T = {t.name: t for t in SM.tools(s)}
    def run(args):
        try:
            return ["ok", T["sketch_attach"].fn(json.loads(json.dumps(args)))]
        except ToolError as e:
            return ["refused", e.code, e.message]
    def support():
        return [[o.Label, x] for o, x in sk.AttachmentSupport]
'''


class SketchOnAnEdgeAgain(unittest.TestCase):
    """Finding 3."""

    def test_repair_and_edge_with_a_feature_built_from_the_sketch(self):
        got = sk2(PROFILE, '''
            out = {"repair": run({"sketch": "TubeProfile018", "repair": True}), "s1": support()}
            out["edge"] = run({"sketch": "TubeProfile018", "edge": "Binder010.Edge2", "at": 0.5})
            out["s2"], out["mode"] = support(), [sk.MapMode, sk.MapPathParameter]
            print(json.dumps(out, default=str))
        ''')
        self.assertEqual(got["repair"][0], "ok", got["repair"])
        self.assertEqual(got["repair"][1]["repaired"], ["Binder010.Edge1"])
        self.assertEqual(got["repair"][1]["mode"], "NormalToEdge")
        self.assertEqual(got["s1"], [["Binder010", "Edge1"]])
        self.assertEqual(got["edge"][0], "ok", got["edge"])
        self.assertEqual(got["edge"][1]["on"], "Binder010.Edge2")
        self.assertEqual(got["s2"], [["Binder010", "Edge2"]])
        self.assertEqual(got["mode"], ["NormalToEdge", 0.5])

    def test_refusals(self):
        got = sk2(PROFILE, '''
            out = [run({"sketch": "TubeProfile018", "edge": "Binder010.Edge9"}),
                   run({"sketch": "TubeProfile018", "edge": "Binder010.Edge1", "mode": "FlatFace"}),
                   run({"sketch": "TubeProfile018", "edge": "Binder010.Edge1", "plane": "XY"}),
                   run({"sketch": "TubeProfile018", "edge": "Pipe.Edge1"}),
                   run({"sketch": "TubeProfile018", "edge": "Binder010"})]
            fc.state["flags"]["invalid_after"] = {"TubeProfile018": "Attachment: no edge"}
            fc.trace.append("---- the call")
            fc.trace.append("recompute()")
            out.append(run({"sketch": "TubeProfile018", "edge": "Binder010.Edge2"}))
            out.append(support())
            print(json.dumps(out, default=str))
        ''')
        noedge, badmode, both, cycle, bare, fails, after = got
        self.assertEqual(noedge[:2], ["refused", "invalid_input"])
        self.assertIn("Binder010 has no Edge9", noedge[2])
        self.assertIn("mode 'FlatFace': on an edge, one of NormalToEdge", badmode[2])
        self.assertEqual(both[2], "edge or repair: not with plane or face.")
        self.assertIn("Pipe is built from TubeProfile018", cycle[2])
        self.assertIn("an object and one of its edges", bare[2])
        self.assertEqual(fails[:2], ["refused", "failed"])
        self.assertIn("would not attach to Binder010.Edge2 (NormalToEdge): Attachment: no edge", fails[2])
        self.assertEqual(after, [["Binder010", ";Edge1;:H10f,E"]])  # put back as it was


def _feat(label, type_="PartDesign::AdditivePipe", refine=True):
    return types.SimpleNamespace(Label=label, TypeId=type_, PropertiesList=["Refine", "Profile"], Refine=refine)


class RefineOnAWeldment(unittest.TestCase):
    """Finding 4."""

    def test_the_todo_names_refine_off(self):
        sys.path.insert(0, ROOT)
        from agentlink import fusehint

        pipes = [_feat(f"Pipe{i:03d}") for i in range(12)]
        body = types.SimpleNamespace(TypeId="PartDesign::Body", Label="Frame", Group=pipes)
        t = fusehint.refine_todo(body, "")
        self.assertIn('Refine off on the features (object_set { object: "Pipe000", values: { Refine: false } } on each: '
                      "Pipe000, Pipe001, Pipe002, Pipe003, Pipe004 and 7 more), then rebuild (recompute) and body_check { body: \"Frame\" }", t)
        self.assertIn("a weldment of many tube members (12)", t)
        # few pipes: only when the check says unorientable
        few = types.SimpleNamespace(TypeId="PartDesign::Body", Label="Lug", Group=pipes[:2])
        self.assertIsNone(fusehint.refine_todo(few, "NOT valid"))
        self.assertIn("Refine off", fusehint.refine_todo(few, "FreeCAD's Check Geometry: Unorientable Shape"))
        # Refine already off: nothing to say
        off = types.SimpleNamespace(TypeId="PartDesign::Body", Label="Off", Group=[_feat(f"P{i}", refine=False) for i in range(12)])
        self.assertIsNone(fusehint.refine_todo(off, "unorientable"))
        self.assertIsNone(fusehint.refine_todo(types.SimpleNamespace(TypeId="Part::Feature", Label="X"), "unorientable"))

    def test_a_pipe_is_made_with_refine_off(self):
        got = sk2('''
            from agentlink.families import feature as F
            b = fc.body(s)
            f = fc.feature(s, b, "AdditivePipe", "Pipe", Refine=True)
            F.pipe_options(f, {})
            off = f.Refine
            F.pipe_options(f, {"refine": True})
            print(json.dumps([off, f.Refine]))
        ''')
        self.assertEqual(got, [False, True])

    def test_the_guide_has_the_trap(self):
        with open(os.path.join(ROOT, "agentlink", "guides", "design.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("Trap: Refine on every feature of a big pipe weldment can make the body unorientable", text)


class _O:
    def __init__(self, name, type_="Part::Feature", **kw):
        self.Name, self.Label, self.TypeId = name, name, type_
        self.Group, self.OutListRecursive, self.InListRecursive, self.State = [], [], [], []
        self.__dict__.update(kw)
        self.purged = False

    def purgeTouched(self):
        self.purged = True


class _Doc:
    def __init__(self, objs):
        self.Objects, self.calls = objs, []

    def getObject(self, n):
        return next((o for o in self.Objects if o.Name == n), None)

    def recompute(self, objs=None):
        self.calls.append(None if objs is None else sorted(o.Name for o in objs))
        return 1


QUIET = '''
    import json, sys
    sys.path[:0] = [{root!r}, {tests!r}]
    import _dataasm_standin
    _dataasm_standin.install()
    sys.path.insert(0, {tests!r})
    from test_bicycle_l5_1121 import _O, _Doc
    from agentlink.families import picks
    from agentlink import around
    spokes, frame, lcs, feat = _O("Spokes", "PartDesign::Body"), _O("Frame", "PartDesign::Body"), _O("LCS_S", "PartDesign::CoordinateSystem"), _O("Cyl", "PartDesign::AdditiveCylinder")
    asm, jg = _O("Bicycle", "Assembly::AssemblyObject"), _O("Joints", "Assembly::JointGroup")
    j = _O("SpokesJ", "App::FeaturePython", Reference1=[frame, ["LCS_F.", "LCS_F."]], Reference2=[spokes, ["LCS_S.", "LCS_S."]])
    jg.Group, asm.Group = [j], [jg, spokes, frame]
    feat.InListRecursive = [spokes, asm]
    feat.State = ["Touched"]
    doc = _Doc([frame, spokes, lcs, feat, asm, jg, j])
    out = {{}}
    around.start()
    picks.recompute_scoped(doc, [feat])
    out["scoped"], out["purged"] = doc.calls[-1], asm.purged
    picks.recompute_whole(doc)
    out["whole"] = doc.calls[-1]
    out["around"] = sorted(around.take())
    # a joint end on a face of the spokes: the solve can move a part, so the assembly runs
    j.Reference2 = [spokes, ["Face3", "Face3"]]
    asm.purged = False
    picks.recompute_scoped(doc, [feat])
    out["face"], out["facePurged"] = doc.calls[-1], asm.purged
    picks.recompute_whole(doc)
    out["faceWhole"] = doc.calls[-1]
    # the LCS itself changed (object_set on it): the assembly runs
    j.Reference2 = [spokes, ["LCS_S.", "LCS_S."]]
    lcs.InListRecursive = [spokes, asm]
    picks.recompute_scoped(doc, [lcs])
    out["lcs"] = doc.calls[-1]
    print(json.dumps(out))
'''


class QuietAssembly(unittest.TestCase):
    """Finding 5."""

    def test_an_assembly_whose_solve_moves_nothing_is_left_out(self):
        code = textwrap.dedent(QUIET).format(root=ROOT, tests=TESTS)
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180)
        self.assertEqual(r.returncode, 0, r.stderr[-3000:])
        got = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(got["scoped"], ["Cyl", "Spokes"])
        self.assertTrue(got["purged"])
        self.assertEqual(got["whole"], ["Cyl", "Spokes"])
        self.assertIn("recompute", got["around"])
        self.assertEqual(got["face"], ["Bicycle", "Cyl", "Spokes"])
        self.assertFalse(got["facePurged"])
        self.assertIsNone(got["faceWhole"])  # the whole document, as before
        self.assertEqual(got["lcs"], ["Bicycle", "LCS_S", "Spokes"])


if __name__ == "__main__":
    unittest.main()
