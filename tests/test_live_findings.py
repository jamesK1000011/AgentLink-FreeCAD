# SPDX-License-Identifier: LGPL-2.1-or-later
# Rough edges found in a live test drive on the Mac (16 Nov 2026), each
# held here: tool_groups' filters, mesh files coming in as meshes, meshes
# exported, placements in FreeCAD's own key names, a call beside a heavy
# untouched mesh staying fast, part_wire polyline, part_primitive direction
# and view_snapshot's several views.
import os
import time
import unittest

from _fc import HAVE, caller, server


@unittest.skipUnless(HAVE, "FreeCAD is not importable here")
class LiveFindings(unittest.TestCase):
    def setUp(self):
        self.session, self.srv = server()
        self.call = caller(self.srv)
        self.call("doc_new", {"name": "Findings"})

    def ok(self, n, a=None):
        err, out = self.call(n, a)
        self.assertFalse(err, f"{n}: {out}")
        return out

    def no(self, n, a=None):
        err, out = self.call(n, a)
        self.assertTrue(err, f"{n} should be refused: {out}")
        return out["error"]

    # 1. tool_groups answers with what its filter asks for.
    # 1b. One tool's card and a search of the index, nothing listed for it.
    def test_tool_groups_find_and_card(self):
        before = self.ok("tool_groups")["listed"]
        got = self.ok("tool_groups", {"find": "fillet edges"})
        names = [t["tool"] for t in got["tools"]]
        self.assertIn("pd_fillet", names[:5])
        self.assertTrue(all(set(t) == {"tool", "group", "does"} for t in got["tools"]))
        self.assertLessEqual(len(got["tools"]), 10)
        card = self.ok("tool_groups", {"tool": "pd_fillet"})["tools"][0]
        self.assertEqual(card["group"], "feature")
        self.assertIn("properties", card["inputSchema"])
        self.assertTrue(card["description"])
        self.assertEqual(self.ok("tool_groups")["listed"], before)
        self.assertEqual(self.ok("tool_groups", {"find": "zzqqxx"})["tools"], [])
        e = self.no("tool_groups", {"tool": "pd_filet"})
        self.assertEqual(e["code"], "not_found")
        self.assertIn("pd_fillet", e["message"])

    def test_tool_groups_filters(self):
        whole = self.ok("tool_groups")
        self.assertGreater(len(whole["groups"]), 3)
        one = self.ok("tool_groups", {"group": "doc"})
        self.assertNotIn("groups", one)
        self.assertEqual(one["group"], "doc")
        self.assertIn("import_file", one["tools"])
        self.assertTrue(one["about"])
        both = self.ok("tool_groups", {"group": "model", "detail": True})
        self.assertNotIn("groups", both)
        self.assertEqual(both["group"], "model")
        self.assertLess(len(str(both)), len(str(whole)))
        detail = self.ok("tool_groups", {"detail": True})
        self.assertTrue(all("tools" not in g and "about" in g for g in detail["groups"]))
        self.assertIn("core", self.no("tool_groups", {"group": "nope"})["message"])

    # 2. and 3. A mesh file is a mesh unless solid: true; export writes it.
    def _stl(self):
        self.ok("part_primitive", {"kind": "box", "size": [10, 10, 10], "name": "Cube"})
        p = self.ok("export", {"objects": "Cube", "format": "stl"})["path"]
        self.ok("object_delete", {"objects": ["Cube"]})
        return p

    def test_mesh_import_default_and_export(self):
        p = self._stl()
        m = self.ok("import_file", {"path": p, "name": "Scan"})["objects"][0]
        self.assertEqual(m["type"], "Mesh::Feature")
        self.assertIn("solid: true", m["note"])
        b = self.ok("import_file", {"path": p, "name": "Solid", "solid": True})["objects"][0]
        self.assertEqual(b["type"], "Part::Feature")
        out = self.ok("export", {"objects": "Scan", "path": "scan_out.stl"})
        self.assertEqual(out["meshes"], ["Scan"])
        self.assertEqual(out["verify"]["triangles"], 12)
        self.assertTrue(os.path.isfile(out["path"]))
        self.assertTrue(self.ok("export", {"objects": ["Scan"], "format": "obj"})["path"].endswith(".obj"))
        self.assertIn("solid: true", self.no("export", {"objects": "Scan", "format": "step"})["message"])
        old = self.ok("export_file", {"body": "Scan", "path": "scan_old.stl"})
        self.assertTrue(old["mesh"])
        self.assertEqual(old["verify"]["triangles"], 12)
        self.assertIn("Scan", self.no("export_file", {"body": "Nope"})["message"])

    # 4. Placement in FreeCAD's own spelling, any case; unknown keys refused;
    # a set that changed nothing says so.
    def test_placement_spellings(self):
        self.ok("part_primitive", {"kind": "box", "size": [10, 10, 10], "name": "Block"})
        r = self.ok("object_set", {"object": "Block", "values": {"Placement": {"Base": [1, 2, 3], "Axis": [0, 0, 1], "Angle": 90}}})
        to = r["set"]["Placement"]["to"]
        self.assertEqual(to["at"], [1, 2, 3])
        self.assertAlmostEqual(to["angle"], 90, places=3)
        self.assertNotIn("unchanged", r)
        # A move keeps the turn.
        r = self.ok("object_set", {"object": "Block", "values": {"Placement": {"at": [5, 0, 0]}}})
        self.assertAlmostEqual(r["set"]["Placement"]["to"]["angle"], 90, places=3)
        r = self.ok("object_set", {"object": "Block", "values": {"Placement": {"base": [5, 0, 0], "ROTATION": {"Axis": [0, 0, 1], "Angle": 90}}}})
        self.assertEqual(r["unchanged"], ["Placement"])
        self.assertTrue(r["set"]["Placement"]["unchanged"])
        self.assertIn("unchanged", r["warning"])
        e = self.no("object_set", {"object": "Block", "values": {"Placement": {"Position": [0, 0, 0], "Spin": 3}}})
        self.assertIn("Spin", e["message"])
        self.assertIn("Base", e["message"])

    # 5. A call beside a heavy mesh it does not touch stays fast.
    def test_untouched_heavy_mesh_stays_fast(self):
        import Mesh
        import numpy as np

        self.ok("part_primitive", {"kind": "box", "size": [10, 10, 10], "name": "Small"})

        size = [10]

        def timed(n):
            best = 1e9
            for _ in range(n):
                size[0] += 1  # a new value each time: a real change
                t = time.time()
                r = self.ok("object_set", {"object": "Small", "values": {"Length": size[0]}})
                best = min(best, time.time() - t)
                self.assertNotIn("unchanged", r)
            return best

        base = timed(3)
        # A stand-in for the 3.1M-triangle scan: a 300k-triangle grid, hidden
        # and left touched (as an imported or edited mesh can be).
        n = 388
        xs = np.linspace(0, 100, n)
        X, Y = np.meshgrid(xs, xs)
        P = np.stack([X, Y, np.sin(X) * np.cos(Y)], -1)
        a, b, c, d = P[:-1, :-1], P[1:, :-1], P[1:, 1:], P[:-1, 1:]
        tris = np.concatenate([np.stack([a, b, c], -2).reshape(-1, 3, 3), np.stack([a, c, d], -2).reshape(-1, 3, 3)])
        m = Mesh.Mesh()
        m.addFacets([[tuple(q) for q in t] for t in tris.tolist()])
        big = self.session.doc.addObject("Mesh::Feature", "Heavy")
        big.Mesh = m
        self.session.doc.recompute()
        big.Visibility = False
        big.touch()
        self.assertGreater(big.Mesh.CountFacets, 290000)
        heavy = timed(3)
        print(f"\nobject_set: {base * 1000:.0f} ms alone, {heavy * 1000:.0f} ms beside a {big.Mesh.CountFacets}-triangle mesh")
        self.assertLess(heavy, max(1.0, base * 5), "an unrelated object_set got slower beside the heavy mesh")
        # Not re-run by a call that did not touch it.
        self.assertIn("Touched", big.State)

    def test_snapshot_reuses_stats(self):
        # The module the session itself measures with (agentlink.tools' geo),
        # not whatever "agentlink.geometry" names by now: another test file
        # loading a second copy made the two differ, and the count read 0.
        from agentlink import tools

        geometry = tools.geo

        self.ok("part_primitive", {"kind": "box", "size": [10, 10, 10], "name": "Kept"})
        self.ok("part_primitive", {"kind": "box", "size": [10, 10, 10], "at": [50, 0, 0], "name": "Moved"})
        calls = []
        real = geometry.stats

        def counting(sh):
            calls.append(sh)
            return real(sh)

        geometry.stats = counting
        try:
            self.ok("object_set", {"object": "Moved", "values": {"Height": 20}})
        finally:
            geometry.stats = real
        # Only the body that changed is measured again.
        self.assertEqual(len(calls), 1)
        st = self.ok("session_state")
        self.assertEqual(sorted(b["name"] for b in st["bodies"]), ["Kept", "Moved"])

    # 6. part_wire polyline; polygon with points points to it.
    def test_polyline(self):
        r = self.ok("part_wire", {"kind": "polyline", "points": [[0, 0, 0], [20, 0, 0], [20, 10, 0], [0, 10, 0]], "closed": True, "name": "Outline"})
        self.assertTrue(r["closed"])
        self.assertAlmostEqual(r["length"], 60, places=6)
        self.assertEqual(r["type"], "Polygon")
        r = self.ok("part_wire", {"kind": "polyline", "points": [[0, 0, 0], [5, 0, 0], [5, 5, 0]]})
        self.assertFalse(r["closed"])
        e = self.no("part_wire", {"kind": "polygon", "points": [[0, 0, 0], [5, 0, 0], [5, 5, 0]]})
        self.assertIn("polyline", e["message"])
        self.assertIn("part_extrude", e["message"])
        ext = self.ok("part_extrude", {"profile": "Outline", "length": 5})
        self.assertAlmostEqual(ext.get("volume", 1000), 1000, delta=0.01)

    # 7. A cylinder or cone pointed along direction.
    def test_primitive_direction(self):
        r = self.ok("part_primitive", {"kind": "cylinder", "radius": 2, "height": 30, "direction": [1, 0, 0], "name": "Rod"})
        size = self.ok("session_state")["bodies"][0]["box"]
        self.assertAlmostEqual(size[0], 30, places=4)
        self.assertAlmostEqual(size[2], 4, places=4)
        self.assertIn("placement", r)
        self.ok("part_primitive", {"kind": "cone", "radius": 4, "radius2": 1, "height": 12, "direction": [0, -1, 0], "at": [0, 50, 0], "name": "Tip"})
        tip = [b for b in self.ok("session_state")["bodies"] if b["name"] == "Tip"][0]
        self.assertAlmostEqual(tip["box"][1], 12, places=4)
        self.assertIn("direction", self.no("part_primitive", {"kind": "box", "direction": [1, 0, 0]})["message"])
        self.no("part_primitive", {"kind": "cylinder", "direction": [0, 0, 0]})

    # 8. view_snapshot takes several views (the window only: headless says so
    # after checking them).
    def test_snapshot_views_checked(self):
        import FreeCAD

        from agentlink.families import view

        self.assertEqual(view.snap_grid(1), (1, 1))
        self.assertEqual(view.snap_grid(4), (2, 2))
        self.assertEqual(view.snap_grid(5), (3, 2))
        self.assertIn("view", self.no("view_snapshot", {"views": ["top", "sideways"]})["message"])
        self.no("view_snapshot", {"views": ["top"] * 7})
        if not FreeCAD.GuiUp:
            self.assertEqual(self.no("view_snapshot", {"views": ["top", "front"]})["code"], "unavailable")


if __name__ == "__main__":
    unittest.main()
