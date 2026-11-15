# SPDX-License-Identifier: LGPL-2.1-or-later
# The Placer driven through a small stand-in Qt and FreeCADGui: each layout
# places a panel, a workbench switch hides another workbench's panel and
# brings it back, the Combo View tab comes forward only the first time, and
# a task hands the tab back when it ends. The live check is on the Mac.
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentlink import layout  # noqa: E402


class Sig:
    def __init__(self):
        self.slots = []

    def connect(self, fn):
        self.slots.append(fn)

    def emit(self, *a):
        for fn in list(self.slots):
            fn(*a)


class W:
    """A widget: parent, shown, title, a property bag."""

    def __init__(self, parent=None, *a):
        self.parent, self.shown, self.props, self.max_w = parent, False, {}, None
        self._w = None

    def __getattr__(self, name):
        if name.startswith("set") or name in ("raise_", "installEventFilter", "deleteLater", "move", "place"):
            return lambda *a, **k: None
        raise AttributeError(name)

    def show(self):
        self.shown = True

    def hide(self):
        self.shown = False

    def setVisible(self, on):  # noqa: N802
        self.shown = bool(on)

    def isVisible(self):  # noqa: N802
        return self.shown

    def isFloating(self):  # noqa: N802
        return False

    def setMaximumWidth(self, w):  # noqa: N802
        self.max_w = w

    def property(self, k):
        return self.props.get(k)

    def setProperty(self, k, v):  # noqa: N802
        self.props[k] = v

    def setWidget(self, w):  # noqa: N802
        self._w = w

    def widget(self):
        return self._w

    def parentWidget(self):  # noqa: N802
        return self.parent

    def takeWidget(self):  # noqa: N802
        w, self._w = self._w, None
        return w

    def rect(self):
        return types.SimpleNamespace(width=lambda: 1000, height=lambda: 700)


class Tabs(W):
    def __init__(self, *a):
        super().__init__()
        self.pages, self.cur = [], -1
        self.currentChanged = Sig()

    def addTab(self, w, title):  # noqa: N802
        self.pages.append((w, title))
        if self.cur < 0:
            self.cur = 0
        return len(self.pages) - 1

    def count(self):
        return len(self.pages)

    def tabText(self, i):  # noqa: N802
        return self.pages[i][1] if 0 <= i < len(self.pages) else ""

    def indexOf(self, w):  # noqa: N802
        return next((i for i, (x, _t) in enumerate(self.pages) if x is w), -1)

    def removeTab(self, i):  # noqa: N802
        self.pages.pop(i)
        self.cur = min(self.cur, len(self.pages) - 1)

    def setCurrentIndex(self, i):  # noqa: N802
        if i != self.cur:
            self.cur = i
            self.currentChanged.emit(i)

    def setCurrentWidget(self, w):  # noqa: N802
        self.setCurrentIndex(self.indexOf(w))

    def current(self):
        return self.tabText(self.cur)

    def currentIndex(self):  # noqa: N802
        return self.cur


class Meta:
    def __init__(self, name):
        self.name = name

    def className(self):  # noqa: N802
        return self.name


class Dock(W):
    def __init__(self, title="", parent=None, name=None, cls="QDockWidget"):
        super().__init__(parent)
        self.title = title
        self.name = title if name is None else name
        self.cls = cls
        self.w = 270

    def metaObject(self):  # noqa: N802
        return Meta(self.cls)

    def width(self):
        return self.w

    def windowTitle(self):  # noqa: N802
        return self.title

    def objectName(self):  # noqa: N802
        return self.name

    def findChild(self, cls, name=None):
        return getattr(self, "tabs", None)

    def findChildren(self, cls):
        return [self.tabs] if getattr(self, "tabs", None) else []


class Main(W):
    def __init__(self, combo=True, name="Std_ComboView", cls="QDockWidget"):
        super().__init__()
        self.workbenchActivated = Sig()
        self.docks = [Dock("Report view", name="Std_ReportView")]
        self.right = []
        self.resized = []
        if combo:
            c = Dock("Combo View", name=name, cls=cls)
            c.shown = True
            self.combo_dock = c
            c.tabs = Tabs()
            c.tabs.addTab(W(), "Model")
            c.tabs.addTab(W(), "Tasks")
            self.docks.append(c)
            self.combo = c.tabs
        self.area = W()

    def width(self):
        return 900

    def height(self):
        return 700

    def isMaximized(self):  # noqa: N802
        return False

    isFullScreen = isMaximized

    def findChildren(self, cls):
        return list(self.docks)

    def addDockWidget(self, area, dock):  # noqa: N802
        self.right.append(dock)

    def tabifyDockWidget(self, a, b):  # noqa: N802
        pass

    def resizeDocks(self, docks, sizes, orientation):  # noqa: N802
        self.resized.append(sizes[0])
        docks[0].w = sizes[0]

    def centralWidget(self):  # noqa: N802
        return self.area


class Slide(W):
    def __init__(self, area, on_toggle=None, on_open=None):
        super().__init__(area)
        self.tabs = Tabs()
        self.on_toggle, self.on_open = on_toggle, on_open

    def set_open(self, on):
        self.shown = bool(on) and self.tabs.count() > 0
        self.on_open(self.shown)

    def toggle(self):
        self.set_open(not self.shown)
        self.on_toggle(self.shown)


class Params:
    def __init__(self):
        self.v = {}

    def GetString(self, k, d=""):  # noqa: N802
        return self.v.get(k, d)


class Placer(unittest.TestCase):
    def setUp(self):
        self.params = Params()
        self.mw = Main()
        self.wb = ["PartDesignWorkbench"]
        self.task = [False]
        gui = types.SimpleNamespace(getMainWindow=lambda: self.mw,
                                    activeWorkbench=lambda: types.SimpleNamespace(name=lambda: self.wb[0]),
                                    Control=types.SimpleNamespace(activeDialog=lambda: self.task[0]))
        core = types.SimpleNamespace(Qt=types.SimpleNamespace(RightDockWidgetArea=2, ScrollBarAlwaysOff=1, Horizontal=1),
                                     QTimer=lambda *a: types.SimpleNamespace(setInterval=lambda *a: None, timeout=Sig(), start=lambda: None),
                                     QObject=object, QEvent=types.SimpleNamespace(Close=19, Resize=14))
        core.QTimer.singleShot = lambda ms, fn: fn()
        widgets = types.SimpleNamespace(QDockWidget=Dock, QTabWidget=Tabs, QScrollArea=W, QFrame=types.SimpleNamespace(NoFrame=0),
                                        QSizePolicy=types.SimpleNamespace(Expanding=7, Ignored=13, Preferred=5))
        self.saved = (layout._qt, layout._gui, layout.read, dict(layout._CLASSES))
        self.core = core
        layout._qt = lambda: (core, widgets)
        layout._gui = lambda: gui
        layout.read = lambda params=None: layout.normalise(self.params.GetString(layout.PARAM, layout.DEFAULT))
        layout._CLASSES.clear()
        layout._CLASSES.update(Watch=lambda **k: W(), Slide=Slide)
        self.p = layout.Placer()

    def tearDown(self):
        layout._qt, layout._gui, layout.read, classes = self.saved
        layout._CLASSES.clear()
        layout._CLASSES.update(classes)

    def dock(self, title):
        d = Dock(title)
        d.setWidget(W())
        return d

    def switch(self, wb):
        self.wb[0] = wb
        self.mw.workbenchActivated.emit(wb)

    def test_right_capped_and_only_in_its_workbench(self):
        self.params.v["PanelLayout"] = "right"
        d = self.dock("ScanRuler")
        content = d.widget()
        self.switch("ScanRulerWorkbench")
        self.assertEqual(self.p.show("sr", d, "ScanRulerWorkbench"), "right")
        self.assertTrue(d.shown)
        self.assertEqual(d.max_w, 360)
        self.assertIsNot(d.widget(), content)  # in a frame that follows the dock's width
        self.assertIs(d.widget().widget(), content)
        self.switch("PartDesignWorkbench")
        self.assertFalse(d.shown)
        self.switch("ScanRulerWorkbench")
        self.assertTrue(d.shown)

    def test_closed_stays_closed_until_asked(self):
        self.params.v["PanelLayout"] = "right"
        d = self.dock("Make")
        self.switch("WorkshopMakeWorkbench")
        self.p.show("make", d, "WorkshopMakeWorkbench")
        self.p._closed(d)
        d.hide()
        self.switch("PartDesignWorkbench")
        self.switch("WorkshopMakeWorkbench")
        self.assertFalse(d.shown)
        self.p.show("make", d, "WorkshopMakeWorkbench")
        self.assertTrue(d.shown)

    def test_left_tab_forward_first_time_then_remembered(self):
        self.params.v["PanelLayout"] = "left-tab"
        d = self.dock("ScanRuler")
        content = d.widget()
        self.switch("ScanRulerWorkbench")
        self.assertEqual(self.p.show("sr", d, "ScanRulerWorkbench"), "left-tab")
        self.p.reveal("sr")  # as the workbench opens: Memory's choice stands
        c = self.mw.combo
        self.assertEqual([c.tabText(i) for i in range(c.count())], ["Model", "Tasks", "ScanRuler"])
        self.assertEqual(c.current(), "ScanRuler")
        self.assertFalse(d.shown)
        c.setCurrentIndex(0)  # the person turns to Model
        self.switch("PartDesignWorkbench")
        self.assertEqual([c.tabText(i) for i in range(c.count())], ["Model", "Tasks"])
        self.assertIs(d.widget(), content)  # back in its dock
        self.switch("ScanRulerWorkbench")
        self.assertIn("ScanRuler", [c.tabText(i) for i in range(c.count())])
        self.assertEqual(c.current(), "Model")

    def test_task_wins_then_hands_back(self):
        self.params.v["PanelLayout"] = "left-tab"
        d = self.dock("Texturizer")
        self.switch("TexturizerWorkbench")
        self.p.show("tx", d, "TexturizerWorkbench")
        c = self.mw.combo
        self.assertEqual(c.current(), "Texturizer")
        self.task[0] = True
        self.p.memory.task(True, "TexturizerWorkbench")
        c.setCurrentIndex(1)  # FreeCAD: Tasks
        c.setCurrentIndex(0)  # FreeCAD: Model as the task closes
        self.task[0] = False
        self.assertEqual(self.p.memory.task(False, "TexturizerWorkbench"), "Texturizer")

    def test_default_is_left_tab_and_finds_std_combo_view(self):
        d = self.dock("ScanRuler")
        self.switch("ScanRulerWorkbench")
        self.assertEqual(self.p.show("sr", d, "ScanRulerWorkbench"), "left-tab")

    def test_combo_view_found_by_its_class(self):
        self.mw = Main(name="SomethingElse", cls="Gui::DockWnd::ComboView")
        self.assertIs(layout.combo_tabs(self.mw), self.mw.combo)

    def test_outer_tabs_chosen_over_the_property_editors(self):
        # FreeCAD 1.1: no "combiTab" by name, and the property editor's
        # View/Data tabs (inside the Model tab) can come first.
        c = self.mw.combo_dock
        outer = c.tabs
        inner = Tabs()
        inner.parent = W(parent=outer)
        c.findChild = lambda cls, name=None: None
        c.findChildren = lambda cls: [inner, outer]
        self.assertIs(layout.combo_tabs(self.mw), outer)

    def test_empty_tasks_gives_way(self):
        self.params.v["PanelLayout"] = "right"
        self.mw.combo.setCurrentIndex(1)  # Tasks, no task running
        self.p.show("sr", self.dock("ScanRuler"), "ScanRulerWorkbench")
        self.assertEqual(self.mw.combo.current(), "Model")
        self.task[0] = True
        self.mw.combo.setCurrentIndex(1)
        self.switch("ScanRulerWorkbench")
        self.assertEqual(self.mw.combo.current(), "Tasks")  # a task runs: left to FreeCAD

    def test_slide_out_narrows_the_combo_view(self):
        self.params.v["PanelLayout"] = "left-slide"
        self.mw.combo_dock.w = 270
        self.switch("SafetyNetWorkbench")
        self.p.show("sn", self.dock("SafetyNet"), "SafetyNetWorkbench")
        self.assertEqual(self.mw.combo_dock.w, 220)
        self.p.toggle()
        self.assertEqual(self.mw.combo_dock.w, 270)

    def test_left_slide_toggles(self):
        self.params.v["PanelLayout"] = "left-slide"
        d = self.dock("SafetyNet")
        self.switch("SafetyNetWorkbench")
        self.assertEqual(self.p.show("sn", d, "SafetyNetWorkbench"), "left-slide")
        self.assertTrue(self.p.slide.shown)
        self.assertFalse(self.p.toggle())
        self.switch("PartDesignWorkbench")
        self.assertEqual(self.p.slide.tabs.count(), 0)
        self.switch("SafetyNetWorkbench")
        self.assertFalse(self.p.slide.shown)  # left closed there

    def test_setting_changed_takes_effect_at_the_next_switch(self):
        self.params.v["PanelLayout"] = "right"
        d = self.dock("ScanRuler")
        self.switch("ScanRulerWorkbench")
        self.p.show("sr", d, "ScanRulerWorkbench")
        self.params.v["PanelLayout"] = "left-tab"
        self.switch("PartDesignWorkbench")
        self.switch("ScanRulerWorkbench")
        self.assertEqual(self.p.entries["sr"]["where"], "left-tab")
        self.assertNotEqual(d.max_w, 360)  # off the right side's cap

    def test_no_combo_view_falls_back_to_the_right(self):
        self.mw = Main(combo=False)
        self.params.v["PanelLayout"] = "left-tab"
        self.assertEqual(self.p.show("x", self.dock("X"), "XWorkbench"), "right")


if __name__ == "__main__":
    unittest.main()
