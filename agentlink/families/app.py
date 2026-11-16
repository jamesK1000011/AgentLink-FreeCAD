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

from .. import paths
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
_GUARDED = {("Mod/AgentLink", "ExtensionRepos"), ("Macro", "MacroPath")}
_GUARDED_WORDS = ("binarypath", "executable", "exepath", "binpath")


# Whole groups no agent sets: the Addon Manager's (its catalog address and
# custom repositories decide what code an update installs).
_GUARDED_GROUPS = ("Addons", "AddonManager", "Mod/AddonManager")


def guarded(path, name):
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
    return any(w in (name or "").lower() for w in _GUARDED_WORDS)


def _guarded_values(path="BaseApp"):
    """The guarded settings as they stand, the whole tree walked."""
    out = {}
    g = FreeCAD.ParamGet(ROOT + path)
    for row in g.GetContents() or []:
        if guarded(path, row[1]):
            out[(path, row[1])] = (row[0], row[2])
    for sub in g.GetGroups() or []:
        out.update(_guarded_values(path + "/" + sub))
    return out


def _guarded_restore(before):
    """Put the guarded settings back as they were: changed ones reset,
    new ones taken out. Returns the names put back."""
    after = _guarded_values()
    back = []
    for key, (kind, val) in after.items():
        if before.get(key) == (kind, val):
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
}
# Families of commands refused by name: macros by number run the person's
# macros; every other import or export asks for a file in a dialog.
REFUSED_LIKE = re.compile(r"^(Std_Dlg|Std_Macro_\d|Std_MacroStep|Std_ToggleBreakpoint|.*_(Import|Export)$)")


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


def apply_cfg(path):
    """Set every value a preference pack's .cfg holds, group by group (what
    FreeCAD's own pack manager does, without its dialog)."""
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


def tools(session):
    s = session

    def pref_get(a):
        path, g = _group(a.get("path"))
        out = {"path": path, "values": _contents(g)}
        try:
            out["groups"] = sorted(g.GetGroups())
        except Exception:
            pass
        if a.get("name"):
            v = out["values"].get(a["name"])
            if v is None:
                raise ToolError("not_found", f"No setting '{a['name']}' in {path} (FreeCAD's default applies until one is set): " + ", ".join(sorted(out["values"])[:40]))
            return {"path": path, "name": a["name"], **v}
        return out

    def pref_set(a):
        path, g = _group(a.get("path"))
        values = dict(a.get("values") or {})
        if a.get("name"):
            values[a["name"]] = a.get("value")
        if not values:
            raise ToolError("invalid_input", "name and value, or values { name: value } (path: the group, \"BaseApp/Preferences/…\"; pref_get { path } lists its settings and types).")
        hit = [k for k in values if guarded(path, k)]
        if hit:
            raise ToolError("not_allowed", f"{', '.join(hit)}: the person's to set (Edit > Preferences, or Agent Link's panel) — they decide what an agent may do, what code FreeCAD loads and what programs it runs. Nothing was changed.")
        _settings_changing("pref_set", path)
        done = {}
        later = []
        for k, v in values.items():
            before = _contents(g).get(k, {}).get("value")
            kind = _set(g, k, v, a.get("type"))
            done[k] = {"was": before, "now": _contents(g).get(k, {}).get("value"), "type": kind}
            if _settings_changed("pref_set", path, k, before, done[k]["now"]).get("applies"):
                later.append(k)
        out = {"path": path, "set": done, "note": "Most settings take effect at once; a few (the theme, the stylesheet, toolbars) only after FreeCAD restarts. An add-on that keeps a settings history can list the changes and take them back."}
        if later:
            out["appliesAtNextLaunch"] = later
        return out

    def pref_reset(a):
        path, g = _group(a.get("path"))
        names = a.get("names") or []
        if not names:
            raise ToolError("invalid_input", "names: the settings to take back to FreeCAD's defaults (path: their group; pref_get { path } lists what is stored).")
        hit = [k for k in names if guarded(path, k)]
        if hit:
            raise ToolError("not_allowed", f"{', '.join(hit)}: the person's to reset (Edit > Preferences, or Agent Link's panel). Nothing was changed.")
        _settings_changing("pref_reset", path)
        have = _contents(g)
        absent = [k for k in names if k not in have]
        for k in names:
            kind = _contents(g).get(k, {}).get("type", "")
            before = _contents(g).get(k, {}).get("value")
            {"Boolean": g.RemBool, "Integer": g.RemInt, "Unsigned": g.RemUnsigned, "Float": g.RemFloat, "String": g.RemString}.get(kind, lambda _n: None)(k)
            _settings_changed("pref_reset", path, k, before, None)
        out = {"path": path, "reset": [k for k in names if k not in absent]}
        if absent:
            out["notSet"] = absent
            out["note"] = "notSet: not stored in this group, so already at FreeCAD's default (or the name or path is wrong: pref_get { path } lists what is stored)."
        return out

    def pref_pack(a):
        have = packs()
        name = a.get("apply")
        if not name:
            return {"packs": sorted(have), "next": "pref_pack { apply: name } sets its values; restart FreeCAD for the theme and stylesheet."}
        if name not in have:
            raise ToolError("not_found", f"apply: no preference pack '{name}' — the packs: " + (", ".join(sorted(have)) or "none") + ".")
        _settings_changing("pref_pack", "BaseApp/Preferences")
        n = apply_cfg(have[name])
        _settings_changed("pref_pack", "BaseApp/Preferences", f"pack {name}", None, f"{n} values")
        return {"applied": name, "values": n, "note": "Restart FreeCAD for the stylesheet and theme to take hold; navigation and colours change now."}

    def cmd_list(a):
        gui = _gui()
        q = str(a.get("query", "")).lower()
        rows = []
        for name in sorted(gui.listCommands()):
            if q and q not in name.lower():
                info = None
                try:
                    info = gui.Command.get(name).getInfo()
                except Exception:
                    pass
                if not info or q not in (str(info.get("menuText", "")) + str(info.get("toolTip", ""))).lower():
                    continue
            row = {"name": name}
            try:
                info = gui.Command.get(name).getInfo()
                row["menu"] = re.sub(r"&(?!&)", "", str(info.get("menuText", "")))
                tip = str(info.get("toolTip", "")).strip()
                if tip:
                    row["tip"] = re.sub(r"<[^>]+>", "", tip)[:160]
                if info.get("shortcutText"):
                    row["shortcut"] = info["shortcutText"]
            except Exception:
                pass
            if refused(name):
                row["refused"] = refused(name)
            rows.append(row)
            if len(rows) >= int(a.get("limit", 80)):
                break
        return {"commands": rows, "count": len(rows), "workbench": gui.activeWorkbench().name()}

    def cmd_run(a):
        gui = _gui()
        name = a.get("name", "")
        if refused(name):
            raise ToolError("refused", f"{name} is not run from here: {refused(name)}.")
        if name not in gui.listCommands():
            near = [n for n in gui.listCommands() if name and name.lower() in n.lower()][:8]
            raise ToolError("not_found", f"No command '{name}' in this FreeCAD" + (f" — did you mean {', '.join(near)}?" if near else "") + " cmd_list { query } finds them; a workbench's commands exist only once it has been activated (workbench { activate }).")
        # FreeCAD runs a command only while it is active (its button not
        # greyed): Gui.runCommand on an inactive one does nothing and says
        # nothing, so that is read first and said.
        active = None
        try:
            c = gui.Command.get(name)
            active = bool(c.isActive()) if c is not None else None
        except Exception:  # noqa: BLE001 - a command that cannot say: run it
            active = None
        if active is False:
            sel = []
            try:
                sel = [f"{x.ObjectName}{'.' + ','.join(x.SubElementNames) if x.SubElementNames else ''}" for x in gui.Selection.getSelectionEx("*")][:6]
            except Exception:  # noqa: BLE001
                pass
            raise ToolError("invalid_state", f"{name} is not active just now (its button is greyed out), so FreeCAD would do nothing: it needs another selection ({', '.join(sel) if sel else 'nothing is selected'}: selection {{ objects }}), an open document or view, another workbench ({gui.activeWorkbench().name()} is active: workbench {{ activate }}), or no task panel open. Nothing was run.")
        front = FreeCAD.ActiveDocument.Name if FreeCAD.ActiveDocument else None
        before = len(FreeCAD.ActiveDocument.Objects) if FreeCAD.ActiveDocument else 0
        gui.runCommand(name, int(a.get("index", 0)))
        FreeCAD.ActiveDocument and FreeCAD.ActiveDocument.recompute()
        gui.updateGui()
        out = {"ran": name, "wasActive": active, "workbench": gui.activeWorkbench().name(), "document": FreeCAD.ActiveDocument.Name if FreeCAD.ActiveDocument else None}
        if FreeCAD.ActiveDocument is not None and FreeCAD.ActiveDocument.Name == front:
            out["objectsAdded"] = len(FreeCAD.ActiveDocument.Objects) - before
        try:
            if s.doc is not None and out["document"] and out["document"] != s.doc.Name:
                out["note"] = f"The command ran on the document in front ({out['document']}), not the one the session works in ({s.doc.Name}): doc_switch {{ document, front: true }} brings that one to the front first."
        except Exception:  # noqa: BLE001
            pass
        return out

    def menu_list(a):
        bar = _menubar()
        out = []
        top = a.get("menu")
        for act in bar.actions():
            title = re.sub(r"&(?!&)", "", act.text()).strip()
            if not title or act.menu() is None:
                continue
            if top and title.lower() != str(top).lower():
                continue
            act.menu().aboutToShow.emit()
            _actions(act.menu(), [title], out)
        if top and not out:
            have = [re.sub(r"&(?!&)", "", x.text()).strip() for x in bar.actions() if x.menu() is not None and x.text()]
            raise ToolError("not_found", f"No menu '{top}' in the {_gui().activeWorkbench().name()} workbench's menu bar: {', '.join(have)}.")
        return {"items": out if top else out[: int(a.get("limit", 400))], "count": len(out)}

    def menu_run(a):
        path = a.get("path") or []
        if not path:
            raise ToolError("invalid_input", "path: the menu's titles, e.g. [\"View\", \"Standard views\", \"Fit all\"].")
        act = _find_action(path)
        name = act.objectName()
        if refused(name):
            raise ToolError("refused", f"'{' > '.join(path)}' ({name}) is not run from here: {refused(name)}.")
        if act.menu() is not None:
            raise ToolError("invalid_input", f"'{' > '.join(path)}' is a menu, not an item: menu_list {{ menu: \"{path[0]}\" }} shows its items.")
        if not act.isEnabled():
            raise ToolError("invalid_state", f"'{' > '.join(path)}' is greyed out just now, so pressing it would do nothing: it needs a selection (selection {{ objects }}), an open document, or its task panel closed first. Nothing was pressed.")
        act.trigger()
        _gui().updateGui()
        return {"pressed": path, "command": name or None, "checked": act.isChecked() if act.isCheckable() else None}

    def workbench(a):
        gui = _gui()
        if a.get("activate"):
            want = str(a["activate"]).lower().replace(" ", "")
            names = gui.listWorkbenches()
            hit = next((k for k, w in names.items() if k.lower() == want or k.lower() == want + "workbench" or getattr(w, "MenuText", "").lower().replace(" ", "") == want), None)
            if hit is None:
                raise ToolError("not_found", f"activate: no workbench {a['activate']!r} — the workbenches: " + ", ".join(sorted(getattr(w, "MenuText", k) for k, w in names.items())) + ".")
            was = gui.activeWorkbench().name()
            from .. import echo

            echo.bench_ready(hit)  # OpenSCAD's first start would otherwise ask Finder for the program and wait
            ok = gui.activateWorkbench(hit)
            if ok is False or gui.activeWorkbench().name() != hit:
                raise ToolError("failed", f"FreeCAD did not switch to {hit} (still {gui.activeWorkbench().name()}): the workbench failed to load — report_read {{ problems: true }} shows its error.")
            wbs = gui.listWorkbenches()
            return {"active": hit, "was": was, "workbenches": sorted(getattr(w, "MenuText", k) for k, w in wbs.items())}
        wbs = gui.listWorkbenches()
        return {"active": gui.activeWorkbench().name(), "workbenches": sorted(getattr(w, "MenuText", k) for k, w in wbs.items())}

    def show(a):
        """Show or hide objects in the window, as the eye in the tree does.
        A PartDesign body shows its tip (its finished part), not its history."""
        _gui()
        doc = s.doc
        names = a.get("objects")
        if names in (None, "all"):
            objs, unknown = [o for o in doc.Objects if o.TypeId in ("PartDesign::Body",) or (hasattr(o, "Shape") and not o.InList and o.TypeId not in ("App::Origin", "App::Line", "App::Plane"))], []
        else:
            objs, unknown = named_objects(doc, names)
            if unknown and not objs:
                raise ToolError("not_found", f"No object {', '.join(repr(str(n)) for n in unknown)} in {doc.Label}.")
        on = bool(a.get("visible", True))
        done = []
        for o in objs:
            if not getattr(o, "ViewObject", None):
                continue
            o.ViewObject.Visibility = on
            if on and o.TypeId == "PartDesign::Body" and o.Tip is not None:
                o.Tip.ViewObject.Visibility = True
            done.append(o.Label)
        import FreeCADGui

        FreeCADGui.updateGui()
        out = {"visible" if on else "hidden": done}
        if unknown:
            out["unknown"] = [str(n) for n in unknown]
            out["note"] = "Not found, so left out; the rest done."
        return out

    def selection(a):
        import FreeCADGui

        _gui()
        if not a.get("objects"):
            if a.get("clear", True):
                FreeCADGui.Selection.clearSelection()
                return {"selected": [], "cleared": True}
            # clear: false and no objects: read what is selected, sub-elements too.
            rows = [{"object": x.Object.Label, **({"elements": list(x.SubElementNames)} if x.SubElementNames else {})} for x in FreeCADGui.Selection.getSelectionEx(s.doc.Name)]
            return {"selected": [r["object"] for r in rows], "detail": rows, "document": s.doc.Name}
        names = a.get("objects")
        if not (isinstance(names, list) and all(isinstance(n, str) and n for n in names)):
            raise ToolError("invalid_input", "objects: a list of names or labels (whole objects; none clears the selection).")
        # Found first, so a wrong name leaves the selection as it was.
        objs = []
        for n in names:
            o = s.doc.getObject(n) or next((x for x in s.doc.Objects if x.Label == n), None)
            if o is None:
                raise ToolError("not_found", f"objects: no object '{n}' in {s.doc.Label} — object_list names them. The selection was left as it was.")
            objs.append(o)
        FreeCADGui.Selection.clearSelection()
        for o in objs:
            FreeCADGui.Selection.addSelection(o)
        # Read from the session's document by name: with no name FreeCAD
        # answers for the document in front, which may be another.
        got = [x.Object.Label for x in FreeCADGui.Selection.getSelectionEx(s.doc.Name)]
        out = {"selected": got, "document": s.doc.Name}
        if len(got) != len(set(o.Name for o in objs)):
            out["note"] = "Not every object took the selection (one with no view in the window cannot be selected)."
        return out

    def window_snapshot(a):
        """The whole FreeCAD window as the person sees it — toolbars, tree,
        panels, the 3D view — drawn by Qt itself, so it works in the
        background with no screen-recording permission. part: one dock
        panel by its title (e.g. "Report view", "Agent Link")."""
        gui = _gui()
        mw = gui.getMainWindow()
        target = mw
        if a.get("part"):
            want = str(a["part"]).lower()
            from PySide import QtGui

            QtW = getattr(__import__("PySide", fromlist=["QtWidgets"]), "QtWidgets", QtGui)
            docks = mw.findChildren(QtW.QDockWidget)
            target = next((d for d in docks if d.windowTitle().lower() == want or d.objectName().lower() == want), None)
            if target is None:
                raise ToolError("not_found", f"part: no panel titled {a['part']!r} — the panels: " + ", ".join(sorted(d.windowTitle() for d in docks if d.windowTitle())) + ".")
        from ..grab import grab_window

        pix = grab_window(target)
        out = paths.local(s, a.get("path") or os.path.join(s.out_dir, "window.png"))
        if not pix.save(out, "PNG"):
            raise ToolError("failed", f"Could not write {out}")
        res = {"path": out, "width": pix.width(), "height": pix.height()}
        if a.get("inline", True):
            with open(out, "rb") as f:
                res["_png"] = f.read()
        return res

    def _shots():
        try:
            with open(os.path.join(os.path.expanduser("~/AgentLink"), "shots", "index.json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return []

    def snapshot_latest(a):
        rows = _shots()
        if not rows:
            raise ToolError("not_found", "No screenshots yet: the person takes one with the camera button (Agent Link toolbar) or Alt+Shift+S.")
        k = int(a.get("index", 1))
        if not 1 <= k <= len(rows):
            raise ToolError("invalid_input", f"index: 1 to {len(rows)}.")
        r = dict(rows[-k])
        path = r["original"] if a.get("original") else r["path"]
        r.pop("marks", None)
        if os.path.isfile(path):
            with open(path, "rb") as f:
                r["_png"] = f.read()
        if not r.get("done"):
            r["note"] = (r.get("note") or "") + " (the person is still marking it up)"
        return r

    def snapshot_list(a):
        return {"shots": [{k: v for k, v in r.items() if k != "marks"} for r in reversed(_shots())]}

    def app_restart(a):
        """Quit this FreeCAD and start it again (new add-on code, a theme):
        the settings written, each changed document saved first — one never
        saved is refused unless discard: true."""
        gui = _gui()
        import subprocess
        import sys

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

        # What is saved (unattended use, L): by default only the documents
        # this session changed, each checkpointed first. Anything else that
        # changed is copied and reopens beside its file from the copy — never
        # saved over the person's file without their say-so.
        rule = a.get("save", "agent")
        if rule not in ("agent", "none", "all"):
            raise ToolError("invalid_input", "save: agent (the documents this session changed; the default) | none | all (needs confirm: \"save all\" typed by the person).")
        if rule == "all" and (a.get("confirm") or "").strip() != "save all":
            raise ToolError("not_allowed", "save: all saves documents the person may not want saved: confirm: \"save all\", typed by them. Nothing was changed.")
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
            raise ToolError("invalid_state", f"{', '.join(lost)}: changed and not being saved, and nothing here keeps a copy to reopen them from (that needs an add-on that keeps checkpoints). doc_save them first, save: all (with the person's confirm), or discard: true for never-saved ones. Nothing was changed.")
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
        return {"restarting": True, "saved": saved, "reopens": reopen, **({"keptInPlace": kept} if kept else {}), **({"fromCopies": [c["label"] for c in copied]} if copied else {}), **({"discarded": dropped} if dropped else {}), **({"app": bundle, "settings": migrated} if target else {}), "note": "FreeCAD quits and opens again in a few seconds with these documents, its link on by itself; calls meanwhile wait for it (up to 90 s)."}

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
            app = os.path.expanduser(a["open"]).rstrip("/")
            if not (app.endswith(".app") and os.path.isdir(os.path.join(app, "Contents"))):
                raise ToolError("not_found", "No FreeCAD app at " + app)
            if FreeCAD.GuiUp:
                raise ToolError("invalid_state", "This FreeCAD's window is open: app_restart { app } switches it over.")
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
        return {"from": src, "groups": merged, "backup": backup if os.path.exists(backup) else None, "kept": {"/".join(k): v for k, v in keep.items()}, "macros": copied, **({"guardedKept": put_back} if put_back else {}), "note": "Merged: the file's values win, this one's other settings stay — except the guarded ones (what an agent may do, extension repositories, the macro folder, program paths), which stay as they were. Some (theme, toolbars) show after app_restart. To undo, the backup is a whole settings file: a merge of it puts back the values it held but leaves keys the import added."}

    return [
        Tool("app_install", "Install another FreeCAD release beside this one on a Mac: version (\"1.1.3\", \"latest\") from FreeCAD's GitHub release, SHA-256 checked; the current FreeCAD.app kept as \"FreeCAD <version>.app\". It downloads in the background (minutes): the call answers started, and a call with no arguments reads its state (downloading … installed | failed) and the app's path. Then app_restart { app } switches the window over; with the window closed, open: an .app carries settings over and opens it. Elsewhere than macOS it is refused. Ask the person before installing.",
             obj({"version": {"type": "string"}, "open": {"type": "string"}}), app_install, changes=False),
        Tool("pref_get", "Read FreeCAD's settings (the parameter tree Edit > Preferences writes): path a group (\"BaseApp/Preferences/View\"; BaseApp/Preferences when left out) answers values { name: { type Boolean | Integer | Unsigned | Float | String, value } } and groups (its subgroups, to walk down); name: one setting. Only settings ever changed are stored: one that is absent is at FreeCAD's default (refused as not found, with the names stored). Works headless. Changes nothing.",
             obj({"path": {"type": "string"}, "name": {"type": "string"}}), pref_get),
        Tool("pref_set", "Change FreeCAD's settings: path (the group), then name + value or values { name: value }. The type follows the stored setting's own; for one not stored yet give type (bool, int, uint, float, string) or it is taken from the value — a wrong type is stored beside the right one and FreeCAD ignores it, so check with pref_get. Reply: set { name: { was, now, type } }, appliesAtNextLaunch. Most apply at once; the theme, stylesheet, language and toolbars after app_restart. Refused for the person's own: Agent Link's ExtensionRepos, the switches add-ons guard, the Addon Manager's groups, the macro folder and program paths (…BinaryPath, …Executable).",
             obj({"path": {"type": "string"}, "name": {"type": "string"}, "value": {}, "values": {"type": "object"}, "type": {"type": "string"}}), pref_set, changes=True),
        Tool("pref_import", "Bring settings over from another settings file: by default the user.cfg of the release before this one (after a FreeCAD upgrade), or path. Merged in, the file's values winning; this FreeCAD's settings are copied to a backup first (reply: backup) and the guarded ones stay as they were; macros the new release lacks are copied too (macros: false not). Reply: from, groups, backup, macros, guardedKept. Some (theme, toolbars) show after app_restart.",
             obj({"path": {"type": "string"}, "macros": {"type": "boolean"}}), pref_import),
        Tool("pref_reset", "Take settings back to FreeCAD's defaults by removing the stored values: path (the group), names. Reply: reset, notSet (names not stored there: already at the default, or misspelt). Guarded settings are refused as in pref_set.", obj({"path": {"type": "string"}, "names": {"type": "array", "items": {"type": "string"}}}, ["names"]), pref_reset),
        Tool("pref_pack", "Preference packs (themes and their settings; FreeCAD's own, saved ones and add-ons'): with nothing, packs lists their names; apply: name sets every value the pack holds (reply: values, how many). The stylesheet and theme show after app_restart; navigation and colours at once. There is no un-apply: an add-on that keeps a settings history can take it back.", obj({"apply": {"type": "string"}}), pref_pack, changes=True),
        Tool("cmd_list", "FreeCAD's commands (every toolbar button and menu item is one): name, menu text, tip, shortcut, and refused (why cmd_run will not run it). query: part of a name or words of its menu text or tip; limit (80). Only commands of workbenches already activated in this run exist (workbench { activate } loads one). Reply: commands, count, workbench (the active one). Window only. Changes nothing.",
             obj({"query": {"type": "string"}, "limit": {"type": "integer"}}), cmd_list),
        Tool("cmd_run", "Run a FreeCAD command by name (Std_ViewFitAll, Std_ViewIsometric, PartDesign_Pad …) as pressing its button would: on the window's current selection (selection sets it) and the document in front (doc_switch { front: true }), in the active workbench. A command that is not active (greyed out) is refused, since FreeCAD would silently do nothing; commands that open a modal dialog, run macros or quit are refused with the tool for the job. Many modelling commands open a task panel and wait: dialog_answer presses its OK or Cancel. index: the item of a group command (0). Reply: ran, wasActive, workbench, document, objectsAdded — a command gives no result of its own, so read the model after (session_state). The headless tools do modelling better; this is for view and window commands. Window only.",
             obj({"name": {"type": "string"}, "index": {"type": "integer"}}, ["name"]), cmd_run, changes=True),
        Tool("menu_list", "The window's menu bar as the person sees it in the active workbench: items [{ path: [titles], command (its name for cmd_run), enabled: false when greyed, checked for toggles }]; menu: one top menu only (all of it; without it, the first limit 400 items). Menus change with the workbench. Window only. Changes nothing.",
             obj({"menu": {"type": "string"}, "limit": {"type": "integer"}}), menu_list),
        Tool("menu_run", "Press a menu item by its path of titles ([\"View\", \"Standard views\", \"Fit all\"]; as menu_list gives them, case and a trailing … aside). A greyed item is refused (it would do nothing), a submenu too, and what cmd_run refuses (modal dialogs, macros, quit). Reply: pressed, command, checked (a toggle's state after). Acts on the selection and the document in front, as cmd_run. Window only.",
             obj({"path": {"type": "array", "items": {"type": "string"}}}, ["path"]), menu_run, changes=True),
        Tool("show", "Show or hide objects in the window as the tree's eye does: objects (names or labels; left out or \"all\": every body and top-level shape), visible (true; false hides). A PartDesign body shown also shows its tip, the finished part. Reply: visible or hidden [labels], unknown (names not found; the rest still done). Hidden parts are left out of view_render and of checks that go by what is shown. Window only.",
             obj({"objects": {}, "visible": {"type": "boolean"}}), show, changes=True),
        Tool("selection", "Set the window's selection for cmd_run and menu_run to act on: objects [names or labels] replaces it with those whole objects (faces and edges are picked with gui_input clicks); no objects clears it; clear: false with no objects reads it instead (detail gives the picked faces and edges). A wrong name is refused and the selection left as it was. Reply: selected [labels], document. Window only.",
             obj({"objects": {"type": "array", "items": {"type": "string"}}, "clear": {"type": "boolean"}}), selection),
        Tool("window_snapshot", "A picture of the FreeCAD window as the person sees it (toolbars, tree, panels, 3D view), or part: one dock panel by its title (\"Report view\", \"Model\", \"Agent Link\"; a wrong title lists them). Drawn by Qt in the background: no screen recording, the window need not be in front. path: a .png (window.png in the session's folder); inline: false leaves the picture out of the reply. Reply: path, width, height. For how something looks, never as proof a step worked: read state for that. Window only.",
             obj({"part": {"type": "string"}, "path": {"type": "string"}, "inline": {"type": "boolean"}}), window_snapshot),
        Tool("snapshot_latest", "The person's newest screenshot (index 2, 3 … for older ones) as a picture with their marks (original: true without), with its note, numbered pins and their comments, workbench and time; a note says when they are still marking it up. Only the person takes them (the camera button, Alt+Shift+S): none yet is refused. Changes nothing.",
             obj({"index": {"type": "integer"}, "original": {"type": "boolean"}}), snapshot_latest),
        Tool("snapshot_list", "The person's screenshots, newest first, without the pictures: time, note, pins, saved path. snapshot_latest { index } shows one. Changes nothing.", obj({}), snapshot_list),
        Tool("app_restart", "Quit this FreeCAD window and open it again (new add-ons, a theme, settings that need a restart): settings written; save agent (default: the documents this session changed, each checkpointed first) | none | all (confirm: \"save all\" typed by the person) — the agent's never-saved documents are kept once in ~/AgentLink/unsaved, any other changed document reopens from a copy beside its file, never saved over it (discard: true drops never-saved ones); app: another FreeCAD .app (app_install's) opens that one instead, this one's settings and add-ons carried into its folders first. Window only.",
             obj({"discard": {"type": "boolean"}, "app": {"type": "string"}, "save": {"type": "string", "enum": ["agent", "none", "all"]}, "confirm": {"type": "string"}}), app_restart),
        Tool("workbench", "The window's workbenches: with nothing, active (its internal name, e.g. PartDesignWorkbench) and workbenches (their menu names); activate: a menu name or internal name (\"Part Design\", \"BIM\", \"FEM\") switches to it, loading it the first time (seconds; its commands and menus exist only from then on). Reply: active, was. Changing tools switch workbench by themselves; this is for cmd_run and menu_run. Window only.", obj({"activate": {"type": "string"}}), workbench),
    ]
