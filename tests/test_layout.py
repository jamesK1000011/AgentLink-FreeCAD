# SPDX-License-Identifier: LGPL-2.1-or-later
# The panel layout setting and its rules, without a window: the setting
# read with its default, which panels show per workbench, which tab comes
# forward, Agent Link's tabs per workbench, one credit line, and the Report
# view opening itself on a problem line.
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentlink import hooks, layout, panel_tabs, report_watch  # noqa: E402


class Params:
    def __init__(self, **kw):
        self.v = dict(kw)

    def GetString(self, k, d=""):  # noqa: N802
        return self.v.get(k, d)

    def GetBool(self, k, d=False):  # noqa: N802
        return self.v.get(k, d)

    def SetBool(self, k, v):  # noqa: N802
        self.v[k] = v


class Setting(unittest.TestCase):
    def test_default_is_left_tab(self):
        self.assertEqual(layout.read(Params()), "left-tab")
        self.assertEqual(layout.read(Params(PanelLayout="nonsense")), "left-tab")
        self.assertEqual(layout.read(), "left-tab")  # no FreeCAD here
        self.assertFalse(layout.is_set(Params()))

    def test_values(self):
        for v in ("right", "left-tab", "left-slide"):
            self.assertEqual(layout.read(Params(PanelLayout=v)), v)
        self.assertEqual(layout.normalise(" Left_Tab "), "left-tab")
        self.assertTrue(layout.is_set(Params(PanelLayout="left-slide")))

    def test_widths(self):
        self.assertEqual(layout.width_cap("right"), 360)
        self.assertEqual(layout.width_cap("left-tab"), 300)
        self.assertEqual(layout.width_cap("left-slide"), 300)
        # The slide-out at most 300 px over the 3D view, half of a narrow one.
        self.assertEqual(layout.slide_width(1000), 300)
        self.assertEqual(layout.slide_width(500), 250)
        self.assertLessEqual(layout.CONTENT_MIN, layout.SLIDE_MAX)

    def test_combo_view_found_by_name_or_class(self):
        self.assertTrue(layout.is_combo("Std_ComboView"))  # FreeCAD 1.x
        self.assertTrue(layout.is_combo("Combo View"))
        self.assertTrue(layout.is_combo("", "Gui::DockWnd::ComboView"))
        self.assertFalse(layout.is_combo("Std_ReportView", "QDockWidget"))

    def test_an_empty_tasks_tab_gives_way_to_model(self):
        self.assertEqual(layout.unstick(["Model", "Tasks"], "Tasks", False), "Model")
        self.assertIsNone(layout.unstick(["Model", "Tasks"], "Tasks", True))  # a task runs: FreeCAD's
        self.assertIsNone(layout.unstick(["Model", "Tasks", "ScanRuler"], "ScanRuler", False))

    def test_window_size_kept(self):
        self.assertEqual(layout.size_to_restore((856, 900), (1414, 900), False), (856, 900))
        self.assertIsNone(layout.size_to_restore((856, 900), (1414, 900), True))
        self.assertIsNone(layout.size_to_restore((856, 900), (856, 900), False))


class WhichPanels(unittest.TestCase):
    def test_only_the_active_workbenchs(self):
        panels = {"ScanRulerDock": "ScanRulerWorkbench", "TexturizerSidebar": "TexturizerWorkbench",
                  "AgentLinkPanel": layout.EVERYWHERE, "WorkshopMakeDock": ("WorkshopMakeWorkbench",)}
        self.assertEqual(layout.shown("TexturizerWorkbench", panels), ["TexturizerSidebar", "AgentLinkPanel"])
        self.assertEqual(layout.shown("PartDesignWorkbench", panels), ["AgentLinkPanel"])
        self.assertEqual(layout.shown("WorkshopMakeWorkbench", panels), ["AgentLinkPanel", "WorkshopMakeDock"])


class Forward(unittest.TestCase):
    def test_first_time_then_remembered(self):
        m = layout.Memory()
        self.assertEqual(m.opened("ScanRulerWorkbench", "ScanRuler"), "ScanRuler")
        m.chose("ScanRulerWorkbench", "Model")
        self.assertEqual(m.opened("ScanRulerWorkbench", "ScanRuler"), "Model")

    def test_tasks_win_then_hand_back(self):
        m = layout.Memory()
        m.opened("wb", "Texturizer")
        self.assertEqual(m.task(True, "wb"), "Tasks")  # a task starts: Tasks forward
        self.assertIsNone(m.task(True, "wb"))
        m.chose("wb", "Tasks")
        m.chose("wb", "Model")  # FreeCAD turning to Model as the task closes
        self.assertEqual(m.task(False, "wb"), "Texturizer")
        self.assertIsNone(m.task(False, "wb"))

    def test_slide_open_first_then_as_left(self):
        m = layout.Memory()
        self.assertTrue(m.slide_open("wb"))
        m.slid("wb", False)
        self.assertFalse(m.slide_open("wb"))


class AgentLinkTabs(unittest.TestCase):
    ROWS = panel_tabs.tab_order([{"title": t, "order": o} for t, o in (
        ("Setups", 30), ("Materials", 32), ("Fits", 34), ("Texture", 60), ("ScanRuler", 70), ("Manual", 80), ("Session", 90), ("Old", 85))])
    WHERE = {"Setups": {"WorkshopMakeWorkbench"}, "Materials": {"WorkshopMakeWorkbench"}, "Fits": {"WorkshopMakeWorkbench"},
             "Review": {"WorkshopMakeWorkbench"}, "Texture": {"TexturizerWorkbench"}, "ScanRuler": {"ScanRulerWorkbench"},
             "Manual": {"WorkshopDocumentsWorkbench"}, "Session": {"SafetyNetWorkbench"}}

    def tabs(self, wb, extra=()):
        return panel_tabs.tabs_for(self.ROWS, wb, self.WHERE, extra)

    def test_core_everywhere_addons_with_their_workbench(self):
        # "Old" names no workbench: an add-on written before tab_in shows everywhere.
        self.assertEqual(self.tabs("PartDesignWorkbench"), ["Notes", "Steps", "Old", "Activity"])
        self.assertEqual(self.tabs("ScanRulerWorkbench"), ["Notes", "Steps", "ScanRuler", "Old", "Activity"])
        self.assertEqual(self.tabs("WorkshopMakeWorkbench"), ["Notes", "Steps", "Setups", "Materials", "Fits", "Review", "Old", "Activity"])
        self.assertEqual(self.tabs("AgentLinkWorkbench"), ["Notes", "Steps", "Review", "Old", "Activity"])

    def test_asked_for_by_name(self):
        self.assertIn("Session", self.tabs("PartDesignWorkbench", {"Session"}))

    def test_never_all_ten(self):
        for wb in ("PartDesignWorkbench", "ScanRulerWorkbench", "TexturizerWorkbench", "WorkshopMakeWorkbench"):
            self.assertLessEqual(len(self.tabs(wb)), 8)

    def test_one_credit(self):
        self.assertFalse(panel_tabs.credit_shown("ScanRuler"))
        self.assertFalse(panel_tabs.credit_shown("Texture"))
        self.assertTrue(panel_tabs.credit_shown("Notes"))

    def test_register_tab_in_workbench(self):
        state = hooks.saved()
        try:
            hooks.reset()
            hooks.register_tab("Setups", lambda p: None, 30, workbench="WorkshopMakeWorkbench")
            hooks.tab_in("Review", "WorkshopMakeWorkbench")
            self.assertEqual(hooks.TAB_WORKBENCHES, {"Setups": {"WorkshopMakeWorkbench"}, "Review": {"WorkshopMakeWorkbench"}})
            rows = panel_tabs.tab_order(hooks.TABS)
            self.assertEqual(panel_tabs.tabs_for(rows, "SketcherWorkbench", hooks.TAB_WORKBENCHES), ["Notes", "Steps", "Activity"])
        finally:
            hooks.restore(state)


class Caption(unittest.TestCase):
    def test_bottom_right_clear_of_the_slide_out(self):
        from agentlink import echo

        most, x, y = echo.caption_box(856 - 270, 900, 260, 40)
        self.assertGreater(x, 300)  # right of a 300 px slide-out
        self.assertEqual(y, 900 - 40 - 14)
        self.assertEqual(x + min(260, most), 586 - 14)  # its right edge at the view's
        self.assertLessEqual(most, 420)
        most, x, _y = echo.caption_box(1400, 900, 1000, 40)
        self.assertEqual(most, 420)
        self.assertGreater(x, 300)


class AddonPages(unittest.TestCase):
    def test_own_dock_beside_agent_link(self):
        """With Agent Link's placer an add-on's page is its own dock; an
        Agent Link without it hosts the page as a tab."""
        state = hooks.saved()
        try:
            hooks.reset()
            self.assertTrue(layout.hosted_tabs(hooks))
            hooks.provide(layout.SERVICE, object())
            self.assertFalse(layout.hosted_tabs(hooks))
            self.assertIsNone(layout.caller())
            hooks.provide("panel_caller", "c")
            self.assertEqual(layout.caller(), "c")
            self.assertFalse(layout.in_agentlink_panel("Setups"))
            hooks.register_tab("Setups", lambda p: None, 30)
            self.assertTrue(layout.in_agentlink_panel("Setups"))
        finally:
            hooks.restore(state)


class GuiDoc:
    """A stand-in Gui document: its Modified flips on any view property set."""

    def __init__(self):
        self.Modified = False

    def set_view(self):
        self.Modified = True


class AppDoc:
    def __init__(self):
        self.UndoNames = []


class Marks(unittest.TestCase):
    """A panel's own work (Workshop Make opening its panel set the "*" with
    no undo step on the Mac) leaves the window's modified marks alone; a
    real change keeps its mark."""

    def test_a_view_write_is_put_back(self):
        g, d = GuiDoc(), AppDoc()
        docs = lambda: [("Box", g, d)]  # noqa: E731
        later = []
        with layout.keep_marks(docs, later=lambda ms, fn: later.append(fn)):
            g.set_view()
        self.assertFalse(g.Modified)
        g.set_view()  # set again after the panel's work, before the window settles
        for fn in later:
            fn()
        self.assertFalse(g.Modified)

    def test_a_real_change_keeps_its_mark(self):
        g, d = GuiDoc(), AppDoc()
        with layout.keep_marks(lambda: [("Box", g, d)], later=lambda ms, fn: None):
            d.UndoNames.append("setup")
            g.set_view()
        self.assertTrue(g.Modified)

    def test_an_already_changed_document_stays_marked(self):
        g, d = GuiDoc(), AppDoc()
        g.Modified = True
        with layout.keep_marks(lambda: [("Box", g, d)], later=lambda ms, fn: None):
            pass
        self.assertTrue(g.Modified)


class Doc:
    def __init__(self):
        self.n = 2

    def blockCount(self):  # noqa: N802
        return self.n


class Widget:
    def __init__(self):
        self.doc = Doc()
        self.lines = [("12:00  Agent Link: listening", "#ffffff"), ("", None)]

    def document(self):
        return self.doc


class Dock:
    def __init__(self, shown=True):
        self.shown = shown

    def isVisible(self):  # noqa: N802
        return self.shown

    def setVisible(self, on):  # noqa: N802
        self.shown = on

    def hide(self):
        self.shown = False

    def show(self):
        self.shown = True

    def raise_(self):
        pass


class ReportView(unittest.TestCase):
    def make(self, **params):
        self.w, self.d = Widget(), Dock()
        self.p = Params(**params)
        self.now = [100.0]

        def blocks(w, start):
            return w.lines[start:], len(w.lines)

        return report_watch.AutoOpen(self.p, dock=lambda: self.d, widget=lambda: self.w,
                                     colours=lambda: {"#ff0000", "#ffaa00"}, blocks=blocks, clock=lambda: self.now[0])

    def test_shown_again_by_freecad_is_hidden_again(self):
        """FreeCAD shows the Report view again as it starts and at a
        workbench switch: hidden again then; later the person's choice."""
        a = self.make(PanelLayout="left-tab")
        a.tick()
        self.d.show()  # FreeCAD's saved layout, at start
        self.assertEqual(a.tick(), "hidden")
        self.now[0] += 60
        self.d.show()  # the person opens it
        self.assertIsNone(a.tick())
        self.assertTrue(self.d.shown)
        a.switched("ScanRulerWorkbench")
        self.assertEqual(a.tick(), "hidden")

    def test_noise_does_not_open_it(self):
        a = self.make(PanelLayout="left-tab")
        a.tick()
        self.now[0] += 60
        self.write("12:00  (qt.qpa.fonts) Populating font family aliases took 147 ms. Replace uses of missing font family", None)
        self.write("12:00  Cannot find icon: Std_DlgMacroExecute", "#ffaa00")
        self.assertIsNone(a.tick())
        self.assertFalse(self.d.shown)

    def write(self, text, colour):
        self.w.lines[-1:] = [(text, colour), ("", None)]
        self.w.doc.n = len(self.w.lines)

    def test_hidden_by_default_without_a_layout_setting(self):
        a = self.make()
        self.assertEqual(a.tick(), "hidden")
        self.assertFalse(self.d.shown)

    def test_left_alone_when_report_auto_is_off(self):
        a = self.make(ReportAuto=False)
        self.assertIsNone(a.tick())
        self.assertTrue(self.d.shown)

    def test_hidden_then_opens_on_a_problem_line(self):
        a = self.make(PanelLayout="left-tab")
        self.assertEqual(a.tick(), "hidden")
        self.assertFalse(self.d.shown)
        self.write("12:01  Agent Link: link on", "#ffffff")
        self.assertIsNone(a.tick())
        self.assertFalse(self.d.shown)
        self.write("12:02  Pauses: box is in no print setup", "#ff0000")
        self.assertEqual(a.tick(), "opened")
        self.assertTrue(self.d.shown)

    def test_words_alone_open_it(self):
        a = self.make(PanelLayout="right")
        a.tick()
        self.write("Traceback (most recent call last):", None)
        self.assertEqual(a.tick(), "opened")

    def test_turned_off_gives_the_persons_state_back(self):
        a = self.make(PanelLayout="right")
        a.tick()
        self.assertFalse(self.d.shown)
        self.p.v["ReportAuto"] = False
        self.assertEqual(a.tick(), "restored")
        self.assertTrue(self.d.shown)
        self.assertIsNone(a.tick())


if __name__ == "__main__":
    unittest.main()
