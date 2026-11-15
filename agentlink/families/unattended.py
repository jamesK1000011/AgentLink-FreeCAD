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

from .. import keep
from ..protocol import Tool, ToolError
from ..tools import obj

GROUP = "unattended"
INFO = "Unattended use: answer harmless dialogs, the pinned document, the heavy-job queue, the Addon Manager."

def bad(msg):
    return ToolError("invalid_input", msg)


def tools(s):
    def dialog_answer(a):
        from .. import gui_link

        d = gui_link.modal_info() if FreeCAD.GuiUp else None
        if d is None:
            return {"dialog": None, "note": "No dialog is open in the FreeCAD window."}
        info = {k: v for k, v in d.items() if k != "widget"}
        btn = a.get("button")
        if not btn:
            return {"dialog": info}
        if not keep.harmless(d):
            raise ToolError("not_allowed", f"\"{d['title']}\" is not a plain information box ({', '.join(d['buttons'])}): which button is the person's call — ask them in chat, quoting it.")
        if btn.lower() not in [b.lower() for b in d["buttons"]]:
            raise bad(f"button: one of {', '.join(d['buttons'])}.")
        if not gui_link.press(d, btn):
            raise ToolError("failed", f"Could not press {btn}.")
        keep.log_watchdog({"event": "dialog", "title": d["title"], "pressed": btn, "by": "dialog_answer"})
        return {"pressed": btn, "dialog": info}

    def doc_switch(a):
        ref = a.get("document")
        if not ref:
            return {"document": s.doc.Name if s.doc else None, "label": s.doc.Label if s.doc else None,
                    "open": [{"name": d.Name, "label": d.Label, "file": d.FileName or None} for d in FreeCAD.listDocuments().values()]}
        want = os.path.abspath(os.path.expanduser(ref)) if (os.sep in ref or ref.lower().endswith(".fcstd")) else None
        nd = next((d for d in FreeCAD.listDocuments().values() if ref in (d.Name, d.Label) or (want and d.FileName and os.path.abspath(d.FileName) == want)), None)
        if nd is None:
            raise ToolError("not_found", f"{ref}: not open — " + (", ".join(d.Label for d in FreeCAD.listDocuments().values()) or "no documents are open") + ". doc_open opens a file.")
        if s.doc is not None and nd.Name == s.doc.Name:
            return {"document": nd.Name, "label": nd.Label, "note": "Already on it."}
        s.switch(nd)
        try:
            s.pinned_label = nd.Label
        except Exception:
            pass
        front = False
        if a.get("front") and getattr(FreeCAD, "GuiUp", False):
            import FreeCADGui

            FreeCAD.setActiveDocument(nd.Name)
            FreeCADGui.setActiveDocument(nd.Name)
            front = True
        return {"document": nd.Name, "label": nd.Label, "front": front, "bodies": [o.Label for o in s.bodies()],
                "note": "The agent works here from now on, whatever is in front of the window." + ("" if front else " front: true also brings it to the front.")}

    # ---- the Addon Manager, headless (I) ---------------------------------------------------

    # Kept by agentlink_update (pinned to what CI checked), never by the Addon Manager.
    OURS = {"AgentLink", "ScanRulerFC", "OrcaLink", "AddonManager"}

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
                raise ToolError("not_found", f"{name} is not installed (addon list).")
            ok = uninst.AddonUninstaller(Addon(name)).run()
            keep.record_versions({"addon": name}, None, "removed" if ok else "remove failed")
            if not ok:
                raise ToolError("failed", f"The Addon Manager could not remove {name}.")
            return {"removed": name, "note": "Gone from the Mod folder; app_restart (window) takes it out of the running FreeCAD."}
        if action not in ("install", "update"):
            raise bad("action: list | search { query } | install { name, url?, branch?, confirm } | update { name, confirm } | remove { name, confirm }.")
        if action == "install" and os.path.isdir(where):
            raise ToolError("invalid_state", f"{name} is installed already: action update.")
        if action == "update" and not os.path.isdir(where):
            raise ToolError("not_found", f"{name} is not installed: action install.")
        url, branch = a.get("url"), a.get("branch") or ""
        sources_file = keep.path("addon-sources.json")
        sources = keep._load(sources_file, {}) or {}
        if action == "update":
            # An update comes from where the add-on came from, never a new address.
            if url:
                raise bad("update takes no url: it comes from where the add-on was installed from. To change where it comes from, remove it and install it from the new address (each with the person's confirm).")
            url, branch = (sources.get(name) or {}).get("url"), branch or (sources.get(name) or {}).get("branch") or ""
        if url:
            if not (url.startswith(("https://", "git@")) or os.path.isdir(os.path.expanduser(url))):
                raise bad("url: an https or git address of the add-on's repository, or a folder on this computer.")
            ad = Addon(name, os.path.expanduser(url) if os.path.isdir(os.path.expanduser(url)) else url, branch=branch)
        else:
            from AddonCatalog import AddonCatalog

            cat = AddonCatalog(_catalog(fci))
            if name not in cat.get_available_addon_ids():
                raise ToolError("not_found", f"{name} is not in FreeCAD's add-on catalog: addon search, or give its url.")
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
        if action == "install":
            sources[name] = {"url": url or None, "branch": branch or None}
            keep._save(sources_file, sources)
        return {action + "ed" if action == "install" else "updated": name, "folder": where, "smoke": "passed", **({"previous": kept} if kept else {}),
                "note": "In the Mod folder and checked headless; app_restart (window) loads it there."}

    def queue_go(a):
        q = keep.queue_state()
        was = q.get("held")
        q["held"] = False
        q["notice"] = None
        keep.save_queue(q)
        m = keep.preset()
        return {"go": True, "wasHeld": bool(was), "running": [r.get("tool") for r in q.get("running") or []],
                "machine": {k: m.get(k) for k in ("heavySlots", "memoryCeilingGB", "fan")},
                "note": "Heavy jobs start again. Only on the person's go (their words in chat)."}

    st = {"type": "string"}
    return [
        Tool("queue_go", "The person's go for heavy jobs held while they worked in the window (call it only on their word in chat). Answers what is running and this Mac's preset.", obj({}), queue_go),
        Tool("addon", "FreeCAD's Addon Manager, headless (FreeCAD 1.1 and newer): list (installed in the Mod folder) | search { query } (the official catalog) | install { name, url? (git or a folder), branch?, confirm: \"install <name>\" typed by the person } | update { name, confirm: \"update <name>\" typed by the person } | remove { name, confirm: \"remove <name>\" typed by the person }. Each install or update passes a smoke test or is rolled back.",
             obj({"action": {"type": "string", "enum": ["list", "search", "install", "update", "remove"]}, "name": st, "query": st, "url": st, "branch": st, "confirm": st}), addon),
        Tool("doc_switch", "Which open document the agent works in: document (name, label or file) switches to it — the session stays on it whatever the person brings to the front of the window; front: true also brings it to the front. No document: the agent's one and those open.",
             obj({"document": st, "front": {"type": "boolean"}}), doc_switch),
        Tool("dialog_answer", "The modal dialog in the FreeCAD window, if any (title, text, buttons); button presses one — only on a plain information box (OK). Any other dialog is the person's: quote it to them in chat.",
             obj({"button": st}), dialog_answer),
    ]
