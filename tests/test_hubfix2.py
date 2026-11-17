# SPDX-License-Identifier: LGPL-2.1-or-later
# The hub's own faults from the second hardening run, on stand-ins (plain
# Python; the same against FreeCAD is in test_hubfix2_fc.py):
#   - each family's state belongs to its document (agentlink/docstates.py);
#   - a call that changed nothing leaves no undo step (agentlink/changes.py);
#   - every changing call's answer carries a health;
#   - what a call leaves waiting for a recompute is said by that call;
#   - a guard does not refuse a change for what was failing before it;
#   - one long check does not hold an answer (free-form faces, a check that
#     was slow before), and says what it left out;
#   - where a batch call's time went (agentlink/around.py), the view fit
#     without its animation inside a batch, a standing verdict said once.
import json
import os
import subprocess
import sys
import textwrap
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

from agentlink import around, batchrec, changes, docstates, echo, health, hooks  # noqa: E402


class Doc:
    def __init__(self, name):
        self.Name = self.Label = name
        self.Objects = []


class S:
    """A session as docstates sees it: a doc and a __dict__."""

    def __init__(self, doc):
        self._doc = doc

    @property
    def doc(self):
        return self._doc

    @doc.setter
    def doc(self, d):
        self._doc = d
        docstates.settle(self, d)

    @property
    def family_state(self):
        return docstates.settle(self, self._doc)

    @family_state.setter
    def family_state(self, v):
        docstates.put(self, self._doc, v)


class StatePerDocument(unittest.TestCase):
    def setUp(self):
        self.open = {}
        self._was = docstates.open_documents
        docstates.open_documents = lambda: dict(self.open)
        self._hooks = hooks.saved()
        self.told = []
        hooks.on("document_state_leaving", lambda s, d, st: self.told.append(("leaving", d.Name, dict(st), s.doc.Name)))
        hooks.on("document_state_entered", lambda s, d, st, restored: self.told.append(("entered", d.Name, restored)))

    def tearDown(self):
        docstates.open_documents = self._was
        hooks.restore(self._hooks)
        docstates.OWN.clear()

    def new(self, name):
        d = self.open[name] = Doc(name)
        return d

    def test_a_new_document_starts_empty_and_going_back_finds_the_state(self):
        a, b = self.new("A"), self.new("B")
        s = S(a)
        s.family_state.setdefault("mine", {})["scan"] = "of A"
        s.doc = b  # doc_new, doc_open: any route
        self.assertEqual(s.family_state, {})
        s.family_state["mine"] = {"scan": "of B"}
        s.doc = a
        self.assertEqual(s.family_state, {"mine": {"scan": "of A"}})
        s.doc = b
        self.assertEqual(s.family_state, {"mine": {"scan": "of B"}})
        self.assertEqual(docstates.set_aside(s), ["A"])

    def test_the_events_say_when(self):
        a, b = self.new("A"), self.new("B")
        s = S(a)
        s.family_state["mine"] = 1
        s.doc = b
        # leaving is told after the move (write to the document given), with A's state
        self.assertEqual(self.told, [("leaving", "A", {"mine": 1}, "B"), ("entered", "B", False)])
        del self.told[:]
        s.doc = a
        self.assertEqual(self.told, [("entered", "A", True)])  # B's state was empty: no leaving

    def test_a_closed_document_is_let_go_and_its_name_is_not_its_identity(self):
        a, b = self.new("A"), self.new("B")
        s = S(a)
        s.family_state["mine"] = "old A"
        s.doc = b
        del self.open["A"]          # closed while the session is away
        a2 = self.new("A")          # another document under the same name
        s.doc = a2
        self.assertEqual(s.family_state, {})
        self.assertEqual(docstates.set_aside(s), ["B"])

    def test_leaving_a_closed_document_sets_nothing_aside(self):
        a, b = self.new("A"), self.new("B")
        s = S(a)
        s.family_state["mine"] = 1
        del self.open["A"]  # doc_close, doc_revert: closed first, then the session moves
        s.doc = b
        self.assertEqual(s.family_state, {})
        self.assertEqual(docstates.set_aside(s), [])
        self.assertEqual([t[0] for t in self.told], ["entered"])

    def test_an_add_on_that_settles_its_own_state_keeps_its_key(self):
        a, b = self.new("A"), self.new("B")
        s = S(a)
        hooks.own_document_state("own")
        s.family_state.update({"own": "A's, to settle itself", "mine": 1})
        s.doc = b
        self.assertEqual(s.family_state, {"own": "A's, to settle itself"})
        s.doc = a
        self.assertEqual(s.family_state, {"own": "A's, to settle itself", "mine": 1})

    def test_a_book_on_the_session_says_the_same_with_no_call(self):
        a, b = self.new("A"), self.new("B")
        s = S(a)
        s._bookish_documents = {"owner": a}
        s.family_state.update({"bookish": "A's", "other": 2})
        s.doc = b
        self.assertEqual(s.family_state, {"bookish": "A's"})

    def test_putting_a_state_back(self):
        a = self.new("A")
        s = S(a)
        kept = s.family_state
        kept["mine"] = 1
        del self.open["A"]
        a2 = self.new("A")
        s.doc = a2                 # reopened from a copy: empty
        self.assertEqual(s.family_state, {})
        s.family_state = kept      # the add-on puts back what it kept
        self.assertIs(s.family_state, kept)


# ScanRuler's own settle (scanstate.settle) against the hub's book: only
# where that add-on is importable (not here by default).
class WithAnAddOnsOwnSettle(unittest.TestCase):
    def test_its_state_stays_with_its_document(self):
        try:
            from scanrulerfc import scanstate
        except Exception:
            self.skipTest("the add-on is not on the path")
        opened = {}
        was = docstates.open_documents
        docstates.open_documents = lambda: dict(opened)
        try:
            a, b = Doc("A"), Doc("B")
            opened.update(A=a, B=b)
            s = S(a)
            st_a = scanstate.state(s)
            st_a["marked"] = "of A"
            s.doc = b
            st_b = scanstate.state(s)
            self.assertIsNot(st_b, st_a)
            self.assertIsNone(st_b["marked"])
            st_b["marked"] = "of B"
            s.doc = a
            self.assertIs(scanstate.state(s), st_a)
            s.doc = b
            self.assertIs(scanstate.state(s), st_b)
        finally:
            docstates.open_documents = was


N, G, C, R, V = changes.NEW, changes.GONE, changes.CHANGED, changes.RECOMPUTED, changes.VIEW


class WhatACallLeft(unittest.TestCase):
    def test_objects_made_and_removed_again_leave_nothing(self):
        ev = [(N, "D", "Tmp", None), (C, "D", "Tmp", "Shape"), (V, "D", "Tmp", "Visibility"), (R, "D", "Tmp", None), (G, "D", "Tmp", None)]
        self.assertEqual(changes.stays(ev), set())
        self.assertTrue(changes.only_passing(ev))

    def test_anything_else_stays(self):
        tmp = [(N, "D", "Tmp", None), (G, "D", "Tmp", None)]
        for more in ([(C, "D", "Box", "Length")], [(V, "D", "Box", "ShapeColor")], [(N, "D", "Kept", None)], [(G, "D", "Old", None)],
                     [(C, "E", "Other", "Label")], [(C, "?", "?", "Dyn")]):
            self.assertFalse(changes.only_passing(tmp + more), more)
        self.assertFalse(changes.only_passing([]))                       # nothing seen is not "made and removed"
        self.assertFalse(changes.only_passing([(R, "D", "Box", None)]))  # a recompute alone records nothing
        # removed, and the name made again: that one is here
        self.assertEqual(changes.stays(tmp + [(N, "D", "Tmp", None)]), {("D", "Tmp")})

    def test_what_changed_after_its_last_recompute(self):
        ev = [(N, "D", "New", None), (C, "D", "Pad", "Length"), (R, "D", "Pad", None), (C, "D", "Dim", "X"), (R, "D", "Dim", None),
              (C, "D", "Dim", "FormatSpec"), (C, "E", "Far", "X")]
        since, rec = changes.after_recompute(ev, "D")
        self.assertEqual(since, {"New": [], "Pad": [], "Dim": ["FormatSpec"]})
        self.assertEqual(rec, {"Pad", "Dim"})

    def test_watches_nest_and_empty_the_log(self):
        w1 = changes.open(arm=False)
        changes.note(C, "D", "A", "p")
        w2 = changes.open(arm=False)
        changes.note(C, "D", "B", "p")
        ev2, ok2 = changes.close(w2)
        ev1, ok1 = changes.close(w1)
        self.assertEqual(([e[2] for e in ev2], [e[2] for e in ev1], ok1, ok2), (["B"], ["A", "B"], True, True))
        changes.note(C, "D", "late", "p")  # no watch open: not kept
        w3 = changes.open(arm=False)
        self.assertEqual(changes.close(w3), ([], True))


class TxDoc:
    """A document's undo as FreeCAD 1.1 keeps it: a step exists once
    something is recorded, commit pushes it (empty or not), abort drops it."""

    def __init__(self, pending=False, names=()):
        self.HasPendingTransaction = pending
        self.UndoNames = list(names)
        self.did = []

    @property
    def UndoCount(self):
        return len(self.UndoNames)

    def commitTransaction(self):
        self.did.append("commit")
        if self.HasPendingTransaction:
            self.UndoNames.insert(0, "step")
            self.HasPendingTransaction = False

    def abortTransaction(self):
        self.did.append("abort")
        self.HasPendingTransaction = False


class TheUndoStep(unittest.TestCase):
    def finish(self, d, ev, ok=True):
        closed = []
        got = changes.finish(d, d, ev, ok, d.UndoCount, list(d.UndoNames), closer=closed.append)
        return got, closed

    def test_nothing_recorded_is_no_step_and_the_name_is_taken_back(self):
        d = TxDoc(pending=False, names=["earlier"])
        (made, why), closed = self.finish(d, [])
        self.assertFalse(made)
        self.assertIn("changed nothing", why)
        self.assertEqual((d.UndoNames, closed), (["earlier"], [False]))

    def test_a_change_is_a_step(self):
        d = TxDoc(pending=True)
        (made, why), closed = self.finish(d, [(C, "D", "Box", "Length")])
        self.assertEqual((made, why, d.did, closed), (True, None, ["commit"], [False]))

    def test_only_made_and_removed_objects_is_dropped_not_pushed(self):
        d = TxDoc(pending=True, names=["earlier"])
        (made, why), closed = self.finish(d, [(N, "D", "Tmp", None), (G, "D", "Tmp", None)])
        self.assertFalse(made)
        self.assertEqual((d.did, d.UndoNames, closed), (["abort"], ["earlier"], [True]))
        self.assertIn("removed again", why)

    def test_never_dropped_when_the_call_was_not_seen_whole(self):
        d = TxDoc(pending=True)
        (made, _why), _ = self.finish(d, [(N, "D", "Tmp", None), (G, "D", "Tmp", None)], ok=False)
        self.assertEqual((made, d.did), (True, ["commit"]))

    def test_never_dropped_with_nothing_seen(self):
        # A step pending and no event at all: something the observers do
        # not hear of made it; it is kept.
        d = TxDoc(pending=True)
        (made, _why), _ = self.finish(d, [])
        self.assertEqual((made, d.did), (True, ["commit"]))

    def test_a_step_the_call_committed_itself_counts(self):
        d = TxDoc(pending=False, names=["earlier"])
        u0, names0 = d.UndoCount, list(d.UndoNames)
        d.UndoNames.insert(0, "inner")
        self.assertEqual(changes.finish(d, d, [], True, u0, names0, closer=lambda a: None), (True, None))

    def test_a_stand_in_document_is_committed_and_counted_as_before(self):
        class Old:
            did = []

            def commitTransaction(self):
                self.did.append("commit")

        d = Old()
        self.assertEqual(changes.finish(d, d, [], True, 0, None, closer=lambda a: None), (True, None))
        self.assertEqual(d.did, ["commit"])


# ---- the session itself, with a stand-in FreeCAD, in a process of its own ------------------

FAKE = textwrap.dedent('''
    import sys, types, json
    sys.path.insert(0, %r)

    class Any(types.ModuleType):
        def __getattr__(self, k):
            if k.startswith("__"):
                raise AttributeError(k)
            return lambda *a, **kw: None

    class Obj:
        TypeId = "Part::Feature"
        def __init__(self, doc, name, valid=True):
            self.Document, self.Name, self.Label, self._valid = doc, name, name, valid
            self.State, self.InList, self.OutList = [], [], []
        def isValid(self):
            return self._valid
        def getStatusString(self):
            return "Valid" if self._valid else "Error"

    class Doc:
        def __init__(self, name):
            self.Name = self.Label = name
            self.Objects, self.UndoMode, self.UndoNames = [], 1, []
            self.HasPendingTransaction = False
            self.FileName = ""
            self.did = []
        UndoCount = property(lambda self: len(self.UndoNames))
        def openTransaction(self, name):
            self.name = name
        def change(self):
            self.HasPendingTransaction = True
        def commitTransaction(self):
            self.did.append("commit")
            if self.HasPendingTransaction:
                self.UndoNames.insert(0, self.name)
                self.HasPendingTransaction = False
        def abortTransaction(self):
            self.did.append("abort")
            self.HasPendingTransaction = False
        def recompute(self):
            return 0
        def getObject(self, n):
            return next((o for o in self.Objects if o.Name == n), None)

    docs, closed = {}, []
    fc = Any("FreeCAD")
    fc.GuiUp = False
    fc.Console = types.SimpleNamespace(PrintWarning=lambda *a: None, PrintMessage=lambda *a: None, PrintError=lambda *a: None, PrintLog=lambda *a: None)
    def new(name):
        docs[name] = Doc(name)
        return docs[name]
    fc.newDocument = new
    fc.listDocuments = lambda: dict(docs)
    fc.closeActiveTransaction = lambda abort=False: closed.append(bool(abort))
    sys.modules["FreeCAD"] = fc
    sys.modules["Part"] = Any("Part")
''') % HERE


def in_a_process(body):
    """body run after FAKE in a Python of its own; what it prints as JSON."""
    r = subprocess.run([sys.executable, "-c", FAKE + textwrap.dedent(body)], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


class TheSession(unittest.TestCase):
    def test_family_state_follows_the_document_by_every_route(self):
        got = in_a_process('''
            from agentlink import tools
            s = tools.Session(out_dir=".")
            first = s.doc
            s.family_state.setdefault("mine", {})["n"] = 1
            b = new("B")
            s.doc = b                      # as doc_new, doc_open and doc_close set it
            in_b = dict(s.family_state)
            s.family_state["mine"] = {"n": 2}
            s.switch(first)                # as doc_switch and doc_revert do
            back = dict(s.family_state)
            s.doc = b
            print(json.dumps({"in_b": in_b, "back": back, "b_again": s.family_state}))
        ''')
        self.assertEqual(got, {"in_b": {}, "back": {"mine": {"n": 1}}, "b_again": {"mine": {"n": 2}}})

    def test_a_call_that_changed_nothing_is_no_undo_step(self):
        got = in_a_process('''
            from agentlink import tools
            class T:
                name, changes = "writes_files_only", True
            s = tools.Session(out_dir=".")
            d = s.doc
            s.execute(T, lambda: d.change())      # a real change
            one = (s.tx, list(d.UndoNames), dict(s.last_step))
            s.execute(T, lambda: None)            # changes nothing
            two = (s.tx, list(d.UndoNames), dict(s.last_step))
            try:
                s.execute(T, lambda: 1 / 0)       # refused: the name is taken back too
            except ZeroDivisionError:
                pass
            print(json.dumps({"one": one, "two": two, "closed": closed, "did": d.did}))
        ''')
        self.assertEqual(got["one"], [1, ["writes_files_only"], {"tool": "writes_files_only", "made": True}])
        self.assertEqual(got["two"][:2], [1, ["writes_files_only"]])
        self.assertFalse(got["two"][2]["made"])
        self.assertEqual(got["closed"], [False, False, True])
        self.assertEqual(got["did"], ["commit", "commit", "abort"])

    def test_two_documents_of_one_label_are_told_apart_in_open(self):
        got = in_a_process('''
            from agentlink.families import doc as fam
            a, b, c = new("Model"), new("Model1"), new("Other")
            b.Label = "Model"
            print(json.dumps(fam.open_labels([a, b, c])))
        ''')
        self.assertEqual(got, ["Model (Model)", "Model (Model1)", "Other"])

    def test_a_guard_does_not_count_what_was_failing_before_the_call(self):
        got = in_a_process('''
            from agentlink import health
            from agentlink.families import pd_common as pc
            d = new("D")
            d.Objects += [Obj(d, "Left", valid=False), Obj(d, "Sheet")]
            class Sess:
                doc = d
            before = [b["object"] for b in pc.newly_broken(d)]     # no call in hand: every failing object, as always
            m = health.mark(Sess)
            during = [b["object"] for b in pc.newly_broken(d)]
            d.Objects.append(Obj(d, "Pad", valid=False))           # the call breaks one
            broke = [b["object"] for b in pc.newly_broken(d)]
            everything = [b["object"] for b in pc.broken(d)]
            health.drop(m)
            print(json.dumps({"before": before, "during": during, "broke": broke, "all": everything}))
        ''')
        self.assertEqual(got, {"before": ["Left"], "during": [], "broke": ["Pad"], "all": ["Left", "Pad"]})


# ---- health --------------------------------------------------------------------------------

class HObj:
    TypeId = "TechDraw::DrawViewDimension"

    def __init__(self, doc, name, state=(), output=()):
        self.Document, self.Name, self.Label = doc, name, name
        self.State, self._output = list(state), set(output)
        self.InList, self.InListRecursive, self.OutList = [], [], [self]
        doc.Objects.append(self)

    def isValid(self):
        return True

    def getPropertyStatus(self, prop):
        return ["Output"] if prop in self._output else []

    def getTypeOfProperty(self, prop):
        return []


class HSession:
    def __init__(self, doc):
        self.doc = doc


class Tool:
    name, group, changes = "drawing_make", "documents", True


class Health(unittest.TestCase):
    def run_call(self, doc, events, seen_whole=True):
        s = HSession(doc)
        m = health.mark(s)
        m["watch"]["seen"] = seen_whole
        for kind, name, prop in events:
            changes.note(kind, doc.Name, name, prop)
            if kind in (N, R):
                health._observer_note(next(o for o in doc.Objects if o.Name == name))
        out = health.attach(s, Tool, m, {})
        return out["health"]

    def test_every_changing_call_carries_a_health(self):
        d = Doc("D")
        HObj(d, "View")
        self.assertEqual(self.run_call(d, []), {"ok": True, "verdict": "nothing red"})

    def test_a_check_that_fails_says_so(self):
        d = Doc("D")
        s = HSession(d)
        m = health.mark(s)
        was = health.check
        health.check = lambda *a: 1 / 0
        try:
            out = health.attach(s, Tool, m, {})
        finally:
            health.check = was
            health.drop(m)
        self.assertIsNone(out["health"]["ok"])
        self.assertIn("did not run", out["health"]["verdict"])
        self.assertIn("recompute", out["health"]["verdict"])

    def test_what_the_call_left_waiting_is_said_by_that_call(self):
        d = Doc("D")
        HObj(d, "Template", state=["Touched"])
        HObj(d, "Dimension", state=["Touched"])
        h = self.run_call(d, [(R, "Template", None), (C, "Template", "EditableTexts"), (N, "Dimension", None)])
        self.assertEqual(h["needRecompute"], ["Template", "Dimension"])
        self.assertIn("2 objects not recomputed yet", h["verdict"])
        self.assertIn("recompute", h["todo"])

    def test_touched_from_before_its_own_recompute_is_not_asked_again(self):
        # One object's recompute executes and leaves the mark: up to date.
        d = Doc("D")
        HObj(d, "Screw", state=["Touched"])
        self.assertEqual(self.run_call(d, [(C, "Screw", "Offset"), (R, "Screw", None)]), {"ok": True, "verdict": "nothing red"})

    def test_an_output_property_changed_after_the_recompute_does_not_wait(self):
        d = Doc("D")
        HObj(d, "Screw", state=["Touched"], output=["Label"])
        self.assertNotIn("needRecompute", self.run_call(d, [(R, "Screw", None), (C, "Screw", "Label")]))

    def test_a_call_not_seen_whole_reads_as_before(self):
        d = Doc("D")
        HObj(d, "Template", state=["Touched"])
        h = self.run_call(d, [(R, "Template", None), (C, "Template", "EditableTexts")], seen_whole=False)
        self.assertNotIn("needRecompute", h)

    def test_failing_before_is_the_innermost_mark_on_that_document(self):
        d = Doc("D")
        o = HObj(d, "Left")
        o.isValid = lambda: False
        o.getStatusString = lambda: "Error"
        self.assertEqual(health.failing_before(d), set())
        m = health.mark(HSession(d))
        try:
            self.assertEqual(health.failing_before(d), {"Left"})
            self.assertEqual(health.failing_before(Doc("Other")), set())
        finally:
            health.drop(m)
        self.assertEqual(health.failing_before(d), set())


class Surface:
    pass


def face(kind, u=0, v=0):
    su = type(kind, (Surface,), {})()
    su.NbUPoles, su.NbVPoles = u, v
    return type("Face", (), {"Surface": su})()


class Shape:
    ShapeType = "Solid"

    def __init__(self, faces, check=None, seconds=0.0):
        self.Faces = faces
        self.Solids, self.Shells = [self], [self]
        self.Volume = 631.65
        self._check, self._seconds, self.checked = check, seconds, 0

    def isNull(self):
        return False

    def countElement(self, kind):
        return len(self.Faces) if kind == "Face" else 0

    def isValid(self):
        return True

    def isClosed(self):
        return True

    def check(self, bop):
        self.checked += 1
        if self._check:
            raise ValueError(self._check)


class Part_:
    TypeId = "Part::Feature"

    def __init__(self, name, shape):
        self.Name = self.Label = name
        self.Shape = shape


class LongChecks(unittest.TestCase):
    def setUp(self):
        import types

        import agentlink

        health._slow.clear()
        self._key = health._key
        health._key = lambda o: ("Solid", len(o.Shape.Faces), 0, 0, 0, 0, 0, 1, 1, 1, o.Shape.Volume)
        # geometry needs FreeCAD: its three functions health uses, stood in.
        self._geo = (sys.modules.get("agentlink.geometry"), agentlink.__dict__.get("geometry"))

        def core_check(shape):
            try:
                shape.check(True)
                return True, []
            except ValueError as e:
                return False, [str(e)]

        self.geo = types.ModuleType("agentlink.geometry")
        self.geo.core_check, self.geo.soft_bop = core_check, lambda lines: False
        self.geo.shape_key = lambda sh: ("hash", id(sh), sh.Volume)
        sys.modules["agentlink.geometry"] = agentlink.geometry = self.geo

    def tearDown(self):
        import agentlink

        health._key = self._key
        health._slow.clear()
        mod, attr = self._geo
        if mod is None:
            sys.modules.pop("agentlink.geometry", None)
        else:
            sys.modules["agentlink.geometry"] = mod
        if attr is None:
            agentlink.__dict__.pop("geometry", None)
        else:
            agentlink.geometry = attr

    def test_free_form_is_counted_by_control_points(self):
        self.assertEqual(health.freeform(Shape([face("Plane"), face("Cylinder"), face("Toroid")])), 0)
        self.assertEqual(health.freeform(Shape([face("BSplineSurface", 80, 9), face("Plane")])), 720)
        self.assertEqual(health.freeform(Shape([face("OffsetSurface")])), 100)
        self.assertGreater(health.freeform(Shape([face("BSplineSurface", 50, 9)] * 40), stop=300), 300)

    def test_a_plain_part_reads_as_it_always_did(self):
        sh = Shape([face("Plane")] * 6)
        r = health.shape_reading(Part_("Box", sh), deadline=1e18, doc_name="D")
        self.assertEqual((r["line"], r["red"], sh.checked), ("Box: valid, closed, 1 solid", False, 1))
        self.assertNotIn("unchecked", r)

    def test_a_swept_spring_is_not_given_the_long_check_and_says_so(self):
        sh = Shape([face("BSplineSurface", 80, 9), face("Plane"), face("Plane")])
        r = health.shape_reading(Part_("Spring", sh), deadline=1e18, doc_name="D")
        self.assertEqual((r["line"], r["red"], sh.checked), ("Spring: valid, closed, 1 solid", False, 0))
        self.assertEqual(len(r["unchecked"]), 1)
        self.assertIn("free-form", r["unchecked"][0])
        self.assertIn('body_check { body: "Spring" }', r["unchecked"][0])

    def test_a_failing_check_is_still_red(self):
        sh = Shape([face("Plane")] * 6, check="BOPAlgo_SelfIntersect Face3")
        r = health.shape_reading(Part_("Bad", sh), deadline=1e18, doc_name="D")
        self.assertTrue(r["red"])
        self.assertIn("FreeCAD's geometry check: BOPAlgo_SelfIntersect", r["line"])

    def test_out_of_time_is_said_not_passed_over(self):
        sh = Shape([face("Plane")] * 6)
        r = health.shape_reading(Part_("Box", sh), deadline=0, doc_name="D")
        self.assertEqual(sh.checked, 0)
        self.assertIn("out of time", r["unchecked"][0])

    def test_a_check_that_ran_long_is_not_run_on_that_shape_again(self):
        sh = Shape([face("Plane")] * 6)
        p = Part_("Slow", sh)
        was, clock = health.time.time, [0.0]

        def tick():
            clock[0] += 3.0  # every reading of the clock is 3 s on
            return clock[0]

        health.time.time = tick
        try:
            health.shape_reading(p, deadline=1e18, doc_name="D")
        finally:
            health.time.time = was
        self.assertEqual(sh.checked, 1)
        r = health.shape_reading(p, deadline=1e18, doc_name="D")
        self.assertEqual(sh.checked, 1)
        self.assertTrue(any("on this shape before" in u for u in r["unchecked"]))
        sh.Faces = [face("Plane")] * 8  # the shape changed: checked again
        r = health.shape_reading(p, deadline=1e18, doc_name="D")
        self.assertEqual(sh.checked, 2)

    def test_a_part_key_is_kept_while_the_shape_is_the_same_one(self):
        calls = []
        health._key = lambda o: calls.append(o.Name) or ("k", o.Shape.Volume)
        health._keys.clear()
        try:
            p = Part_("Ball", Shape([face("Sphere")]))
            self.assertEqual(health._key_kept("D", p), ("k", 631.65))
            self.assertEqual(health._key_kept("D", p), ("k", 631.65))
            self.assertEqual(calls, ["Ball"])           # read once
            p.Shape.Volume = 700.0                      # another shape
            self.assertEqual(health._key_kept("D", p), ("k", 700.0))
            self.assertEqual(health._key_fresh("D", p), ("k", 700.0))
            self.assertEqual(calls, ["Ball"] * 3)
        finally:
            health._keys.clear()


# ---- a batch call's time, the fit, the compact lines ---------------------------------------

class Around(unittest.TestCase):
    def test_nothing_said_when_little_ran_round_the_tool(self):
        self.assertIsNone(around.split(900, 700, {"echoAfter": 150, "health": 100}))

    def test_the_split(self):
        got = around.split(7600, 1500, {"echoBefore": 400, "echoAfter": 5600, "fit": 5200, "callDone": 3, "health": 900, "healthMark": 450, "record": 20})
        self.assertEqual(got, {"wall": 7600, "outside": {"ms": 6100, "echoBefore": 400, "echoAfter": 5600, "fit": 5200, "record": 20},
                               "inside": {"health": 900, "healthMark": 450}, "tool": 150})

    def test_a_long_health_alone_is_said(self):
        got = around.split(46300, 46119, {"health": 43837})
        self.assertEqual((got["inside"], got["tool"]), ({"health": 43837}, 2282))

    def test_parts_are_gathered_per_call(self):
        around.start()
        with around.part("fit"):
            pass
        around.add("fit", 0.25)
        around.add("health", 1.0)
        self.assertEqual(around.take(), {"fit": 250, "health": 1000})
        around.add("late", 1.0)  # no call in hand
        self.assertEqual(around.take(), {})


class View:
    def __init__(self, animated=True):
        self.animated, self.log = animated, []

    def getSceneGraph(self):
        return object()

    def isAnimationEnabled(self):
        return self.animated

    def setAnimationEnabled(self, on):
        self.animated = bool(on)
        self.log.append(("animation", bool(on)))

    def fitAll(self):
        self.log.append(("fit", self.animated))


class Fit(unittest.TestCase):
    def test_when_the_fit_may_animate(self):
        self.assertTrue(echo.fit_animated(None, "full"))                                      # a call on its own
        self.assertFalse(echo.fit_animated({"i": 0, "n": 8, "lastChange": 6}, "full"))       # a batch's first calls
        self.assertFalse(echo.fit_animated({"i": 4, "n": 8, "lastChange": 6}, "short"))
        self.assertTrue(echo.fit_animated({"i": 6, "n": 8, "lastChange": 6}, "full"))        # its last change
        self.assertTrue(echo.fit_animated({"i": 7, "n": 8, "lastChange": 6}, "full"))        # its last call

    def fit(self, view, animate):
        import types

        was = {k: sys.modules.get(k) for k in ("FreeCADGui", "agentlink.restart_mark")}
        fc_was = echo.FreeCAD
        doc = types.SimpleNamespace(Name="D")
        sys.modules["FreeCADGui"] = types.SimpleNamespace(ActiveDocument=types.SimpleNamespace(Document=doc, ActiveView=view))
        sys.modules["agentlink.restart_mark"] = types.SimpleNamespace(read=lambda: None)
        echo.FreeCAD = types.SimpleNamespace(ActiveDocument=doc, listDocuments=lambda: {"D": doc}, Console=types.SimpleNamespace(PrintLog=lambda *a: None))
        try:
            return echo.fit(animate=animate)
        finally:
            echo.FreeCAD = fc_was
            for k, v in was.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v

    def test_a_fit_without_the_animation_puts_it_back(self):
        v = View(animated=True)
        self.assertTrue(self.fit(v, animate=False))
        self.assertEqual(v.log, [("animation", False), ("fit", False), ("animation", True)])
        self.assertTrue(v.animated)

    def test_a_view_with_animation_off_is_left_off(self):
        v = View(animated=False)
        self.fit(v, animate=False)
        self.assertEqual((v.log, v.animated), ([("fit", False)], False))

    def test_a_call_on_its_own_fits_as_before(self):
        v = View(animated=True)
        self.fit(v, animate=True)
        self.assertEqual(v.log, [("fit", True)])


OLD = "2 objects still failing from before this call: Left, Dimension002"


class CompactLines(unittest.TestCase):
    def test_a_standing_part_is_said_once_and_again_when_it_changes(self):
        other = "1 object still failing from before this call: Left"
        got, cut = batchrec.brief_verdicts([f"{OLD}; Box: valid, closed, 1 solid", OLD, None, f"{OLD}; Pad: valid, closed, 1 solid",
                                           "nothing red", other, other, f"{OLD}; 1 object not recomputed yet"])
        self.assertEqual(got, [f"{OLD}; Box: valid, closed, 1 solid", "as before", None, "Pad: valid, closed, 1 solid", "nothing red", other,
                               "as before", f"{OLD}; 1 object not recomputed yet"])
        self.assertTrue(cut)

    def test_verdicts_without_one_are_untouched(self):
        vs = ["Box: valid, closed, 1 solid", "nothing red", "1 object failed to recompute: Pad (x) — 2 more were failing before this call"]
        self.assertEqual(batchrec.brief_verdicts(vs), (vs, False))

    def test_the_reply_and_the_file(self):
        results = [{"tool": "sheet_set", "ok": True, "result": {"health": {"ok": False, "verdict": OLD}}} for _ in range(3)]
        got = {"results": results, "ran": 3}
        short = batchrec.to_reply(got, 0, "run.json", 10)
        self.assertEqual([r["health"] for r in short["results"]], [OLD, "as before", "as before"])
        self.assertIn("first call", short["healthNote"])
        # what goes to the file is as it was
        self.assertEqual([r["result"]["health"]["verdict"] for r in got["results"]], [OLD] * 3)
        plain = batchrec.to_reply({"results": [{"tool": "t", "ok": True, "result": {"health": {"verdict": "nothing red"}}}]}, 0, "run.json", 10)
        self.assertNotIn("healthNote", plain)


if __name__ == "__main__":
    unittest.main()
