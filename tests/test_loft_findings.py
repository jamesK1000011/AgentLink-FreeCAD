# SPDX-License-Identifier: LGPL-2.1-or-later
# Found rebuilding a scanned pistol as clean B-rep by lofting closed
# cross-sections (live test drive, 16 Nov 2026): a closed B-spline came out
# a bare open edge; a loft through such sections twisted into a solid far
# bigger than its sections, inside out, yet "sound"; a fuse with it changed
# nothing and said it removed the tool; show stopped at one unknown name.
# The sized heavy-call gate is tested beside them with stand-ins.
import math
import os
import sys
import tempfile
import time
import unittest

from _fc import HAVE, add_body, caller, server

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def ellipse(z, a=14.0, b=9.0, n=24, start=0, reverse=False, dx=0.0):
    pts = [[dx + a * math.cos(2 * math.pi * i / n), b * math.sin(2 * math.pi * i / n), z] for i in range(n)]
    pts = pts[start:] + pts[:start]
    return list(reversed(pts)) if reverse else pts


@unittest.skipUnless(HAVE, "FreeCAD is not importable here")
class LoftFindings(unittest.TestCase):
    def setUp(self):
        self.session, self.srv = server()
        self.call = caller(self.srv)
        self.call("doc_new", {"name": "Loft"})

    def ok(self, n, a=None):
        err, out = self.call(n, a)
        self.assertFalse(err, f"{n}: {out}")
        return out

    def no(self, n, a=None):
        err, out = self.call(n, a)
        self.assertTrue(err, f"{n} should be refused: {out}")
        return out["error"]

    def bodies(self):
        return {b["name"] for b in self.ok("session_state")["bodies"]}

    # 1. closed: true is one closed wire (a periodic B-spline), said truly.
    def test_bspline_closed_is_a_closed_wire(self):
        w = self.ok("part_wire", {"kind": "bspline", "closed": True, "points": ellipse(0), "name": "S0"})
        self.assertEqual((w["edges"], w["wires"], w["closed"]), (1, 1, True))
        # The first point repeated at the end closes it too.
        pts = ellipse(5)
        w2 = self.ok("part_wire", {"kind": "bspline", "closed": False, "points": pts + [pts[0]], "name": "S1"})
        self.assertEqual((w2["wires"], w2["closed"]), (1, True))
        o = self.session.doc.getObject(self.session.doc.getObjectsByLabel("S1")[0].Name)
        self.assertTrue(o.Shape.Edges[0].Curve.isPeriodic())
        op = self.ok("part_wire", {"kind": "bspline", "points": ellipse(10)[:8], "name": "Arc"})
        self.assertEqual((op["wires"], op["closed"]), (1, False))
        self.no("part_wire", {"kind": "bspline", "closed": True, "points": ellipse(0)[:2]})

    # 2. The loft lines its profiles up and is checked before it is kept.
    def test_loft_aligns_and_stays_in_its_box(self):
        names = []
        for i, z in enumerate((0, 20, 40, 60, 80)):
            # Seams all round the outline and every other one run backwards:
            # the twist the live loft had.
            a = 14.0 - 2.0 * math.sin(i)
            pts = ellipse(z, a=a, b=9.0 + i * 0.5, start=(i * 7) % 24, reverse=bool(i % 2))
            names.append(self.ok("part_wire", {"kind": "bspline", "closed": True, "points": pts, "name": f"Sec{i}"})["object"])
        out = self.ok("part_loft", {"profiles": names, "name": "Grip"})
        self.assertTrue(out["sound"], out)
        self.assertGreater(out["volume"], 0)
        self.assertTrue(out.get("aligned"), out)
        x, y, z = out["box"]
        self.assertLess(x, 2 * 14.0 * 1.15 + 0.5)
        self.assertLess(y, 2 * 11.0 * 1.15 + 0.5)
        self.assertAlmostEqual(z, 80, delta=0.5)
        # Roughly the ellipses' mean area times the height.
        mean = sum(math.pi * (14.0 - 2.0 * math.sin(i)) * (9.0 + i * 0.5) for i in range(5)) / 5
        self.assertAlmostEqual(out["volume"], mean * 80, delta=0.15 * mean * 80)
        # And a fuse with it adds to the body.
        self.ok("part_primitive", {"kind": "box", "size": [10, 10, 10], "at": [-5, -5, 75], "name": "Cap"})
        f = self.ok("part_boolean", {"op": "fuse", "base": "Grip", "tools": ["Cap"]})
        self.assertGreater(f["volumeChange"], 10)

    def test_loft_of_an_open_profile_is_refused(self):
        a = self.ok("part_wire", {"kind": "bspline", "closed": True, "points": ellipse(0), "name": "A"})["object"]
        b = self.ok("part_wire", {"kind": "bspline", "points": ellipse(20)[:12], "name": "B"})["object"]
        e = self.no("part_loft", {"profiles": [a, b]})
        self.assertIn("not closed", e["message"])
        self.assertNotIn("Loft", self.bodies())

    def test_ruled_loft_still_works(self):
        out = self.ok("part_loft", {"profiles": [{"points": [[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0]]}, {"points": [[0, 0, 10], [10, 0, 10], [10, 10, 10], [0, 10, 10]]}], "ruled": True})
        self.assertAlmostEqual(out["volume"], 1000, delta=0.01)
        self.assertTrue(out["sound"])

    def test_overshoot_is_named_a_twist(self):
        import FreeCAD
        import Part
        from agentlink.families import model

        wires = [Part.Wire([Part.makeCircle(5, FreeCAD.Vector(0, 0, z))]) for z in (0, 10)]
        over, axis = model.loft_overshoot(Part.makeBox(60, 10, 10, FreeCAD.Vector(-30, -5, 0)), wires)
        self.assertGreater(over, 0.15)
        self.assertEqual(axis, "x")
        self.assertTrue(model.loft_problem(Part.makeBox(60, 10, 10, FreeCAD.Vector(-30, -5, 0)), wires, True).startswith("profiles twist"))
        self.assertIsNone(model.loft_problem(Part.makeCylinder(5, 10), wires, True))

    def test_align_reverses_and_restarts(self):
        import FreeCAD
        import Part
        from agentlink.families import model

        def bs(pts):
            c = Part.BSplineCurve()
            c.interpolate([FreeCAD.Vector(*p) for p in pts], PeriodicFlag=True)
            return Part.Wire([c.toShape()])

        w0, w1 = bs(ellipse(0)), bs(ellipse(10, start=9, reverse=True))
        out, done = model.align_profiles([w0, w1])
        n0, n1 = model.winding_normal(out[0]), model.winding_normal(out[1])
        self.assertGreater(n0.dot(n1), 0)
        self.assertLess((model.start_of(out[1]) - model.start_of(out[0])).Length, 10.5 + 0.5)
        self.assertTrue(any("reversed" in d for d in done), done)
        self.assertTrue(out[1].isClosed())

    # 3. "sound" is valid, closed and a volume above 0, everywhere.
    def test_inside_out_is_not_sound(self):
        import Part
        from agentlink import geometry as geo

        good = Part.makeBox(10, 10, 10)
        self.assertTrue(geo.soundness(good)["ok"])
        bad = Part.makeBox(10, 10, 10)
        bad.reverse()
        if bad.Volume <= 0:
            s = geo.soundness(bad)
            self.assertFalse(s["ok"])
            self.assertTrue(any("volume" in p for p in s["problems"]))
            add_body(self.session, "Inside", bad)
            self.assertFalse(self.ok("body_check", {"body": "Inside"})["ok"])

    # 4. A fuse refuses a tool it cannot join, and keeps it.
    def test_fuse_refuses_an_unsound_tool(self):
        import FreeCAD
        import Part

        self.ok("part_primitive", {"kind": "box", "size": [20, 20, 20], "name": "Base"})
        bad = Part.makeBox(10, 10, 10, FreeCAD.Vector(15, 5, 5))
        bad.reverse()
        if bad.Volume <= 0:
            add_body(self.session, "Flipped", bad)
            e = self.no("part_boolean", {"op": "fuse", "base": "Base", "tools": ["Flipped"]})
            self.assertIn("not a sound solid", e["message"])
            self.assertIn("Flipped", self.bodies())
        # An open shell is no solid tool at all.
        shell = Part.makeBox(10, 10, 10, FreeCAD.Vector(15, 5, 5)).Faces[:5]
        add_body(self.session, "Open", Part.Shell(shell))
        self.no("part_boolean", {"op": "fuse", "base": "Base", "tools": ["Open"]})
        self.assertTrue(self.session.doc.getObjectsByLabel("Open"))  # a shell: kept, though no body

    def test_fuse_dropped_is_seen(self):
        import FreeCAD
        import Part
        from agentlink.families import model

        class B:
            def __init__(self, label, shape):
                self.Label, self.Shape = label, shape

        base = Part.makeBox(20, 20, 20)
        tool = B("Ear", Part.makeBox(10, 10, 10, FreeCAD.Vector(15, 5, 5)))
        inside = B("Core", Part.makeBox(5, 5, 5, FreeCAD.Vector(5, 5, 5)))
        self.assertEqual(model.fuse_dropped(base, [tool, inside], base), ["Ear"])
        self.assertEqual(model.fuse_dropped(base, [tool], base.fuse(tool.Shape)), [])
        self.assertIsNone(model.unsound_tool(tool.Shape))

    # 6. show does the names it finds and lists the rest.
    def test_named_objects_lists_unknown(self):
        from agentlink.families.app import named_objects

        self.ok("part_primitive", {"kind": "box", "size": [5, 5, 5], "name": "Guard"})
        objs, unknown = named_objects(self.session.doc, ["Guard", "Guard window", "Guard"])
        self.assertEqual([o.Label for o in objs], ["Guard"])
        self.assertEqual(unknown, ["Guard window"])


# 5. The sized gate: a Part boolean of many faces is estimated from its face
# pairs, asked about first in the window, and marked for the watchdog.
class Face:
    pass


class Shape:
    def __init__(self, n):
        self.Faces = [Face()] * n

    def isNull(self):
        return False


class Obj:
    def __init__(self, name, n):
        self.Name = self.Label = name
        self.Shape = Shape(n)
        self.InList = []


class Doc:
    def __init__(self, objs):
        self.Objects = objs

    def getObject(self, n):
        return next((o for o in self.Objects if o.Name == n), None)


class Sess:
    def __init__(self, doc):
        self.doc = doc


class Tool:
    def __init__(self, name, changes=True):
        self.name, self.changes = name, changes


class SizedGate(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp(prefix="agentlink-sized-")
        self.env = {k: os.environ.get(k) for k in ("AGENTLINK_HOME", "AGENTLINK_GATE")}
        os.environ["AGENTLINK_HOME"] = self.home
        os.environ["AGENTLINK_GATE"] = "1"
        from agentlink import heavy, keep

        self.heavy, self.keep = heavy, keep
        doc = Doc([Obj("Grip", 2119), Obj("Guard", 1282), Obj("Pin", 54), Obj("Peg", 6)])
        self.gate = heavy.Gate(Sess(doc))

    def tearDown(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_size_is_face_pairs(self):
        s = self.heavy.sized_size(self.gate.s, "part_boolean", {"op": "fuse", "base": "Grip", "tools": ["Guard", "Pin"]})
        self.assertEqual(s, 2119 * (1282 + 54))
        # base left out: the biggest other body.
        self.assertEqual(self.heavy.sized_size(self.gate.s, "part_boolean", {"tools": "Peg"}), 2119 * 6)
        self.assertIsNone(self.heavy.sized_size(self.gate.s, "part_boolean", {"base": "Grip", "tools": ["Nope"]}))

    def test_heavy_fuse_is_asked_then_marked_then_cleared(self):
        from agentlink.protocol import ToolError

        args = {"op": "fuse", "base": "Grip", "tools": ["Guard", "Pin"]}
        t = Tool("part_boolean")
        with self.assertRaises(ToolError) as cm:
            self.gate.before(t, args)
        self.assertIn("frozen", cm.exception.message)
        self.assertFalse(os.path.exists(self.keep.heavy_call_mark()))
        started = time.time()
        self.gate.before(t, args)  # the same call again runs it
        lim = self.keep.heavy_call_limit(started, time.time())
        est = self.keep.sized_estimate({}, "part_boolean", 2119 * 1336)
        self.assertGreater(est, 60)
        self.assertAlmostEqual(lim, max(self.keep.DEADLINES["change"], 3 * est), delta=0.01)
        # A mark from before the call in hand started is not this call's.
        self.assertIsNone(self.keep.heavy_call_limit(started + 5, time.time()))
        self.gate.after(t, args, True)
        self.assertFalse(os.path.exists(self.keep.heavy_call_mark()))

    def test_small_boolean_is_left_alone(self):
        self.gate.before(Tool("part_boolean"), {"op": "cut", "base": "Peg", "tools": ["Pin"]})
        self.assertFalse(os.path.exists(self.keep.heavy_call_mark()))
        self.gate.after(Tool("part_boolean"), {}, True)

    def test_estimate_learns_from_runs(self):
        q = {"timings": {"part_boolean": [[1000.0, 1.0], [2000.0, 2.0]]}}
        self.assertAlmostEqual(self.keep.sized_estimate(q, "part_boolean", 4000), 4.0, delta=0.01)
        self.assertIsNone(self.keep.sized_estimate(q, "part_fillet", 4000))

    def test_undo_is_marked_not_asked(self):
        big = Doc([Obj("Grip", 6000)])
        g = self.heavy.Gate(Sess(big))
        started = time.time()
        g.before(Tool("history_undo"), {})
        self.assertIsNotNone(self.keep.heavy_call_limit(started, time.time()))
        g.after(Tool("history_undo"), {}, True)
        self.assertFalse(os.path.exists(self.keep.heavy_call_mark()))


if __name__ == "__main__":
    unittest.main()
