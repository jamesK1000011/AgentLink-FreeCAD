# SPDX-License-Identifier: LGPL-2.1-or-later
# The rest of the window, for an agent: FreeCAD's settings (any parameter
# group, and the preference packs applied by their values), its commands
# (listed with what they do, run by name), its menus (walked as the person
# sees them, an item pressed by its path) and its workbenches. Settings work
# headless too; commands and menus need the window (the link on).
#
# A command or menu item that would open a modal dialog would hold the
# window until someone closes it, and the agent with it: those are refused,
# with the tool that does the same job named.

import json
import os
import re
import xml.etree.ElementTree as ET

import FreeCAD

from .. import paths, runners
from ..protocol import Tool, ToolError
from ..tools import obj

GROUP = "app"
INFO = "FreeCAD itself: settings (any parameter, preference packs), commands and menus run by name in the window, workbenches."

_INSTALL_DIR = os.path.join(os.path.expanduser("~"), "AgentLink", "install")

# FreeCAD 1.1 on keeps its settings and add-ons in a folder per release
# (…/FreeCAD/v1-1); the first time a release opens it asks, in a dialog,
# whether to copy the older ones. Done here beforehand, the same way
# (ApplicationDirectories.migrateAllPaths), so it opens with them.
_MIGRATE = (
    "import FreeCAD as F,os,sys\n"
    "AD=getattr(F,'ApplicationDirectories',None)\n"
    "p=[F.getUserAppDataDir(),F.getUserConfigDir()]\n"
    "if AD is None: sys.stdout.write('@@unversioned@@')\n"
    "elif all(AD.usingCurrentVersionConfig(x) for x in p):\n"
    "  done=[]\n"
    "  for x in p:\n"
    "    x=x.rstrip('/'); old=os.path.dirname(x)\n"
    "    if not os.path.exists(os.path.join(x,'.agentlink-migrated')) and os.path.isdir(old):\n"
    "      AD.migrateConfig(old,x); open(os.path.join(x,'.agentlink-migrated'),'w').close(); done.append(x)\n"
    "  sys.stdout.write(('@@migrated@@' if done else '@@already@@')+repr(done or p))\n"
    "else:\n"
    "  new=AD.migrateAllPaths(p)\n"
    "  sys.stdout.write('@@migrated@@'+repr(new))\n"
)
# Run in the new release once its own folders exist. FreeCAD 1.1.3 on
# macOS 26+ hangs for good the first time a pop-up notification opens: Qt
# logs a warning while making its window, the log goes back to the
# notification area, which waits on itself. The pop-ups off (the list
# behind the bell stays).
_QUIET = (
    "import FreeCAD as F,sys\n"
    "g=F.ParamGet('User parameter:BaseApp/Preferences/NotificationArea')\n"
    "g.SetBool('NonIntrusiveNotificationsEnabled',False)\n"
    "F.saveParameter()\n"
    "sys.stdout.write('@@quiet@@'+F.getUserConfigDir())\n"
)


def _freecad_bundle(target):
    """A FreeCAD release to switch to: an app bundle in /Applications or
    ~/Applications whose Info.plist names FreeCAD. Anything else is refused:
    the path is run, and a folder the agent made itself (export_file makes
    folders) must not pass for an app."""
    import plistlib

    t = os.path.realpath(os.path.expanduser(str(target)).rstrip("/"))
    homes = [os.path.realpath("/Applications"), os.path.realpath(os.path.expanduser("~/Applications"))]
    if not (t.endswith(".app") and os.path.dirname(t) in homes and os.path.isdir(os.path.join(t, "Contents"))):
        raise ToolError("not_found", f"No FreeCAD app at {target}: a release in /Applications or ~/Applications (app_install says where it put one).")
    try:
        with open(os.path.join(t, "Contents", "Info.plist"), "rb") as f:
            info = plistlib.load(f)
    except Exception:
        info = {}
    names = " ".join(str(info.get(k, "")) for k in ("CFBundleIdentifier", "CFBundleName", "CFBundleExecutable")).lower()
    if "freecad" not in names:
        raise ToolError("not_found", f"{t} is not a FreeCAD app (its Info.plist names {info.get('CFBundleIdentifier') or 'nothing'}).")
    return t


# Settings the agent may not change: the code FreeCAD loads (extension
# repositories, the macro folder), the programs it runs (solver and mesher
# paths), and what add-ons guard of their own (hooks.guard_setting: an
# add-on's switch for how far an agent goes). Set by the person in
# Preferences or the panel; an agent that could set them could raise its
# own rights or have its code run.
_GUARDED = {("Mod/AgentLink", "ExtensionRepos"), ("Macro", "MacroPath"), ("Mod/AgentLink", "WindowApprove")}
# Names of programs, converters, editors and code: a name that holds one of
# these anywhere (case ignored). Red team 4, R4-7: the Draft ODA converter
# (TeighaFileConverter), external editors, Python paths.
_GUARDED_WORDS = ("binarypath", "executable", "exepath", "binpath", "converter", "pythonpath", "nativedialog", "nativefiledialog")
# Names that end in one of these (case ignored): a setting that says where
# files go or come from, or which program, server or code is used
# (…Path, …Dir, …Folder, …File, …Url, …Repos, …Editor, …Program, …Macro).
_GUARDED_ENDS = re.compile(r"(path|paths|dir|dirs|directory|folder|folders|(?<!pro)file|files|url|urls|uri|repo|repos|repositories|"
                           r"editor|program|binary|python|interpreter|server|proxy|location|macro|macros|script|scripts|command)$", re.I)


# Whole groups no agent sets: the Addon Manager's (its catalog address and
# custom repositories decide what code an update installs), the macro
# settings, and the file dialog settings (Dialog/DontUseNativeDialog turns on
# Qt's own dialog, where a typed path is not checked: R4-2).
_GUARDED_GROUPS = ("Addons", "AddonManager", "Mod/AddonManager", "Macro", "Dialog")


def path_like(value):
    """True for a value that names a file, a folder or an address: an
    absolute or home path, a Windows drive, "..", or a URL (R4-7)."""
    if not isinstance(value, str):
        return False
    v = value.strip()
    return bool(v) and (v.startswith(("/", "~", "\\", "$")) or "://" in v or v.lower().startswith("file:") or bool(re.match(r"^[A-Za-z]:[\\/]", v))
                        or bool(re.search(r"(^|[\\/])\.\.([\\/]|$)", v)))


def guarded(path, name, value=None):
    """True for a setting that the person sets, not an agent: the groups and
    names above, the switches that add-ons guard, and (value given) a value
    that is a path or an address."""
    p = (path or "").strip("/")
    if p.startswith(ROOT):
        p = p[len(ROOT):]
    if any(p == g or p.endswith("/" + g) or p.startswith(g + "/") or ("/" + g + "/") in ("/" + p + "/") for g in _GUARDED_GROUPS):
        return True
    from .. import hooks

    for gp, gn in _GUARDED | set(hooks.GUARDED):
        gp = (gp or "").strip("/")
        if name == gn and (p.endswith(gp) or p == gp):
            return True
    n = str(name or "")
    if any(w in n.lower() for w in _GUARDED_WORDS) or _GUARDED_ENDS.search(n):
        return True
    return path_like(value)


def _all_values(path="BaseApp"):
    """Every setting as it stands, the whole tree walked."""
    out = {}
    g = FreeCAD.ParamGet(ROOT + path)
    for row in g.GetContents() or []:
        out[(path, row[1])] = (row[0], row[2])
    for sub in g.GetGroups() or []:
        out.update(_all_values(path + "/" + sub))
    return out


def _guarded_values(path="BaseApp"):
    """Every setting as it stands (the guarded ones are found against it
    after a merge: a value that became a path counts too)."""
    return _all_values(path)


def _guarded_restore(before):
    """Put the guarded settings back as they were: changed ones reset,
    new ones taken out. A setting counts as guarded by its name, or by its
    value before or after (a path or an address). Returns the names put
    back."""
    after = _all_values()
    back = []
    for key, (kind, val) in after.items():
        if before.get(key) == (kind, val):
            continue
        if not (guarded(key[0], key[1], val) or (key in before and guarded(key[0], key[1], before[key][1]))):
            continue
        g = FreeCAD.ParamGet(ROOT + key[0])
        rem = {"Boolean": g.RemBool, "Integer": g.RemInt, "Unsigned": g.RemUnsigned, "Float": g.RemFloat, "String": g.RemString}.get(kind)
        if rem:
            rem(key[1])
        if key in before:
            k0, v0 = before[key]
            {"Boolean": g.SetBool, "Integer": g.SetInt, "Unsigned": g.SetUnsigned, "Float": g.SetFloat, "String": g.SetString}[k0](key[1], v0)
        back.append("/".join(key))
    return back


def _insert_cfg(path):
    """Merge a settings file into the running settings, group by top-level
    group (FreeCAD gives no handle on the root itself): its values win."""
    import tempfile

    top = ET.parse(path).getroot().find("FCParamGroup")
    if top is None:
        raise ToolError("invalid_input", path + " is not a FreeCAD settings file.")
    done = []
    for g in top.findall("FCParamGroup"):
        name = g.get("Name")
        if not name:
            continue
        doc = ET.Element("FCParameters")
        r = ET.SubElement(doc, "FCParamGroup", Name="Root")
        r.extend(list(g))
        fd, tmp = tempfile.mkstemp(suffix=".cfg")
        os.close(fd)
        try:
            ET.ElementTree(doc).write(tmp, encoding="utf-8", xml_declaration=True)
            FreeCAD.ParamGet(ROOT + name).Insert(tmp)
        finally:
            os.remove(tmp)
        done.append(name)
    return done


CFG_VALUES = ("FCBool", "FCInt", "FCUInt", "FCFloat", "FCText")


def cfg_count(path):
    """How many settings (values, not groups) a settings file holds: its
    FCBool, FCInt, FCUInt, FCFloat and FCText entries under its groups —
    what pref_import brought in, for its words (p8: no count was said).
    None when it cannot be read."""
    try:
        top = ET.parse(path).getroot().find("FCParamGroup")
        return sum(1 for e in top.iter() if e.tag in CFG_VALUES) if top is not None else None
    except Exception:  # noqa: BLE001
        return None


def version_older(want, running):
    """True when the release number want ("1.0.2") is older than running
    (FreeCAD.Version()[:3]); "latest" never is."""
    if str(want or "").strip() in ("", "latest"):
        return False
    try:
        w = [int(x) for x in str(want).split(".")]
        r = [int(x) for x in list(running)[:3]]
    except (TypeError, ValueError):
        return False
    n = max(len(w), len(r))
    return w + [0] * (n - len(w)) < r + [0] * (n - len(r))


def install_approval(what, version, app=None, running=()):
    """approve_code for app_install (red team 4, R4-12): it puts an app in
    place and runs it. {"ok": True} once the person approved this one
    action, else the pending answer with the approve_code arguments. A
    release older than the running one says so in what the person sees."""
    from .. import approvals

    run = ".".join(str(x) for x in list(running)[:3])
    older = version_older(version, running)
    if what == "open":
        title = f"Open the FreeCAD app {app} with this FreeCAD's settings and add-ons"
        lines = [f"App: {app}", "The app runs on this computer, with the add-ons copied into it."]
    else:
        title = f"Install FreeCAD {version} beside this one ({'OLDER than the running ' + run if older else 'running ' + run})"
        lines = [f"Release: {version}, from FreeCAD's GitHub release (SHA-256, code signature and team checked).",
                 "The app is put in /Applications and runs at app_restart { app }."]
        if older:
            lines.append(f"This release is older than the running {run}: an older FreeCAD can have file-reader faults that are fixed now.")
    shown = {"source": app if what == "open" else "https://github.com/FreeCAD/FreeCAD/releases",
             "version": (version or "") + (f" (older than the running {run})" if older else ""),
             "risk": "puts an app in place and runs it" if what != "open" else "runs an app"}
    try:
        return approvals.ask("addon-install", f"FreeCAD {version or app}", title, lines, approvals.identity("app_install", what, version, app), shown=shown)
    except approvals.Refused as e:
        raise ToolError(e.code, e.message)


def _alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def _bundle_python(app=None):
    import sys

    if app is None:
        exe = sys.executable
        if ".app/" not in exe:
            return None
        app = exe.split(".app/")[0] + ".app"
    for n in ("python3", "python"):
        p = os.path.join(app, "Contents", "Resources", "bin", n)
        if os.path.exists(p):
            return p
    return None


def _clean_env():
    """This FreeCAD's environment without what its bundle set for its own
    Python and Qt: another release started from here must find its own."""
    env = dict(os.environ)
    for k in list(env):
        if k.startswith(("PYTHON", "DYLD_", "QT_", "FREECAD", "CONDA", "__PYVENV")) or k in ("LD_LIBRARY_PATH", "GMSH_PATH"):
            env.pop(k)
    return env


def _temp_copy(file):
    """True for a file in a temporary folder an add-on opened a copy from
    (agentlink-recovered-…, agentlink-restore-…)."""
    folder = os.path.basename(os.path.dirname(str(file or "")))
    return folder.startswith(("agentlink-recovered-", "agentlink-restore-"))


def _unsaved_dir():
    from .. import keep

    return keep.path("unsaved")


def _scratch(file):
    """A file that is Agent Link's own, not the person's: a copy reopened
    from a temporary folder, or an agent's never-saved document kept in
    ~/AgentLink/unsaved at a restart. Saved in place and reopened by path at
    the next restart, so it comes back once, never as a copy of a copy."""
    f = os.path.abspath(str(file or ""))
    if not file:
        return False
    if _temp_copy(f):
        return True
    root = os.path.abspath(_unsaved_dir())
    return os.path.dirname(f) == root


def unsaved_path(label, taken=()):
    """Where an agent's never-saved document is kept at a restart: a file
    named after its label in ~/AgentLink/unsaved, not one already used."""
    base = re.sub(r"\s*\(recovered[^)]*\)\s*$", "", str(label or ""))
    base = re.sub(r"[^A-Za-z0-9 _.-]+", "_", base).strip(" .") or "Unnamed"
    folder = _unsaved_dir()
    p = os.path.join(folder, base + ".FCStd")
    n = 2
    while os.path.exists(p) or p in taken:
        p = os.path.join(folder, f"{base}-{n}.FCStd")
        n += 1
    return p


def restart_plan(docs, changed, rule, mine, discard=False):
    """[(doc, how)] for app_restart, how one of: save (over its file, by the
    rule), keep (Agent Link's own file, saved in place), unsaved (an agent's
    never-saved document, saved into ~/AgentLink/unsaved), drop, copy (the
    person's: a copy reopened beside it by the reopen add-on)."""
    plan = []
    for d in docs:
        if not changed(d):
            continue
        f = getattr(d, "FileName", "") or ""
        if f and _scratch(f):
            plan.append((d, "keep"))
        elif f and (rule == "all" or (rule == "agent" and d.Name in mine)):
            plan.append((d, "save"))
        elif not f and discard:
            plan.append((d, "drop"))
        elif not f and rule != "none" and d.Name in mine:
            plan.append((d, "unsaved"))
        else:
            plan.append((d, "copy"))
    return plan


def _carry_settings(app):
    """Run the other release headless to copy this one's settings and
    add-ons into its versioned folders (and, on a Mac, turn off the pop-up
    notifications that hang 1.1.3 there); says what it did."""
    import platform
    import subprocess

    bin_ = os.path.join(app, "Contents", "Resources", "bin")
    cmd = next((os.path.join(bin_, n) for n in ("freecadcmd", "FreeCADCmd") if os.path.exists(os.path.join(bin_, n))), None)
    if cmd is None:
        return "no FreeCADCmd in " + app + ": its first start asks about settings itself"

    def run(code):
        try:
            r = subprocess.run([cmd, "-c", code], capture_output=True, text=True, timeout=300, env=_clean_env())
        except Exception as e:
            return None, str(e)
        out = (r.stdout or "") + (r.stderr or "")
        m = re.search(r"@@(\w+)@@(.*)", out)
        return (m.group(1), m.group(2)) if m else (None, out.strip()[-300:] or "no answer")

    kind, what = run(_MIGRATE)
    said = {"migrated": "settings and add-ons copied: " + what, "already": "it has its own settings already: " + what, "unversioned": "it shares this one's settings folder"}.get(kind, "not carried over: " + what)
    if platform.system() == "Darwin":
        q, w = run(_QUIET)
        said += "; pop-up notifications off (they hang 1.1.3 on this macOS)" if q == "quiet" else "; pop-up notifications NOT turned off: " + w
    return said


ROOT = "User parameter:"
# Settings this FreeCAD set for its own sake, kept over an imported file's.
_KEEP = [("BaseApp/Preferences/NotificationArea", "NonIntrusiveNotificationsEnabled")]
# Commands that would hold the window (modal dialogs) or end the session.
REFUSED = {
    "Std_DlgPreferences": "pref_get / pref_set read and write the same settings",
    "Std_DlgParameter": "pref_get / pref_set",
    "Std_DlgCustomize": "pref_set (toolbars and shortcuts are parameters too)",
    "Std_Quit": "the person closes FreeCAD",
    "Std_CloseAllWindows": "doc_close per document",
    "Std_DlgMacroExecute": "running a macro is the person's call",
    "Std_DlgMacroRecord": "the person records macros",
    "Std_AddonMgr": "the person installs add-ons",
    "Std_Open": "doc_open { path }",
    "Std_SaveAs": "doc_save { path }",
    "Std_Import": "import_file { path }",
    "Std_Export": "export",
    "Std_Print": "the person prints",
    "Std_PrintPdf": "export to PDF",
    "Std_About": "session_state",
    "Std_RecentMacros": "running a macro is the person's call",
    "Std_MacroStartDebug": "running a macro is the person's call",
    "Std_Revert": "doc_revert, after the person says to drop their changes",
    "Std_CloseActiveWindow": "doc_close",
    "Std_ExportDependencyGraph": "it asks where to save in a dialog",
    "Std_ExportGraphviz": "it asks where to save in a dialog",
    "Part_Export": "export",
    "Part_Import": "import_file { path }",
    "Mesh_Import": "import_file { path }",
    "Mesh_Export": "meshobj_export",
    "Std_RecentFiles": "doc_open { path }",
    "Std_RestartInSafeMode": "app_restart",
}
# Commands that open a file dialog to read or write a file (red team 4,
# R4-2): the path typed there is not checked. Read from FreeCAD 1.1's
# command list (docs/hardening/freecad-1.1.0-commands.txt); each names the
# tool that does the job with a checked path.
FILE_DIALOG_COMMANDS = {
    "Std_Save": "doc_save (a never-saved document opens a Save As dialog)",
    "Std_SaveAll": "doc_save_all",
    "Std_SaveCopy": "doc_save { path }",
    "Std_MergeProjects": "doc_merge",
    "Std_ProjectUtil": "doc_open { path } and doc_save { path }",
    "Std_ViewScreenShot": "view_snapshot or window_snapshot",
    "Std_ViewSaveCamera": "view (the camera of a view is a read, not a file)",
    "Std_ViewRestoreCamera": "view",
    "Std_ViewLoadImage": "the person opens images",
    "Std_TextureMapping": "the person picks a texture file",
    "Std_PrintPreview": "the person prints",
    "Std_ExportDependencyGraph": "it asks where to save in a dialog",
    "TechDraw_ExportPageSVG": "td_export",
    "TechDraw_ExportPageDXF": "td_export",
    "TechDraw_Symbol": "td_view_more",
    "TechDraw_Image": "td_view_more",
    "TechDraw_PageTemplate": "td_page { template }",
    "TechDraw_PrintAll": "the person prints",
    "Assembly_ExportASMT": "asm_export",
    "CAM_ExportTemplate": "cam_template_export",
    "CAM_Post": "cam_post",
    "CAM_ToolBitLoad": "cam_tool_add",
    "CAM_ToolBitSave": "cam_library",
    "CAM_ToolBitSaveAs": "cam_library",
    "CAM_ToolBitLibraryOpen": "cam_library",
    "Robot_ExportKukaCompact": "robot_export",
    "Robot_ExportKukaFull": "robot_export",
    "IFC_Save": "ifc_save",
    "IFC_SaveAs": "ifc_save",
    "BIM_ImagePlane": "bim_image_plane",
    "BIM_IfcExplorer": "ifc_open",
    "BIM_ProjectManager": "the person keeps project templates",
    "Part_ImportCurveNet": "part_import_curves",
    "Part_ImportStep": "import_file { path }",
    "Import_ReadBREP": "import_file { path }",
    "Import_Iges": "import_file { path }",
    "Sandbox_FileDialog": "it asks for a file in a dialog",
    "Sandbox_MeshLoad": "import_file { path }",
}
REFUSED.update({k: v + " — it asks for a file in a dialog, where the path is not checked" for k, v in FILE_DIALOG_COMMANDS.items()})
# Families of commands refused by name: macros by number run the person's
# macros; every other import or export asks for a file in a dialog.
REFUSED_LIKE = re.compile(r"^(Std_Dlg|Std_Macro_\d|Std_MacroStep|Std_ToggleBreakpoint|.*_(Import|Export)$|.*_(Import|Export|Save|Open|Load)[A-Z].*$)")


def refused(name):
    """Why a command is not run from here, or None."""
    if name in REFUSED:
        return REFUSED[name]
    if name and REFUSED_LIKE.match(name):
        return "it runs a macro or asks in a dialog that would hold the window — the matching tool does the job"
    return None


def named_objects(doc, names):
    """The objects named (by name or label), each once, and the names not
    found: a call over several objects does the rest and lists those."""
    objs, unknown = [], []
    for n in names if isinstance(names, list) else [names]:
        o = doc.getObject(n) if isinstance(n, str) else None
        o = o or next((x for x in doc.Objects if x.Label == n), None)
        if o is None:
            unknown.append(n)
        elif o not in objs:
            objs.append(o)
    return objs, unknown


def _gui():
    if not FreeCAD.GuiUp:
        raise ToolError("unavailable", "This FreeCAD has no window: commands and menus run only in the window (the link on). Settings (pref_*) work here too.")
    import FreeCADGui

    return FreeCADGui


def _group(path):
    path = (path or "BaseApp/Preferences").strip("/")
    if path.startswith(ROOT):
        path = path[len(ROOT):]
    return path, FreeCAD.ParamGet(ROOT + path)


def _contents(g):
    out = {}
    for row in g.GetContents() or []:
        kind, name, value = row[0], row[1], row[2]
        out[name] = {"type": kind, "value": value}
    return out


def _set(g, name, value, kind=None):
    kind = (kind or "").lower()
    if not kind:
        old = _contents(g).get(name)
        kind = (old or {}).get("type", "").lower()
    if not kind:
        kind = "boolean" if isinstance(value, bool) else "integer" if isinstance(value, int) else "float" if isinstance(value, float) else "string"
    if value is None:
        raise ToolError("invalid_input", f"{name}: a value (pref_reset takes a setting back to its default).")
    if kind in ("boolean", "bool"):
        # bool("false") is True: text is read as what it says.
        if isinstance(value, str):
            t = value.strip().lower()
            if t not in ("true", "false", "1", "0", "yes", "no", "on", "off"):
                raise ToolError("invalid_input", f"{name}: true or false, not {value!r}.")
            value = t in ("true", "1", "yes", "on")
        g.SetBool(name, bool(value))
    elif kind in ("integer", "int", "unsigned", "uint"):
        try:
            f = float(value)
        except (TypeError, ValueError):
            raise ToolError("invalid_input", f"{name}: a whole number, not {value!r}.") from None
        if f != int(f):
            raise ToolError("invalid_input", f"{name}: a whole number, not {value!r} (it would be cut to {int(f)}).")
        if kind in ("unsigned", "uint") and f < 0:
            raise ToolError("invalid_input", f"{name}: 0 or more.")
        (g.SetInt if kind in ("integer", "int") else g.SetUnsigned)(name, int(f))
    elif kind in ("float", "double"):
        g.SetFloat(name, float(value))
    else:
        g.SetString(name, str(value))
    return kind


PACK_TYPES = {"FCBool": "bool", "FCInt": "int", "FCUInt": "uint", "FCFloat": "float", "FCText": "string"}


def apply_cfg(path, skipped=None):
    """Set every value a preference pack's .cfg holds, group by group (what
    FreeCAD's own pack manager does, without its dialog). A guarded setting
    (guarded: program paths, folders, the macro and dialog groups) is not
    set: its name goes into skipped (R4-7)."""
    tree = ET.parse(path)
    n = 0

    def walk(node, prefix):
        nonlocal n
        for child in node:
            if child.tag == "FCParamGroup":
                walk(child, prefix + [child.get("Name")])
            elif child.tag in PACK_TYPES and prefix:
                g = FreeCAD.ParamGet(ROOT + "/".join(prefix))
                v = child.text if child.tag == "FCText" else child.get("Value")
                if child.tag == "FCBool":
                    v = v in ("1", "true", "True")
                if guarded("/".join(prefix), child.get("Name"), v):
                    if skipped is not None:
                        skipped.append("/".join(prefix + [str(child.get("Name"))]))
                    continue
                _set(g, child.get("Name"), v, PACK_TYPES[child.tag])
                n += 1

    root = tree.getroot()
    # The file's top groups are Root > BaseApp > …; parameters address from BaseApp.
    for top in root:
        if top.tag == "FCParamGroup" and top.get("Name") == "Root":
            walk(top, [])
        else:
            walk(root, [])
            break
    return n


def packs():
    """The preference packs this FreeCAD has: its own and every add-on's."""
    found = {}
    roots = [os.path.join(FreeCAD.getResourceDir(), "Gui", "PreferencePacks"), os.path.join(FreeCAD.getUserAppDataDir(), "SavedPreferencePacks")]
    mod = os.path.join(FreeCAD.getUserAppDataDir(), "Mod")
    if os.path.isdir(mod):
        roots += [os.path.join(mod, m) for m in os.listdir(mod)]
    roots.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    for r in roots:
        if not os.path.isdir(r):
            continue
        for d in os.listdir(r):
            cfg = os.path.join(r, d, d + ".cfg")
            if os.path.isfile(cfg):
                found.setdefault(d, cfg)
    return found


def _actions(menu, path, out, depth=0):
    for act in menu.actions():
        if act.isSeparator():
            continue
        title = re.sub(r"&(?!&)", "", act.text()).replace("&&", "&").strip()
        if not title:
            continue
        sub = act.menu()
        row = {"path": path + [title]}
        if act.objectName() and not sub:
            row["command"] = act.objectName()
        if not act.isEnabled():
            row["enabled"] = False
        if act.isCheckable():
            row["checked"] = act.isChecked()
        if sub is not None and depth < 4:
            _actions(sub, path + [title], out, depth + 1)
        else:
            out.append(row)


def _menubar():
    gui = _gui()
    return gui.getMainWindow().menuBar()


def _find_action(path):
    bar = _menubar()
    want = [re.sub(r"\.\.\.$|…$", "", p).strip().lower() for p in path]
    acts = bar.actions()
    for i, w in enumerate(want):
        hit = None
        for act in acts:
            t = re.sub(r"&(?!&)", "", act.text()).replace("&&", "&").strip()
            t = re.sub(r"\.\.\.$|…$", "", t).strip().lower()
            if t == w:
                hit = act
                break
        if hit is None:
            have = [re.sub(r"&(?!&)", "", a.text()).strip() for a in acts if not a.isSeparator() and a.text()]
            raise ToolError("not_found", f"No menu item '{path[i]}' there: " + ", ".join(have[:40]))
        if i == len(want) - 1:
            return hit
        if hit.menu() is None:
            raise ToolError("invalid_input", f"'{path[i]}' is an item, not a menu.")
        hit.menu().aboutToShow.emit()  # menus FreeCAD fills when opened (Recent files, Workbench)
        acts = hit.menu().actions()


RESTART_KEYS = {"StyleSheet", "Theme", "OverlayStyleSheet", "ToolbarIconSize", "Language", "TreeViewMode", "StyleParameters", "DPI", "Workbench"}


def _user_cfg():
    return os.path.join(FreeCAD.getUserConfigDir(), "user.cfg")


def _settings_changing(tool, path):
    """Before a settings change: an add-on keeping a settings log snapshots
    them now (the setting_changing event)."""
    from .. import hooks

    hooks.emit("setting_changing", tool, path)


def _settings_changed(tool, path, name, before, after):
    """After a settings change: whether it needs a restart, said to the
    add-ons listening (the setting_changed event)."""
    from .. import hooks

    restart = name in RESTART_KEYS or "MainWindow" in (path or "")
    gui = getattr(FreeCAD, "GuiUp", False)
    entry = {"tool": tool, "path": path, "name": name, "from": before, "to": after, "restart": restart}
    if restart and not gui:
        entry["applies"] = "at next launch"
    hooks.emit("setting_changed", path, name, before, after, tool=tool, restart=restart, applies=entry.get("applies"))
    return entry


# ---- what the data entries call (agentlink/data/tools.json) ----------------------------------------

def subgroups(g):
    """A parameter group's subgroups by name, sorted, to walk down; None
    where this FreeCAD cannot say."""
    try:
        return sorted(g.GetGroups())
    except Exception:
        return None


def stored(g, name):
    """One stored setting of a group as { type, value }; {} when it is not
    stored (FreeCAD's default applies)."""
    return _contents(g).get(name, {})


def removed(g, kind, name):
    """A stored value taken out of its group by its kind (Boolean, Integer,
    Unsigned, Float, String): FreeCAD's default applies again. Nothing for a
    setting that is not stored."""
    rem = {"Boolean": g.RemBool, "Integer": g.RemInt, "Unsigned": g.RemUnsigned, "Float": g.RemFloat, "String": g.RemString}.get(kind)
    if rem:
        rem(name)


def cmd_matches(gui, name, q):
    """Whether a command is one cmd_list's query asks for: q in its name,
    or in its menu text or tip (a command that cannot say what it is does
    not match by those)."""
    if not q or q in name.lower():
        return True
    try:
        info = gui.Command.get(name).getInfo()
    except Exception:
        return False
    return bool(info) and q in (str(info.get("menuText", "")) + str(info.get("toolTip", ""))).lower()


def cmd_row(gui, name):
    """A command as cmd_list answers it: its name, menu text (without the
    shortcut's mark), tip (no markup, 160 characters) and shortcut; the
    name alone for one that cannot say."""
    row = {"name": name}
    try:
        info = gui.Command.get(name).getInfo()
        row["menu"] = re.sub(r"&(?!&)", "", str(info.get("menuText", "")))
        tip = str(info.get("toolTip", "")).strip()
        if tip:
            row["tip"] = re.sub(r"<[^>]+>", "", tip)[:160]
        # FreeCAD 1.1's getInfo names it "shortcut" (src/Gui/CommandPyImp.cpp); "shortcutText" was read
        # here, which no FreeCAD gives, so no row ever had one.
        keys = info.get("shortcut") or info.get("shortcutText")
        if keys:
            row["shortcut"] = str(keys)
    except Exception:
        pass
    return row


def is_active(gui, name):
    """Whether a command is active now (its button not greyed): True or
    False, or None for one that cannot say (it is run). FreeCAD runs a
    command only while it is active: Gui.runCommand on an inactive one does
    nothing and says nothing, so this is read first."""
    try:
        c = gui.Command.get(name)
        return bool(c.isActive()) if c is not None else None
    except Exception:  # noqa: BLE001 - a command that cannot say: run it
        return None


def in_edit(gui):
    """What the document in front has open for editing (a sketch's view
    provider), or None: nothing, or no document in front."""
    try:
        return gui.ActiveDocument.getInEdit() if gui.ActiveDocument else None
    except Exception:  # noqa: BLE001
        return None


def selected(gui):
    """The window's selection for a refusal's words: up to six of
    Object.Face1,Edge2; none where it cannot be read."""
    try:
        return [f"{x.ObjectName}{'.' + ','.join(x.SubElementNames) if x.SubElementNames else ''}" for x in gui.Selection.getSelectionEx("*")][:6]
    except Exception:  # noqa: BLE001
        return []


def body_for(gui, name):
    """Before a Part Design command with no active body: the body of the
    selected objects made active, as a person's double-click on it does,
    and its label; None when there is nothing to do. Live 101: after a
    restart no body was active, and PartDesign_Pad opened the modal "Active
    Body Required" with the sketch of a body selected."""
    if not str(name).startswith("PartDesign_") or name == "PartDesign_Body":
        return None
    try:
        view = gui.ActiveDocument.ActiveView if gui.ActiveDocument else None
        if view is None or view.getActiveObject("pdbody") is not None:
            return None
        bodies = []
        for x in gui.Selection.getSelectionEx("*"):
            o = x.Object
            b = o if getattr(o, "TypeId", "") == "PartDesign::Body" else next(
                (p for p in (getattr(o, "InList", None) or ()) if getattr(p, "TypeId", "") == "PartDesign::Body"), None)
            if b is not None and b not in bodies:
                bodies.append(b)
        if len(bodies) != 1:
            return None
        view.setActiveObject("pdbody", bodies[0])
        return bodies[0].Label
    except Exception:  # noqa: BLE001 - FreeCAD asks the person as before
        return None


def bare(text):
    """A menu's title as the person reads it: without the & that marks its
    shortcut letter."""
    return re.sub(r"&(?!&)", "", text).strip()


def dock_panels(mw):
    """The window's dock panels (Report view, Model, an add-on's), for
    window_snapshot's part."""
    from PySide import QtGui

    QtW = getattr(__import__("PySide", fromlist=["QtWidgets"]), "QtWidgets", QtGui)
    return mw.findChildren(QtW.QDockWidget)


def grab(target):
    """A picture of the window or one of its panels, drawn by Qt itself
    (agentlink/grab.py): it works in the background, no screen recording."""
    from ..grab import grab_window

    return grab_window(target)


def shots():
    """The person's screenshots as their index lists them
    (~/AgentLink/shots/index.json), oldest first; none when there is no
    index or it does not read."""
    try:
        with open(os.path.join(os.path.expanduser("~/AgentLink"), "shots", "index.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def read_bytes(path):
    """A file's bytes (a picture for the answer)."""
    with open(path, "rb") as f:
        return f.read()


def tools(session):
    s = session

    def working():
        """The name of the document the session works in; None when it has
        none, or the one it had is gone."""
        try:
            return s.doc.Name if s.doc is not None else None
        except Exception:  # noqa: BLE001
            return None

    def bench_ready(key):
        """A workbench made ready to load unattended (echo.bench_ready):
        OpenSCAD's first start would otherwise ask Finder for the program and wait."""
        from .. import echo

        echo.bench_ready(key)

    # pref_get, pref_set, pref_reset, pref_pack, cmd_list, cmd_run, menu_list, menu_run, show, selection, window_snapshot, snapshot_latest,
    # snapshot_list and workbench are data: these are what their entries call. cmd_run's Sketcher_LeaveSketch case is in its entry.
    helpers = {
        "window": _gui, "doc": lambda: s.doc, "front": lambda: FreeCAD.ActiveDocument, "working": working,
        "group": _group, "contents": _contents, "subgroups": subgroups, "stored": stored, "set_value": _set, "removed": removed, "guarded": guarded,
        "changing": _settings_changing, "changed": _settings_changed, "packs": packs, "apply_cfg": apply_cfg,
        "refused": refused, "cmd_matches": cmd_matches, "cmd_row": cmd_row, "is_active": is_active, "body_for": body_for, "in_edit": in_edit, "selected": selected,
        "menubar": _menubar, "bare": bare, "walk": _actions, "find_action": _find_action, "bench_ready": bench_ready,
        "named_objects": named_objects, "dock_panels": dock_panels, "grab": grab, "local": lambda p: paths.local(s, p),
        "out_file": lambda name: os.path.join(s.out_dir, name), "read_bytes": read_bytes, "isfile": os.path.isfile, "shots": shots,
    }

    def app_restart(a):
        """Quit this FreeCAD and start it again (new add-on code, a theme):
        the settings written, each changed document saved first — one never
        saved is refused unless discard: true."""
        gui = _gui()
        import subprocess
        import sys

        # What is saved (unattended use, L): by default only the documents
        # this session changed, each checkpointed first. Anything else that
        # changed is copied and reopens beside its file from the copy — never
        # saved over the person's file without their say-so. save: all needs
        # the person's approval (approve_file, agentlink/approvals.py), asked
        # before anything else is done.
        rule = a.get("save", "agent")
        if rule not in ("agent", "none", "all"):
            raise ToolError("invalid_input", "save: agent (the documents this session changed; the default) | none | all (needs the person's approval: approve_file).")
        if rule == "all":
            from .. import approvals
            from ..store import is_changed

            docs = sorted((d.Label, d.FileName or "", bool(is_changed(d))) for d in FreeCAD.listDocuments().values())
            changed_docs = [x for x in docs if x[2]]
            try:
                got = approvals.ask("save-all", "restart", "Save every changed document over its file at the restart",
                                    [f"{lb}: {fn or 'never saved'}" for lb, fn, _c in changed_docs] or ["No document is changed now."],
                                    approvals.identity("save-all", changed_docs),
                                    shown={"document": ", ".join(lb for lb, _f, _c in changed_docs) or "none changed", "file": ", ".join(fn or "never saved" for _l, fn, _c in changed_docs) or "none"})
            except approvals.Refused as e:
                raise ToolError(e.code, e.message)
            if not got.get("ok"):
                return {**got, "restarting": False, "changed": False}

        target = a.get("app")
        if target:
            target = _freecad_bundle(target)
            # The other release must pass the smoke test with these add-ons
            # before the window moves onto it (unattended use, G); the
            # window stays where it is otherwise, and the new app stays on
            # disk for a look.
            from .. import keep, smoke

            here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            res = smoke.against(app=target, addon_dirs=[here])
            cur = sys.executable
            before = {"app": cur.split(".app/")[0] + ".app" if ".app/" in cur else cur, "freecad": ".".join(FreeCAD.Version()[:3])}
            keep.record_versions(before, {"app": target, "freecad": res.get("freecad")}, "smoke passed" if res.get("ok") else "smoke failed: refused")
            if not res.get("ok"):
                raise ToolError("failed", f"{os.path.basename(target)} failed the smoke test with these add-ons, so the window stays on {before['freecad']}: " + "; ".join(res.get("failures") or [])[:600] + f". It stays at {target} for a look.")

        # A step playing hides the body: show it again before anything is saved.
        try:
            from .. import panel

            if panel._panel is not None:
                panel._panel.stop()
        except Exception:
            pass
        # Extensions tidy up first (a document of their own not kept).
        from .. import ext

        ext.restarting(s)

        def changed(d):
            from ..store import is_changed

            return is_changed(d)

        s.restart_save = rule
        from .. import hooks

        # Saved copies are an add-on's: "checkpoints" (take) before a save,
        # "reopen" (keep) for the documents not saved, reopened from their
        # copies beside their files once FreeCAD is back.
        cps, reopener = hooks.service("checkpoints"), hooks.service("reopen")
        mine = set(getattr(s, "agent_docs", ()) or ())
        # Agent Link's own files (a copy reopened from a temporary folder, an
        # agent's never-saved document kept at the last restart) are saved
        # in place and reopened by path: they come back once, never as a
        # "(recovered …)" copy of a copy on every restart.
        plan = restart_plan(list(FreeCAD.listDocuments().values()), changed, rule, mine, bool(a.get("discard")))
        lost = [d.Label for d, how in plan if how == "copy"]
        if lost and reopener is None:
            raise ToolError("invalid_state", f"{', '.join(lost)}: changed and not being saved, and nothing here keeps a copy to reopen them from (that needs an add-on that keeps checkpoints). doc_save them first, save: all (with the person's approval, approve_file), or discard: true for never-saved ones. Nothing was changed.")
        saved, dropped, kept = [], [], []
        for d, how in plan:
            if how == "keep":
                d.save()
                kept.append(d.Label)
            elif how == "unsaved":
                os.makedirs(_unsaved_dir(), exist_ok=True)
                f = unsaved_path(d.Label, saved)
                d.saveAs(f)
                saved.append(f)
                kept.append(d.Label)
            elif how == "save":
                if cps is not None:
                    try:
                        cps.take(s, "before restart", auto=True, doc=d)
                    except Exception:
                        pass
                d.save()
                saved.append(d.FileName)
            elif how == "drop":
                dropped.append(d.Label)
        to_copy = [d for d, how in plan if how == "copy"]
        copied = reopener.keep(to_copy) if lost else []
        # Reopened by path: every document with a file, its own reopened
        # copies included (saved in place above when changed), but not one
        # the add-on keeps a copy of now: it reopens what it keeps.
        reopen = [d.FileName for d in FreeCAD.listDocuments().values() if d.FileName and all(d is not c for c in to_copy)]
        # Calls wait for the window (and these documents) instead of going to
        # the hidden FreeCAD meanwhile; the one in front is in front again.
        from .. import restart_mark

        restart_mark.write(reopen, active=getattr(s.doc, "FileName", None) or None)
        FreeCAD.saveParameter()
        exe = sys.executable
        bundle = exe.split(".app/")[0] + ".app" if ".app/" in exe else None
        migrated = None
        if target:
            # The settings and add-ons, this one's freshly written, carried
            # into the other release's own folders before it first opens.
            migrated = _carry_settings(target)
            bundle = target
            # A fresh time on the mark: the carrying-over took a while, and a
            # stale mark is ignored (M5's second half).
            restart_mark.write(reopen, active=getattr(s.doc, "FileName", None) or None)
        # The app and the files go to the shell as arguments, never into the
        # command's text: a path is not shell code, whatever it holds.
        # Waits for this FreeCAD to be gone (it writes its settings as it
        # quits), puts a settings snapshot in place when a settings rollback asked,
        # and opens it again in the background (open -g: never in front).
        cfg_from = a.get("_cfg_from") or ""
        cfg_to = os.path.join(FreeCAD.getUserConfigDir(), "user.cfg") if cfg_from else ""
        wait = 'pid=$1; src=$2; dst=$3; shift 3; n=0; while kill -0 "$pid" 2>/dev/null && [ $n -lt 120 ]; do sleep 0.5; n=$((n+1)); done; sleep 1; if [ -n "$src" ]; then cp -f "$src" "$dst"; fi; '
        if bundle:
            argv = ["/bin/sh", "-c", wait + 'exec open -g -a "$0" "$@"', bundle, str(os.getpid()), cfg_from, cfg_to, *reopen]
        else:
            argv = ["/bin/sh", "-c", wait + '"$0" "$@" &', exe, str(os.getpid()), cfg_from, cfg_to, *reopen]
        # Agent Link starts this FreeCAD: its Document Recovery at start (a
        # crash before) is answered by the link (unattended use, F).
        from .. import keep

        keep.mark_launch(None, "app_restart")
        subprocess.Popen(argv, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=_clean_env() if target else None)
        for d in list(FreeCAD.listDocuments().values()):
            FreeCAD.closeDocument(d.Name)
        from PySide import QtCore, QtGui

        app = QtGui.QApplication.instance() if hasattr(QtGui, "QApplication") else None
        if app is None:
            from PySide import QtWidgets

            app = QtWidgets.QApplication.instance()
        QtCore.QTimer.singleShot(300, app.quit)
        return {"restarting": True, "saved": saved, "reopens": reopen, **({"keptInPlace": kept} if kept else {}), **({"fromCopies": [c["label"] for c in copied]} if copied else {}), **({"discarded": dropped} if dropped else {}), **({"app": bundle, "settings": migrated} if target else {}), "note": "FreeCAD quits and opens again in a few seconds with these documents, its link on by itself. Each call meanwhile waits for it, up to 45 s, and never goes to the hidden FreeCAD. The agent works in its document of before."}

    def app_install(a):
        """Install another FreeCAD release beside this one (a Mac): started
        in the background, then read back with no arguments."""
        import platform
        import subprocess
        import sys

        os.makedirs(_INSTALL_DIR, exist_ok=True)
        state = os.path.join(_INSTALL_DIR, "state.json")
        cur = None
        if os.path.exists(state):
            with open(state) as f:
                cur = json.load(f)
        running = bool(cur and cur.get("state") not in ("installed", "failed") and _alive(cur.get("pid")))
        if a.get("open"):
            # Only a FreeCAD bundle in /Applications or ~/Applications (R4-12).
            app = _freecad_bundle(a["open"])
            if FreeCAD.GuiUp:
                raise ToolError("invalid_state", "This FreeCAD's window is open: app_restart { app } switches it over.")
            got = install_approval("open", None, app, FreeCAD.Version()[:3])
            if not got.get("ok"):
                return got
            said = _carry_settings(app)
            subprocess.Popen(["/usr/bin/open", "-a", app], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=_clean_env())
            return {"opening": app, "settings": said, "note": "Its window opens in a few seconds; its link comes on by itself once Agent Link is among its add-ons."}
        version = a.get("version")
        if not version:
            if cur is None:
                return {"state": "none", "running_version": ".".join(FreeCAD.Version()[:3]), "next": "app_install { version: \"1.1.3\" } (or \"latest\")"}
            out = dict(cur)
            if cur.get("state") == "installed":
                out["next"] = "app_restart { app: \"%s\" } opens it, settings and add-ons carried over" % cur.get("app")
            elif cur.get("state") not in ("failed",) and not running:
                out["state"] = "stopped"
            return out
        if running:
            raise ToolError("invalid_state", "An install is already running (" + str(cur.get("state")) + "); app_install with no arguments follows it.")
        if platform.system() != "Darwin":
            raise ToolError("unsupported", "app_install installs the macOS release; elsewhere use the system's package manager.")
        py = _bundle_python()
        if py is None:
            raise ToolError("not_found", "No python3 in this FreeCAD's bundle to run the install with.")
        if not re.fullmatch(r"latest|\d+\.\d+(\.\d+)?", str(version)):
            raise ToolError("invalid_input", f"version: \"latest\" or a release number like \"1.1.3\", not {str(version)[:40]!r}.")
        # It puts an app in place and runs it: the person approves (R4-12).
        got = install_approval("install", str(version), None, FreeCAD.Version()[:3])
        if not got.get("ok"):
            return got
        job = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "install_job.py")
        if os.path.exists(state):
            os.remove(state)
        log = open(os.path.join(_INSTALL_DIR, "install.log"), "w")
        p = subprocess.Popen([py, "-I", job, version, state], start_new_session=True, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        return {"started": True, "pid": p.pid, "version": version, "note": "Downloading FreeCAD's official disk image from its GitHub release, SHA-256 checked against the release's; the FreeCAD.app there now is kept under its version's name. app_install with no arguments follows it (a few minutes)."}

    def pref_import(a):
        """Merge another settings file (the release before this one's, by
        default) into this FreeCAD's settings; this one's kept first."""
        import shutil
        import time

        src = a.get("path")
        if not src:
            cfg = FreeCAD.getUserConfigDir().rstrip("/")
            tries = [os.path.join(os.path.dirname(cfg), "user.cfg")]
            AD = getattr(FreeCAD, "ApplicationDirectories", None)
            if AD is not None:
                try:
                    if not AD.usingCurrentVersionConfig(cfg):
                        tries = []
                except Exception:
                    pass
            src = next((t for t in tries if os.path.exists(t)), None)
            if not src:
                raise ToolError("not_found", "No earlier release's settings beside this one's (" + cfg + "): give path: a user.cfg.")
        src = os.path.expanduser(src)
        if not os.path.isfile(src):
            raise ToolError("not_found", "No settings file at " + src)
        backup = os.path.join(os.path.expanduser("~"), "AgentLink", "prefs-backup-%d.cfg" % int(time.time()))
        os.makedirs(os.path.dirname(backup), exist_ok=True)
        FreeCAD.saveParameter()
        mine = os.path.join(FreeCAD.getUserConfigDir(), "user.cfg")
        if os.path.exists(mine):
            shutil.copy2(mine, backup)
        _settings_changing("pref_import", "BaseApp/Preferences")
        keep = {}
        for path, name in _KEEP:
            g = FreeCAD.ParamGet(ROOT + path)
            if name in g.GetBools():
                keep[(path, name)] = g.GetBool(name)
        guard0 = _guarded_values()
        merged = _insert_cfg(src)
        settings = cfg_count(src)
        put_back = _guarded_restore(guard0)
        for (path, name), v in keep.items():
            FreeCAD.ParamGet(ROOT + path).SetBool(name, v)
        FreeCAD.saveParameter()
        copied = []
        if a.get("macros", True):
            new_mac = os.path.join(FreeCAD.getUserAppDataDir(), "Macro")
            old_mac = os.path.join(os.path.dirname(FreeCAD.getUserAppDataDir().rstrip("/")), "Macro")
            if os.path.isdir(old_mac) and os.path.realpath(old_mac) != os.path.realpath(new_mac):
                os.makedirs(new_mac, exist_ok=True)
                for n in os.listdir(old_mac):
                    if os.path.isfile(os.path.join(old_mac, n)) and not os.path.exists(os.path.join(new_mac, n)):
                        shutil.copy2(os.path.join(old_mac, n), os.path.join(new_mac, n))
                        copied.append(n)
        _settings_changed("pref_import", "BaseApp/Preferences", f"import {os.path.basename(src)}", None, f"{len(merged)} groups")
        return {"from": src, "groups": merged, **({"settings": settings} if settings is not None else {}), "backup": backup if os.path.exists(backup) else None, "kept": {"/".join(k): v for k, v in keep.items()}, "macros": copied, **({"guardedKept": put_back} if put_back else {}), "note": "Merged: the file's values win, this one's other settings stay — except the guarded ones (what an agent may do, extension repositories, the macro folder, program paths), which stay as they were. Some (theme, toolbars) show after app_restart. To undo, the backup is a whole settings file: a merge of it puts back the values it held but leaves keys the import added."}

    return [
        Tool("app_install", "Install another FreeCAD release next to this one on a Mac. version: \"1.1.3\", \"latest\", from FreeCAD's GitHub release; the tool checks SHA-256. The "
                            "current FreeCAD.app is kept as \"FreeCAD <version>.app\". It downloads in the background (minutes): the call answers started. A call with no arguments "
                            "reads its state (downloading … installed | failed) and the path of the app. Then app_restart { app } switches the window over. With the window closed, "
                            "open: an .app carries settings over and opens it. On systems other than macOS, the tool refuses. Ask the person before you install. "
                            "An install and open need the person's approval: the first call answers pending with the approve_code arguments. Call approve_code with them, "
                            "then call again. A release older than the running one is shown as older. open takes only a FreeCAD app in /Applications or ~/Applications.",
             obj({"version": {"type": "string"}, "open": {"type": "string"}}), app_install, changes=False),
        Tool("pref_import", "Bring settings over from another settings file. By default: the user.cfg of the release before this one (after a FreeCAD upgrade). Or path. The tool "
                            "merges them in, and the values of the file win. It first copies this FreeCAD's settings to a backup (answer: backup). The guarded settings stay as "
                            "they were. It also copies macros that the new release does not have (macros: false does not). Answer: from, groups, settings (how many values came in), backup, macros, guardedKept. Some "
                            "(theme, toolbars) show after app_restart.",
             obj({"path": {"type": "string"}, "macros": {"type": "boolean"}}), pref_import),
        Tool("app_restart", "Quit this FreeCAD window and open it again, with the same documents. Use it for new add-on code, a theme, or a setting that needs a restart. Window "
                            "only. The call answers first. Then FreeCAD quits about 0.3 s later, and is back in a few seconds with its link on automatically. Each call made during "
                            "that time waits for it, up to 45 s. Then the call fails with a clear message, and it never goes to the hidden FreeCAD. The agent "
                            "works in its document of before again. session_state tells the status. save tells what happens to documents. save agent (the default): saves the "
                            "documents that this session changed, each checkpointed first. save none: saves nothing. save all: saves every changed document. It writes over files "
                            "that the agent did not change. So it needs the person's approval. The first call answers pending with the approve_file arguments. Call "
                            "approve_file with them, then call again. In every case, nothing of the person's is lost or written "
                            "over. The tool keeps the agent's never-saved documents once in ~/AgentLink/unsaved, and opens them again from there. Any other changed document opens "
                            "again from a copy next to its file. The add-on that keeps checkpoints makes that copy. Without that add-on, the tool refuses, changes nothing, and "
                            "tells you to use doc_save on them first. discard: true drops the never-saved documents instead. A task panel or sketch left open is not carried over. "
                            "app: the path of another FreeCAD .app (one that app_install put there). It opens that release instead. It must first pass the smoke test with these "
                            "add-ons. Else the tool refuses, and the window stays as it is. The tool carries this release's settings and add-ons into its folders. Answer: "
                            "restarting true, saved (documents written), reopens (what will open again), keptInPlace, fromCopies, discarded, app and settings (with app), note. Use "
                            "it only when a restart is necessary. After it, every open task panel, the undo history and the selection are gone. For a window that no longer answers "
                            "at all, use app_force_restart, not this tool.",
             obj({"discard": {"type": "boolean"}, "app": {"type": "string"}, "save": {"type": "string", "enum": ["agent", "none", "all"]}}), app_restart),
    ] + runners.tools(GROUP, s, helpers)
