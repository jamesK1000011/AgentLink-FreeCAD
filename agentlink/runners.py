# SPDX-License-Identifier: LGPL-2.1-or-later
"""Agent Link's own tools as data: the runners.

A tool is an entry in agentlink/data/tools.json (the tool-data format,
agentlink/tooldata.py; docs/data-tools.md says what each construct is
for) with a runner and what it needs, instead of a handler of its own:

  make     make one object (a maker such as Arch.makePanel, or a TypeId),
           name it, set properties from the arguments, answer
  apply    one method on a found object's data (a mesh, shape or points
           copy), the result kept
  command  one FreeCAD command by name on a selection
  read     find objects and answer chosen properties
  steps    a list of steps run in order, each able to use the ones before
           it: for a tool that is more than one command

Each family keeps its finishing code and its named helpers (finish, done,
named …; the small functions that are real geometry or FreeCAD-API logic)
and hands them to tools(group, session, helpers); the entries name the
helpers they use, so nothing here repeats them. Descriptions, schemas and
refusal messages are in the data word for word.

Values in an entry ("expressions"):
  "=expression"    worked out by agentlink/expr.py's evaluator: arithmetic,
                   comparisons, and/or/not, "x if c else y", lists and
                   [… for x in xs], a helper or a listed function by name,
                   a value's methods. "a" is the call's arguments, and
                   a.name the argument "name" (None when left out).
  "$x.Attr"        a value in the run: the arguments resolved so far by
                   name, "a" (the call's arguments), "o" (the object made or
                   found), "m" (apply's working copy), "tool", "fields"; a
                   name ending in ? is getattr(…, None); "x[].Label" maps a list
  {"fmt": "…"}     a message filled from the run's values: "{o.Label} copy",
                   "{sill + height:g} mm", "{path!r}" (expr.fmt)
  {"len": e}  {"sum": e}  {"round": [e, n]}  {"or": [e, …]} (the first truthy)
  {"if": [cond, then, else]}  {"not": e}  {"vec": [x, y, z]}
  {"set": [object, "Property", e]}  sets it (in an argument's "then", a
                   step run once the object is made, in the entry's order;
                   "$value" there is the argument, its default when left
                   out, and "$key" its name)
  {"do": [object, "method", e, …]}  calls one of its methods
  {"call": "helper", "with": [e, …]}  a family helper's answer
  {"when": e, "value": e}  in an answer: the field only when e is truthy
  anything else    itself (lists and objects element by element)

A rule ({"check", "of", "message", "code", "after"}) may carry "when": an
expression; the rule is only checked when it is truthy (a check that
belongs to one way of calling the tool: its base given, not its points).

The steps runner's steps (each one object; "when": e on any of them runs
it only when e is truthy):
  {"let": {"name": e, …}}        values, in order ("p, q": e unpacks)
  {"refuse": message, "when": e, "code": "invalid_input", "first": [steps]}
                                 the refusal, in its place in the order;
                                 first: what to undo before it
  {"make": "Arch.makeStairs", "call": [e, …], "kw": {…}, "as": "o",
   "headless": true}             a maker called (through the family's
                                 headless_call when headless)
  {"add": "Part::Feature", "name": "Opening", "as": "hole"}   a new object
  {"set": {"o.Label": e, "o.Placement.Base": e}}   properties, in order
  {"do": e}  {"do": [e, …]}      for what it does (a method, a helper)
  {"put": {"field": e}, "into": "out"}   items into a dict (the answer)
  {"push": {"list": e}}          one more on a list
  {"each": "x", "in": e, "index": "i", "steps": [steps]}
  {"when": e, "then": [steps], "else": [steps]}
  {"choose": e, "of": {"value": [steps], …}, "else": [steps]}
  {"try": [steps], "on": "error" | "refusal" | "failure" | ["ValueError", …],
   "except": [steps], "reraise": true}
                                 "error" there is what was caught; failure:
                                 any error but a tool's own refusal, which
                                 passes through (except ToolError: raise);
                                 reraise: the except steps undo, and the
                                 error then goes on as it was
  {"answer": {"via": helper, "with": [e, …], "fields": {…}, "late": true,
              "then": [steps]}}  ends the run with this answer; late: the
                                 helper reads the fields itself, after its
                                 recompute; then: steps after the answer
                                 is made ("out"), for what must be read
                                 or made after it
The entry's own "answer" is the one a run reaches the end with.
"""
import os

from . import expr
from .protocol import Tool, ToolError

RUNNERS = ("make", "apply", "command", "read", "steps")
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
        if e.startswith("="):
            return expr.evaluate(e[1:], env, helpers)
        return _path(env, e[1:]) if e.startswith("$") else e
    if isinstance(e, list):
        return [value(x, env, helpers) for x in e]
    if isinstance(e, dict):
        if len(e) == 1:
            (op, arg), = e.items()
            if op == "fmt":
                return expr.fmt(arg, env, helpers)
            if op == "len":
                return len(value(arg, env, helpers))
            if op == "sum":
                return sum(value(arg, env, helpers))
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
    if "when" in r and not value(r["when"], env, helpers):
        return
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
        raise ToolError(r.get("code", "invalid_input"), expr.fmt(r["message"], env, helpers) if r.get("format") else r["message"])


_maker = expr.FUNCTIONS["maker"]


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
            # The step sees the argument as given ("$value", its default when left out) and its name ("$key").
            value(spec["then"], {**env, "value": a.get(k, spec["default"]) if "default" in spec else a.get(k), "key": k}, helpers)
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
    return _answered(e.get("answer") or {}, env, helpers)


def _answered(ans, env, helpers):
    for x in ans.get("first", []):
        value(x, env, helpers)  # e.g. recompute and record the step before the fields are read
    # late: the fields are read by the helper itself, once it has recomputed and recorded the step.
    env["fields"] = (lambda: fields(ans.get("fields"), env, helpers)) if ans.get("late") else fields(ans.get("fields"), env, helpers)
    out = helpers[ans["via"]](*[value(x, env, helpers) for x in ans.get("with", [])]) if ans.get("via") else env["fields"]
    if ans.get("then"):
        env["out"] = out  # after the answer: what is read or made once it is there
        _steps(ans["then"], env, helpers)
        out = env["out"]
    return out


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


# ---- the steps runner -----------------------------------------------------------------------

ACTIONS = ("let", "refuse", "make", "add", "set", "do", "put", "push", "each", "choose", "try", "then", "answer")
EXTRA = {"let": (), "refuse": ("code", "first"), "make": ("call", "kw", "as", "headless"), "add": ("name", "as"), "set": (), "do": (),
         "put": ("into",), "push": (), "each": ("in", "index", "steps"), "choose": ("of", "else"), "try": ("on", "except", "reraise"),
         "then": ("else",), "answer": ()}


class _Done(BaseException):
    """A run ended by an answer step (not an error: no try step catches it)."""

    def __init__(self, out):
        self.out = out


def _assign(names, v, env):
    if "," not in names:
        env[names] = v
        return
    keys = [k.strip() for k in names.split(",")]
    vals = list(v)
    if len(keys) != len(vals):
        raise ValueError(f"{names}: {len(keys)} names for {len(vals)} values")
    env.update(zip(keys, vals))


def _steps(steps, env, helpers):
    for st in steps:
        _step(st, env, helpers)


def _step(st, env, helpers):
    if "when" in st and not value(st["when"], env, helpers):
        if "then" in st:
            _steps(st.get("else", []), env, helpers)
        return
    if "let" in st:
        for k, x in st["let"].items():
            _assign(k, value(x, env, helpers), env)
    elif "refuse" in st:
        _steps(st.get("first", []), env, helpers)
        raise ToolError(st.get("code", "invalid_input"), value(st["refuse"], env, helpers))
    elif "make" in st:
        fn = value(st["make"], env, helpers) if st["make"].startswith("=") else _maker(st["make"])
        args = [value(x, env, helpers) for x in st.get("call", [])]
        kw = {k: value(x, env, helpers) for k, x in (st.get("kw") or {}).items()}
        env[st.get("as", "o")] = helpers["headless_call"](fn, *args, **kw) if st.get("headless") else fn(*args, **kw)
    elif "add" in st:
        env[st.get("as", "o")] = helpers["doc"]().addObject(st["add"], st.get("name", st["add"].split("::")[-1]))
    elif "set" in st:
        for path, x in st["set"].items():
            v = value(x, env, helpers)
            head, *mid, last = path.split(".")
            o = env[head]
            for k in mid:
                o = getattr(o, k)
            setattr(o, last, v)
    elif "do" in st:
        value(st["do"], env, helpers)
    elif "put" in st:
        into = env[st.get("into", "out")]
        for k, x in st["put"].items():
            into[k] = value(x, env, helpers)
    elif "push" in st:
        for k, x in st["push"].items():
            env[k].append(value(x, env, helpers))
    elif "each" in st:
        for i, x in enumerate(list(value(st["in"], env, helpers))):
            _assign(st["each"], x, env)
            if "index" in st:
                env[st["index"]] = i
            _steps(st["steps"], env, helpers)
    elif "choose" in st:
        v = value(st["choose"], env, helpers)
        _steps(st["of"][v] if isinstance(v, str) and v in st["of"] else st.get("else", []), env, helpers)
    elif "try" in st:
        try:
            _steps(st["try"], env, helpers)
        except _caught(st.get("on", "error")) as e:
            if st.get("on") == "failure" and isinstance(e, ToolError):
                raise  # a refusal made inside is the tool's own answer
            env["error"] = e
            _steps(st.get("except", []), env, helpers)
            if st.get("reraise"):
                raise  # the except steps undid what was done; the error goes on as it was
    elif "then" in st:
        _steps(st["then"], env, helpers)
    elif "answer" in st:
        raise _Done(_answered(st["answer"], env, helpers))
    else:
        raise ValueError(f"step {sorted(st)}: not a step the runner takes")


ERRORS = {"error": Exception, "refusal": ToolError, "failure": Exception, "TypeError": TypeError, "ValueError": ValueError, "KeyError": KeyError,
          "AttributeError": AttributeError, "ImportError": ImportError}


def _caught(on):
    """What a try step catches: "error" (any), "refusal" (a tool's own),
    "failure" (any but a tool's own refusal), or a list of Python's error
    names."""
    return tuple(ERRORS[k] for k in on) if isinstance(on, list) else ERRORS[on]


def run_steps(name, e, a, helpers):
    env = {"a": a, "tool": name}
    try:
        _steps(e.get("steps") or [], env, helpers)
    except _Done as d:
        return d.out
    return _answer(e, env, helpers)


RUN = {"make": run_make, "apply": run_apply, "command": run_command, "read": run_read, "steps": run_steps}


def tool(name, e, helpers):
    run = RUN[e["runner"]]
    return Tool(name, e["description"], e["inputSchema"], lambda a: run(name, e, a, helpers), changes=e["changes"], group=e["group"],
                reads=e.get("reads"), activity=e.get("activity"))


def tools(group, session, helpers, data=None, family=None):
    """The group's data-defined tools, bound to the family's helpers. Where
    two family modules share a group, an entry says whose helpers it calls
    ("family": the module's name) and that module asks for its own."""
    ents = entries() if data is None else data
    return [tool(k, v, helpers) for k, v in ents.items() if v["group"] == group and v.get("runner") and v.get("family") == family]


def check_entry(name, e):
    """What is wrong with a runner entry (the parts tooldata.check leaves to it)."""
    out = []
    r = e.get("runner")
    if r not in RUNNERS:
        return [f"{name}.runner: one of {', '.join(RUNNERS)}"]
    for k in ("target", "args", "rules", "answer", "steps"):
        out += [f"{name}.{k}{w}" for w in _check_values(e.get(k), "")]
    if r == "steps":
        if not isinstance(e.get("steps"), list):
            return out + [f"{name}.steps: a list of steps"]
        if set(e) & {"target", "args", "rules"}:
            out.append(f"{name}: a steps tool has steps and an answer, not target, args or rules")
        out += [f"{name}.steps{w}" for w in _check_steps(e["steps"], "")]
        return out + _check_answer(name + ".answer", e.get("answer"))
    if "steps" in e:
        out.append(f"{name}.steps: only with the steps runner")
    t = e.get("target")
    if not isinstance(t, dict):
        return out + [f"{name}.target: an object"]
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
        elif rule.get("format") and expr.check_fmt(rule["message"]):
            out.append(f"{name}.rules[{i}].message: {expr.check_fmt(rule['message'])}")
    return out + _check_answer(name + ".answer", e.get("answer"))


def _check_answer(where, ans):
    if ans is None:
        return []
    if not isinstance(ans, dict) or set(ans) - {"first", "via", "with", "fields", "late", "then"}:
        return [f"{where}: first, via, with, fields, late, then"]
    if "then" in ans:
        if not isinstance(ans["then"], list):
            return [f"{where}.then: a list of steps"]
        return [f"{where}.then{w}" for w in _check_steps(ans["then"], "")]
    return []


def _check_values(x, where):
    """Every expression and message template in x that the evaluator would not read."""
    out = []
    if isinstance(x, str):
        if x.startswith("=") and expr.check(x[1:]):
            out.append(f"{where}: {expr.check(x[1:])}")
    elif isinstance(x, list):
        for i, v in enumerate(x):
            out += _check_values(v, f"{where}[{i}]")
    elif isinstance(x, dict):
        if set(x) == {"fmt"} and isinstance(x["fmt"], str):
            w = expr.check_fmt(x["fmt"])
            return [f"{where}.fmt: {w}"] if w else []
        for k, v in x.items():
            out += _check_values(v, f"{where}.{k}")
    return out


def _check_steps(steps, where):
    out = []
    for i, st in enumerate(steps):
        at = f"{where}[{i}]"
        if not isinstance(st, dict):
            out.append(f"{at}: an object")
            continue
        acts = [k for k in ACTIONS if k in st]
        if len(acts) != 1:
            out.append(f"{at}: one of {', '.join(ACTIONS)} (has {sorted(st)})")
            continue
        act = acts[0]
        extra = set(st) - {act, "when"} - set(EXTRA[act])
        if extra:
            out.append(f"{at}: {act} does not take {sorted(extra)}")
        if act == "refuse":
            if st.get("code", "invalid_input") not in CODES:
                out.append(f"{at}.code: one of {', '.join(sorted(CODES))}")
            if not (isinstance(st["refuse"], str) or isinstance(st["refuse"], dict) and set(st["refuse"]) == {"fmt"}):
                out.append(f"{at}.refuse: the message, or {{\"fmt\": a message with fields}}")
        if act in ("let", "set", "put", "push") and not isinstance(st[act], dict):
            out.append(f"{at}.{act}: an object of names and values")
        if act == "make" and not isinstance(st["make"], str):
            out.append(f"{at}.make: a maker's dotted name")
        if act == "each" and not (isinstance(st.get("steps"), list) and "in" in st and isinstance(st["each"], str)):
            out.append(f"{at}: each (a name), in and steps")
        if act == "choose" and not isinstance(st.get("of"), dict):
            out.append(f"{at}.of: an object of steps by value")
        if act == "try" and not all(isinstance(k, str) and k in ERRORS for k in (st["on"] if isinstance(st.get("on"), list) else [st.get("on", "error")])):
            out.append(f"{at}.on: error | refusal | failure | a list of {', '.join(sorted(set(ERRORS) - {'error', 'refusal', 'failure'}))}")
        if act == "try" and not isinstance(st.get("reraise", False), bool):
            out.append(f"{at}.reraise: true or false")
        if act == "answer":
            out += _check_answer(f"{at}.answer", st["answer"])
        for key in ("first", "steps", "else", "except", "then", "try"):
            if key in st and key in (act, *EXTRA[act]):
                if isinstance(st[key], list):
                    out += _check_steps(st[key], f"{at}.{key}")
                else:
                    out.append(f"{at}.{key}: a list of steps")
        if act == "choose" and isinstance(st.get("of"), dict):
            for k, v in st["of"].items():
                out += _check_steps(v, f"{at}.of.{k}") if isinstance(v, list) else [f"{at}.of.{k}: a list of steps"]
    return out


def calls(e):
    """The names an entry's expressions call as functions, and the helpers
    it names (to check an entry against its family's helpers)."""
    names = set()

    def walk(x):
        if isinstance(x, str):
            if x.startswith("="):
                names.update(expr.called(x[1:]))
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, dict):
            if set(x) == {"fmt"} and isinstance(x["fmt"], str):
                for _, field, _s, _c in expr._split(x["fmt"]):
                    if field and not expr._PLAIN.match(field):
                        names.update(expr.called(field))
                return
            for k in ("call", "via", "helper"):
                if isinstance(x.get(k), str):
                    names.add(x[k])
            if x.get("headless"):
                names.add("headless_call" if x["headless"] is True else x["headless"])
            for v in x.values():
                walk(v)

    for k in ("target", "args", "rules", "answer", "steps"):
        walk(e.get(k))
    return names - set(expr.FUNCTIONS)
