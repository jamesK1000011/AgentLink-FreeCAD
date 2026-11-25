# SPDX-License-Identifier: LGPL-2.1-or-later
# Bicycle test drive of 20 Nov 2026, findings 7 and 8, without FreeCAD (plain
# Python, or the data tests' stand-in FreeCAD in a child process):
#   7  a pad that fused a solid onto several hollow tube ends that meet at one
#      point left the body invalid: the health names the step and gives the
#      design rule, and finds the tube bores that end inside the new solid
#      (agentlink/fusehint.py; only on an invalid result);
#   8  param_bind read "Pad.Length" by the object's Name (the chainring's pad)
#      when the frame's pad had the label "Pad": a name that is one object's
#      Name and another's Label is refused with the <<Label>> forms to choose
#      from, as is a default name of an object in another Body when the
#      target's own Body has one like it.
import json
import os
import subprocess
import sys
import textwrap
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)
sys.path.insert(0, ROOT)
sys.path.insert(0, TESTS)

from agentlink import exprs, fusehint  # noqa: E402


def child(*parts):
    code = textwrap.dedent(f'''
        import json, sys, tempfile
        sys.path[:0] = [{ROOT!r}, {TESTS!r}]
        import _datask2_standin
        fc = _datask2_standin.install()
        from agentlink.protocol import ToolError
        from agentlink.families import param
        def run(s, name, args):
            t = next(t for t in param.tools(s) if t.name == name)
            try:
                return ["ok", t.fn(json.loads(json.dumps(args)))]
            except ToolError as e:
                return ["refused", e.code, e.message]
    ''') + "\n".join(textwrap.dedent(b) for b in parts)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


BIKE = '''
    s = fc.Session(tempfile.mkdtemp())
    chain = fc.body(s, "Chainring")
    csk = fc.sketch(s, chain)                                                                    # Name Sketch
    csk.__dict__["Label"] = "RingSketch"
    fc.feature(s, chain, "Pad", "Ring", Profile=csk, Length=4.0)                                 # Name Pad, label Ring
    frame = fc.body(s, "Frame")
    fsk = fc.sketch(s, frame)                                                                    # Name Sketch001
    fsk.__dict__["Label"] = "FrameSketch"
    fpad = fc.feature(s, frame, "Pad", "Pad", Profile=fsk, Length=20.0)                          # Name Pad001, label Pad
    fc.params(s, [("tube", "30 mm")])
    fc.settle(s)
'''


# ---- finding 8: a name that is two objects -------------------------------------------------

class BindByName(unittest.TestCase):
    def test_owners_reads_the_objects_an_expression_names(self):
        self.assertEqual(exprs.owners("Pad.Length / 2 + <<Pad>>.Width"), [("Pad", "Length")])
        self.assertEqual(exprs.owners("Sketch.Constraints.width * 2.5 mm"), [("Sketch", "Constraints")])
        self.assertEqual(exprs.owners("Doc#Pad.Length + 'a.b' + tube"), [])

    def test_a_target_that_is_a_name_and_another_label_is_refused(self):
        got = child(BIKE, '''
            out = {"r": run(s, "param_bind", {"target": "Pad.Length", "expression": "Params.tube"}),
                   "bound": [o.Name for o in s.doc.Objects if o.__dict__.get("ExpressionEngine")]}
            print(json.dumps(out))
        ''')
        r = got["r"]
        self.assertEqual(r[:2], ["refused", "invalid_input"], r)
        self.assertIn("'Pad' names two objects", r[2])
        self.assertIn("the name of Pad, label Ring, in Chainring and the label of Pad001, label Pad, in Frame", r[2])
        self.assertIn("<<Ring>>.Length (Pad", r[2])
        self.assertIn("<<Pad>>.Length (Pad001", r[2])
        self.assertEqual(got["bound"], [])          # nothing bound

    def test_the_label_form_binds_the_one_meant(self):
        got = child(BIKE, '''
            r = run(s, "param_bind", {"target": "<<Pad>>.Length", "expression": "Params.tube"})
            out = {"r": r[0], "engine": {o.Name: o.__dict__.get("ExpressionEngine") for o in s.doc.Objects if o.__dict__.get("ExpressionEngine")}}
            out["missing"] = run(s, "param_bind", {"target": "<<Nope>>.Length", "expression": "Params.tube"})
            print(json.dumps(out))
        ''')
        self.assertEqual(got["r"], "ok")
        self.assertEqual(got["engine"], {"Pad001": [["Length", "Params.tube"]]})
        self.assertEqual(got["missing"][:2], ["refused", "not_found"])

    def test_an_expression_that_names_two_objects_is_refused(self):
        got = child(BIKE, '''
            print(json.dumps(run(s, "param_bind", {"target": "Ring.Length", "expression": "Pad.Length / 2"})))
        ''')
        self.assertEqual(got[0], "refused", got)
        self.assertIn("expression Pad.Length", got[2])
        self.assertIn("<<Pad>>.Length (Pad001", got[2])

    def test_a_default_name_in_another_body_is_refused_when_the_target_body_has_one_like_it(self):
        got = child(BIKE, '''
            out = {"other": run(s, "param_bind", {"target": "Ring.Length", "expression": "Sketch001.Constraints.width"}),
                   "label": run(s, "param_bind", {"target": "Ring.Length", "expression": "<<FrameSketch>>.Constraints.width"})}
            print(json.dumps(out))
        ''')
        r = got["other"]
        self.assertEqual(r[0], "refused", r)
        self.assertIn("Sketch001 is Sketch001, label FrameSketch, in Frame, but Ring is in Chainring, which has its own", r[2])
        self.assertIn("<<RingSketch>>.Constraints (Sketch", r[2])
        self.assertIn("or <<FrameSketch>>.Constraints to keep the one in Frame", r[2])
        self.assertEqual(got["label"][0], "ok", got["label"])     # said by its label: taken

    def test_plain_names_still_work(self):
        got = child('''
            s = fc.Session(tempfile.mkdtemp())
            b = fc.body(s)
            fc.feature(s, b, "Pad", Profile=fc.sketch(s, b), Length=10.0)
            fc.params(s, [("tube", "30 mm")])
            fc.settle(s)
            out = [run(s, "param_bind", {"target": "Pad.Length", "expression": "tube"})[0],
                   run(s, "param_bind", {"target": "Pad.Length", "expression": "Params.tube / 2"})[0],
                   run(s, "param_bind", {"target": "Pad.Length", "expression": "Sketch.Placement.Base.x + 1 mm"})[0]]
            print(json.dumps(out))
        ''')
        self.assertEqual(got, ["ok", "ok", "ok"])


# ---- finding 7: an additive step that leaves the body invalid ------------------------------

class V:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)


class Cyl:
    """Part's cylinder surface, as fusehint reads it."""

    def __init__(self, centre, axis, radius):
        self.Center, self.Axis, self.Radius = V(*centre), V(*axis), radius


Cyl.__name__ = "Cylinder"


class Face:
    """A cylinder face of a tube along x from x0 to x1 at y, z = 0: inner
    (normal to the axis) or outer."""

    def __init__(self, x0, x1, r, inner, along=(1, 0, 0)):
        self.Surface = Cyl((0, 0, 0), along, r)
        self.x0, self.x1, self.r, self.inner, self.along = x0, x1, r, inner, along
        self.ParameterRange = (0.0, 6.283185, x0, x1)

    def valueAt(self, u, v):
        import math

        a = self.along
        if a == (1, 0, 0):
            return V(v, self.r * math.cos(u), self.r * math.sin(u))
        return V(self.r * math.cos(u), v, self.r * math.sin(u))

    def normalAt(self, u, v):
        p = self.valueAt(u, v)
        a = self.along
        rad = (0, p.y, p.z) if a == (1, 0, 0) else (p.x, 0, p.z)
        s = -1 if self.inner else 1
        return V(*(s * c / self.r for c in rad))


class Box:
    """A solid: a box, with faces of its own."""

    def __init__(self, lo, hi, faces=()):
        self.lo, self.hi, self.Faces = lo, hi, list(faces)
        self.Solids = [self]

    def isInside(self, p, tol, on):
        return all(self.lo[i] - tol <= c <= self.hi[i] + tol for i, c in enumerate((p.x, p.y, p.z)))


class Feat:
    def __init__(self, type_, name, label=None, **kw):
        self.TypeId, self.Name, self.Label = type_, name, label or name
        self.__dict__.update(kw)


class FuseHint(unittest.TestCase):
    def bike(self, base_faces):
        tubes = Feat("PartDesign::Pipe", "Pipe", "Tubes", Shape=Box((-60, -60, -60), (60, 60, 60), base_faces))
        lug = Feat("PartDesign::Pad", "Pad003", "Lug", BaseFeature=tubes, AddSubShape=Box((-10, -10, -10), (10, 10, 10)))
        return Feat("PartDesign::Body", "Body", "Frame", Tip=lug), lug

    def test_tube_ends_that_meet_inside_the_new_solid_are_named(self):
        # two tubes, 4 mm bore, both end at x = 0 / y = 0: inside the 20 mm lug
        faces = [Face(-60, 0, 5, False), Face(-60, 0, 4, True), Face(0, 60, 5, False, (0, 1, 0)), Face(0, 60, 4, True, (0, 1, 0))]
        body, lug = self.bike(faces)
        h = fusehint.for_invalid(body)
        self.assertEqual(h["feature"], "Lug")
        self.assertEqual(h["kind"], "pad")
        self.assertEqual([b["face"] for b in h["bores"]], ["Face2", "Face4"])
        self.assertTrue(all(b["of"] == "Tubes" for b in h["bores"]))
        self.assertIn("end the tubes at the shell surface, or cut the bore after the fuse", h["todo"])
        self.assertIn('body_check { body: "Frame" }', h["todo"])
        self.assertIn("2 tube bores (Tubes Face2, Face4) end inside the new solid of Lug", h["line"])

    def test_no_bore_inside_gives_the_plain_cause(self):
        # blind QA 26 Nov: no tube bore found, so no tube rule (a crank has no tubes)
        faces = [Face(-60, -30, 4, True)]      # a bore that ends far from the lug
        body, _ = self.bike(faces)
        h = fusehint.for_invalid(body)
        self.assertEqual(h["bores"], [])
        self.assertNotIn("tube", h["todo"])
        self.assertEqual(h["todo"], 'Lug (pad) left the shape invalid: the sketch can have loops that cross or touch (sketch_state names them); '
                                    'history_undo, change the sketch, then body_check { body: "Frame" } to confirm')
        self.assertEqual(h["line"], "after Lug (pad)")
        body.Shape = Box((0, 0, 0), (1, 1, 1))
        body.Shape.Solids = [1, 2]
        self.assertTrue(fusehint.for_invalid(body)["todo"].startswith("Lug made 2 solids: the sketch can have loops that cross or touch"))

    def test_part_fuse_of_hollow_tubes(self):
        a = Feat("Part::Feature", "TubeA", Shape=Box((-60, -5, -5), (0, 5, 5), [Face(-60, 0, 4, True)]))
        b = Feat("Part::Feature", "TubeB", Shape=Box((-5, 0, -5), (5, 60, 5), [Face(0, 60, 4, True, (0, 1, 0))]))
        fuse = Feat("Part::MultiFuse", "Fusion", "Joint", Shapes=[a, b])
        h = fusehint.for_invalid(fuse)
        self.assertEqual(h["kind"], "fuse")
        self.assertEqual(len(h["bores"]), 2)
        self.assertIn('body_check { body: "Joint" }', h["todo"])

    def test_other_steps_get_nothing(self):
        body = Feat("PartDesign::Body", "Body", "Frame", Tip=Feat("PartDesign::Fillet", "Fillet", Base=None))
        self.assertIsNone(fusehint.for_invalid(body))
        self.assertIsNone(fusehint.for_invalid(Feat("Part::Cut", "Cut")))
        self.assertIsNone(fusehint.for_invalid(None))

    def test_an_error_of_an_additive_step(self):
        faces = [Face(-60, 0, 5, False), Face(-60, 0, 4, True), Face(0, 60, 5, False, (0, 1, 0)), Face(0, 60, 4, True, (0, 1, 0))]
        _, lug = self.bike(faces)
        self.assertIn("cut the bore after the fuse", fusehint.for_error(lug, "Resulting shape is not a valid solid"))
        plain = fusehint.for_error(Feat("PartDesign::Pad", "Pad"), "Resulting shape is not a valid solid")
        self.assertNotIn("tube", plain)
        self.assertIn("loops that cross or touch (sketch_state names them)", plain)
        fuse = fusehint.for_error(Feat("Part::MultiFuse", "Fusion", Shapes=[]), "Resulting shape is not a valid solid")
        self.assertEqual(fuse, "Fusion (fuse) left the shape invalid: history_undo, change it, then body_check says where the shape is broken")
        self.assertIsNone(fusehint.for_error(Feat("PartDesign::Pad", "Pad"), "Sketch is not closed"))
        self.assertIsNone(fusehint.for_error(Feat("PartDesign::Fillet", "Fillet"), "Resulting shape is invalid"))

    def test_health_uses_it_only_on_an_invalid_shape(self):
        src = open(os.path.join(ROOT, "agentlink", "health.py"), encoding="utf-8").read()
        at = src.index("fusehint.for_invalid(")
        self.assertLess(src.rindex("if not valid:", 0, at), at)      # only after isValid said no
        self.assertEqual(src.count("fusehint.for_invalid("), 1)
        self.assertIn("fusehint.for_error(", src)


if __name__ == "__main__":
    unittest.main()
