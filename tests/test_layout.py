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
    def test_default_is_right(self):
        self.assertEqual(layout.read(Params()), "right")
        self.assertEqual(layout.read(Params(PanelLayout="nonsense")), "right")
        self.assertEqual(layout.read(), "right")  # no FreeCAD here
        self.assertFalse(layout.is_set(Params()))

    def test_values(self):
        for v in ("right", "left-tab", "left-slide"):
            self.assertEqual(layout.read(Params(PanelLayout=v)), v)
        self.assertEqual(layout.normalise(" Left_Tab "), "left-tab")
        self.assertTrue(layout.is_set(Params(PanelLayout="left-slide")))

    def test_widths(self):
        self.assertEqual(layout.width_cap("right"), 360)
        self.assertEqual(layout.width_cap("left-tab"), 300)
        self.assertLessEqual(layout.width_cap("left-slide"), 360)

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

        def blocks(w, start):
            return w.lines[start:], len(w.lines)

        return report_watch.AutoOpen(self.p, dock=lambda: self.d, widget=lambda: self.w,
                                     colours=lambda: {"#ff0000", "#ffaa00"}, blocks=blocks)

    def write(self, text, colour):
        self.w.lines[-1:] = [(text, colour), ("", None)]
        self.w.doc.n = len(self.w.lines)

    def test_left_alone_when_the_layout_is_not_set(self):
        a = self.make()
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
