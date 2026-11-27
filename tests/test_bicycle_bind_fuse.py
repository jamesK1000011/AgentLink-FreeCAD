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

from agentlink import exprs  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
