# SPDX-License-Identifier: LGPL-2.1-or-later
# The echo's third window pass (docs/hardening/echo3-findings.md): what a
# changing call shows (its lit button, its words, its selection) is held
# until the next changing call, so a picture of the window taken right after
# it shows it; a sketch the agent left open in another document is left;
# the Sketcher's edit toolbars put back; a sketch framed by its own lines;
# results under other things uncovered; the 3D view brought back after a
# page. Without FreeCAD: stand-ins record what the echo asks.
import json
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import echo, overlay  # noqa: E402


class Tool:
    def __init__(self, name, changes):
        self.name, self.changes = name, changes
        self.activity = None


def reply(body):
    return {"isError": False, "content": [{"type": "text", "text": json.dumps(body)}]}


class Replay(unittest.TestCase):
    """A batch's "change, snapshot" pairs, replayed against stand-ins: the
    snapshot puts out nothing and says nothing."""

    def setUp(self):
        self.events = []
        status = types.SimpleNamespace(showMessage=lambda text, ms=0: self.events.append(("status", text, ms)))
        gui = types.ModuleType("FreeCADGui")
        gui.activeWorkbench = lambda: types.SimpleNamespace(name=lambda: "PartDesignWorkbench")
        gui.listWorkbenches = lambda: {"PartDesignWorkbench": 1}
        gui.activateWorkbench = lambda wb: None
        gui.getMainWindow = lambda: types.SimpleNamespace(statusBar=lambda: status)
        gui.ActiveDocument = None
        gui.Selection = types.SimpleNamespace(clearSelection=lambda: self.events.append(("clear",)),
                                              addSelection=lambda *a: None, getSelection=lambda: [])
        self.had = sys.modules.get("FreeCADGui")
        sys.modules["FreeCADGui"] = gui
        keys = ("FreeCAD", "enabled", "caption", "_paint", "_wait", "rings_off", "flash_command", "restore_covers",
                "leave_agent_edit")
        self.saved = {k: getattr(echo, k) for k in keys}
        params = types.SimpleNamespace(GetBool=lambda k, d=True: d, GetInt=lambda k, d=0: d)
        echo.FreeCAD = types.SimpleNamespace(GuiUp=True, ActiveDocument=None, ParamGet=lambda p: params,
                                             Console=types.SimpleNamespace(PrintLog=lambda *a: None))
        echo.enabled = lambda: True
        echo.caption = lambda text, ms=echo.HOLD_MS: self.events.append(("caption", text, ms))
        echo._paint = lambda ms=0: None
        echo._wait = lambda ms: None
        echo.rings_off = lambda: self.events.append(("ringsOff",)) or True
        echo.flash_command = lambda cmd, ms=echo.HOLD_MS, settle=False, menu_ms=1300: self.events.append(("flash", cmd, ms)) or "button"
        echo.restore_covers = lambda: []
        echo.leave_agent_edit = lambda *a: None
        self.session = types.SimpleNamespace(doc=None, batch_now=None)
        self.echo = echo.Echo(self.session)

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(echo, k, v)
        if self.had is None:
            sys.modules.pop("FreeCADGui", None)
        else:
            sys.modules["FreeCADGui"] = self.had

    def call(self, tool, args, body):
        self.echo.before(tool, args)
        self.echo.after(tool, args, reply(body))

    def test_change_then_snapshot_keeps_the_ring_and_the_words(self):
        pad, snap = Tool("pd_pad", True), Tool("window_snapshot", False)
        self.call(pad, {"sketch": "Profile", "length": 5}, {"feature": "Pad"})
        at_change = list(self.events)
        self.assertEqual(at_change.count(("ringsOff",)), 1)
        flashes = [e for e in at_change if e[0] == "flash"]
        self.assertEqual(flashes, [("flash", "PartDesign_Pad", echo.HOLD_MS)])  # held, not 1.3 s
        captions = [e for e in at_change if e[0] == "caption"]
        self.assertTrue(captions and all(ms == echo.HOLD_MS for _c, _t, ms in captions))  # held, not 2.6 s
        trace = self.session.echo_trace
        del self.events[:]
        self.call(snap, {"part": "window"}, {"path": "shot.png"})
        # The snapshot put nothing out, said nothing, selected nothing, and
        # left the change's trace for session_state.
        self.assertEqual(self.events, [])
        self.assertIs(self.session.echo_trace, trace)
        # The next change puts the ring out and says its own words.
        self.call(Tool("pd_pocket", True), {"sketch": "Corner"}, {"feature": "Pocket"})
        self.assertEqual(self.events.count(("ringsOff",)), 1)
        self.assertIn(("flash", "PartDesign_Pocket", echo.HOLD_MS), self.events)

    def test_a_read_says_its_words_and_leaves_the_ring(self):
        self.call(Tool("pd_pad", True), {"sketch": "Profile"}, {"feature": "Pad"})
        del self.events[:]
        self.call(Tool("asm_check", False), {"assembly": "Crank"}, {"assembly": "Crank", "verdict": "clear"})
        self.assertNotIn(("ringsOff",), self.events)
        self.assertTrue(any(e[0] == "caption" and e[2] == echo.HOLD_MS for e in self.events))

    def test_watch_list(self):
        for name in ("window_snapshot", "view_snapshot", "report_read", "snapshot_latest"):
            self.assertTrue(echo.watching(name), name)
        for name in ("pd_pad", "asm_check", "view_set", "sketch_state"):
            self.assertFalse(echo.watching(name), name)
        # An add-on's own looks.
        echo.declare(types.SimpleNamespace(WATCH=["scan_peek"]))
        try:
            self.assertTrue(echo.watching("scan_peek"))
        finally:
            echo.WATCH.discard("scan_peek")


class HeldOnTheOverlay(unittest.TestCase):
    def test_a_held_ring_stays_until_put_out(self):
        now = [100.0]
        board = overlay.Board(clock=lambda: now[0])
        board.add("echo", [{"widget": object(), "style": "flash"}], ms=echo.HOLD_MS)
        now[0] += 10.0  # a slow call and a picture after it
        self.assertEqual(board.expire(), [])
        self.assertEqual(len(board.marks), 1)
        board.clear(owner="echo")  # the next changing call
        self.assertTrue(board.empty())

    def test_nothing_new_to_paint_is_not_painted_again(self):
        w = object()
        board = overlay.Board()
        board.add("echo", [{"widget": w, "style": "flash"}])
        rect = {"r": (10, 10, 30, 30)}
        k1 = overlay.paint_key(board, None, lambda m: rect["r"])
        self.assertEqual(k1, overlay.paint_key(board, None, lambda m: rect["r"]))
        rect["r"] = (12, 10, 30, 30)  # the button moved
        self.assertNotEqual(k1, overlay.paint_key(board, None, lambda m: rect["r"]))


class LeaveTheAgentsSketch(unittest.TestCase):
    def test_rule(self):
        sk = types.SimpleNamespace(Name="Sketch001", Label="Cuts")
        mine = {("A", "Sketch001")}
        self.assertTrue(echo.edit_to_leave("asm_joint", {"assembly": "Crank"}, "B", "A", sk, mine))
        self.assertTrue(echo.edit_to_leave("part_primitive", {}, "B", "A", sk, mine))
        # The person's own sketch is never left.
        self.assertFalse(echo.edit_to_leave("asm_joint", {}, "B", "A", sk, set()))
        # The same document: the in-document rule (closes_edit) decides.
        self.assertFalse(echo.edit_to_leave("asm_joint", {}, "A", "A", sk, mine))
        # A flow in hand: a command, a menu, a click, a dialog, a modal loop.
        for name in ("cmd_run", "menu_run", "gui_input", "dialog_answer"):
            self.assertFalse(echo.edit_to_leave(name, {}, "B", "A", sk, mine), name)
        self.assertFalse(echo.edit_to_leave("asm_joint", {}, "B", "A", sk, mine, flow=True))
        # A call that names the sketch works with it.
        self.assertFalse(echo.edit_to_leave("object_set", {"object": "Cuts"}, "B", "A", sk, mine))

    def test_opened_by_the_echo_is_noted(self):
        sk = types.SimpleNamespace(Name="S", Label="S", Document=types.SimpleNamespace(Name="A"))
        gd = types.SimpleNamespace(setEdit=lambda n: None, ActiveView=None)
        echo._agent_edits.discard(("A", "S"))
        saved = echo.FreeCAD
        echo.FreeCAD = None  # the camera check fails softly
        try:
            echo.enter_edit(gd, sk)
        finally:
            echo.FreeCAD = saved
        self.assertIn(("A", "S"), echo._agent_edits)
        echo._agent_edits.discard(("A", "S"))


class SketchBars(unittest.TestCase):
    def test_rule(self):
        hidden = [(n, False) for n in echo.SKETCH_EDIT_BARS]
        self.assertEqual(echo.bars_to_show(hidden), list(echo.SKETCH_EDIT_BARS))
        some = [("Edit Mode", True), ("Geometries", False)]
        self.assertEqual(echo.bars_to_show(some), [])  # the person's choice kept
        self.assertEqual(echo.bars_to_show([("Part Design Helper", False)]), [])


class SketchFrame(unittest.TestCase):
    class BB:
        def __init__(self, x0, y0, x1, y1):
            self.XMin, self.YMin, self.ZMin, self.XMax, self.YMax, self.ZMax = x0, y0, 0.0, x1, y1, 0.0

        def isValid(self):
            return True

    def sketch(self, boxes, dz=0.0):
        geos = [types.SimpleNamespace(toShape=lambda b=b: types.SimpleNamespace(BoundBox=b)) for b in boxes]
        pl = types.SimpleNamespace(multVec=lambda v: types.SimpleNamespace(x=v.x, y=v.y, z=v.z + dz))
        return types.SimpleNamespace(Geometry=geos, getGlobalPlacement=lambda: pl)

    def setUp(self):
        self.saved = echo.FreeCAD
        echo.FreeCAD = types.SimpleNamespace(Vector=lambda x, y, z: types.SimpleNamespace(x=x, y=y, z=z),
                                             Console=types.SimpleNamespace(PrintLog=lambda *a: None))

    def tearDown(self):
        echo.FreeCAD = self.saved

    def test_the_whole_rectangle(self):
        """pd 004: a 53 x 26 rectangle was off a 5.5 mm view."""
        box = echo.sketch_box(self.sketch([self.BB(0, 0, 53, 0), self.BB(53, 0, 53, 26), self.BB(0, 26, 53, 26)], dz=4))
        self.assertEqual(box, (0, 0, 4, 53, 26, 4))
        g = echo.grown(box)
        self.assertLess(g[0], 0)
        self.assertGreater(g[3], 53)
        self.assertGreaterEqual(g[5] - g[2], 2.0)  # flat: still a depth to frame

    def test_an_empty_sketch_shows_its_plane(self):
        box = echo.sketch_box(self.sketch([]))
        self.assertEqual(box, (-50.0, -50.0, 0.0, 50.0, 50.0, 0.0))

    def test_frame_box_off_without_a_view(self):
        self.assertFalse(echo.frame_box(None, (0, 0, 0, 1, 1, 1)))


class Uncover(unittest.TestCase):
    def test_rule(self):
        room = (2, 2, 0, 8, 8, 3)
        roof = (0, 0, 2, 10, 10, 6)        # holds the room's middle? no: z 1.5 below it
        house = (0, 0, 0, 10, 10, 6)
        far = (20, 20, 0, 30, 30, 3)
        tiny = (4, 4, 0, 6, 6, 3)          # round the middle, but smaller than the room
        self.assertEqual(echo.covers([room], [("roof", roof), ("house", house), ("far", far), ("tiny", tiny)]), ["house"])
        # A copy on top of its source: the same box.
        self.assertEqual(echo.covers([room], [("source", room)]), ["source"])

    def test_view_state_only_and_put_back(self):
        log = []

        class VO:
            PropertiesList = ["Transparency", "Visibility"]

            def __init__(self, name):
                object.__setattr__(self, "name", name)
                object.__setattr__(self, "Transparency", 0)
                object.__setattr__(self, "Visibility", True)

            def __setattr__(self, k, v):
                log.append((self.name, k, v))
                object.__setattr__(self, k, v)

        def bb(x0, y0, z0, x1, y1, z1):
            return types.SimpleNamespace(XMin=x0, YMin=y0, ZMin=z0, XMax=x1, YMax=y1, ZMax=z1, isValid=lambda: True,
                                         DiagonalLength=1.0)

        def obj(name, box):
            return types.SimpleNamespace(Name=name, Label=name, ViewObject=VO(name), Shape=types.SimpleNamespace(BoundBox=box),
                                         InListRecursive=[], OutListRecursive=[])

        space = obj("Space", bb(2, 2, 0, 8, 8, 3))
        roof = obj("Roof", bb(0, 0, 0, 10, 10, 6))
        doc = types.SimpleNamespace(Name="House", Objects=[space, roof])
        doc.getObject = lambda n: next((o for o in doc.Objects if o.Name == n), None)
        for o in (space, roof):
            o.Document = doc
        docs = {"House": doc}
        saved = echo.FreeCAD
        echo.FreeCAD = types.SimpleNamespace(listDocuments=lambda: dict(docs), getDocument=lambda n: docs[n],
                                             Console=types.SimpleNamespace(PrintLog=lambda *a: None))
        self.addCleanup(setattr, echo, "FreeCAD", saved)
        self.assertEqual(echo.uncover(doc, [space]), ["Roof"])
        self.assertEqual(roof.ViewObject.Transparency, echo.COVER_ALPHA)
        self.assertEqual(echo.restore_covers(), ["Roof"])
        self.assertEqual(roof.ViewObject.Transparency, 0)
        self.assertTrue(all(k == "Transparency" for _n, k, _v in log))  # nothing but the view's transparency
        self.assertTrue(all(n == "Roof" for n, _k, _v in log))


    def test_put_back_after_the_document_closed_or_the_object_went(self):
        """A cover is looked up by name at the next change: a closed document
        or a deleted object is passed over, never touched."""
        vo = types.SimpleNamespace()
        doc = types.SimpleNamespace(getObject=lambda n: None)  # the roof was deleted
        saved = echo.FreeCAD
        echo.FreeCAD = types.SimpleNamespace(listDocuments=lambda: {"Kept": doc}, getDocument=lambda n: doc,
                                             Console=types.SimpleNamespace(PrintLog=lambda *a: None))
        self.addCleanup(setattr, echo, "FreeCAD", saved)
        echo._covers[:] = [("Closed", "Roof", 0), ("Kept", "Roof", 10)]
        self.assertEqual(echo.restore_covers(), [])
        self.assertEqual(echo._covers, [])
        self.assertFalse(hasattr(vo, "Transparency"))


# ---- round 4: nothing deferred outlives what it touches ---------------------------------

class Signal:
    def __init__(self):
        self.slots = []

    def connect(self, fn):
        self.slots.append(fn)
        return fn

    def disconnect(self, fn):
        self.slots.remove(fn)

    def emit(self, *a):
        for fn in list(self.slots):
            fn(*a)


class FakeQObject:
    def __init__(self, parent=None):
        self._parent, self.dead = parent, False
        self.destroyed = Signal()

    def parent(self):
        if self.dead:
            raise RuntimeError("Internal C++ object already deleted.")
        return self._parent

    def setObjectName(self, n):
        self.name = n

    def destroy(self):
        """C++ deletes it: destroyed is sent, then any call raises."""
        self.destroyed.emit()
        self.dead = True


class FakeTimer(FakeQObject):
    made = []

    def __init__(self, parent=None):
        super().__init__(parent)
        self.timeout, self.running, self.deleted = Signal(), False, False
        FakeTimer.made.append(self)

    def setSingleShot(self, on):
        pass

    def start(self, ms):
        self.running = True

    def stop(self):
        self.running = False

    def deleteLater(self):
        self.deleted = True

    def fire(self):
        if self.running:
            self.running = False
            self.timeout.emit()


FakeQtCore = types.SimpleNamespace(QObject=FakeQObject, QTimer=FakeTimer)


class NothingDeferredOutlivesItsTarget(unittest.TestCase):
    def setUp(self):
        FakeTimer.made = []
        self.later = overlay.Later((FakeQtCore,))
        self.ran = []

    def test_alive(self):
        window = FakeQObject()
        button = FakeQObject(FakeQObject(window))
        self.assertTrue(overlay.alive(button))
        window.dead = True  # the toolbar's window went: the whole chain is gone
        self.assertFalse(overlay.alive(button))
        self.assertFalse(overlay.alive(None))
        self.assertFalse(overlay.alive(object(), valid=lambda o: False))  # shiboken: deleted

    def test_timers_are_ours_not_the_targets(self):
        label = FakeQObject()
        self.later.later(30000, lambda: self.ran.append(1), label)
        t = FakeTimer.made[-1]
        self.assertIs(t._parent, self.later.owner())  # owned by our QObject, never the label
        self.assertIsNot(t._parent, label)

    def test_target_destroyed_before_the_timer_fires(self):
        label = FakeQObject()
        self.later.later(30000, lambda: self.ran.append(1), label)
        t = FakeTimer.made[-1]
        label.destroy()  # the document closed and its 3D view with the caption
        self.assertFalse(t.running)       # stopped by destroyed
        self.assertTrue(t.deleted)
        self.assertEqual(self.later.pending, {})
        t.fire()
        self.assertEqual(self.ran, [])

    def test_target_dead_without_a_destroyed_signal(self):
        """A wrapper whose C++ object went without a signal seen: the
        callback checks alive() and does nothing."""
        button = FakeQObject()
        self.later.later(1300, lambda: self.ran.append(1), button)
        t = FakeTimer.made[-1]
        button.dead = True
        t.fire()
        self.assertEqual(self.ran, [])
        self.assertEqual(self.later.pending, {})

    def test_alive_target_runs_once(self):
        action = FakeQObject()
        self.later.later(1300, lambda: self.ran.append(1), action)
        t = FakeTimer.made[-1]
        t.fire()
        t.fire()
        self.assertEqual(self.ran, [1])
        self.assertEqual(action.destroyed.slots, [])  # its connection taken off
        action.destroy()  # later: nothing left to call

    def test_a_failing_callback_never_raises(self):
        self.later.later(10, lambda: 1 / 0, None)
        FakeTimer.made[-1].fire()

    def test_caption_on_a_closed_view_is_not_touched(self):
        dead = FakeQObject()
        dead.dead = True
        calls = []
        dead.isVisible = lambda: calls.append("isVisible")
        echo._hide_later(dead, "words", None)
        self.assertEqual(calls, [])

    def test_a_caption_whose_view_closed_is_made_again(self):
        """The held caption's 3D view was closed: the old label is never
        touched; a new one is made on the view in front."""
        made = []

        class Label(FakeQObject):
            def __init__(self, parent):
                super().__init__(parent)
                made.append(self)
                self.w = self.h = 10

            def __getattr__(self, k):  # setText, show, move, ...
                return lambda *a, **kw: None

            def width(self):
                return self.w

            def height(self):
                return self.h

        old = FakeQObject()
        old.dead = True
        old.hide = lambda: self.fail("a dead label touched")
        host = FakeQObject()
        host.width = lambda: 800
        host.height = lambda: 600
        keys = ("_caption", "_qt", "_view_widget")
        saved = {k: getattr(echo, k) for k in keys}
        self.addCleanup(lambda: [setattr(echo, k, v) for k, v in saved.items()])
        echo._caption = old
        qtcore = types.SimpleNamespace(Qt=types.SimpleNamespace(WA_TransparentForMouseEvents=1))
        echo._qt = lambda: (qtcore, None, types.SimpleNamespace(QLabel=Label))
        echo._view_widget = lambda: host
        saved_later = overlay._LATER[:]
        overlay._LATER[:] = [self.later]
        self.addCleanup(lambda: overlay._LATER.__setitem__(slice(None), saved_later))
        echo.caption("Padded Profile")
        self.assertEqual(len(made), 1)
        self.assertIs(echo._caption, made[0])
        t = FakeTimer.made[-1]
        self.assertIs(t._parent, self.later.owner())
        made[0].destroy()  # this view closes too, before the 30 s are up
        self.assertFalse(t.running)

    def test_lit_menu_item_gone(self):
        dead = FakeQObject()
        dead.dead = True
        calls = []
        dead.setFont = lambda f: calls.append(f)
        echo._later(dead, "setFont", "font")
        self.assertEqual(calls, [])


class OverlayDropsTheDead(unittest.TestCase):
    def test_marks_of_destroyed_buttons_go_without_a_touch(self):
        ov = overlay.Overlay(gui=None)
        live, gone, menu = FakeQObject(), FakeQObject(), FakeQObject()
        ov.board.add("echo", [{"widget": live, "style": "flash"}, {"widget": gone, "style": "flash"}], ms=echo.HOLD_MS)
        ov.board.add("x", [{"widget": live, "host": menu}])
        painter = FakeQObject()
        ov._painters[menu] = painter
        gone.dead = True  # a workbench change deleted its toolbar
        menu.dead = True  # and its menu
        dropped = ov.gone()
        self.assertEqual(len(dropped), 2)
        self.assertEqual([m.widget for m in ov.board.marks], [live])
        self.assertNotIn(menu, ov._painters)
        self.assertIsNone(ov._map(types.SimpleNamespace(host=None, widget=gone, rect=None, viewport=None)))


class Names(unittest.TestCase):
    def test_projected_lines_are_outside_geometry(self):
        self.assertEqual(echo.sub_names("sketch_project", {"ids": [-3, -4]}), ["ExternalEdge1", "ExternalEdge2"])

    def test_more_results(self):
        self.assertEqual(echo.out_names("asm_new", {}, {"assembly": "CrankSlider", "parts": ["Base"]}), ["CrankSlider"])
        self.assertEqual(echo.out_names("meshobj_smooth", {}, {"mesh": "Globe smooth", "facets": 10}), ["Globe smooth"])
        self.assertEqual(echo.out_names("draft_layer", {}, {"layer": "Frames", "objects": ["Frame"]}), ["Frames"])

    def test_view_titles(self):
        self.assertTrue(echo.view_title_is("Tut : 1[*]", "Tut"))
        self.assertTrue(echo.view_title_is("Tut", "Tut"))
        self.assertFalse(echo.view_title_is("Tut2 : 1", "Tut"))
        self.assertFalse(echo.view_title_is("Page - Tut", "Tut"))


class AfterAChange(unittest.TestCase):
    """What a changing call made when its answer names nothing: the new
    objects; nothing new: the last call's selection is not left standing."""

    def setUp(self):
        self.sel, self.cleared = [], []

        class Obj:
            def __init__(s, name):
                s.Name = s.Label = name
                s.TypeId = "Mesh::Feature"
                s.ViewObject = types.SimpleNamespace(Visibility=True)
                s.InList = []
                s.Document = types.SimpleNamespace(Name="Doc")
                s.Parents = []

        self.Obj = Obj
        self.doc = types.SimpleNamespace(Name="Doc", Label="Doc", Objects=[Obj("Globe")])
        self.doc.getObject = lambda n: next((o for o in self.doc.Objects if o.Name == n), None)
        gui = types.ModuleType("FreeCADGui")
        gui.ActiveDocument = types.SimpleNamespace(getInEdit=lambda: None, ActiveView=None)
        gui.Selection = types.SimpleNamespace(clearSelection=lambda: self.cleared.append(1),
                                              addSelection=lambda *a: self.sel.append(a), getSelection=lambda: [])
        gui.getMainWindow = lambda: types.SimpleNamespace(statusBar=lambda: types.SimpleNamespace(showMessage=lambda *a: None),
                                                          findChild=lambda *a: None)
        self.had = sys.modules.get("FreeCADGui")
        sys.modules["FreeCADGui"] = gui
        keys = ("FreeCAD", "enabled", "say", "_paint", "_qt", "_model_tab_back", "fit", "rings_off", "flash_command")
        self.saved = {k: getattr(echo, k) for k in keys}
        params = types.SimpleNamespace(GetBool=lambda k, d=True: d, GetInt=lambda k, d=0: d)
        echo.FreeCAD = types.SimpleNamespace(GuiUp=True, ActiveDocument=self.doc, ParamGet=lambda p: params,
                                             Console=types.SimpleNamespace(PrintLog=lambda *a: None))
        echo.enabled = lambda: True
        echo.say = lambda words, ms=echo.HOLD_MS, where="": words
        echo._paint = lambda *a, **k: None
        echo._qt = lambda: (None, None, types.SimpleNamespace(QMdiArea=object, QToolBar=object, QTabBar=object))
        echo._model_tab_back = lambda: False
        echo.fit = lambda animate=True, selection=False: "selection" if selection else "all"
        echo.rings_off = lambda: True
        echo.flash_command = lambda *a, **k: "button"
        self.session = types.SimpleNamespace(doc=self.doc, batch_now=None)
        self.echo = echo.Echo(self.session)

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(echo, k, v)
        if self.had is None:
            sys.modules.pop("FreeCADGui", None)
        else:
            sys.modules["FreeCADGui"] = self.had

    def test_the_new_object_is_the_result(self):
        tool = Tool("meshobj_unwrap", True)
        self.echo.before(tool, {"object": "Nothing"})
        self.doc.Objects.append(self.Obj("Unwrapped"))
        self.echo.after(tool, {"object": "Nothing"}, reply({"faces": 3}))
        tr = self.session.echo_trace
        self.assertEqual(tr["made"], ["Unwrapped"])
        self.assertEqual(tr["madeFrom"], "new")
        self.assertIn(("Doc", "Unwrapped"), self.sel)
        json.dumps(tr)  # the trace goes into a batch's answer: names, never objects

    def test_nothing_made_clears_the_last_selection(self):
        tool = Tool("pref_set", True)
        self.echo.before(tool, {"path": "x"})
        del self.cleared[:]
        self.echo.after(tool, {"path": "x"}, reply({"ok": True}))
        self.assertEqual(self.session.echo_trace["made"], [])
        self.assertTrue(self.cleared)
        self.assertEqual(self.sel, [])


if __name__ == "__main__":
    unittest.main()
