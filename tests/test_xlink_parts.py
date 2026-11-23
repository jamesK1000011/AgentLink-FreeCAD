# SPDX-License-Identifier: LGPL-2.1-or-later
# One file for each part: link_make links an object of another .FCStd
# (FreeCAD's XLink), and the assembly takes that link as a part, without
# FreeCAD (the data tests' stand-ins, in a child process):
#   A  link_make { to: "Doc#Object" } and { file, to }: the link's target is
#      the object of the other document; the answer gives file, relative and
#      check; an unsaved other document is refused ("doc_save it first"); a
#      file not open is opened in the background and the agent's document
#      stays the active one;
#   B  doc_save's check of the saved file: a link path that finds no file
#      (FreeCAD issue 33468) is named;
#   C  asm_add and asm_joint take the link as a part, and a joint on an LCS
#      inside the linked part reads that LCS from the linked file, not an
#      object of the same name in the assembly's file.
import json
import os
import subprocess
import sys
import textwrap
import unittest
import zipfile

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)
sys.path.insert(0, ROOT)


def child(standin, body):
    """body run in a Python of its own after the stand-in is in; what it
    prints last, as JSON."""
    code = textwrap.dedent(f'''
        import json, os, sys, tempfile
        sys.path[:0] = [{ROOT!r}, {TESTS!r}]
        import {standin}
        fc = {standin}.install()
        fc.fc.GuiUp = False
        fc.state.setdefault("flags", {{}})
        from agentlink.protocol import ToolError

        def run(tools, name, args):
            t = next(t for t in tools if t.name == name)
            try:
                return ["ok", t.fn(json.loads(json.dumps(args)))]
            except ToolError as e:
                return ["refused", e.code, e.message]
    ''') + textwrap.dedent(body)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


class LinkToAnotherFile(unittest.TestCase):
    def test_a_link_to_an_object_of_another_document(self):
        got = child("_datasheet_standin", '''
            from agentlink.families import std_more
            tmp = tempfile.mkdtemp()
            s = fc.Session(tmp)
            here = s.doc
            here.Name = here.Label = "Bike"
            here.FileName = os.path.join(tmp, "Bike.FCStd")
            fc.body("Block", fc.solid("block", (0, 0, 0), (10, 10, 10)))
            Doc = type(here)
            far = Doc()
            far.Name, far.Label, far.FileName = "Frame", "Frame part", os.path.join(tmp, "parts", "Frame.FCStd")
            fc.state["doc"] = far
            fc.body("Tube", fc.solid("tube", (0, 0, 0), (40, 4, 4)))
            fc.state["doc"] = here
            fc.state["docs"] = {"Bike": here, "Frame": far}
            active = []
            fc.fc.setActiveDocument = lambda name: active.append(name)
            tools = std_more.tools(s)
            out = {}
            out["by name"] = run(tools, "link_make", {"to": "Frame#Tube"})
            lk = here.getObjectsByLabel(out["by name"][1]["link"])[0] if out["by name"][0] == "ok" else None
            out["target doc"] = lk.LinkedObject.__dict__.get("Name") if lk else None
            out["target in far"] = bool(lk) and lk.LinkedObject in far.Objects
            out["by label"] = run(tools, "link_make", {"to": "frame part#Tube", "name": "Second"})
            out["same doc"] = run(tools, "link_make", {"to": "Bike#Block"})
            out["no doc"] = run(tools, "link_make", {"to": "Fork#Blade"})
            out["no object"] = run(tools, "link_make", {"to": "Frame#"})
            far.FileName = ""
            out["unsaved"] = run(tools, "link_make", {"to": "Frame#Tube"})
            far.FileName = os.path.join(tmp, "parts", "Frame.FCStd")
            # a file not open: opened in the background, the agent's document kept
            os.makedirs(os.path.join(tmp, "parts"), exist_ok=True)
            with open(os.path.join(tmp, "parts", "Fork.FCStd"), "w") as f:
                f.write("x")
            opened = []

            def open_document(path, hidden=False):
                opened.append([os.path.basename(path), hidden])
                nd = Doc()
                nd.Name, nd.Label, nd.FileName = "Fork", "Fork", path
                fc.state["doc"] = nd
                fc.body("Blade", fc.solid("blade", (0, 0, 0), (5, 5, 30)))
                fc.state["doc"] = here
                fc.state["docs"]["Fork"] = nd
                return nd

            fc.fc.openDocument = open_document
            out["by file"] = run(tools, "link_make", {"file": "parts/Fork.FCStd", "to": "Blade"})
            out["opened"] = opened
            out["active"] = active
            out["session doc"] = s.doc.Name
            out["again, open"] = run(tools, "link_make", {"file": "parts/Fork.FCStd", "to": "Fork#Blade"})
            out["opened again"] = len(opened)
            out["no file"] = run(tools, "link_make", {"file": "parts/Seat.FCStd", "to": "Post"})
            out["not fcstd"] = run(tools, "link_make", {"file": "parts/Seat.step", "to": "Post"})
            # outside this file's folder tree
            far.FileName = os.path.join(os.path.dirname(tmp), "elsewhere", "Frame.FCStd")
            out["apart"] = run(tools, "link_make", {"to": "Frame#Tube"})
            print(json.dumps(out, default=str))
        ''')
        ok = got["by name"]
        self.assertEqual(ok[0], "ok", ok)
        self.assertEqual(ok[1]["to"], "Tube")
        self.assertTrue(ok[1]["file"].endswith(os.path.join("parts", "Frame.FCStd")))
        self.assertIs(ok[1]["relative"], True)
        self.assertIn("33468", ok[1]["check"])
        self.assertIn("doc_open", ok[1]["check"])
        self.assertTrue(got["target in far"])
        self.assertEqual(got["by label"][0], "ok", got["by label"])
        same = got["same doc"]
        self.assertEqual(same[0], "ok", same)
        self.assertNotIn("file", same[1])
        self.assertNotIn("check", same[1])
        self.assertEqual(got["no doc"][:2], ["refused", "not_found"])
        self.assertIn("Fork", got["no doc"][2])
        self.assertEqual(got["no object"][:2], ["refused", "invalid_input"])
        self.assertEqual(got["unsaved"][:2], ["refused", "invalid_state"])
        self.assertIn("doc_save it first", got["unsaved"][2])
        byf = got["by file"]
        self.assertEqual(byf[0], "ok", byf)
        self.assertEqual(byf[1]["to"], "Blade")
        self.assertIs(byf[1]["relative"], True)
        self.assertEqual(got["opened"], [["Fork.FCStd", True]])
        self.assertEqual(got["active"], ["Bike"])
        self.assertEqual(got["session doc"], "Bike")
        self.assertEqual(got["again, open"][0], "ok", got["again, open"])
        self.assertEqual(got["opened again"], 1)
        self.assertEqual(got["no file"][:2], ["refused", "not_found"])
        self.assertEqual(got["not fcstd"][:2], ["refused", "invalid_input"])
        self.assertEqual(got["apart"][0], "ok", got["apart"])
        self.assertIs(got["apart"][1]["relative"], False)


class SavedLinkPaths(unittest.TestCase):
    def test_a_link_path_that_finds_no_file_is_named(self):
        import tempfile

        sys.path.insert(0, TESTS)
        tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(tmp, "parts"))
        open(os.path.join(tmp, "parts", "Frame.FCStd"), "w").close()
        p = os.path.join(tmp, "Bike.FCStd")
        xml = ('<Document><Object name="Link"><Property name="LinkedObject"><XLink file="parts/Frame.FCStd" stamp="x" name="Tube"/></Property></Object>'
               '<Object name="Link001"><Property name="LinkedObject"><XLink file="../../../Frame.FCStd" stamp="x" name="Tube"/></Property></Object></Document>')
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("Document.xml", xml)
        code = textwrap.dedent(f'''
            import json, sys
            sys.path[:0] = [{ROOT!r}, {TESTS!r}]
            import _datapart_standin
            _datapart_standin.install()
            from agentlink.families.doc import lost_links
            print(json.dumps([lost_links({p!r}), lost_links({os.path.join(tmp, "parts", "Frame.FCStd")!r})]))
        ''')
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr[-3000:])
        lost, none = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertEqual(lost, ["../../../Frame.FCStd"])
        self.assertEqual(none, [])


class LinkedPartInAssembly(unittest.TestCase):
    def test_asm_add_and_a_joint_on_the_lcs_of_a_linked_part(self):
        got = child("_dataasm_standin", '''
            from agentlink.families import assembly as A
            fc.state["solves"] = 0
            s = fc.Session(tempfile.mkdtemp())
            here = s.doc
            base = fc.a_part("Base", (0, 0, 0), (10, 10, 10), name="Base")
            a = fc.an_object("Assembly::AssemblyObject", "Assembly", "Assembly")
            a.__dict__["Type"] = "Assembly"
            jg = fc.into(a, fc.an_object("Assembly::JointGroup", "Joints"))
            fc.into(a, base)
            g = fc.into(jg, fc.an_object("App::FeaturePython", "GroundedJoint"))
            g.__dict__["ObjectToGround"] = base
            # an object named LCS in the assembly's own file, not the part's
            mine = fc.an_object("PartDesign::CoordinateSystem", "LCS", "Assembly LCS", kinds=("App::LocalCoordinateSystem",))
            mine.__dict__["Placement"] = fc.Placement(fc.fc.Vector(90, 90, 90), fc.Rotation())
            # the part's own file: a body with its LCS
            Doc = type(here)
            far = Doc()
            far.Name = far.Label = "Lid"
            fc.state["doc"] = far
            body = fc.a_part("Lid body", (0, 0, 0), (10, 10, 2), name="Body", type_="PartDesign::Body")
            lcs = fc.an_object("PartDesign::CoordinateSystem", "LCS", "Hinge LCS", kinds=("App::LocalCoordinateSystem",))
            lcs.__dict__["Placement"] = fc.Placement(fc.fc.Vector(1, 2, 3), fc.Rotation())
            fc.into(body, lcs)
            for o in (body, lcs):
                o.__dict__["Document"] = far
            fc.state["doc"] = here
            link = fc.an_object("App::Link", "Link", "Lid link")
            link.__dict__["LinkedObject"] = body
            link.__dict__["Shape"] = body.Shape
            link.__dict__["Placement"] = fc.Placement(fc.fc.Vector(0, 0, 10), fc.Rotation())
            tools = A.tools(s)
            out = {}
            out["add"] = run(tools, "asm_add", {"parts": ["Lid link"]})
            out["joint"] = run(tools, "asm_joint", {"kind": "fixed", "a": {"part": "Base", "element": "Face2"}, "b": {"part": "Lid link", "element": "Hinge LCS"}})
            j = [o for o in here.Objects if o.Name == "Fixed"]
            out["label"] = A.ref_label(here, j[0].Reference2) if j else None
            print(json.dumps(out, default=str))
        ''')
        self.assertEqual(got["add"][0], "ok", got["add"])
        self.assertIn("Lid link", got["add"][1]["added"])
        ok = got["joint"]
        self.assertEqual(ok[0], "ok", ok)
        self.assertEqual(ok[1]["b"], "Lid link.Hinge LCS")
        self.assertEqual(ok[1]["at"]["b"], [1.0, 2.0, 13.0])
        self.assertEqual(got["label"], "Lid link.Hinge LCS")


if __name__ == "__main__":
    unittest.main()
