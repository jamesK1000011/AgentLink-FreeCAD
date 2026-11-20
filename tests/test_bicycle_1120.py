# SPDX-License-Identifier: LGPL-2.1-or-later
# The assembly findings of the bicycle test drive of 20 Nov 2026, on the data
# tests' stand-in FreeCAD (tests/_dataasm_standin.py) in a child process:
#   3  asm_joint keep: the offset that holds parts already placed where they
#      stand, so the joint moves nothing;
#   4  asm_joint turns no part over by itself: a warning names the overlap
#      and says how to flip; autoFlip: true is the old way, with a warning
#      when the flip puts a part's centre across the joint's plane;
#   5  asm_joint kind chain: FreeCAD's belt joint with the ratio
#      teeth1 / teeth2, the teeth given or read from PartDesign sprockets;
#   6  asm_sweep stops in time: the steps done, partial, continueWith;
#   7  asm_sweep: overlaps there from the first step, the same at every
#      step, apart from the contacts the motion makes.
import json
import os
import subprocess
import sys
import textwrap
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)
sys.path.insert(0, ROOT)


def entries():
    with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
        return json.load(f)["entries"]


def child(*bodies):
    """body run in a Python of its own after the stand-in FreeCAD is in and
    an assembly of Base (grounded) and Lid made; what it prints last, as JSON."""
    code = textwrap.dedent(f'''
        import json, sys, tempfile
        sys.path[:0] = [{ROOT!r}, {TESTS!r}]
        import _dataasm_standin
        fc = _dataasm_standin.install()
        from agentlink.protocol import ToolError
        from agentlink.families import assembly as A
        fc.fc.GuiUp = False
        fc.fc.Version = lambda: ["1", "1", "3"]
        fc.state["solves"] = 0
        s = fc.Session(tempfile.mkdtemp())
        V, P, R = fc.fc.Vector, fc.fc.Placement, fc.fc.Rotation
        J = {J!r}

        def run(name, args):
            t = next(t for t in A.tools(s) if t.name == name)
            try:
                return ["ok", t.fn(json.loads(json.dumps(args)))]
            except ToolError as e:
                return ["refused", e.code, e.message]

        def assembly(*names):
            a = fc.an_object("Assembly::AssemblyObject", "Assembly", "Assembly")
            a.__dict__["Type"] = "Assembly"
            jg = fc.into(a, fc.an_object("Assembly::JointGroup", "Joints"))
            for p in names:
                fc.into(a, fc.doc().getObject(p))
            g = fc.into(jg, fc.an_object("App::FeaturePython", "GroundedJoint"))
            g.__dict__["ObjectToGround"] = fc.doc().getObject(names[0])
            return a, jg

        def joint(jg, kind, a, b, label=None, **props):
            from _dataasm_standin import JOINT_TYPES
            j = fc.into(jg, fc.an_object("App::FeaturePython", kind, label))
            fc.joint(j, JOINT_TYPES.index(kind))
            def ref(r):
                p, _, el = r.partition(".")
                return [fc.doc().getObject(p), [el, el]]
            j.__dict__.update(Reference1=ref(a), Reference2=ref(b), **props)
            return j

        def place(name, at, deg=0.0):
            fc.doc().getObject(name).Placement = P(V(*at), R(V(0, 0, 1), deg))

        fc.a_part("Base", (0, 0, 0), (10, 10, 10), name="Base")
        fc.a_part("Lid", (0, 0, 10), (10, 10, 12), name="Lid")
    ''') + "\n".join(textwrap.dedent(b) for b in bodies)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


J = {"kind": "fixed", "a": {"part": "Base", "element": "Face1"}, "b": {"part": "Lid", "element": "Face2"}}

# A solve as FreeCAD's for a fixed joint: the part not grounded put where
# part·Placement·Offset of both ends meet. side: which way the offset runs.
SOLVER = '''
    def solver(asm, side="2"):
        def solve():
            jg = next(o for o in asm.Group if o.TypeId == "Assembly::JointGroup")
            for j in jg.Group:
                if getattr(j, "JointType", None) != "Fixed" or not j.Reference1:
                    continue
                p1, p2 = j.Reference1[0], j.Reference2[0]
                o1, o2 = j.Offset1, j.Offset2
                if side == "inverse":
                    o2 = o2.inverse()
                g1 = p1.Placement.multiply(j.Placement1).multiply(o1)
                p2.Placement = g1.multiply(j.Placement2.multiply(o2).inverse())
            return 0
        asm.__dict__["solve"] = solve
    import _dataasm_standin as SI
    jo = sys.modules["JointObject"]
    first_joint = jo.Joint
    def joint_with_frames(j, index):
        first_joint(j, index)
        # the joint's frames on each part, as updateJCSPlacements leaves them
        j.__dict__.update(Placement1=P(V(5, 5, 10), R(V(0, 0, 1), 0)), Placement2=P(V(5, 5, 0), R(V(0, 0, 1), 0)))
    jo.Joint = joint_with_frames
'''


class Keep(unittest.TestCase):
    """Finding 3."""

    def test_keep_moves_nothing_and_answers_the_offset(self):
        got = child(SOLVER, '''
            out = {}
            for side in ("2", "inverse"):
                fc.state["doc"].__dict__["Objects"] = [o for o in fc.state["doc"].Objects if o.Name in ("Base", "Lid")]
                for o in fc.state["doc"].Objects:
                    o.InList[:] = []
                place("Base", (0, 0, 0)); place("Lid", (30, 4, 25), 30.0)
                asm, jg = assembly("Base", "Lid")
                solver(asm, side)
                lid0 = fc.doc().getObject("Lid").Placement.copy()
                r = run("asm_joint", dict(J, keep=True))
                lid = fc.doc().getObject("Lid").Placement
                out[side] = [r, lid.isSame(lid0, 1e-6)]
            # without keep the same joint moves the lid onto the base
            fc.state["doc"].__dict__["Objects"] = [o for o in fc.state["doc"].Objects if o.Name in ("Base", "Lid")]
            place("Lid", (30, 4, 25), 30.0)
            asm, jg = assembly("Base", "Lid")
            solver(asm)
            out["plain"] = run("asm_joint", J)
            out["with offset"] = run("asm_joint", dict(J, keep=True, offset=1))
            out["with reverse"] = run("asm_joint", dict(J, keep=True, reverse=True))
            print(json.dumps(out, default=str))
        ''')
        for side in ("2", "inverse"):
            r, same = got[side]
            self.assertEqual(r[0], "ok", r)
            self.assertEqual(r[1]["moved"], {}, side)
            self.assertTrue(same, side)
            kept = r[1]["kept"]
            self.assertIn(kept["property"], ("Offset1", "Offset2"))
            self.assertEqual(kept["moved"], {"mm": 0.0, "degrees": 0.0})
            self.assertNotIn("keepWarning", r[1])
            self.assertEqual(set(kept), {"property", "at", "axis", "angle", "moved"})
        # the first try is part·Placement2·Offset2 = part·Placement1: offset 30° and the lid's offset in the joint's frame
        self.assertEqual(got["2"][0][1]["kept"]["property"], "Offset2")
        self.assertAlmostEqual(abs(got["2"][0][1]["kept"]["angle"]), 30.0, places=3)
        self.assertIn("Lid", got["plain"][1]["moved"])
        self.assertNotIn("kept", got["plain"][1])
        self.assertEqual(got["with offset"][:2], ["refused", "invalid_input"])
        self.assertIn("keep, or offset, rotate and gap", got["with offset"][2])
        self.assertEqual(got["with reverse"][:2], ["refused", "invalid_input"])
        self.assertIn("keep turns no part over", got["with reverse"][2])


class NoFlipByItself(unittest.TestCase):
    """Finding 4."""

    def run_case(self, args, flip_to):
        return child(f'''
            asm, jg = assembly("Base", "Lid")
            fc.state["flags"].update(joint_puts={{"Lid": [0, 0, -5]}}, flip_puts={{"Lid": {flip_to!r}}})
            r = run("asm_joint", {args!r})
            print(json.dumps([r, list(fc.doc().getObject("Lid").Placement.Base)], default=str))
        ''')

    def test_default_warns_and_does_not_flip(self):
        r, at = self.run_case(J, [0, 0, 0])
        self.assertEqual(r[0], "ok", r)
        self.assertNotIn("flipped", r[1])
        self.assertEqual(at, [0.0, 0.0, -5.0])  # left as the solve put it
        self.assertEqual(r[1]["overlaps"][0]["parts"], ["Base", "Lid"])
        w = r[1]["warning"]
        self.assertTrue(w.startswith("Parts overlap after the solve: Base/Lid "), w)
        self.assertIn("mm³", w)
        self.assertIn("did not turn a part over", w)
        self.assertIn("reverse: true", w)
        self.assertIn("autoFlip: true", w)

    def test_auto_flip_is_the_old_way(self):
        r, at = self.run_case(dict(J, autoFlip=True), [0, 0, 0])
        self.assertEqual(r[0], "ok", r)
        self.assertIn("turned over to stop the parts overlapping", r[1]["flipped"])
        self.assertNotIn("overlaps", r[1])
        self.assertNotIn("flipWarning", r[1])  # the lid stayed above the joint's plane
        self.assertEqual(at, [0.0, 0.0, 0.0])

    def test_auto_flip_across_the_plane_is_said(self):
        # the flip puts the lid below the base: its centre crosses the joint's plane (z = 0)
        r, at = self.run_case(dict(J, autoFlip=True), [0, 0, -30])
        self.assertEqual(r[0], "ok", r)
        self.assertIn("flipped", r[1])
        self.assertIn("other side of the joint's plane", r[1]["flipWarning"])
        self.assertIn("Lid", r[1]["flipWarning"])
        self.assertEqual([c["part"] for c in r[1]["crossedPlane"]], ["Lid"])
        c = r[1]["crossedPlane"][0]
        self.assertGreater(c["before"], 0)
        self.assertLess(c["after"], 0)

    def test_auto_flip_and_reverse_not_both(self):
        r, _ = self.run_case(dict(J, autoFlip=True, reverse=False), [0, 0, 0])
        self.assertEqual(r[:2], ["refused", "invalid_input"])

    def test_explicit_reverse_still_flips(self):
        r, at = self.run_case(dict(J, reverse=True), [0, 0, 0])
        self.assertIs(r[1]["flipped"], True)


class ChainByTeeth(unittest.TestCase):
    """Finding 5."""

    def test_teeth_given(self):
        got = child('''
            asm, jg = assembly("Base", "Lid")
            r = run("asm_joint", {"kind": "chain", "a": {"part": "Base", "element": "Face1"}, "b": {"part": "Lid", "element": "Face1"}, "teeth1": 50, "teeth2": 16})
            j = next(x for x in jg.Group if getattr(x, "JointType", None) == "Belt")
            print(json.dumps([r, j.Label, j.Distance / j.Distance2, j.Distance]))
        ''')
        r, label, ratio, r1 = got
        self.assertEqual(r[0], "ok", r)
        self.assertEqual(r[1]["kind"], "chain")
        self.assertEqual(label, "Chain")
        self.assertAlmostEqual(ratio, 3.125, places=9)
        self.assertEqual(r[1]["ratio"], 3.125)
        self.assertEqual(r[1]["teeth"], [50, 16])
        self.assertEqual(r[1]["ratioFrom"], "teeth1 50 given; teeth2 16 given")
        self.assertAlmostEqual(r1, 50 * 12.7 / (2 * 3.141592653589793), places=6)  # pitch radius of a 1/2 in chain

    def test_teeth_read_from_the_sprockets_and_the_sweep_drives_by_them(self):
        got = child('''
            fc.a_part("Wheel", (40, 0, 0), (50, 10, 2), name="Wheel")
            asm, jg = assembly("Base", "Lid", "Wheel")
            for part, label, n in (("Lid", "Chainring", 50), ("Wheel", "Cog", 16)):
                sp = fc.an_object("PartDesign::Sprocket", "Sprocket", label)
                sp.__dict__["NumberOfTeeth"] = n
                fc.doc().getObject(part).__dict__["Group"] = [sp]
            joint(jg, "Revolute", "Base.Face1", "Lid.Face1", "Crank")
            joint(jg, "Revolute", "Base.Face1", "Wheel.Face1", "Axle")
            r = run("asm_joint", {"kind": "chain", "a": {"part": "Lid", "element": "Face1"}, "b": {"part": "Wheel", "element": "Face1"}})
            sw = run("asm_sweep", {"joint": "Crank", "steps": 1, "to": 10})
            # two sprockets in one part: say which
            sp = fc.an_object("PartDesign::Sprocket", "Sprocket", "Small ring")
            sp.__dict__["NumberOfTeeth"] = 34
            fc.doc().getObject("Lid").__dict__["Group"].append(sp)
            two = run("asm_joint", {"kind": "chain", "a": {"part": "Lid", "element": "Face1"}, "b": {"part": "Wheel", "element": "Face1"}})
            # none in Base
            none = run("asm_joint", {"kind": "chain", "a": {"part": "Wheel", "element": "Face1"}, "b": {"part": "Base", "element": "Face1"}})
            rev = run("asm_joint", {"kind": "revolute", "a": {"part": "Base", "element": "Face1"}, "b": {"part": "Lid", "element": "Face1"}, "teeth1": 3})
            print(json.dumps([r, sw, two, none, rev]))
        ''')
        r, sw, two, none, rev = got
        self.assertEqual(r[0], "ok", r)
        self.assertEqual(r[1]["ratio"], 3.125)
        self.assertIn("Chainring", r[1]["ratioFrom"])
        self.assertIn("Cog", r[1]["ratioFrom"])
        self.assertIn("NumberOfTeeth", r[1]["ratioFrom"])
        self.assertEqual(sw[0], "ok", sw)
        self.assertEqual(sw[1]["driven"], [{"part": "Wheel", "via": "Chain", "turns": "degrees", "per": 3.125}])
        self.assertEqual(sw[1]["steps"][-1]["driven"], {"Wheel": 31.25})
        self.assertEqual(two[:2], ["refused", "invalid_input"])
        self.assertIn("give teeth1", two[2])
        self.assertIn("Small ring", two[2])
        self.assertEqual(none[:2], ["refused", "invalid_input"])
        self.assertIn("no Sprocket with NumberOfTeeth in Base", none[2])
        self.assertEqual(rev[:2], ["refused", "invalid_input"])
        self.assertIn("teeth1, teeth2: for kind chain, belt and gears only", rev[2])


class MoreRefusals(unittest.TestCase):
    """Every new refusal of asm_joint reached (tests/_dataasm_cases.py UNREACHED)."""

    def test_refusals(self):
        got = child('''
            asm, jg = assembly("Base", "Lid")
            C = {"kind": "chain", "a": {"part": "Base", "element": "Face1"}, "b": {"part": "Lid", "element": "Face1"}}
            out = {"teeth and radii": run("asm_joint", dict(C, teeth1=50, teeth2=16, radius1=5)),
                   "chain, nothing to go by": run("asm_joint", C),
                   "half the teeth": run("asm_joint", dict(C, teeth1=50)),
                   "teeth not whole": run("asm_joint", dict(C, teeth1=50.5, teeth2=16)),
                   "keep and autoFlip": run("asm_joint", dict(J, keep=True, autoFlip=True))}
            jo = sys.modules["JointObject"]
            first_joint = jo.Joint
            def no_frames(j, index):
                first_joint(j, index)
                del j.__dict__["Placement1"]
            jo.Joint = no_frames
            out["keep, no frames"] = run("asm_joint", dict(J, keep=True))
            print(json.dumps(out))
        ''')
        self.assertEqual(got["teeth and radii"], ["refused", "invalid_input", "teeth or radii, not both: teeth1 and teeth2 set radius1 and radius2."])
        self.assertEqual(got["chain, nothing to go by"][:2], ["refused", "invalid_input"])
        self.assertTrue(got["chain, nothing to go by"][2].startswith("chain: teeth1 and teeth2, a PartDesign Sprocket in each part"), got)
        self.assertEqual(got["half the teeth"][:2], ["refused", "invalid_input"])
        self.assertIn("teeth2: no Sprocket with NumberOfTeeth in Lid", got["half the teeth"][2])
        self.assertIn("a whole number of teeth", got["teeth not whole"][2])
        self.assertIn("keep turns no part over", got["keep and autoFlip"][2])
        self.assertEqual(got["keep, no frames"][:2], ["refused", "invalid_input"])
        self.assertIn("keep: FreeCAD gave this joint no frames to read", got["keep, no frames"][2])


class SweepInTime(unittest.TestCase):
    """Finding 6."""

    def test_the_sweep_stops_in_time_and_says_how_to_go_on(self):
        got = child('''
            asm, jg = assembly("Base", "Lid")
            joint(jg, "Revolute", "Base.Face1", "Lid.Face1", "Hinge")
            lid0 = fc.doc().getObject("Lid").Placement.copy()
            t = [0.0]
            def clock():
                t[0] += 1.0
                return t[0]
            A._clock = clock
            A.SWEEP_BUDGET = 6.0
            part = run("asm_sweep", {"joint": "Hinge", "from": 0, "to": 90, "steps": 9})
            back = fc.doc().getObject("Lid").Placement.isSame(lid0, 1e-9)
            A.SWEEP_BUDGET = 0.5  # out of time in the first step
            none = run("asm_sweep", {"joint": "Hinge", "steps": 2})
            A.SWEEP_BUDGET = 1000.0
            full = run("asm_sweep", {"joint": "Hinge", "steps": 2})
            print(json.dumps([part, back, none, full]))
        ''')
        part, back, none, full = got
        self.assertEqual(part[0], "ok", part)
        p = part[1]
        self.assertIs(p["partial"], True)
        done = p["stepsDone"]
        self.assertTrue(0 < done < 10, done)
        self.assertEqual(len(p["steps"]), done)
        self.assertEqual(p["continueWith"], {"joint": "Hinge", "from": 10.0 * done, "to": 90.0, "steps": 9 - done})
        self.assertIn(f"after {done} of 10 steps", p["partialNote"])
        self.assertTrue(back)
        self.assertEqual(none[1]["stepsDone"], 0)
        self.assertEqual(none[1]["verdict"], "not checked")
        self.assertEqual(none[1]["continueWith"], {"joint": "Hinge", "from": 0.0, "to": 90.0, "steps": 2})
        self.assertNotIn("partial", full[1])
        self.assertEqual(len(full[1]["steps"]), 3)

    def test_rest_and_budget_helpers(self):
        got = child('''
            class J:
                Label = "Hinge"
            print(json.dumps([A.sweep_rest(J(), 0, 90, 9, None), A.sweep_rest(J(), -30, 30, 6, 4), A.SWEEP_BUDGET]))
        ''')
        self.assertIsNone(got[0])
        self.assertEqual(got[1], {"joint": "Hinge", "from": 10.0, "to": 30.0, "steps": 2})
        self.assertLess(got[2], 80)


class StaticOverlaps(unittest.TestCase):
    """Finding 7."""

    def test_split_static(self):
        got = child('''
            def row(at, *hits):
                r = {"at": at}
                if hits:
                    r["overlaps"] = [{"parts": list(p), "volume": v} for p, v in hits]
                return r
            rows = [row(0, (("Axle", "Hub"), 120.0), (("Crank", "Frame"), 5.0)),
                    row(10, (("Hub", "Axle"), 120.4), (("Crank", "Frame"), 9.0)),
                    row(20, (("Axle", "Hub"), 119.8)),
                    row(30, (("Axle", "Hub"), 120.0), (("Pedal", "Frame"), 2.0))]
            motion, static = A.split_static(rows)
            one, none = A.split_static(rows[:1])
            print(json.dumps([motion, static, one, none]))
        ''')
        motion, static, one, none = got
        self.assertEqual(static, [{"parts": ["Axle", "Hub"], "volume": 120.0}])
        self.assertEqual(motion[0]["overlaps"], [{"parts": ["Crank", "Frame"], "volume": 5.0}])
        self.assertNotIn("overlaps", motion[2])
        self.assertEqual(motion[3]["overlaps"], [{"parts": ["Pedal", "Frame"], "volume": 2.0}])
        self.assertEqual(len(one[0]["overlaps"]), 2)  # one step proves nothing
        self.assertEqual(none, [])

    def test_the_sweep_leaves_static_overlaps_out_of_the_verdict(self):
        got = child('''
            fc.a_part("Pin", (2, 2, 5), (4, 4, 15), name="Pin")  # pressed into the base, the lid turns round it
            asm, jg = assembly("Base", "Lid", "Pin")
            joint(jg, "Slider", "Base.Face2", "Lid.Face1", "Slide")
            print(json.dumps(run("asm_sweep", {"joint": "Slide", "steps": 2})))
        ''')
        self.assertEqual(got[0], "ok", got)
        r = got[1]
        pairs = [sorted(h["parts"]) for h in r["staticOverlaps"]]
        self.assertIn(["Base", "Pin"], pairs)
        for row in r["steps"]:
            for h in row.get("overlaps", ()):
                self.assertNotIn(sorted(h["parts"]), pairs)
        self.assertIn("staticNote", r)
        if r["verdict"] == "collides":
            self.assertTrue(all(any(row["at"] == at and row.get("overlaps") for row in r["steps"]) for at in r["collidesAt"]))


class Cards(unittest.TestCase):
    def test_the_cards_say_it(self):
        e = entries()
        j, sw = e["asm_joint"], e["asm_sweep"]
        props = j["inputSchema"]["properties"]
        for k in ("keep", "autoFlip", "teeth1", "teeth2"):
            self.assertIn(k, props)
        self.assertIn("chain", props["kind"]["enum"])
        for words in ("chain: the belt joint with the ratio teeth1 / teeth2 (50 / 16 = 3.125)", "PartDesign Sprocket", "Omitted: no turn; a warning names each overlap",
                      "autoFlip: true", "flipWarning", "keep: true finds the offset and turn", "kept, ratio, ratioFrom"):
            self.assertIn(words, j["description"])
        for words in ("about 60 s", "partial: true", "continueWith", "staticOverlaps", "count only the contacts that the motion makes"):
            self.assertIn(words, sw["description"])

    def test_echo_lights_the_belt_button_for_a_chain(self):
        from agentlink import echo

        self.assertEqual(echo.command_for("asm_joint", {"kind": "chain"}), "Assembly_CreateJointBelt")


if __name__ == "__main__":
    unittest.main()
