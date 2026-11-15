# SPDX-License-Identifier: LGPL-2.1-or-later
# gui_input without FreeCAD or a real Qt: the steps checked, the targets
# parsed, the y-flip and pixel-ratio maths, finding a widget by what it
# shows, the answer's cap, and delivery through stand-in Qt objects handed
# in (a drag's press, moves and release to one widget, a dialog in front
# refusing a target outside it, keys to the focused widget).
import json
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import gui_input as gi
from agentlink.protocol import ToolError


class Steps(unittest.TestCase):
    def bad(self, steps):
        with self.assertRaises(ToolError) as e:
            gi.parse_steps(steps)
        self.assertEqual(e.exception.code, "invalid_input")
        return e.exception.message

    def test_every_kind(self):
        out = gi.parse_steps([
            {"click": {"view": [10, 20]}, "button": "Right", "double": True, "modifiers": ["Shift", "ctrl", "shift"]},
            {"press": {"widget": {"objectName": "grip"}, "at": [3, 4]}},
            {"move": {"view_world": [1, 2, 3]}},
            {"release": {"window": [5, 6]}, "button": "middle"},
            {"drag": {"from": {"view": [0, 0]}, "to": {"view": [9, 9]}}},
            {"scroll": {"view": [1, 1]}, "dy": -2},
            {"key": "esc", "modifiers": ["alt"]},
            {"key": "a", "target": {"widget": {"class": "QLineEdit"}}},
            {"type": "12.5"},
            {"wait": 3000},
            {"shot": "after.png"},
        ])
        self.assertEqual([s["do"] for s in out], ["click", "press", "move", "release", "drag", "scroll", "key", "key", "type", "wait", "shot"])
        self.assertEqual(out[0]["button"], "right")
        self.assertEqual(out[0]["mods"], ["shift", "ctrl"])
        self.assertTrue(out[0]["double"])
        self.assertEqual(out[1]["target"], {"kind": "widget", "value": {"objectName": "grip"}, "at": [3.0, 4.0]})
        self.assertEqual(out[2]["target"]["value"], [1.0, 2.0, 3.0])
        self.assertEqual(out[3]["button"], "middle")
        self.assertEqual((out[4]["steps"], out[4]["button"]), (gi.DRAG_STEPS, "left"))
        self.assertEqual(out[5]["dy"], -2.0)
        self.assertEqual(out[6]["key"], ("name", "Escape"))
        self.assertEqual(out[7]["key"], ("char", "a"))
        self.assertIsNone(out[8]["target"])
        self.assertEqual(out[9]["ms"], 3000)
        self.assertEqual(out[10]["name"], "after")

    def test_refusals(self):
        self.bad([])
        self.bad("click")
        self.bad([{"wait": 1}] * (gi.MAX_STEPS + 1))
        self.assertIn("one of", self.bad([{"tap": {"view": [1, 1]}}]))
        self.bad([{"click": {"view": [1, 1]}, "press": {"view": [1, 1]}}])
        self.assertIn("steps[0].dy", self.bad([{"click": {"view": [1, 1]}, "dy": 1}]))
        self.bad([{"click": {"view": [1, 1]}, "button": "side"}])
        self.bad([{"click": {"view": [1, 1]}, "modifiers": ["hyper"]}])
        self.bad([{"click": {"view": [1, 1]}, "double": "yes"}])
        self.bad([{"wait": 3001}])
        self.bad([{"wait": True}])
        self.bad([{"wait": 3000}] * 7)
        self.bad([{"shot": "../x"}])
        self.bad([{"shot": "a/b"}])
        self.bad([{"scroll": {"view": [1, 1]}, "dy": 0}])
        self.bad([{"scroll": {"view": [1, 1]}}])
        self.bad([{"drag": {"from": {"view": [1, 1]}}}])
        self.bad([{"drag": {"from": {"view": [1, 1]}, "to": {"view": [2, 2]}, "steps": 0}}])
        self.bad([{"drag": {"from": {"view": [1, 1]}, "to": {"view": [2, 2]}, "speed": 3}}])
        self.bad([{"key": "Return Return"}])
        self.bad([{"type": ""}])

    def test_targets(self):
        for t in ({"view": [1]}, {"view": [1, "2"]}, {"view": [1, float("nan")]}, {"view_world": [1, 2]},
                  {"view": [1, 1], "window": [1, 1]}, {"view": [1, 1], "at": [1, 1]}, {"widget": {}},
                  {"widget": {"name": "x"}}, {"widget": {"text": ""}}, {"widget": {"text": "OK"}, "at": [1]}, [1, 2], {}):
            with self.assertRaises(ToolError, msg=repr(t)):
                gi.parse_target(t, "t")
        self.assertEqual(gi.parse_target({"window": [3, 4]}, "t"), {"kind": "window", "value": [3.0, 4.0]})


class Maths(unittest.TestCase):
    def test_flip_and_ratio(self):
        # Coin's viewport in device pixels, origin bottom-left; the widget 400×300 logical at 2×.
        self.assertEqual(gi.view_point(200, 600, 400, 300, (800, 600)), (100.0, 0.0))
        self.assertEqual(gi.view_point(0, 0, 400, 300, (800, 600)), (0.0, 300.0))
        self.assertEqual(gi.view_point(400, 300, 400, 300, (800, 600)), (200.0, 150.0))
        # Coin's size unknown: the widget's pixel ratio.
        self.assertEqual(gi.view_point(400, 300, 400, 300, None, 2.0), (200.0, 150.0))
        self.assertEqual(gi.view_point(50, 100, 400, 300, None, 1.0), (50.0, 200.0))
        self.assertEqual(gi.view_point(50, 100, 400, 300, (0, 0), 1.0), (50.0, 200.0))

    def test_inside_lerp_notches(self):
        self.assertTrue(gi.inside(0, 0, 10, 10))
        self.assertFalse(gi.inside(10, 5, 10, 10))
        self.assertFalse(gi.inside(-1, 5, 10, 10))
        pts = gi.lerp_points((0, 0), (12, 24), 12)
        self.assertEqual(len(pts), 12)
        self.assertEqual(pts[0], (1, 2))
        self.assertEqual(pts[-1], (12, 24))
        self.assertEqual(gi.notches_to_angle(1), 120)
        self.assertEqual(gi.notches_to_angle(-0.5), -60)

    def test_key_names(self):
        self.assertEqual(gi.key_name("Return"), ("name", "Return"))
        self.assertEqual(gi.key_name("pgdown"), ("name", "PageDown"))
        self.assertEqual(gi.key_name("f2"), ("name", "F2"))
        self.assertEqual(gi.key_name("+"), ("char", "+"))
        with self.assertRaises(ToolError):
            gi.key_name("é")


class Matching(unittest.TestCase):
    def props(self, **k):
        base = {"objectName": "", "text": "", "toolTip": "", "classes": ["QWidget"], "under": []}
        base.update(k)
        return base

    def test_fields(self):
        p = self.props(objectName="ok", text="&Apply changes", toolTip="<b>Apply</b> the changes now",
                       classes=["Gui::PrefSpinBox", "QDoubleSpinBox"], under=["Tasks", "FreeCAD"])
        self.assertTrue(gi.widget_match(p, {"text": "apply  CHANGES"}))
        self.assertFalse(gi.widget_match(p, {"text": "apply"}))
        self.assertTrue(gi.widget_match(p, {"text": "apply"}, loose=True))
        self.assertTrue(gi.widget_match(p, {"toolTip": "apply the"}))
        self.assertTrue(gi.widget_match(p, {"class": "prefspinbox"}))
        self.assertTrue(gi.widget_match(p, {"class": "QDoubleSpinBox", "under": "tasks"}))
        self.assertFalse(gi.widget_match(p, {"class": "SpinBox"}))
        self.assertFalse(gi.widget_match(p, {"under": "Report view"}))
        self.assertFalse(gi.widget_match(p, {"objectName": "OK"}))

    def test_whole_text_first(self):
        cands = [("long", self.props(text="OK and more")), ("exact", self.props(text="OK"))]
        self.assertEqual(gi.pick(cands, {"text": "ok"}), "exact")
        self.assertEqual(gi.pick(cands[:1], {"text": "ok"}), "long")
        self.assertIsNone(gi.pick(cands, {"objectName": "none"}))


class Cap(unittest.TestCase):
    def test_capped(self):
        steps = [{"i": i, "do": "click", "hit": {"class": "Gui::View3DInventorViewer" * 3, "text": "x" * 200, "global": [i, i]}} for i in range(60)]
        out = gi.cap_answer({"steps": steps, "note": "n" * 500})
        self.assertLessEqual(len(json.dumps(out, ensure_ascii=False, separators=(",", ":"))), gi.ANSWER_MAX)
        self.assertEqual(out["steps"][0]["i"], 0)
        self.assertEqual(out["steps"][-1]["i"], 59)
        self.assertEqual(out["steps_left_out"], 60 - len(out["steps"]))

    def test_small_unchanged(self):
        a = {"steps": [{"i": 0, "do": "wait"}]}
        self.assertEqual(gi.cap_answer(a), a)


# ---- stand-in Qt ----------------------------------------------------------------------------

class P:
    def __init__(self, x=0, y=0):
        if isinstance(x, P):
            x, y = x._x, x._y
        self._x, self._y = float(x), float(y)

    def x(self):
        return self._x

    def y(self):
        return self._y


class Flag(int):
    def __or__(self, o):
        return Flag(int(self) | int(o))


class Meta:
    def __init__(self, name):
        self.name = name

    def className(self):
        return self.name

    def superClass(self):
        return None


class Widget:
    def __init__(self, name, ox, oy, w, h, parent=None, cls="QWidget", focus=0):
        self.name, self.ox, self.oy, self.w, self.h, self.parent, self.cls, self.focus = name, ox, oy, w, h, parent, cls, focus
        self.kids = []
        self.focused = False
        if parent is not None:
            parent.kids.append(self)

    # geometry: ox, oy are global
    def mapToGlobal(self, p):
        return P(p.x() + self.ox, p.y() + self.oy)

    def mapFromGlobal(self, p):
        return P(p.x() - self.ox, p.y() - self.oy)

    def window(self):
        w = self
        while w.parent is not None:
            w = w.parent
        return w

    def mapTo(self, other, p):
        return P(p.x() + self.ox - other.ox, p.y() + self.oy - other.oy)

    def mapFrom(self, other, p):
        return P(p.x() + other.ox - self.ox, p.y() + other.oy - self.oy)

    def childAt(self, p):
        return None

    def objectName(self):
        return self.name

    def metaObject(self):
        return Meta(self.cls)

    def isVisible(self):
        return True

    def width(self):
        return self.w

    def height(self):
        return self.h

    def isEnabled(self):
        return True

    def focusPolicy(self):
        return self.focus

    def setFocus(self, reason=None):
        self.focused = True

    def isWindow(self):
        return self.parent is None

    def parentWidget(self):
        return self.parent

    def toolTip(self):
        return ""

    def windowTitle(self):
        return self.name

    def isAncestorOf(self, w):
        p = w.parent
        while p is not None:
            if p is self:
                return True
            p = p.parent
        return False

    def findChildren(self, cls):
        out = []
        for k in self.kids:
            out += [k] + k.findChildren(cls)
        return out

    def focusWidget(self):
        return next((k for k in self.findChildren(None) if k.focused), None)


def fake_qt(sent, app_state):
    Qt = types.SimpleNamespace(
        MouseButton=types.SimpleNamespace(NoButton=Flag(0), LeftButton=Flag(1), RightButton=Flag(2), MiddleButton=Flag(4)),
        KeyboardModifier=types.SimpleNamespace(NoModifier=Flag(0), ShiftModifier=Flag(0x02000000), ControlModifier=Flag(0x04000000), AltModifier=Flag(0x08000000), MetaModifier=Flag(0x10000000)),
        Key=types.SimpleNamespace(Key_Return=0x01000004, Key_Escape=0x01000000),
        FocusPolicy=types.SimpleNamespace(ClickFocus=2),
        FocusReason=types.SimpleNamespace(MouseFocusReason=0, OtherFocusReason=7),
        ScrollPhase=types.SimpleNamespace(NoScrollPhase=0),
    )
    QEvent = types.SimpleNamespace(Type=types.SimpleNamespace(**{n: n for n in ("MouseButtonPress", "MouseButtonRelease", "MouseButtonDblClick", "MouseMove", "KeyPress", "KeyRelease")}))

    class QMouseEvent:
        def __init__(self, t, lp, wp, gp, b, bs, m):
            self.t, self.lp, self.gp, self.b, self.bs, self.m = t, lp, gp, b, bs, m

    class QKeyEvent:
        def __init__(self, t, key, m, text=""):
            self.t, self.key, self.m, self.text = t, key, m, text

    class QWheelEvent:
        def __init__(self, *a):
            self.t, self.a = "Wheel", a

    class QApplication:
        @staticmethod
        def instance():
            return app_state["app"]

        @staticmethod
        def sendEvent(w, ev):
            sent.append((w.name, ev))
            return True

        @staticmethod
        def widgetAt(p):
            return app_state.get("main")

    class QTimer:
        def __init__(self):
            self.timeout = types.SimpleNamespace(connect=lambda f: None)

        def setInterval(self, ms):
            pass

        def start(self):
            pass

        def stop(self):
            pass

    QtCore = types.SimpleNamespace(
        Qt=Qt, QEvent=QEvent, QPointF=P, QPoint=P, QTimer=QTimer,
        QThread=types.SimpleNamespace(currentThread=lambda: types.SimpleNamespace(loopLevel=lambda: 1)),
        QEventLoop=types.SimpleNamespace(ProcessEventsFlag=types.SimpleNamespace(AllEvents=0)),
        QCoreApplication=types.SimpleNamespace(processEvents=lambda flags, ms: None),
    )
    QtGui = types.SimpleNamespace(QMouseEvent=QMouseEvent, QKeyEvent=QKeyEvent, QWheelEvent=QWheelEvent)
    QtWidgets = types.SimpleNamespace(QApplication=QApplication, QWidget=Widget, QDockWidget=type("QDockWidget", (Widget,), {}),
                                      QAbstractScrollArea=type("QAbstractScrollArea", (Widget,), {}), QMdiArea=type("QMdiArea", (Widget,), {}))
    return types.SimpleNamespace(QtCore=QtCore, QtGui=QtGui, QtWidgets=QtWidgets)


class Delivery(unittest.TestCase):
    def setUp(self):
        gi.HELD.update({"widget": None, "buttons": []})
        self.addCleanup(gi.HELD.update, {"widget": None, "buttons": []})
        self.sent = []
        self.mw = Widget("main", 100, 50, 1200, 800)
        self.vp = Widget("viewport", 400, 150, 600, 400, parent=self.mw, cls="QOpenGLWidget", focus=2)
        self.edit = Widget("edit", 120, 600, 100, 20, parent=self.mw, cls="QLineEdit", focus=2)
        self.state = {"modal": None, "popup": None, "main": self.mw}
        st = self.state
        self.state["app"] = types.SimpleNamespace(activePopupWidget=lambda: st["popup"], activeModalWidget=lambda: st["modal"],
                                                  topLevelWidgets=lambda: [self.mw], focusWidget=lambda: None)
        self.qt = fake_qt(self.sent, self.state)
        gv = types.SimpleNamespace(viewport=lambda: self.vp)
        view = types.SimpleNamespace(getPointOnViewport=lambda v: (v[0] * 2, v[1] * 2), getSize=lambda: (1200, 800), graphicsView=lambda: gv)
        gui = types.SimpleNamespace(getMainWindow=lambda: self.mw, ActiveDocument=types.SimpleNamespace(ActiveView=view))
        self.run = gi.Run(self.qt, gui, lambda *a: a, lambda: None, list, None, lambda body: False, "/nonexistent")

    def kinds(self):
        return [(w, ev.t) for w, ev in self.sent]

    def test_drag_goes_to_the_pressed_widget(self):
        out = self.run.run(gi.parse_steps([{"drag": {"from": {"view": [10, 20]}, "to": {"window": [100, 100]}, "steps": 4}}]))
        # The hand arrives first, as a real one does (hover-lit grips take the press).
        self.assertEqual(self.kinds(), [("viewport", "MouseMove"), ("viewport", "MouseButtonPress")] + [("viewport", "MouseMove")] * 4 + [("viewport", "MouseButtonRelease")])
        press, moves, rel = self.sent[1][1], [e for _w, e in self.sent[2:6]], self.sent[6][1]
        self.assertEqual((press.lp.x(), press.lp.y()), (10.0, 20.0))
        self.assertEqual((press.gp.x(), press.gp.y()), (410.0, 170.0))
        self.assertEqual(int(press.b), 1)
        self.assertTrue(all(int(m.bs) == 1 and int(m.b) == 0 for m in moves))
        # window [100, 100] is global (200, 150): (-200, 0) in the viewport, held by the grab.
        self.assertEqual((rel.lp.x(), rel.lp.y()), (-200.0, 0.0))
        self.assertEqual(int(rel.bs), 0)
        self.assertTrue(self.vp.focused)
        self.assertEqual(out["steps"][0]["hit"]["class"], "QOpenGLWidget")
        self.assertEqual(out["steps"][0]["hit"]["global"], [410, 170])
        self.assertNotIn("held", out)

    def test_view_world_flipped(self):
        # (100, 50, 0) projects to Coin's (200, 100) of 1200×800: logical (100, 350) of 600×400.
        self.run.run(gi.parse_steps([{"click": {"view_world": [100, 50, 0]}}]))
        ev = self.sent[0][1]
        self.assertEqual((ev.lp.x(), ev.lp.y()), (100.0, 350.0))
        self.assertEqual(self.kinds(), [("viewport", "MouseMove"), ("viewport", "MouseButtonPress"), ("viewport", "MouseButtonRelease")])

    def test_double_click(self):
        self.run.run(gi.parse_steps([{"click": {"view": [5, 5]}, "double": True}]))
        self.assertEqual([t for _w, t in self.kinds()], ["MouseMove", "MouseButtonPress", "MouseButtonRelease", "MouseButtonDblClick", "MouseButtonRelease"])
        self.assertEqual(int(self.sent[3][1].bs), 1)
        self.assertEqual(gi.HELD["buttons"], [])

    def test_outside_the_view_refused(self):
        out = self.run.run(gi.parse_steps([{"click": {"view": [700, 10]}}]))
        self.assertIn("outside the 3D view", out["steps"][0]["error"])
        self.assertEqual(self.sent, [])

    def test_press_held_across_steps(self):
        out = self.run.run(gi.parse_steps([{"press": {"view": [5, 5]}, "button": "right"}, {"move": {"view": [6, 6]}}]))
        self.assertEqual(out["held"], ["right"])
        self.assertEqual(int(self.sent[1][1].bs), 2)
        self.run.run(gi.parse_steps([{"release": {"view": [7, 7]}, "button": "right"}]))
        self.assertEqual(gi.HELD["buttons"], [])

    def test_dialog_in_front_refuses_targets_outside(self):
        dlg = Widget("Pad parameters", 300, 300, 200, 100, cls="QDialog")
        ok = Widget("ok", 350, 360, 60, 20, parent=dlg, cls="QPushButton")
        ok.text = lambda: "OK"
        self.state["modal"] = dlg
        self.state["app"].topLevelWidgets = lambda: [self.mw, dlg]
        out = self.run.run(gi.parse_steps([{"click": {"widget": {"text": "OK"}}}, {"click": {"view": [5, 5]}}, {"wait": 1}]))
        self.assertEqual(out["steps"][0]["hit"]["text"], "OK")
        self.assertIn("holds the window", out["steps"][1]["error"])
        self.assertEqual(len(out["steps"]), 2)  # stopped at the refusal
        self.assertEqual([w for w, _e in self.sent], ["ok", "ok", "ok"])  # a move onto it, press, release

    def test_keys_and_text_to_the_focused_widget(self):
        self.edit.focused = True
        self.run.run(gi.parse_steps([{"type": "Ab"}, {"key": "Return", "modifiers": ["shift"]}]))
        evs = [e for _w, e in self.sent]
        self.assertTrue(all(w == "edit" for w, _e in self.sent))
        self.assertEqual([(e.t, e.key, e.text) for e in evs[:4]], [("KeyPress", ord("A"), "A"), ("KeyRelease", ord("A"), "A"), ("KeyPress", ord("B"), "b"), ("KeyRelease", ord("B"), "b")])
        self.assertEqual(int(evs[0].m), 0x02000000)
        self.assertEqual((evs[4].key, evs[4].text, int(evs[4].m)), (0x01000004, "\r", 0x02000000))

    def test_unknown_key_named(self):
        out = self.run.run(gi.parse_steps([{"key": "Hyper"}]))
        self.assertIn("not a key Qt knows", out["steps"][0]["error"])


class Chain(Meta):
    def __init__(self, names):
        super().__init__(names[0])
        self.rest = names[1:]

    def superClass(self):
        return Chain(self.rest) if self.rest else None


class Rect:
    def __init__(self, x, y, w, h):
        self._r = (x, y, w, h)

    def x(self):
        return self._r[0]

    def y(self):
        return self._r[1]

    def width(self):
        return self._r[2]

    def height(self):
        return self._r[3]


class TabBar(Widget):
    def __init__(self, name, ox, oy, tabs, parent=None):
        super().__init__(name, ox, oy, 100 * len(tabs), 24, parent=parent, cls="QTabBar")
        self.tabs = tabs

    def metaObject(self):
        return Chain(["QTabBar", "QWidget"])

    def count(self):
        return len(self.tabs)

    def tabText(self, i):
        return self.tabs[i]

    def tabRect(self, i):
        return Rect(100 * i, 0, 100, 24)


class Ix:
    def __init__(self, model, row, col=0):
        self.m, self.r, self.c = model, row, col

    def row(self):
        return self.r

    def parent(self):
        return Ix(self.m, -1)

    def isValid(self):
        return self.r >= 0

    def sibling(self, r, c):
        return Ix(self.m, r, c)


class Model:
    def __init__(self, rows, checks=None):
        self.rows, self.checks = rows, checks or {}

    def rowCount(self, parent=None):
        return len(self.rows) if parent is None or not parent.isValid() else 0

    def columnCount(self, parent=None):
        return len(self.rows[0])

    def index(self, r, c, parent=None):
        return Ix(self, r, c)

    def data(self, ix, role=0):
        if role == 10:
            return self.checks.get(ix.r)
        return self.rows[ix.r][ix.c]

    def setData(self, ix, v, role):
        self.checks[ix.r] = int(v)
        return True


class ItemView(Widget):
    def __init__(self, name, ox, oy, model, parent=None, cls="QListWidget"):
        super().__init__(name, ox, oy, 200, 300, parent=parent, cls=cls)
        self.m = model
        self.vp = Widget(name + "-viewport", ox, oy, 200, 300, parent=self)
        self.scrolled = []

    def metaObject(self):
        return Chain([self.cls, "QAbstractItemView", "QAbstractScrollArea", "QWidget"])

    def model(self):
        return self.m

    def viewport(self):
        return self.vp

    def scrollTo(self, ix):
        self.scrolled.append(ix.r)

    def visualRect(self, ix):
        return Rect(0, 20 * ix.r, 200, 20)


class Targets(unittest.TestCase):
    def setUp(self):
        gi.HELD.update({"widget": None, "buttons": []})
        self.addCleanup(gi.HELD.update, {"widget": None, "buttons": []})
        self.sent = []
        self.mw = Widget("main", 100, 50, 1200, 800)
        self.dock = type("QDockWidget", (Widget,), {})("Agent Link", 0, 0, 354, 800, parent=self.mw)
        self.bar = TabBar("tabs", 10, 60, ["&Activity", "Notes", "Materials"], parent=self.dock)
        self.model = Model([["PLA", "1.24"], ["PETG", "1.27"], ["ASA", "1.07"]], {0: 0, 1: 0, 2: 2})
        self.view = ItemView("list", 10, 100, self.model, parent=self.dock)
        st = {"modal": None, "popup": None, "main": self.mw}
        st["app"] = types.SimpleNamespace(activePopupWidget=lambda: None, activeModalWidget=lambda: None,
                                          topLevelWidgets=lambda: [self.mw], focusWidget=lambda: None)
        self.qt = fake_qt(self.sent, st)
        self.qt.QtWidgets.QDockWidget = type(self.dock)
        Qt = self.qt.QtCore.Qt
        Qt.ItemDataRole = types.SimpleNamespace(DisplayRole=0, CheckStateRole=10)
        Qt.CheckState = types.SimpleNamespace(Unchecked=0, Checked=2)
        gui = types.SimpleNamespace(getMainWindow=lambda: self.mw, ActiveDocument=None)
        self.run = gi.Run(self.qt, gui, lambda *a: a, lambda: None, list, None, lambda body: False, "/nonexistent")

    def test_parse(self):
        self.assertEqual(gi.parse_target({"tab": {"text": "Materials", "under": "Agent Link"}}, "t")["kind"], "tab")
        t = gi.parse_target({"item": {"text": "PLA", "column": 0}, "check": True}, "t")
        self.assertEqual((t["kind"], t["check"]), ("item", True))
        for bad_ in ({"tab": {}}, {"tab": {"text": "A", "column": 1}}, {"item": {"text": "A", "column": -1}},
                     {"tab": {"text": "A"}, "check": True}, {"item": {"text": "A"}, "check": "yes"}):
            with self.assertRaises(ToolError):
                gi.parse_target(bad_, "t")

    def test_wait_says_split(self):
        with self.assertRaises(ToolError) as e:
            gi.parse_steps([{"wait": 5000}])
        self.assertIn("split it into several waits", str(e.exception))

    def test_tab_clicked_at_its_centre(self):
        out = self.run.run(gi.parse_steps([{"click": {"tab": {"text": "materials", "under": "Agent Link"}}}]))
        hit = out["steps"][0]["hit"]
        self.assertEqual((hit["class"], hit["tab"]), ("QTabBar", "Materials"))
        press = [e for w, e in self.sent if e.t == "MouseButtonPress"][0]
        self.assertEqual((press.lp.x(), press.lp.y()), (250.0, 12.0))
        self.assertEqual((press.gp.x(), press.gp.y()), (260.0, 72.0))
        self.assertTrue(all(w == "tabs" for w, _e in self.sent))
        # & ignored
        out = self.run.run(gi.parse_steps([{"click": {"tab": {"text": "Activity"}}}]))
        self.assertEqual(out["steps"][-1]["hit"]["tab"], "Activity")

    def test_tab_not_found(self):
        out = self.run.run(gi.parse_steps([{"click": {"tab": {"text": "Materials", "under": "Elsewhere"}}}]))
        self.assertIn("No visible tab", out["steps"][0]["error"])

    def test_item_row_clicked_and_scrolled_to(self):
        out = self.run.run(gi.parse_steps([{"click": {"item": {"text": "PETG"}}}]))
        hit = out["steps"][0]["hit"]
        self.assertEqual((hit["class"], hit["item"], hit["row"]), ("QListWidget", "PETG", 1))
        self.assertEqual(self.view.scrolled, [1])
        press = [e for w, e in self.sent if e.t == "MouseButtonPress"][0]
        self.assertEqual((press.lp.x(), press.lp.y()), (100.0, 30.0))
        self.assertTrue(all(w == "list-viewport" for w, _e in self.sent))
        self.assertNotIn("check", hit)

    def test_item_by_column(self):
        out = self.run.run(gi.parse_steps([{"click": {"item": {"text": "1.07", "column": 1}}}]))
        self.assertEqual(out["steps"][0]["hit"]["row"], 2)

    def test_check_falls_back_to_the_model(self):
        out = self.run.run(gi.parse_steps([{"click": {"item": {"text": "PLA"}, "check": True}}]))
        hit = out["steps"][0]["hit"]
        press = [e for w, e in self.sent if e.t == "MouseButtonPress"][0]
        self.assertLess(press.lp.x(), 20)  # on the box, left of the text
        self.assertIn("through the model", hit["check"])
        self.assertTrue(hit["checked"])
        self.assertEqual(self.model.checks[0], 2)

    def test_check_by_click(self):
        sent, model = self.sent, self.model
        real = model.data

        def data(ix, role=0):
            if role == 10 and ix.r == 2:
                flips = sum(1 for w, e in sent if e.t == "MouseButtonRelease")
                return 0 if flips % 2 else 2
            return real(ix, role)
        model.data = data
        out = self.run.run(gi.parse_steps([{"click": {"item": {"text": "ASA"}, "check": True}}]))
        hit = out["steps"][0]["hit"]
        self.assertEqual(hit["check"], "clicked")
        self.assertFalse(hit["checked"])


if __name__ == "__main__":
    unittest.main()
