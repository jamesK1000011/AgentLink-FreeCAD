# SPDX-License-Identifier: LGPL-2.1-or-later
# The panel's tab helpers, the parts that need no window: add-ons' tabs
# filled through their own fill(), and the narrow-dock row and colour.
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# FreeCAD's PySide shim comes with FreeCAD: load it first where it is here.
if os.environ.get("FREECAD_LIB"):
    sys.path.append(os.environ["FREECAD_LIB"])
try:
    import FreeCAD  # noqa: F401,E402
except ImportError:
    pass

from agentlink import panel_tabs  # noqa: E402


class PanelTabs(unittest.TestCase):
    """Setups, Materials, Fits and Manual are the add-ons' tabs now
    (register_tab): the panel keeps no copy, and fills theirs through their
    own fill()."""

    def test_no_own_copies(self):
        for name in ("_setups_tab", "_materials_tab", "_fits_tab", "_manual_tab", "summary", "manual_steps", "manual_plan_steps", "missing_tool"):
            self.assertFalse(hasattr(panel_tabs.Tabs, name) or hasattr(panel_tabs, name), name)

    def test_fill_tab_asks_the_addon(self):
        seen = []

        class Wdg:
            def fill(self):
                seen.append("Setups")

        t = panel_tabs.Tabs()
        t.addon_tabs = {"Setups": Wdg(), "Plain": object()}
        t.fill_tab("Setups")
        t.fill_tab("Plain")
        t.fill_tab("Manual")  # no add-on: nothing to fill
        self.assertEqual(seen, ["Setups"])


if __name__ == "__main__":
    unittest.main()


HAVE_QT = panel_tabs.QtWidgets is not None


@unittest.skipUnless(HAVE_QT, "no PySide here")
class NarrowPanel(unittest.TestCase):
    """Button rows wrap when the dock is narrow; the quiet text keeps its
    contrast in a dark theme."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        QW = panel_tabs.QtWidgets
        app = QW.QApplication.instance()
        if app is not None and not isinstance(app, QW.QApplication):
            # FreeCAD without its window runs a QCoreApplication: no widgets there.
            raise unittest.SkipTest("a Qt core application is running (FreeCAD headless): no widgets")
        cls.app = app or QW.QApplication([])

    def test_flow_row_wraps(self):
        QW = panel_tabs.QtWidgets
        row = panel_tabs.FlowRow([QW.QPushButton(t) for t in ("Use copy", "Roll back", "Approve", "Run")])
        one = row.heightForWidth(2000)
        self.assertGreater(row.heightForWidth(120), one * 2)
        self.assertLessEqual(row.minimumSizeHint().width(), 200)

    def test_muted_reads_on_dark(self):
        QW, QG = panel_tabs.QtWidgets, panel_tabs.QtGui
        lab = QW.QLabel("x")
        pal = lab.palette()
        pal.setColor(QG.QPalette.Window, QG.QColor(30, 30, 30))
        pal.setColor(QG.QPalette.WindowText, QG.QColor(230, 230, 230))
        lab.setPalette(pal)
        c = panel_tabs.muted(lab)
        lum = sum(int(c[i:i + 2], 16) for i in (1, 3, 5)) / 3
        self.assertGreater(lum, 120)  # well clear of the dark background
