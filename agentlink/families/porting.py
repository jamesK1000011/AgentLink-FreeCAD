# SPDX-License-Identifier: LGPL-2.1-or-later
# Porting: the scaffold that drafts an Agent Link port of an installed
# add-on (agentlink/porting.py), and cookbooks: an add-on's commands,
# functions and call lists as data, run by the runners that exist after the
# person's OK (agentlink/cookbook.py). The design is
# docs/design/porting-2026-11-18.md; the guide is guide_read { topic:
# "porting" }. The tools are data (agentlink/data/tools.json, group
# "porting"); what is here is what their entries call by name.
#
# Not lean and not in the static base: with no cookbook installed the base
# listing is the same as before.

import json

from .. import cookbook, porting, runners
from .. import paths
from ..protocol import ToolError

GROUP = "porting"
INFO = "Port an add-on to Agent Link: a draft port from its commands (port_scaffold), and cookbooks of its commands, functions and call lists, run after the person's OK."

WRITERS = {"cookbook_export"}
AREAS = {"port_": "Porting", "cookbook_": "Cookbooks"}
NO_ECHO = ("port_scaffold", "cookbook_list", "cookbook_show", "cookbook_import", "cookbook_export", "cookbook_approve", "cookbook_unapprove",
           "cookbook_probe")
MAX_PROBES = 50


def _refusing(fn):
    def run(*a, **k):
        try:
            return fn(*a, **k)
        except (cookbook.Refused, porting.Refused) as e:
            raise ToolError(e.code, e.message)

    return run


def _answer(r):
    """A tool's answer from server.call: the body, or its refusal raised."""
    try:
        body = json.loads(r["content"][0]["text"])
    except (KeyError, IndexError, ValueError, TypeError):
        body = {}
    if r.get("isError"):
        err = body.get("error", body) if isinstance(body, dict) else {}
        code = err.get("code") if isinstance(err, dict) else None
        msg = err.get("message") if isinstance(err, dict) else None
        raise ToolError(code if code in runners.CODES else "failed", str(msg or err)[:2000])
    return body


def tools(session):
    s = session

    def names():
        srv = getattr(s, "server", None)
        return set(getattr(srv, "tools", None) or ())

    def scaffold(folder, name=None, overwrite=False):
        if not isinstance(folder, str) or not folder.strip():
            raise ToolError("invalid_input", "folder: the add-on's folder, for example one in FreeCAD's Mod folder.")
        paths.check("port_scaffold", "folder", folder, s.out_dir, False)
        return porting.scaffold(folder, name, None, bool(overwrite), taken=names())

    def run_command(cmd, index):
        args = {"name": cmd, **({"index": index} if index else {})}
        return _answer(s.server.call({"name": "cmd_run", "arguments": args}))

    def run_bench(wb, cmd):
        """Before a command recipe: the add-on's workbench activated when the
        command is not there yet (its workbench never loaded). The cookbook's
        addon.workbench, else the one an add-on's tool data names for the
        command. Words for the answer, or None."""
        try:
            import FreeCADGui

            if cmd in FreeCADGui.listCommands():
                return None
        except Exception:  # noqa: BLE001 - headless: cmd_run says why
            return None
        if not wb:
            from .. import toolindex

            wb = toolindex.bench_for_command(cmd)
        if not wb:
            return None
        try:
            _answer(s.server.call({"name": "workbench", "arguments": {"activate": wb}}))
        except ToolError as e:
            return f"{wb} could not be activated ({e.message[:120]}); the command may be missing"
        return f"activated {wb} first: {cmd} comes with it"

    def run_python(p, args):
        return cookbook.plain(cookbook.call_python(p, args, getattr(s, "doc", None)))

    def run_script(calls):
        return _answer(s.server.call({"name": "batch", "arguments": {"calls": calls, "rollback": True}}))

    # ---- schema v2 (agentlink/cookbook2.py): the FreeCAD side is agentlink/cookbook_fc.py ----

    def _app():
        try:
            import FreeCAD

            return FreeCAD
        except ImportError:
            return None

    def _gui():
        App = _app()
        if App is None or not getattr(App, "GuiUp", False):
            return None
        import FreeCADGui

        return FreeCADGui

    def _doc():
        App = _app()
        return getattr(App, "ActiveDocument", None) if App is not None else getattr(s, "doc", None)

    def v2_state(picks):
        from .. import cookbook_fc

        App = _app()
        if App is None:
            return {"document": _doc() is not None, "selection": list(picks), "types": {}}
        return cookbook_fc.state(App, _gui(), picks)

    def v2_snapshot(doc=None):
        from .. import cookbook_fc

        return cookbook_fc.snapshot(doc if doc is not None else _doc())

    def v2_function(call, values, inputs, doc=None):
        """The add-on's own function, by import inside its package
        (cookbook.resolve_function), with checked keyword inputs only."""
        from .. import cookbook_fc

        fn = cookbook.resolve_function(call["module"], call["name"])
        d = doc if doc is not None else _doc()
        try:
            kw = cookbook_fc.kwargs(d, inputs, values)
        except cookbook_fc.PickError as e:
            raise ToolError("invalid_input", f"{e}. Nothing was run.")
        if call.get("document"):
            if d is None:
                raise ToolError("invalid_state", "The entry needs a document: doc_new or doc_open first. Nothing was run.")
            kw[call["document"]] = d
        got = fn(**kw)
        if d is not None and hasattr(d, "recompute"):
            d.recompute()
        return got

    def v2_form(form, values, wb):
        """A task panel's fields filled from data, then its accept button:
        no clicks of the person's cursor (agentlink/cookbook_fc.py)."""
        if _gui() is None:
            raise ToolError("unavailable", "A form entry needs the FreeCAD window (a task panel). Headless, call a level 1 entry. Nothing was run.")
        from .. import cookbook_fc, gui_link

        said = run_bench(wb, form["command"])
        run_command(form["command"], 0)
        info = gui_link.task_info()
        if not info:
            raise ToolError("invalid_state", f"{form['command']} opened no task panel. The add-on version may differ. Nothing more was done.")
        fields = {w: (values.get(f["input"]) if "input" in f else f["value"]) for w, f in form.get("fields", {}).items()
                  if "value" in f or f.get("input") in values}
        try:
            shown = cookbook_fc.fill(info["widget"], fields)
        except cookbook_fc.FormError as e:
            gui_link.press_task(info, "Cancel")
            raise ToolError("invalid_input", f"{e}. The task panel was closed with Cancel.")
        if not gui_link.press_task(info, form.get("accept", "OK")):
            raise ToolError("invalid_state", f"The task panel has no {form.get('accept', 'OK')} button. It is still open: dialog_answer reads it.")
        return {"filled": shown, "pressed": form.get("accept", "OK"), **({"workbench": said} if said else {})}

    def v2_runners():
        return {"state": v2_state, "snapshot": v2_snapshot, "function": v2_function, "form": v2_form, "command": run_command, "workbench": run_bench,
                "doc_name": lambda: getattr(_doc(), "Name", None)}

    def run_entry(name, entry, args):
        return cookbook.run(name, entry, args or {}, {"command": run_command, "python": run_python, "script": run_script, "workbench": run_bench,
                                                      **v2_runners()}, names())

    def probe(name, entry=None):
        """Each entry once, headless, in a hidden scratch document; the
        result kept in ~/AgentLink/cookbook-probes/<name>.json (never in the
        cookbook file, so the OK holds). Levels 2 and 4 need the window:
        a cookbook_run there records its result too."""
        from .. import cookbook2, cookbook_fc

        doc, sha, problems = cookbook.load(name, names())
        if cookbook.major(doc) != cookbook2.VERSION_MAJOR:
            raise ToolError("invalid_input", f"{name} is a format 1 cookbook. cookbook_probe reads format 2; port_scaffold drafts one.")
        if not cookbook.is_approved(name, sha):
            raise ToolError("not_allowed", f"{name} is not probed: a probe runs the add-on's code. {cookbook.next_words(name)} Nothing was run.")
        if problems:
            raise ToolError("invalid_input", f"{name} has faults: " + "; ".join(problems[:4]) + ". Nothing was run.")
        ents = doc["entries"]
        if entry is not None and entry not in ents:
            raise ToolError("not_found", f"{name} has no entry {str(entry)[:48]!r}.")
        pkg = (doc.get("addon") or {}).get("package")
        version = cookbook.installed_version(pkg) if pkg else None
        App = _app()
        rows = []
        for k in ([entry] if entry else list(ents)[:MAX_PROBES]):
            e = ents[k]
            lv = e["level"]
            if lv == 5:
                rows.append({"entry": k, "result": "skip", "why": "not supported: " + str(e.get("blocker", ""))[:120]})
                continue
            if lv == 3:
                r = cookbook.record_probe(name, k, "pass", version, "branches read; a tree runs no code")
            elif lv in (2, 4):
                r = {"result": "skip", "why": "needs the window: run it once with cookbook_run, which records the result"}
            elif App is None:
                r = {"result": "skip", "why": "no FreeCAD here"}
            else:
                r = _probe_one(name, k, e, App, version, cookbook_fc, cookbook2)
            rows.append({"entry": k, **r})
        cov = cookbook2.coverage(doc, cookbook.probes_of(name), version)
        return {"cookbook": name, "addonVersion": version, "probes": rows, "coverage": cov["bars"],
                "note": "Probes ran in a hidden scratch document, closed after. The cookbook file is not changed."}

    def _probe_one(name, k, e, App, version, cookbook_fc, cookbook2):
        with cookbook_fc.scratch(App) as d:
            vals, why = cookbook_fc.probe_values(App, d, e.get("inputs"))
            if vals is None:
                return {"result": "skip", "why": why}
            try:
                values = cookbook2.check_inputs(e.get("inputs"), vals)
                before = cookbook_fc.snapshot(d)
                got = v2_function(e["call"]["function"], values, e.get("inputs") or {}, d)
                faults = cookbook2.result_faults((e.get("result") or {}).get("check"), before, cookbook_fc.snapshot(d), got)
            except Exception as x:  # noqa: BLE001 - the add-on's fault, or a guard's refusal
                msg = getattr(x, "message", None) or f"{type(x).__name__}: {x}"
                return cookbook.record_probe(name, k, "fail", version, cookbook.clean_text(msg, 200))
            if faults:
                return cookbook.record_probe(name, k, "fail", version, "; ".join(faults))
            return cookbook.record_probe(name, k, "pass", version)

    def export(name, path):
        doc, sha = cookbook.export_doc(name, names())
        p = paths.local(s, path)
        if not str(p).endswith(".json"):
            raise ToolError("invalid_input", "path: a .json file.")
        for root in cookbook.protected():
            if cookbook.inside(p, root):
                raise ToolError("invalid_input", "path: the cookbooks folder and the OK store are Agent Link's own. Export somewhere else.")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=1, ensure_ascii=False)
            f.write("\n")
        return {"exported": name, "path": p, "entries": len(doc.get("entries", {})), "sha256": sha,
                "note": "Script files are in the file as calls. The importer's person gives the OK again."}

    def importing(path, overwrite=False):
        p = paths.local(s, path)
        return cookbook.import_file(p, bool(overwrite), names())

    # What the tools' entries (agentlink/data/tools.json, group "porting") call by name.
    helpers = {
        "scaffold": _refusing(scaffold),
        "cookbooks": _refusing(lambda: cookbook.listing(names())),
        "cookbook_of": _refusing(lambda name: cookbook.show(name, names())),
        "import_cookbook": _refusing(importing),
        "export_cookbook": _refusing(export),
        "approve_cookbook": _refusing(lambda name, sha=None: cookbook.approve(name, sha, names())),
        "unapprove_cookbook": _refusing(lambda name: cookbook.unapprove(name)),
        "run_entry": _refusing(run_entry),
        "probe_cookbook": _refusing(probe),
    }
    return runners.tools(GROUP, s, helpers)
