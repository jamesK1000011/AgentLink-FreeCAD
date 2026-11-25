# SPDX-License-Identifier: LGPL-2.1-or-later
# Unattended use on a real FreeCAD: the records inside undo (B), the calls
# kept for macros, and the rest of item 2 that runs headless. Checkpoints,
# auto-save, recovery, the settings log and macros are tested in SafetyNet.
import json
import os
import tempfile
import unittest

_HOME = tempfile.mkdtemp(prefix="agentlink-home-")

from _pd_base import HAVE, Base  # noqa: E402


@unittest.skipUnless(HAVE, "FreeCAD with PartDesign and Sketcher is not importable here")
class Unattended(Base):
    @classmethod
    def setUpClass(cls):
        # Its own home for this class, whatever other modules did to the env.
        cls._was_home = os.environ.get("AGENTLINK_HOME")
        os.environ["AGENTLINK_HOME"] = _HOME
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        if cls._was_home is None:
            os.environ.pop("AGENTLINK_HOME", None)
        else:
            os.environ["AGENTLINK_HOME"] = cls._was_home
    def box(self, name, size):
        return self.ok("part_primitive", {"kind": "box", "size": size, "name": name})

    def vol(self, label):
        return self.session.doc.getObjectsByLabel(label)[0].Shape.Volume

    def test_3_records_undo_with_the_change(self):
        self.ok("part_spec", {"spec": {"minWall": 1.2}})
        self.ok("part_spec", {"spec": {"minWall": 2.0}})
        from agentlink import store

        self.assertIsNotNone(self.session.doc.getObject(store.HOLDER))
        self.assertEqual(store.spec(self.session.doc)["minWall"], 2.0)
        self.ok("history_undo")
        self.assertEqual(store.spec(self.session.doc)["minWall"], 1.2)
        self.ok("history_redo")
        self.assertEqual(store.spec(self.session.doc)["minWall"], 2.0)
        # the holder is no part
        self.assertNotIn(store.HOLDER, [o.Name for o in self.session.bodies()])

    def test_4_records_from_an_old_file(self):
        import FreeCAD

        from agentlink import store

        d = FreeCAD.newDocument("OldRecords")
        try:
            d.Meta = {store.KEY + "spec": json.dumps({"minWall": 0.8})}
            self.assertEqual(store.spec(d)["minWall"], 0.8)
            store.write(d, "waivers", [])
            self.assertEqual(store.spec(d)["minWall"], 0.8)  # copied over
            self.assertIsNotNone(d.getObject(store.HOLDER))
        finally:
            FreeCAD.closeDocument(d.Name)

    def test_6_calls_kept_for_macros(self):
        n = len(self.session.calls)
        self.box("U d", [3, 3, 3])
        self.assertEqual(self.session.calls[-1]["tool"], "part_primitive")
        self.assertEqual(len(self.session.calls), n + 1)
        self.ok("history_undo")
        self.ok("history_redo")
        self.assertEqual(len(self.session.calls), n + 1)

    def test_9_smoke_test_passes_here(self):
        import sys

        from agentlink import smoke

        r = smoke.run()
        self.assertTrue(r["ok"], r["failures"])
        self.assertGreater(r["families"]["loaded"], 30)
        lib = os.environ.get("FREECAD_LIB")
        out = smoke.against(python=sys.executable, lib=lib, addon_dirs=[os.path.dirname(os.path.dirname(os.path.abspath(__file__)))], timeout=300)
        self.assertTrue(out["ok"], out["failures"])

    def test_10_doc_switch_and_own_errors(self):
        import FreeCAD

        s = self.session
        home = s.doc
        other = FreeCAD.newDocument("Elsewhere")
        try:
            r = self.ok("doc_switch", {"document": other.Name})
            self.assertEqual(s.doc.Name, other.Name)
            self.assertIn(other.Label, [d["label"] for d in self.ok("doc_switch")["open"]])
            self.assertEqual(self.refused("doc_switch", {"document": "Nowhere"})["code"], "not_found")
            # M4: an unrelated object failing in the recompute is a note, not a refusal
            self.box("K box", [10, 10, 10])
            bad = s.doc.addObject("Part::Extrusion", "BadExtrusion")
            s.doc.recompute()
            broke = "Invalid" in bad.State or "Error" in bad.State or not bad.isValid()
            out = self.ok("object_set", {"object": "K box", "values": {"Length": 12}})
            if broke:
                self.assertIn("BadExtrusion", out.get("note", ""))
            self.assertAlmostEqual(s.doc.getObjectsByLabel("K box")[0].Shape.Volume, 1200, places=3)
            del bad, r
        finally:
            self.ok("doc_switch", {"document": home.Name})
            FreeCAD.closeDocument(other.Name)
        self.assertEqual(self.ok("session_state")["document"], home.Name)

    def test_12_addon_manager(self):
        import tempfile

        import FreeCAD

        if tuple(int(x) for x in FreeCAD.Version()[:2]) < (1, 1):
            e = self.refused("addon")
            self.assertEqual(e["code"], "unavailable")
            self.assertIn("1.1", e["message"])
            return
        src = os.path.join(tempfile.mkdtemp(prefix="agentlink-addon-"), "AgentLinkTestAddon")
        os.makedirs(src)
        open(os.path.join(src, "Init.py"), "w").write("# a test add-on: does nothing\n")
        open(os.path.join(src, "package.xml"), "w").write("<?xml version='1.0'?><package format='1'><name>AgentLinkTestAddon</name><version>0.1</version><description>Agent Link test</description></package>\n")
        r = self.call("addon", {"action": "list"})
        if r[0] and r[1]["error"]["code"] == "unavailable":
            self.skipTest(r[1]["error"]["message"])
        def approved(args):
            # The person's OK is approve_code, which the client asks for
            # (agentlink/approvals.py): the first call is pending and
            # changes nothing.
            p = self.ok("addon", args)
            self.assertTrue(p.get("pending"), p)
            self.assertIs(p.get("changed"), False, p)
            self.assertEqual(p["approve"]["tool"], "approve_code", p)
            self.ok("approve_code", p["approve"]["arguments"])
            return self.ok("addon", args)

        got = approved({"action": "install", "name": "AgentLinkTestAddon", "url": src})
        self.assertEqual(got["smoke"], "passed")
        names = [x["name"] for x in self.ok("addon", {"action": "list"})["installed"]]
        self.assertIn("AgentLinkTestAddon", names)
        self.refused("addon", {"action": "update", "name": "AgentLinkTestAddon", "url": "https://example.com/other.git"})
        up = approved({"action": "update", "name": "AgentLinkTestAddon"})
        self.assertTrue(os.path.isdir(up["previous"]))
        self.assertIn("agentlink_update", self.refused("addon", {"action": "update", "name": "AgentLink"})["message"])
        approved({"action": "remove", "name": "AgentLinkTestAddon"})
        self.assertNotIn("AgentLinkTestAddon", [x["name"] for x in self.ok("addon", {"action": "list"})["installed"]])

    def test_13_machine_queue_and_estimates(self):
        from agentlink import keep, once

        once.reset(self.session)
        # Only on request (or while heavy jobs run or wait): noise in every read otherwise (24 Nov blind QA).
        self.assertNotIn("machine", self.ok("session_state"))
        st = self.ok("session_state", {"machine": True})
        self.assertIn("heavySlots", st["machine"])
        self.assertTrue(self.ok("queue_go")["go"])
        # Past runs say a heavy tool is slow at this size: logged data only
        # (no prejudging, 18 Nov). The first call runs (here it refuses for
        # its own reason: no mesh), and view_render runs at once.
        q = keep.queue_state()
        q["timings"] = {"view_render": [[1, 400.0], [2, 800.0]], "meshobj_decimate": [[1, 400.0], [2, 800.0]]}
        keep.save_queue(q)
        self.box("N box", [10, 10, 10])
        os.environ["AGENTLINK_GATE"] = "1"
        try:
            e = self.refused("meshobj_decimate", {})
            self.assertNotIn("takes about", e["message"])
            self.ok("view_render", {"view": "iso", "inline": False})
        finally:
            os.environ.pop("AGENTLINK_GATE", None)
            q = keep.queue_state()
            q["timings"] = {}
            keep.save_queue(q)


if __name__ == "__main__":
    unittest.main()
