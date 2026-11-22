# SPDX-License-Identifier: LGPL-2.1-or-later
# The Model Context Protocol, as much as a tool server needs: JSON-RPC 2.0,
# one message a line (the stdio framing), initialize, tools/list,
# tools/call and ping. No dependencies, so it runs in FreeCAD's own Python
# (FreeCADCmd, the GUI) as well as a plain interpreter — nothing to install
# into an application bundle.

import json
import math
import os
import sys
import threading
import time
import traceback

PROTOCOL = "2025-06-18"
# How text that UTF-8 cannot hold (a lone surrogate, from a file name or an
# add-on's text) is written on the wire: as a backslash escape. Inside a JSON
# string that is a valid \uXXXX escape, so the line still goes out and parses;
# "strict" failed the write and the call had no answer.
WIRE_ERRORS = "backslashreplace"




def _docs_open():
    try:
        import FreeCAD

        return set(FreeCAD.listDocuments())
    except Exception:
        return None


def _settled(fn):
    """fn run, then any document it opened from a copy in a temporary folder
    (a recovered copy, a checkpoint opened beside its file) marked
    unchanged, on the thread that ran it (store.settle_opened says why)."""
    before = _docs_open()
    out = fn()
    if before is not None:
        try:
            from .store import settle_copies

            settle_copies(before)
        except Exception:
            pass
    return out

def _with_health(session, tool, args):
    """tool.fn(args) with the shared health check round it; a health module
    that will not load or run leaves the answer as the tool gave it."""
    from . import around

    try:
        from . import health

        with around.part("healthMark"):
            m = health.mark(session)
    except Exception:
        return tool.fn(args)
    try:
        out = tool.fn(args)
    except BaseException:
        health.drop(m)
        raise
    with around.part("health"):
        return health.attach(session, tool, m, out)


class ToolError(Exception):
    """A refusal the agent can act on: a code (invalid_input, not_found,
    failed) and a message that says what to do next."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


# What runs while a dialog or menu holds the window: the calls that act on
# it (they take only targets inside it), and a picture of the window.
FRONT_CALLS = ("dialog_answer", "gui_input", "gui_unstick")
FRONT_READS = ("window_snapshot",)
# Reads that may share a batch with a FRONT_CALLS tool while a dialog holds
# the window (live 56b: a batch of gui_input and sketch_state was refused
# "Blocked by a dialog"). They change nothing and need no event loop of
# their own: they run inside the dialog's loop, after the gui_input steps
# before them (so they read what those steps did, the dialog closed or
# not). A tool by name, or any tool whose name ends in one of
# DIALOG_READ_ENDS. Changes stay refused while a dialog is up.
DIALOG_READS = ("session_state", "tool_find", "tool_groups", "job_status", "usage_report")
DIALOG_READ_ENDS = ("_state", "_list", "_get", "_read")


def dialog_read(name):
    """True for a read that may run in a batch beside FRONT_CALLS while a
    dialog holds the window (DIALOG_READS, DIALOG_READ_ENDS)."""
    return isinstance(name, str) and name != "batch" and (name in FRONT_READS or name in DIALOG_READS or name.endswith(DIALOG_READ_ENDS))


def _as_json(v):
    """v, or the value of v when it came as a string of its JSON (some
    clients send a large value so: batch's calls, a call, its arguments)."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return None
    return v


def batch_calls(args):
    """The (tool, arguments) of a batch's calls, read as batch reads them
    (calls, a call or the arguments as a string of JSON); None when they
    cannot be read, or for a batch from a file."""
    args = _as_json(args)
    if not isinstance(args, dict) or args.get("file") is not None:
        return None
    calls = _as_json(args.get("calls"))
    if isinstance(calls, dict):
        calls = calls.get("calls")
    if not isinstance(calls, list):
        return None
    out = []
    for c in calls:
        c = _as_json(c)
        if not isinstance(c, dict) or not isinstance(c.get("tool"), str):
            return None
        a = _as_json(c.get("arguments"))
        out.append((c["tool"], a if isinstance(a, dict) else {}))
    return out


def batch_tools(args):
    """The tool names of a batch's calls (batch_calls), or None."""
    calls = batch_calls(args)
    return None if calls is None else [t for t, _a in calls]


def front_call(name, args, read_ok=None, declared=None):
    """True for a call that runs while a dialog or menu holds the window: a
    FRONT_CALLS tool, FRONT_READS alone (window_snapshot draws the menu or
    dialog over the window), or a batch with at least one FRONT_CALLS tool
    whose other calls are FRONT_READS or dialog reads (dialog_read; a lean
    client reaches gui_input through batch). declared(tool, arguments),
    when given, lets through a call that its tool's data declares a front
    read (frontReads: an add-on tool's status action, live 56c). read_ok(tool,
    arguments), when given, must also pass for each read (the window checks
    there that the call changes nothing and is not a heavy read)."""
    if name in FRONT_CALLS or name in FRONT_READS:
        return True
    if name != "batch":
        return False
    calls = batch_calls(args)
    if not calls or not any(t in FRONT_CALLS for t, _a in calls):
        return False
    for t, a in calls:
        if t in FRONT_CALLS or t in FRONT_READS:
            continue
        if not dialog_read(t):
            try:
                if declared is None or not declared(t, a):
                    return False
            except Exception:  # noqa: BLE001 - not known: not let through
                return False
        if read_ok is not None:
            try:
                if not read_ok(t, a):
                    return False
            except Exception:  # noqa: BLE001 - not known: not let through
                return False
    return True


def bad(msg):
    """The usual refusal: invalid_input with msg."""
    return ToolError("invalid_input", msg)


class Tool:
    def __init__(self, name, description, schema, fn, changes=False, group="core", reads=None, activity=None, front_reads=None):
        self.name = name
        # The calls that may run beside gui_input while a dialog or menu
        # holds the window (front_call): {argument: [values]}, {} for every
        # call; None for none. Declared in the tool's data (frontReads).
        self.front_reads = None if front_reads is None else dict(front_reads)
        self.description = description
        self.schema = schema
        self.fn = fn
        # A change runs as one undo step (the session wraps it in a
        # transaction); a read changes nothing.
        self.changes = changes
        # The calls of a changing tool that only read: {argument: [values]}
        # (setup's action list or of). Such a call is no undo step, marks
        # nothing changed and is not shown as a change (for_call).
        self.reads = dict(reads or {})
        # Its group: listed when the group is on (tool_groups), callable
        # by name whether listed or not.
        self.group = group
        # What a call did, in the Activity tab's words: a template or a list
        # of them ("Sliced {object}"; agentlink/activity.py), or None for
        # the shared table's.
        self.activity = activity

    def front_read(self, args):
        """Whether this call is a front read its data declares (frontReads):
        it changes nothing and may run inside a dialog's or menu's loop."""
        if self.front_reads is None or self.changes_for(args):
            return False
        a = args if isinstance(args, dict) else {}
        for k, values in self.front_reads.items():
            v = a.get(k, ((self.schema or {}).get("properties") or {}).get(k, {}).get("default"))
            if v not in values:
                return False
        return True

    def changes_for(self, args):
        """Whether this call changes the document."""
        if not self.changes:
            return False
        a = args if isinstance(args, dict) else {}
        for k, values in self.reads.items():
            # An argument left out takes its schema's default, if it has one.
            v = a.get(k, ((self.schema or {}).get("properties") or {}).get(k, {}).get("default"))
            if v in values:
                return False
        return True

    def for_call(self, args):
        """This tool as this call sees it: a read-only view when the call
        only reads."""
        if self.changes and not self.changes_for(args):
            import copy

            view = copy.copy(self)
            view.changes = False
            return view
        return self

    def listing(self):
        return {"name": self.name, "description": self.description, "inputSchema": self.schema}


SYNONYMS = {
    "centre": ("center",), "center": ("centre",), "colour": ("color",), "color": ("colour",),
    "body": ("object", "part"), "object": ("body",), "part": ("body", "object"),
    "bodies": ("objects", "parts"), "objects": ("bodies",), "parts": ("bodies", "objects"),
    "file": ("path",), "filename": ("path", "file"), "path": ("file",),
}


# Fields an agent often gives one tool by another name (seen in the usage
# log's refusals, efficiency design C2, 22 Nov): per tool, the field given and
# the field the tool has. Taken as that field when it is not given, and said
# in the answer's readAs. The cards do not change.
FIELD_ALIASES = {
    "object_set": {"set": "values", "properties": "values", "props": "values"},
    "varset_set": {"values": "properties", "set": "properties"},
    "varset_new": {"values": "properties"},
    "doc_close": {"document": "documents", "name": "documents"},
    "doc_open": {"file": "path", "document": "path"},
    "object_get": {"properties": "filter", "property": "filter", "names": "filter"},
    "object_delete": {"object": "objects", "name": "objects"},
    "shape_query": {"object": "body"},
}


def _as_alias(spec, v):
    """A value given under an alias, in the shape of the field it is read as:
    one name for a list field, a list of names for a filter."""
    t = spec.get("type") if isinstance(spec, dict) else None
    if t == "array" and not isinstance(v, list):
        return [v]
    if not t and isinstance(v, list) and all(isinstance(x, str) for x in v):
        return "|".join(v)
    return v


def check_input(schema, args, tool=None):
    """Unknown keys and missing required ones refused by name, as the
    answers name them: what the agent got wrong and what is allowed.
    Answers the aliases read (FIELD_ALIASES), as "given as field" words."""
    if not isinstance(args, dict):
        raise ToolError("invalid_input", "arguments: an object.")
    props = schema.get("properties", {})
    read_as = []
    for k, alt in (FIELD_ALIASES.get(tool) or {}).items():
        if k in args and k not in props and alt in props and alt not in args:
            args[alt] = _as_alias(props.get(alt), args.pop(k))
            read_as.append(f"{k} as {alt}")
    # The same thing by another common name (centre for center, body for
    # object …): taken as the field the tool has, when that one is not given.
    for k in [k for k in args if k not in props]:
        alt = next((s for s in SYNONYMS.get(k, ()) if s in props and s not in args), None)
        if alt is not None:
            args[alt] = args.pop(k)
    unknown = [k for k in args if k not in props]
    if unknown and schema.get("additionalProperties") is False:
        raise ToolError("invalid_input", f"input.{unknown[0]}: not a known field — the fields here: {', '.join(props) or 'none'}")
    for k in schema.get("required", []):
        if k not in args:
            raise ToolError("invalid_input", f"input.{k}: required.")
    for k, v in list(args.items()):
        spec = props.get(k)
        if isinstance(spec, dict) and v is not None:
            args[k] = _typed(f"input.{k}", spec, v)
    return read_as


_PY = {"string": (str,), "number": (int, float), "integer": (int,), "boolean": (bool,), "array": (list,), "object": (dict,)}


def _typed(where, spec, v):
    """A value checked against its field's type and enum — and coerced where
    a client sent the same thing in another dress: a number or a boolean as
    a string, a list or an object as a string of its JSON."""
    t = spec.get("type")
    if isinstance(t, str) and t in _PY:
        ok = isinstance(v, _PY[t]) and not (t in ("number", "integer") and isinstance(v, bool))
        if ok and isinstance(v, float) and not math.isfinite(v):
            ok = False
        if not ok and isinstance(v, str):
            text = v.strip()
            try:
                if t == "number":
                    v, ok = float(text), True
                    if not math.isfinite(v):
                        ok = False
                elif t == "integer" and text.lstrip("-").isdigit():
                    v, ok = int(text), True
                elif t == "boolean" and text.lower() in ("true", "false"):
                    v, ok = text.lower() == "true", True
                elif t in ("array", "object"):
                    parsed = json.loads(text)
                    if isinstance(parsed, _PY[t]):
                        v, ok = parsed, True
            except ValueError:
                pass
        if not ok and t == "number" and isinstance(v, int) and not isinstance(v, bool):
            ok = True
        if not ok and t == "integer" and isinstance(v, float) and v.is_integer():
            v, ok = int(v), True
        if not ok:
            raise ToolError("invalid_input", f"{where}: {_said(t)}, not {_kind(v)}.")
    if "enum" in spec and v not in spec["enum"]:
        lowered = {str(e).lower(): e for e in spec["enum"]}
        if isinstance(v, str) and v.lower() in lowered:
            return lowered[v.lower()]
        raise ToolError("invalid_input", f"{where}: one of {', '.join(map(str, spec['enum']))} — not {v!r}.")
    return v


def _said(t):
    return {"string": "text", "number": "a number", "integer": "a whole number", "boolean": "true or false", "array": "a list", "object": "an object"}[t]


def _kind(v):
    if isinstance(v, bool):
        return "true/false"
    return {str: "text", int: "a number", float: "a number", list: "a list", dict: "an object"}.get(type(v), type(v).__name__)


MAX_REPLY = 60_000  # characters: a reply past this costs the agent's context more than it tells


def trim(out, limit):
    """A reply cut to fit: its longest lists shortened (the count kept in
    truncated), longest first, until the whole fits."""
    cut = {}

    def lists(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                yield from lists(v, path + [k])
        elif isinstance(o, list):
            yield path, o
            for i, v in enumerate(o[:50]):
                yield from lists(v, path + [i])

    for _ in range(40):
        if len(compact(out)) <= limit:
            break
        # a batch's results are each a call's answer: shortened inside, never dropped
        found = [(len(compact(l)), p, l) for p, l in lists(out, []) if len(l) > 4 and p[-1:] != ["results"]]
        if not found:
            break
        size, path, l = max(found, key=lambda x: x[0])
        keep = max(4, len(l) // 2)
        parent = out
        for k in path[:-1]:
            parent = parent[k]
        name = ".".join(map(str, path))
        cut.setdefault(name, len(l))
        parent[path[-1]] = l[:keep]
    if cut:
        out["truncated"] = {k: f"{v} items, the first shown — ask for fewer (a filter, a range) to see the rest" for k, v in cut.items()}
    return out


def _finite(o):
    """NaN and infinities as null: JSON has no such numbers, and a client's
    parser (Node's JSON.parse) refuses the whole reply when Python writes
    them."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _finite(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_finite(v) for v in o]
    return o


def _plain(o):
    """What json does not know, as its plain value: a numpy number or bool
    (a tool's own arithmetic) by .item(), a set as a list, anything else as
    text. One numpy bool in one answer failed a whole batch's reply
    ("Object of type bool_ is not JSON serializable")."""
    item = getattr(o, "item", None)
    if callable(item):
        try:
            v = item()
            if isinstance(v, (bool, int, float, str)) or v is None:
                return v
        except Exception:
            pass
    tolist = getattr(o, "tolist", None)
    if callable(tolist):
        try:
            return tolist()
        except Exception:
            pass
    if isinstance(o, (set, frozenset)):
        return sorted(o, key=str)
    return str(o)


def compact(obj):
    try:
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=_plain)
    except ValueError:
        return json.dumps(_finite(json.loads(json.dumps(obj, default=_plain))), separators=(",", ":"), ensure_ascii=False, allow_nan=False)



def _outcome(tool, exc):
    """A refusal's outcome for a changing call: what Session.execute put on
    the error (changes.mark_outcome), else not_started (it was refused before
    any change began: input, guards, a job check). None for a read."""
    got = getattr(exc, "outcome", None)
    if got:
        return got
    try:
        if tool is not None and tool.changes and tool.name != "batch":
            return "not_started"
    except Exception:
        pass
    return None


# Refusal codes that mean "not now", not "not so": the same call may go
# through a moment later. Only the link's own busy answer is one today.
TRANSIENT = {"busy"}


def retry_once_ok(changes, err):
    """True when the link may send a refused call again once by itself
    (E10): a read refused for a transient cause, or a changing call refused
    for one before it began (outcome not_started). Never a changing call
    whose outcome is unknown or anything else: it may have changed the
    document already."""
    if not isinstance(err, dict) or err.get("code") not in TRANSIENT:
        return False
    if not changes:
        return True
    return err.get("outcome") == "not_started"


def failed_words(name, e):
    """A tool's own failure as a sentence. A bare KeyError said only the
    key ("asm_joint failed: 'M8x25-Screw219'"): it is an object or entry
    looked up by a name that is no longer there."""
    if isinstance(e, KeyError):
        key = e.args[0] if e.args else "?"
        return (f"{name} failed: it looked up {key!r} and found nothing by that name — an object renamed or removed while it ran "
                "(a workbench that relabels its objects on recompute does this). Nothing was kept; session_state or asm_list gives the names as they are now.")
    if "invalid bounding box" in str(e):
        # FreeCAD's own words for measuring something with no shape: a view
        # whose source has no solid, an empty body (td_dim on such a view
        # said only "Cannot determine diagonal length of invalid bounding box").
        return (f"{name} failed: what it measured has no shape (FreeCAD: {e}) — an empty body, or a drawing view whose source has no solid. "
                "Nothing was kept; session_state lists the bodies that have one, recompute names what failed to build.")
    return f"{name} failed: {e}"


class Server:
    def __init__(self, name, version, tools, instructions="", run=None, groups=None, resources=None, guard=None):
        self.name = name
        self.version = version
        self.tools = {t.name: t for t in tools}
        self.instructions = instructions
        # How a call is run: run(tool, fn) — directly, or as one undo step
        # (the session's), or handed to the GUI's thread.
        self.run = run or (lambda tool, fn: fn())
        # The groups listed now; None lists every tool.
        self.groups = groups
        self.resources = resources
        # A check on a call's arguments before it runs (where files may go).
        self.guard = guard
        # Notifications to send after the reply in hand (list_changed).
        self.outbox = []
        # What the calls cost the agent (usage.Meter), when one is kept.
        self.meter = None
        # Told of each call that went through: on_call(tool, args).
        self.on_call = None
        # Writes a notification at once, while a call runs (progress); None: not sent.
        self.notify = None
        # The session the calls act on (tools.build_server sets it): whose
        # call it is (session.by) and its undo count, for call_done.
        self.session = None
        # Heavy jobs' estimates and memory ceiling (agentlink/heavy.py).
        self.gate = None
        # What the client was last sent by tools/list ({listed tool: a hash
        # of its description and inputs}, every tool's name), and the state
        # list_stale() last named in full: session_state says once when the
        # list in the client's hands is no longer the one here.
        self._listed = None
        self._all_then = None
        self._stale_said = None

    def add(self, tool):
        self.tools[tool.name] = tool

    def listed(self):
        # An alias (an old name kept callable) is never listed beside its tool.
        base = getattr(self, "static_base", None)
        if base is not None:
            # The static minimal list (agentlink/staticbase.py): its base and any group turned on beyond the lean default.
            extra = set(self.groups or ()) - set(getattr(self, "lean_groups", None) or ())
            order = {n: i for i, n in enumerate(base)}
            out = [t for t in self.tools.values() if (t.name in base or t.group in extra) and not getattr(t, "alias_of", None)]
            return sorted(out, key=lambda t: order.get(t.name, len(order)))
        return [t for t in self.tools.values() if (self.groups is None or t.group in self.groups) and not getattr(t, "alias_of", None)]

    def is_listed(self, name):
        """Whether the client was shown this tool in the list as it is now."""
        return any(t.name == name for t in self.listed())

    def _list_sig(self):
        out = {}
        for t in self.listed():
            try:
                out[t.name] = hash((t.description, json.dumps(t.schema, sort_keys=True, default=str)))
            except Exception:
                out[t.name] = 0
        return out

    def note_listed(self):
        """tools/list was answered: what the client holds from now on."""
        self._listed = self._list_sig()
        self._all_then = set(self.tools)
        self._stale_said = None

    def list_stale(self, cap=30):
        """None while the client's tool list is the one here (or it never
        listed). Else what changed since it last listed — groups enabled or
        hidden, an add-on installed, updated or removed: the first time
        { added, removed, updated (listed tools whose description or inputs
        changed), callable (new tools that are not listed), note }, each a
        list of names; asked again before the client lists, the counts only."""
        if self._listed is None:
            return None
        now = self._list_sig()
        was = self._listed
        added = sorted(n for n in now if n not in was)
        removed = sorted(n for n in was if n not in now)
        updated = sorted(n for n in now if n in was and now[n] != was[n])
        new_all = sorted(n for n in self.tools if n not in (self._all_then or ()) and n not in now and not getattr(self.tools[n], "alias_of", None))
        gone_all = sorted(n for n in (self._all_then or ()) if n not in self.tools and n not in was)
        if not (added or removed or updated or new_all or gone_all):
            self._stale_said = None
            return None
        parts = {"added": added, "removed": removed, "updated": updated, "callable": new_all, "gone": gone_all}
        state = tuple(tuple(v) for v in parts.values())
        if self._stale_said == state:
            return {**{k: len(v) for k, v in parts.items() if v}, "note": "As said before: the tool list changed since it was last listed, and has not been listed again."}
        self._stale_said = state
        out = {k: (v[:cap] + [f"… {len(v) - cap} more"] if len(v) > cap else v) for k, v in parts.items() if v}
        out["note"] = ("The tool list changed since it was last listed (tools/list): list it again to see the new descriptions and inputs. "
                       "Meanwhile every tool here is callable by name, and tool_groups { tool: name } gives one tool's description and inputs.")
        return out

    def set_groups(self, groups):
        self.groups = groups
        self.outbox.append({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"})

    def handle(self, msg, client=None):
        """One message in; the reply, or None for a notification. client:
        the connection it came on (the window link's paired connection;
        None for stdio). An approval is bound to it (approvals.py, R4-11)."""
        mid = msg.get("id")
        method = msg.get("method")
        if method is None:
            return None
        try:
            if method == "initialize":
                if self.session is not None:
                    # A new conversation: every standing word is said again (agentlink/once.py).
                    from . import once

                    once.reset(self.session)
                if self.meter is not None:
                    # A new conversation: a new job in the usage log.
                    try:
                        self.meter.new_job("initialize")
                    except Exception:
                        pass
                result = {
                    "protocolVersion": PROTOCOL,
                    "capabilities": {"tools": {"listChanged": True}, **({"resources": {}} if self.resources else {})},
                    "serverInfo": {"name": self.name, "version": self.version},
                    "instructions": self.instructions,
                }
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                from . import staticbase

                staticbase.apply(self)
                result = {"tools": staticbase.listing(self, self.listed())}
                self.note_listed()
                if self.meter is not None:
                    self.meter.list(result["tools"], self.instructions)
            elif method == "resources/list" and self.resources:
                result = {"resources": self.resources.list()}
            elif method == "resources/read" and self.resources:
                result = {"contents": [self.resources.read((msg.get("params") or {}).get("uri", ""))]}
            elif method == "tools/call":
                params = msg.get("params") or {}
                from . import approvals

                with approvals.connection_call(client):
                    if params.get("name") in approvals.CLIENT_ONLY:
                        # approve_file / approve_code: this call came from the
                        # client, which asked the person when they set "ask
                        # first". Nested calls (batch, jobs, cookbooks, lessons)
                        # go through call() only and are refused there.
                        with approvals.client_call(params.get("name"), params.get("arguments")):
                            result = self.call(params)
                    else:
                        result = self.call(params)
            elif mid is None:
                return None  # notifications/initialized and the like
            else:
                return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"{method}: not supported."}}
        except Exception as e:  # a protocol error, not a tool's
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": str(e)}}
        return None if mid is None else {"jsonrpc": "2.0", "id": mid, "result": result}

    def call(self, params):
        t0 = time.time()
        s = self.session
        prior = None
        if self.meter is not None and s is not None:
            try:
                from . import appliesnow

                prior = appliesnow.before_call(s)  # what the applies-now filter last said, before this call moves it
            except Exception:
                prior = None
        before = (getattr(s, "tx", None), getattr(s, "doc", None)) if s is not None else None
        from . import around

        with _as_user(s), _acting(s), _hang_trace(s, params.get("name")), _progress_for(self, params):
            result = self._call(params)
            with around.part("callDone"):  # the add-ons' call_done handlers
                self._done(params, result, before)
        with around.part("notice"):
            _add_notice(result)
            _add_rider(result, params.get("name"))
        if self.meter is not None:
            tm = time.time()
            try:
                content = result.get("content") or []
                text = "".join(c.get("text", "") for c in content if c.get("type") == "text")
                import base64

                # Every picture: its first bytes (the PNG's size in its header) and its size in bytes.
                pics = [(base64.b64decode(c["data"][:64]), len(c["data"]) * 3 // 4) for c in content if c.get("type") == "image" and c.get("data")]
                from .usage import err_code

                err = err_code(result)
                tool = self.tools.get(params.get("name"))
                self.meter.call(str(params.get("name")), compact(params.get("arguments") or {}), text, None, err, (time.time() - t0) * 1000,
                                args=params.get("arguments") or {}, group=getattr(tool, "group", None), images=pics)
            except Exception:
                pass
            around.add("meter", time.time() - tm)
            if s is not None:
                # What the applies-now filter last said of this tool, against what the call did.
                with around.part("appliesMeter"):
                    try:
                        from . import appliesnow

                        appliesnow.after_call(s, str(params.get("name")), bool(result.get("isError")), prior, params.get("arguments"))
                    except Exception:
                        pass
        return result

    def handle_light(self, msg):
        """A tools/call for a socket-thread tool (hooks.THREAD_TOOLS): its
        arguments checked and its handler run here, on the caller's thread,
        with none of a call's window work (no undo step, echo, call_done,
        notice, rider or meter). The reply, as handle() gives it."""
        mid = msg.get("id")
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = self.tools.get(name)
        t0 = time.time()
        try:
            if tool is None:
                result = self.refusal("not_found", f"{name}: no such tool.")
            else:
                check_input(tool.schema, args)
                # The same path check as a call through the window's queue
                # (red team 4, R4-10): a socket-thread tool's file fields too.
                guard = getattr(self, "guard", None)
                if guard is not None:
                    guard(tool, args)
                out = tool.fn(args)
                if isinstance(out, dict):
                    out.setdefault("ms", int((time.time() - t0) * 1000))
                result = {"content": [{"type": "text", "text": compact(out)}]}
        except ToolError as e:
            result = self.refusal(e.code, e.message)
        except ValueError as e:
            result = self.refusal("invalid_input", str(e))
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            result = self.refusal("failed", f"{name} failed: {e}", _test_trace())
        if getattr(self, "meter", None) is not None:
            # In the usage log too: every tools/call passes the meter, also a socket-thread one.
            try:
                from .usage import err_code

                text = "".join(c.get("text", "") for c in result.get("content") or [] if c.get("type") == "text")
                self.meter.call(str(name), compact(args), text, None, err_code(result), (time.time() - t0) * 1000, args=args, group=getattr(tool, "group", None))
            except Exception:
                pass
        return None if mid is None else {"jsonrpc": "2.0", "id": mid, "result": result}

    def _done(self, params, result, before):
        """hooks call_done(session, tool, ok, changed) for a call to a tool
        there is; changed: it went through and changed the document (its
        undo count moved, the session's document is another one, or the
        tool changes it by its kind)."""
        s = self.session
        name = params.get("name")
        tool = self.tools.get(name)
        # A call that counts as the person's (gui_input's as: "person") says
        # so for its own call_done only: taken here, so it never outlives it.
        by = getattr(s, "done_by", None) if s is not None else None
        if by is not None:
            try:
                s.done_by = None
            except Exception:
                pass
        if s is None or tool is None:
            return
        ok = not result.get("isError")
        changed = False
        if ok:
            try:
                changed = (getattr(s, "tx", None) != before[0] or getattr(s, "doc", None) is not before[1]
                           or tool.changes_for(params.get("arguments") or {}))
            except Exception:
                changed = bool(tool.changes)
        try:
            from . import hooks

            if by == hooks.PERSON and getattr(s, "by", hooks.AGENT) == hooks.AGENT:
                with hooks.as_person(s):
                    hooks.emit("call_done", s, name, ok, bool(changed))
            else:
                hooks.emit("call_done", s, name, ok, bool(changed))
        except Exception:
            pass

    def _call(self, params):
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = self.tools.get(name)
        if tool is None:
            import difflib

            near = difflib.get_close_matches(str(name), list(self.tools), n=5, cutoff=0.5)
            prefix = str(name).split("_")[0] + "_"
            same = [n for n in self.tools if n.startswith(prefix)][:12] if not near else []
            if len(self.tools) <= 30:
                hint = f"the tools: {', '.join(self.tools)}"
            else:
                hint = f"near: {', '.join(near)}" if near else (f"its family: {', '.join(same)}" if same else "tool_groups lists them all")
            return self.refusal("not_found", f"{name}: no such tool — {hint}.")
        t0 = time.time()
        tool = tool.for_call(args)
        read_as = []
        try:
            # background: true on any read the tool does not take itself:
            # run it as a job (agentlink/jobs.py).
            asked = False
            if "background" in args and "background" not in (tool.schema.get("properties") or {}):
                asked = args.pop("background") in (True, "true")
            from . import around as _ar

            read_as = check_input(tool.schema, args, tool.name)
            if self.guard is not None:
                with _ar.part("guard"):
                    self.guard(tool, args)
            from . import jobs

            s = self.session
            as_job = False
            edit0, coedit = None, None
            if s is not None:
                with _ar.part("jobCheck"):
                    jobs.guard_change(tool, args, s)
                    # The person's open edit or task panel: a change to that
                    # body (or that document) is held (agentlink/coedit.py).
                    from . import coedit

                    edit0 = coedit.check(tool, args, s)
                    as_job = jobs.wanted(tool, args, s, asked=asked)
            elif asked:
                raise ToolError("invalid_input", "background: a job needs a session.")
            if asked and not as_job:
                # Inside a batch nothing runs as a job (the batch is one
                # answer): said so, where the general reason read as if a
                # plain read (meshobj_info) were not one — and by what the
                # call is (jobs.background_refusal): a read that writes a
                # file belongs in the batch's order, a change is never a job.
                raise ToolError("invalid_input", jobs.background_refusal(tool, args, getattr(s, "batch_now", None) is not None, s))
            changes0 = getattr(s, "_applies_seq", 0)
            if tool.name == "doc_save" and s is not None:
                from . import partialdoc

                said = partialdoc.refusal(getattr(s, "doc", None), tool.name)
                if said:
                    raise ToolError("invalid_state", said)
            gate = self.gate
            if gate is not None:
                gate.as_job = as_job
                try:
                    with _ar.part("gateBefore"):
                        gate.before(tool, args)
                finally:
                    gate.as_job = False
            try:
                if as_job:
                    out = self.run(tool, lambda: self._as_job(tool, args))
                elif tool.changes and s is not None and tool.name != "batch":
                    # The shared health check (agentlink/health.py) round
                    # every changing call, on the thread the tool runs on:
                    # what FreeCAD says went red, onto the answer as "health".
                    # A batch's calls each carry their own.
                    out = self.run(tool, lambda: _settled(lambda: _with_health(s, tool, args)))
                else:
                    out = self.run(tool, lambda: _settled(lambda: tool.fn(args)))
            except BaseException:
                if coedit is not None:
                    coedit.settle(edit0)
                if gate is not None:
                    gate.after(tool, args, False)
                raise
            if coedit is not None:
                # An edit the call opened (a cmd_run's sketch) is the agent's.
                coedit.settle(edit0)
            if gate is not None:
                # A job logs its own time when it ends (the call may have
                # answered before it did).
                with _ar.part("gateAfter"):
                    gate.after(tool, args, not as_job)
            if s is not None and not as_job:
                jobs.note_slow(tool, args, s, time.time() - t0)
            if s is not None and not as_job and (tool.changes or (tool.name == "batch" and getattr(s, "_applies_seq", 0) != changes0)):
                # Which tools apply to the document as it is now, read from their own leading checks: one short
                # line beside the health's next (agentlink/appliesnow.py). A batch's answer carries it once.
                try:
                    from . import appliesnow

                    with _ar.part("appliesNow"):
                        appliesnow.push(s, tool, out, count=tool.name != "batch")
                except Exception:
                    pass
            if self.on_call is not None:
                try:
                    with _ar.part("onCall"):
                        self.on_call(tool, args)
                except Exception:
                    pass
        except ToolError as e:
            if name == "batch":
                from . import staticbase

                return self.refusal(e.code, staticbase.batch_hint(e.message), outcome=_outcome(tool, e))
            return self.refusal(e.code, e.message, outcome=_outcome(tool, e), left=getattr(e, "outcome_left", None))
        except ValueError as e:
            return self.refusal("invalid_input", str(e), outcome=_outcome(tool, e), left=getattr(e, "outcome_left", None))
        except (SystemExit, KeyboardInterrupt) as e:
            # Code a tool ran (an add-on's, an approved cookbook entry's)
            # called sys.exit or raised KeyboardInterrupt: FreeCAD stays up.
            # Session.execute has already taken the step back.
            out_of = _outcome(tool, e)
            kept = "nothing was kept" if out_of in ("rolled_back", "not_started") else "some objects stay (left)"
            what = "called exit" if isinstance(e, SystemExit) else "was interrupted (KeyboardInterrupt)"
            return self.refusal("failed", f"{name}: the add-on's code {what}; {kept}. FreeCAD and Agent Link go on.",
                                outcome=out_of, left=getattr(e, "outcome_left", None))
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            return self.refusal("failed", failed_words(name, e), _test_trace(), outcome=_outcome(tool, e), left=getattr(e, "outcome_left", None))
        if read_as and isinstance(out, dict):
            # Fields given by another common name (FIELD_ALIASES): what was read.
            out["readAs"] = "read " + ", ".join(read_as)
        image = None
        s = self.session
        if isinstance(out, dict) and s is not None and getattr(s, "batch_now", None) is None:
            # Standing words a tool has already said in this conversation
            # left out and named in saidBefore (agentlink/once.py); a
            # batch's calls are thinned in its reply, in order, never inside
            # it (its record and to files keep every answer whole).
            from . import once

            once.thin_reply(s, self.tools.get(name, tool), out, self.tools)
        if isinstance(out, dict):
            # A picture for the agent to look at: image content beside the
            # text (the file is written as well; inline false leaves it out).
            image = out.pop("_png", None)
            out.setdefault("ms", int((time.time() - t0) * 1000))
        text = compact(out)
        if len(text) > MAX_REPLY and isinstance(out, dict):
            out = trim(out, MAX_REPLY)
            text = compact(out)
        content = [{"type": "text", "text": text}]
        if image is not None:
            import base64

            content.append({"type": "image", "data": base64.b64encode(image).decode("ascii"), "mimeType": "image/png"})
        return {"content": content}

    def _as_job(self, tool, args, wait=None):
        """Run tool on a worker thread (agentlink/jobs.py): its answer when
        it ends within JOB_WAIT, else the job's id and how to wait for it."""
        from . import jobs

        job = jobs.start(tool, args, self.session)
        waited = jobs.JOB_WAIT if wait is None else max(0.0, float(wait))
        if jobs.wait_for(job, waited):
            # Its answer goes back in this call: the echo shows it with the
            # call (agentlink/echo.py), not again when the job's end is heard.
            jobs.answered(job)
            if job["status"] == "failed":
                raise ToolError(job["error"]["code"], job["error"]["message"])
            out = job["result"]
            if isinstance(out, dict):
                out = dict(out)
                out.setdefault("job", job["job"])
            return out
        if waited <= 0:
            # job_start { wait: false } (live, 17 Nov: it said "past 45 s"
            # with no wait at all): the words say what was done.
            return {**jobs.summary(job), "note": f"{tool.name} started as a job and was not waited for (wait: false); nothing else was changed."}
        return {**jobs.summary(job), "note": f"{tool.name} is still running (past {waited:.0f} s, longer than a call may wait): it goes on as a job; nothing else was changed."}

    @staticmethod
    def refusal(code, message, trace=None, outcome=None, left=None):
        err = {"code": code, "message": message}
        if outcome:
            # What the refused call left in the document: not_started (no
            # change was made: safe to call again), rolled_back (taken back
            # whole), cleanup_incomplete (left: the objects that stay).
            err["outcome"] = outcome
        if left:
            err["left"] = list(left)
        if trace:
            err["trace"] = trace
        return {"content": [{"type": "text", "text": compact({"error": err})}], "isError": True}


# ---- progress notifications --------------------------------------------------
#
# The echo's step text (echo.say: the status bar's words) goes to the client
# as notifications/progress too, when the call's request gave a
# progressToken (params._meta.progressToken). A notification is a message of
# its own: it adds nothing to the answer. server.notify writes one at once
# (serve_lines and the window's link set it); without it nothing is sent.

_PROGRESS = []  # the calls in hand, innermost last: {server, token, n}


class _progress_for:
    def __init__(self, server, params):
        meta = (params or {}).get("_meta") if isinstance(params, dict) else None
        tok = meta.get("progressToken") if isinstance(meta, dict) else None
        self.entry = {"server": server, "token": tok, "n": 0} if isinstance(tok, (str, int)) and not isinstance(tok, bool) else None

    def __enter__(self):
        if self.entry is not None:
            self.entry["notify"] = getattr(self.entry["server"], "notify", None)  # this call's own writer, as it is now
            _PROGRESS.append(self.entry)
        return self

    def __exit__(self, *exc):
        if self.entry is not None and self.entry in _PROGRESS:
            _PROGRESS.remove(self.entry)
        return False


def progress(message):
    """Send message as a notifications/progress of the call in hand, if its
    request gave a progressToken and the server can write at once. True when
    sent. Never raises."""
    if not _PROGRESS:
        return False
    e = _PROGRESS[-1]
    notify = e.get("notify")
    if notify is None:
        return False
    e["n"] += 1
    msg = {"jsonrpc": "2.0", "method": "notifications/progress",
           "params": {"progressToken": e["token"], "progress": e["n"], "message": str(message)[:300]}}
    try:
        notify(msg)
        return True
    except Exception:
        return False


def _test_trace():
    """The traceback of the exception in hand, for a refusal's "trace" under
    the tests only (AGENTLINK_TEST=1): CI's log then shows where a tool
    failed. Never sent to an agent otherwise."""
    if os.environ.get("AGENTLINK_TEST") != "1":
        return None
    return traceback.format_exc()[-4000:]


def _add_notice(result):
    """A line an add-on's notice service has for the agent (hooks.notice):
    added once, as "notice", to the answer in hand, refusals too. Anything
    going wrong leaves the answer as it was."""
    try:
        from . import hooks

        content = result.get("content") or []
        body = json.loads(content[0]["text"]) if content and content[0].get("type") == "text" else None
        if not isinstance(body, dict):
            return
        line = hooks.notice()
        if not line:
            return
        had = body.get("notice")
        body["notice"] = f"{had} {line}" if had else line
        content[0]["text"] = compact(body)
    except Exception:
        pass


class _Nothing:
    def __enter__(self):
        return None

    def __exit__(self, *exc):
        return False


class _hang_trace:
    """While something runs that may hold FreeCAD — a call, a job's worker
    thread, a batch's wait for a heavy read: should it still be running
    after AFTER seconds, Python's own stack of every thread is written to
    <outDir>/crash/hang-<tool>.txt (a job's: hang-job-<tool>.txt, a batch's
    wait: hang-batch-wait-<tool>.txt), under a first line that says what
    was running. faulthandler writes it from a watchdog thread of its own,
    without Python's lock, so a call stuck inside FreeCAD on the GUI thread
    — or a job's thread stuck there with the GUI thread waiting for it —
    still leaves where each thread was. One that ends in time leaves
    nothing; one that ends late adds a last line saying it did end (long,
    not hung).

    faulthandler has one timer for the whole process, and several of these
    are open at once (a batch's wait round a job's thread, a call inside a
    batch): the timer is always set for the open one that is due first, and
    set again for the next as each ends. A batch's own call is not watched
    (it runs many calls, each watched, and may rightly take 100 s). The one
    file open is the one the timer writes to; it is closed whenever the
    timer moves on, and when the last watch ends none is left open."""

    AFTER = 60.0
    _lock = threading.Lock()
    _live = []  # the watches open now
    _armed = None  # [watch, file, the size of its first line]: what the timer holds

    def __init__(self, session, name, kind="call", after=None):
        self.name, self.kind = str(name or "call"), kind
        self.out = session if isinstance(session, str) else getattr(session, "out_dir", None)
        self.after = float(self.AFTER if after is None else after)
        self.path, self.on, self.fired, self.off, self.t0 = None, False, False, False, 0.0

    def __enter__(self):
        try:
            if not self.out or (self.kind == "call" and self.name == "batch"):
                return self
            import re

            d = os.path.join(self.out, "crash")
            os.makedirs(d, exist_ok=True)
            stem = ("" if self.kind == "call" else re.sub(r"[^A-Za-z0-9]+", "-", self.kind).strip("-") + "-") + re.sub(r"[^A-Za-z0-9_]", "_", self.name)
            self.path = os.path.join(d, "hang-" + stem + ".txt")
            self.t0 = time.time()
            self.due = time.monotonic() + self.after
            self.thread = threading.current_thread().name
            with self._lock:
                self._live.append(self)
                self.on = True
                self._set()
        except Exception:
            pass
        return self

    def __exit__(self, *exc):
        if not self.on:
            return False
        try:
            with self._lock:
                self.on = False
                if self in self._live:
                    self._live.remove(self)
                self._set()
                if self.fired:
                    # It ran long and ended: said under the stacks, so the
                    # file is not read as a hang.
                    with open(self.path, "a", encoding="utf-8") as f:
                        f.write(f"\n{self.kind} {self.name} ended after {time.time() - self.t0:.0f} s: long, not hung.\n")
        except Exception:
            pass
        return False

    @classmethod
    def _set(cls):
        """The timer set for the open watch due first (the lock held)."""
        import faulthandler

        held = cls._armed
        cls._armed = None
        if held is not None:
            w, f, head = held
            try:
                faulthandler.cancel_dump_traceback_later()
            except Exception:
                pass
            try:
                wrote = os.fstat(f.fileno()).st_size > head
            except Exception:
                wrote = True
            try:
                f.close()
            except Exception:
                pass
            if wrote:
                w.fired = True
            else:
                try:
                    os.remove(w.path)
                except OSError:
                    pass
        while True:
            waiting = [w for w in cls._live if not w.fired and not w.off]
            if not waiting:
                return
            w = min(waiting, key=lambda x: x.due)
            f = None
            try:
                f = open(w.path, "w", encoding="utf-8")
                f.write(f"Agent Link: {w.kind} {w.name} (thread {w.thread}, started {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(w.t0))}) "
                        f"was still running after {w.after:g} s. Python's stack of every thread then:\n\n")
                f.flush()
                head = os.fstat(f.fileno()).st_size
                # One overdue already (the timer was another's when its time
                # came) is written at once.
                faulthandler.dump_traceback_later(max(w.due - time.monotonic(), 0.05), repeat=False, file=f)
                cls._armed = [w, f, head]
                return
            except Exception:
                # This one cannot be watched (its file, the timer): the
                # others still get theirs.
                w.off = True
                try:
                    faulthandler.cancel_dump_traceback_later()
                except Exception:
                    pass
                if f is not None:
                    try:
                        f.close()
                        os.remove(w.path)
                    except Exception:
                        pass


def hang_trace(session, name, kind="call", after=None):
    """`with hang_trace(session or its folder, tool, kind):` — see _hang_trace."""
    return _hang_trace(session, name, kind, after)


def _acting(session):
    """hooks.acting while the agent's call runs (a panel click is the
    person's: session.by "person")."""
    try:
        from . import hooks

        if session is None or getattr(session, "by", hooks.AGENT) == hooks.AGENT:
            return hooks.acting()
    except Exception:
        pass
    return _Nothing()


def _as_user(session):
    """The test flag AGENTLINK_AS_USER=1 (hooks.as_user): the agent's call
    runs as the person's. Off, or a call the person already makes: as is."""
    try:
        from . import hooks

        if session is not None and getattr(session, "by", hooks.AGENT) == hooks.AGENT and hooks.as_user():
            return hooks.as_person(session)
    except Exception:
        pass
    return _Nothing()


def _add_rider(result, tool=None):
    """The add-ons' rider lines (hooks.rider_line) onto the answer in hand,
    as "rider", while any has something in hand. Anything going wrong
    leaves the answer as it was."""
    try:
        from . import hooks

        line = hooks.rider_line(tool)
        if not line:
            return
        content = result.get("content") or []
        body = json.loads(content[0]["text"]) if content and content[0].get("type") == "text" else None
        if not isinstance(body, dict):
            return
        body["rider"] = line
        content[0]["text"] = compact(body)
    except Exception:
        pass


def add_report(reply, lines):
    """New Report view problem lines (report_watch.take) onto a call's
    answer, as "report"; anything going wrong leaves the answer as it was."""
    if not lines:
        return
    try:
        result = reply.get("result") or {}
        content = result.get("content") or []
        body = json.loads(content[0]["text"]) if content and content[0].get("type") == "text" else None
        if not isinstance(body, dict):
            return
        body["report"] = lines
        try:
            from . import health

            health.note_report(body, lines)
        except Exception:
            pass
        content[0]["text"] = compact(body)
    except Exception:
        pass


_NOT_JSON = object()
# The note the hidden FreeCAD writes as it takes a call off its input, before
# the call begins: { id, changes } (supervise.py reads it; no client sees it).
TOOK = "notifications/agentlink/took"


def _call_changes(server, msg):
    """True when the call in msg may change something; True when that cannot be told."""
    try:
        params = msg.get("params") or {}
        tool = server.tools.get(params.get("name"))
        return True if tool is None else bool(tool.changes_for(params.get("arguments") or {}))
    except Exception:  # noqa: BLE001
        return True


def serve_lines(server, readline, write):
    """Read a message a line until the input ends; write each reply a line.
    A socket-thread tool (hooks.THREAD_TOOLS: job_status) is answered at
    once on a thread of its own, beside the call in hand (finding 41: it
    waited behind the job's own call); every other call in order."""
    import queue as _queue

    lock = threading.Lock()

    def out(text):
        with lock:
            write(text)

    if getattr(server, "notify", None) is None:
        server.notify = lambda m: out(compact(m) + "\n")  # a progress notification, written at once

    def light(msg):
        try:
            from . import hooks

            name = (msg.get("params") or {}).get("name")
            return msg.get("method") == "tools/call" and name in hooks.THREAD_TOOLS and hasattr(server, "handle_light")
        except Exception:  # noqa: BLE001
            return False

    def side(msg):
        reply = server.handle_light(msg)
        if reply is not None:
            out(compact(reply) + "\n")

    inbox = _queue.Queue()

    def reader():
        while True:
            line = readline()
            if not line:
                inbox.put(None)
                return
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                inbox.put(_NOT_JSON)  # answered in its turn, after the lines before it
                continue
            if isinstance(msg, dict) and light(msg):
                threading.Thread(target=side, args=(msg,), daemon=True).start()
                continue
            inbox.put(msg)

    threading.Thread(target=reader, name="agentlink-stdin", daemon=True).start()
    took_marks = bool(os.environ.get("AGENTLINK_SUPERVISED"))
    while True:
        msg = inbox.get()
        if msg is None:
            return
        if msg is _NOT_JSON:
            out(compact({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "not JSON"}}) + "\n")
            continue
        if took_marks and isinstance(msg, dict) and msg.get("method") == "tools/call" and msg.get("id") is not None:
            # Said to the supervisor before the call begins (E2): after a
            # restart it sends again only the calls never taken here.
            # As a notification: written at once, with none of a reply's after-work.
            server.notify({"jsonrpc": "2.0", "method": TOOK, "params": {"id": msg["id"], "changes": _call_changes(server, msg)}})
        reply = server.handle(msg)
        if reply is not None:
            out(compact(reply) + "\n")
        while server.outbox:
            out(compact(server.outbox.pop(0)) + "\n")
