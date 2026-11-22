# SPDX-License-Identifier: LGPL-2.1-or-later
"""The fast path (efficiency design C6, A6) and targeted reads (22 Nov).

The full answers and the guided workflow stay as they are. This is one more
way in, for an agent that already knows what it does:

  fast { do: [steps] }   one call runs a block of steps in the hub's step
                         language, calls tools through the server's normal
                         path, and answers with one short line, not a full
                         answer per call.
  get { what }           one value, with its unit: "Pad.Length",
                         "Body.volume", "Body.Edge7.length", "sketch.dof",
                         "active.body". Also a step of a block.

The block's steps (a subset of agentlink/runners.py's steps runner; never
make, add, set or do, which reach FreeCAD's objects directly):

  {"let": {"name": e, …}}                     values, in order
  {"call": "tool", "field": e, …, "as": "x"}  one tool call; its fields
                                              inline, or "args": {…}; its
                                              answer is "x" (and "last")
  {"get": "Body.volume" | "=e", "as": "v"}    a targeted read; its value
                                              goes in the answer's values
  {"each": "x", "in": e, "index": "i", "steps": [steps]}
  {"when": e, "then": [steps], "else": [steps]}  ("when" on any step too)
  {"choose": e, "of": {"value": [steps]}, "else": [steps]}
  {"try": [steps], "on": "refusal" | "error", "except": [steps]}
  {"refuse": "words", "code": "invalid_input"} ends the block, rolled back
  {"push": {"list": e}}                       one more on a list

e: a value, or "=expression" (agentlink/expr.py: parsed with Python's own
parser, walked by the hub's evaluator, an allow-list; never eval or exec).
"==text" is the text "=text". No Python is run that the agent wrote.

Safety of a block (the same as batch's where batch has it): every call goes
through the server's own path (input checks, field aliases, path guards,
each tool's leading checks and refusals, approvals, the co-work hold, the
undo step, the health); one checkpoint before the first change, when an
add-on offers checkpoints; the block stands or falls as a whole: a refusal
rolls it back with batch's rollback (tools.roll_back), which stops at the
person's own undo step; a record file like batch's (batches/…json); a dry
run (check: true) checks every step first and runs nothing. Before step 1
of a real run the same check runs (A6): a step that would be refused is
refused by its number before anything changes.

Plain Python: FreeCAD is reached through the tools and the session only.
"""
import ast
import copy
import json
import os
import re
import time

from . import expr
from .protocol import ToolError, check_input, compact

PREFS = "User parameter:BaseApp/Preferences/Mod/AgentLink"
PREF = "FastPath"
ENV = "AGENTLINK_FASTPATH"
OFF_CODE = "not_allowed"
FAST, GET = "fast", "get"

# What a block does not call: another runner, the person's own OK and
# settings, input to the window and its dialogs, jobs, the history (a block
# rolls back by undo), a restart. The same list as a cookbook script's
# (agentlink/cookbook.py SCRIPT_BLOCKED), and more.
BLOCKED = {"batch", FAST, "job_start", "live_run", "app_restart", "app_force_restart", "agentlink_update", "pref_set", "pref_reset",
           "pref_import", "pref_pack", "app_extensions", "addon", "port_scaffold", "approve_file", "approve_code", "gui_input",
           "dialog_answer", "gui_unstick", "addon_test", "cookbook_run"}
# The history tools (by their prefix, the add-ons' too) do not run in a block:
# a block is taken back by undo. Only the reading of the history does.
READ_HISTORY = {"history_diff"}
MAX_STEPS = 2000      # steps a block may take (a loop's steps each count)
MAX_CALLS = 200       # tool calls a block may make
MAX_DRY_CALLS = 400   # calls a check reads before it stops reading
WORDS = 240           # a warning's or refusal's words in the answer

STEPS = ("call", "get", "let", "each", "choose", "try", "refuse", "push")
EXTRA = {"call": ("as", "args"), "get": ("as",), "let": (), "each": ("in", "index", "steps"), "choose": ("of", "else"),
         "try": ("on", "except"), "refuse": ("code",), "push": (), "then": ("else",)}
CATCH = ("refusal", "error")

# A left-out field a tool requires, filled from what the session holds now
# (the current body, sketch and last result): field → what fills it.
REQUIRED_FROM = {"body": "body", "sketch": "sketch", "profile": "sketch", "object": "last", "objects": "last", "feature": "feature",
                 "bodies": "body"}
# A field a tool takes "when there is one" (body, sketch): filled only from
# what this block made or named, so the block's own sketch is meant.
BLOCK_FROM = ("body", "sketch")
HELPERS_OF_ORIGIN = ("App::Origin", "App::Line", "App::Plane", "App::Point")


def enabled():
    """Whether the fast path and the get read are on: preference FastPath
    (Mod/AgentLink, default on), and AGENTLINK_FASTPATH=off turns it off."""
    if os.environ.get(ENV, "on").strip().lower() in ("0", "false", "off", "no"):
        return False
    try:
        import FreeCAD

        return bool(FreeCAD.ParamGet(PREFS).GetBool(PREF, True))
    except Exception:  # noqa: BLE001 - no FreeCAD here: the default
        return True


def off(tool):
    return ToolError(OFF_CODE, f"fast path off: {tool} does not run here (the person's preference FastPath in Mod/AgentLink, "
                               f"or {ENV}=off). Call the tools one by one, or use batch.")


# ---- the block's shape and its expressions ---------------------------------------------------

_NO_CALL = {"maker"}
_NO_METHOD = {"format", "format_map"}


def _expr_words(text):
    """What is wrong with an expression of a block, or None."""
    w = expr.check(text)
    if w:
        return w
    for n in ast.walk(expr.parse(text)):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name) and f.id in _NO_CALL:
                return f"{text!r}: {f.id}() is not part of a block's expressions"
            if isinstance(f, ast.Attribute) and f.attr in _NO_METHOD:
                return f"{text!r}: .{f.attr}() is not part of a block's expressions"
    return None


def _values_words(x, where):
    if isinstance(x, str):
        if x.startswith("=") and not x.startswith("=="):
            w = _expr_words(x[1:])
            return [(where, w)] if w else []
        return []
    if isinstance(x, list):
        return [w for i, v in enumerate(x) for w in _values_words(v, f"{where}.{i}")]
    if isinstance(x, dict):
        return [w for k, v in x.items() for w in _values_words(v, f"{where}.{k}")]
    return []


def action(st):
    """A step's action: call when it has one (its other fields are the
    call's), else the one of STEPS it has, else then (a when step)."""
    if "call" in st:
        return "call"
    acts = [k for k in STEPS if k in st]
    if len(acts) == 1:
        return acts[0]
    if not acts and "then" in st:
        return "then"
    return None


def shape_words(steps, where="do"):
    """[(where, what is wrong)] with a block's steps, before anything runs."""
    if not isinstance(steps, list):
        return [(where, "a list of steps")]
    out = []
    for i, st in enumerate(steps):
        at = f"{where}.{i}"
        if not isinstance(st, dict):
            out.append((at, "a step is an object"))
            continue
        act = action(st)
        if act is None:
            have = [k for k in STEPS if k in st]
            out.append((at, f"one of {', '.join(STEPS)}, or when with then (has {', '.join(sorted(st)) or 'nothing'})" if not have
                        else f"one action a step: {', '.join(have)}"))
            continue
        if act != "call":
            extra = set(st) - {act, "when"} - set(EXTRA[act])
            if extra:
                out.append((at, f"{act} does not take {', '.join(sorted(extra))}"))
                continue
        if "when" in st:
            out += _values_words(st["when"], f"{at}.when")
        if act == "call":
            if not isinstance(st["call"], str) or not st["call"]:
                out.append((at, "call: a tool's name"))
            if "args" in st and not isinstance(st["args"], (dict, str)):
                out.append((f"{at}.args", "the call's fields as an object"))
            if "as" in st and not _name_ok(st["as"]):
                out.append((f"{at}.as", "a plain name (letters, digits, _; not first)"))
            out += _values_words({k: v for k, v in st.items() if k not in ("call", "as", "when")}, at)
        elif act == "get":
            if not isinstance(st["get"], str) or not st["get"].strip():
                out.append((at, "get: what to read (\"Pad.Length\", \"Body.volume\", \"=expression\")"))
            elif st["get"].startswith("="):
                out += _values_words(st["get"], f"{at}.get")
            else:
                w = what_words(st["get"])
                if w:
                    out.append((f"{at}.get", w))
            if "as" in st and not _name_ok(st["as"]):
                out.append((f"{at}.as", "a plain name"))
        elif act in ("let", "push"):
            if not isinstance(st[act], dict) or not st[act]:
                out.append((at, f"{act}: an object of names and values"))
            else:
                for k in st[act]:
                    if not all(_name_ok(n.strip()) for n in str(k).split(",")):
                        out.append((f"{at}.{act}", f"{k!r}: a plain name (or \"p, q\" to unpack)"))
                out += _values_words(st[act], f"{at}.{act}")
        elif act == "each":
            if not _name_ok(st["each"]) or "in" not in st or not isinstance(st.get("steps"), list):
                out.append((at, "each (a name), in and steps"))
            else:
                out += _values_words(st["in"], f"{at}.in")
                out += shape_words(st["steps"], f"{at}.steps")
            if "index" in st and not _name_ok(st["index"]):
                out.append((f"{at}.index", "a plain name"))
        elif act == "then":
            if "when" not in st:
                out.append((at, "then goes with when"))
            out += shape_words(st["then"], f"{at}.then")
            if "else" in st:
                out += shape_words(st["else"], f"{at}.else")
        elif act == "choose":
            out += _values_words(st["choose"], f"{at}.choose")
            if not isinstance(st.get("of"), dict):
                out.append((f"{at}.of", "an object of steps by value"))
            else:
                for k, v in st["of"].items():
                    out += shape_words(v, f"{at}.of.{k}")
            if "else" in st:
                out += shape_words(st["else"], f"{at}.else")
        elif act == "try":
            if st.get("on", "refusal") not in CATCH:
                out.append((f"{at}.on", "refusal (a tool's refusal) or error (any)"))
            out += shape_words(st["try"], f"{at}.try")
            out += shape_words(st.get("except", []), f"{at}.except")
        elif act == "refuse":
            if not isinstance(st["refuse"], str):
                out.append((at, "refuse: the words"))
            else:
                out += _values_words(st["refuse"], f"{at}.refuse")
    return out


_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _name_ok(n):
    return isinstance(n, str) and bool(_NAME.match(n))


# ---- targeted reads ----------------------------------------------------------------------------

ACTIVE = ("active.body", "active.sketch", "active.document", "selection", "bodies")
SHAPE = {"volume": ("measure", "volume", "mm³"), "area": ("measure", "area", "mm²"), "size": ("measure", "size", "mm"),
         "min": ("measure", "min", "mm"), "max": ("measure", "max", "mm"),
         "mass": ("measure_mass", "mass", "g"), "centerOfMass": ("measure_mass", "centerOfMass", "mm"),
         "density": ("measure_mass", "density", "g/cm³"), "inertia": ("measure_mass", "inertia", "g·mm²")}
SKETCH = {"dof": None, "closedWires": None, "openVertices": None, "readyForFeature": None, "conflicting": None, "redundant": None,
          "malformed": None}
ELEMENT = re.compile(r"^(Edge|Face|Vertex)\d+$")
ELEMENT_DEFAULT = {"Edge": "length", "Face": "area", "Vertex": "at"}
ELEMENT_UNITS = {"length": "mm", "radius": "mm", "diameter": "mm", "area": "mm²", "at": "mm", "mid": "mm", "centroid": "mm", "center": "mm",
                 "apex": "mm", "minorRadius": "mm", "semiAngle": "°"}
PROP_UNITS = {"Length": "mm", "Distance": "mm", "Angle": "°", "Area": "mm²", "Volume": "mm³"}


def what_words(what):
    """What is wrong with a targeted read's form, or None (the objects are
    looked up when it runs)."""
    if not isinstance(what, str) or not what.strip():
        return "what: \"Pad.Length\", \"Body.volume\", \"Body.Edge7.length\", \"sketch.dof\", \"active.body\""
    w = what.strip()
    if w in ACTIVE:
        return None
    parts = w.split(".")
    if len(parts) < 2 or not all(parts):
        # A tool's name here (live, 22 Nov: a local model read "body_check"):
        # a tool runs as a step of its own.
        tool = f" If {w} is a tool, run it as a step: {{ \"call\": \"{w}\" }}." if len(parts) == 1 and "_" in w else ""
        return f"what {w!r}: an object and what to read of it, \"Object.Property\" (\"Pad.Length\", \"Body.volume\"), or one of {', '.join(ACTIVE)}.{tool}"
    return None


def _fmt_num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return v
    v = round(float(v), 4)
    if v == int(v) and abs(v) < 1e15:
        v = int(v)
        return f"{v:,}" if abs(v) >= 10000 else str(v)
    return f"{v:,.4g}" if abs(v) >= 10000 else f"{v:g}"


def with_unit(v, unit):
    """A value as get answers it: a number with its unit ("1520 mm³"), a
    list of numbers with it after ("[1, 2, 3] mm"), anything else as it is."""
    if unit is None:
        return v
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"{_fmt_num(v)} {unit}"
    if isinstance(v, list) and v and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
        return f"[{', '.join(str(_fmt_num(x)) for x in v)}] {unit}"
    return v


def _reader(server, name, args):
    """An existing reader's answer, by its tool (its own input checks and
    refusals; no echo, meter or undo step: it changes nothing)."""
    t = server.tools.get(name)
    if t is None or t.changes_for(args):
        raise ToolError("unavailable", f"get: the reader {name} is not here, so this read cannot be made.")
    a = copy.deepcopy(args)
    check_input(t.schema, a, name)
    out = t.fn(a)
    return out if isinstance(out, dict) else {}


def _doc_object(doc, name):
    if doc is None:
        return None
    try:
        o = doc.getObject(name)
        if o is not None:
            return o
        found = doc.getObjectsByLabel(name)
        return found[0] if found else None
    except Exception:  # noqa: BLE001
        return None


def _gui():
    try:
        import FreeCAD

        if not getattr(FreeCAD, "GuiUp", False):
            return None
        import FreeCADGui

        return FreeCADGui
    except Exception:  # noqa: BLE001
        return None


def current(session, which):
    """The current body or sketch: the one the session's last block made or
    named (still there), else the window's active body or sketch in edit,
    else the only one in the document. Its label, or None."""
    doc = getattr(session, "doc", None)
    ctx = context(session)
    if ctx.get(which):
        o = _doc_object(doc, ctx[which])
        if o is not None:
            return o.Label
    gui = _gui()
    if gui is not None:
        try:
            gd = gui.ActiveDocument
            if which == "body":
                o = gd.ActiveView.getActiveObject("pdbody")
            else:
                o = getattr(gd.getInEdit(), "Object", None)
                if getattr(o, "TypeId", "") != "Sketcher::SketchObject":
                    o = None
            if o is not None:
                return o.Label
        except Exception:  # noqa: BLE001
            pass
    want = "PartDesign::Body" if which == "body" else "Sketcher::SketchObject"
    try:
        found = [o for o in doc.Objects if getattr(o, "TypeId", "") == want]
    except Exception:  # noqa: BLE001
        found = []
    return found[0].Label if len(found) == 1 else None


def read(server, session, what):
    """One targeted read: (the value, its unit or None)."""
    w = what_words(what)
    if w:
        raise ToolError("invalid_input", w)
    w = what.strip()
    doc = getattr(session, "doc", None)
    if w == "active.document":
        return (getattr(doc, "Label", None), None)
    if w in ("active.body", "active.sketch"):
        return (current(session, w.split(".")[1]), None)
    if w == "bodies":
        return ([o.Label for o in session.bodies()], None)
    if w == "selection":
        gui = _gui()
        rows = []
        if gui is not None:
            try:
                for x in gui.Selection.getSelectionEx("", 0) or ():
                    subs = [str(n) for n in (getattr(x, "SubElementNames", None) or ()) if n]
                    rows += [f"{x.Object.Label}.{s}" if s else x.Object.Label for s in subs or [""]]
            except Exception:  # noqa: BLE001
                pass
        return (rows, None)
    parts = w.split(".")
    o, rest = None, []
    if parts[0] in ("body", "sketch") and _doc_object(doc, parts[0]) is None:
        label = current(session, parts[0])
        if label is None:
            raise ToolError("not_found", f"{w}: no current {parts[0]} (none made or named by a block, none active, not just one in the document). Name it: \"{parts[0].capitalize()}.{'.'.join(parts[1:])}\".")
        o, rest = _doc_object(doc, label), parts[1:]
    else:
        for i in range(len(parts) - 1, 0, -1):
            o = _doc_object(doc, ".".join(parts[:i]))
            if o is not None:
                rest = parts[i:]
                break
    if o is None:
        raise ToolError("not_found", f"{w}: no object {parts[0]!r} in {getattr(doc, 'Label', 'the document')} (a name or a label; session_state lists the bodies).")
    head = rest[0]
    if ELEMENT.match(head):
        kind = re.match(r"[A-Za-z]+", head).group(0)
        attr = rest[1] if len(rest) > 1 else ELEMENT_DEFAULT[kind]
        got = _reader(server, "measure", {"a": f"{o.Name}.{head}"}).get("a") or {}
        if attr not in got:
            raise ToolError("not_found", f"{w}: {head} has no {attr} — it has {', '.join(k for k in got if k != 'ref')}.")
        return (_walk(got[attr], rest[2:], w), ELEMENT_UNITS.get(attr) if len(rest) <= 2 else None)
    if head in SKETCH and getattr(o, "TypeId", "") == "Sketcher::SketchObject":
        got = _reader(server, "sketch_state", {"sketch": o.Name, "detail": False})
        return (_walk(got.get(head), rest[1:], w), None)
    if head in SHAPE and not _has_prop(o, head):
        tool, key, unit = SHAPE[head]
        got = _reader(server, tool, {"a": o.Name} if tool == "measure" else {"body": o.Name})
        got = got.get("a", got) if tool == "measure" else got
        if key not in got:
            raise ToolError("not_found", f"{w}: {tool} gave no {key} for {o.Label}.")
        return (_walk(got[key], rest[1:], w), unit if len(rest) == 1 else None)
    got = _reader(server, "object_get", {"object": o.Name, "filter": [head]})
    entry = (got.get("properties") or {}).get(head)
    if not isinstance(entry, dict):
        raise ToolError("not_found", f"{w}: {o.Label} has no property {head} (object_get {{ object: \"{o.Label}\" }} lists them).")
    return (_walk(entry.get("value"), rest[1:], w), PROP_UNITS.get(entry.get("type")) if len(rest) == 1 else None)


def _has_prop(o, name):
    try:
        return name in (o.PropertiesList or ())
    except Exception:  # noqa: BLE001
        return False


def _walk(v, keys, what):
    for k in keys:
        if isinstance(v, dict) and k in v:
            v = v[k]
        elif isinstance(v, list) and re.fullmatch(r"-?\d+", k) and -len(v) <= int(k) < len(v):
            v = v[int(k)]
        else:
            have = ", ".join(map(str, v)) if isinstance(v, dict) else (f"a list of {len(v)}" if isinstance(v, list) else type(v).__name__)
            raise ToolError("not_found", f"{what}: no {k!r} there ({have}).")
    return v


def get_tool(server, session, a):
    """get { what }: {what: value with its unit}, for one or several."""
    if not enabled():
        raise off(GET)
    what = a.get("what")
    whats = [what] if isinstance(what, str) else what
    if not isinstance(whats, list) or not whats or len(whats) > 20 or not all(isinstance(x, str) for x in whats):
        raise ToolError("invalid_input", "what: \"Pad.Length\", \"Body.volume\", \"Body.Edge7.length\", \"sketch.dof\", \"active.body\", or a list of up to 20.")
    out, missed = {}, {}
    for x in whats:
        # One value that cannot be read does not lose the others (live, 22
        # Nov: a body with no material had no mass, and the whole list was
        # refused). A single what still refuses as before.
        try:
            v, unit = read(server, session, x)
        except ToolError as e:
            if len(whats) == 1:
                raise
            missed[x.strip()] = e.message
            continue
        out[x.strip()] = with_unit(v, unit)
    if missed:
        out["missed"] = missed
    return out


# ---- the session's context: current body, sketch, last result -----------------------------------

def context(session):
    """The session's fast-path context for its document now: {doc, body,
    sketch, feature, last} (object names), empty for another document."""
    doc = getattr(session, "doc", None)
    name = getattr(doc, "Name", None)
    ctx = getattr(session, "fast_ctx", None)
    if not isinstance(ctx, dict) or ctx.get("doc") != name:
        ctx = {"doc": name}
        try:
            session.fast_ctx = ctx
        except Exception:  # noqa: BLE001
            pass
    return ctx


class Unknown:
    """A value a check cannot know before the block runs (a call's answer)."""

    def __repr__(self):
        return "?"


UNKNOWN = Unknown()


def _has_unknown(v, depth=0):
    if v is UNKNOWN:
        return True
    if depth > 4:
        return False
    if isinstance(v, dict):
        return any(_has_unknown(x, depth + 1) for x in v.values())
    if isinstance(v, (list, tuple)):
        return any(_has_unknown(x, depth + 1) for x in v)
    return False


class Stop(Exception):
    """The block stops at a step: (where, tool, code, words)."""

    def __init__(self, where, tool, code, words, body=None):
        super().__init__(words)
        self.where, self.tool, self.code, self.words, self.body = where, tool, code, words, body


def _no_maker(*_a, **_k):
    raise expr.ExprError("maker() is not part of a block's expressions")


SAFE = {"maker": _no_maker}


# ---- the run ------------------------------------------------------------------------------------

class Run:
    """One block, run (dry False) or checked (dry True: nothing is called,
    each call's tool, fields and, before the first change, leading checks
    are read)."""

    def __init__(self, server, session, dry=False, budget=None):
        self.server, self.s, self.dry = server, session, dry
        self.env = {"last": UNKNOWN if dry else None}
        self.steps_taken = 0
        self.calls = 0
        self.rows = []           # each call: {step, tool, ok, result | error}
        self.values = {}
        self.warnings = []
        self.filled = []
        self.made = []           # labels of what the block made
        self.health_bad = 0
        self.changed = False     # a changing call came before (dry: leading checks stop counting)
        self.guarded = 0         # inside a try that catches refusals
        self.notes = []          # dry: what was not read
        self.read_checks = 0
        self.mine = None         # the run's batch_now (set by the caller of a real run)
        self.on_call = None      # the real call: on_call(where, tool, args) -> body
        self.block_ctx = {}      # what this block made or named: body, sketch
        self.t0 = time.time()
        self.budget = budget

    # values
    def val(self, e, where):
        if isinstance(e, str):
            if e.startswith("=="):
                return e[1:]
            if e.startswith("="):
                try:
                    return expr.evaluate(e[1:], self.env, SAFE)
                except Exception as x:  # noqa: BLE001
                    if self.dry and self._unknown_in(e[1:]):
                        return UNKNOWN
                    raise Stop(where, None, "invalid_input", f"{e[:80]}: {type(x).__name__}: {str(x)[:120]}") from None
            return e
        if isinstance(e, list):
            return [self.val(x, f"{where}.{i}") for i, x in enumerate(e)]
        if isinstance(e, dict):
            return {k: self.val(v, f"{where}.{k}") for k, v in e.items()}
        return e

    def _unknown_in(self, text):
        try:
            names = {n.id for n in ast.walk(expr.parse(text)) if isinstance(n, ast.Name)}
        except Exception:  # noqa: BLE001
            return False
        return any(_has_unknown(self.env.get(n)) for n in names)

    def truth(self, e, where):
        v = self.val(e, where)
        return v if v is UNKNOWN else bool(v)

    # steps
    def block(self, steps, where):
        for i, st in enumerate(steps):
            self.step(st, f"{where}.{i}")

    def step(self, st, where):
        self.steps_taken += 1
        if self.steps_taken > MAX_STEPS:
            raise Stop(where, None, "invalid_input", f"the block took more than {MAX_STEPS} steps: split it, or loop over less.")
        act = action(st)
        if "when" in st and act != "then":
            c = self.truth(st["when"], f"{where}.when")
            if c is not UNKNOWN and not c:
                return
        if act == "let":
            for k, x in st["let"].items():
                self._assign(k, self.val(x, f"{where}.let.{k}"), where)
        elif act == "call":
            self.call(st, where)
        elif act == "get":
            self.get(st, where)
        elif act == "each":
            xs = self.val(st["in"], f"{where}.in")
            if xs is UNKNOWN:
                self._assign(st["each"], UNKNOWN, where)
                if "index" in st:
                    self.env[st["index"]] = UNKNOWN
                self.notes.append(f"{where}: what it loops over is known only when the block runs; its steps were read once")
                self.block(st["steps"], f"{where}.steps")
                return
            try:
                xs = list(xs)
            except TypeError:
                raise Stop(f"{where}.in", None, "invalid_input", f"in: a list to loop over, not {type(xs).__name__}") from None
            for i, x in enumerate(xs):
                self._assign(st["each"], x, where)
                if "index" in st:
                    self.env[st["index"]] = i
                self.block(st["steps"], f"{where}.steps")
                if self.dry and self.calls > MAX_DRY_CALLS:
                    return
        elif act == "then":
            c = self.truth(st["when"], f"{where}.when")
            if c is UNKNOWN:
                self.block(st["then"], f"{where}.then")
                self.block(st.get("else", []), f"{where}.else")
            elif c:
                self.block(st["then"], f"{where}.then")
            else:
                self.block(st.get("else", []), f"{where}.else")
        elif act == "choose":
            v = self.val(st["choose"], f"{where}.choose")
            if v is UNKNOWN:
                for k, steps in st["of"].items():
                    self.block(steps, f"{where}.of.{k}")
                self.block(st.get("else", []), f"{where}.else")
            else:
                key = v if isinstance(v, str) else json.dumps(v)
                if key in st["of"]:
                    self.block(st["of"][key], f"{where}.of.{key}")
                else:
                    self.block(st.get("else", []), f"{where}.else")
        elif act == "try":
            on = st.get("on", "refusal")
            self.guarded += 1
            try:
                self.block(st["try"], f"{where}.try")
            except Stop as e:
                self.guarded -= 1
                if on == "refusal" and e.tool is None:
                    raise  # not a tool's refusal: an error of the block itself
                self.env["error"] = {"step": e.where, "tool": e.tool, "code": e.code, "message": e.words}
                if not self.dry:
                    self.warnings.append(_cut(f"{e.where}{' (' + e.tool + ')' if e.tool else ''}: {e.words} (caught)"))
                self.block(st.get("except", []), f"{where}.except")
                return
            self.guarded -= 1
            if self.dry:
                self.env["error"] = UNKNOWN
                self.block(st.get("except", []), f"{where}.except")
        elif act == "refuse":
            if self.dry:
                return  # the block's own refusal: only when it runs
            words = self.val(st["refuse"], f"{where}.refuse")
            raise Stop(where, None, st.get("code", "invalid_input") if st.get("code") in _CODES else "invalid_input", str(words))
        elif act == "push":
            for k, x in st["push"].items():
                lst = self.env.get(k)
                if lst is None:
                    lst = self.env[k] = []
                if lst is UNKNOWN:
                    continue
                if not isinstance(lst, list):
                    raise Stop(where, None, "invalid_input", f"push {k}: {k} is not a list")
                lst.append(self.val(x, f"{where}.push.{k}"))

    def _assign(self, names, v, where):
        if "," not in names:
            self.env[names] = v
            return
        keys = [k.strip() for k in names.split(",")]
        if v is UNKNOWN:
            for k in keys:
                self.env[k] = UNKNOWN
            return
        vals = list(v) if isinstance(v, (list, tuple)) else None
        if vals is None or len(vals) != len(keys):
            raise Stop(where, None, "invalid_input", f"{names}: {len(keys)} names for {'one value' if vals is None else len(vals)}")
        self.env.update(zip(keys, vals))

    # a call
    def call(self, st, where):
        name = st["call"]
        server = self.server
        tool = server.tools.get(name)
        if tool is None:
            import difflib

            near = difflib.get_close_matches(str(name), list(server.tools), n=3, cutoff=0.5)
            raise Stop(where, name, "not_found", f"{name}: no such tool{' — near: ' + ', '.join(near) if near else ''} (tool_find finds tools).")
        if name in BLOCKED or getattr(tool, "alias_of", None) in BLOCKED or (name.startswith("history_") and name not in READ_HISTORY):
            raise Stop(where, name, "refused", f"{name} does not run in a fast block (another runner, the person's OK or settings, the window's "
                                               "input and dialogs, jobs, the history or a restart): call it on its own.")
        if "args" in st:
            args = self.val(st["args"], f"{where}.args")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = None
        else:
            args = {k: self.val(v, f"{where}.{k}") for k, v in st.items() if k not in ("call", "as", "when")}
        if args is not UNKNOWN and not isinstance(args, dict):
            raise Stop(where, name, "invalid_input", "args: the call's fields as an object")
        self.calls += 1
        if self.calls > MAX_CALLS and not self.dry:
            raise Stop(where, name, "invalid_input", f"more than {MAX_CALLS} calls in one block: split it.")
        if self.dry:
            self._dry_call(tool, args, where, st)
            return
        if self.budget is not None and self.calls > 1 and time.time() - self.t0 > self.budget:
            raise Stop(where, name, "invalid_input", f"out of time: no call starts after {self.budget:g} s (a client waits about 80 s). "
                                                     "The block was taken back whole: split it into shorter blocks.")
        self.fill(tool, args, where)
        try:
            from . import jobs, keep

            if keep.is_heavy(name) and jobs.eligible(tool, args, self.s):
                raise Stop(where, name, "refused", f"{name} is a heavy read: call it on its own, where it runs as a job.")
        except Stop:
            raise
        except Exception:  # noqa: BLE001
            pass
        body = self.on_call(where, tool, args)
        if "as" in st:
            self.env[st["as"]] = body
        self.env["last"] = body

    def fill(self, tool, args, where):
        """Left-out fields from the context: a required one from the
        session's (REQUIRED_FROM), a body or sketch "when there is one"
        from what this block made or named (BLOCK_FROM)."""
        schema = tool.schema or {}
        props = schema.get("properties") or {}
        req = schema.get("required") or []
        ctx = context(self.s)
        doc = getattr(self.s, "doc", None)
        for k in props:
            if k in args or (k in req and k not in REQUIRED_FROM) or (k not in req and k not in BLOCK_FROM):
                continue
            src = REQUIRED_FROM.get(k) if k in req else k
            v = (self.block_ctx.get(src) if k not in req else (self.block_ctx.get(src) or ctx.get(src)))
            if not v or (UNKNOWN is not v and _doc_object(doc, v) is None):
                continue
            if v is UNKNOWN:
                args[k] = UNKNOWN
                continue
            args[k] = [v] if (props.get(k) or {}).get("type") == "array" else v
            self.filled.append(f"{tool.name}.{k}={_label(doc, v)}")
        # What this call names becomes current.
        for k in BLOCK_FROM:
            if isinstance(args.get(k), str) and k in props:
                o = _doc_object(doc, args[k])
                if o is not None:
                    self.block_ctx[k] = o.Name

    def note_made(self, names0, tool, args):
        """The objects a call made: the context's body, sketch, feature and
        last; their labels for the answer."""
        doc = getattr(self.s, "doc", None)
        ctx = context(self.s)
        try:
            new = [o for o in doc.Objects if o.Name not in names0]
        except Exception:  # noqa: BLE001
            new = []
        for o in new:
            t = getattr(o, "TypeId", "")
            if t in HELPERS_OF_ORIGIN:
                continue
            self.made.append(o.Label)
            if t == "PartDesign::Body":
                self.block_ctx["body"] = ctx["body"] = o.Name
            elif t == "Sketcher::SketchObject":
                self.block_ctx["sketch"] = ctx["sketch"] = o.Name
                b = _parent_body(o)
                if b is not None:
                    self.block_ctx["body"] = ctx["body"] = b.Name
            else:
                ctx["feature"] = o.Name
                b = _parent_body(o)
                if b is not None:
                    self.block_ctx["body"] = ctx["body"] = b.Name
            ctx["last"] = o.Name
        for k in BLOCK_FROM:
            if self.block_ctx.get(k):
                ctx[k] = self.block_ctx[k]

    def _dry_call(self, tool, args, where, st):
        name = tool.name
        if self.calls > MAX_DRY_CALLS:
            if len(self.notes) < 40:
                self.notes.append(f"{where}: past {MAX_DRY_CALLS} calls the check reads no more")
            return
        if args is UNKNOWN:
            args = {}
            self.notes.append(f"{where} ({name}): its fields are known only when the block runs")
        self.fill(tool, args, where)
        known = {k: v for k, v in args.items() if not _has_unknown(v)}
        unknown = [k for k in args if k not in known]
        schema = dict(tool.schema or {})
        if unknown:
            schema["required"] = [k for k in schema.get("required") or [] if k not in unknown]
        t = tool.for_call(known)
        a = copy.deepcopy(known)
        try:
            check_input(schema, a, name)
        except ToolError as e:
            self._dry_refusal(where, name, e.code, e.message)
        changing = True
        try:
            changing = bool(t.changes_for(a))
        except Exception:  # noqa: BLE001
            pass
        if not self.changed and not unknown:
            try:
                from . import needs

                r = needs.of_tool(tool, a)
                self.read_checks += 1
                if r.get("applies") is False and r.get("wouldRefuse"):
                    x = r["wouldRefuse"][0]
                    self._dry_refusal(where, name, x.get("code", "invalid_input"), _said(x.get("words")) + " That is its leading check.")
            except Stop:
                raise
            except Exception:  # noqa: BLE001 - a reading is advice; it never stops a block by failing
                pass
        if changing:
            self.changed = True
        body = UNKNOWN
        if "as" in st:
            self.env[st["as"]] = body
        self.env["last"] = body
        if changing and name in ("sketch_new", "pd_body_new"):
            # Made by the block: its name is known only when it runs.
            self.block_ctx["sketch" if name == "sketch_new" else "body"] = UNKNOWN

    def _dry_refusal(self, where, name, code, words):
        if self.guarded:
            self.notes.append(_cut(f"{where} ({name}) would be refused, inside a try that catches it: {words}"))
            return
        raise Stop(where, name, code, words)

    # a targeted read
    def get(self, st, where):
        what = st["get"]
        key = st.get("as") or what
        if what.startswith("="):
            v = self.val(what, f"{where}.get")
            self.env[st.get("as") or "got"] = v
            if not self.dry:
                self.values[key] = _plain(v)
            return
        if self.dry:
            self.env[st.get("as") or "got"] = UNKNOWN
            return
        try:
            v, unit = read(self.server, self.s, what)
        except ToolError as e:
            raise Stop(where, GET, e.code, e.message) from None
        self.env[st.get("as") or "got"] = v
        self.values[key] = with_unit(_plain(v), unit)


_CODES = {"invalid_input", "not_found", "invalid_state", "unavailable", "failed", "not_allowed", "refused"}


def _plain(v):
    try:
        return json.loads(compact(v))
    except Exception:  # noqa: BLE001
        return str(v)


def _said(s):
    """Words that end as a sentence does, so the next words follow on."""
    s = str(s).rstrip()
    return s if not s or s[-1] in ".!?)»\"'" else s + "."


def _cut(s, n=WORDS):
    s = str(s)
    return s if len(s) <= n else s[:n - 1] + "…"


def _label(doc, name):
    o = _doc_object(doc, name)
    return getattr(o, "Label", name) if o is not None else name


def _parent_body(o):
    try:
        g = o.getParentGeoFeatureGroup()
        return g if getattr(g, "TypeId", "") == "PartDesign::Body" else None
    except Exception:  # noqa: BLE001
        return None


def _volume(session):
    try:
        return sum(float(o.Shape.Volume) for o in session.bodies())
    except Exception:  # noqa: BLE001
        return None


def _health_words(body):
    h = body.get("health") if isinstance(body, dict) else None
    if isinstance(h, dict) and h.get("ok") is False:
        return _cut(h.get("verdict") or "not clean")
    return None


# ---- the checks before step 1 (A6) ---------------------------------------------------------------

def check(server, session, steps):
    """The dry run: (the run, None) when every step reads as fine, or
    (the run, Stop) at the first that would be refused."""
    shape = shape_words(steps)
    run = Run(server, session, dry=True)
    if shape:
        where, words = shape[0]
        return run, Stop(where, None, "invalid_input", words)
    try:
        run.block(steps, "do")
    except Stop as e:
        return run, e
    return run, None


def precheck_calls(server, calls, first=0):
    """batch { check: true } (A6): each call's fields and, up to and with
    its first changing call, its leading checks, read before the first call
    runs. None, or the ToolError naming the call by its index."""
    from . import chain as _chain

    changed = False
    for i, c in enumerate(calls):
        t = server.tools.get(c["tool"])
        if t is None:
            continue
        args = c.get("arguments") or {}
        if _chain.has_refs(args):
            changed = changed or bool(getattr(t, "changes", False))
            continue  # $from / $file: known only as it runs
        a = copy.deepcopy(args)
        try:
            check_input(t.schema, a, t.name)
        except ToolError as e:
            return ToolError(e.code, f"calls.{first + i} ({t.name}): {_said(e.message)} Read before the batch ran (check: true). Nothing was run.")
        try:
            changing = bool(t.for_call(a).changes_for(a))
        except Exception:  # noqa: BLE001
            changing = bool(getattr(t, "changes", False))
        if not changed:
            try:
                from . import needs

                r = needs.of_tool(t, a)
                if r.get("applies") is False and r.get("wouldRefuse"):
                    x = r["wouldRefuse"][0]
                    return ToolError(x.get("code", "invalid_input"), f"calls.{first + i} ({t.name}): {_said(x.get('words'))} Read from its leading checks "
                                                                      "before the batch ran (check: true). Nothing was run.")
            except Exception:  # noqa: BLE001 - advice only
                pass
        changed = changed or changing
    return None


# ---- the fast tool --------------------------------------------------------------------------------

def _summary(run, ok, secs, v0, v1, cp=None):
    parts = [f"{'ok' if ok else 'refused'} {run.calls} call{'s' if run.calls != 1 else ''} {secs:.1f} s"]
    if run.made:
        shown = run.made[:8]
        parts.append(" ".join(f"+{x}" for x in shown) + (f" +{len(run.made) - 8} more" if len(run.made) > 8 else ""))
    if v0 is not None and v1 is not None and abs(v1 - v0) > 1e-6:
        parts.append(f"vol {_fmt_num(v0)}→{_fmt_num(v1)} mm³")
    parts.append("clean" if not run.health_bad else f"health: {run.health_bad} not clean")
    return " · ".join(parts)


def fast_tool(server, session, a):
    """fast { do: [steps], check }: the block's answer (module docstring)."""
    if not enabled():
        raise off(FAST)
    steps = a.get("do")
    if isinstance(steps, str):
        try:
            steps = json.loads(steps)
        except ValueError:
            raise ToolError("invalid_input", "do came as a string that is not JSON: give a list of steps. Nothing was run.") from None
    if isinstance(steps, dict) and "do" in steps:
        steps = steps["do"]
    if not isinstance(steps, list) or not steps:
        raise ToolError("invalid_input", "do: a list of steps ({ call: tool, …fields }, { let }, { each }, { when }, { get } …). Nothing was run.")
    dry, stop = check(server, session, steps)
    if stop is not None:
        err = ToolError(stop.code, f"step {stop.where}{' (' + stop.tool + ')' if stop.tool else ''}: {_said(stop.words)} Read before step 1. Nothing was run.")
        err.outcome = "not_started"
        raise err
    if a.get("check"):
        out = {"fast": f"check ok: {dry.calls} call{'s' if dry.calls != 1 else ''}; leading checks read for {dry.read_checks} (the ones before the first change)"
                       + ". Nothing was run."}
        if dry.notes:
            out["notRead"] = dry.notes[:12]
        return out
    return _run(server, session, steps, a)


def _run(server, session, steps, a):
    from . import tools as T

    s = session
    budget = a.get("budget", T.BATCH_BUDGET)
    if isinstance(budget, bool) or not isinstance(budget, (int, float)) or not 1 <= budget <= T.BATCH_BUDGET_MAX:
        raise ToolError("invalid_input", f"budget: seconds this block may start calls for, 1 to {T.BATCH_BUDGET_MAX:g} ({T.BATCH_BUDGET:g} when left out). Nothing was run.")
    run = Run(server, s, budget=float(budget))
    start = s.doc
    _u0, names0 = T.undo_mark(start)
    try:
        import FreeCAD

        limit = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Document").GetInt("MaxUndoSize", 20)
        limit = int(limit) if isinstance(limit, int) else 20
    except Exception:  # noqa: BLE001
        limit = 20
    state = {"start": start, "made": 0, "own": [], "cp": None}
    from . import batchrec as _batchrec

    prev = getattr(s, "batch_now", None)
    record = _batchrec.BatchRecord(s.out_dir, 0, 0)
    record.head["fast"] = True
    try:
        from . import paths as _paths

        if record.path:
            _paths.made(s, record.path, "run")
    except Exception:  # noqa: BLE001
        pass
    record.write({"running": True, "results": []})
    mine = {"results": run.rows, "n": None, "i": 0, "tool": None, "answered": False, "names0": names0, "own": state["own"],
            "t0": _batchrec.clock_start(prev), "lastChange": None, "echoed": 0, "budget": float(budget), "first": 0, "total": None,
            "file": None, "record": record, "hold": None, "fast": True}
    run.mine = mine
    v0 = _volume(s)

    def on_call(where, tool, args):
        name = tool.name
        try:
            changing = bool(tool.for_call(args).changes_for(args))
        except Exception:  # noqa: BLE001
            changing = bool(getattr(tool, "changes", False))
        if changing:
            if state["start"] is not None and state["made"] >= limit:
                raise Stop(where, name, "invalid_input", f"past {limit} changing calls: FreeCAD keeps only {limit} undo steps, so the block could not be "
                                                         "taken back whole. Split it.")
            if state["cp"] is None:
                state["cp"] = _checkpoint(s) or False
        doc = s.doc
        u0 = T.undo_count(doc) or 0
        try:
            before = {o.Name for o in doc.Objects} if changing and doc is not None else None
        except Exception:  # noqa: BLE001
            before = None
        mine.update(i=run.calls - 1, tool=name)
        s.batch_now = mine
        r = server.call({"name": name, "arguments": copy.deepcopy(args)})
        try:
            body = json.loads(r["content"][0]["text"])
        except Exception:  # noqa: BLE001
            body = {}
        ok = not r.get("isError")
        start_now = state["start"]
        inc, start_now = T.own_steps(server, s, name, start_now, doc, u0, limit, mine, ok)
        state["start"] = start_now
        state["made"] += inc
        if ok and before is not None:
            run.note_made(before, name, args)
        row = {"step": where, "tool": name, "ok": ok, **({"result": body} if ok else {"error": body.get("error")})}
        run.rows.append(row)
        record.write({"running": True, "ran": len(run.rows), "results": run.rows})
        if not ok:
            err = body.get("error") or {}
            raise Stop(where, name, err.get("code", "failed"), err.get("message") or f"{name} was refused", body)
        hw = _health_words(body)
        if hw:
            run.health_bad += 1
            run.warnings.append(_cut(f"{where} ({name}) health: {hw}"))
        for k in ("warning", "warnings"):
            w = body.get(k) if isinstance(body, dict) else None
            if isinstance(w, str):
                run.warnings.append(_cut(f"{where} ({name}): {w}"))
            elif isinstance(w, list):
                run.warnings += [_cut(f"{where} ({name}): {x}") for x in w[:3]]
        return body

    run.on_call = on_call
    stop = None
    try:
        run.block(steps, "do")
    except Stop as e:
        stop = e
    finally:
        s.batch_now = prev
    secs = time.time() - run.t0
    rel = os.path.relpath(record.path, s.out_dir) if record.ok and record.path else None
    if stop is None:
        try:
            if s.doc is not None and s.doc is start:
                s.snapshot("fast block")
        except Exception:  # noqa: BLE001
            pass
        out = {"fast": _summary(run, True, secs, v0, _volume(s))}
        if run.values:
            out["values"] = run.values
        if run.warnings:
            out["warnings"] = run.warnings[:12]
        if run.filled:
            out["filled"] = list(dict.fromkeys(run.filled))[:12]
        if state["cp"]:
            out["checkpoint"] = state["cp"]
        if rel:
            out["record"] = rel
        record.write({**out, "results": run.rows}, final=True)
        return out
    # Refused: the block is taken back whole (batch's rollback).
    got = {}
    start = state["start"]
    if start is None:
        got = {"undone": 0, "outcome": "kept" if state["made"] else "not_started",
               "warning": "The document the block started in was closed during it: nothing to take back there."}
    else:
        got = T.roll_back(s, start, state["made"], mine.get("own"), names0, run.rows, label="block")
    words = [f"step {stop.where}{' (' + stop.tool + ')' if stop.tool else ''}: {_said(stop.words)}"]
    ran = sum(1 for r in run.rows if r.get("ok"))
    words.append(f"{ran} call{'s' if ran != 1 else ''} ran before it;"
                 f" the block was taken back ({got.get('undone', 0)} undo step{'s' if got.get('undone', 0) != 1 else ''})."
                 if got.get("outcome") in ("rolled_back", "not_started") else
                 f" {got.get('undone', 0)} of {state['made']} steps were taken back (outcome {got.get('outcome')}).")
    for k in ("warning", "rollbackNote"):
        if got.get(k):
            words.append(got[k])
    if got.get("removed"):
        words.append(f"Removed what undo did not reach: {', '.join(got['removed'][:8])}.")
    if rel:
        words.append(f"The record: {rel}.")
    err = ToolError(stop.code if stop.code in _CODES or stop.code == "busy" else "failed", " ".join(words))
    err.outcome = got.get("outcome") or "not_started"
    if got.get("outcome") in ("partial", "kept"):
        err.outcome_left = run.made
    record.write({"error": {"code": err.code, "message": err.message, "outcome": err.outcome}, "results": run.rows}, final=True)
    raise err


def _checkpoint(session):
    """One checkpoint before the block's first change, when an add-on
    offers checkpoints (its id), else None."""
    try:
        from . import hooks

        cps = hooks.service("checkpoints")
        if cps is None:
            return None
        got = cps.take(session, "before a fast block", auto=True)
        e = got[0] if isinstance(got, tuple) else got
        return e.get("id") if isinstance(e, dict) else None
    except Exception:  # noqa: BLE001
        return None
