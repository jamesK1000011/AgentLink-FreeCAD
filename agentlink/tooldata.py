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
pathKeys and writeKeys: its other fields that hold a file it reads (pathKeys)
or writes (writeKeys), nested ones too ("kicadPcb", "texture.file",
"profiles.*"), checked as the top-level path fields are (agentlink/paths.py);
reads: for a changing tool, the calls that only read, {"action": ["list"]}
(no undo step, nothing marked changed, not shown as a change); activity:
what a call did in the Activity tab's words, a template whose {fields} come
from the call's arguments or answer ("Sliced {object}", agentlink/activity.py).

workbench, commands, words: how the tool is found (tool_groups { find } and
{ now: true }; agentlink/toolindex.py): FreeCAD's workbench class name it
belongs to ("MeshWorkbench"), the FreeCAD commands it does the work of
(["Mesh_Decimating"]), and a few search words its name lacks (["reduce",
"simplify"]). All optional; Agent Link keeps nothing of an add-on's tools
itself, so these travel with the add-on.

Long reads, for add-on authors: a client drops a call after about 80 s. The
supervisor answers any call with no answer after about 60 s with a job id
(job_status gives the answer later; agentlink/sup_jobs.py), for reads and
changes alike. No estimate holds a call back. A read ("changes": false)
that leaves the window alone may say "heavy": true (or be in its family
module's HEAVY): it then runs on a worker thread and is queued and timed.
The watchdog stops FreeCAD only when it is truly hung: no heartbeat and no
CPU work for a minute (supervise.stalled), never for being slow.

Agent Link's own tools (agentlink/data/tools.json) carry no handler: the
entry is the whole tool, run by agentlink/runners.py (docs/data-tools.md
has what each construct is for, with an example of each). An add-on binds
handlers and needs none of this.

  runner   make | apply | command | read: a wrapper of one FreeCAD command,
           with target (what it runs), args (each argument's default,
           conversion, helper, property or later step), rules (its checks,
           each with its refusal word for word) and answer.
           steps: a tool that is more than one command, with steps and
           answer:

    "steps": [
      {"let": {"length": "=pos(a, 'length', 4500)", "steps": "=int(a.get('steps', max(3, round(height / 175))))"}},
      {"refuse": "steps: 2 or more.", "when": "=steps < 2"},
      {"make": "Arch.makeStairs", "call": [null], "kw": {"length": "=length", "steps": "=steps"}},
      {"set": {"o.Placement": "=placement(vec(a.get('at', [0, 0, 0]), 'at'), frame(d, V(0, 0, 1).cross(d)))"}},
      {"do": "=named(o, a.name or 'Stairs')"}],
    "answer": {"via": "finish", "with": ["=o", "=tool", "$fields"],
               "fields": {"riser": "=round(height / steps, 1)"},
               "then": [{"put": {"note": "…"}, "when": "=not 600 <= 2 * riser + going <= 650"}]}

  A step is one object with one action; "when": e on any step runs it only
  when e is truthy.
    let      {"name": e, …} values in order; "p, q": e unpacks
    refuse   the refusal's message, in its place in the order; with when,
             code (invalid_input when left out; runners.CODES lists them,
             not_allowed and refused among them) and first (steps that undo
             what the call already made). {"fmt": "…{field}…"} fills it.
    make     a maker by dotted name ("Arch.makeStairs"; "=expression" for
             one chosen by input) with call, kw, as ("o"), headless
    add      a document object of a TypeId, with name and as
    set      {"o.Label": e, "o.Placement.Base": e} properties in order
    do       one expression or a list, for what they do
    put      {"field": e} into the answer ("into": another dict)
    push     {"list": e} one more on a list
    each     a name (or "k, v"), in, index, steps: a loop
    then     with when and else: one branch or the other
    choose   an expression, of {"value": [steps]}, else: a branch by value
    try      steps, on (error | refusal | failure | ["ValueError", …]),
             except (steps; "error" there is what was caught); failure: any
             error but a refusal; reraise: after except, the error goes on
    answer   {"via", "with", "fields", "late", "then"}: ends the run with
             this answer. via: the family helper that finishes (recompute,
             snapshot, step); fields: the answer's own fields in order
             ("...": e spreads a dict, {"when": e, "value": e} only then);
             late: the helper reads the fields itself, after its recompute;
             then: steps after the answer is made ("out"), for what is read
             or made after it. The entry's own "answer" is the one a run
             reaches the end with.

  Expressions ("=…", agentlink/expr.py): arithmetic, comparisons, and / or
  / not, "x if c else y", lists, dicts and comprehensions, a value's
  attributes and methods, the listed functions and the family's helpers by
  name. Nothing is given to eval or exec: the text is parsed and walked by
  an evaluator that knows only these, and an entry that holds anything
  else is refused when it is loaded.

  Helpers: each family module declares a dict of named functions and hands
  it to runners.tools(group, session, helpers): its finishing code, FreeCAD's
  own makers of geometry, and the small functions that are real geometry or
  FreeCAD-API logic (a wall's side, a built roof's ridge). An entry calls
  them by name with data arguments; the entry stays the tool's definition.
  family: where two family modules share a group, the module whose helpers
  the entry calls ("bim_more").

A handler refuses by raising any exception with `code` (invalid_input,
not_found, invalid_state, unavailable, failed) and `message`: the agent gets
it as a refusal, never a crash.
"""
import json
import os
import re

ACCEPTS_MAJOR = 1
REQUIRED = {"group": str, "description": str, "inputSchema": dict, "changes": bool, "source": str, "date": str}
# A card in fields (owner, 27 Nov, decision 3) stands in for description:
# does (one line), rules, returns and hint (lists of sentences). What each
# input means is in its inputSchema property's description.
CARD_FIELDS = {"does": str, "rules": list, "returns": list, "hint": list}
OPTIONAL = {"title": str, "heavy": bool, "writes": bool, "pathIsCurve": bool, "pathKeys": list, "writeKeys": list, "reads": dict, "frontReads": dict, "kindInputs": dict, "activity": str,
            "workbench": str, "commands": list, "words": list}
# Agent Link's own tools only (agentlink/data/tools.json): a tool that wraps
# one FreeCAD command, or a list of steps, run by one of agentlink/runners.py's
# runners. An add-on binds handlers instead and never needs these.
RUNNER = {"runner": str, "target": dict, "args": dict, "rules": list, "answer": dict, "steps": list, "family": str}
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
        if "card" in e:
            out += check_card(name, e["card"])
        for k, t in REQUIRED.items():
            if k == "description" and "card" in e and "description" not in e:
                continue
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
        for k in ("commands", "words"):
            if isinstance(e.get(k), list) and not all(isinstance(x, str) and x for x in e[k]):
                out.append(f"{name}.{k}: a list of words")
        for k in ("pathKeys", "writeKeys"):
            if isinstance(e.get(k), list):
                from . import paths

                bad = [x for x in e[k] if not paths.valid_key(x)]
                if bad:
                    out.append(f"{name}.{k}: dotted field names such as \"texture.file\" or \"profiles.*\", not {bad[:3]}")
        extra = set(e) - set(REQUIRED) - set(OPTIONAL) - set(RUNNER) - {"card"}
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


def check_card(name, c):
    """What is wrong with an entry's card fields."""
    if not isinstance(c, dict):
        return [f"{name}.card: an object of {', '.join(CARD_FIELDS)}"]
    out = []
    if not isinstance(c.get("does"), str) or len(c["does"]) < 10:
        out.append(f"{name}.card.does: one line on what the tool does")
    for k, t in CARD_FIELDS.items():
        if k in c and not isinstance(c[k], t):
            out.append(f"{name}.card.{k}: {t.__name__}")
        if t is list and isinstance(c.get(k), list) and not all(isinstance(x, str) and x for x in c[k]):
            out.append(f"{name}.card.{k}: a list of sentences")
    extra = set(c) - set(CARD_FIELDS)
    if extra:
        out.append(f"{name}.card: unknown fields {sorted(extra)}")
    return out


def card_text(e):
    """All the words of an entry's card, in field order, for the search
    index and other readers of the words; the card itself is shown in
    fields, never as this text."""
    if not isinstance(e.get("card"), dict):
        return e.get("description", "")
    c = e["card"]
    return " ".join([c.get("does", "")] + list(c.get("rules", [])) + list(c.get("returns", [])) + list(c.get("hint", []))).strip()


def card_words(e):
    """Every word of an entry's card and of its inputs' meanings: what the
    one-text description held before the split (27 Nov), for readers that
    search the words (tests, scripts). Never shown as one text."""
    props = ((e.get("inputSchema") or {}).get("properties") or {})
    ins = [p.get("description", "") for p in props.values() if isinstance(p, dict) and p.get("description")]
    return " ".join([card_text(e)] + ins).strip()


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


# The names of every tool already in the server: build_server sets it to its
# own table before the families' tools are made (agentlink/tools.py).
SERVER_NAMES = None


def hub_names():
    """Every hub tool's name: the tools already in the server (code tools and
    data tools), Agent Link's data tools and its tool index (every tool it
    defines, code or data). Red team 2, R2-4: the data tools alone left out
    export_file, batch, approve_code and the rest made in code."""
    hub = set()
    try:
        from . import runners

        hub.update(runners.entries())
    except Exception:  # noqa: BLE001
        pass
    try:
        from . import toolindex

        hub.update(k for k in toolindex.load() if isinstance(k, str))
    except Exception:  # noqa: BLE001
        pass
    if SERVER_NAMES is not None:
        hub.update(SERVER_NAMES)
    return hub


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
    # An add-on's entry with the name of one of Agent Link's own tools is
    # left out by the server (an extension never hides a hub tool); what it
    # declares is left out here too, so it never turns off the hub tool's
    # path check (pathIsCurve) or moves its place in tool_find (red team,
    # 2026-11-18).
    hub = hub_names()
    mine_only = {k: v for k, v in mine.items() if k not in hub}
    keep.declare_heavy(k for k, v in mine_only.items() if v.get("heavy"))
    from . import toolindex

    for k, v in mine_only.items():
        toolindex.declare(k, v)
        if v.get("writes"):
            paths.WRITERS.add(k)
        if v.get("pathIsCurve"):
            paths.GEOMETRIC.add(k)
        if v.get("pathKeys") or v.get("writeKeys"):
            paths.declare_keys(k, v.get("pathKeys"), v.get("writeKeys"))
    return [with_card(Tool(k, card_text(v), v["inputSchema"], refusing(handlers[k]), changes=v["changes"], group=group, reads=v.get("reads"),
                           activity=v.get("activity"), front_reads=v.get("frontReads")), v)
            for k, v in mine.items()]


def with_card(t, e):
    """The tool, with its card fields when its entry has them."""
    t.fields = dict(e["card"]) if isinstance(e.get("card"), dict) else None
    return t
