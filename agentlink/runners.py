# SPDX-License-Identifier: LGPL-2.1-or-later
"""Agent Link's own tools as data: the four runners.

A tool that only wraps one FreeCAD command is an entry in
agentlink/data/tools.json (the tool-data format, agentlink/tooldata.py) with
a runner and what it needs, instead of a handler of its own:

  make     make one object (a maker such as Arch.makePanel, or a TypeId),
           name it, set properties from the arguments, answer
  apply    one method on a found object's data (a mesh, shape or points
           copy), the result kept
  command  one FreeCAD command by name on a selection
  read     find objects and answer chosen properties

Each family keeps its finishing code (finish, done, keep, named …) and
hands it to tools(group, session, helpers); the entries name the helpers
they use, so nothing here repeats them. Descriptions, schemas and refusal
messages are in the data word for word.

Values in an entry ("expressions"):
  "$x.Attr"        a value in the run: the arguments resolved so far by
                   name, "a" (the call's arguments), "o" (the object made or
                   found), "m" (apply's working copy), "tool", "fields"; a
                   name ending in ? is getattr(…, None); "x[].Label" maps a list
  {"fmt": "…"}     str.format over the same values ("{o.Label} copy")
  {"len": e}  {"round": [e, n]}  {"or": [e, …]} (the first truthy)
  {"if": [cond, then, else]}  {"not": e}  {"vec": [x, y, z]}
  {"set": [object, "Property", e]}  sets it (in an argument's "then")
  {"do": [object, "method", e, …]}  calls one of its methods
  {"call": "helper", "with": [e, …]}  a family helper's answer
  {"when": e, "value": e}  in an answer: the field only when e is truthy
  anything else    itself (lists and objects element by element)
"""
import importlib
import os

from .protocol import Tool, ToolError

RUNNERS = ("make", "apply", "command", "read")
DATA = os.path.join(os.path.dirname(__file__), "data")
CODES = {"invalid_input", "not_found", "invalid_state", "unavailable", "failed"}

_entries = None


def entries():
    """Agent Link's own data-defined tools: name → entry (those with a runner)."""
    global _entries
    if _entries is None:
        from . import tooldata

        path = os.path.join(DATA, "tools.json")
        _entries = {k: v for k, v in tooldata.load(DATA).items() if v.get("runner")} if os.path.isfile(path) else {}
    return _entries


# ---- expressions ---------------------------------------------------------------------------

def _path(env, p):
    parts = p.split(".")
    head = parts[0]
    if head.endswith("[]"):
        return [_attrs(x, parts[1:]) for x in env[head[:-2]]]
    if head not in env:
        raise KeyError(f"${head}: not a value in this run")
    cur = env[head]
    for i, k in enumerate(parts[1:], 1):
        if k.endswith("[]"):
            lst = _attrs(cur, [k[:-2]])
            return [_attrs(x, parts[i + 1:]) for x in lst]
        cur = _attrs(cur, [k])
    return cur


def _attrs(x, names):
    for k in names:
        if k.endswith("?"):
            x = getattr(x, k[:-1], None)
        elif isinstance(x, dict):
            x = x.get(k)
        else:
            x = getattr(x, k)
    return x


def value(e, env, helpers):
    if isinstance(e, str):
        return _path(env, e[1:]) if e.startswith("$") else e
    if isinstance(e, list):
        return [value(x, env, helpers) for x in e]
    if isinstance(e, dict):
        if len(e) == 1:
            (op, arg), = e.items()
            if op == "fmt":
                return arg.format(**env)
            if op == "len":
                return len(value(arg, env, helpers))
            if op == "round":
                return round(value(arg[0], env, helpers), arg[1])
            if op == "if":
                c, t, f = arg
                return value(t, env, helpers) if value(c, env, helpers) else value(f, env, helpers)
            if op == "set":
                o, prop, v = (value(x, env, helpers) for x in arg)
                setattr(o, prop, v)
                return v
            if op == "do":
                o, meth, *rest = arg
                return getattr(value(o, env, helpers), meth)(*[value(x, env, helpers) for x in rest])
            if op == "not":
                return not value(arg, env, helpers)
            if op == "vec":
                import FreeCAD

                return FreeCAD.Vector(*[value(x, env, helpers) for x in arg])
            if op == "or":
                v = None
                for x in arg:
                    v = value(x, env, helpers)
                    if v:
                        return v
                return v
        if "call" in e and set(e) <= {"call", "with"}:
            return helpers[e["call"]](*[value(x, env, helpers) for x in e.get("with", [])])
        return {k: value(v, env, helpers) for k, v in e.items()}
    return e


def fields(spec, env, helpers):
    """An answer's fields in their order: "...name" spreads a dict, a
    {"when", "value"} field is left out when its condition is not met."""
    out = {}
    for k, e in (spec or {}).items():
        if isinstance(e, dict) and set(e) == {"when", "value"}:
            if not value(e["when"], env, helpers):
                continue
            e = e["value"]
        v = value(e, env, helpers)
        if k.startswith("..."):
            out.update(v or {})
        else:
            out[k] = v
    return out


# ---- arguments and rules --------------------------------------------------------------------

AS = {"float": float, "int": int, "str": str, "bool": bool}


def resolve(k, spec, a, env, helpers):
    """One argument: plain (default, as), through a family helper
    (helper, with), or from a fixed choice (map)."""
    if "helper" in spec:
        args = spec.get("with", ["$value"])
        local = {**env, "value": a.get(k, spec["default"]) if "default" in spec else a.get(k), "key": k}
        return helpers[spec["helper"]](*[value(x, local, helpers) for x in args])
    v = a.get(k, spec["default"]) if "default" in spec else a.get(k)
    if "map" in spec:
        v = spec["map"].get(v) if isinstance(v, str) else None
    if spec.get("as") and (v is not None or spec["as"] == "bool"):
        v = AS[spec["as"]](v)  # bool(None) is False, as bool(a.get(k)) is
    return v


def check(r, env, helpers):
    """One rule: raises its refusal (message as written) when it fails."""
    kind = r["check"]
    if kind == "available":
        ok = value(r["of"], env, helpers) is not None
    elif kind == "given":
        ok = value(r["of"], env, helpers) is not None
    elif kind == "truthy":
        ok = bool(value(r["of"], env, helpers))
    elif kind == "nonzero":
        ok = value(r["of"], env, helpers) != 0
    elif kind == "range":
        v = value(r["of"], env, helpers)
        lo, hi = r.get("min"), r.get("max")
        ok = (lo is None or v >= lo) and (hi is None or v <= hi)
    elif kind == "count":
        n = len(value(r["of"], env, helpers))
        lo, hi = r.get("min"), r.get("max")
        ok = (lo is None or n >= lo) and (hi is None or n <= hi)
    elif kind == "derived":
        o = value(r["of"], env, helpers)
        ok = any(o.isDerivedFrom(t) for t in r["from"])
    else:
        raise ValueError(f"rule {kind}: not a check the runners make")
    if not ok:
        raise ToolError(r.get("code", "invalid_input"), r["message"].format(**env) if r.get("format") else r["message"])


def _maker(dotted):
    mod, _, fn = dotted.rpartition(".")
    try:
        return getattr(importlib.import_module(mod), fn, None)
    except ImportError:
        return None


# ---- the runners ----------------------------------------------------------------------------

def _start(name, e, a, helpers):
    """The run's values with the arguments resolved in order, each rule
    checked as soon as what it checks is there (after: an argument's name;
    "start" before any; "made" once make's object is there; the rest once
    all are resolved)."""
    env = {"a": a, "tool": name}
    rules = list(e.get("rules") or [])
    target = e.get("target")
    if isinstance(target, dict) and target.get("maker"):
        env["maker"] = _maker(target["maker"])

    def due(after):
        for r in [r for r in rules if r.get("after", "") == after]:
            check(r, env, helpers)
            rules.remove(r)

    due("start")
    for k, spec in (e.get("args") or {}).items():
        if "then" in spec or (spec.get("prop") and "helper" not in spec and "value" not in spec):
            continue  # set on the object once it is made
        env[k.lstrip("=")] = value(spec["value"], env, helpers) if "value" in spec else resolve(k, spec, a, env, helpers)
        due(k)
    return env, rules


def _finish_rules(rules, env, helpers):
    for r in [r for r in rules if r.get("after", "") in ("", "args")]:
        check(r, env, helpers)
        rules.remove(r)


def _after(e, a, env, helpers):
    """Once the object is made, in the entry's order: each argument's
    property (consecutive ones set together through the family's setprops
    when it has one, which sets what the object has; directly otherwise),
    and each "then" (naming it, as a rule)."""
    o = env["o"]
    batch = {}

    def flush():
        if batch:
            helpers["setprops"](o, dict(batch))
            batch.clear()

    for k, spec in (e.get("args") or {}).items():
        if "then" in spec:
            flush()
            value(spec["then"], env, helpers)
            continue
        if not spec.get("prop"):
            continue
        if k.lstrip("=") in env:
            v = env[k.lstrip("=")]
        else:
            v = a.get(k, spec["default"]) if "default" in spec else a.get(k)
            if spec.get("when") == "truthy" and not v:
                continue
            if "map" in spec:
                v = spec["map"].get(v) if isinstance(v, str) else None
            if spec.get("as") and v is not None:
                v = AS[spec["as"]](v)
        if spec.get("when") == "truthy" and not v:
            continue
        prop = spec["prop"]
        if spec.get("has") or "." in prop:
            # Only on an object that has it, set directly; "Placement.Base"
            # sets the part in place, as o.Placement.Base = … does.
            flush()
            head, _, rest = prop.partition(".")
            if spec.get("has") and not hasattr(o, head):
                continue
            if rest:
                setattr(getattr(o, head), rest, v)
            else:
                setattr(o, head, v)
            continue
        if "setprops" in helpers:
            if spec.get("alone"):
                flush()
            batch[spec["prop"]] = v
            if spec.get("alone"):
                flush()
        elif v is not None:
            setattr(o, spec["prop"], v)
    flush()


def _answer(e, env, helpers):
    ans = e.get("answer") or {}
    for x in ans.get("first", []):
        value(x, env, helpers)  # e.g. recompute and record the step before the fields are read
    env["fields"] = fields(ans.get("fields"), env, helpers)
    if ans.get("via"):
        return helpers[ans["via"]](*[value(x, env, helpers) for x in ans.get("with", [])])
    return env["fields"]


def run_make(name, e, a, helpers):
    env, rules = _start(name, e, a, helpers)
    _finish_rules(rules, env, helpers)
    t = e["target"]
    args = [value(x, env, helpers) for x in t.get("call", [])]
    kw = {k: value(x, env, helpers) for k, x in (t.get("kw") or {}).items()}
    if t.get("maker"):
        fn = env["maker"]
        o = helpers[t["headless"]](fn, *args, **kw) if t.get("headless") else fn(*args, **kw)
    else:
        o = helpers["doc"]().addObject(t["type"], t.get("base", t["type"].split("::")[-1]))
    env["o"] = o
    for r in [r for r in rules if r.get("after") == "made"]:
        check(r, env, helpers)  # what the maker gave back (None: it made nothing)
    _after(e, a, env, helpers)
    return _answer(e, env, helpers)


def run_apply(name, e, a, helpers):
    env, rules = _start(name, e, a, helpers)
    t = e["target"]
    o = env[t.get("on", "o")]
    env["o"] = o
    if t.get("copy"):
        env["m"] = getattr(o, t["copy"]).copy()
    _finish_rules(rules, env, helpers)
    on = env["m"] if t.get("copy") else o
    res = getattr(on, t["method"])(*[value(x, env, helpers) for x in t.get("call", [])])
    env["result"] = res
    return _answer(e, env, helpers)


def run_command(name, e, a, helpers):
    """A FreeCAD command by name on the objects given, in the window."""
    import FreeCAD

    env, rules = _start(name, e, a, helpers)
    _finish_rules(rules, env, helpers)
    t = e["target"]
    if not getattr(FreeCAD, "GuiUp", False):
        raise ToolError("unavailable", t.get("windowOnly") or f"{t['command']} works only through the FreeCAD window.")
    import FreeCADGui

    sel = value(t.get("select", []), env, helpers) or []
    FreeCADGui.Selection.clearSelection()
    for o in sel:
        FreeCADGui.Selection.addSelection(o)
    try:
        FreeCADGui.runCommand(t["command"], 0)
    finally:
        FreeCADGui.Selection.clearSelection()
    env["selected"] = sel
    return _answer(e, env, helpers)


def run_read(name, e, a, helpers):
    env, rules = _start(name, e, a, helpers)
    _finish_rules(rules, env, helpers)
    t = e["target"]
    found = value(t.get("from", "$doc.Objects"), {**env, "doc": helpers["doc"]()}, helpers)
    where = t.get("where")
    rows = []
    for o in found:
        env["o"] = o
        if where and not helpers[where](o):
            continue
        rows.append(fields(t.get("each"), env, helpers))
    env["rows"] = rows
    return _answer(e, env, helpers)


RUN = {"make": run_make, "apply": run_apply, "command": run_command, "read": run_read}


def tool(name, e, helpers):
    run = RUN[e["runner"]]
    return Tool(name, e["description"], e["inputSchema"], lambda a: run(name, e, a, helpers), changes=e["changes"], group=e["group"],
                reads=e.get("reads"), activity=e.get("activity"))


def tools(group, session, helpers, data=None):
    """The group's data-defined tools, bound to the family's helpers."""
    ents = entries() if data is None else data
    return [tool(k, v, helpers) for k, v in ents.items() if v["group"] == group and v.get("runner")]


def check_entry(name, e):
    """What is wrong with a runner entry (the parts tooldata.check leaves to it)."""
    out = []
    r = e.get("runner")
    if r not in RUNNERS:
        return [f"{name}.runner: one of {', '.join(RUNNERS)}"]
    t = e.get("target")
    if not isinstance(t, dict):
        return [f"{name}.target: an object"]
    need = {"make": ("maker", "type"), "apply": ("method",), "command": ("command",), "read": ()}[r]
    if need and not any(k in t for k in need):
        out.append(f"{name}.target: needs {' or '.join(need)}")
    for k, spec in (e.get("args") or {}).items():
        if not isinstance(spec, dict):
            out.append(f"{name}.args.{k}: an object")
    for i, rule in enumerate(e.get("rules") or []):
        if not isinstance(rule, dict) or not isinstance(rule.get("message"), str) or "check" not in rule:
            out.append(f"{name}.rules[{i}]: check and message")
        elif rule.get("code", "invalid_input") not in CODES:
            out.append(f"{name}.rules[{i}].code: one of {', '.join(sorted(CODES))}")
    ans = e.get("answer")
    if ans is not None and (not isinstance(ans, dict) or set(ans) - {"first", "via", "with", "fields"}):
        out.append(f"{name}.answer: first, via, with, fields")
    return out
