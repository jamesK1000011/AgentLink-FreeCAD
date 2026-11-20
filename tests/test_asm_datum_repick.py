# SPDX-License-Identifier: LGPL-2.1-or-later
# asm_joint after the bicycle test drive of 20 Nov (a Part boolean on a part
# broke the joints on its faces), without FreeCAD (the data tests' stand-in
# FreeCAD in a child process):
#   A  a joint end on a datum inside the part (an LCS, a datum plane, line or
#      point): the reference is [part, ["LCS.", "LCS."]], as FreeCAD 1.1's
#      Assembly stores a whole datum (empty element); the joint sits on the
#      datum's origin along its z axis;
#   B  an end picked by a query keeps the query on the joint
#      (AgentLinkQuery); the health check after a changing call finds an end
#      whose face is gone or renumbered, runs the query again and re-points
#      the joint ("re-picked Face1 -> Face5"), or keeps it broken and says why.
import json
import os
import subprocess
import sys
import textwrap
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)


def child(body):
    """body run in a Python of its own after the assembly stand-in is in;
    what it prints last, as JSON."""
    code = textwrap.dedent(f'''
        import json, sys, tempfile
        sys.path[:0] = [{ROOT!r}, {TESTS!r}]
        import _dataasm_standin
        fc = _dataasm_standin.install()
        from agentlink.protocol import ToolError
        from agentlink.families import assembly as A
        fc.fc.GuiUp = False
        fc.state["solves"] = 0
        fc.state.setdefault("flags", {{}})

        def run(s, name, args):
            t = next(t for t in A.tools(s) if t.name == name)
            try:
                return ["ok", t.fn(json.loads(json.dumps(args)))]
            except ToolError as e:
                return ["refused", e.code, e.message]

        def scene(base_type="PartDesign::Body"):
            s = fc.Session(tempfile.mkdtemp())
            base = fc.a_part("Base", (0, 0, 0), (10, 10, 10), name="Base", type_=base_type)
            fc.a_part("Lid", (0, 0, 10), (10, 10, 12), name="Lid")
            a = fc.an_object("Assembly::AssemblyObject", "Assembly", "Assembly")
            a.__dict__["Type"] = "Assembly"
            jg = fc.into(a, fc.an_object("Assembly::JointGroup", "Joints"))
            for p in ("Base", "Lid"):
                fc.into(a, fc.doc().getObject(p))
            g = fc.into(jg, fc.an_object("App::FeaturePython", "GroundedJoint"))
            g.__dict__["ObjectToGround"] = base
            return s, a, base
    ''') + textwrap.dedent(body)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


class DatumEnds(unittest.TestCase):
    def test_a_joint_on_an_lcs_in_the_body(self):
        got = child('''
            s, asm, base = scene()
            lcs = fc.an_object("PartDesign::CoordinateSystem", "LCS", "Rear LCS", kinds=("App::LocalCoordinateSystem",))
            lcs.__dict__["Placement"] = fc.Placement(fc.fc.Vector(2, 3, 10), fc.Rotation())
            fc.into(base, lcs)
            out = {}
            del fc.trace[:]
            out["by label"] = run(s, "asm_joint", {"kind": "fixed", "a": {"part": "Base", "element": "Rear LCS"}, "b": {"part": "Lid", "element": "Face2"}})
            out["trace"] = [t for t in fc.trace if t.startswith("setJointConnectors") and "LCS" in t]
            out["by datum"] = run(s, "asm_joint", {"kind": "fixed", "a": {"part": "Base", "datum": "LCS"}, "b": {"part": "Lid", "element": "Face2"}})
            out["unknown"] = run(s, "asm_joint", {"kind": "fixed", "a": {"part": "Base", "element": "Front LCS"}, "b": {"part": "Lid", "element": "Face2"}})
            out["no datums"] = run(s, "asm_joint", {"kind": "fixed", "a": {"part": "Base", "element": "Face1"}, "b": {"part": "Lid", "element": "Spot"}})
            j = [o for o in fc.doc().Objects if o.Name == "Fixed"][0]
            out["label"] = A.ref_label(fc.doc(), j.Reference1)
            part, d, sub = A.ref_element(fc.doc(), j.Reference1)
            ax = A.joint_axis(d)
            out["axis"] = [list(ax[0]), list(ax[1])]
            out["sub"] = sub
            out["old form"] = A.ref_label(fc.doc(), [asm, ["Base.LCS.", "Base.LCS."]])
            out["kept"] = "AgentLinkQuery" in j.PropertiesList
            print(json.dumps(out, default=str))
        ''')
        ok = got["by label"]
        self.assertEqual(ok[0], "ok", ok)
        self.assertEqual(ok[1]["a"], "Base.Rear LCS")
        self.assertEqual(ok[1]["at"]["a"], [2.0, 3.0, 10.0])
        self.assertNotIn("queryKept", ok[1])
        self.assertTrue(any("[<Base>, ['LCS.', 'LCS.']]" in t for t in got["trace"]), got["trace"])
        self.assertEqual(got["by datum"][0], "ok", got["by datum"])
        self.assertEqual(got["unknown"][:2], ["refused", "invalid_input"])
        self.assertIn("Its datums: Rear LCS", got["unknown"][2])
        self.assertEqual(got["no datums"][:2], ["refused", "invalid_input"])
        self.assertIn("Lid (Part::Feature) holds no LCS or datum", got["no datums"][2])
        self.assertIn("App::Part", got["no datums"][2])
        self.assertEqual(got["label"], "Base.Rear LCS")
        self.assertEqual(got["axis"], [[2.0, 3.0, 10.0], [0.0, 0.0, 1.0]])
        self.assertEqual(got["sub"], "LCS.")
        self.assertEqual(got["old form"], "Base.Rear LCS")
        self.assertFalse(got["kept"])

    def test_a_datum_in_an_app_part_is_named_from_the_part_down(self):
        got = child('''
            s = fc.Session(tempfile.mkdtemp())
            box = fc.an_object("App::Part", "Part", "Frame")
            body = fc.into(box, fc.an_object("PartDesign::Body", "Body", "Tube"))
            lcs = fc.into(body, fc.an_object("PartDesign::CoordinateSystem", "LCS", "Head LCS"))
            other = fc.into(box, fc.an_object("PartDesign::Plane", "DatumPlane", "Head LCS"))
            out = {"path": A.datum_sub(box, "Tube.Head LCS", "a.element"), "plane": A.datum_sub(box, "DatumPlane", "a.element")}
            try:
                A.datum_sub(box, "Head LCS", "a.element")
            except ToolError as e:
                out["two"] = e.message
            print(json.dumps(out))
        ''')
        self.assertEqual(got["path"], "Body.LCS.")
        self.assertEqual(got["plane"], "DatumPlane.")
        self.assertIn("2 datums of Frame are named Head LCS", got["two"])


class StoredQuery(unittest.TestCase):
    def test_a_query_is_kept_and_a_renumbered_face_is_picked_again(self):
        got = child('''
            s, asm, base = scene("Part::Feature")
            out = {}
            out["joint"] = run(s, "asm_joint", {"kind": "fixed", "a": {"part": "Base", "element": {"kind": "face", "normal": [0, 0, 1]}}, "b": {"part": "Lid", "element": "Face2"}})
            j = [o for o in fc.doc().Objects if o.Name == "Fixed"][0]
            note = json.loads(j.AgentLinkQuery)
            out["note"] = sorted(note)
            out["query"] = note["Reference1"]["query"]
            # nothing changed: no line
            out["calm"] = A.repick(fc.doc(), asm)
            # a Part boolean gives the base a new shape: Face1 is now another face
            base.__dict__["Shape"] = fc.solid("Base cut", (0, 0, 0), (10, 10, 10), faces=9)
            base.__dict__["box0"] = base.Shape.box
            A.requery = lambda part, q: [("Face5", part.Shape.Faces[4])]
            tool = type("T", (), {"group": "part", "name": "part_boolean"})()
            out["health"] = A._health(s, tool, [])
            out["ref"] = [j.Reference1[0].Name, list(j.Reference1[1])]
            out["now"] = json.loads(j.AgentLinkQuery)["Reference1"]["element"]
            # the face gone ("?" as FreeCAD marks a lost element), and the query finds nothing
            j.__dict__["Reference1"] = [base, ["?Face5", "?Face5"]]
            A.requery = lambda part, q: []
            out["nothing"] = A.repick(fc.doc(), asm)
            # an end given by name has no query to run
            j.__dict__["Reference2"] = [fc.doc().getObject("Lid"), ["?Face2", "?Face2"]]
            out["no query"] = [x["line"] for x in A.repick(fc.doc(), asm)]
            print(json.dumps(out, default=str))
        ''')
        self.assertEqual(got["joint"][0], "ok", got["joint"])
        self.assertEqual(got["joint"][1]["queryKept"], ["a"])
        self.assertEqual(got["note"], ["Reference1"])
        self.assertEqual(got["query"]["normal"], [0.0, 0.0, 1.0])
        self.assertEqual(got["calm"], [])
        lines = [x["line"] for x in got["health"]]
        self.assertIn("Fixed: re-picked Face1 -> Face5 on Base (stored query)", lines)
        self.assertTrue(any(ln.startswith("Assembly: assembly") for ln in lines), lines)  # the solver's line follows a re-pick
        self.assertEqual(got["ref"], ["Base", ["Face5", "Face5"]])
        self.assertEqual(got["now"], "Face5")
        self.assertEqual(len(got["nothing"]), 1)
        self.assertTrue(got["nothing"][0]["red"])
        self.assertIn("Base.Face5 is broken; not picked again: the stored query finds nothing now", got["nothing"][0]["line"])
        self.assertIn("pd_datum", got["nothing"][0]["todo"])
        self.assertIn("Fixed: Lid.Face2 is broken, and the joint has no stored query to pick it again", got["no query"])

    def test_a_part_moved_by_a_solve_takes_its_query_along(self):
        got = child('''
            s, asm, base = scene("Part::Feature")
            lid = fc.doc().getObject("Lid")
            run(s, "asm_joint", {"kind": "fixed", "a": {"part": "Base", "element": "Face1"}, "b": {"part": "Lid", "element": {"kind": "face", "near": [5, 5, 10]}}})
            j = [o for o in fc.doc().Objects if o.Name == "Fixed"][0]
            # the solver moves the lid 5 mm up: its shape and its box with it
            lid.Placement = fc.Placement(fc.fc.Vector(0, 0, 5), fc.Rotation())
            lid.Shape.Placement = fc.Placement(fc.fc.Vector(0, 0, 5), fc.Rotation())
            for f in lid.Shape.Faces:  # the stand-in's faces keep their own box
                f.box = f.box.moved(fc.fc.Vector(0, 0, 5))
            A.requery = lambda part, q: (_ for _ in ()).throw(AssertionError("no re-pick for a move"))
            out = {"lines": A.repick(fc.doc(), asm)}
            note = json.loads(j.AgentLinkQuery)["Reference2"]
            out["near"], out["frame"] = note["query"]["near"], note["frame"][:3]
            # a Part boolean bakes the shape where it stands: placement none, faces where they were
            lid.Shape.Placement = fc.Placement()
            out["baked"] = A.repick(fc.doc(), asm)
            note = json.loads(j.AgentLinkQuery)["Reference2"]
            out["near2"], out["frame2"] = note["query"]["near"], note["frame"][:3]
            print(json.dumps(out, default=str))
        ''')
        self.assertEqual(got["lines"], [])
        self.assertEqual(got["near"], [5.0, 5.0, 15.0])
        self.assertEqual(got["frame"], [0.0, 0.0, 5.0])
        self.assertEqual(got["baked"], [])
        self.assertEqual(got["near2"], [5.0, 5.0, 15.0])  # the query stays where the face is
        self.assertEqual(got["frame2"], [0.0, 0.0, 0.0])

    def test_the_choice_of_a_re_pick(self):
        got = child('''
            class El:
                def __init__(self, d):
                    self.d = d
                def distToShape(self, v):
                    return (self.d, [], [])
            A.Part.Vertex = lambda p: p
            out = {
                "one": A.repick_choice([("Face3", El(0))], {}),
                "none": A.repick_choice([], {}),
                "many": A.repick_choice([("Face3", El(0)), ("Face4", El(1))], {}),
                "nearest": A.repick_choice([("Face3", El(2.0)), ("Face4", El(0.5))], {"near": [0, 0, 0]}),
                "equal": A.repick_choice([("Face3", El(1.0)), ("Face4", El(1.0))], {"near": {"point": [0, 0, 0]}}),
            }
            # the query runs on the part's shape as it is now (shape_query's own filter)
            from agentlink.families import measure as M
            M.filter_shape = lambda shape, q: ("face", [(7, "el7", {"ref": "Face7"})])
            out["requery"] = A.requery(fc.doc().getObject("Lid") if fc.doc().getObject("Lid") else type("P", (), {"Shape": None, "TypeId": "Part::Feature"})(), {"kind": "face"})
            print(json.dumps(out, default=str))
        ''')
        self.assertEqual(got["one"], ["Face3", None])
        self.assertEqual(got["none"], [None, "the stored query finds nothing now"])
        self.assertIn("finds 2 (Face3, Face4) and has no near point", got["many"][1])
        self.assertEqual(got["nearest"], ["Face4", None])
        self.assertEqual(got["equal"], [None, "the stored query finds two equal matches (Face3, Face4)"])
        self.assertEqual(got["requery"], [["Face7", "el7"]])


class Card(unittest.TestCase):
    def test_the_card_says_lcs_first(self):
        with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            e = json.load(f)["entries"]["asm_joint"]
        for words in ("Put joints on LCS markers, not on faces that a boolean makes", "queryKept", "re-picked Face12 -> Face15", "two equal faces"):
            self.assertIn(words, e["description"])
        self.assertIn("a datum (\"LCS\", { datum })", e["inputSchema"]["properties"]["a"]["description"])


if __name__ == "__main__":
    unittest.main()
