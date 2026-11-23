# SPDX-License-Identifier: LGPL-2.1-or-later
# The cases tests/test_dataapp_data.py runs through the old handler and the
# new data entry of each converted application tool of families/app.py, and
# of `addon` (families/unattended.py), on the stand-in FreeCAD
# (tests/_dataapp_standin.py): its normal paths and each of its refusals.
import json
import os

# The family files whose tools were converted.
FILES = ("app", "unattended")
# Each converted tool and its family file's group.
CONVERTED = {**{k: "app" for k in ("pref_get", "pref_set", "pref_reset", "pref_pack", "cmd_list", "cmd_run", "menu_list", "menu_run", "workbench", "show", "selection",
                                   "window_snapshot", "snapshot_latest", "snapshot_list")}, "addon": "unattended"}
# Tools of app.py kept as code, and why.
KEPT = {
    "app_restart": "one run of the machine's own state: the open documents saved by a plan (the person's never written over), the restart mark, the other "
                   "release smoke-tested and its settings carried, a shell started that waits for this process to be gone, and Qt told to quit",
    "app_install": "starts the background installer process and reads back its state file; one of its refusals has the code unsupported, which a refuse "
                   "step does not take",
    "pref_import": "one merge over files: the settings backed up, a settings file inserted group by group through temporary files, the guarded settings "
                   "and this FreeCAD's own put back after it, macros copied",
}
SKETCH_NOTE = "A drawing tool of the sketch was still on: it was ended and the sketch closed."
# What some cases must have answered (not two empty runs alike): fields of an answer, or the whole refusal.
EXPECT = {
    ("pref_get", "a group"): {"path": "BaseApp/Preferences/View", "values": {"Gradient": {"type": "Boolean", "value": True}, "Zoom": {"type": "Float", "value": 0.2}}, "groups": ["Deep"]},
    ("pref_get", "one that is not stored"): ["refused", "not_found", "No setting 'Nope' in BaseApp/Preferences/View (FreeCAD's default applies until one is set): Gradient, Zoom"],
    ("pref_set", "an agent's own rights"): ["refused", "not_allowed", "ExtensionRepos: the person's to set (Edit > Preferences, or Agent Link's panel) — they decide what an agent may do, "
                                           "what code FreeCAD loads and what programs it runs. Nothing was changed."],
    ("pref_set", "several, the stored type kept"): {"path": "BaseApp/Preferences/View", "set": {"Gradient": {"was": True, "now": False, "type": "boolean"},
                                                                                              "Zoom": {"was": 0.2, "now": 0.5, "type": "float"},
                                                                                              "Title": {"was": None, "now": "Mine", "type": "string"}}},
    ("pref_set", "a theme, headless"): {"appliesAtNextLaunch": ["Theme"]},
    ("pref_reset", "one stored, one not"): {"path": "BaseApp/Preferences/View", "reset": ["Zoom"], "notSet": ["Nope"]},
    ("pref_reset", "a program's path"): ["refused", "not_allowed", "gmshBinaryPath: the person's to reset (Edit > Preferences, or Agent Link's panel). Nothing was changed."],
    ("pref_pack", "the packs"): {"packs": ["Dark", "Studio Dark", "Studio Light"]},
    ("pref_pack", "one applied"): {"applied": "Dark", "values": 3},
    ("cmd_list", "two at most"): {"count": 2, "workbench": "PartDesignWorkbench"},
    ("cmd_run", "one that would quit"): ["refused", "refused", "Std_Quit is not run from here: the person closes FreeCAD."],
    ("cmd_run", "leave sketch, none open"): {"ran": None, "already": "no sketch is open for editing, so there is nothing to close", "workbench": "PartDesignWorkbench", "document": "Model"},
    ("cmd_run", "leave sketch, a drawing tool still on"): {"ran": "Sketcher_LeaveSketch", "wasActive": False, "closed": "Sketch", "note": SKETCH_NOTE, "workbench": "PartDesignWorkbench",
                                                           "document": "Model"},
    ("cmd_run", "leave sketch, no document in front"): {"ran": None, "document": None},
    ("cmd_run", "leave sketch, active"): {"ran": "Sketcher_LeaveSketch", "wasActive": True, "objectsAdded": 0},
    ("cmd_run", "greyed, something selected"): ["refused", "invalid_state", "PartDesign_Pad is not active just now (its button is greyed out), so FreeCAD would do nothing: it needs another "
                                                "selection (Body.Face1,Edge2: selection { objects }), an open document or view, another workbench (PartDesignWorkbench is active: workbench "
                                                "{ activate }), or no task panel open. Nothing was run."],
    ("cmd_run", "one that adds two"): {"ran": "PartDesign_Pad", "wasActive": True, "workbench": "PartDesignWorkbench", "document": "Model", "objectsAdded": 2},
    ("cmd_run", "another document in front"): {"document": "Other", "objectsAdded": 0, "note": "The command ran on the document in front (Other), not the one the session works in (Model): "
                                                                                                "doc_switch { document, front: true } brings that one to the front first."},
    ("cmd_run", "none of that name, some near"): ["refused", "not_found", "No command 'pad' in this FreeCAD — did you mean PartDesign_Pad? cmd_list { query } finds them; a workbench's "
                                                  "commands exist only once it has been activated (workbench { activate })."],
    ("menu_list", "one menu"): {"count": 4},
    ("menu_run", "a toggle"): {"pressed": ["View", "Axis cross"], "command": "Std_AxisCross", "checked": True},
    ("menu_run", "one that would quit"): ["refused", "refused", "'File > Exit' (Std_Quit) is not run from here: the person closes FreeCAD."],
    ("menu_run", "a submenu"): ["refused", "invalid_input", "'View > Standard views' is a menu, not an item: menu_list { menu: \"View\" } shows its items."],
    ("workbench", "by its menu name"): {"active": "BIMWorkbench", "was": "PartDesignWorkbench", "workbenches": ["BIM", "NoneWorkbench", "Part Design"]},
    ("workbench", "one that will not load"): ["refused", "failed", "FreeCAD did not switch to BIMWorkbench (still PartDesignWorkbench): the workbench failed to load — report_read "
                                              "{ problems: true } shows its error."],
    ("show", "hide two, one unknown"): {"hidden": ["Block", "Pin"], "unknown": ["Nope"], "note": "Not found, so left out; the rest done."},
    ("show", "everything, a body's tip too"): {"visible": ["Block", "Body001", "Empty body"]},
    ("selection", "two"): {"selected": ["Block", "Pin"], "document": "Model"},
    ("selection", "read, with faces"): {"selected": ["Block"], "detail": [{"object": "Block", "elements": ["Face1", "Edge2"]}], "document": "Model"},
    ("selection", "a wrong name"): ["refused", "not_found", "objects: no object 'Nope' in Model — object_list names them. The selection was left as it was."],
    ("window_snapshot", "the window"): {"width": 1200, "height": 800},
    ("window_snapshot", "a panel there is not"): ["refused", "not_found", "part: no panel titled 'Tasks' — the panels: Model, Report view."],
    ("snapshot_latest", "the newest, still marked up"): {"note": "look here (the person is still marking it up)", "pins": [1]},
    ("snapshot_latest", "past the oldest"): ["refused", "invalid_input", "index: 1 to 2."],
    ("snapshot_list", "two"): {"shots": [{"path": "<out>/b.png", "original": "<out>/b0.png", "note": "look here", "pins": [1]}, {"path": "<out>/a.png", "original": "<out>/a0.png", "done": True}]},
    ("addon", "install without the person's word"): ["refused", "not_allowed", "confirm: \"install Gears\", word for word, typed by the person — an add-on is code FreeCAD runs. Nothing was changed."],
    ("addon", "remove without the person's word"): ["refused", "not_allowed", "confirm: \"remove Gears\", word for word, typed by the person — it takes their add-on away. Nothing was changed."],
    ("addon", "install from an address"): {"installed": "Gears", "folder": "<out>/Mod/Gears", "smoke": "passed"},
    ("addon", "update"): {"updated": "Gears", "smoke": "passed", "previous": "<out>/keep/addons-previous/Gears-20261116-120000"},
    ("addon", "update from a new address"): ["refused", "invalid_input", "update takes no url: it comes from where the add-on was installed from. To change where it comes from, remove it "
                                             "and install it from the new address (each with the person's confirm)."],
    ("addon", "update one put there by hand, its address given"): {"updated": "Gears", "smoke": "passed"},
    ("addon", "update one put there by hand that the catalog has not"): ["refused", "not_found", "Mine is not in FreeCAD's add-on catalog (names are exact, capitals too): addon { action: "
                                                                         "\"search\", query } finds it, or give its url (git or a folder). It was put in the Mod folder by hand, so no source is "
                                                                         "recorded: update { name, url, confirm } once names where it comes from."],
    ("addon", "update that fails"): ["refused", "failed", "The Addon Manager could not update Gears — the version before is back."],
    ("addon", "install that raises"): ["refused", "failed", "The Addon Manager could not install Gears: git said no."],
    ("addon", "update that breaks the smoke test"): ["refused", "failed", "Gears broke the smoke test after its update: families did not load; no tools. The version before is back."],
    ("addon", "install that breaks the smoke test"): ["refused", "failed", "Gears broke the smoke test after its install: . It was removed again."],
    ("addon", "one of Agent Link's own"): ["refused", "invalid_input", "AgentLink is kept up to date by agentlink_update, not here."],
}
# Refusals written in the data that no case here reaches. window_snapshot width (efficiency
# design D1, 22 Nov) came after BASE: the handler had no width, so no case compares it with one;
# tests/test_eff_a.py checks it.
UNREACHED = ["window_snapshot: width: 16 to 8192 px."]


def cases(fc, tmp, old, new):
    ns = fc.ns

    def prep(*fns, gui=True, **flags):
        def prepare(s):
            fc.fc.GuiUp = gui
            fc.state["flags"].update(flags)
            fc.state["params"] = {k: dict(v) for k, v in flags.get("params", {}).items()}  # the settings stored before the call
            for fn in fns:
                fn(s)
        return prepare

    def block(s):
        return fc.body("Block", fc.solid("block", (0, 0, 0), (10, 10, 10), volume=1000.0), ViewObject=ns(Visibility=False))

    def pin(s):
        return fc.body("Pin", fc.solid("pin", (2, 2, 0), (4, 4, 30), volume=120.0), name="Pin", ViewObject=ns(Visibility=True))

    def pd_body(s):
        pad = s.doc.new("PartDesign::Pad", "Pad", ViewObject=ns(Visibility=False), InList=["in the body"])
        s.doc.new("PartDesign::Body", "Body", Tip=pad, ViewObject=ns(Visibility=False))
        s.doc.new("App::Origin", "Origin", ViewObject=ns(Visibility=False), Shape=None)
        s.doc.new("App::FeaturePython", "Bare")  # no view: nothing to show
        s.doc.new("PartDesign::Body", "Empty", Tip=None, ViewObject=ns(Visibility=False)).__dict__.update(Label="Empty body")

    def other_front(s):
        fc.fc.ActiveDocument = fc.docs().setdefault("Other", fc.Doc("Other", "Other part"))

    def no_front(s):
        fc.fc.ActiveDocument = None
        fc.gui.ActiveDocument = None

    def editing(s):
        fc.state["editing"] = ns(Object=s.doc.new("Sketcher::SketchObject", "Sketch"))

    def editing_nameless(s):
        fc.state["editing"] = ns()

    def picked(*subs):
        return lambda s: fc.state["selected"].append(fc.Picked(block(s), subs))

    VIEW = {"BaseApp/Preferences/View": {"Gradient": ("Boolean", True), "Zoom": ("Float", 0.2)}, "BaseApp/Preferences/View/Deep": {"Level": ("Integer", 3)},
            "BaseApp/Preferences/Mod/Gmsh": {"gmshBinaryPath": ("String", "/usr/bin/gmsh"), "Count": ("Unsigned", 4), "Name": ("String", "x")}}

    def pack(s):
        folder = os.path.join(s.out_dir, "res", "Gui", "PreferencePacks", "Dark")
        os.makedirs(folder)
        with open(os.path.join(folder, "Dark.cfg"), "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0"?><FCParameters><FCParamGroup Name="Root"><FCParamGroup Name="BaseApp"><FCParamGroup Name="Preferences">'
                    '<FCParamGroup Name="View"><FCBool Name="Gradient" Value="0"/><FCUInt Name="BackgroundColor" Value="255"/><FCText Name="Theme">Dark</FCText>'
                    '</FCParamGroup></FCParamGroup></FCParamGroup></FCParamGroup></FCParameters>')

    def shots(*rows):
        def write(s):
            folder = os.path.join(s.out_dir, "AgentLink", "shots")
            os.makedirs(folder)
            for r in rows:
                for k in ("path", "original"):
                    if r.get(k) and not r[k].startswith("gone"):
                        fc.png(os.path.join(s.out_dir, r[k]), 40, 30)
            with open(os.path.join(folder, "index.json"), "w", encoding="utf-8") as f:
                json.dump([{**r, **{k: os.path.join(s.out_dir, r[k]) for k in ("path", "original") if r.get(k)}} for r in rows], f)
        return write

    TWO = ({"path": "a.png", "original": "a0.png", "done": True, "marks": [[1, 2]]}, {"path": "b.png", "original": "b0.png", "note": "look here", "pins": [1], "marks": []})

    def bad_index(s):
        os.makedirs(os.path.join(s.out_dir, "AgentLink", "shots"))
        with open(os.path.join(s.out_dir, "AgentLink", "shots", "index.json"), "w") as f:
            f.write("{ not json")

    def in_mod(*names, package=None, git=False):
        def make(s):
            for n in names:
                d = os.path.join(s.out_dir, "Mod", n)
                os.makedirs(os.path.join(d, ".git") if git else d, exist_ok=True)
                with open(os.path.join(d, "was-here.txt"), "w") as f:
                    f.write("the version before")
                if package:
                    with open(os.path.join(d, "package.xml"), "w", encoding="utf-8") as f:
                        f.write(package)
            with open(os.path.join(s.out_dir, "Mod", "a-file.txt"), "w") as f:
                f.write("not a folder")
            os.makedirs(os.path.join(s.out_dir, "Mod", ".hidden"), exist_ok=True)
        return make

    def local_repo(s):
        os.makedirs(os.path.join(s.out_dir, "repo"))

    def no_manager_folder(s):
        os.remove(os.path.join(s.out_dir, "Mod", "AddonManager", "Addon.py"))

    out = []

    def add(tool, case, prepare, args):
        out.append((tool, case, prepare, args))

    # ---- settings ----------------------------------------------------------------------------------
    G = "pref_get"
    add(G, "the default group, nothing stored", prep(gui=False), {})
    add(G, "a group", prep(params=VIEW), {"path": "BaseApp/Preferences/View"})
    add(G, "a group by its full address", prep(params=VIEW), {"path": "User parameter:BaseApp/Preferences/View/"})
    add(G, "a group that cannot list its subgroups", prep(params=VIEW, no_groups=True), {"path": "BaseApp/Preferences/View"})
    add(G, "one setting", prep(params=VIEW), {"path": "BaseApp/Preferences/View", "name": "Zoom"})
    add(G, "one that is not stored", prep(params=VIEW), {"path": "BaseApp/Preferences/View", "name": "Nope"})
    P = "pref_set"
    V = "BaseApp/Preferences/View"
    add(P, "nothing to set", prep(params=VIEW), {"path": V})
    add(P, "a name with no value", prep(params=VIEW), {"path": V, "name": "Zoom"})
    add(P, "an agent's own rights", prep(), {"path": "BaseApp/Preferences/Mod/AgentLink", "name": "ExtensionRepos", "value": "x"})
    add(P, "a program's path among others", prep(params=VIEW), {"path": "BaseApp/Preferences/Mod/Gmsh", "values": {"Count": 5, "gmshBinaryPath": "/tmp/evil"}})
    add(P, "the Addon Manager's group", prep(), {"path": "BaseApp/Preferences/Addons", "name": "AnyThing", "value": 1})
    add(P, "the macro folder", prep(), {"path": "User parameter:BaseApp/Preferences/Macro", "name": "MacroPath", "value": "/tmp"})
    add(P, "one new, a boolean", prep(gui=False), {"path": V, "name": "Gradient", "value": True})
    add(P, "several, the stored type kept", prep(params=VIEW), {"path": V, "values": {"Gradient": "off", "Zoom": 0.5, "Title": "Mine"}})
    add(P, "name and values together", prep(params=VIEW), {"path": V, "values": {"Zoom": 1}, "name": "Count", "value": 7})
    add(P, "a type given", prep(), {"path": V, "name": "Colour", "value": "255", "type": "uint"})
    add(P, "a theme, headless", prep(gui=False), {"name": "Theme", "value": "Dark"})
    add(P, "a theme, in the window", prep(), {"name": "Theme", "value": "Dark"})
    add(P, "the main window's own", prep(gui=False), {"path": "BaseApp/MainWindow", "values": {"Geometry": "abc", "Size": 3}})
    add(P, "true or false in words that are neither", prep(params=VIEW), {"path": V, "values": {"Zoom": 2, "Gradient": "maybe"}})
    add(P, "a whole number with a fraction", prep(params=VIEW), {"path": V + "/Deep", "name": "Level", "value": 1.5})
    add(P, "a whole number in words", prep(params=VIEW), {"path": V + "/Deep", "name": "Level", "value": "many"})
    add(P, "an unsigned below nothing", prep(params=VIEW), {"path": "BaseApp/Preferences/Mod/Gmsh", "name": "Count", "value": -1})
    add(P, "crash: a float in words", prep(params=VIEW), {"path": V, "name": "Zoom", "value": "big"})
    Rs = "pref_reset"
    add(Rs, "no names", prep(params=VIEW), {"path": V})
    add(Rs, "a program's path", prep(params=VIEW), {"path": "BaseApp/Preferences/Mod/Gmsh", "names": ["Count", "gmshBinaryPath"]})
    add(Rs, "one stored, one not", prep(params=VIEW), {"path": V, "names": ["Zoom", "Nope"]})
    add(Rs, "each kind", prep(params={"G": {"b": ("Boolean", True), "i": ("Integer", 1), "u": ("Unsigned", 2), "f": ("Float", 0.5), "s": ("String", "x"), "odd": ("Odd", 1)}}, gui=False),
        {"path": "G", "names": ["b", "i", "u", "f", "s", "odd"]})
    add(Rs, "a restart key", prep(params={V: {"Theme": ("String", "Dark")}}, gui=False), {"path": V, "names": ["Theme"]})
    K = "pref_pack"
    add(K, "the packs", prep(pack, gui=False), {})
    add(K, "one there is not", prep(pack), {"apply": "Neon"})
    add(K, "one applied", prep(pack, params=VIEW), {"apply": "Dark"})
    add(K, "the repository's own applied", prep(gui=False), {"apply": "Studio Dark"})

    # ---- commands ----------------------------------------------------------------------------------
    # "shortcut": the key FreeCAD 1.1's Command.getInfo() has (src/Gui/CommandPyImp.cpp). The handler read
    # "shortcutText", which FreeCAD never gives (tests/test_dataapp_data.py: a meant difference).
    INFO = {"Std_ViewFitAll": {"menuText": "Fit &all", "toolTip": "<b>Fits</b> the whole content on the screen ", "shortcut": "V, F"},
            "PartDesign_Pad": {"menuText": "Pad", "toolTip": "", "shortcutText": ""}, "Std_Quit": {"menuText": "E&xit", "toolTip": "Quits the application"},
            "Sketcher_LeaveSketch": {}}
    L = "cmd_list"
    add(L, "headless", prep(gui=False), {})
    add(L, "all of them", prep(info=INFO), {})
    add(L, "by part of a name", prep(info=INFO), {"query": "VIEW"})
    add(L, "by words of the tip or menu", prep(info=INFO), {"query": "the"})
    add(L, "nothing like it", prep(info=INFO), {"query": "zzz", "limit": "all"})
    add(L, "two at most", prep(info=INFO), {"limit": 2})
    add(L, "a limit of nothing", prep(info=INFO), {"limit": 0})
    add(L, "crash: a limit in words", prep(info=INFO), {"limit": "all"})
    C = "cmd_run"
    add(C, "headless", prep(gui=False), {"name": "Std_ViewFitAll"})
    add(C, "one that would quit", prep(), {"name": "Std_Quit"})
    add(C, "one of a family that asks in a dialog", prep(), {"name": "Part_Export"})
    add(C, "a macro by its number", prep(), {"name": "Std_Macro_3"})
    add(C, "none of that name, some near", prep(), {"name": "pad"})
    add(C, "none of that name", prep(), {"name": "Draft_Line"})
    add(C, "no name", prep(), {})
    add(C, "a view command", prep(block), {"name": "Std_ViewFitAll"})
    add(C, "one that adds two", prep(block, adds=2), {"name": "PartDesign_Pad", "index": 1})
    add(C, "one that cannot say whether it is active", prep(cannot_say=("Std_ViewFitAll",)), {"name": "Std_ViewFitAll"})
    add(C, "one FreeCAD lists but does not hand out", prep(no_command=("Std_ViewFitAll",)), {"name": "Std_ViewFitAll"})
    add(C, "greyed, nothing selected", prep(greyed=("PartDesign_Pad",)), {"name": "PartDesign_Pad"})
    add(C, "greyed, something selected", prep(picked("Face1", "Edge2"), greyed=("PartDesign_Pad",)), {"name": "PartDesign_Pad"})
    add(C, "greyed, a whole object selected", prep(picked(), greyed=("PartDesign_Pad",)), {"name": "PartDesign_Pad"})
    add(C, "greyed, the selection unreadable", prep(greyed=("PartDesign_Pad",), selection_fails=True), {"name": "PartDesign_Pad"})
    S = "Sketcher_LeaveSketch"
    add(C, "leave sketch, none open", prep(block, greyed=(S,)), {"name": S})
    add(C, "leave sketch, a drawing tool still on", prep(editing, greyed=(S,)), {"name": S})
    add(C, "leave sketch, what is open has no object", prep(editing_nameless, greyed=(S,)), {"name": S})
    add(C, "leave sketch, the edit unreadable", prep(editing, greyed=(S,), edit_fails=True), {"name": S})
    add(C, "leave sketch, no document in front", prep(editing, no_front, greyed=(S,)), {"name": S})
    add(C, "leave sketch, another document in front", prep(editing, other_front, greyed=(S,)), {"name": S})
    add(C, "leave sketch, active", prep(editing), {"name": S})
    add(C, "leave sketch, cannot say", prep(editing, cannot_say=(S,)), {"name": S})
    add(C, "another document in front", prep(block, other_front), {"name": "Std_ViewFitAll"})
    add(C, "the front changes as it runs", prep(block, front_after=None), {"name": "Std_ViewFitAll"})
    add(C, "no document in front", prep(no_front), {"name": "Std_ViewFitAll"})
    add(C, "crash: an index in words", prep(), {"name": "Std_ViewFitAll", "index": "first"})

    # ---- menus -------------------------------------------------------------------------------------
    M = "menu_list"
    add(M, "headless", prep(gui=False), {})
    add(M, "the whole bar", prep(), {})
    add(M, "one menu", prep(), {"menu": "view", "limit": 1})
    add(M, "the first two", prep(), {"limit": 2})
    add(M, "a menu there is not", prep(), {"menu": "Tools"})
    add(M, "an item is not a menu", prep(), {"menu": "Lone"})
    add(M, "an empty bar", prep(empty_bar=True), {})
    add(M, "crash: a limit in words", prep(), {"limit": "few"})
    N = "menu_run"
    add(N, "no path", prep(), {"path": []})
    add(N, "headless", prep(gui=False), {"path": ["View", "Fit all"]})
    add(N, "no such menu", prep(), {"path": ["Tools", "Fit all"]})
    add(N, "no such item", prep(), {"path": ["View", "Standard views", "Upside down"]})
    add(N, "through an item", prep(), {"path": ["File", "New", "Deeper"]})
    add(N, "one that would quit", prep(), {"path": ["File", "Exit"]})
    add(N, "one that asks in a dialog", prep(), {"path": ["file", "open…"]})
    add(N, "a submenu", prep(), {"path": ["View", "Standard views"]})
    add(N, "a top menu", prep(), {"path": ["View"]})
    add(N, "greyed", prep(), {"path": ["View", "Standard views", "Isometric"]})
    add(N, "an item", prep(), {"path": ["view", "standard views", "fit all..."]})
    add(N, "a toggle", prep(), {"path": ["View", "Axis cross"]})
    add(N, "a title with an ampersand, no command", prep(), {"path": ["View", "Save & Co"]})
    add(N, "a top item with no menu", prep(), {"path": ["Lone"]})

    # ---- workbenches -------------------------------------------------------------------------------
    W = "workbench"
    add(W, "headless", prep(gui=False), {})
    add(W, "which", prep(), {})
    add(W, "by its menu name", prep(), {"activate": "bim"})
    add(W, "by its menu name with a space", prep(), {"activate": "Part Design"})
    add(W, "by its own name", prep(), {"activate": "NoneWorkbench"})
    add(W, "by its own name without the ending", prep(), {"activate": "None"})
    add(W, "one there is not", prep(), {"activate": "Gears"})
    add(W, "one that will not load", prep(bench_fails=True), {"activate": "BIM"})
    add(W, "one FreeCAD stays out of", prep(bench_stays=True), {"activate": "BIM"})
    add(W, "one FreeCAD says true for", prep(bench_answer=True), {"activate": "BIM"})

    # ---- shown and selected ------------------------------------------------------------------------
    H = "show"
    add(H, "headless", prep(block, gui=False), {})
    add(H, "everything, a body's tip too", prep(block, pd_body), {})
    add(H, "everything, by the word", prep(block, pin), {"objects": "all", "visible": True})
    add(H, "hide everything", prep(block, pin, pd_body), {"visible": False})
    add(H, "hide two, one unknown", prep(block, pin), {"objects": ["Block", "Nope", "Pin", "Block"], "visible": False})
    add(H, "one by its name alone", prep(block, pin), {"objects": "Pin", "visible": 0})
    add(H, "a body by its label, a thing with no view", prep(pd_body), {"objects": ["Empty body", "Bare", "Body"]})
    add(H, "none of them there", prep(block), {"objects": ["Nope", 7]})
    add(H, "an empty list", prep(block), {"objects": []})
    X = "selection"
    add(X, "headless", prep(block, gui=False), {"objects": ["Block"]})
    add(X, "cleared", prep(picked("Face1")), {})
    add(X, "cleared, an empty list", prep(picked("Face1")), {"objects": [], "clear": True})
    add(X, "read, with faces", prep(picked("Face1", "Edge2")), {"clear": False})
    add(X, "read, whole objects", prep(picked()), {"clear": False})
    add(X, "read, nothing selected", prep(), {"clear": False})
    add(X, "not a list", prep(block), {"objects": "Block"})
    add(X, "a name that is empty", prep(block), {"objects": ["Block", ""]})
    add(X, "a name that is a number", prep(block), {"objects": [3]})
    add(X, "a wrong name", prep(picked("Face1"), pin), {"objects": ["Pin", "Nope"]})
    add(X, "two", prep(block, pin), {"objects": ["Block", "Pin"]})
    add(X, "one twice, by name and label", prep(block, pin), {"objects": ["Pin", "Pin"], "clear": False})
    add(X, "one that will not take it", prep(block, pin, unselectable=("Pin",)), {"objects": ["Block", "Pin"]})

    # ---- pictures ----------------------------------------------------------------------------------
    Wn = "window_snapshot"
    add(Wn, "headless", prep(gui=False), {"inline": True})
    add(Wn, "the window", prep(), {"inline": True})
    add(Wn, "a panel by its title, to a path, not sent", prep(), {"part": "report VIEW", "path": "panel.png", "inline": False})
    add(Wn, "a panel by its own name", prep(), {"inline": True, "part": "comboview"})
    add(Wn, "a panel there is not", prep(), {"inline": True, "part": "Tasks"})
    add(Wn, "it will not save", prep(save_fails=True), {"inline": True, "path": "sub/window.png"})
    SL = "snapshot_latest"
    add(SL, "none yet", prep(gui=False), {})
    add(SL, "an index that does not read", prep(bad_index, gui=False), {})
    add(SL, "the newest, still marked up", prep(shots(*TWO), gui=False), {})
    add(SL, "the one before, done", prep(shots(*TWO), gui=False), {"index": 2})
    add(SL, "the original", prep(shots(*TWO), gui=False), {"index": 1, "original": True})
    add(SL, "its picture gone", prep(shots({"path": "gone.png", "original": "gone0.png", "done": True, "note": "kept"}), gui=False), {})
    add(SL, "past the oldest", prep(shots(*TWO), gui=False), {"index": 3})
    add(SL, "before the newest", prep(shots(*TWO), gui=False), {"index": 0})
    add(SL, "crash: an index in words", prep(shots(*TWO), gui=False), {"index": "last"})
    add("snapshot_list", "none", prep(gui=False), {})
    add("snapshot_list", "two", prep(shots(*TWO), gui=False), {})

    # ---- the Addon Manager -------------------------------------------------------------------------
    A = "addon"
    CAT = {"Gears": ["main", "dev", "a", "b", "c"], "gearbox": ["master"], "Other": []}
    PKG = "<package><name>Gears</name><version> 1.2.0 </version><description>Makes\n  gears of many kinds</description></package>"
    HTTPS = "https://example.org/Gears.git"
    add(A, "a FreeCAD before the manager ran headless", prep(gui=False, version=["1", "0", "2"]), {})
    add(A, "no Addon Manager in this FreeCAD", prep(no_manager_folder, gui=False), {})
    add(A, "its modules do not load", prep(lambda s: fc.manager(False), gui=False), {"action": "list"})
    add(A, "what is installed", prep(in_mod("Gears", package=PKG), in_mod("AgentLink", git=True), in_mod("Plain"), gui=False), {})
    add(A, "search, all of the catalog", prep(gui=False, catalog=CAT), {"action": "search"})
    add(A, "search by part of a name", prep(gui=False, catalog=CAT, catalog_url="https://example.org/cache.zip"), {"action": "search", "query": "GEAR"})
    add(A, "search with no network", prep(gui=False, no_prefs=True), {"action": "search", "query": "gear"})
    add(A, "no name", prep(gui=False), {"action": "install"})
    add(A, "a name that climbs", prep(gui=False), {"action": "remove", "name": "../Gears", "confirm": "remove ../Gears"})
    add(A, "one of Agent Link's own", prep(gui=False), {"action": "update", "name": "AgentLink", "confirm": "update AgentLink"})
    add(A, "install without the person's word", prep(gui=False), {"action": "install", "name": "Gears"})
    add(A, "update with other words", prep(in_mod("Gears"), gui=False), {"action": "update", "name": "Gears", "confirm": "install Gears"})
    add(A, "remove without the person's word", prep(in_mod("Gears"), gui=False), {"action": "remove", "name": "Gears", "confirm": " "})
    add(A, "an action there is not", prep(gui=False), {"action": "upgrade", "name": "Gears", "confirm": "upgrade Gears"})
    add(A, "remove one not installed", prep(gui=False), {"action": "remove", "name": "Gears", "confirm": "remove Gears"})
    add(A, "remove", prep(in_mod("Gears"), gui=False), {"action": "remove", "name": "Gears", "confirm": " remove Gears "})
    add(A, "remove that fails", prep(in_mod("Gears"), gui=False, remove_fails=True), {"action": "remove", "name": "Gears", "confirm": "remove Gears"})
    add(A, "install one that is there", prep(in_mod("Gears"), gui=False), {"action": "install", "name": "Gears", "confirm": "install Gears"})
    add(A, "update one that is not there", prep(gui=False), {"action": "update", "name": "Gears", "confirm": "update Gears"})
    add(A, "update from a new address", prep(in_mod("Gears"), gui=False, sources={"Gears": {"url": "https://example.org/old.git", "branch": None}}),
        {"action": "update", "name": "Gears", "confirm": "update Gears", "url": HTTPS})
    add(A, "update one put there by hand, its address given", prep(in_mod("Gears"), gui=False), {"action": "update", "name": "Gears", "confirm": "update Gears", "url": HTTPS, "branch": "dev"})
    add(A, "update one put there by hand, a source with no address", prep(in_mod("Gears"), gui=False, sources={"Gears": {"url": None, "branch": "main"}}),
        {"action": "update", "name": "Gears", "confirm": "update Gears", "url": HTTPS})
    add(A, "update one put there by hand that the catalog has not", prep(in_mod("Mine"), gui=False, catalog={"Gears": []}), {"action": "update", "name": "Mine", "confirm": "update Mine"})
    add(A, "install from no address at all", prep(gui=False), {"action": "install", "name": "Gears", "confirm": "install Gears", "url": "ftp://example.org/Gears"})
    add(A, "install from an address", prep(gui=False), {"action": "install", "name": "Gears", "confirm": "install Gears", "url": HTTPS, "branch": "dev"})
    add(A, "install from a folder", prep(local_repo, gui=False), {"action": "install", "name": "Gears", "confirm": "install Gears", "url": "~/repo"})
    add(A, "install from the catalog", prep(gui=False, catalog=CAT), {"action": "install", "name": "Gears", "confirm": "install Gears"})
    add(A, "install from the catalog, a branch", prep(gui=False, catalog=CAT), {"action": "install", "name": "Gears", "confirm": "install Gears", "branch": "dev"})
    add(A, "install one the catalog has not", prep(gui=False, catalog=CAT), {"action": "install", "name": "gears", "confirm": "install gears"})
    add(A, "install with no catalog to be had", prep(gui=False), {"action": "install", "name": "Gears", "confirm": "install Gears"})
    add(A, "install that fails", prep(gui=False, install="nothing"), {"action": "install", "name": "Gears", "confirm": "install Gears", "url": HTTPS})
    add(A, "install that fails half-way", prep(gui=False, install="half"), {"action": "install", "name": "Gears", "confirm": "install Gears", "url": HTTPS})
    add(A, "install that raises", prep(gui=False, install="raises"), {"action": "install", "name": "Gears", "confirm": "install Gears", "url": HTTPS})
    add(A, "install that breaks the smoke test", prep(gui=False, smoke={"ok": False}), {"action": "install", "name": "Gears", "confirm": "install Gears", "url": HTTPS})
    SRC = {"Gears": {"url": HTTPS, "branch": "dev"}}
    add(A, "update", prep(in_mod("Gears"), gui=False, sources=SRC), {"action": "update", "name": "Gears", "confirm": "update Gears"})
    add(A, "update, another branch", prep(in_mod("Gears"), gui=False, sources=SRC), {"action": "update", "name": "Gears", "confirm": "update Gears", "branch": "main"})
    add(A, "update one whose address is not known", prep(in_mod("Gears"), gui=False, catalog=CAT, sources=None), {"action": "update", "name": "Gears", "confirm": "update Gears"})
    add(A, "update that fails", prep(in_mod("Gears"), gui=False, sources=SRC, install="nothing"), {"action": "update", "name": "Gears", "confirm": "update Gears"})
    add(A, "update that raises half-way", prep(in_mod("Gears"), gui=False, sources=SRC, install="raises"), {"action": "update", "name": "Gears", "confirm": "update Gears"})
    add(A, "update that breaks the smoke test", prep(in_mod("Gears"), gui=False, sources=SRC, smoke={"ok": False, "failures": ["families did not load", "no tools"]}),
        {"action": "update", "name": "Gears", "confirm": "update Gears"})
    return out
