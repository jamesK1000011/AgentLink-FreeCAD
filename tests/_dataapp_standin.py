# SPDX-License-Identifier: LGPL-2.1-or-later
# The stand-in FreeCAD of tests/test_dataapp_data.py: tests/_datacore_standin.py
# as it is, and on top of it what the hub's application tools reach
# (families/app.py, and `addon` of families/unattended.py): a parameter tree
# that keeps what is set; a window with commands (active or greyed), a menu
# bar of Qt-like actions, workbenches, a selection, a sketch open for editing,
# dock panels and a picture of itself; the person's screenshots; and the Addon
# Manager's modules, an installer and a smoke test as stubs that write down
# what they were asked. Nothing of the stand-ins under it is changed for their
# own tests: this one is only ever installed in this test's child process.
import io
import json
import os
import sys
import types
import zipfile


def install():
    import _datacore_standin

    fc = _datacore_standin.install()
    flag, log, state, F, gui = fc.flag, fc.log, fc.state, fc.fc, fc.gui
    CoreSession = fc.Session

    # ---- the parameter tree ----------------------------------------------------------------------

    def params():
        return state.setdefault("params", {})

    class Group:
        def __init__(self, path):
            self.path = path[len("User parameter:"):] if path.startswith("User parameter:") else path

        def rows(self):
            return params().setdefault(self.path, {})

        def GetContents(self):
            return [(kind, name, value) for name, (kind, value) in self.rows().items()]

        def GetGroups(self):
            if flag("no_groups"):
                raise RuntimeError("no groups")
            pre = self.path + "/"
            return [p[len(pre):].split("/")[0] for p in params() if p.startswith(pre)]

    def setter(kind):
        def put(self, name, value):
            log(f"Set{kind}", self.path, name, value)
            self.rows()[name] = ({"Bool": "Boolean", "Int": "Integer"}.get(kind, kind), value)

        return put

    def remover(kind):
        def rem(self, name):
            log(f"Rem{kind}", self.path, name)
            self.rows().pop(name, None)

        return rem

    for kind in ("Bool", "Int", "Unsigned", "Float", "String"):
        setattr(Group, "Set" + kind, setter(kind))
        setattr(Group, "Rem" + kind, remover(kind))
    F.ParamGet = Group
    F.Version = lambda: list(flag("version", ["1", "1", "3", "0"]))
    F.getHomePath = lambda: state["home"]
    F.getResourceDir = lambda: os.path.join(state["home"], "res")
    F.getUserAppDataDir = lambda: os.path.join(state["home"], "data")

    from agentlink import hooks

    hooks.emit = lambda *a, **kw: log("hooks.emit", *a, **kw)

    # ---- the window: commands, workbenches, the selection, a sketch in edit -------------------------

    class Command:
        def __init__(self, name):
            self.name = name

        def getInfo(self):
            info = flag("info", {}).get(self.name)
            if info is None:
                raise RuntimeError("no info")
            return info

        def isActive(self):
            if self.name in flag("cannot_say", ()):
                raise RuntimeError("cannot say")
            return self.name not in flag("greyed", ())

    def command(name):
        return None if name in flag("no_command", ()) else Command(name)

    def run_command(name, index=0):
        log("runCommand", name, index)
        for i in range(flag("adds", 0)):
            state["doc"].new("Part::Feature", f"Made{i}")
        if flag("front_after", 0) != 0:
            F.ActiveDocument = flag("front_after")

    class Bench:
        def __init__(self, key, text=None):
            self.key = key
            if text is not None:
                self.MenuText = text

        def name(self):
            return self.key

    def benches():
        return {"PartDesignWorkbench": Bench("PartDesignWorkbench", "Part Design"), "BIMWorkbench": Bench("BIMWorkbench", "BIM"), "NoneWorkbench": Bench("NoneWorkbench")}

    def activate(key):
        log("activateWorkbench", key)
        if flag("bench_fails"):
            return False
        if not flag("bench_stays"):
            state["bench"] = key
        return flag("bench_answer")

    class Picked:
        def __init__(self, o, subs=()):
            self.Object, self.ObjectName, self.SubElementNames = o, o.Name, tuple(subs)

    class Selection:
        @staticmethod
        def clearSelection():
            log("clearSelection")
            state["selected"] = []

        @staticmethod
        def addSelection(o):
            log("addSelection", o)
            if o.Name not in flag("unselectable", ()):
                state["selected"].append(Picked(o))

        @staticmethod
        def getSelectionEx(name=None):
            if flag("selection_fails"):
                raise RuntimeError("no selection")
            return list(state.setdefault("selected", []))

    class GuiDoc:
        def getInEdit(self):
            if flag("edit_fails"):
                raise RuntimeError("no edit")
            return state.get("editing")

        def resetEdit(self):
            log("resetEdit")
            state["editing"] = None

    gui.listCommands = lambda: list(flag("commands", ["Std_ViewFitAll", "Std_ViewIsometric", "PartDesign_Pad", "Sketcher_LeaveSketch", "Std_Quit", "Std_DlgPreferences", "Part_Export"]))
    gui.Command = types.SimpleNamespace(get=command)
    gui.runCommand = run_command
    gui.updateGui = lambda: log("updateGui")
    gui.activeWorkbench = lambda: Bench(state.setdefault("bench", "PartDesignWorkbench"))
    gui.listWorkbenches = benches
    gui.activateWorkbench = activate
    gui.Selection = Selection

    # ---- the menu bar and the panels ---------------------------------------------------------------

    class Signal:
        def __init__(self, title):
            self.title = title

        def emit(self):
            log("aboutToShow", self.title)

    class Menu:
        def __init__(self, title, acts):
            self.acts, self.aboutToShow = acts, Signal(title)

        def actions(self):
            return list(self.acts)

    class Action:
        def __init__(self, text="", name="", sub=None, enabled=True, checked=None, sep=False):
            self.t, self.n, self.sub, self.on, self.chk, self.sep = text, name, (Menu(text, sub) if sub is not None else None), enabled, checked, sep

        def text(self):
            return self.t

        def objectName(self):
            return self.n

        def menu(self):
            return self.sub

        def isSeparator(self):
            return self.sep

        def isEnabled(self):
            return self.on

        def isCheckable(self):
            return self.chk is not None

        def isChecked(self):
            return bool(self.chk)

        def trigger(self):
            log("trigger", self.t)
            if self.chk is not None:
                self.chk = not self.chk

    def bar_actions():
        A = Action
        return [
            A("&File", sub=[A("&New", "Std_New"), A("&Open...", "Std_Open"), A(sep=True), A("E&xit", "Std_Quit")]),
            A("&View", sub=[A("Standard views", sub=[A("Fit &all", "Std_ViewFitAll"), A("&Isometric", "Std_ViewIsometric", enabled=False)]),
                            A("&Axis cross", "Std_AxisCross", checked=False), A("Save && Co", "Std_Both"), A("", "Std_Nameless")]),
            A("", sub=[]), A("Lone", "Std_Lone"),
        ] if not flag("empty_bar") else []

    class Dock:
        def __init__(self, title, name):
            self.title, self.name = title, name

        def windowTitle(self):
            return self.title

        def objectName(self):
            return self.name

        def __repr__(self):
            return f"<dock {self.name}>"

    class Window:
        def menuBar(self):
            return Menu("bar", bar_actions())

        def findChildren(self, cls):
            return [Dock("Report view", "ReportView"), Dock("Model", "ComboView"), Dock("", "Untitled")]

        def __repr__(self):
            return "<the main window>"

    gui.getMainWindow = lambda: Window()
    pyside = types.ModuleType("PySide")
    pyside.QtGui = types.SimpleNamespace()
    pyside.QtWidgets = types.SimpleNamespace(QDockWidget=Dock)
    sys.modules["PySide"] = pyside

    class Pix:
        def save(self, path, fmt):
            log("pix.save", os.path.basename(path), fmt)
            if flag("save_fails"):
                return False
            fc.png(path, 1200, 800)
            return True

        def width(self):
            return 1200

        def height(self):
            return 800

    from agentlink import echo
    from agentlink import grab as grab_module

    grab_module.grab_window = lambda target: (log("grab_window", repr(target)), Pix())[1]
    echo.bench_ready = lambda key: log("bench_ready", key)

    # ---- the Addon Manager, its installer and the smoke test ---------------------------------------

    def mod_folder():
        return os.path.join(state["home"], "Mod")

    class Addon:
        def __init__(self, name, url=None, branch=""):
            self.name, self.url, self.branch = name, url, branch
            log("Addon", name, url, branch)

    class Installer:
        def __init__(self, ad):
            self.ad = ad

        def run(self):
            log("AddonInstaller.run", self.ad.name)
            how = flag("install", "ok")
            if how == "raises":
                raise RuntimeError("git said no")
            if how in ("ok", "half"):
                os.makedirs(os.path.join(mod_folder(), self.ad.name), exist_ok=True)
            return how == "ok"

    class Uninstaller:
        def __init__(self, ad):
            self.ad = ad

        def run(self):
            log("AddonUninstaller.run", self.ad.name)
            return not flag("remove_fails")

    class Catalog:
        def __init__(self, cat):
            self.cat = cat

        def get_available_addon_ids(self):
            return list(self.cat)

        def get_available_branches(self, i):
            return list(self.cat[i])

        def get_addon_from_id(self, name, branch):
            log("get_addon_from_id", name, branch)
            a = Addon.__new__(Addon)
            a.name, a.url, a.branch = name, f"https://example.org/{name}", branch
            return a

    def prefs_get(key):
        if flag("no_prefs"):
            raise RuntimeError("no preferences")
        return flag("catalog_url")

    mods = {
        "addonmanager_freecad_interface": types.SimpleNamespace(DataPaths=lambda: types.SimpleNamespace(mod_dir=mod_folder()), Preferences=lambda: types.SimpleNamespace(get=prefs_get)),
        "addonmanager_installer": types.SimpleNamespace(AddonInstaller=Installer),
        "addonmanager_uninstaller": types.SimpleNamespace(AddonUninstaller=Uninstaller),
        "Addon": types.SimpleNamespace(Addon=Addon),
        "AddonCatalog": types.SimpleNamespace(AddonCatalog=Catalog),
    }

    def manager(on):
        """The Addon Manager's modules there to import, or not."""
        for k, m in mods.items():
            sys.modules.pop(k, None)
            if on:
                sys.modules[k] = m

    import urllib.request

    class Answer(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout=None):
        log("urlopen", req.full_url)
        cat = flag("catalog")
        if cat is None:
            raise OSError("no network here")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("addon_catalog_cache.json", json.dumps(cat))
        return Answer(buf.getvalue())

    urllib.request.urlopen = urlopen

    from agentlink import keep, smoke

    keep.path = lambda *parts: (log("keep.path", *parts), os.path.join(state["home"], "keep", *parts))[1]
    keep.record_versions = lambda before, after, why: log("record_versions", before, after, why)
    keep._load = lambda path, default=None: (log("keep._load", os.path.basename(path)), flag("sources", default))[1]
    keep._save = lambda path, data: log("keep._save", os.path.basename(path), data)
    smoke.against = lambda **kw: (log("smoke.against", sorted(kw)), flag("smoke", {"ok": True}))[1]

    # ---- the session -------------------------------------------------------------------------------

    class Session(CoreSession):
        def __init__(self, out_dir="/tmp"):
            CoreSession.__init__(self, out_dir)
            state["params"] = {}
            state["selected"], state["editing"], state["bench"] = [], None, "PartDesignWorkbench"
            os.environ["HOME"] = out_dir
            F.ActiveDocument = self.doc
            gui.ActiveDocument = GuiDoc()
            os.makedirs(os.path.join(out_dir, "Mod", "AddonManager"), exist_ok=True)
            with open(os.path.join(out_dir, "Mod", "AddonManager", "Addon.py"), "w") as f:
                f.write("")
            manager(True)

    fc.Session, fc.Picked, fc.manager, fc.mod_folder, fc.GuiDoc = Session, Picked, manager, mod_folder, GuiDoc
    return fc
