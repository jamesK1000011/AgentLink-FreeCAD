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
from ..protocol import ToolError

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

    def file_dialog_approval(d, btn):
        """None for a press that needs no approval; else {"ok": True} once
        the person approved this press (approve_file), or the pending answer
        with its arguments (agentlink/approvals.py)."""
        got = gl("file_dialog_press")(d, btn)
        if got is None:
            return None
        from .. import approvals

        title, text, button = got
        try:
            return approvals.ask("dialog", title or "a file dialog", f"Press {button} on the FreeCAD dialog \"{title}\"", [text],
                                 approvals.identity("dialog", title, text, button), shown={"document": title, "file": text, "button": button})
        except approvals.Refused as e:
            raise ToolError(e.code, e.message)

    helpers = {
        "modal": modal, "task_panel": task_panel, "press": lambda d, btn: gl("press")(d, btn), "press_task": lambda task, btn: gl("press_task")(task, btn),
        "fill": lambda d, text, item: gl("fill")(d, text, item), "back_out": lambda: gl("BACK_OUT"), "log_watchdog": lambda row: keep.log_watchdog(row),
        "crash_kept": crash_kept,
        "close_press_refusal": lambda d, btn: gl("unsafe_close_press")(d, btn, gl("calls_in_hand")()),
        "file_picker_refusal": lambda d, btn: gl("file_picker_press")(d, btn),
        "file_dialog_approval": file_dialog_approval,
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

    # ---- addon is data (agentlink/data/tools.json): what its entry calls on top of the above ----

    def catalog(fci):
        """FreeCAD's add-on catalog as the Addon Manager reads it
        (AddonCatalog over the official cache, fetched once a day)."""
        from AddonCatalog import AddonCatalog

        return AddonCatalog(_catalog(fci))

    def well_named(name):
        """Whether name can be an add-on's folder in Mod: letters, digits,
        - and _, nothing that climbs out of the folder."""
        return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,60}", str(name)))

    def addon_at(addon_class, name, url, branch):
        """The Addon Manager's Addon for name at an address the person gave:
        a folder on this computer (~ expanded) when url is one, else the git
        address as written."""
        folder = os.path.expanduser(url)
        return addon_class(name, folder if os.path.isdir(folder) else url, branch=branch)

    def uninstalled(uninst, addon_class, name):
        """The Addon Manager's uninstaller run on the add-on of that name:
        whether it took it out of Mod."""
        return uninst.AddonUninstaller(addon_class(name)).run()

    def set_aside(where, name):
        """The installed add-on moved out of Mod into
        ~/AgentLink/addons-previous before its update, so a failed install
        or smoke test can put it back; where it went."""
        kept = keep.path("addons-previous", f"{name}-{keep.stamp()}")
        os.makedirs(os.path.dirname(kept), exist_ok=True)
        shutil.move(where, kept)
        return kept

    def installer_run(inst, ad):
        """The Addon Manager's installer run on one add-on: (ok, None), or
        (False, the error's words) when it raised."""
        try:
            return inst.AddonInstaller(ad).run(), None
        except Exception as e:
            return False, str(e)

    def put_back(where, kept):
        """The rollback: what a failed install or update left in Mod taken
        out, and the version set aside before an update moved back."""
        if os.path.isdir(where):
            shutil.rmtree(where, ignore_errors=True)
        if kept:
            shutil.move(kept, where)

    # ---- the person's approval of an install, update or removal (agentlink/approvals.py) ----

    def _git_out(args, timeout=20):
        import subprocess

        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        except (OSError, subprocess.SubprocessError):
            return None
        return r.stdout.strip() if r.returncode == 0 else None

    def _package_facts(folder):
        """(version, author) from the add-on's package.xml; None for each
        that is not there."""
        try:
            with open(os.path.join(folder, "package.xml"), encoding="utf-8", errors="replace") as f:
                x = f.read(200000)
        except OSError:
            return None, None
        v = re.search(r"<version>([^<]+)</version>", x)
        who = re.findall(r"<(?:maintainer|author)\b[^>]*>([^<]+)</(?:maintainer|author)>", x)
        return (" ".join(v.group(1).split()) if v else None), (", ".join(dict.fromkeys(" ".join(w.split()) for w in who))[:120] or None)

    def _owner(url):
        m = re.search(r"[:/]([^/:]+)/[^/]+?(?:\.git)?/?$", str(url or ""))
        return m.group(1) if m else None

    def addon_approval(action, name, where, url, branch, ad):
        """The person's approval of one install, update or removal: the
        answer to give back (pending, with the approve_code arguments), or
        {"ok": True, "commit", "fingerprint"} once approved. The version is
        a commit (git, catalog) or a fingerprint of the folder's files (a
        folder, a removal): a new version needs a new approval."""
        from .. import approvals, ext

        commit = None
        if action == "remove":
            fp = approvals.folder_fingerprint(where) or approvals.identity("gone", where)
            ver, author = _package_facts(where)
            src = (keep._load(keep.path("addon-sources.json"), {}) or {}).get(name) or {}
            shown = {"source": src.get("url") or f"the Mod folder ({name})", "version": f"{ver or 'no version'}; files {fp}", "author": author or "not given"}
            title, why = f"Remove the add-on {name}", "It takes the add-on away."
        else:
            folder = os.path.expanduser(url) if url else None
            br = branch or getattr(ad, "branch", None) or ""
            if folder and os.path.isdir(folder):
                fp = approvals.folder_fingerprint(folder)
                ver, author = _package_facts(folder)
                shown = {"source": os.path.abspath(folder), "version": f"{ver or 'no version'}; files {fp}", "author": author or "not given"}
            else:
                src = url or getattr(ad, "url", None)
                git = ext._git()
                got = _git_out([git, "ls-remote", src, br or "HEAD"]) if (git and src) else None
                commit = (got or "").split()[0] if got else None
                if not commit:
                    raise ToolError("unavailable", f"The commit of {name} at {src or 'the catalog'} ({br or 'its default branch'}) could not be read (git ls-remote). "
                                                   "The approval names the exact version, so nothing was changed. Check the network and the address, then call again.")
                fp = "commit:" + commit
                ver, _a = _package_facts(where) if action == "update" else (None, None)
                shown = {"source": src, "version": f"commit {commit}" + (f" (branch {br})" if br else ""), "author": _owner(src) or "not given"}
            title, why = f"{action.capitalize()} the add-on {name}", "FreeCAD runs an add-on as code, with the full reach of this computer."
        try:
            got = approvals.ask("addon-" + action, name, title, [f"Action: {action}", f"Add-on: {name}", *(f"{k}: {v}" for k, v in shown.items()), why], fp, shown=shown)
        except approvals.Refused as e:
            raise ToolError(e.code, e.message)
        if got.get("ok"):
            return {"ok": True, "commit": commit, "fingerprint": fp}
        return got

    def version_moved(where, appr):
        """After an install from git: the words when the installed commit is
        not the approved one (a new version came between), else None. An
        install with no .git (a zip) is not checked here."""
        commit = (appr or {}).get("commit")
        if not commit or not os.path.isdir(os.path.join(where, ".git")):
            return None
        from .. import ext

        git = ext._git()
        head = _git_out([git, "-C", where, "rev-parse", "HEAD"]) if git else None
        if not head or head == commit:
            return None
        return (f"{os.path.basename(where)} came in at commit {head[:12]}, not the approved {commit[:12]}: a new version came between the approval and the install. "
                "A new version needs a new approval. It was taken out again: call addon again.")

    helpers.update({
        "manager": _am, "in_mod": _installed, "catalog": catalog, "well_named": well_named, "OURS": OURS,
        "join": os.path.join, "isdir": os.path.isdir, "expanduser": os.path.expanduser,
        "addon_at": addon_at, "uninstalled": uninstalled, "record": lambda before, after, why: keep.record_versions(before, after, why),
        "kept_file": lambda name: keep.path(name), "loaded": lambda file: keep._load(file, {}) or {}, "saved": lambda file, data: keep._save(file, data),
        "set_aside": set_aside, "installer_run": installer_run, "put_back": put_back, "smoke_here": _smoke_here,
        "addon_approval": addon_approval, "version_moved": version_moved,
    })
    return runners.tools(GROUP, s, helpers)
