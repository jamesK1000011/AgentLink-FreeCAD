# SPDX-License-Identifier: LGPL-2.1-or-later
# The hub's findings of the bicycle test drive of 20 Nov 2026, without
# FreeCAD (plain Python, or the data tests' stand-in FreeCAD in a child
# process):
#   2  after a restart the agent's document and the document in front
#      differed: doc_switch to the agent's own document binds both again
#      (rebound), and session_state says mismatch;
#   9  fea_solve's refusal gives Gmsh's and CalculiX's own error lines, where
#      they are (surface 12 is Face12, points, elements) and the log's path;
#   10 part_refine (and fix) that makes a valid shape worse changes nothing
#      and says why;
#   11 a copied body keeps its material; fea_setup says which material and
#      where it came from.
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)
sys.path.insert(0, ROOT)
sys.path.insert(0, TESTS)

from agentlink import ccx_io  # noqa: E402


def entries():
    with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
        return json.load(f)["entries"]


def child(standin, body):
    code = textwrap.dedent(f'''
        import json, sys, tempfile
        sys.path[:0] = [{ROOT!r}, {TESTS!r}]
        import {standin}
        fc = {standin}.install()
    ''') + "\n".join(textwrap.dedent(part) for part in body.split("\n#BODY\n"))
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


# ---- finding 2: the agent's document and the one in front ------------------------------------

class FrontDocument(unittest.TestCase):
    def test_doc_switch_to_its_own_document_rebinds_when_another_is_in_front(self):
        got = child("_datacore_standin", CALL + '''
            from agentlink.families import unattended
            from agentlink import docstates
            F = fc.fc
            s = fc.Session(tempfile.mkdtemp())
            bike = s.doc
            bike.Label = "Bicycle"
            other = F.newDocument("Recovered")
            F.ActiveDocument = other                  # the window opened it last
            out = {"mismatch": docstates.mismatch(s.doc)}
            del fc.trace[:]
            out["switch"] = run(unattended, s, "doc_switch", {"document": "Bicycle"})
            out["calls"] = [t for t in fc.trace if "setActiveDocument" in t]
            F.ActiveDocument = bike
            out["after"] = docstates.mismatch(s.doc)
            out["again"] = run(unattended, s, "doc_switch", {"document": "Bicycle"})
            print(json.dumps(out, default=str))
        ''')
        m = got["mismatch"]
        self.assertEqual((m["agentDocument"], m["frontDocument"]), ("Bicycle", "Recovered"))
        self.assertIn('doc_switch { document: "Bicycle" }', m["mismatch"])
        ok, r = got["switch"][0], got["switch"][1]
        self.assertEqual(ok, "ok", got["switch"])
        self.assertTrue(r["rebound"])
        self.assertIn("Recovered was in front", r["note"])
        self.assertNotIn("Already on it", r["note"])
        self.assertTrue(any("Model" in c for c in got["calls"]), got["calls"])   # FreeCAD's active document set
        self.assertEqual(got["after"], {})
        self.assertEqual(got["again"][1]["note"], "Already on it.")              # both agree: nothing to do

    def test_a_document_object_closed_and_opened_again_rebinds(self):
        got = child("_datacore_standin", CALL + '''
            from agentlink.families import unattended
            F = fc.fc
            s = fc.Session(tempfile.mkdtemp())
            old = s.doc
            F.closeDocument("Model")
            new = F.newDocument("Model")              # the same name, another document
            s.__dict__["doc"] = old                   # the session still holds the closed one
            F.ActiveDocument = new
            r = run(unattended, s, "doc_switch", {"document": "Model"})
            print(json.dumps({"r": r, "same": s.doc is new}, default=str))
        ''')
        self.assertTrue(got["r"][1].get("rebound"), got["r"])
        self.assertTrue(got["same"])

    def test_session_state_and_the_cards_say_it(self):
        src = open(os.path.join(ROOT, "agentlink", "tools.py"), encoding="utf-8").read()
        self.assertIn("**self._front_state(),", src)
        self.assertIn("agentDocument, frontDocument and mismatch", src)
        self.assertIn("rebound: true", entries()["doc_switch"]["description"])


# ---- finding 9: the solvers' own lines and where ---------------------------------------------

GMSH = """Info    : Meshing 3D...
Info    : Tetrahedrizing 4120 nodes...
Error   : Invalid boundary mesh (overlapping facets) on surface 12 surface 15
Error   : No elements in volume 1
Warning : 3 elements remain invalid in surface 8
Error   : ------------------------------
Error   : Mesh generation error summary
Error   :     1 warning
Error   :     2 errors
Error   : Check the full log for details
Error   : ------------------------------
"""


class SolverWords(unittest.TestCase):
    def test_gmsh_lines_entities_and_the_log(self):
        rep = ccx_io.gmsh_report(GMSH)
        self.assertEqual(rep["errors"], ["Invalid boundary mesh (overlapping facets) on surface 12 surface 15", "No elements in volume 1"])
        self.assertEqual(rep["warnings"], ["3 elements remain invalid in surface 8"])
        self.assertIn({"kind": "surface", "tag": 12, "shape": "Face12"}, rep["entities"])
        self.assertIn({"kind": "volume", "tag": 1, "shape": "Solid1"}, rep["entities"])
        log = ccx_io.keep_log(tempfile.mkdtemp(), "gmsh.log", GMSH)
        words = ccx_io.gmsh_words(rep, log)
        self.assertNotIn("Check the full log", words.split("Full Gmsh log")[0])
        self.assertNotIn("2 errors", words)
        self.assertIn("Gmsh surface 12 (Face12)", words)
        self.assertIn(log, words)
        with open(log) as f:
            self.assertEqual(f.read(), GMSH)

    def test_gmsh_points(self):
        rep = ccx_io.gmsh_report("PLC Error:  A segment and a facet intersect at point (10.5,-2,3e+01).\nError   : 1 error")
        self.assertEqual(rep["points"], [[10.5, -2.0, 30.0]])
        self.assertIn("at (10.5, -2, 30) mm", ccx_io.gmsh_words(rep))

    def test_only_the_summary_falls_back_to_the_tail(self):
        rep = ccx_io.gmsh_report("Error   :     2 errors\nError   : Check the full log for details")
        self.assertEqual(rep["errors"], [])
        self.assertIn("the tail", ccx_io.gmsh_words(rep, None, "the tail"))

    def test_calculix_lines_elements_and_where(self):
        log = "*ERROR in e_c3d: nonpositive jacobian\n       determinant in element 412\n\n Job finished\n*ERROR reading *BOUNDARY: node 7 is not defined\n"
        rep = ccx_io.ccx_report(log)
        self.assertEqual(rep["errors"][0], "*ERROR in e_c3d: nonpositive jacobian determinant in element 412")
        self.assertEqual((rep["elements"], rep["nodes"]), ([412], [7]))
        words = ccx_io.ccx_words(rep, "/tmp/ccx.log", {412: [1.0, 2.5, 3.0]})
        self.assertIn("element 412 at (1, 2.5, 3) mm", words)
        self.assertIn("node 7", words)
        self.assertIn("Full CalculiX log: /tmp/ccx.log", words)

    def test_strength_uses_them(self):
        src = open(os.path.join(ROOT, "agentlink", "families", "strength.py"), encoding="utf-8").read()
        self.assertEqual(src.count("ccx_io.gmsh_words("), 3)   # own deck, FEM route, shell
        self.assertEqual(src.count("ccx_io.ccx_words("), 2)    # the job, the other runs
        self.assertIn('keep_log(wd, "gmsh.log", text)', src)


# ---- finding 10: part_refine never makes a body worse ----------------------------------------

class Shp:
    def __init__(self, valid=True, closed=(True,), volume=100.0):
        self.valid, self.vol = valid, volume
        self.Solids = [type("So", (), {"Shells": [type("Sh", (), {"isClosed": (lambda self, c=c: c)})()]})() for c in closed]

    def isValid(self):
        return self.valid

    @property
    def Volume(self):
        return self.vol


class RefineHarm(unittest.TestCase):
    def harm(self, a, b):
        # geometry imports FreeCAD and Part: stubs only for this import, and
        # the module taken back out, so no other test sees them.
        import importlib
        import types
        from unittest import mock

        with mock.patch.dict(sys.modules, {"FreeCAD": types.ModuleType("FreeCAD"), "Part": types.ModuleType("Part")}):
            sys.modules.pop("agentlink.geometry", None)
            geo = importlib.import_module("agentlink.geometry")
            try:
                return geo.refine_harm(a, b)
            finally:
                sys.modules.pop("agentlink.geometry", None)

    def test_each_way_worse_is_named(self):
        five = (True,) * 5
        self.assertIsNone(self.harm(Shp(closed=five, volume=5000), Shp(closed=five, volume=5000.2)))
        self.assertIn("isValid false", self.harm(Shp(closed=five, volume=5000), Shp(valid=False, closed=five, volume=5000)))
        self.assertIn("closed solids went from 5 to 3", self.harm(Shp(closed=five), Shp(closed=(True, True, True, False, False))))
        self.assertIn("volume went from", self.harm(Shp(volume=5000), Shp(volume=4900)))

    def test_a_broken_shape_may_be_repaired(self):
        self.assertIsNone(self.harm(Shp(valid=False, closed=(False,), volume=90), Shp(volume=90)))

    def test_the_entry_checks_before_it_bakes_and_puts_refine_back(self):
        steps = json.dumps(entries()["part_refine"]["steps"])
        self.assertLess(steps.index("refine_harm(sh, ref)"), steps.index("bake(o, ref, a.name)"))
        self.assertIn('{"set": {"tip.Refine": "=had"}}', steps)
        self.assertIn("Nothing was changed", steps)


# ---- finding 11: a copy keeps its material ---------------------------------------------------

class CopyKeepsMaterial(unittest.TestCase):
    def test_copy_record_clone_and_what_fea_setup_says(self):
        got = child("_datacore_standin", '''
            from agentlink import store
            from agentlink.families import material as M
            M._cache["lib"] = {}
            s = fc.Session(tempfile.mkdtemp())
            d = s.doc
            class O:
                def __init__(self, label, **kw):
                    self.Label = self.Name = label
                    self.__dict__.update(kw)
            frame = O("Frame"); study = O("FrameStudy"); clone = O("Clone", Objects=[frame]); bare = O("Bare")
            d.Objects = [frame, study, clone, bare]
            d.Meta = {}
            store.holder = lambda doc, make=False: None
            store.write(d, "materials", {"Frame": "aluminium"})
            out = {"before": M.of_body_said(d, "FrameStudy")[1:]}
            out["kept"] = M.carry(d, frame, [study])
            out["study"] = [M.of_body_said(d, "FrameStudy")[0]["id"]] + list(M.of_body_said(d, "FrameStudy")[1:])
            out["clone"] = [M.of_body_said(d, "Clone")[0]["id"]] + list(M.of_body_said(d, "Clone")[1:])
            out["own"] = list(M.of_body_said(d, "Frame")[1:])
            out["bare"] = [M.of_body_said(d, "Bare")[0]["id"]] + list(M.of_body_said(d, "Bare")[1:])
            out["from"] = store.read(d, "materialFrom", {})
            print(json.dumps(out))
        ''')
        self.assertEqual(got["before"], [False, "assumed PLA: no material on FrameStudy or on what it was copied from (material_set records the real one)"])
        self.assertEqual(got["kept"], ["FrameStudy"])
        self.assertEqual(got["study"], ["aluminium", True, "set on FrameStudy"])
        self.assertEqual(got["clone"], ["aluminium", True, "copied with the body from Frame (its material_set record)"])
        self.assertEqual(got["own"], [True, "set on Frame"])
        self.assertEqual(got["bare"][:2], ["pla", False])
        self.assertEqual(got["from"], {"FrameStudy": "Frame"})

    def test_the_copy_tools_carry_it_and_fea_setup_says_it(self):
        e = entries()
        for k in ("part_transform", "object_duplicate", "draft_clone"):
            self.assertIn("carry_material(o, [", json.dumps(e[k]["steps"]), k)
            self.assertIn("keeps the material", e[k]["description"], k)
        self.assertEqual(json.dumps(e["part_transform"]["steps"]).count("carry_material("), 2)   # copy, and mirror / scale
        self.assertEqual(json.dumps(e["object_duplicate"]["steps"]).count("carry_material("), 2)  # simple and full
        fs = json.dumps(e["fea_setup"])
        self.assertIn("of_body_said(", fs)
        self.assertIn("materialNote", fs)


if __name__ == "__main__":
    unittest.main()
