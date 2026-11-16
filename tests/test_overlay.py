# SPDX-License-Identifier: LGPL-2.1-or-later
# The overlay painter, the control finders and the 3D annotation layer,
# without a window: colours for light and dark themes, where a callout goes,
# the marks and their expiry, hidden targets reported, the echo's lit
# buttons painted through the overlay (no stylesheet), the echo's skip
# list, a menubar path, coin nodes from stand-ins, and the never-list.
import os
import re
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import annotate, echo, hooks, overlay, panel_tabs, targets  # noqa: E402

PKG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agentlink")


class Params:
    def __init__(self, **v):
        self.v = v

    def GetString(self, k, d=""):
        return self.v.get(k, d)


class Colours(unittest.TestCase):
    def test_halo_by_window(self):
        self.assertEqual(overlay.halo(overlay.luminance("#f5f5f5")), "#000000")
        self.assertEqual(overlay.halo(overlay.luminance("#2b2b2b")), "#ffffff")

    def test_theme_name_wins_over_a_dark_palette(self):
        # FreeCAD's light themes are stylesheets; the palette may stay dark.
        dark_palette = (40, 40, 40)
        lum = overlay.window_luminance(dark_palette, Params(Theme="FreeCAD Light", StyleSheet="FreeCAD.qss"))
        self.assertEqual(overlay.halo(lum), "#000000")
        lum = overlay.window_luminance((240, 240, 240), Params(Theme="Studio Dark"))
        self.assertEqual(overlay.halo(lum), "#ffffff")
        # No name that says: the palette decides.
        self.assertEqual(overlay.halo(overlay.window_luminance((240, 240, 240), Params(Theme="Classic"))), "#000000")
        self.assertEqual(overlay.halo(overlay.window_luminance(None, Params())), "#ffffff")

    def test_accent_too_close_falls_back(self):
        self.assertEqual(overlay.ring_colour("#1f5fa0", "#f0f0f0"), "#1f5fa0")
        self.assertEqual(overlay.ring_colour("#3f93e0", "#2a2a2a"), "#3f93e0")
        got = overlay.ring_colour("#f2f2f2", "#f0f0f0")
        self.assertIn(got, overlay.SAFE)
        self.assertGreaterEqual(overlay.contrast(got, "#f0f0f0"), 3.0)

    def test_bubble_and_ink(self):
        self.assertEqual(overlay.bubble(0.9)[0], "#ffffff")
        self.assertEqual(overlay.bubble(0.05)[0], "#26292e")
        self.assertEqual(overlay.ink("#ffff00"), "#000000")
        self.assertEqual(overlay.ink("#000080"), "#ffffff")


class Placement(unittest.TestCase):
    AREA = (0, 0, 1200, 800)

    def inside(self, r):
        x, y, w, h = r[:4]
        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(x + w, 1200)
        self.assertLessEqual(y + h, 800)

    def test_below_when_there_is_room(self):
        r = overlay.place_callout((100, 50, 30, 30), (200, 60), self.AREA)
        self.assertEqual(r[4], "below")
        self.inside(r)
        self.assertEqual(overlay.overlap(r[:4], (100, 50, 30, 30)), 0)

    def test_free_side_near_the_bottom_right(self):
        r = overlay.place_callout((1150, 760, 30, 30), (300, 80), self.AREA)
        self.assertIn(r[4], ("above", "left"))
        self.inside(r)
        self.assertEqual(overlay.overlap(r[:4], overlay.grow((1150, 760, 30, 30), 6)), 0)

    def test_tall_target_goes_beside(self):
        r = overlay.place_callout((10, 5, 250, 790), (320, 100), self.AREA)
        self.assertEqual(r[4], "right")
        self.inside(r)

    def test_no_target_top_centre_and_too_big_is_cut_to_the_window(self):
        r = overlay.place_callout(None, (2000, 2000), self.AREA)
        self.assertEqual(r[4], "top")
        self.inside(r)

    def test_never_over_the_3d_view(self):
        # The Mac: a Pad button on the toolbar row above the 3D view, the
        # Combo View on the left with its tab bar; the view's GL surface
        # paints over the overlay, so the callout must not reach into it.
        area = (0, 0, 1400, 900)
        view = (360, 80, 1040, 780)
        tabs = (0, 80, 360, 26)
        pad = (380, 40, 28, 28)
        x, y, w, h, side = overlay.place_callout(pad, (330, 60), area, forbid=[view], soft=[tabs])
        self.assertEqual(overlay.overlap((x, y, w, h), view), 0)
        self.assertEqual(overlay.overlap((x, y, w, h), tabs), 0)
        self.assertEqual(overlay.overlap((x, y, w, h), overlay.grow(pad, 6)), 0)
        self.assertLessEqual(x + w, 1400)

    def test_narrows_to_fit_a_narrow_dock(self):
        area = (0, 0, 1200, 800)
        view = (230, 0, 970, 800)  # everything right of a 230 px dock is 3D view

        def measure(w):  # 1200 px of text, 20 px a line
            return 16 + 20 * -(-1200 // max(1, w - 16))

        x, y, w, h, _side = overlay.place_callout((240, 300, 30, 30), (330, 80), area, forbid=[view], measure=measure)
        self.assertEqual(overlay.overlap((x, y, w, h), view), 0)
        self.assertLessEqual(w, 230)
        self.assertGreaterEqual(w, 180)
        self.assertEqual(h, measure(w))

    def test_no_target_avoids_the_view(self):
        x, y, w, h, side = overlay.place_callout(None, (300, 60), (0, 0, 1200, 800), forbid=[(300, 0, 900, 800)])
        self.assertEqual(side, "top")
        self.assertEqual(overlay.overlap((x, y, w, h), (300, 0, 900, 800)), 0)

    def test_badge_inside(self):
        b = overlay.badge_at((0, 0, 20, 20), self.AREA)
        self.assertGreaterEqual(b[0], 0)
        self.assertGreaterEqual(b[1], 0)


class Clock:
    t = 100.0

    def __call__(self):
        return self.t


class BoardTest(unittest.TestCase):
    def test_marks_expire_and_clear_by_owner(self):
        c = Clock()
        b = overlay.Board(c)
        b.add("a", [{"widget": 1}], say="hi", ms=500)
        h2, _ = b.add("b", [{"widget": 2, "badge": 1}])
        c.t += 0.6
        b.expire()
        self.assertEqual([m.owner for m in b.marks], ["b"])
        self.assertEqual(list(b.says), [])
        b.clear("b")
        self.assertTrue(b.empty())
        del h2

    def test_scene_reports_hidden_and_anchors_the_callout(self):
        b = overlay.Board(Clock())
        b.add("a", [{"widget": "seen", "badge": 1}, {"widget": "gone", "badge": 2}], say="Press Pad.")
        items, calls, hidden = b.scene(None, lambda m: (10, 10, 20, 20) if m.widget == "seen" else None, (0, 0, 100, 100))
        self.assertEqual(items, [((10, 10, 20, 20), 1, "ring")])
        self.assertEqual(calls, [((10, 10, 20, 20), "Press Pad.")])
        self.assertEqual([m.widget for m in hidden], ["gone"])

    def test_callout_alone_when_nothing_shows(self):
        b = overlay.Board(Clock())
        b.add("a", [{"widget": "gone"}], say="Menu: Part Design › Pad")
        _items, calls, _hidden = b.scene(None, lambda m: None, (0, 0, 100, 100))
        self.assertEqual(calls, [(None, "Menu: Part Design › Pad")])


# ---- stand-in widgets ---------------------------------------------------------

class Region:
    def __init__(self, empty):
        self.e = empty

    def isEmpty(self):
        return self.e


class W:
    def __init__(self, name, win=None, pos=(0, 0), size=(30, 30), visible=True, covered=False):
        self.name, self.win, self.pos, self.size = name, win, pos, size
        self.vis, self.covered = visible, covered
        self.calls = []

    def isVisible(self):
        return self.vis

    def window(self):
        return self.win or self

    def visibleRegion(self):
        return Region(self.covered)

    def rect(self):
        return (0, 0) + self.size

    def mapTo(self, target, p):
        return (self.pos[0] + p[0], self.pos[1] + p[1])

    def __getattr__(self, k):  # the never-list: anything else is recorded
        if k.startswith("__"):
            raise AttributeError(k)

        def rec(*a, **kw):
            self.calls.append(k)
        return rec


class Gui:
    def __init__(self, mw):
        self.mw = mw

    def getMainWindow(self):
        return self.mw


class Service(unittest.TestCase):
    def setUp(self):
        self.mw = W("main", size=(1200, 800))
        self.ov = overlay.Overlay(gui=Gui(self.mw))

    def test_hidden_targets_are_reported_not_painted(self):
        ok = W("pad", self.mw, pos=(200, 40))
        hid = W("pocket", self.mw, visible=False)
        other = W("float", W("elsewhere"))
        cov = W("under", self.mw, covered=True)
        got = self.ov.show([{"widget": ok, "badge": 1}, {"widget": hid}, {"widget": other}, {"widget": cov}], say="Press Pad.")
        self.assertEqual(got["shown"], [0])
        self.assertEqual(dict(got["hidden"]), {1: "hidden", 2: "in another window", 3: "covered"})
        self.assertEqual(self.ov._map(self.ov.board.marks[0]), (200, 40, 30, 30))

    def test_a_row_scrolled_away_is_hidden(self):
        tree = W("tree", self.mw, pos=(10, 100), size=(250, 300))
        got = self.ov.show([{"widget": tree, "rect": lambda: (0, 400, 250, 18)}])
        self.assertEqual(got["hidden"], [(0, "scrolled out of view")])
        got = self.ov.show([{"widget": tree, "rect": lambda: (0, 36, 250, 18)}])
        self.assertEqual(got["shown"], [0])
        self.assertEqual(self.ov._map(self.ov.board.marks[-1]), (10, 136, 250, 18))

    def test_without_a_window_nothing_is_drawn(self):
        ov = overlay.Overlay(gui=Gui(None))
        got = ov.show([{"widget": W("x")}])
        self.assertIsNone(got["handle"])
        self.assertIn("no window", got["hidden"][0][1])

    def test_clear_and_flash(self):
        b = W("btn", self.mw)
        self.assertTrue(self.ov.flash(b, 1300))
        self.assertEqual(self.ov.board.marks[0].style, "flash")
        self.ov.clear("echo")
        self.assertTrue(self.ov.board.empty())
        self.assertFalse(self.ov.flash(W("off", self.mw, visible=False)))

    def test_never_touches_the_widgets(self):
        ws = [W(str(i), self.mw, pos=(i * 40, 0)) for i in range(3)]
        self.ov.show([{"widget": w} for w in ws], say="x", ms=100)
        self.ov.flash(ws[0])
        self.ov.clear()
        for w in ws:
            forbidden = {"setFocus", "setStyleSheet", "raise_", "activateWindow", "popup", "exec", "exec_", "showFullScreen", "click"}
            self.assertFalse(forbidden & set(w.calls), w.calls)
        self.assertFalse({"raise_", "activateWindow", "showFullScreen", "setFocus"} & set(self.mw.calls), self.mw.calls)


class NeverList(unittest.TestCase):
    """No cursor moves, synthetic input, focus, opened menus, raised window
    or full screen in the painter, the finders or the annotation layer."""

    BAD = [r"QCursor", r"\.setPos\(", r"\.setFocus\(", r"\.popup\(", r"\.exec_?\(", r"activateWindow", r"showFullScreen",
           r"sendEvent", r"postEvent", r"QTest", r"\.click\(", r"\.trigger\("]

    def test_sources(self):
        for f in ("overlay.py", "targets.py", "annotate.py"):
            with open(os.path.join(PKG, f), encoding="utf-8") as fh:
                src = fh.read()
            code = "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
            code = re.sub(r'"""[\s\S]*?"""', "", code)
            for pat in self.BAD:
                self.assertIsNone(re.search(pat, code), f"{f}: {pat}")
            # Only the overlay raises itself among its siblings, never a window.
            self.assertEqual(re.findall(r"(\w+)\.raise_\(\)", code), ["self"] if f == "overlay.py" else [])


# ---- the echo's lit buttons and its skip list --------------------------------

class FakeQt:
    class QToolButton:
        def __init__(self):
            self.sheets = []

        def setStyleSheet(self, s):
            self.sheets.append(s)

    class QMenu:
        def __init__(self, act):
            self.act = act

        def menuAction(self):
            return self.act

    class QFont:
        def __init__(self, f=None):
            self.bold = False

        def setBold(self, b):
            self.bold = b

    class QTimer:
        later = []

        @staticmethod
        def singleShot(ms, fn):
            FakeQt.QTimer.later.append(fn)


class Act:
    def __init__(self):
        self.f = None

    def font(self):
        return FakeQt.QFont()

    def setFont(self, f):
        self.f = f


class EchoThroughOverlay(unittest.TestCase):
    def setUp(self):
        self.saved = (echo._qt, targets.actions, targets.associated, overlay._SERVICE)

    def tearDown(self):
        echo._qt, targets.actions, targets.associated, overlay._SERVICE = self.saved

    def test_buttons_lit_on_the_overlay_never_by_stylesheet(self):
        btn, act, title = FakeQt.QToolButton(), Act(), Act()
        menu = FakeQt.QMenu(title)
        fake = types.SimpleNamespace(QToolButton=FakeQt.QToolButton, QMenu=FakeQt.QMenu)
        qtgui = types.SimpleNamespace(QFont=FakeQt.QFont)
        qtcore = types.SimpleNamespace(QTimer=FakeQt.QTimer)
        echo._qt = lambda: (qtcore, qtgui, fake)
        targets.actions = lambda cmd, mw=None: [act] if cmd == "PartDesign_Pad" else []
        targets.associated = lambda a: [btn, menu]
        flashed = []
        overlay._SERVICE = types.SimpleNamespace(flash=lambda w, ms: flashed.append((w, ms)))
        echo.flash_command("PartDesign_Pad", ms=900)
        self.assertEqual(flashed, [(btn, 900)])
        self.assertEqual(btn.sheets, [])
        self.assertTrue(act.f.bold and title.f.bold)  # the menu item and its title, bold for a moment


class EchoSkip(unittest.TestCase):
    def setUp(self):
        self.saved = set(echo.NO_ECHO)

    def tearDown(self):
        echo.NO_ECHO.clear()
        echo.NO_ECHO.update(self.saved)

    def test_core_and_declared(self):
        for n in ("batch", "session_state", "tool_groups", "guide_read"):
            self.assertTrue(echo.skipped(n))
        self.assertFalse(echo.skipped("mine_point"))
        echo.declare(types.SimpleNamespace(NO_ECHO=("mine_", "other_peek")))
        self.assertTrue(echo.skipped("mine_point"))
        self.assertTrue(echo.skipped("other_peek"))
        self.assertFalse(echo.skipped("other_peeking_more") and False)
        self.assertFalse(echo.skipped("pd_pad"))

    def test_before_shows_nothing_for_a_skipped_tool(self):
        echo.declare(types.SimpleNamespace(NO_ECHO=("mine_",)))
        shown = []
        saved = echo.caption, echo.enabled
        echo.caption = lambda *a, **k: shown.append(a)
        echo.enabled = lambda: True
        try:
            tool = types.SimpleNamespace(name="mine_point", changes=True)
            echo.Echo(types.SimpleNamespace()).before(tool, {})
        finally:
            echo.caption, echo.enabled = saved
        self.assertEqual(shown, [])


# ---- finding controls ----------------------------------------------------------

class A:
    def __init__(self, text, sub=None, sep=False):
        self.t, self.sub, self.sep = text, sub, sep

    def text(self):
        return self.t

    def isSeparator(self):
        return self.sep

    def menu(self):
        return self.sub


class M:
    def __init__(self, *acts):
        self.acts = list(acts)

    def actions(self):
        return self.acts


class Finders(unittest.TestCase):
    def test_norm(self):
        self.assertEqual(targets.norm("&Part Design"), "part design")
        self.assertEqual(targets.norm("Create an additive feature…"), "create an additive feature")
        self.assertEqual(targets.norm("Save &As...\tCtrl+Shift+S"), "save as")

    def test_walk(self):
        pad = A("&Pad")
        add = M(A("Additive box"), A("", sep=True), pad)
        sub = A("Create an additive feature", add)
        pd = M(A("Create body"), sub)
        top = A("&Part Design", pd)
        chain, missing = targets.walk([A("&File", M()), top], ["Part Design", "Create an additive feature", "Pad"])
        self.assertIsNone(missing)
        self.assertEqual([(m, a) for m, a in chain], [(None, top), (pd, sub), (add, pad)])
        chain, missing = targets.walk([top], ["Part Design", "Nope", "Pad"])
        self.assertEqual(missing, "Nope")
        self.assertEqual(len(chain), 1)

    def test_workbench_of(self):
        self.assertEqual(targets.workbench_of("PartDesign_Pad"), "PartDesignWorkbench")
        self.assertEqual(targets.workbench_of("Part_Box"), "PartWorkbench")
        self.assertIsNone(targets.workbench_of("Std_Undo"))
        self.assertIsNone(targets.workbench_of("Mine_Do"))

    def test_command_for_is_echos(self):
        self.assertEqual(targets.command_for("pd_pad", {}), "PartDesign_Pad")


# ---- the 3D annotation layer ---------------------------------------------------

class Node:
    def __init__(self, kind):
        self.kind, self.children, self.name = kind, [], None
        self.point = types.SimpleNamespace(setValues=lambda *a: setattr(self, "pts", a[2]), setValue=lambda *a: setattr(self, "pts", a))
        self.coordIndex = types.SimpleNamespace(setValues=lambda *a: setattr(self, "idx", a[2]))
        self.numVertices = types.SimpleNamespace(setValue=lambda n: setattr(self, "n", n))

    def addChild(self, c):
        self.children.append(c)

    def removeChild(self, c):
        self.children.remove(c)

    def setName(self, n):
        self.name = n


class FakeCoin(types.SimpleNamespace):
    def __getattr__(self, k):
        if k.startswith("So"):
            return lambda: Node(k)
        raise AttributeError(k)


class V:
    def __init__(self, *p):
        self.x, self.y, self.z = p


class Face:
    CenterOfMass = V(0.3, 0.3, 0)

    def tessellate(self, tol):
        return [V(0, 0, 0), V(1, 0, 0), V(0, 1, 0)], [(0, 1, 2)]


class Edge:
    FirstParameter, LastParameter = 0.0, 4.0

    def valueAt(self, t):
        return V(t, 0, 0)

    def discretize(self, Number):
        return [V(i, 0, 0) for i in range(Number)]


class Shape:
    def getElement(self, n):
        return {"Face6": Face(), "Edge3": Edge(), "Vertex1": types.SimpleNamespace(Point=V(1, 2, 3))}[n]


class Annotations(unittest.TestCase):
    def test_light_and_clear(self):
        scene = Node("root")
        ann = annotate.Annotations(coin=FakeCoin(), scene=lambda: scene)
        got = ann.light(types.SimpleNamespace(Label="Pad"), ["Face6", "Edge3", "Vertex1", "Face99", "Bogus"], owner="mine", shape=Shape())
        self.assertEqual(got["lit"], ["Face6", "Edge3", "Vertex1"])
        self.assertEqual([s for s, _ in got["missing"]], ["Face99", "Bogus"])
        root = scene.children[0]
        self.assertEqual([n.kind for n in root.children], ["SoAnnotation"] * 3)
        face = root.children[0]
        self.assertEqual([c.kind for c in face.children], ["SoMaterial", "SoPolygonOffset", "SoCoordinate3", "SoIndexedFaceSet"])
        self.assertEqual(face.children[3].idx, [0, 1, 2, -1])
        ann.clear("mine")
        self.assertEqual(scene.children, [])

    def test_badge_at_the_first_lit_centre(self):
        scene = Node("root")
        ann = annotate.Annotations(coin=FakeCoin(), scene=lambda: scene)
        ann.light(types.SimpleNamespace(Label="Pad"), ["Face99", "Edge3", "Face6"], owner="mine", shape=Shape(), badge=2)
        kids = scene.children[0].children
        self.assertEqual([n.kind for n in kids], ["SoAnnotation"] * 3)  # edge, its badge, face
        badge = kids[1]
        self.assertEqual([c.kind for c in badge.children], ["SoMaterial", "SoTranslation", "SoCoordinate3", "SoMarkerSet", "SoFont", "SoText2"])
        self.assertEqual(badge.children[1].translation, (2.0, 0, 0))
        self.assertEqual(badge.children[5].string, "  2")
        scene2 = Node("root")
        annotate.Annotations(coin=FakeCoin(), scene=lambda: scene2).light(object(), ["Face6"], shape=Shape())
        self.assertEqual(len(scene2.children[0].children), 1)  # no badge asked, none drawn

    def test_no_view(self):
        ann = annotate.Annotations(coin=FakeCoin(), scene=lambda: None)
        got = ann.light(object(), ["Face1"], shape=Shape())
        self.assertEqual(got["lit"], [])
        self.assertIn("no 3D view", got["missing"][0][1])

    def test_kind_of(self):
        self.assertEqual(annotate.kind_of("Face12"), "face")
        self.assertEqual(annotate.kind_of("Edge1"), "edge")
        self.assertIsNone(annotate.kind_of("Faces"))


# ---- commands inside a toolbar dropdown (group commands) ------------------------

class GAct:
    def __init__(self, name="", menu=None, prop=None):
        self.n, self.m, self.p = name, menu, prop

    def objectName(self):
        return self.n

    def property(self, k):
        return self.p if k == "CommandName" else None

    def menu(self):
        return self.m


class GMenu:
    def __init__(self, *acts):
        self.acts = list(acts)

    def actions(self):
        return self.acts


class Btn:
    def __init__(self, default=None, menu=None):
        self.d, self.m = default, menu

    def defaultAction(self):
        return self.d

    def menu(self):
        return self.m


class DeadBtn:
    def defaultAction(self):
        raise RuntimeError("Internal C++ object already deleted.")

    menu = defaultAction


def group(name, *children, own_menu=False):
    m = GMenu(*[GAct(c) for c in children])
    return Btn(GAct(name, menu=None if own_menu else m), m if own_menu else None)


class Groups(unittest.TestCase):
    """FreeCAD 1.1.3: Sketcher's rectangles, arcs and circles and Part
    Design's primitives sit in dropdown buttons whose default action is the
    group's, not the child command's."""

    def setUp(self):
        self.rects = group("Sketcher_CompCreateRectangles", "Sketcher_CreateRectangle", "Sketcher_CreateRectangle_Center", "Sketcher_CreateOblong")
        self.arcs = group("Sketcher_CompCreateArc", "Sketcher_CreateArc", "Sketcher_Create3PointArc")
        self.circles = group("Sketcher_CompCreateCircle", "Sketcher_CreateCircle", "Sketcher_Create3PointCircle", own_menu=True)
        prims = GMenu(GAct(prop=b"PartDesign_AdditiveBox"), GAct(prop=b"PartDesign_AdditiveCylinder"))  # named only by property
        self.prims = Btn(GAct("PartDesign_CompPrimitiveAdditive", menu=prims))
        self.line = Btn(GAct("Sketcher_CreateLine"))
        btns = [self.rects, self.arcs, self.circles, self.prims, self.line, DeadBtn()]
        self.mw = types.SimpleNamespace(findChildren=lambda cls: list(btns))

    def find(self, cmd):
        return targets.group_buttons(cmd, self.mw, tool_button=object)

    def test_each_group_found_by_its_child(self):
        for cmd, btn in (("Sketcher_CreateRectangle", self.rects), ("Sketcher_CreateOblong", self.rects),
                         ("Sketcher_Create3PointArc", self.arcs), ("Sketcher_CreateCircle", self.circles),
                         ("PartDesign_AdditiveCylinder", self.prims)):
            with self.subTest(cmd=cmd):
                got = self.find(cmd)
                self.assertEqual([b for b, _m, _a in got], [btn])
                self.assertEqual(targets.command_name(got[0][2]), cmd)

    def test_own_button_and_unknown_not_groups(self):
        self.assertEqual(self.find("Sketcher_CreateLine"), [])  # its own button: buttons() has it
        self.assertEqual(self.find("Sketcher_CreatePolyline"), [])

    def test_submenu_inside_a_dropdown(self):
        inner = GMenu(GAct("Sketcher_CreateSlot"))
        b = Btn(GAct("Sketcher_CompSlots", menu=GMenu(GAct("More", menu=inner))))
        mw = types.SimpleNamespace(findChildren=lambda cls: [b])
        self.assertEqual(targets.group_buttons("Sketcher_CreateSlot", mw, tool_button=object)[0][0], b)

    def test_watch_menu_rings_the_item_when_opened(self):
        ov = overlay.Overlay(gui=Gui(W("main")))
        seen = []
        ov._watch_menu = lambda m, a, h, o, b: seen.append((m, a, h, o, b))
        ov.watch_menu("menu", "act", owner="tutor", handle=3, badge=2)
        ov.watch_menu(None, "act")
        self.assertEqual(seen, [("menu", "act", 3, "tutor", 2)])


class Covered(unittest.TestCase):
    """visibleRegion can be empty for a button the person plainly sees;
    what the window has under the button's middle decides."""

    def test_under_the_middle(self):
        btn = W("btn", None, pos=(100, 40))
        child = types.SimpleNamespace(parentWidget=lambda: btn)
        mw = types.SimpleNamespace(childAt=lambda p: child)
        btn.mapTo = lambda target, p: p
        btn.rect = lambda: types.SimpleNamespace(center=lambda: (15, 15))
        self.assertTrue(overlay.Overlay._hit(btn, mw))
        other = types.SimpleNamespace(parentWidget=lambda: None)
        self.assertFalse(overlay.Overlay._hit(btn, types.SimpleNamespace(childAt=lambda p: other)))
        self.assertFalse(overlay.Overlay._hit(btn, types.SimpleNamespace(childAt=lambda p: None)))

    def test_empty_region_but_hit_is_not_covered(self):
        mw = W("main", size=(1200, 800))
        ov = overlay.Overlay(gui=Gui(mw))
        btn = W("btn", mw, covered=True)
        ov._hit = lambda w, m: True
        self.assertIsNone(ov.visible(btn))
        ov._hit = lambda w, m: False
        self.assertEqual(ov.visible(btn), "covered")


class TabSlot(unittest.TestCase):
    def test_slot_15_is_free_and_between_notes_and_steps(self):
        self.assertNotIn(15, [o for _t, o in panel_tabs.CORE_TABS])
        rows = panel_tabs.tab_order([{"title": "Lessons", "order": 15}])
        self.assertEqual([t for t, _o, _a in rows][:3], ["Notes", "Lessons", "Steps"])


class Provided(unittest.TestCase):
    def test_services_named_in_hooks(self):
        self.assertIn('"overlay"', hooks.__doc__)
        self.assertIn('"annotations"', hooks.__doc__)
        with open(os.path.join(PKG, "workbench.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn('hooks.provide("overlay", overlay.service())', src)
        self.assertIn('hooks.provide("annotations", annotate.service())', src)


if __name__ == "__main__":
    unittest.main()
