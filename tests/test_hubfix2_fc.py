# SPDX-License-Identifier: LGPL-2.1-or-later
# The second hardening run's hub faults on a real FreeCAD document; skipped
# where FreeCAD cannot be imported (test_hubfix2.py has them on stand-ins).
# Written without a FreeCAD to run them on: from FreeCAD 1.1's source
# (src/App/Document.cpp, AutoTransaction.cpp, Transactions.cpp).
import unittest

from _pd_base import HAVE, Base


class Changing:
    """A changing tool as the session's execute sees one."""

    changes = True

    def __init__(self, name):
        self.name = name


@unittest.skipUnless(HAVE, "FreeCAD with PartDesign and Sketcher is not importable here")
class Hubfix2(Base):
    def test_1_a_call_that_changes_nothing_is_no_undo_step(self):
        s, d = self.session, self.session.doc
        self.ok("part_primitive", {"kind": "box", "size": [10, 10, 10], "name": "Kept"})
        u, names, tx = d.UndoCount, list(d.UndoNames), s.tx
        s.execute(Changing("changes_nothing"), lambda: None)
        self.assertEqual((d.UndoCount, list(d.UndoNames), s.tx), (u, names, tx))
        self.assertFalse(s.last_step["made"])
        self.assertFalse(d.HasPendingTransaction)
        # The call's name does not stand as the active transaction: a later
        # change made with no transaction of its own is not a step under it.
        d.getObjectsByLabel("Kept")[0].Label2 = "a note"
        self.assertNotIn("changes_nothing", list(d.UndoNames))
        self.assertEqual(d.UndoCount, u)

    def test_2_objects_made_and_removed_again_are_no_undo_step(self):
        s, d = self.session, self.session.doc
        u, names, tx = d.UndoCount, list(d.UndoNames), s.tx

        def passing():
            o = d.addObject("Part::Box", "Passing")
            d.recompute()
            d.removeObject(o.Name)

        s.execute(Changing("makes_and_removes"), passing)
        self.assertEqual((d.UndoCount, list(d.UndoNames), s.tx), (u, names, tx))
        self.assertEqual(s.last_step, {"tool": "makes_and_removes", "made": False, "why": "it made only objects it removed again"})
        self.assertIsNone(d.getObject("Passing"))
        # history_undo then takes back the box, not a step that did nothing
        out = self.ok("history_undo", {})
        self.assertEqual(out["steps"], ["part_primitive"])
        self.ok("history_redo", {})

    def test_3_a_change_beside_passing_objects_is_a_step_and_stays(self):
        s, d = self.session, self.session.doc
        u, tx = d.UndoCount, s.tx
        box = d.getObjectsByLabel("Kept")[0]

        def both():
            o = d.addObject("Part::Box", "Passing")
            box.Length = 12
            d.removeObject(o.Name)
            d.recompute()

        s.execute(Changing("changes_too"), both)
        self.assertEqual((s.tx, s.last_step["made"]), (tx + 1, True))
        self.assertEqual(float(box.Length), 12.0)
        self.assertEqual(list(d.UndoNames)[0], "changes_too")
        if u < 20:
            self.assertEqual(d.UndoCount, u + 1)

    def test_4_every_changing_call_carries_a_health(self):
        out = self.ok("part_primitive", {"kind": "box", "size": [5, 5, 5], "name": "Second"})
        self.assertIn("health", out)
        from agentlink import health

        s = self.session
        got = health.attach(s, Changing("nothing_to_say"), health.mark(s), {})
        self.assertEqual(got["health"]["ok"], True, got)

    def test_5_what_a_call_leaves_waiting_is_said_by_that_call(self):
        s, d = self.session, self.session.doc
        box = d.getObjectsByLabel("Kept")[0]
        from agentlink import health

        m = health.mark(s)
        d.recompute()
        box.Width = 7  # after the recompute: waits for the next one
        h = health.attach(s, Changing("sets_after_recompute"), m, {})["health"]
        self.assertIn("Kept", h.get("needRecompute", []), h)
        d.recompute()
        # One object's own recompute leaves FreeCAD's mark on it; it is up to date.
        m = health.mark(s)
        box.Width = 8
        box.recompute()
        h = health.attach(s, Changing("recomputes_one"), m, {})["health"]
        self.assertNotIn("Kept", h.get("needRecompute", []), h)
        d.recompute()

    def test_6_a_guard_does_not_refuse_for_what_was_failing_before(self):
        d = self.session.doc
        # An object that fails its recompute, from before the call.
        body = d.addObject("PartDesign::Body", "BrokenBody")
        pad = body.newObject("PartDesign::Pad", "BadPad")  # no profile: it fails
        d.recompute()
        if pad.isValid():
            self.skipTest("this FreeCAD takes a pad with no profile: no failing object to stand in")
        made = self.ok("sheet_new", {"name": "Fresh"})
        out = self.ok("sheet_set", {"sheet": made["made"], "cells": {"A1": 12}})
        # Said once in a conversation (agentlink/once.py): the call that saw
        # it first says it, a later one names it in saidBefore.
        said = [x["health"] for x in (made, out) if "still failing from before this call" in (x.get("health") or {}).get("verdict", "")]
        self.assertTrue(said, (made.get("health"), out["health"]))
        if said[0] is not out["health"]:
            self.assertIn("failing", out["health"].get("saidBefore", []), out["health"])
        # A change that does break something new is still refused.
        e = self.refused("sheet_set", {"sheet": made["made"], "cells": {"B1": "=A1 +"}})
        self.assertNotIn("BadPad", e["message"])
        d.removeObject(pad.Name)
        d.removeObject(body.Name)
        d.recompute()

    def test_7_family_state_belongs_to_its_document(self):
        s = self.session
        first = s.doc.Name
        s.family_state.setdefault("hubfix2", {})["of"] = first
        new = self.ok("doc_new", {"name": "Hubfix2 other"})
        self.assertNotIn("hubfix2", s.family_state)
        s.family_state["hubfix2"] = {"of": new["document"]}
        self.ok("doc_switch", {"document": first})
        self.assertEqual(s.family_state["hubfix2"], {"of": first})
        self.ok("doc_switch", {"document": new["document"]})
        self.assertEqual(s.family_state["hubfix2"], {"of": new["document"]})
        out = self.ok("doc_close", {"discard": True})
        self.assertEqual(out["document"], first)
        self.assertEqual(s.family_state["hubfix2"], {"of": first})
        self.assertEqual(len(out["open"]), len(set(out["open"])))

    def test_8_two_documents_of_one_label_are_told_apart(self):
        import FreeCAD

        a = self.ok("doc_new", {"name": "Twin"})
        b = self.ok("doc_new", {"name": "Twin2"})
        FreeCAD.getDocument(b["document"]).Label = FreeCAD.getDocument(a["document"]).Label
        c = self.ok("doc_new", {"name": "Third"})
        out = self.ok("doc_close", {"documents": [c["document"]], "discard": True})
        twins = [x for x in out["open"] if x.startswith("Twin")]
        self.assertEqual(sorted(twins), sorted([f"Twin ({a['document']})", f"Twin ({b['document']})"]))
        self.ok("doc_close", {"documents": [a["document"], b["document"]], "discard": True})


if __name__ == "__main__":
    unittest.main()
