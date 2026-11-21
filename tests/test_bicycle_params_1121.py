# SPDX-License-Identifier: LGPL-2.1-or-later
# Bicycle design runs of 20 Nov 2026 on FreeCAD 1.1.3, the parameter, body
# and attachment findings, without FreeCAD (the data tests' stand-in FreeCAD
# in a child process):
#   1  param_bind on an LCS: other objects are written by label
#      (<<Dims>>.offset, rewritten in the answer); a value that FreeCAD does
#      not apply after the recompute is refused and the expression removed;
#   2  param_bind on Placement of an attached object: Placement.Base.* and
#      Placement.Rotation.Angle bind AttachmentOffset (redirected), other
#      Placement paths are refused with the AttachmentOffset to bind;
#   3  param_bind expression null or "" clears it: cleared, old;
#   4  a body is found by its Name before a label, and by a label it had
#      before object_rename;
#   5  pd_binder of a document-level source sets Relative false (relative:
#      true keeps FreeCAD's default);
#   6  object_set Placement on an attached datum sets its AttachmentOffset
#      (redirected);
#   7  a changing call that touches an object a joint names solves the
#      assembly again in the health step.
import json
import os
import subprocess
import sys
import textwrap
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)
sys.path.insert(0, ROOT)


def child(standin, *parts):
    code = textwrap.dedent(f'''
        import json, sys, tempfile
        sys.path[:0] = [{ROOT!r}, {TESTS!r}]
        import {standin}
        fc = {standin}.install()
        from agentlink.protocol import ToolError
        def run(mod, s, name, args):
            t = next(t for t in mod.tools(s) if t.name == name)
            try:
                return ["ok", t.fn(json.loads(json.dumps(args)))]
            except ToolError as e:
                return ["refused", e.code, e.message]
    ''') + "\n".join(textwrap.dedent(b) for b in parts)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


# A Frame body with a placed LCS (attached to the body's origin, FlatFace) and a
# variable set Dims (object name VarSet).
FRAME = '''
    from agentlink.families import param, doc as D, feature_more as FM
    s = fc.Session(tempfile.mkdtemp())
    s.meta = {}
    b = fc.body(s, "Frame")
    lcs = s.doc.new("Part::LocalCoordinateSystem", "LCS")
    lcs.__dict__.update(Label="Head LCS", MapMode="FlatFace", AttachmentSupport=[(b.Origin, "")],
                        AttachmentOffset=fc.Placement(fc.Vec(0, 0, 5)), Placement=fc.Placement(fc.Vec(0, 0, 5)),
                        types={"AttachmentOffset": "App::PropertyPlacement", "Placement": "App::PropertyPlacement"})
    b._place(lcs)
    fc.varset(s, "Dims", offset=("App::PropertyLength", (12, "mm")))
    fc.settle(s)
    Obj = type(lcs)
    def evaluates(v):
        Obj.evalExpression = lambda self, e: v
    def applies(on):
        first = Obj.setExpression
        def set_(self, path, e):
            first(self, path, e)
            if on and e is not None and path == "AttachmentOffset.Base.z":
                self.__dict__["AttachmentOffset"] = fc.Placement(fc.Vec(0, 0, 12))
        Obj.setExpression = set_
'''


class LcsByLabel(unittest.TestCase):
    def test_rewritten_by_label_and_read_back(self):
        got = child("_datask2_standin", FRAME, '''
            evaluates(type("Q", (), {"Value": 12.0})())                # a Quantity as FreeCAD's evalExpression gives it
            out = {"missed": run(param, s, "param_bind", {"target": "Head LCS.AttachmentOffset.Base.z", "expression": "VarSet.offset"}),
                   "engine": lcs.__dict__.get("ExpressionEngine")}
            applies(True)
            out["ok"] = run(param, s, "param_bind", {"target": "Head LCS.AttachmentOffset.Base.z", "expression": "Dims.offset"})
            print(json.dumps(out, default=str))
        ''')
        r = got["missed"]
        self.assertEqual(r[:2], ["refused", "failed"], r)
        self.assertIn("reads 5.0 after the recompute, not 12.0", r[2])
        self.assertIn("<<Label>>.prop", r[2])
        self.assertFalse(got["engine"])                       # removed
        ok = got["ok"]
        self.assertEqual(ok[0], "ok", ok)
        self.assertEqual(ok[1]["expression"], "<<Dims>>.offset")
        self.assertEqual(ok[1]["rewritten"]["from"], "VarSet.offset")
        self.assertEqual(ok[1]["rewritten"]["to"], "<<Dims>>.offset")

    def test_sub_names_and_said(self):
        got = child("_datask2_standin", FRAME, '''
            from agentlink.families import picks
            pad = fc.feature(s, b, "Pad", "Pad", Profile=fc.sketch(s, b), Length=10.0)
            out = {"lcs": list(picks.doc_refs_said(s.doc, lcs, "VarSet.offset + Pad.Length")),
                   "pad": list(picks.doc_refs_said(s.doc, pad, "VarSet.offset")),
                   "attached": [picks.attached(lcs), picks.attached(pad)]}
            print(json.dumps(out, default=str))
        ''')
        self.assertEqual(got["lcs"][0], "<<Dims>>.offset + <<Pad>>.Length")
        self.assertEqual(got["pad"][0], "VarSet.offset")         # not an LCS: kept
        self.assertEqual(got["attached"], [True, False])


class AttachedPlacement(unittest.TestCase):
    def test_redirected_and_refused(self):
        got = child("_datask2_standin", FRAME, '''
            applies(False)
            out = {"z": run(param, s, "param_bind", {"target": "Head LCS.Placement.Base.z", "expression": "<<Dims>>.offset"}),
                   "engine": lcs.__dict__.get("ExpressionEngine"),
                   "axis": run(param, s, "param_bind", {"target": "Head LCS.Placement.Rotation.Axis.x", "expression": "1"})}
            print(json.dumps(out, default=str))
        ''')
        z = got["z"]
        self.assertEqual(z[0], "ok", z)
        self.assertEqual(z[1]["redirected"]["to"], "AttachmentOffset.Base.z")
        self.assertIn("MapMode FlatFace", z[1]["redirected"]["why"])
        self.assertEqual(got["engine"], [["AttachmentOffset.Base.z", "<<Dims>>.offset"]])
        a = got["axis"]
        self.assertEqual(a[:2], ["refused", "invalid_input"], a)
        self.assertIn("Placement is computed (attached, MapMode FlatFace): bind AttachmentOffset.Rotation.Axis.x instead", a[2])


class Clear(unittest.TestCase):
    def test_null_and_empty_clear(self):
        got = child("_datask2_standin", FRAME, '''
            pad = fc.feature(s, b, "Pad", "Pad", Profile=fc.sketch(s, b), Length=10.0)
            fc.params(s, [("tube", "30 mm")])
            fc.bound(pad, ".Length", "Params.tube")                 # as FreeCAD can keep the path
            out = {"empty": run(param, s, "param_bind", {"target": "Pad.Length", "expression": ""}),
                   "engine": pad.__dict__.get("ExpressionEngine"),
                   "again": run(param, s, "param_bind", {"target": "Pad.Length", "expression": None})}
            print(json.dumps(out, default=str))
        ''')
        e = got["empty"]
        self.assertEqual(e[0], "ok", e)
        self.assertTrue(e[1]["cleared"])
        self.assertEqual(e[1]["old"], "Params.tube")
        self.assertEqual(got["engine"], [])
        self.assertEqual(got["again"][0], "ok")
        self.assertFalse(got["again"][1]["cleared"])
        self.assertIn("Nothing was bound", got["again"][1]["note"])


class BodyByName(unittest.TestCase):
    def test_name_first_and_a_former_label(self):
        got = child("_datask2_standin", '''
            from agentlink.families import doc as D, pd_common as pc, picks
            s = fc.Session(tempfile.mkdtemp())
            s.meta = {}
            master = fc.body(s, "Master")                          # Name Master
            frame = fc.body(s, "Body")                             # Name Body
            frame.__dict__["Label"] = "FrameW"
            other = fc.body(s, "Other")
            other.__dict__["Label"] = "Master Copy"
            fc.settle(s)
            out = {"rename": run(D, s, "object_rename", {"object": "FrameW", "label": "Frame"})[0],
                   "old": pc.pd_body(s.doc, "FrameW").Name, "name": pc.pd_body(s.doc, "Body").Label,
                   "find": picks.find(s.doc, "FrameW").Name}
            other.__dict__["Label"] = "Body"                       # a label that is another body's Name
            out["first"] = pc.pd_body(s.doc, "Body").Name
            print(json.dumps(out))
        ''')
        self.assertEqual(got["rename"], "ok")
        self.assertEqual(got["old"], "Body")
        self.assertEqual(got["name"], "Frame")
        self.assertEqual(got["find"], "Body")
        self.assertEqual(got["first"], "Body")


class BinderRelative(unittest.TestCase):
    def test_document_level_source_is_not_relative(self):
        got = child("_datask2_standin", FRAME, '''
            Doc = type(s.doc)
            first_new = Doc.new
            def new(self, t, name=None, **kw):
                o = first_new(self, t, name, **kw)
                if t.endswith("SubShapeBinder"):
                    o.__dict__["Relative"] = True
                return o
            Doc.new = new
            line = s.doc.new("Part::Line", "Line")
            line.__dict__.update(Label="Fork line", Shape=fc.Shape("edge", [fc.Vec(0, 0, 0), fc.Vec(0, 0, 100)]))
            fork = fc.body(s, "Fork")
            fc.settle(s)
            out = {"doc": run(FM, s, "pd_binder", {"body": "Fork", "from": "Fork line"}),
                   "kept": run(FM, s, "pd_binder", {"body": "Fork", "from": "Fork line", "relative": True})}
            print(json.dumps(out, default=str))
        ''')
        d = got["doc"]
        self.assertEqual(d[0], "ok", d)
        self.assertIs(d[1]["relative"], False)
        self.assertIn("at document level", d[1]["relativeNote"])
        k = got["kept"]
        self.assertEqual(k[0], "ok", k)
        self.assertIs(k[1]["relative"], True)


class DatumPlacement(unittest.TestCase):
    def test_object_set_placement_sets_the_offset(self):
        got = child("_datask2_standin", FRAME, '''
            out = {"set": run(D, s, "object_set", {"object": "Head LCS", "values": {"Placement": {"at": [1, 2, 3]}}}),
                   "offset": list(lcs.AttachmentOffset.Base),
                   "both": run(D, s, "object_set", {"object": "Head LCS", "values": {"Placement": {"at": [1, 2, 3]}, "AttachmentOffset": {"at": [0, 0, 0]}}})}
            print(json.dumps(out, default=str))
        ''')
        r = got["set"]
        self.assertEqual(r[0], "ok", r)
        self.assertEqual(r[1]["redirected"]["Placement"]["to"], "AttachmentOffset")
        self.assertEqual(r[1]["set"]["AttachmentOffset"]["to"]["at"], [1.0, 2.0, 3.0])
        self.assertEqual(got["offset"], [1.0, 2.0, 3.0])
        self.assertEqual(got["both"][:2], ["refused", "invalid_input"])


class JointFollows(unittest.TestCase):
    def test_a_changed_lcs_solves_the_assembly(self):
        got = child("_dataasm_standin", '''
            from agentlink.families import assembly as A
            fc.fc.GuiUp = False
            fc.state["solves"] = 0
            fc.state.setdefault("flags", {})
            s = fc.Session(tempfile.mkdtemp())
            base = fc.a_part("Base", (0, 0, 0), (10, 10, 10), name="Base", type_="PartDesign::Body")
            lid = fc.a_part("Lid", (0, 0, 10), (10, 10, 12), name="Lid")
            a = fc.an_object("Assembly::AssemblyObject", "Assembly", "Assembly")
            a.__dict__["Type"] = "Assembly"
            jg = fc.into(a, fc.an_object("Assembly::JointGroup", "Joints"))
            for p in ("Base", "Lid"):
                fc.into(a, fc.doc().getObject(p))
            g = fc.into(jg, fc.an_object("App::FeaturePython", "GroundedJoint"))
            g.__dict__["ObjectToGround"] = base
            lcs = fc.into(base, fc.an_object("PartDesign::CoordinateSystem", "LCS", "Rear LCS", kinds=("App::LocalCoordinateSystem",)))
            j = fc.into(jg, fc.an_object("App::FeaturePython", "Fixed"))
            j.__dict__.update(Reference1=[base, ["LCS.", "LCS."]], Reference2=[lid, ["Face2", "Face2"]])
            tool = type("T", (), {"group": "doc", "name": "object_set"})()
            other = fc.an_object("Part::Feature", "Loose", "Loose")
            out = {"names": sorted(A.joined_names(fc.doc(), a))}
            out["calm"] = A._health(s, tool, [other])
            out["calm solves"] = fc.state["solves"]
            out["lcs"] = A._health(s, tool, [lcs])
            out["solves"] = fc.state["solves"]
            print(json.dumps(out, default=str))
        ''')
        self.assertEqual(got["names"], ["Base", "LCS", "Lid"])
        self.assertEqual(got["calm"], [])
        self.assertEqual(got["calm solves"], 0)
        self.assertEqual(got["solves"], 1)
        self.assertIn("Assembly: assembly solved again: the parts joined to Rear LCS follow it (no part moved)", [x["line"] for x in got["lcs"]])


if __name__ == "__main__":
    unittest.main()
