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
NO_ECHO = ("port_scaffold", "cookbook_list", "cookbook_show", "cookbook_import", "cookbook_export", "cookbook_approve", "cookbook_unapprove")


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

    def run_python(p, args):
        return cookbook.plain(cookbook.call_python(p, args, getattr(s, "doc", None)))

    def run_script(calls):
        return _answer(s.server.call({"name": "batch", "arguments": {"calls": calls, "rollback": True}}))

    def run_entry(name, entry, args):
        return cookbook.run(name, entry, args or {}, {"command": run_command, "python": run_python, "script": run_script}, names())

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
    }
    return runners.tools(GROUP, s, helpers)
