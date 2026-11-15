# SPDX-License-Identifier: LGPL-2.1-or-later
"""The tool-data format: how an add-on publishes its tools for agents.

An add-on keeps its tools in <folder>/tools.json (data/tools.schema.json here
is the format), and binds a handler to each name with
hooks.tools_from_data(folder, group, handlers). Agent Link owns this format;
the add-on's own code never imports Agent Link (only its agentlink_families
module does).

    {"dataVersion": "1.0.0", "licence": "CC-BY-4.0", "about": "...",
     "entries": {"tool_name": {"group": "...", "description": "...",
       "inputSchema": {"type": "object", "properties": {...}},
       "changes": false, "source": "...", "date": "YYYY-MM-DD",
       "heavy": false, "writes": false, "pathIsCurve": false}}}

heavy: a long job (queued, timed, given a deadline); writes: its "path" is a
file it writes, not reads; pathIsCurve: its "path" is a curve in the model;
reads: for a changing tool, the calls that only read, {"action": ["list"]}
(no undo step, nothing marked changed, not shown as a change).

A handler refuses by raising any exception with `code` (invalid_input,
not_found, invalid_state, unavailable, failed) and `message`: the agent gets
it as a refusal, never a crash.
"""
import json
import os
import re

ACCEPTS_MAJOR = 1
REQUIRED = {"group": str, "description": str, "inputSchema": dict, "changes": bool, "source": str, "date": str}
OPTIONAL = {"title": str, "heavy": bool, "writes": bool, "pathIsCurve": bool, "reads": dict}
# Agent Link's own tools only (agentlink/data/tools.json): a tool that wraps
# one FreeCAD command, run by one of agentlink/runners.py's runners. An
# add-on binds handlers instead and never needs these.
RUNNER = {"runner": str, "target": dict, "args": dict, "rules": list, "answer": dict}
CODES = {"invalid_input", "not_found", "invalid_state", "unavailable", "failed"}
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class FormatError(ValueError):
    pass


def load(folder):
    """folder/tools.json, checked against the format; its entries in order."""
    path = os.path.join(folder, "tools.json")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    problems = check(doc)
    if problems:
        raise FormatError(f"{path}: " + "; ".join(problems[:5]))
    return doc["entries"]


def check(doc):
    """What is wrong with a tools.json document, as a list ([] when fine)."""
    out = []
    v = str(doc.get("dataVersion", ""))
    if not re.match(r"^\d+\.\d+\.\d+$", v):
        out.append("dataVersion: a version like 1.0.0")
    elif int(v.split(".")[0]) != ACCEPTS_MAJOR:
        out.append(f"dataVersion {v}: this Agent Link reads format {ACCEPTS_MAJOR}.x")
    entries = doc.get("entries")
    if not isinstance(entries, dict) or not entries:
        return out + ["entries: an object of tools by name"]
    for name, e in entries.items():
        if not re.match(r"^[a-z][a-z0-9_]*$", name):
            out.append(f"{name}: names are lower_case")
        if not isinstance(e, dict):
            out.append(f"{name}: an object")
            continue
        for k, t in REQUIRED.items():
            if not isinstance(e.get(k), t):
                out.append(f"{name}.{k}: required ({t.__name__})")
        for k, t in OPTIONAL.items():
            if k in e and not isinstance(e[k], t):
                out.append(f"{name}.{k}: {t.__name__}")
        for k, t in RUNNER.items():
            if k in e and not isinstance(e[k], t):
                out.append(f"{name}.{k}: {t.__name__}")
        if "runner" in e:
            from . import runners

            out += runners.check_entry(name, e)
        elif set(e) & set(RUNNER):
            out.append(f"{name}: {sorted(set(e) & set(RUNNER))} without a runner")
        extra = set(e) - set(REQUIRED) - set(OPTIONAL) - set(RUNNER)
        if extra:
            out.append(f"{name}: unknown fields {sorted(extra)}")
        s = e.get("inputSchema")
        if isinstance(s, dict) and (s.get("type") != "object" or not isinstance(s.get("properties"), dict)):
            out.append(f"{name}.inputSchema: type object with properties")
        if isinstance(e.get("date"), str) and not _DATE.match(e["date"]):
            out.append(f"{name}.date: YYYY-MM-DD")
        if isinstance(e.get("description"), str) and len(e["description"]) < 20:
            out.append(f"{name}.description: say what it does and when to use it")
    return out


def refusing(fn):
    """fn, with an add-on's refusal (an exception carrying code and message)
    turned into Agent Link's ToolError."""
    from .protocol import ToolError

    def run(*a):
        try:
            return fn(*a)
        except ToolError:
            raise
        except Exception as e:  # noqa: BLE001
            code, msg = getattr(e, "code", None), getattr(e, "message", None)
            if code in CODES and isinstance(msg, str):
                raise ToolError(code, msg)
            raise

    return run


def build(folder, group, handlers, who="this add-on"):
    """Tools for one group, in the file's order: every tool of the group
    needs a handler and every handler a tool. Its heavy, writes and
    pathIsCurve fields go where Agent Link reads them."""
    from . import keep, paths
    from .protocol import Tool

    mine = {k: v for k, v in load(folder).items() if v["group"] == group}
    missing, extra = set(mine) - set(handlers), set(handlers) - set(mine)
    if missing or extra:
        raise FormatError(f"{who}'s {group} tools: no handler for {sorted(missing)}, no definition for {sorted(extra)}")
    keep.declare_heavy(k for k, v in mine.items() if v.get("heavy"))
    for k, v in mine.items():
        if v.get("writes"):
            paths.WRITERS.add(k)
        if v.get("pathIsCurve"):
            paths.GEOMETRIC.add(k)
    return [Tool(k, v["description"], v["inputSchema"], refusing(handlers[k]), changes=v["changes"], group=group, reads=v.get("reads"))
            for k, v in mine.items()]
