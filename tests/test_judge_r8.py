# SPDX-License-Identifier: LGPL-2.1-or-later
# Three faults blind judges found replaying plans on FreeCAD 1.1.3 (T18, T11,
# T08), each checked here on the stand-ins (each in a child process of its
# own: a stand-in FreeCAD must not be seen by the other tests, nor one
# stand-in by another):
#
#   td_list        a page whose views stay without lines still lists its
#                  dimensions (notReady, the part's own value through the 3D
#                  references as model3d), any kind of dimension
#                  (DrawViewDimExtent too), and before the title block, so a
#                  reader that cuts a long answer short still has them;
#   td_dim_special arc_length answers the arc's length as measured, the
#                  chord TechDraw measures beside it (FreeCAD 1.1.3 has no
#                  arc-length type: its own Arc Length tool makes the same
#                  Distance with the arc's length as text);
#   ifc_*          the IFC file a document edits is linked from the document
#                  (its Meta, saved with the .FCStd): a new session on it
#                  (the document saved and opened again) opens it again.
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

_ran = {}


def _child(mode):
    if mode not in _ran:
        r = subprocess.run([sys.executable, os.path.abspath(__file__), mode], capture_output=True, text=True, timeout=200)
        if r.returncode != 0:
            raise AssertionError(f"child {mode} failed:\n{r.stderr[-3000:]}")
        _ran[mode] = json.loads([ln for ln in r.stdout.splitlines() if ln.startswith("{")][-1])
    return _ran[mode]


class TdList(unittest.TestCase):
    def test_dimensions_on_views_without_lines_are_listed_with_their_3d_value(self):
        got = _child("--td2")["cold"]
        dims = {d["label"]: d for d in got["dimensions"]}
        self.assertEqual(set(dims), {"Length", "Bore", "Overall"})
        for d in dims.values():
            self.assertIs(d["notReady"], True, d)
            self.assertNotIn("measured", d)  # never 0 as if measured
            self.assertNotIn("error", d)
        self.assertEqual(dims["Length"]["model3d"], 40.0)  # Box.Edge1, from the part
        self.assertNotIn("model3d", dims["Bore"])  # no 3D references: nothing said
        self.assertEqual(dims["Overall"]["type"], "Distance")  # a DrawViewDimExtent is a dimension, not "other"
        self.assertNotIn("DrawViewDimExtent", json.dumps(got.get("other")))
        self.assertIn("listed, each with notReady", got["notReady"])
        # The dimensions come before the long tail (a reader cutting the answer short still has them).
        keys = list(got)
        self.assertLess(keys.index("dimensions"), keys.index("titleBlock"))
        self.assertLess(keys.index("dimensions"), keys.index("notReady"))
        self.assertEqual(keys[-1], "titleBlock")

    def test_a_page_with_lines_reads_as_before(self):
        got = _child("--td2")["warm"]
        dims = {d["label"]: d for d in got["dimensions"]}
        self.assertEqual(dims["Length"]["measured"], 40.0)
        self.assertEqual(dims["Length"]["text"], "40.00")
        self.assertNotIn("notReady", dims["Length"])
        self.assertNotIn("model3d", dims["Length"])


class ArcLength(unittest.TestCase):
    def test_measured_is_the_arc_and_the_chord_is_beside_it(self):
        got = _child("--td")
        a = got["made"]
        self.assertEqual(a["kind"], "arc_length")
        self.assertEqual(a["type"], "Distance")  # FreeCAD's own type: there is no arc-length one in 1.1.3
        self.assertEqual(a["measures"], "arc length")
        self.assertEqual(a["text"], "◠ 14.1")
        self.assertAlmostEqual(a["measured"], 14.1421, places=3)  # the length special_length reads, as the text shows it
        self.assertIn("chord", a)
        self.assertNotEqual(a["measured"], a["chord"])
        self.assertIn("Arc Length tool", a["how"])
        listed = got["listed"][0]
        self.assertEqual(listed["measured"], a["measured"])
        self.assertEqual(listed["measures"], "arc length")
        # A plain dimension says nothing of the kind.
        self.assertNotIn("measures", got["plain"])


class IfcAfterReopen(unittest.TestCase):
    def test_a_new_session_on_the_document_opens_the_linked_file_again(self):
        got = _child("--ifc")
        self.assertTrue(got["link"]["path"].endswith("house.ifc"))
        self.assertEqual(got["link"]["schema"], "IFC4")
        self.assertEqual(got["reopened"]["count"], 3)  # ifc_find in the new session: the walls, no ifc_open
        self.assertEqual(got["reopenTrace"], ["ifcopenshell.open('house.ifc')"])
        self.assertEqual(got["edited"]["changed"], 3)  # and an edit goes on in the file opened again
        self.assertEqual(got["saved"]["edits"], 1)

    def test_after_a_save_the_saved_copy_is_the_one_opened_again(self):
        got = _child("--ifc")
        self.assertTrue(got["saved"]["path"].endswith("house_edited.ifc"))
        self.assertTrue(got["linkAfterSave"]["saved"].endswith("house_edited.ifc"))
        self.assertEqual(got["afterSaveTrace"], ["ifcopenshell.open('house_edited.ifc')"])

    def test_no_link_refuses_as_before_and_a_gone_file_says_so(self):
        got = _child("--ifc")
        self.assertEqual(got["none"], ["invalid_state", "No IFC file is open in this session: ifc_open { path } first (bim_export writes one from the model)."])
        self.assertEqual(got["gone"], ["invalid_state", "This document edited house.ifc, which is no longer there: ifc_open { path } again."])

    def test_the_dry_reading_still_reads_the_check(self):
        """tool_groups { needs }: with no file and no link, ifc_find's first check is read (false); with a link it is not told."""
        got = _child("--ifc")
        self.assertIs(got["needsNone"]["applies"], False)
        self.assertIsNone(got["needsLinked"]["applies"])


# ---- the children ---------------------------------------------------------------------------

def _td2():
    import importlib

    fc = importlib.import_module("_datatd2_standin").install()
    import _datatd2_cases
    from agentlink.families import techdraw

    out = {}
    for case, key in (("views that stay without lines", "cold"), ("a page with everything", "warm")):
        prep = next(p for t, c, p, a in _datatd2_cases.cases("techdraw", fc, tempfile.mkdtemp()) if t == "td_list" and c == case)
        fc.state["flags"] = {}
        fc.fresh()
        s = fc.Session(tempfile.mkdtemp())
        prep(s)
        page = s.doc.getObject("Page")
        box = s.doc.getObject("Box")
        length = s.doc.getObject("Dimension")
        length.__dict__["References3D"] = [(box, ("Edge1",))]
        if key == "cold":
            v = s.doc.getObject("View")
            ext = s.dim(v, ["Edge0"], "Overall")
            ext.__dict__["TypeId"] = "TechDraw::DrawViewDimExtent"
            ext.__dict__["kinds"] = ("TechDraw::DrawViewDimension", "TechDraw::DrawView")
        t = next(t for t in techdraw.tools(s) if t.name == "td_list")
        out[key] = t.fn({"page": page.Label})
    print(json.dumps(out, ensure_ascii=False, default=repr))


def _td():
    import importlib

    fc = importlib.import_module("_datatd_standin").install()
    import _datatd_cases
    from agentlink.families import techdraw

    cs = {c: (t, p, a) for t, c, p, a in _datatd_cases.cases(fc, tempfile.mkdtemp())}
    tool, prep, args = cs["an arc's length"]
    fc.state["flags"] = {}
    s = fc.Session(tempfile.mkdtemp())
    prep(s)
    tools = {t.name: t for t in techdraw.tools(s)}
    made = tools[tool].fn(args)
    plain = tools["td_dim"].fn({"view": "Front", "refs": ["Edge0"]}) if "td_dim" in tools else {}
    listed = [d for d in tools["td_list"].fn({})["dimensions"] if d.get("measures")]
    print(json.dumps({"made": made, "listed": listed, "plain": plain}, ensure_ascii=False, default=repr))


HOUSE = {"schema": "IFC4", "entities": [
    {"id": 1, "class": "IfcProject", "Name": "Annex"},
    {"id": 2, "class": "IfcBuildingStorey", "GlobalId": "0storeyGround000000001", "Name": "Ground", "Elevation": 0.0},
    *[{"id": 20 + i, "class": "IfcWall", "GlobalId": f"0wall{i:017d}", "Name": f"Wall {i + 1}", "storey": 2} for i in range(3)]]}


def _ifc():
    import _datamisc_standin

    fc = _datamisc_standin.install()
    from agentlink import needs
    from agentlink.families import ifc
    from agentlink.protocol import ToolError

    fc.fc.GuiUp = False
    fc.state["flags"] = {}
    out = {}
    d = tempfile.mkdtemp()
    with open(os.path.join(d, "house.ifc"), "w", encoding="utf-8") as f:
        f.write(json.dumps(HOUSE))

    def tools(s):
        return {t.name: t for t in ifc.tools(s)}

    def refused(fn, a):
        try:
            fn(a)
        except ToolError as e:
            return [e.code, e.message]
        return None

    def session(doc=None):
        s = fc.Session(d)
        if doc is not None:
            s.doc = doc  # the same document, as saved and opened again: its Meta with it
        return s

    first = session()
    out["none"] = refused(tools(first)["ifc_find"].fn, {})
    out["needsNone"] = needs.of_tool(tools(first)["ifc_find"])
    tools(first)["ifc_open"].fn({"path": "house.ifc"})
    out["link"] = ifc.link_of(first.doc)
    # The document saved and opened again: a new session on it, the IFC file open nowhere.
    again = session(first.doc)
    out["needsLinked"] = needs.of_tool(tools(again)["ifc_find"])
    del fc.trace[:]
    out["reopened"] = tools(again)["ifc_find"].fn({"class": "IfcWall"})
    out["reopenTrace"] = [str(x) for x in fc.trace]
    out["edited"] = tools(again)["ifc_edit"].fn({"class": "IfcWall", "attributes": {"Description": "checked"}})
    out["saved"] = tools(again)["ifc_save"].fn({})
    out["linkAfterSave"] = ifc.link_of(again.doc)
    third = session(again.doc)
    del fc.trace[:]
    tools(third)["ifc_find"].fn({})
    out["afterSaveTrace"] = [str(x) for x in fc.trace]
    # The files gone: the link says which.
    os.remove(os.path.join(d, "house.ifc"))
    os.remove(os.path.join(d, "house_edited.ifc"))
    out["gone"] = refused(tools(session(third.doc))["ifc_find"].fn, {})
    print(json.dumps(out, ensure_ascii=False, default=repr))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1].startswith("--"):
        {"--td2": _td2, "--td": _td, "--ifc": _ifc}[sys.argv[1]]()
    else:
        unittest.main()
