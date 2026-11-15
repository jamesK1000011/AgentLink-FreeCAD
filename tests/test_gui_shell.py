# SPDX-License-Identifier: LGPL-2.1-or-later
# Agent Link's own GUI, the parts that need no window: the workbench loads
# under stand-in FreeCAD modules, every command's icon resolves, the panel's
# tab order and plain words (empty tabs, no reviewer, the link line, the
# usage strip), and the theme's accents read from parameters or a .cfg and
# put only on Agent Link's own widgets. Qt-only checks skip without PySide.
import os
import runpy
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

from agentlink import commands, hooks, launcher_check, panel_tabs, theme, usage  # noqa: E402

ICONS = os.path.join(ROOT, "agentlink", "icons")


class Params:
    """A parameter group as FreeCAD.ParamGet gives it, from a dict."""

    def __init__(self, d):
        self.d = d

    def GetUnsigned(self, name, default=0):
        return self.d.get(name, default)


class Theme(unittest.TestCase):
    def test_from_parameters(self):
        p = Params({"ThemeAccentColor1": 0x3F93D6FF, "ThemeAccentColor2": 0xB4783CFF})
        self.assertEqual(theme.accents(p), ["#3f93d6", "#b4783c", None])
        r = theme.roles(params=p)
        self.assertEqual((r["accent"], r["accent2"], r["accent3"]), ("#3f93d6", "#b4783c", "#3f93d6"))
        self.assertEqual({k: r[k] for k in ("ok", "warn", "bad")}, theme.FIXED)

    def test_from_a_pack_cfg(self):
        for pack in ("Studio Dark", "Studio Light"):
            a = theme.accents(os.path.join(ROOT, pack, pack + ".cfg"))
            self.assertTrue(all(c and c.startswith("#") and len(c) == 7 for c in a), (pack, a))

    def test_from_a_small_cfg(self):
        with tempfile.NamedTemporaryFile("w", suffix=".cfg", delete=False) as f:
            f.write('<FCParameters><FCParamGroup Name="Root"><FCParamGroup Name="Themes">'
                    '<FCUInt Name="ThemeAccentColor1" Value="4278190335"/></FCParamGroup></FCParamGroup></FCParameters>')
        try:
            self.assertEqual(theme.accents(f.name), ["#ff0000", None, None])
        finally:
            os.unlink(f.name)

    def test_nothing_set_falls_back(self):
        r = theme.roles(params=Params({}))
        self.assertTrue(r["accent"].startswith("#"))
        self.assertEqual(theme.hex_of(0), None)
        self.assertEqual(theme.hex_of("junk"), None)

    def test_rules_only_on_our_widgets(self):
        css = panel_tabs.panel_qss(theme.roles(params=Params({"ThemeAccentColor1": 0x3F93D6FF})))
        rules = [l for l in css.splitlines() if l.strip()]
        self.assertTrue(rules)
        for line in rules:
            self.assertTrue(line.startswith("#AgentLinkPanel "), line)
            # Colours only: FreeCAD's theme keeps shapes, fonts and surfaces.
            body = line[line.index("{") + 1:line.rindex("}")]
            self.assertEqual({d.split(":")[0].strip() for d in body.split(";") if d.strip()}, {"color"}, line)
        self.assertIn("#3f93d6", css)


class Tabs(unittest.TestCase):
    def test_order_with_addon_tabs(self):
        addon = [{"title": "Session", "order": 90}, {"title": "Setups", "order": 30}, {"title": "Texture", "order": 60},
                 {"title": "Notes", "order": 1}]  # a core title is never taken
        self.assertEqual([t for t, _, _ in panel_tabs.tab_order(addon)],
                         ["Notes", "Steps", "Setups", "Review", "Texture", "Session", "Activity"])
        self.assertEqual([t for t, _, _ in panel_tabs.tab_order([])], ["Notes", "Steps", "Review", "Activity"])

    def test_each_empty_tab_says_what_it_is_for(self):
        self.assertEqual(set(panel_tabs.EMPTY), {t for t, _ in panel_tabs.CORE_TABS})
        self.assertIn("Pin a note", panel_tabs.EMPTY["Notes"])
        self.assertIn("plays a body's build", panel_tabs.EMPTY["Steps"])
        self.assertIn("reviewer's verdict", panel_tabs.EMPTY["Review"])
        self.assertIn("Each thing the agent does", panel_tabs.EMPTY["Activity"])

    def test_review_with_no_reviewer(self):
        state = hooks.saved()
        try:
            hooks.reset()
            self.assertIsNone(hooks.review(object(), "Body"))
            hint = panel_tabs.review_hint(bool(hooks.REVIEWERS))
            self.assertTrue(hint.startswith("No reviewer installed."))
            self.assertIn("Body check", hint)
            hooks.register_reviewer(lambda s, b: {"verdict": "pass"})
            self.assertEqual(hooks.review(object(), "Body"), {"verdict": "pass"})
            self.assertEqual(panel_tabs.review_hint(bool(hooks.REVIEWERS)), panel_tabs.EMPTY["Review"])
        finally:
            hooks.restore(state)

    def test_link_line(self):
        self.assertEqual(panel_tabs.link_status(False), "Link off. Start link lets an agent drive this window.")
        self.assertEqual(panel_tabs.link_status(True, "Bracket"), "Link on. The agent works in Bracket.")
        self.assertIn("document in front", panel_tabs.link_status(True))

    def test_usage_strip_says_estimate_not_billing(self):
        s = usage.strip({"perDay": [], "tokens": 1234})
        self.assertTrue(s.endswith("(estimate, not billing)"), s)


class Commands(unittest.TestCase):
    def test_every_pixmap_resolves(self):
        names = [n for n, _ in commands.COMMANDS]
        self.assertEqual(len(set(names)), len(names))
        for name, cls in commands.COMMANDS:
            res = cls().GetResources()
            self.assertTrue(res.get("MenuText") and res.get("ToolTip"), name)
            self.assertTrue(os.path.isfile(os.path.join(ICONS, res["Pixmap"] + ".svg")), (name, res["Pixmap"]))

    def test_setup_check_words(self):
        self.assertIn("not here yet", launcher_check.summary({"fetched": False}))
        r = {"fetched": True, "bytes": 10, "hasUpdateTool": True, "ownPackageJson": False, "esModuleScope": "/x/package.json", "log": ["start: ok"]}
        self.assertTrue(launcher_check.can_mend(r))
        self.assertIn("cannot load", launcher_check.summary(r))
        self.assertIn("start: ok", launcher_check.summary(r))
        r.update(ownPackageJson=True)
        self.assertFalse(launcher_check.can_mend(r))
        self.assertIn("Nothing stops it loading", launcher_check.summary(r))

    def test_updates_words(self):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "package.xml"), "w") as f:
            f.write("<package><version>9.8.7</version></package>")
        os.makedirs(os.path.join(d, ".git", "refs", "heads"))
        with open(os.path.join(d, ".git", "HEAD"), "w") as f:
            f.write("ref: refs/heads/main\n")
        with open(os.path.join(d, ".git", "refs", "heads", "main"), "w") as f:
            f.write("0123456789abcdef0123456789abcdef01234567\n")
        self.assertEqual(commands.installed_version(d), ("9.8.7", "0123456"))
        t = commands.updates_text("9.8.7", "0123456")
        self.assertIn("Agent Link 9.8.7 (commit 0123456)", t)
        self.assertIn("agentlink_update", t)
        self.assertEqual(commands.installed_version(tempfile.mkdtemp()), ("?", None))


class InitGuiLoads(unittest.TestCase):
    """InitGui.py under stand-in FreeCAD and FreeCADGui: the workbench is
    added, its commands registered by name, and toolbar and menu name only
    registered commands."""

    def test_loads(self):
        added, cmds, bars, menus, paths = [], {}, {}, {}, []

        class Workbench:
            def appendToolbar(self, name, items):
                bars[name] = items

            def appendMenu(self, name, items):
                menus[name] = items

        gui = types.ModuleType("FreeCADGui")
        gui.Workbench = Workbench
        gui.addWorkbench = added.append
        gui.addCommand = cmds.__setitem__
        gui.addIconPath = paths.append
        app = types.ModuleType("FreeCAD")
        pyside = types.ModuleType("PySide")  # no QtCore: autostart's timer is skipped
        with mock.patch.dict(sys.modules, {"FreeCADGui": gui, "FreeCAD": app, "PySide": pyside}):
            runpy.run_path(os.path.join(ROOT, "InitGui.py"))
            self.assertEqual(len(added), 1)
            wb = added[0]
            self.assertEqual(wb.MenuText, "Agent Link")
            self.assertTrue(os.path.isfile(wb.Icon))
            self.assertEqual(paths, [os.path.join(os.path.dirname(commands.__file__), "icons")])
            wb.Initialize()
        self.assertEqual(list(cmds), [n for n, _ in commands.COMMANDS])
        for items in list(bars.values()) + list(menus.values()):
            for i in items:
                self.assertTrue(i == "Separator" or i in cmds, i)
        self.assertIn("AgentLink_Check", menus["Agent Link"])
        self.assertIn("AgentLink_Update", menus["Agent Link"])


HAVE_QT = panel_tabs.QtWidgets is not None


@unittest.skipUnless(HAVE_QT, "no PySide here")
class Follows(unittest.TestCase):
    """The accents land on the widget and come back after a palette change."""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        QW = panel_tabs.QtWidgets
        app = QW.QApplication.instance()
        if app is not None and not isinstance(app, QW.QApplication):
            raise unittest.SkipTest("a Qt core application is running (FreeCAD headless): no widgets")
        cls.app = app or QW.QApplication([])

    def test_restyled_on_palette_change(self):
        QW, QG = panel_tabs.QtWidgets, panel_tabs.QtGui
        w = QW.QWidget()
        w.setObjectName("AgentLinkPanel")
        theme.follow(w, panel_tabs.panel_qss)
        self.assertIn("#AgentLinkPanel", w.styleSheet())
        w.setStyleSheet("")
        pal = w.palette()
        pal.setColor(QG.QPalette.Window, QG.QColor(20, 20, 20))
        w.setPalette(pal)
        self.assertIn("#AgentLinkPanel", w.styleSheet())


if __name__ == "__main__":
    unittest.main()
