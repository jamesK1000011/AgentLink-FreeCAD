# SPDX-License-Identifier: LGPL-2.1-or-later
# Unattended use (the "no one at the computer" test): what lets work go on, or stop
# safely and say why, with no one at the Mac. Answering harmless dialogs,
# the window's pinned document, the heavy-job queue and the Addon Manager.
# The rules and the files behind them are in agentlink/keep.py; the watchdog
# is in agentlink/supervise.py. Saved copies, recovery after a crash, the
# settings log and approved macros are an add-on's (agentlink/hooks.py).
#
# The person's calls stay the person's: installing code needs their own
# words in chat (a typed confirm), never the agent's.

import json
import os
import re
import shutil
import time

import FreeCAD

from .. import keep, runners
from ..protocol import Tool, ToolError, bad
from ..tools import obj

GROUP = "unattended"
INFO = "Unattended use: the pinned document, the heavy-job queue, the Addon Manager (dialog_answer and app_force_restart are in core)."

# Used when the launcher's list is missing or unreadable (an install from
# before it wrote one): Agent Link itself and the Addon Manager, no add-on
# named here; the next launcher run writes the list.
OURS_FALLBACK = frozenset({"AgentLink", "AddonManager"})
INSTALLED_NAMES = ".installed-names"


def mod_dir():
    """FreeCAD's user Mod folder, where the launcher installs."""
    return os.path.join(FreeCAD.getUserAppDataDir(), "Mod")


def installed_names(mod=None):
    """The folder names the launcher installed, from <Mod>/AgentLink/
    .installed-names (a JSON list), plus AddonManager; None when the file
    is missing or unreadable."""
    try:
        with open(os.path.join(mod or mod_dir(), "AgentLink", INSTALLED_NAMES), encoding="utf-8") as f:
            names = json.load(f)
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(names, list):
        return None
    return {n for n in names if isinstance(n, str) and n} | {"AgentLink", "AddonManager"}


def ours(mod=None):
    try:
        got = installed_names(mod)
    except Exception:  # noqa: BLE001  (no FreeCAD paths here)
        got = None
    return set(got) if got is not None else set(OURS_FALLBACK)



def _modified(d):
    from .doc import modified_state

    from ..store import is_changed

    if not is_changed(d):
        return {}
    st = modified_state(d)
    # Which flag: FreeCAD's document touched (an object changed) or only
    # the window's mark (a view setting changed), and which objects.
    out = {k: st[k] for k in ("touched", "modified", "touchedObjects") if st.get(k)}
    try:
        names = list(d.UndoNames or [])
        if names:
            out["lastSteps"] = names[:3]
    except Exception:
        pass
    return {"modified": True, "changed": out}


def tools(s):
    # ---- dialog_answer, crash_collect, doc_switch and queue_go are data (agentlink/data/tools.json):
    # what their entries call ----

    def modal():
        """The modal dialog in front of the window (gui_link.modal_info), or
        None: none open, or no window."""
        from .. import gui_link

        return gui_link.modal_info() if FreeCAD.GuiUp else None

    def task_panel():
        """The open task panel (Combo View's Tasks) and its buttons
        (gui_link.task_info), or None."""
        from .. import gui_link

        return gui_link.task_info() if FreeCAD.GuiUp else None

    def gl(name):
        """One of gui_link's dialog functions by name (press, press_task,
        fill), loaded when a dialog is there to answer."""
        from .. import gui_link

        return getattr(gui_link, name)

    def crash_kept():
        """Crash evidence copied into ~/AgentLink/crash (crash_logs.collect):
        what was kept, or nothing."""
        from .. import crash_logs

        return crash_logs.collect()

    def _bring_front(nd):
        """The document's 3D view made the window's active tab: the GUI's own
        setActiveDocument leaves another document's tab in front (a recovered
        copy that opened last, say)."""
        import FreeCADGui

        FreeCAD.setActiveDocument(nd.Name)
        FreeCADGui.setActiveDocument(nd.Name)
        try:
            from PySide import QtGui

            QtW = getattr(__import__("PySide", fromlist=["QtWidgets"]), "QtWidgets", QtGui)
            area = FreeCADGui.getMainWindow().findChild(QtW.QMdiArea)
            want = nd.Label + " : "
            sub = next((w for w in area.subWindowList() if w.windowTitle().replace("[*]", "").startswith(want)), None)
            if sub is not None and area.activeSubWindow() is not sub:
                area.setActiveSubWindow(sub)
        except Exception:
            pass
        return True

    def doc_by(ref):
        """The open document ref names: by its name, its label or its
        .FCStd file, then by name or label in any case; None when none."""
        want = os.path.abspath(os.path.expanduser(ref)) if (os.sep in ref or ref.lower().endswith(".fcstd")) else None
        nd = next((d for d in FreeCAD.listDocuments().values() if ref in (d.Name, d.Label) or (want and d.FileName and os.path.abspath(d.FileName) == want)), None)
        if nd is None:
            nd = next((d for d in FreeCAD.listDocuments().values() if str(ref).lower() in (d.Name.lower(), d.Label.lower())), None)
        return nd

    def moved_to(nd):
        """The session moved to nd and pinned there: where it came from is
        noted (doc.went_from), so closing nd goes back to it."""
        from .doc import went_from

        went_from(s, s.doc)
        s.switch(nd)
        try:
            s.pinned_label = nd.Label
        except Exception:
            pass

    def doc_names(docs):
        """Open documents for a refusal, as doc.doc_names writes them."""
        from .doc import doc_names as names

        return names(docs)

    def lifted(q):
        """The heavy-job queue's hold lifted and its notice cleared, saved."""
        q["held"] = False
        q["notice"] = None
        keep.save_queue(q)

    helpers = {
        "modal": modal, "task_panel": task_panel, "press": lambda d, btn: gl("press")(d, btn), "press_task": lambda task, btn: gl("press_task")(task, btn),
        "fill": lambda d, text, item: gl("fill")(d, text, item), "back_out": lambda: gl("BACK_OUT"), "log_watchdog": lambda row: keep.log_watchdog(row),
        "crash_kept": crash_kept,
        "current": lambda: s.doc, "docs": lambda: list(FreeCAD.listDocuments().values()), "open_row": lambda d: {"name": d.Name, "label": d.Label, "file": d.FileName or None, **_modified(d)},
        "doc_by": doc_by, "doc_names": doc_names, "moved_to": moved_to, "gui_up": lambda: bool(getattr(FreeCAD, "GuiUp", False)), "bring_front": _bring_front,
        "bodies": lambda: s.bodies(),
        "queue_state": lambda: keep.queue_state(), "lifted": lifted, "preset": lambda: keep.preset(),
    }

    # ---- the Addon Manager, headless (I) ---------------------------------------------------

    # Kept by agentlink_update (pinned to what CI checked), never by the
    # Addon Manager: what the launcher installed (installed_names()).
    OURS = ours()

    def _am():
        """The Addon Manager's own modules (FreeCAD 1.1 and newer)."""
        import sys

        v = tuple(int(x) for x in FreeCAD.Version()[:2])
        if v < (1, 1):
            raise ToolError("unavailable", f"The Addon Manager headless needs FreeCAD 1.1 or newer; this is {'.'.join(FreeCAD.Version()[:3])}.")
        roots = []
        for fn in ("getHomePath", "getResourceDir"):
            try:
                r = getattr(FreeCAD, fn)()
                roots += [os.path.join(r, "Mod", "AddonManager"), os.path.join(r, "..", "Mod", "AddonManager"), os.path.join(r, "share", "Mod", "AddonManager")]
            except Exception:
                pass
        here = next((os.path.abspath(r) for r in roots if os.path.isfile(os.path.join(r, "Addon.py"))), None)
        if here is None:
            raise ToolError("unavailable", "This FreeCAD has no Addon Manager (Mod/AddonManager) to drive.")
        if here not in sys.path:
            sys.path.insert(0, here)
        try:
            import addonmanager_freecad_interface as fci
            import addonmanager_installer as inst
            import addonmanager_uninstaller as uninst
            from Addon import Addon
        except Exception as e:
            raise ToolError("unavailable", f"The Addon Manager's modules do not load here: {e}")
        return fci, Addon, inst, uninst

    def _installed(fci):
        d = fci.DataPaths().mod_dir
        rows = []
        try:
            names = sorted(os.listdir(d))
        except OSError:
            names = []
        import re as _re

        for n in names:
            p = os.path.join(d, n)
            if not os.path.isdir(p) or n.startswith("."):
                continue
            row = {"name": n}
            try:
                with open(os.path.join(p, "package.xml"), encoding="utf-8", errors="replace") as f:
                    x = f.read()
                m = _re.search(r"<version>([^<]+)</version>", x)
                if m:
                    row["version"] = m.group(1).strip()
                m = _re.search(r"<description>([^<]+)</description>", x)
                if m:
                    row["about"] = " ".join(m.group(1).split())[:140]
            except OSError:
                pass
            if os.path.isdir(os.path.join(p, ".git")):
                row["git"] = True
            if n in OURS:
                row["managedBy"] = "agentlink_update"
            rows.append(row)
        return d, rows

    def _catalog(fci):
        """The official catalog (FreeCAD's own cache URL), kept for a day."""
        import io
        import urllib.request
        import zipfile

        cache = keep.path("addon_catalog.json")
        try:
            if time.time() - os.path.getmtime(cache) < 86400:
                with open(cache, encoding="utf-8") as f:
                    return json.load(f)
        except (OSError, ValueError):
            pass
        try:
            url = fci.Preferences().get("addon_catalog_cache_url")
        except Exception:
            url = None
        url = url or "https://addons.freecad.org/addon_catalog_cache.zip"
        req = urllib.request.Request(url, headers={"User-Agent": "AgentLink-FreeCAD"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                name = next(n for n in z.namelist() if n.endswith("_cache.json"))
                cat = json.loads(z.read(name).decode("utf-8"))
        except Exception as e:
            raise ToolError("unavailable", f"The add-on catalog could not be fetched ({url}): {e}. An add-on with its own url (git or a folder) installs without it.")
        keep._save(cache, cat)
        return cat

    def _smoke_here():
        import sys

        from .. import smoke

        here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        exe = sys.executable
        if ".app/" in exe:
            return smoke.against(app=exe.split(".app/")[0] + ".app", addon_dirs=[here])
        return smoke.against(python=exe, lib=os.environ.get("FREECAD_LIB"), addon_dirs=[here])

    def addon(a):
        action = a.get("action", "list")
        fci, Addon, inst, uninst = _am()
        if action == "list":
            d, rows = _installed(fci)
            return {"folder": d, "installed": rows}
        if action == "search":
            from AddonCatalog import AddonCatalog

            q = str(a.get("query") or "").lower()
            cat = AddonCatalog(_catalog(fci))
            ids = cat.get_available_addon_ids()
            hits = [i for i in ids if q in i.lower()] if q else ids
            return {"found": len(hits), "addons": [{"name": i, "branches": cat.get_available_branches(i)[:4]} for i in hits[:30]],
                    "note": "addon { action: install, name, confirm: \"install <name>\" } typed by the person installs one."}
        name = a.get("name")
        if not name or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,60}", str(name)):
            raise bad("name: the add-on's name (its folder in Mod: letters, digits, - and _).")
        if name in OURS:
            raise ToolError("invalid_input", f"{name} is kept up to date by agentlink_update, not here.")
        mod = fci.DataPaths().mod_dir
        where = os.path.join(mod, name)
        if action in ("install", "remove", "update"):
            # An update is new code FreeCAD runs too: the person's word, as
            # for an install.
            want = f"{action} {name}"
            if (a.get("confirm") or "").strip() != want:
                raise ToolError("not_allowed", f"confirm: \"{want}\", word for word, typed by the person — " + ("it takes their add-on away" if action == "remove" else "an add-on is code FreeCAD runs") + ". Nothing was changed.")
        if action == "remove":
            if not os.path.isdir(where):
                raise ToolError("not_found", f"{name} is not installed: addon {{ action: \"list\" }} names what is (the folder names in Mod).")
            ok = uninst.AddonUninstaller(Addon(name)).run()
            keep.record_versions({"addon": name}, None, "removed" if ok else "remove failed")
            if not ok:
                raise ToolError("failed", f"The Addon Manager could not remove {name}.")
            return {"removed": name, "note": "Gone from the Mod folder; app_restart (window) takes it out of the running FreeCAD."}
        if action not in ("install", "update"):
            raise bad("action: list | search { query } | install { name, url?, branch?, confirm: \"install <name>\" } | update { name, confirm: \"update <name>\" } | remove { name, confirm: \"remove <name>\" } — confirm is typed by the person.")
        if action == "install" and os.path.isdir(where):
            raise ToolError("invalid_state", f"{name} is installed already: addon {{ action: \"update\", name, confirm: \"update {name}\" }} brings it up to date.")
        if action == "update" and not os.path.isdir(where):
            raise ToolError("not_found", f"{name} is not installed: addon {{ action: \"install\", name, confirm: \"install {name}\" }} (addon {{ action: \"list\" }} names what is).")
        url, branch = a.get("url"), a.get("branch") or ""
        sources_file = keep.path("addon-sources.json")
        sources = keep._load(sources_file, {}) or {}
        if action == "update":
            # An update comes from where the add-on came from, never a new address.
            # One installed by hand (copied into the Mod folder) has no
            # recorded source: install refused it as installed already and
            # update found no place to fetch it from, each pointing at the
            # other. Its first update may name where it comes from; that
            # is recorded, and later updates take no url as before.
            if url and not (sources.get(name) or {}).get("url"):
                pass
            elif url:
                raise bad("update takes no url: it comes from where the add-on was installed from. To change where it comes from, remove it and install it from the new address (each with the person's confirm).")
            else:
                url, branch = (sources.get(name) or {}).get("url"), branch or (sources.get(name) or {}).get("branch") or ""
        if url:
            if not (url.startswith(("https://", "git@")) or os.path.isdir(os.path.expanduser(url))):
                raise bad("url: an https or git address of the add-on's repository, or a folder on this computer.")
            ad = Addon(name, os.path.expanduser(url) if os.path.isdir(os.path.expanduser(url)) else url, branch=branch)
        else:
            from AddonCatalog import AddonCatalog

            cat = AddonCatalog(_catalog(fci))
            if name not in cat.get_available_addon_ids():
                raise ToolError("not_found", f"{name} is not in FreeCAD's add-on catalog (names are exact, capitals too): addon {{ action: \"search\", query }} finds it, or give its url (git or a folder)." + (" It was put in the Mod folder by hand, so no source is recorded: update { name, url, confirm } once names where it comes from." if action == "update" else ""))
            ad = cat.get_addon_from_id(name, branch or None)
        # The add-on as it is kept aside first (update), so a failed smoke
        # test puts it back (G).
        kept = None
        if action == "update":
            kept = keep.path("addons-previous", f"{name}-{keep.stamp()}")
            os.makedirs(os.path.dirname(kept), exist_ok=True)
            shutil.move(where, kept)
        try:
            ok = inst.AddonInstaller(ad).run()
        except Exception as e:
            ok, err = False, str(e)
        else:
            err = None
        if not ok or not os.path.isdir(where):
            if os.path.isdir(where):
                shutil.rmtree(where, ignore_errors=True)
            if kept:
                shutil.move(kept, where)
            keep.record_versions({"addon": name}, None, f"{action} failed")
            raise ToolError("failed", f"The Addon Manager could not {action} {name}" + (f": {err}" if err else "") + (" — the version before is back." if kept else "."))
        res = _smoke_here()
        if not res.get("ok"):
            shutil.rmtree(where, ignore_errors=True)
            if kept:
                shutil.move(kept, where)
            keep.record_versions({"addon": name}, {"addon": name}, "smoke failed: rolled back")
            raise ToolError("failed", f"{name} broke the smoke test after its {action}: " + "; ".join(res.get("failures") or [])[:500] + (". The version before is back." if kept else ". It was removed again."))
        keep.record_versions({"addon": name}, {"addon": name, "url": getattr(ad, "url", url)}, f"{action}: smoke passed")
        if action == "install" or (url and not (sources.get(name) or {}).get("url")):
            # (an update that named the source of one put in by hand: kept too)
            sources[name] = {"url": url or None, "branch": branch or None}
            keep._save(sources_file, sources)
        return {action + "ed" if action == "install" else "updated": name, "folder": where, "smoke": "passed", **({"previous": kept} if kept else {}),
                "note": "In the Mod folder and checked headless; app_restart (window) loads it there."}

    st = {"type": "string"}
    return [
        Tool("addon", "FreeCAD's Addon Manager without its dialog (FreeCAD 1.1 and newer; works headless): action list (the folders in the Mod folder, with version; managedBy marks Agent Link's own, updated by agentlink_update, not here) | search { query } (part of a name, in the official catalog, fetched once a day) | install { name, url? (https / git address or a folder; else the catalog), branch?, confirm: \"install <name>\" } | update { name, confirm: \"update <name>\" } (from where it was installed; one copied into the Mod folder by hand has no recorded source, and its first update takes url, which is then recorded) | remove { name, confirm: \"remove <name>\" }. confirm must be typed by the person, word for word: an add-on is code FreeCAD runs. Each install or update is then loaded in a separate headless FreeCAD (a smoke test, a minute or so) and rolled back when that fails. A new add-on's workbench shows in the window only after app_restart. Reply: installed / updated / removed, folder, smoke.",
             obj({"action": {"type": "string", "enum": ["list", "search", "install", "update", "remove"]}, "name": st, "query": st, "url": st, "branch": st, "confirm": st}), addon),
    ] + runners.tools(GROUP, s, helpers)
