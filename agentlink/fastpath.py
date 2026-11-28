# SPDX-License-Identifier: LGPL-2.1-or-later
"""The fast path (efficiency design C6, A6) and targeted reads (22 Nov).

The full answers and the guided workflow stay as they are. This is one more
way in, for an agent that already knows what it does:

  fast { calls: [steps] }   one call runs a list of steps, calls the tools
                            through the server's normal path, and answers
                            with one short line, not a full answer per call.
  get { what }              one value, with its unit: "Pad.Length",
                            "Body.volume", "Body.Edge7.length", "sketch.dof",
                            "active.body". A tool: a step of calls too.

A step is the same flat step as batch's (agentlink/callshape.py):

  { "tool": "pd_pad", "sketch": "Sketch", "length": 6 }
  { "tool": "sketch_add", "each": { "x": [15, 45] }, "kind": "circle", "center": ["$x", 0], "radius": 3 }
  { "tool": "pd_pad", "length": { "$from": 2, "$at": "height" } }

The tool's inputs stand beside tool. each runs the step once for each
value, in order ("$x" is the value). $from takes a value from the answer of
an earlier call (calls count from 0, each pass is one call). The only
difference to batch is the answer: one short answer here (its first key, result, lists the result line of each call that has one, in order), a full answer
for each call there. There are no other kinds of step: no variables, no
conditions, no expressions. Old forms ({ tool, arguments }, do, as, when,
let, try, choose) are refused with the new form in the words.

Safety of a block (the same as batch's where batch has it): every call goes
through the server's own path (input checks, field aliases, path guards,
each tool's leading checks and refusals, approvals, the co-work hold, the
undo step, the health); one checkpoint before the first change, when an
add-on offers checkpoints; a refusal keeps what ran before it, as batch
does, and with rollback: true rolls the block back with batch's rollback
(tools.roll_back), which stops at the person's own undo step; a record file like batch's (batches/…json); a dry
run (check: true) checks every step first and runs nothing. Before step 1
of a real run the same check runs (A6): a step that would be refused is
refused by its number before anything changes.

Plain Python: FreeCAD is reached through the tools and the session only.
"""
import copy
import json
import os
import re
import time

from . import callshape, chain
from . import resultline as _resultline
from .protocol import ToolError, check_input, compact, kinded, strip_kind

PREFS = "User parameter:BaseApp/Preferences/Mod/AgentLink"
PREF = "FastPath"
ENV = "AGENTLINK_FASTPATH"
OFF_CODE = "not_allowed"
FAST, GET = "fast", "get"

# What a block does not call: another runner, the person's own OK and
# settings, input to the window and its dialogs, jobs, the history (a block
# rolls back by undo), a restart. The same list as a cookbook script's
# (agentlink/cookbook.py SCRIPT_BLOCKED), and more.
BLOCKED = {"batch", FAST, "run", "job_start", "live_run", "app_restart", "app_force_restart", "agentlink_update", "pref_set", "pref_reset",
           "pref_import", "pref_pack", "app_extensions", "addon", "port_scaffold", "approve_file", "approve_code", "gui_input",
           "dialog_answer", "gui_unstick", "addon_test", "cookbook_run"}
# The history tools (by their prefix, the add-ons' too) do not run in a block:
# a block is taken back by undo. Only the reading of the history does.
READ_HISTORY = {"history_diff"}
MAX_STEPS = 2000      # steps a block may take (a loop's steps each count)
MAX_CALLS = 200       # tool calls a block may make
MAX_DRY_CALLS = 400   # calls a check reads before it stops reading
WORDS = 240           # a warning's or refusal's words in the answer

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


# ---- targeted reads ----------------------------------------------------------------------------

ACTIVE = ("active.body", "active.sketch", "active.document", "selection", "bodies")
SHAPE = {"volume": ("measure", "volume", "mm³"), "area": ("measure", "area", "mm²"), "size": ("measure", "size", "mm"),
         "min": ("measure", "min", "mm"), "max": ("measure", "max", "mm"),
         "mass": ("measure_mass", "mass", "g"), "centerOfMass": ("measure_mass", "centerOfMass", "mm"),
         "density": ("measure_mass", "density", "g/cm³"), "inertia": ("measure_mass", "inertia", "g·mm²")}
# Readings of a body's check, not of get (body_check gives them).
CHECK_WORDS = {"solids", "solid", "valid", "isvalid", "closed"}
SKETCH = {"dof": None, "closedWires": None, "openVertices": None, "wires": None, "points": None, "wiresMeet": None, "conflicting": None, "redundant": None,
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
        tool = f" If {w} is a tool, run it as a step: {{ \"tool\": \"{w}\" }}." if len(parts) == 1 and "_" in w else ""
        return f"what {w!r}: an object and what to read of it, \"Object.Property\" (\"Pad.Length\", \"Body.volume\"), or one of {', '.join(ACTIVE)}.{tool}"
    return None


GEOMETRY_UNITS = ("mm", "mm²", "mm³")


def _fmt_num(v, unit="mm³"):
    """A number in plain notation, never 1.405e+04 (24 Nov blind QA: get
    and pd_pad gave the same volume two ways). A length, area or volume as
    the feature answers give it: 2 decimals from 1 up (14053.65); else, and
    below 1, 4 decimals (1.886 g, 0.0123 mm)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return v
    f = float(v)
    if f != f or f in (float("inf"), float("-inf")):
        return str(f)
    places = 2 if unit in GEOMETRY_UNITS and abs(f) >= 1 else 4
    r = round(f, places)
    if r == int(r) and abs(r) < 1e15:
        return str(int(r))
    return f"{r:.{places}f}".rstrip("0").rstrip(".")


def with_unit(v, unit):
    """A value as get answers it: a number with its unit ("1520 mm³"), a
    list of numbers with it after ("[1, 2, 3] mm"), anything else as it is."""
    if unit is None:
        return v
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return f"{_fmt_num(v, unit)} {unit}"
    if isinstance(v, list) and v and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
        return f"[{', '.join(str(_fmt_num(x, unit)) for x in v)}] {unit}"
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
            # Name real ones, never the request turned round (24 Nov QA: it
            # answered Name it: "Sketch.dof,HollowSketch" to "sketch.dof,HollowSketch").
            try:
                have = ([o.Label for o in session.bodies()] if parts[0] == "body" else
                        [o.Label for o in getattr(doc, "Objects", ()) if getattr(o, "TypeId", "") == "Sketcher::SketchObject"])
            except Exception:  # noqa: BLE001
                have = []
            prop = re.split(r"[^A-Za-z0-9_]", parts[1])[0] if len(parts) > 1 and parts[1] else ""
            named = ", ".join(f"{x}.{prop}" if prop else x for x in have[-4:][::-1])
            raise ToolError("not_found", f"{w}: no current {parts[0]} (none made or named by a block, none active, not just one in the document). "
                                         + (f"Name the {parts[0]} by its label, then the property: {named}." if have else f"There is no {parts[0]} in the document."))
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
    if head.lower() in CHECK_WORDS and hasattr(o, "Shape") and not _has_prop(o, head):
        # 26 Nov QA: get Body.solids and Body.valid were sent to object_get,
        # which does not give them either.
        raise ToolError("not_found", f"{w}: get does not read {head}. body_check {{ body: \"{o.Label}\" }} gives solids, valid and closed "
                                     f"(with volume and box); get gives {o.Label}.volume, .area and .size.")
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
        self.kind = None  # the step's own refusal kind (protocol.refusal_kind), when it had one


# ---- the run ------------------------------------------------------------------------------------

class Run:
    """One block, run (dry False) or checked (dry True: nothing is called,
    each call's tool, fields and, before the first change, leading checks
    are read)."""

    def __init__(self, server, session, dry=False, budget=None):
        self.server, self.s, self.dry = server, session, dry
        self.steps_taken = 0
        self.calls = 0           # the calls so far: also the number of the next one
        self.rows = []           # each call: {step, tool, ok, result | error}
        self.answers = {}        # call index -> { ok, tool, answer, size }: what $from takes from
        self.values = {}
        self.warnings = []
        self.filled = []
        self.made = []           # labels of what the block made
        self.made_rows = []      # {name, label, type} of the same: the names later calls take
        self.checks = []         # the key results of check, save and close steps
        self.health_bad = 0
        self.health_first = None
        self.changed = False     # a changing call came before (dry: leading checks stop counting)
        self.notes = []          # dry: what was not read
        self.read_checks = 0
        self.mine = None         # the run's batch_now (set by the caller of a real run)
        self.on_call = None      # the real call: on_call(where, tool, args) -> body
        self.block_ctx = {}      # what this block made or named: body, sketch
        self.t0 = time.time()
        self.budget = budget

    # steps
    def block(self, steps):
        for st in steps:
            self.step(st)

    def step(self, st):
        """One step of calls: its calls are made in order (each: once for
        each value). A step with a wrong form stops the block."""
        self.steps_taken += 1
        where = f"calls.{self.calls}"
        if self.steps_taken > MAX_STEPS:
            raise Stop(where, None, "invalid_input", f"the block took more than {MAX_STEPS} steps: split it.")
        try:
            parts = callshape.steps_of(self.server, st, where, runner="fast")
        except callshape.Refused as e:
            name = st.get("tool") if isinstance(st, dict) and isinstance(st.get("tool"), str) else None
            raise Stop(where, name, "invalid_input", e.words) from None
        for p in parts:
            self.call(p["tool"], p["inputs"], f"calls.{self.calls}")
            if self.dry and self.calls > MAX_DRY_CALLS:
                return

    # a call
    def call(self, name, args, where):
        server = self.server
        tool = server.tools.get(name)
        if tool is None:
            import difflib

            near = difflib.get_close_matches(str(name), list(server.tools), n=3, cutoff=0.5)
            raise Stop(where, name, "not_found", f"{name}: no such tool{' — near: ' + ', '.join(near) if near else ''} (tool_find finds tools).")
        if name in BLOCKED or getattr(tool, "alias_of", None) in BLOCKED or (name.startswith("history_") and name not in READ_HISTORY):
            raise Stop(where, name, "refused", f"{name} does not run in a fast block (another runner, the person's OK or settings, the window's "
                                               "input and dialogs, jobs, the history or a restart): call it on its own.")
        idx = self.calls
        args = self.refs(args, where, name, idx)
        self.calls += 1
        if self.calls > MAX_CALLS and not self.dry:
            raise Stop(where, name, "invalid_input", f"more than {MAX_CALLS} calls in one block: split it.")
        if self.dry:
            self._dry_call(tool, args, where)
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
        self.on_call(where, tool, args)

    def refs(self, args, where, name, idx):
        """args with each { "$from": n, "$at": path } put at the answer of
        call n (the same code as batch's). A check cannot know the answer:
        it reads the form and gives UNKNOWN. $file is batch's only."""
        if not chain.has_refs(args):
            return args
        try:
            if self.dry:
                return _unknown_refs(args, idx)
            return chain.resolve(args, _no_file, self.answers, idx, 0)
        except chain.Miss as e:
            raise Stop(where, name, e.code, e.message) from None

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
            self.made_rows.append({"name": o.Name, "label": o.Label, "type": t.split("::")[-1]})
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

    def _dry_call(self, tool, args, where):
        name = tool.name
        if self.calls > MAX_DRY_CALLS:
            if len(self.notes) < 40:
                self.notes.append(f"{where}: past {MAX_DRY_CALLS} calls the check reads no more")
            return
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
            raise Stop(where, name, e.code, e.message) from None
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
                    raise Stop(where, name, x.get("code", "invalid_input"), _said(x.get("words")) + " That is its leading check.")
            except Stop:
                raise
            except Exception:  # noqa: BLE001 - a reading is advice; it never stops a block by failing
                pass
        if changing:
            self.changed = True
        if changing and name in ("sketch_new", "pd_body_new"):
            # Made by the block: its name is known only when it runs.
            self.block_ctx["sketch" if name == "sketch_new" else "body"] = UNKNOWN


def _no_file(name):
    raise chain.Miss("invalid_input", "$file: a file is read in batch only. fast takes { \"$from\": n, \"$at\": path }, "
                                      "the answer of an earlier call of this block.")


def _unknown_refs(v, idx):
    """v with each reference put at UNKNOWN, after its form is read (a
    check knows no answers): { "$from": n } with n an earlier call."""
    if chain.is_ref(v):
        if chain.FILE in v:
            _no_file(v[chain.FILE])
        extra = sorted(k for k in v if k not in (chain.FROM, chain.AT))
        if extra:
            raise chain.Miss("invalid_input", f"{{ $from }} takes only $at beside it, not {', '.join(extra)}.")
        n = v[chain.FROM]
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise chain.Miss("invalid_input", f"$from: the index of an earlier call of this block (calls are numbered from 0), not {n!r}.")
        if n >= idx:
            raise chain.Miss("invalid_input", f"$from: {n} is not before this call (calls.{idx}): a call takes only an earlier call's answer.")
        return UNKNOWN
    if isinstance(v, dict):
        return {k: _unknown_refs(x, idx) for k, x in v.items()}
    if isinstance(v, list):
        return [_unknown_refs(x, idx) for x in v]
    return v


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


def _volume(session, doc=None):
    """The shown bodies' volume of doc (the session's document when left out)."""
    try:
        from .tools import Session

        d = doc if doc is not None else session.doc
        return sum(float(o.Shape.Volume) for o in Session.bodies_in(d))
    except Exception:  # noqa: BLE001
        return None


def _open(doc):
    """Whether doc is still an open document."""
    try:
        import FreeCAD

        return doc is not None and any(d is doc for d in FreeCAD.listDocuments().values())
    except Exception:  # noqa: BLE001
        return False


# The key fields of a check, save or close step, given in the block's answer
# (live, 22 Nov: an agent spent a call reading the record for body_check's
# verdict and the save's result).
CHECK_KEYS = {
    "body_check": ("body", "valid", "closed", "solids", "volume", "box", "checkGeometry"),
    "doc_save": ("path", "bytes"),
    "doc_close": ("closed", "discarded"),
    "measure": ("value", "unit", "distance", "angle"),
}


def check_row(where, tool, body):
    """A short row of a check step's answer, or None."""
    # Any other *_check tool (an add-on's): its verdict and findings.
    keys = CHECK_KEYS.get(tool) or (("ok", "valid", "findings", "problems") if tool.endswith("_check") else None)
    if not keys or not isinstance(body, dict):
        return None
    row = {"step": where, "tool": tool}
    for k in keys:
        if k in body:
            v = body[k]
            row[k] = len(v) if k in ("problems", "findings") and isinstance(v, list) else v
    return row


def _health_words(body):
    """The health's fields of a call whose health has a fault that FreeCAD
    reports (health.fault_in: a recompute error new or from before, a shape
    that is not valid or not closed, flagged constraints, a dialog) or that
    was not read, as compact JSON; else None."""
    import json

    from . import health as _h
    from . import once

    h = body.get("health") if isinstance(body, dict) else None
    if isinstance(h, dict) and _h.fault_in(h):
        return _cut(json.dumps({k: v for k, v in h.items() if k not in once.HEALTH_ASIDE}, default=str, ensure_ascii=False, separators=(",", ":")))
    return None


# ---- the checks before step 1 (A6) ---------------------------------------------------------------

def check(server, session, steps):
    """The dry run: (the run, None) when every step reads as fine, or
    (the run, Stop) at the first that would be refused."""
    run = Run(server, session, dry=True)
    try:
        run.block(steps)
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
    parts = [f"{'ran' if ok else 'refused'} {run.calls} call{'s' if run.calls != 1 else ''} {secs:.1f} s"]
    if run.made:
        shown = run.made[:8]
        parts.append(" ".join(f"+{x}" for x in shown) + (f" +{len(run.made) - 8} more" if len(run.made) > 8 else ""))
    if v0 is not None and v1 is not None and abs(v1 - v0) > 1e-6:
        parts.append(f"vol {_fmt_num(v0)}→{_fmt_num(v1)} mm³")
    # What the calls' own health readings say: no claim for a reading that is not there (27 Nov review, A1).
    # Which of the two, in the health's own words (s1127e QA, H12: "a fault or
    # no reading" did not say which): the first, then how many in warnings.
    first = getattr(run, "health_first", None)
    parts.append((f"health: {_cut(first, 200)}" + (f" ({run.health_bad} calls with such health; warnings has each)" if run.health_bad > 1 else ""))
                 if run.health_bad and first else
                 f"health: a fault or no reading after {run.health_bad} call{'s' if run.health_bad != 1 else ''} (warnings)" if run.health_bad
                 else "health: no fault in the readings of the calls")
    return " · ".join(parts)


def fast_tool(server, session, a):
    """fast { calls: [steps], check }: the block's answer (module docstring)."""
    if not enabled():
        raise off(FAST)
    steps = a.get("calls")
    if "do" in a and steps is None:
        raise ToolError("invalid_input", callshape.old_words("do", "calls"))
    if isinstance(steps, str):
        try:
            steps = json.loads(steps)
        except ValueError:
            raise ToolError("invalid_input", "calls came as a string that is not JSON: give a list of steps. Nothing was run.") from None
    if not isinstance(steps, list) or not steps:
        raise ToolError("invalid_input", f"calls: a list of steps, {callshape.EXAMPLE}. Nothing was run.")
    dry, stop = check(server, session, steps)
    if stop is not None:
        from .protocol import note_refused

        note_refused(server, str(stop.tool or "fast"), stop.code, f"fast, in the check before step 1, at {stop.where}; nothing was run")
        err = ToolError(stop.code, f"step {stop.where}{' (' + stop.tool + ')' if stop.tool else ''}: {_said(stop.words)} Read before step 1. Nothing was run.")
        err.outcome = "not_started"
        raise err
    if a.get("check"):
        out = {"fast": f"check: no refusal found: {dry.calls} call{'s' if dry.calls != 1 else ''}; leading checks read for {dry.read_checks} (the ones before the first change)"
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
    # A refused call keeps what ran before it (the default, as batch does:
    # owner, 23 Nov); rollback: true takes the block back whole.
    rollback = a.get("rollback") is True
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
    vol_doc = s.doc
    v0 = _volume(s, vol_doc)

    def on_call(where, tool, args):
        name = tool.name
        try:
            changing = bool(tool.for_call(args).changes_for(args))
        except Exception:  # noqa: BLE001
            changing = bool(getattr(tool, "changes", False))
        if changing:
            if rollback and state["start"] is not None and state["made"] >= limit:
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
        if ok and isinstance(body, dict) and isinstance(body.get("filled"), list):
            # A sketch the tool took when none was named (pd_common.sketch_of).
            run.filled += [str(x) for x in body["filled"]]
        row = {"step": where, "tool": name, "ok": ok, **({"result": body} if ok else {"error": kinded(body.get("error"))})}
        run.rows.append(row)
        record.write({"running": True, "ran": len(run.rows), "results": run.rows})
        if not ok:
            err = body.get("error") or {}
            st = Stop(where, name, err.get("code", "failed"), strip_kind(err.get("message")) or f"{name} was refused", body)
            st.kind = err.get("kind")
            raise st
        run.answers[run.calls - 1] = {"ok": True, "tool": name, "answer": body, "size": len(r["content"][0]["text"])}
        if name == "get" and isinstance(body, dict):
            # get's values are in the answer's values (a read of one value).
            what = args.get("what")
            for w in [what] if isinstance(what, str) else (what if isinstance(what, list) else []):
                if isinstance(w, str) and w.strip() in body:
                    run.values[w.strip()] = body[w.strip()]
        cr = check_row(where, name, body)
        if cr:
            run.checks.append(cr)
        hw = _health_words(body)
        if hw:
            run.health_bad += 1
            if not getattr(run, "health_first", None):
                run.health_first = f"{where} ({name}): {hw}"
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
        run.block(steps)
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
        # The volume change of the document it was first read on, while that
        # one is open (live, 22 Nov: a block that saved and closed its
        # document reported the volume of the person's other document).
        v1 = _volume(s, vol_doc) if _open(vol_doc) else None
        # One record for each call that ran, in order, first: the short answer's
        # body (protocol.step_line: call, tool, object, volumeChange, historyStep …).
        steps = _resultline.fast_steps([(r["step"], r["tool"], r.get("result")) for r in run.rows if r.get("ok")])
        out = {**({"result": steps} if steps else {}), "fast": _summary(run, True, secs, v0, v1)}
        if run.made_rows:
            out["made"] = run.made_rows[:40]
        if run.checks:
            out["checks"] = run.checks[:12]
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
    # Refused: what ran stays and the answer says where to go on (the
    # default), or with rollback: true the block is taken back whole.
    got = {}
    start = state["start"]
    ran_rows = [r for r in run.rows if r.get("ok")]
    if not rollback and ran_rows:
        words = [f"step {stop.where}{' (' + stop.tool + ')' if stop.tool else ''}: {_said(stop.words)}",
                 "Ran before it: " + ", ".join(f"{r['step']} {r['tool']}" for r in ran_rows[:12]) + (" …" if len(ran_rows) > 12 else "") + ".",
                 f"What ran before it stays, each its own undo step: {len(ran_rows)} call{'s' if len(ran_rows) != 1 else ''}"
                 + (f", made {', '.join(r['label'] + ' (' + r['name'] + ')' for r in run.made_rows[:12])}" if run.made_rows else "")
                 + f". Go on from step {stop.where} in a new block."]
        if rel:
            words.append(f"The record: {rel}.")
        err = ToolError(stop.code if stop.code in _CODES or stop.code == "busy" else "failed", " ".join(words))
        err.kind = stop.kind
        err.outcome = "kept"
        err.outcome_left = run.made
        record.write({"error": {"code": err.code, "message": err.message, "status": "kept"}, "results": run.rows}, final=True)
        raise err
    if start is None:
        got = {"undone": 0, "result": "kept" if state["made"] else "ran_none",
               "warning": "The document the block started in was closed during it: nothing to take back there."}
    else:
        got = T.roll_back(s, start, state["made"], mine.get("own"), names0, run.rows, label="block")
    words = [f"step {stop.where}{' (' + stop.tool + ')' if stop.tool else ''}: {_said(stop.words)}"]
    ran = sum(1 for r in run.rows if r.get("ok"))
    if ran_rows:
        # What ran before the refusal, by step, so the next block can be the
        # same steps with the one fixed (live, 22 Nov: an agent rebuilt it all).
        words.append("Ran before it: " + ", ".join(f"{r['step']} {r['tool']}" for r in ran_rows[:12]) + (" …" if len(ran_rows) > 12 else "") + ".")
    words.append(f"{ran} call{'s' if ran != 1 else ''} ran before it;"
                 f" the block was taken back ({got.get('undone', 0)} undo step{'s' if got.get('undone', 0) != 1 else ''})."
                 if got.get("result") in ("rolled_back", "ran_none") else
                 f" {got.get('undone', 0)} of {state['made']} steps were taken back (result {got.get('result')}).")
    for k in ("warning", "rollbackNote"):
        if got.get(k):
            words.append(got[k])
    if got.get("removed"):
        words.append(f"Removed what undo did not reach: {', '.join(got['removed'][:8])}.")
    if rel:
        words.append(f"The record: {rel}.")
    err = ToolError(stop.code if stop.code in _CODES or stop.code == "busy" else "failed", " ".join(words))
    err.kind = stop.kind
    err.outcome = {"ran_none": "not_started"}.get(got.get("result"), got.get("result")) or "not_started"
    if got.get("result") in ("partial", "kept"):
        err.outcome_left = run.made
    record.write({"error": {"code": err.code, "message": err.message, "status": err.outcome}, "results": run.rows}, final=True)
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
