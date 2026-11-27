# SPDX-License-Identifier: LGPL-2.1-or-later
# The TechDraw tools on a real FreeCAD: skipped where it cannot be imported.
import os
import unittest

from _pd_base import HAVE, Base

try:
    import TechDraw  # noqa: F401

    HAVE_TD = HAVE
except ImportError:
    HAVE_TD = False


@unittest.skipUnless(HAVE_TD, "FreeCAD with TechDraw is not importable here")
class TechDrawTools(Base):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call = lambda n, a: cls.server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": n, "arguments": a}})  # noqa: E731
        call("pd_body_new", {"name": "Plate"})
        call("sketch_new", {"plane": "XY", "name": "Outline"})
        call("sketch_add", {"sketch": "Outline", "kind": "rectangle", "corner": [0, 0], "size": [60, 40], "dims": True, "name": "plate"})
        call("sketch_add", {"sketch": "Outline", "kind": "circle", "center": [30, 20], "diameter": 10})
        call("pd_pad", {"sketch": "Outline", "length": 8})

    def test_1_page_and_title(self):
        p = self.ok("td_page", {"action": "new", "paper": "A4", "projection": "first", "name": "Plate drawing"})
        self.assertEqual(p["page"], "Plate drawing")
        fields = self.ok("td_title", {"page": "Plate drawing"})["fields"]
        if fields:
            k = sorted(fields)[0]
            out = self.ok("td_title", {"page": "Plate drawing", "fields": {k: "AL-001"}})
            self.assertEqual(out["fields"][k], "AL-001")
        self.refused("td_title", {"page": "Plate drawing", "fields": {"nosuchfield": "x"}})

    def test_2_views_and_dims(self):
        g = self.ok("td_projection", {"page": "Plate drawing", "views": ["front", "top"], "scale": 1})
        self.assertGreaterEqual(len(g["items"]), 2)
        top = next(x["view"] for x in g["items"] if "Top" in x["view"])
        circles = self.ok("td_geometry", {"view": top, "kind": "circles"})["items"]
        self.assertTrue(any(abs(c.get("diameter", 0) - 10) < 0.01 for c in circles))
        d = self.ok("td_dim", {"view": top, "type": "diameter", "refs": [{"circle": {"diameter": 10}}], "fit": "H7"})
        self.assertAlmostEqual(d["measured"], 10, places=3)
        self.assertIn("tolerance", d)
        w = self.ok("td_dim", {"view": top, "type": "horizontal", "refs": [{"point": [0, 0, 8]}, {"point": [60, 0, 8]}], "plus": 0.1})
        self.assertAlmostEqual(w["measured"], 60, places=2)
        self.refused("td_dim", {"view": top, "type": "radius", "refs": [{"point": [0, 0, 8]}]})
        self.refused("td_dim", {"view": top, "type": "diameter", "refs": [{"circle": {"diameter": 99}}]})

    def test_3_section_detail_gdt(self):
        page = self.ok("td_list", {"page": "Plate drawing"})
        top = next(i["view"] for v in page["views"] for i in v.get("items", []) if "Top" in i["view"])
        s = self.ok("td_section", {"view": top, "normal": "-y", "through": [30, 20, 4]})
        self.assertGreater(s["edges"], 0)
        dt = self.ok("td_detail", {"view": top, "center": [0, 0, 8], "radius": 8})
        self.assertGreater(dt["edges"], 0)
        self.ok("td_datum", {"view": top, "letter": "A", "on": {"edge": {"through": [[0, 0, 8], [60, 0, 8]]}}})
        f = self.ok("td_gdt", {"view": top, "on": {"circle": {"diameter": 10}}, "frame": [{"characteristic": "position", "tolerance": 0.1, "diameter": True, "datums": ["A"]}]})
        self.assertIn("⌖", f["reads"])
        self.refused("td_gdt", {"view": top, "on": "Edge0", "frame": [{"characteristic": "perpendicularity", "tolerance": 0.1}]})

    def test_4_notes_tables_export(self):
        self.ok("td_note", {"page": "Plate drawing", "text": "Break sharp edges\nAll dims mm"})
        self.ok("sheet_set", {"sheet": self.ok("sheet_new", {"name": "Parts"})["made"], "rows": [["Item", "Part", "Qty"], [1, "Plate", 1]], "at": "A1"})
        self.ok("td_table", {"page": "Plate drawing", "sheet": "Parts"})
        e = self.ok("td_export", {"page": "Plate drawing"})
        for k in ("svg", "pdf", "dxf"):
            self.assertTrue(os.path.getsize(e["files"][k]["path"]) > 500, k)
        lst = self.ok("td_list", {"page": "Plate drawing"})
        self.assertGreaterEqual(len(lst["dimensions"]), 2)
        self.assertEqual(len(lst["gdt"]), 2)

    def test_5_a_diameter_skips_arcs(self):
        """A slot's R3 ends are arcs of ⌀6, the hole beside it a whole circle
        of ⌀6: a diameter named by size lands on the hole, never on a slot
        end; with only arcs of that size it is refused, naming radius."""
        import FreeCAD
        import Part

        V = FreeCAD.Vector
        plate = Part.makeBox(60, 30, 4)
        hole = Part.makeCylinder(3, 4, V(12, 15, 0))
        slot = Part.makeBox(16, 6, 4, V(30, 12, 0)).fuse([Part.makeCylinder(3, 4, V(30, 15, 0)), Part.makeCylinder(3, 4, V(46, 15, 0))]).removeSplitter()
        small = Part.makeBox(8, 4, 4, V(30, 22, 0)).fuse([Part.makeCylinder(2, 4, V(30, 24, 0)), Part.makeCylinder(2, 4, V(38, 24, 0))]).removeSplitter()
        o = self.session.doc.addObject("Part::Feature", "Slotted")
        o.Label = "Slotted"
        o.Shape = plate.cut(hole).cut(slot).cut(small)
        self.session.doc.recompute()
        self.ok("td_page", {"action": "new", "paper": "A4", "name": "Slots"})
        v = self.ok("td_view", {"page": "Slots", "bodies": ["Slotted"], "direction": "top", "scale": 1, "name": "SlotTop"})
        self.assertGreater(v["edges"], 0)
        kinds = [c["kind"] for c in self.ok("td_geometry", {"view": "SlotTop", "kind": "circles"})["items"] if abs(c.get("diameter", 0) - 6) < 0.01]
        self.assertIn("circle", kinds)
        self.assertIn("arc", kinds)
        # no near given, and three round edges of ⌀6: only the hole is a whole circle
        d = self.ok("td_dim", {"view": "SlotTop", "type": "diameter", "refs": [{"circle": {"diameter": 6}}]})
        self.assertAlmostEqual(d["measured"], 6, places=3)
        self.assertNotIn("note", d)
        ref = d["refs"][0]
        hit = next(c for c in self.ok("td_geometry", {"view": "SlotTop", "kind": "circles"})["items"] if c["ref"] == ref)
        self.assertEqual(hit["kind"], "circle")
        # a point by the slot's end does not pull the diameter onto it
        d2 = self.ok("td_dim", {"view": "SlotTop", "type": "diameter", "refs": [{"circle": {"diameter": 6, "near": [46, 15, 4]}}]})
        self.assertEqual(d2["refs"][0], ref)
        # ⌀4 is there as the small slot's ends only: refused, and the refusal names radius
        err = self.refused("td_dim", {"view": "SlotTop", "type": "diameter", "refs": [{"circle": {"diameter": 4}}]})
        self.assertEqual(err["code"], "not_found")
        self.assertIn("radius", err["message"])
        # a radius on that arc is what is drawn
        r = self.ok("td_dim", {"view": "SlotTop", "type": "radius", "refs": [{"circle": {"diameter": 4, "near": [38, 24, 4]}}]})
        self.assertAlmostEqual(r["measured"], 2, places=3)
        # named outright, an arc still takes a diameter (TechDraw allows it), and the answer says so
        arc = next(c["ref"] for c in self.ok("td_geometry", {"view": "SlotTop", "kind": "circles"})["items"] if c["kind"] == "arc" and abs(c["diameter"] - 6) < 0.01)
        d3 = self.ok("td_dim", {"view": "SlotTop", "type": "diameter", "refs": [arc]})
        self.assertIn("arc", d3.get("note", ""))

    def test_6_section_hatch_off(self):
        """hatch: false sets TechDraw's own word for it (Hide), so the cut
        is plain in the window and in the export."""
        self.ok("td_page", {"action": "new", "paper": "A4", "name": "Cut"})
        v = self.ok("td_view", {"page": "Cut", "bodies": ["Slotted"], "direction": "top", "scale": 1, "name": "CutTop"})
        s = self.ok("td_section", {"view": v["view"], "normal": "-y", "through": [12, 15, 2], "hatch": False})
        sv = next(x for x in self.session.doc.Objects if x.Label == s["view"])
        self.assertIn(str(sv.CutSurfaceDisplay), ("Hide", "None"))

    def test_9_a_page_read_after_opening_its_file_is_measured_not_zero(self):
        # Live, 16 Nov: after doc_open of a file holding a page, td_list read
        # 0 edges and 0.00 dimensions until a recompute — FreeCAD saves a
        # view's settings, not its lines.
        before = self.ok("td_list", {"page": "Plate drawing"})
        saved = self.ok("doc_save", {"path": "td-cold.FCStd"})
        self.ok("doc_close", {})
        self.ok("doc_open", {"path": saved.get("path") or os.path.join(self.dir, "td-cold.FCStd")})
        out = self.ok("td_list", {"page": "Plate drawing"})
        self.assertNotIn("notReady", out, out)
        rows = [x for v in out["views"] for x in ([v] + (v.get("items") or []))]
        self.assertTrue(any(r.get("edges", 0) > 0 for r in rows), out)
        self.assertEqual(len(out["dimensions"]), len(before["dimensions"]))
        was = {d["dimension"]: d.get("measured") for d in before["dimensions"]}
        for d in out["dimensions"]:
            self.assertNotIn("notReady", d)
            self.assertAlmostEqual(d["measured"], was[d["dimension"]], places=3, msg=d)
            self.assertGreater(d["measured"], 0, d)
        # read again: nothing left to work out
        self.assertNotIn("computed", self.ok("td_list", {"page": "Plate drawing"}))


if __name__ == "__main__":
    unittest.main()
