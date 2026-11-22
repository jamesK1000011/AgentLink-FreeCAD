# SPDX-License-Identifier: LGPL-2.1-or-later
"""Red team 4 on the hub (R4-2, R4-4, R4-7, R4-12, R4-13): file dialogs and
file-level boxes take no input but a back-out, cmd_run refuses the commands
that open a file dialog, settings that say where files go or which program
runs are the person's, app_install asks approve_code, and an extension's
text is a repository and a branch name only. Plain Python: the functions of
families/app.py and gui_link.py are read from the source (both need
FreeCAD to import)."""
import ast
import json
import os
import sys
import tempfile
import types
import unittest
import xml.etree.ElementTree as ET
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from agentlink import approvals, ext  # noqa: E402
from agentlink import gui_input as gi  # noqa: E402
from agentlink.protocol import ToolError  # noqa: E402


def _from_source(rel, names, extra=None):
    """The top-level functions and assignments of a module, by name, run in
    a namespace of the agentlink package (relative imports work)."""
    src = os.path.join(ROOT, rel)
    with open(src, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    keep = []
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in names:
            keep.append(n)
        elif isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets):
            keep.append(n)
        elif isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and ast.unparse(n.value.func) in names:
            keep.append(n)
    import re

    ns = {"__name__": "agentlink." + rel[len("agentlink/"):-3].replace("/", "."), "__package__": "agentlink" + ("." + os.path.dirname(rel)[len("agentlink/"):].replace("/", ".") if "/" in rel[len("agentlink/"):] else ""),
          "re": re, "os": os, "ET": ET, "ToolError": ToolError, **(extra or {})}
    exec(compile(ast.Module(keep, []), src, "exec"), ns)
    return types.SimpleNamespace(**{k: v for k, v in ns.items() if not k.startswith("__")}), ns


class Group:
    """A FreeCAD parameter group stand-in."""

    def __init__(self, tree, path):
        self.tree, self.path = tree, path

    def _vals(self):
        return self.tree.setdefault(self.path, {})

    def GetContents(self):
        return [(k, n, v) for n, (k, v) in self._vals().items()]

    def GetGroups(self):
        pre = self.path + "/"
        return sorted({p[len(pre):].split("/")[0] for p in self.tree if p.startswith(pre)})

    def _set(kind):
        def f(self, name, v):
            self._vals()[name] = (kind, v)
        return f

    SetBool, SetInt, SetUnsigned, SetFloat, SetString = _set("Boolean"), _set("Integer"), _set("Unsigned"), _set("Float"), _set("String")

    def _rem(self, name):
        self._vals().pop(name, None)

    RemBool = RemInt = RemUnsigned = RemFloat = RemString = _rem


def fake_freecad(tree):
    return types.SimpleNamespace(ParamGet=lambda p: Group(tree, p[len("User parameter:"):] if p.startswith("User parameter:") else p))


APP_NAMES = {"ROOT", "_GUARDED", "_GUARDED_WORDS", "_GUARDED_ENDS", "_GUARDED_GROUPS", "path_like", "guarded", "_all_values", "_guarded_values",
             "_guarded_restore", "PACK_TYPES", "apply_cfg", "_set", "_contents", "REFUSED", "FILE_DIALOG_COMMANDS", "REFUSED.update", "REFUSED_LIKE",
             "refused", "version_older", "install_approval", "_freecad_bundle"}


def app_module(tree=None):
    tree = {} if tree is None else tree
    mod, ns = _from_source("agentlink/families/app.py", APP_NAMES, {"FreeCAD": fake_freecad(tree)})
    return mod, ns, tree


# ---- R4-7 and R4-2 (a): settings that say where files go or which program runs -------------

class Settings(unittest.TestCase):
    def setUp(self):
        self.app, _ns, _t = app_module()

    def test_the_exact_attacks_are_the_persons(self):
        g = self.app.guarded
        self.assertTrue(g("BaseApp/Preferences/Dialog", "DontUseNativeDialog", True), "R4-2: Qt's own file dialog")
        self.assertTrue(g("User parameter:BaseApp/Preferences/Mod/Draft", "TeighaFileConverter", "/tmp/evil"), "R4-7: the ODA converter")
        self.assertTrue(g("BaseApp/Preferences/Mod/Draft", "TeighaFileConverter"), "by its name alone")
        for path, name in (("BaseApp/Preferences/General", "FileOpenSavePath"), ("BaseApp/Preferences/Mod/Fem/General", "WorkingDir"),
                           ("BaseApp/Preferences/Mod/Spreadsheet", "ExternalEditor"), ("BaseApp/Preferences/Mod/OpenSCAD", "openscadexecutable"),
                           ("BaseApp/Preferences/Mod/X", "PythonPath"), ("BaseApp/Preferences/Mod/X", "CatalogUrl"), ("BaseApp/Preferences/Mod/X", "UserRepos"),
                           ("BaseApp/Preferences/Macro", "RecentMacros"), ("BaseApp/Preferences/Mod/AgentLink", "WindowApprove"),
                           ("BaseApp/Preferences/Mod/AgentLink", "ExtensionRepos"), ("BaseApp/Preferences/Mod/Fem/Ccx", "ccxBinaryPath")):
            self.assertTrue(g(path, name), name)

    def test_a_path_or_address_as_the_value(self):
        g = self.app.guarded
        for v in ("/Users/x/evil", "~/x", "../../x", "https://example.com/x", "file:///tmp/x", "C:\\x", "$HOME/x"):
            self.assertTrue(g("BaseApp/Preferences/View", "Anything", v), v)

    def test_ordinary_settings_stay_the_agents(self):
        g = self.app.guarded
        for name, v in (("Gradient", True), ("Zoom", 0.5), ("Theme", "Studio Dark"), ("NavigationStyle", "Gui::GestureNavigationStyle"),
                        ("StyleSheet", "FreeCAD.qss"), ("Profile", "x"), ("BackgroundColor", "#1864ab"), ("Title", "Mine")):
            self.assertFalse(g("BaseApp/Preferences/View", name, v), name)

    def test_the_bundled_packs_set_every_value(self):
        for pack in ("Studio Dark", "Studio Light"):
            cfg = os.path.join(ROOT, pack, pack + ".cfg")
            if not os.path.exists(cfg):
                continue
            app, _ns, tree = app_module()
            skipped = []
            n = app.apply_cfg(cfg, skipped)
            self.assertGreater(n, 0)
            self.assertEqual(skipped, [], pack)

    def test_a_pack_sets_no_guarded_setting(self):
        app, _ns, tree = app_module()
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "x.cfg")
            with open(cfg, "w") as f:
                f.write('<?xml version="1.0"?><FCParameters><FCParamGroup Name="Root"><FCParamGroup Name="BaseApp"><FCParamGroup Name="Preferences">'
                        '<FCParamGroup Name="Dialog"><FCBool Name="DontUseNativeDialog" Value="1"/></FCParamGroup>'
                        '<FCParamGroup Name="Macro"><FCText Name="MacroPath">/tmp/m</FCText></FCParamGroup>'
                        '<FCParamGroup Name="Mod"><FCParamGroup Name="Draft"><FCText Name="TeighaFileConverter">/tmp/evil</FCText></FCParamGroup></FCParamGroup>'
                        '<FCParamGroup Name="View"><FCBool Name="Gradient" Value="0"/><FCText Name="Background">/tmp/x.png</FCText></FCParamGroup>'
                        '</FCParamGroup></FCParamGroup></FCParamGroup></FCParameters>')
            skipped = []
            self.assertEqual(app.apply_cfg(cfg, skipped), 1)
        self.assertEqual(sorted(skipped), ["BaseApp/Preferences/Dialog/DontUseNativeDialog", "BaseApp/Preferences/Macro/MacroPath",
                                           "BaseApp/Preferences/Mod/Draft/TeighaFileConverter", "BaseApp/Preferences/View/Background"])
        self.assertEqual(tree["BaseApp/Preferences/View"], {"Gradient": ("Boolean", False)})
        self.assertNotIn("BaseApp/Preferences/Dialog", tree)

    def test_an_import_puts_the_guarded_settings_back(self):
        tree = {"BaseApp/Preferences/View": {"Gradient": ("Boolean", True), "Background": ("String", "plain")},
                "BaseApp/Preferences/Mod/Draft": {"Other": ("Integer", 2)}}
        app, _ns, tree = app_module(tree)
        before = app._guarded_values()
        # What a hostile user.cfg merges in.
        tree["BaseApp/Preferences/Dialog"] = {"DontUseNativeDialog": ("Boolean", True)}
        tree["BaseApp/Preferences/Mod/Draft"]["TeighaFileConverter"] = ("String", "/tmp/evil")
        tree["BaseApp/Preferences/View"]["Background"] = ("String", "/tmp/x.png")
        tree["BaseApp/Preferences/View"]["Gradient"] = ("Boolean", False)
        back = app._guarded_restore(before)
        self.assertEqual(sorted(back), ["BaseApp/Preferences/Dialog/DontUseNativeDialog", "BaseApp/Preferences/Mod/Draft/TeighaFileConverter",
                                        "BaseApp/Preferences/View/Background"])
        self.assertEqual(tree["BaseApp/Preferences/View"], {"Gradient": ("Boolean", False), "Background": ("String", "plain")})
        self.assertEqual(tree["BaseApp/Preferences/Dialog"], {})
        self.assertEqual(tree["BaseApp/Preferences/Mod/Draft"], {"Other": ("Integer", 2)})

    def test_pref_set_checks_each_value(self):
        with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            e = json.load(f)["entries"]
        self.assertIn("guarded(path, k, values[k])", json.dumps(e["pref_set"]["steps"]))
        self.assertIn("apply_cfg(have[name], skipped)", json.dumps(e["pref_pack"]["steps"]))


# ---- R4-2 (c): cmd_run refuses the commands that open a file dialog --------------------------

class FileDialogCommands(unittest.TestCase):
    def test_refused_with_the_tool_that_does_the_job(self):
        app, _ns, _t = app_module()
        with open(os.path.join(ROOT, "docs", "hardening", "freecad-1.1.0-commands.txt"), encoding="utf-8") as f:
            known = {ln.strip() for ln in f if ln.strip() and not ln.startswith("#")}
        with open(os.path.join(ROOT, "agentlink", "data", "tool_index.json"), encoding="utf-8") as f:
            tools = set(json.load(f)["entries"]) | {"doc_save_all", "view", "td_page", "import_file", "doc_open", "doc_save"}
        for c in ("Std_SaveCopy", "Std_SaveAs", "Std_Save", "Std_Export", "Std_Import", "Std_Open", "TechDraw_Symbol", "TechDraw_ExportPageSVG",
                  "TechDraw_ExportPageDXF", "Std_ViewScreenShot", "Std_ProjectUtil", "Std_MergeProjects", "CAM_Post", "IFC_SaveAs"):
            self.assertTrue(app.refused(c), c)
        for c, tool in app.FILE_DIALOG_COMMANDS.items():
            self.assertIn(c, known, f"{c}: a FreeCAD 1.1 command")
            why = app.refused(c)
            self.assertIn("dialog", why, c)
            first = tool.split()[0]
            if "_" in first:
                self.assertIn(first, tools, f"{c} names a tool that is there")
        for c in ("Std_ViewFitAll", "PartDesign_Pad", "Std_ViewIsometric", "Sketcher_LeaveSketch"):
            self.assertIsNone(app.refused(c), c)

    def test_gui_input_refuses_them_from_menus_too(self):
        app, _ns, _t = app_module()
        with mock.patch.dict(sys.modules, {"agentlink.families.app": types.SimpleNamespace(refused=app.refused)}):
            self.assertTrue(gi.refused_command("Std_SaveCopy"))
            self.assertTrue(gi.refused_command("TechDraw_Symbol"))


# ---- R4-2 (b) and R4-4: gui_input in a file dialog or a file-level box ----------------------

import test_gui_input as tg  # noqa: E402


class Box(tg.Widget):
    def __init__(self, name, ox, oy, w, h, cls, text="", obj="", roles=None):
        super().__init__(name, ox, oy, w, h, cls=cls)
        self._text, self._obj, self.roles = text, obj or name, roles or {}

    def text(self):
        return self._text

    def objectName(self):
        return self._obj

    def buttonRole(self, b):
        return self.roles.get(b.name, -1)


def button(name, parent, x, y):
    b = tg.Widget(name, x, y, 60, 20, parent=parent, cls="QPushButton")
    b.text = lambda: name
    return b


class Role(int):
    """A PySide6-like enum value with a name."""

    def __new__(cls, v, name):
        o = int.__new__(cls, v)
        o.name = name
        return o


class InDialogs(unittest.TestCase):
    def setUp(self):
        self.d = tg.Delivery("test_drag_goes_to_the_pressed_widget")
        self.d.setUp()
        self.addCleanup(self.d.doCleanups)

    def front(self, dlg):
        self.d.state["modal"] = dlg
        self.d.state["app"].topLevelWidgets = lambda: [self.d.mw, dlg]

    def run_steps(self, steps):
        return self.d.run.run(gi.parse_steps(steps))

    def test_file_dialog_takes_no_typed_path(self):
        dlg = tg.Widget("Save a Copy", 300, 300, 400, 300, cls="Gui::FileDialog")
        dlg.metaObject = lambda: tg.Chain(["Gui::FileDialog", "QFileDialog", "QDialog"])
        name = tg.Widget("fileNameEdit", 310, 500, 200, 20, parent=dlg, cls="QLineEdit", focus=2)
        bb = Box("buttonBox", 500, 550, 200, 30, "QDialogButtonBox", roles={"Save": 0, "Cancel": 1})
        bb.parent = dlg
        dlg.kids.append(bb)
        save, cancel = button("Save", bb, 510, 555), button("Cancel", bb, 580, 555)
        self.front(dlg)
        out = self.run_steps([{"click": {"widget": {"objectName": "fileNameEdit"}}}, {"type": "/Users/x/.zshrc"}])
        self.assertIn("file dialog", out["steps"][0]["error"])
        self.assertIn("doc_save { path }", out["steps"][0]["error"])
        out = self.run_steps([{"click": {"widget": {"text": "Save"}}}])
        self.assertIn("file dialog", out["steps"][0]["error"])
        self.assertEqual([w for w, e in self.d.sent if e.t != "MouseMove"], [], "no press, no key reached the dialog")
        out = self.run_steps([{"key": "Return", "target": {"widget": {"objectName": "fileNameEdit"}}}])
        self.assertIn("file dialog", out["steps"][0]["error"])
        out = self.run_steps([{"key": "Escape", "target": {"widget": {"objectName": "fileNameEdit"}}}])
        self.assertNotIn("error", out["steps"][0])
        out = self.run_steps([{"click": {"widget": {"text": "Cancel"}}}])
        self.assertNotIn("error", out["steps"][0])
        self.assertIn(("Cancel", "MouseButtonRelease"), [(w, e.t) for w, e in self.d.sent])
        self.assertNotIn("Save", [w for w, e in self.d.sent if e.t != "MouseMove"])

    def close_confirm(self, roles):
        box = Box("Unsaved Document", 300, 300, 300, 120, "QMessageBox", text="Do you want to save your changes to document 'Part' before closing?",
                  obj="confirmSave", roles=roles)
        for i, n in enumerate(("Save", "Discard", "Cancel")):
            button(n, box, 310 + 70 * i, 380)
        self.front(box)
        return box

    def test_close_confirm_presses_only_cancel(self):
        for roles in ({"Save": 0, "Discard": 2, "Cancel": 1},
                      {"Save": Role(0, "AcceptRole"), "Discard": Role(2, "DestructiveRole"), "Cancel": Role(1, "RejectRole")}):
            self.d.sent.clear()
            self.close_confirm(roles)
            for b in ("Discard", "Save"):
                out = self.run_steps([{"click": {"widget": {"text": b}}}])
                self.assertIn("dialog_answer", out["steps"][0]["error"], b)
                self.assertIn("approve_file", out["steps"][0]["error"])
            out = self.run_steps([{"key": "Return", "target": {"widget": {"text": "Save"}}}])
            self.assertIn("dialog_answer", out["steps"][0]["error"])
            self.assertEqual([w for w, e in self.d.sent if e.t != "MouseMove"], [])
            out = self.run_steps([{"click": {"widget": {"text": "Cancel"}}}])
            self.assertNotIn("error", out["steps"][0])

    def test_replace_box_takes_no_but_not_yes(self):
        box = Box("Confirm", 300, 300, 300, 120, "QMessageBox", text="x.step already exists. Do you want to replace it?", roles={"Yes": 5, "No": 6})
        button("Yes", box, 310, 380)
        button("No", box, 380, 380)
        self.front(box)
        out = self.run_steps([{"click": {"widget": {"text": "Yes"}}}])
        self.assertIn("approve_file", out["steps"][0]["error"])
        out = self.run_steps([{"click": {"widget": {"text": "No"}}}])
        self.assertNotIn("error", out["steps"][0])

    def test_other_dialogs_are_as_before(self):
        box = Box("Pad", 300, 300, 300, 120, "QMessageBox", text="Pad length must not be zero.", roles={"OK": 0})
        button("OK", box, 310, 380)
        self.front(box)
        out = self.run_steps([{"click": {"widget": {"text": "OK"}}}])
        self.assertNotIn("error", out["steps"][0])

    def test_file_level_words(self):
        self.assertEqual(gi.file_level("Unsaved Document", ""), "close")
        self.assertEqual(gi.file_level("x", "", "confirmSave"), "close")
        self.assertEqual(gi.file_level("x", "a.FCStd exists already. Overwrite?"), "replace")
        self.assertIsNone(gi.file_level("Pad", "Pad length must not be zero."))
        self.assertEqual(gi.role_name(Role(1, "RejectRole")), "RejectRole")
        self.assertEqual(gi.role_name(6), "NoRole")


class DialogAnswerInFileDialogs(unittest.TestCase):
    def setUp(self):
        self.gl, _ns = _from_source("agentlink/gui_link.py", {"BACK_OUT", "is_file_picker", "file_picker_press", "_persons", "fill"})

    def test_accept_presses_and_typing_are_refused(self):
        d = {"class": "Gui::FileDialog", "title": "Save a Copy", "widget": None}
        self.assertIn("doc_save { path }", self.gl.file_picker_press(d, "Save"))
        self.assertIn("not checked", self.gl.file_picker_press({"class": "QFileDialog"}, "&Open"))
        self.assertIsNone(self.gl.file_picker_press(d, "Cancel"))
        self.assertIsNone(self.gl.file_picker_press({"class": "QMessageBox"}, "Save"))
        w = tg.Widget("Open", 0, 0, 10, 10, cls="QFileDialog")
        with self.assertRaises(ValueError) as e:
            self.gl.fill({"class": "QDialog", "widget": w}, text="/Users/x/.ssh/id_ed25519")
        self.assertIn("file dialog", str(e.exception))

    def test_dialog_answer_runs_the_check(self):
        with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
            steps = json.dumps(json.load(f)["entries"]["dialog_answer"]["steps"])
        self.assertIn("file_picker_refusal(d, btn)", steps)
        self.assertLess(steps.index("file_picker_refusal"), steps.index("file_dialog_approval"))
        with open(os.path.join(ROOT, "agentlink", "families", "unattended.py"), encoding="utf-8") as f:
            self.assertIn('"file_picker_refusal"', f.read())


# ---- R4-12: app_install asks approve_code and opens only FreeCAD ----------------------------

class AppInstall(unittest.TestCase):
    def setUp(self):
        approvals.reset()
        approvals.note_client(None, "claude-ai")  # a client that asks the person first
        self.addCleanup(approvals.reset)
        self.app, _ns, _t = app_module()

    def test_versions(self):
        o = self.app.version_older
        self.assertTrue(o("0.19", ("1", "1", "3")))
        self.assertTrue(o("1.1.2", ("1", "1", "3")))
        self.assertFalse(o("1.1.3", ("1", "1", "3")))
        self.assertFalse(o("1.2", ("1", "1", "3")))
        self.assertFalse(o("latest", ("1", "1", "3")))

    def test_an_install_waits_for_approve_code(self):
        got = self.app.install_approval("install", "0.19", None, ("1", "1", "3"))
        self.assertTrue(got["pending"])
        self.assertEqual(got["approve"]["tool"], "approve_code")
        args = got["approve"]["arguments"]
        self.assertIn("older than the running 1.1.3", args["version"])
        self.assertIn("OLDER", args["what"])
        # The person approves (the client's approve_code): the same call goes on, once.
        req = next(iter(approvals._OPEN.values()))
        approvals.give(req, "client")
        self.assertEqual(self.app.install_approval("install", "0.19", None, ("1", "1", "3")), {"ok": True})
        self.assertTrue(self.app.install_approval("install", "0.19", None, ("1", "1", "3"))["pending"], "one approval, one install")
        # Another version is another approval.
        self.assertNotIn("older", self.app.install_approval("install", "1.2.0", None, ("1", "1", "3"))["approve"]["arguments"]["version"])

    def test_open_takes_only_a_freecad_bundle(self):
        with tempfile.TemporaryDirectory() as d:
            calc = os.path.join(d, "Calculator.app", "Contents")
            os.makedirs(calc)
            with self.assertRaises(ToolError):
                self.app._freecad_bundle(os.path.join(d, "Calculator.app"))
        with self.assertRaises(ToolError):
            self.app._freecad_bundle("/System/Applications/Calculator.app")

    def test_the_handler_asks(self):
        with open(os.path.join(ROOT, "agentlink", "families", "app.py"), encoding="utf-8") as f:
            src = f.read()
        body = src[src.index("    def app_install(a):"):src.index("    def pref_import(a):")]
        self.assertIn('_freecad_bundle(a["open"])', body)
        self.assertEqual(body.count("install_approval("), 2)
        self.assertLess(body.index('install_approval("install"'), body.index("subprocess.Popen([py"))


# ---- R4-13: an extension is a repository and a branch name ----------------------------------

class Extensions(unittest.TestCase):
    def test_only_github_names(self):
        self.assertEqual(ext.parse("a/b"), ("a/b", "main", "https://github.com/a/b.git"))
        self.assertEqual(ext.parse("https://github.com/a/b.git@feat/x"), ("a/b", "feat/x", "https://github.com/a/b.git"))
        scp = "git" + "@" + "host:a/b"  # an scp-style address, split so it reads as no mail address
        lock = "a/b" + "@" + "x.lock"
        for bad in ("--upload-pack=touch /tmp/x/y", "file:///tmp/r", "https://evil.example/a/b", scp, "a/b@-x", "a/b@a..b",
                    lock, "a/-b", "../x", "a/..", "a/b@", "-c/x", "a/b@--upload-pack=x"):
            with self.assertRaises(ValueError, msg=bad):
                ext.parse(bad)

    def test_sync_passes_dash_dash_and_skips_bad_text(self):
        ran = []

        def run(cmd, **kw):
            ran.append(cmd)
            if cmd[-1] and cmd[1] == "clone":
                os.makedirs(os.path.join(cmd[-1], "AgentLinkX"), exist_ok=True)
            return types.SimpleNamespace(returncode=0, stdout="abc\n", stderr="")

        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(ext, "repos", lambda: ["--upload-pack=touch /tmp/owned@.", "a/b@dev"]), \
                mock.patch.object(ext, "_git", lambda: "/usr/bin/git"), \
                mock.patch("subprocess.run", run), mock.patch("shutil.copytree", lambda *a, **k: None):
            out = ext.sync(cache=d)
        self.assertEqual(out["failed"][0]["repo"], "--upload-pack=touch /tmp/owned@.")
        self.assertIn("not fetched", out["failed"][0]["why"])
        clone = ran[0]
        self.assertEqual(clone[:6], ["/usr/bin/git", "clone", "--depth", "1", "-b", "dev"])
        self.assertEqual(clone[6:8], ["--", "https://github.com/a/b.git"])
        self.assertFalse(any("upload-pack" in " ".join(c) for c in ran))

    def test_add_refuses_bad_text_before_asking(self):
        approvals.reset()
        approvals.note_client(None, "claude-ai")  # a client that asks the person first
        self.addCleanup(approvals.reset)
        tool = ext.tools(None)[0]
        fake = types.ModuleType("FreeCAD")
        fake.ParamGet = lambda p: types.SimpleNamespace(GetString=lambda *a: "")
        with mock.patch.dict(sys.modules, {"FreeCAD": fake}):
            with self.assertRaises(ToolError) as e:
                tool.fn({"action": "add", "repo": "file:///tmp/r"})
        self.assertEqual(e.exception.code, "invalid_input")
        self.assertEqual(approvals.waiting(), [])


if __name__ == "__main__":
    unittest.main()
