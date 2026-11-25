# SPDX-License-Identifier: LGPL-2.1-or-later
# The Model Context Protocol, as much as a tool server needs: JSON-RPC 2.0,
# one message a line (the stdio framing), initialize, tools/list,
# tools/call and ping. No dependencies, so it runs in FreeCAD's own Python
# (FreeCADCmd, the GUI) as well as a plain interpreter — nothing to install
# into an application bundle.

import json
import math
import os
import re
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
        return health.attach(session, tool, m, out, args)


class ToolError(Exception):
    """A refusal the agent can act on: a code (invalid_input, not_found,
    failed) and a message that says what to do next. kind: fixable, retry
    or stop (refusal_kind), when the raiser knows it; else from the code."""

    def __init__(self, code, message, kind=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.kind = kind


# ---- what kind of refusal ---------------------------------------------------
#
# Every refusal's error carries "kind" (research on small local models,
# 22 Nov): fixable (the call cannot succeed as written; the message says
# what to change), retry (a transient cause: the same call may succeed),
# stop (it cannot succeed: report it). The kind's fixed sentence ends
# the message. The code and the status stay as they are.

KIND_WORDS = {
    "fixable": "Change what the error names and call again.",
    "retry": "Retrying the same call is expected to succeed.",
    "stop": "Do not call it again. Report what happened.",
}
# A FreeCAD error that names no input to change (24 Nov QA: "BRep_API:
# command not done" came back with "The error says what to change"). A
# message that carries this line keeps kind fixable, without that sentence.
NAMES_NOTHING = "FreeCAD's error does not say which input to change."
# The fixable sentence before 26 Nov: taken out of a message that carries it.
OLD_KIND_WORDS = ("This call cannot succeed as written. The error says what to change; call the tool again with the corrected value.",)
# The person's to say or to set: an approval, a hold, a refusal by rule.
STOP_CODES = frozenset(("held_person_editing", "not_allowed", "refused", "denied", "declined", "stopped",
                        "pending_approval", "approval_pending", "unsupported", "unavailable"))
FIX_CODES = frozenset(("invalid_input", "not_found"))
# Words of a cause that passes: the same call may then go through.
TRANSIENT_WORDS = re.compile(r"\b(busy|timed out|time out|timeout|not ready|locked|took no queued call|still running|still starting|try again)\b", re.I)
STOP_MARK = "No progress after "
HELD_BY_DIALOG = "has a menu or dialog open"


def refusal_kind(code, message=""):
    """fixable, retry or stop for a refusal's code and words (KIND_WORDS)."""
    m = str(message or "")
    if code in STOP_CODES and not (code == "unavailable" and TRANSIENT_WORDS.search(m)):
        return "stop"
    if code in FIX_CODES:
        return "fixable"
    if HELD_BY_DIALOG in m:
        return "fixable"  # a dialog holds the window: the words say what closes it first
    if code == "busy" or TRANSIENT_WORDS.search(m):
        return "retry"
    return "fixable"


def strip_kind(message):
    """The message without the kind sentences it carries (a refusal that
    wraps another one's words, a ladder that adds its own)."""
    m = str(message or "")
    for w in (*KIND_WORDS.values(), *OLD_KIND_WORDS):
        m = m.replace(" " + w, "").replace(w, "")
    return m.strip()


def names_input(message):
    """Whether a refusal's words name an input to change: a place
    (input.depth, calls.2, constraints[1]) or a field they start with
    ("edges: …"). The fixable sentence goes only on these (26 Nov QA: it
    ended every refusal, also those that named nothing to change)."""
    m = str(message or "")
    return bool(_PLACES.search(m) or _LEAD.match(m))


def set_kind(err, kind=None):
    """err (a refusal's error object) with its kind and the kind's sentence
    at the end of its message, once. kind None: from its code and words."""
    if not isinstance(err, dict):
        return err
    msg = strip_kind(err.get("message", ""))
    kind = kind or refusal_kind(err.get("code"), msg)
    err["kind"] = kind
    if kind == "stop" and STOP_MARK in msg:
        err["message"] = msg  # the stop line says it already
    elif kind == "fixable" and (NAMES_NOTHING in msg or not names_input(msg)):
        err["message"] = msg  # nothing named to change: the sentence would point nowhere
    else:
        err["message"] = (msg + " " + KIND_WORDS[kind]).strip()
    return err


def kinded(err):
    """set_kind for an error that has no kind yet; one that has stays."""
    if isinstance(err, dict) and "kind" not in err:
        set_kind(err)
    return err


def describe(v):
    """What a value is, not the value (a refusal never pastes a model's
    whole input back: research, 22 Nov — an echo raises the chance of the
    same call again)."""
    if isinstance(v, bool):
        return "true/false"
    if isinstance(v, (int, float)):
        return "a number"
    if isinstance(v, str):
        return f"text of {len(v)} characters"
    if isinstance(v, (list, tuple)):
        return f"a list of {len(v)} item{'' if len(v) == 1 else 's'}"
    if isinstance(v, dict):
        return "an object with " + (f"keys {', '.join(map(str, list(v)[:6]))}" + (" …" if len(v) > 6 else "") if v else "no keys")
    if v is None:
        return "null"
    return type(v).__name__


def short_or_described(v, limit=40):
    """v as written when it is short (a wrong enum value), else describe(v)."""
    r = repr(v)
    return r if len(r) <= limit and not isinstance(v, (dict, list, tuple)) else describe(v)


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


# The supervisor tells the window which MCP client it serves (clientInfo,
# from the client's initialize), on its own connection to the window link.
CLIENT_METHOD = "agentlink/client"


SYNONYMS = {
    "centre": ("center",), "center": ("centre",), "colour": ("color",), "color": ("colour",),
    "body": ("object", "part"), "object": ("body",), "part": ("body", "object"),
    "bodies": ("objects", "parts"), "objects": ("bodies",), "parts": ("bodies", "objects"),
    # file/filename → path went on 24 Nov (rename set 2, rule R5: no alias for a renamed field).
}


# Fields an agent often gives one tool by another name (seen in the usage
# log's refusals, efficiency design C2, 22 Nov): per tool, the field given and
# the field the tool has. Taken as that field when it is not given, and said
# in the answer's readAs. The cards do not change.
FIELD_ALIASES = {
    "doc_close": {"document": "documents", "name": "documents"},
    "doc_open": {"file": "path", "document": "path"},
    "object_get": {"properties": "filter", "property": "filter", "names": "filter"},
    "object_delete": {"object": "objects", "name": "objects"},
    "shape_query": {"object": "body"},
    # batch's commands/steps → calls went on 24 Nov (owner decision 10): the
    # listed schema shows calls, and a wrong name is refused with the fields.
    # object_set's set/properties/props and varset_set/new's values went on 24
    # Nov (rename set 10, rule R5): values is the one property map's name.
}

# A field a model sends to a tool that does not take it, with the words
# that say why and what to send (local-model runs, 24 Nov: sketch_add
# { body }). Not an alias: the call is still refused, and these words come
# after the fields.
WRONG_FIELD_WORDS = {
    "sketch_add": {"body": 'sketch_add takes sketch, not body: a sketch is already in a body. '
                           'Example: { "sketch": "Sketch", "items": [{ "kind": "rectangle", "center": [0, 0], "size": [40, 20] }] }.'},
}

# A field that means something only beside another one (per tool: field ->
# the field it goes with). Given alone, it is left out and said in readAs
# (live findings, 22 Nov: batch { at: "./", calls } was taken for a read).
GOES_WITH = {
    # batch { read, at } became record_read { path, at } (owner decision 12, 24 Nov).
}


# Fields that only ever appear in Agent Link's answers, never as a tool's
# input (live findings, 22 Nov: a local model copied "ms": 0 from the answers
# into every batch call, and each one was refused). Given to a tool that has
# no such input, they are left out and the answer's readAs says so. A tool
# whose schema has the name as a real input keeps it.
ANSWER_FIELDS = ("ms", "msBy", "around", "saidBefore", "record", "appliesNow", "health", "readAs", "step",
                 "options", "notice", "rider", "truncated", "status", "result", "isError", "said", "flattened")

# Optional text inputs that an empty string ("") means nothing for: read as
# left out, so the call gets the answer it gives without them (live findings,
# 22 Nov: tool_find { group: "", tool: "" }). Per tool, kept small: only where
# an empty value cannot mean something of its own.
EMPTY_IS_LEFT_OUT = {
    "tool_find": ("words", "group", "tool", "to"),
    "tool_groups": ("group", "tool", "find", "needs"),
}


def read_as_words(read_as):
    """The answer's readAs line from check_input's list: the aliases read,
    then the fields left out."""
    aliases = [r for r in read_as if not r.startswith("ignored ")]
    other = [r for r in read_as if r.startswith("ignored ")]
    return "; ".join((["read " + ", ".join(aliases)] if aliases else []) + other)


def _as_alias(spec, v):
    """A value given under an alias, in the shape of the field it is read as:
    one name for a list field, a list of names for a filter."""
    t = spec.get("type") if isinstance(spec, dict) else None
    if t == "array" and not isinstance(v, list):
        return [v]
    if not t and isinstance(v, list) and all(isinstance(x, str) for x in v):
        return "|".join(v)
    return v


# tool_find's forms, shown whole when a call fits none (live, 22 Nov: a
# local model sent queries as objects three times; the old words did not
# say that queries are plain strings).
FIND_FORMS = ('tool_find takes: words: "pad sketch" (plain words); queries: ["pad sketch", "hole", "pd_pad"] '
              '(searches, up to 6, and tool names, up to 20, in one list); tool: "pd_pad" (a name, or a list of names); groups: true. '
              'tool and queries can be in one call.')
_QUERY_KEYS = ("words", "query", "q", "text", "find")


def find_queries(a):
    """tool_find's searches as plain strings, and what was read another way.
    The meaning of these shapes is clear, so they are read, not refused:
    queries as objects ({words: "…"}), words as a list, one query as a string."""
    read_as = []
    qs = a.get("queries")
    words = a.get("words")
    if qs is None and isinstance(words, list):
        qs, words = words, None
        read_as.append("words (a list) as queries")
    if qs is None and words is not None:
        qs = [words]
    if isinstance(qs, (str, dict)):
        qs = [qs]
        read_as.append("queries as a list of one")
    if not isinstance(qs, list):
        return [], read_as
    out, objects = [], False
    for q in qs:
        if isinstance(q, dict):
            q = next((q[k] for k in _QUERY_KEYS if isinstance(q.get(k), str)), None)
            objects = True
        if not isinstance(q, str) or not q.strip():
            return [], read_as
        out.append(q)
    if objects:
        read_as.append('queries given as objects, read as their words (queries is a list of plain strings: ["pad sketch", "hole"])')
    return out, read_as


FIND_MAX_SEARCHES = 6
FIND_MAX_CARDS = 20


def loose_name(server, n):
    """A tool name from a name written loosely, or None: a client's prefix,
    other letter case, - for _, or one or two letters wrong in a name with _
    (pd_poket). Words with spaces are never a name."""
    if not isinstance(n, str):
        return None
    w = n.strip()
    if not w or any(c.isspace() for c in w):
        return None
    for cand in (w, w.lower().replace("-", "_")):
        got = plain_name(server, cand)
        if got in server.tools:
            return got
    w = plain_name(server, w.lower().replace("-", "_"))
    if "_" not in w or len(w) < 5:
        return None
    import difflib

    best = difflib.get_close_matches(w, list(server.tools), n=2, cutoff=0.88)
    # Only one close name: two equally close ones are a guess.
    if len(best) == 1 or (len(best) == 2 and difflib.SequenceMatcher(None, w, best[0]).ratio()
                          - difflib.SequenceMatcher(None, w, best[1]).ratio() > 0.04):
        return best[0]
    return None


def sort_find(server, a):
    """tool_find's input sorted: (names, searches, read_as). tool and
    queries (or words) can come in one call, and either can hold names or
    words: a name, also written loosely, gives its card; anything else is a
    search (owner, 22 Nov). Raises ToolError over the limits."""
    qs, read_as = find_queries(a)
    tool = a.get("tool")
    tl = [tool] if isinstance(tool, str) else (list(tool) if isinstance(tool, list) else [])
    names, searches = [], []
    for src, items in (("tool", tl), ("queries", qs)):
        for q in items:
            if not isinstance(q, str) or not q.strip():
                continue
            n = loose_name(server, q)
            if n is not None:
                if n not in names:
                    names.append(n)
                if n != q.strip():
                    read_as.append(f"{q.strip()} as the tool {n}")
            else:
                searches.append(q.strip())
                if src == "tool":
                    read_as.append(f"tool: {q.strip()} is no tool name, so it was searched")
    if len(searches) > FIND_MAX_SEARCHES:
        raise ToolError("invalid_input", f"{len(searches)} searches, and the most is {FIND_MAX_SEARCHES} in one call (tool names do not count). "
                                         f"Split them into two calls. {FIND_FORMS}")
    if len(names) > FIND_MAX_CARDS:
        raise ToolError("invalid_input", f"{len(names)} tool names, and the most is {FIND_MAX_CARDS} cards in one call. Split them into two calls. {FIND_FORMS}")
    return names, searches, read_as


def does_hits(server, n, k=3):
    """For a tool name that is not here: the tools that do what its words
    say, by the search (tool_find), as "name (what it does)" — a wrong tool
    name gets the right tool, never a guess at its inputs (owner, 22 Nov:
    sketch_rectangle and sketch_circle are sketch_add)."""
    t = (getattr(server, "tools", None) or {}).get("tool_find")
    if t is None or not isinstance(n, str):
        return []
    words = re.sub(r"[_\-]+", " ", n.split("__")[-1]).strip()
    try:
        got = t.fn({"words": words, "limit": k})
    except Exception:  # noqa: BLE001 - advice only
        return []
    return [f"{h['tool']} ({h.get('does', '').rstrip('.')})" for h in (got.get("tools") or [])[:k] if isinstance(h, dict) and h.get("tool")]


# A tool name that names a kind of sketch geometry (sketch_rectangle,
# circle, draw_line): that kind is an item of sketch_add (local-model runs,
# 23 Nov: models made up such tools and drew a rectangle as four lines).
# Tool names only, so a did-you-mean: no call is changed or guessed.
# Other words for a kind, as models write them in a tool name.
SKETCH_KIND_WORDS = {"spline": "bspline", "rect": "rectangle", "square": "rectangle", "hexagon": "polygon", "oblong": "slot"}
# The value of each field in a kind's example; fields that are not needed
# (KIND_OPTIONAL) are left out. A kind can have its own value (KIND_VALUES).
KIND_VALUE = {"from": [0, 0], "to": [40, 0], "center": [0, 0], "corner": [0, 0], "radius": 10, "size": [40, 20], "start": 0, "end": 90,
              "points": [[0, 0], [20, 10], [40, 0]], "sides": 6, "at": [0, 0], "major": 40, "minor": 20, "width": 4}
KIND_VALUES = {"rounded_rectangle": {"radius": 4}, "slot": {"radius": 5}, "arc_slot": {"radius": 20}}
KIND_OPTIONAL = {"rotation", "closed", "construction", "dims", "name", "interpolate", "degree"}


def sketch_kinds(server):
    """{kind: [fields]} as sketch_add's card gives them ("circle {center,
    radius|diameter}"), in its order; {} without sketch_add."""
    t = (getattr(server, "tools", None) or {}).get("sketch_add")
    if t is None:
        return {}
    out = {}
    for kind, body in re.findall(r"\b([a-z][a-z0-9_]*) \{([^{}]*)\}", str(t.description or "")):
        if kind in out or kind == "kind":
            continue
        fields = []
        for part in re.sub(r"\([^)]*\)", "", body).split(","):
            w = part.strip().split(" ")[0].split("|")[0].split(":")[0].strip()
            if w == "…":
                fields += [f for f in out.get(kind.split("_", 1)[-1], []) if f not in fields]
            elif re.fullmatch(r"[a-z_]+", w) and w not in fields:
                fields.append(w)
        out[kind] = fields
    return out


def kind_in_name(server, n):
    """The sketch_add kind a tool name names (the longest, by whole name
    words: sketch_rectangle, CreateCircle, draw_arc_slot), or None."""
    if not isinstance(n, str):
        return None
    kinds = sketch_kinds(server)
    if not kinds:
        return None
    words = [w for w in re.split(r"[_\-\s.]+", re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", n.split("__")[-1]).lower()) if w]
    best = None
    for i in range(len(words)):
        for j in range(i + 1, min(len(words), i + 3) + 1):
            w = "_".join(words[i:j])
            k = w if w in kinds else (w[:-1] if w.endswith("s") and w[:-1] in kinds else SKETCH_KIND_WORDS.get(w))
            if k in kinds and (best is None or len(k) > len(best)):
                best = k
    return best


def kind_example(server, kind):
    """One sketch_add item of that kind, with values (KIND_VALUE), or None
    when a field of the card has no known value."""
    fields = sketch_kinds(server).get(kind)
    if fields is None:
        return None
    item = {"kind": kind}
    for f in fields:
        if f in KIND_OPTIONAL:
            continue
        v = (KIND_VALUES.get(kind) or {}).get(f, KIND_VALUE.get(f))
        if v is None:
            return None
        item[f] = v
    return item


def kind_hint(server, n):
    """The words for a tool name that names a sketch_add kind, or None."""
    kind = kind_in_name(server, n)
    if kind is None:
        return None
    ex = kind_example(server, kind)
    words = f'In a sketch, a {kind} is one item of sketch_add: use sketch_add with items [{{ kind: "{kind}", … }}]'
    if ex is None:
        return words + ". Its fields are in sketch_add's card: tool_find { tool: \"sketch_add\" }"
    return words + ". Example: " + json.dumps({"tool": "sketch_add", "arguments": {"items": [ex]}}, separators=(", ", ": "))


def close_names(server, n, k=4):
    """The tool names closest to n: most shared name words first, then the
    closest spelling (pd_pad_create: pd_pad before pd_pocket)."""
    return close_in(plain_name(server, n), server.tools, k)


def close_in(n, names, k=4):
    """The names closest to n: most shared name words (split at _ and -)
    first, then the closest spelling. For tool and guide names only, never
    for the inputs of a tool that changes the document (owner, 24 Nov)."""
    import difflib

    if not isinstance(n, str) or not n:
        return []
    words = {p for p in n.lower().replace("-", "_").split("_") if p}
    scored = []
    for t in names:
        shared = len(words & set(t.split("_")))
        ratio = difflib.SequenceMatcher(None, n, t).ratio()
        if shared or ratio >= 0.6:
            scored.append((shared, ratio, t))
    scored.sort(key=lambda x: (-x[0], -x[1], x[2]))
    return [t for _, _, t in scored[:k]]


def plain_name(server, n):
    """A tool's own name from a client's prefixed one (agentlink_pd_pad,
    mcp__…__pd_pad: the prefix the client puts on MCP tools). Only an exact
    tool name after the prefix counts; anything else comes back as it was."""
    if not isinstance(n, str) or n in server.tools:
        return n
    rest = n
    while "_" in rest:
        rest = rest.split("_", 1)[1]
        if rest in server.tools and n[: len(n) - len(rest)].rstrip("_").lower().split("__")[-1].replace("-", "_") in ("agentlink", "agentlink_freecad", "freecad_agent_link"):
            return rest
    return n


# The pure reads that ignore (and name) a field they do not have. A list,
# not the changes flag: approve_file and approve_code change nothing in the
# document but must take their exact pending arguments, and a tool that
# writes a file can misread a misspelled path. Every tool not here refuses.
STRICT_SHAPE = frozenset(("approve_file", "approve_code"))
FORGIVING_READS = frozenset(("session_state", "tool_find", "tool_groups", "guide_read", "get", "job_status", "usage_report", "report_read"))


# Tools whose answer ends with the live names whatever they changed: the
# runners of many calls (a batch, a fast block) and an option run by number.
LIVE_NAMES_TOOLS = frozenset(("batch", "fast", "pick"))
# The key of the live names; a tool whose answer has a "now" of its own (a
# reading after a change) gets them under the other key.
LIVE_KEY, LIVE_KEY_ELSE = "now", "nowNames"
# Sketch tools that change a sketch's geometry: a change to a sketch that a
# feature uses, while its body has an unused sketch, gets the sketchNote.
SKETCH_GEOMETRY_TOOLS = frozenset(("sketch_add", "sketch_offset", "sketch_external", "sketch_edit", "sketch_copy", "sketch_array",
                                   "sketch_extend", "sketch_join", "sketch_carbon", "sketch_project", "sketch_to_bspline",
                                   "sketch_bspline", "sketch_mirror"))

ORIENT_HEAD = "\n\nWhere you are, read at connect (session_state reads it again): "


def orient_text(got):
    """The orientation as the words at connect: compact JSON."""
    return ORIENT_HEAD + json.dumps(got, ensure_ascii=False, separators=(",", ":"))


# The keys of a batch step (and of the batch) that come with arguments
# when a direct call is sent in the step's form.
WRAP_KEYS = frozenset(("rollback", "stopOnError"))


def names_tool(v, tool):
    """Whether v names this tool: its own name, or the name with a client's
    prefix (agentlink_tool_find, mcp__agentlink__tool_find)."""
    return isinstance(v, str) and bool(tool) and (v == tool or v.endswith("_" + tool))


def check_input(schema, args, tool=None):
    """Unknown keys and missing required ones refused by name, as the
    answers name them: what the agent got wrong and what is allowed.
    Answers the aliases read (FIELD_ALIASES), as "given as field" words."""
    if not isinstance(args, dict):
        raise ToolError("invalid_input", "arguments: an object.")
    props = schema.get("properties", {})
    read_as = []
    # The inputs wrapped as a batch step wraps them ({arguments: {…}} on a
    # direct call; live, 22 Nov: a local model, five times in one run):
    # taken from inside, when arguments is not a field here and the other
    # keys are only the step's own (tool: this tool's name; rollback,
    # stopOnError of the batch). 26 Nov QA: { tool: "agentlink_tool_find",
    # arguments: {…} } got tool_find's own card, and get { arguments: { what } }
    # "what: required". Other keys with it: refused by name.
    inner = args.get("arguments")
    # Not on the approval tools: they take the pending call exactly, shape too.
    if "arguments" in args and "arguments" not in props and isinstance(inner, dict) and tool not in STRICT_SHAPE:
        others = [k for k in args if k != "arguments"]
        if all(k in WRAP_KEYS or (k == "tool" and names_tool(args[k], tool)) for k in others):
            args.clear()
            args.update(inner)
            read_as.append("inputs taken from inside arguments (a direct call takes them at the top level)"
                           + (f"; ignored {', '.join(others)}" if others else ""))
        else:
            first = next(iter(inner), None)
            form = f"{tool} {{ {first}: … }}" if tool and first else "{ field: … }"
            raise ToolError("invalid_input", f"inputs go at the top level of a direct call: {form}, not inside arguments. "
                                             "Only a batch step takes { tool, arguments }.")
    required = set(schema.get("required", []))
    empty = [k for k in (EMPTY_IS_LEFT_OUT.get(tool) or ()) if args.get(k) == "" and k not in required]
    for k in empty:
        args.pop(k)  # read as left out, and not said: an empty value carries nothing (26 Nov QA: noise on every tool_find)
    answer_only = [k for k in args if k in ANSWER_FIELDS and k not in props]
    for k in answer_only:
        args.pop(k)
    if answer_only:
        read_as.append(f"ignored {', '.join(answer_only)} ({'an answer field' if len(answer_only) == 1 else 'answer fields'})")
    for k, partner in (GOES_WITH.get(tool) or {}).items():
        if k in args and args.get(partner) is None:
            args.pop(k)
            read_as.append(f"ignored {k} (it goes with {partner}, which was not given)")
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
    if unknown and schema.get("additionalProperties") is False and tool in FORGIVING_READS:
        # A pure read: a field it does not have is ignored and named, not
        # refused. Nothing can go wrong in a read, and a refusal costs the
        # agent a turn (owner, 22 Nov: reads forgive, changes refuse).
        for k in unknown:
            args.pop(k)
        read_as.append(f"ignored {', '.join(unknown)} (not {'a field' if len(unknown) == 1 else 'fields'} here — the fields: {', '.join(props) or 'none'})")
        unknown = []
    if unknown and schema.get("additionalProperties") is False:
        more = (WRONG_FIELD_WORDS.get(tool) or {}).get(unknown[0])
        raise ToolError("invalid_input", f"input.{unknown[0]}: not a known field — the fields here: {', '.join(props) or 'none'}" + (f". {more}" if more else ""))
    for k in schema.get("required", []):
        if k not in args:
            raise ToolError("invalid_input", f"input.{k}: required.")
    # A value the card's example marks to give, sent as the example's null
    # (or its <name>): refused by name, never read as left out (owner, 22 Nov).
    if tool:
        from . import examples

        for k, what in examples.to_give(tool).items():
            v = args.get(k, 0)
            if v is None or v == f"<{k}>":
                raise ToolError("invalid_input", f"input.{k}: give the value ({what}) in place of {'null' if v is None else v}.")
    for k, v in list(args.items()):
        spec = props.get(k)
        if isinstance(spec, dict) and v is not None:
            number_goes(k, spec, v, props, args)
            args[k] = _typed(f"input.{k}", spec, v)
    return read_as


# A word field given a number that belongs in a number field of the same
# tool (26 Nov QA: pd_pad extent: 5 refused five times, and the words never
# said where the depth goes): { word field: number field }.
NUMBER_GOES = {"extent": "length"}


def number_goes(k, spec, v, props, args):
    """Refuse a number in a word field with the field it goes in, when the
    tool has that number field and it is not given."""
    to = NUMBER_GOES.get(k)
    if (to and spec.get("type") == "string" and isinstance(v, (int, float)) and not isinstance(v, bool)
            and (props.get(to) or {}).get("type") == "number" and to not in args):
        words = str(spec.get("description") or "").strip().rstrip(".")
        words = re.sub(r"\s*\(default\)", "", words)
        raise ToolError("invalid_input", f"input.{k}: {k} takes a word ({words}); a depth goes in {to}: {{ {to}: {v:g} }}.")


_PY = {"string": (str,), "number": (int, float), "integer": (int,), "boolean": (bool,), "array": (list,), "object": (dict,)}


def _form(spec):
    """The field's form from its card, for a refusal of the wrong type
    (owner, 22 Nov: show the form, do not guess): its own description, or
    an object's fields. "" when the card has neither."""
    d = spec.get("description")
    if isinstance(d, str) and d.strip():
        d = d.strip()
        return " The form: " + (d if len(d) <= 220 else d[:217] + "…")
    props = spec.get("properties")
    if spec.get("type") == "object" and isinstance(props, dict) and props:
        return " The form: { " + ", ".join(list(props)[:8]) + " }."
    return ""


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
            raise ToolError("invalid_input", f"{where}: {_said(t)}, not {_kind(v)}.{_form(spec)}")
    if "enum" in spec and v not in spec["enum"]:
        lowered = {str(e).lower(): e for e in spec["enum"]}
        if isinstance(v, str) and v.lower() in lowered:
            return lowered[v.lower()]
        raise ToolError("invalid_input", f"{where}: one of {', '.join(map(str, spec['enum']))} — not {short_or_described(v)}.")
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
    return err.get("status") == "not_started"


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
        # Where the agent is, short (Session.orientation): read at
        # initialize into the words sent then, and given once on the first
        # answer of a conversation (owner, 22 Nov). None: neither.
        self.orient = None
        self._oriented = False
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

    def orient_words(self):
        """The orientation for the words at connect, or "" (none, or it failed)."""
        if self.orient is None:
            return ""
        try:
            return orient_text(self.orient())
        except Exception:  # noqa: BLE001
            return ""

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
                # The client's own name, per connection: approve_file and
                # approve_code count only from a client known to ask the
                # person first (agentlink/approvals.py).
                from . import approvals

                approvals.note_client(client, ((msg.get("params") or {}).get("clientInfo") or {}))
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
                self._oriented = False
                self._ran = []  # a new conversation: no call of it ran yet (again_before)
                self._batch_kept = []  # nor a batch (tools.ran_before)
                now = getattr(self, "instructions_now", None)
                if now is not None:
                    # Made again at each connect: the guide list is read from
                    # the guide files there now (an add-on's guides too).
                    try:
                        self.instructions = now()
                    except Exception:
                        pass
                result = {
                    "protocolVersion": PROTOCOL,
                    "capabilities": {"tools": {"listChanged": True}, **({"resources": {}} if self.resources else {})},
                    "serverInfo": {"name": self.name, "version": self.version},
                    "instructions": self.instructions + self.orient_words(),
                }
            elif method == "ping":
                result = {}
            elif method == CLIENT_METHOD:
                # The supervisor's word on the window link: the name its MCP
                # client gave in initialize (the window never sees that
                # initialize). Nothing else changes.
                from . import approvals

                approvals.note_client(client, ((msg.get("params") or {}).get("clientInfo") or {}))
                # A new conversation on the window link: its first answer orients again.
                self._oriented = False
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
                from . import approvals, timelimit

                timelimit.started()  # the run's time counts from the first call (AGENTLINK_TIME_LIMIT_MIN)

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
        if params.get("name") == "pick" and "pick" in self.tools and self.session is not None:
            # An option run by its number (agentlink/options.py): its call
            # goes through this same path, under the tool's own name.
            from . import options

            return options.pick_call(self, params)
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

        seen = again_before(self, params)
        with _as_user(s), _acting(s), _hang_trace(s, params.get("name")), _progress_for(self, params):
            result = seen["refusal"] if seen and seen.get("refusal") else self._call(params)
            with around.part("callDone"):  # the add-ons' call_done handlers
                self._done(params, result, before)
        try:
            again_after(self, params, result, seen)
        except Exception:  # noqa: BLE001 - a record only
            pass
        try:
            repeat_words(self, params.get("name"), result, params.get("arguments"))
        except Exception:  # noqa: BLE001 - words only
            pass
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
        from . import timelimit

        timelimit.started()
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
        s = self.session
        held = None
        if s is not None:
            # A sketch a tool took when none was named, said in filled; the
            # sketch the call works on, for the used-sketch note
            # (families/pd_common.py sketch_of; decision 4, 23 Nov).
            held = (getattr(s, "filled_now", None), getattr(s, "sketch_now", None))
            s.filled_now, s.sketch_now = [], None
        try:
            result = self._call_core(params)
        finally:
            if s is not None:
                got, sk = s.filled_now, s.sketch_now
                s.filled_now, s.sketch_now = held
                self._acted = (list(got or ()), sk)  # what the call acted on, for again_after
        if s is not None:
            try:
                self._sketch_words(params, result, got, sk)
            except Exception:  # noqa: BLE001 - words only
                pass
        if isinstance(result, dict) and result.get("isError"):
            try:
                self._refusal_extras(params, result)
            except Exception:  # noqa: BLE001 - words only: the refusal stays as it is
                pass
        return result

    def _sketch_words(self, params, result, filled, sk):
        """filled: the sketch a tool took when none was named, as
        "pd_pad.sketch=Sketch 2 (open in edit in the window)". sketchNote: a
        change to the geometry of a sketch a feature uses while its body
        has an unused sketch (decision 4, D-b)."""
        name = plain_name(self, params.get("name")) or params.get("name")
        note = None
        if sk is not None and name in SKETCH_GEOMETRY_TOOLS and isinstance(result, dict) and not result.get("isError"):
            from .families import pd_common

            note = pd_common.used_sketch_note(sk, tool=name)
        if not filled and not note:
            return
        content = (result or {}).get("content") or []
        if not content or content[0].get("type") != "text":
            return
        body = json.loads(content[0]["text"])
        if not isinstance(body, dict):
            return
        tail = {k: body.pop(k) for k in (LIVE_KEY, LIVE_KEY_ELSE) if k in body}
        if filled:
            had = body.get("filled")
            had = list(had) if isinstance(had, list) else ([had] if had else [])
            body["filled"] = list(dict.fromkeys(had + [f"{name}.{w}" for w in filled]))
        if note:
            body["sketchNote"] = note
        body.update(tail)
        content[0]["text"] = compact(body)

    def _live_names(self, name, tool, args):
        """The live names of the agent's document (agentlink/livenames.py)
        for an answer that ends a change: a changing call, a batch, a fast
        block, a call of a tool that is not here. None inside a batch or a
        block (their answer carries it once), or with no document."""
        s = self.session
        if s is None or getattr(s, "batch_now", None) is not None or getattr(s, "doc", None) is None:
            return None
        if not (tool is None or name in LIVE_NAMES_TOOLS):
            try:
                if not tool.changes_for(args if isinstance(args, dict) else {}):
                    return None
            except Exception:  # noqa: BLE001
                if not getattr(tool, "changes", False):
                    return None
        from . import livenames

        return livenames.names(s.doc)

    def _refusal_extras(self, params, result):
        """A refusal of a call at the top level: the live names (now) when
        the call meant a change, and the orientation (whereYouAre) when it is
        the conversation's first answer (local-model runs, 23 Nov: call 1 was
        a refusal, and no answer oriented the model after it)."""
        s = self.session
        if s is None or getattr(s, "batch_now", None) is not None:
            return
        name = plain_name(self, params.get("name"))
        tool = self.tools.get(name)
        add = {}
        now = self._live_names(name, tool, params.get("arguments") or {})
        if now:
            add[LIVE_KEY] = now
        if not self._oriented and name != "session_state" and self.orient is not None:
            self._oriented = True
            try:
                add["whereYouAre"] = self.orient()
            except Exception:  # noqa: BLE001
                pass
        if not add:
            return
        content = result.get("content") or []
        if not content or content[0].get("type") != "text":
            return
        body = json.loads(content[0]["text"])
        if not isinstance(body, dict):
            return
        body.update(add)
        content[0]["text"] = compact(body)

    def _call_core(self, params):
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = self.tools.get(name)
        if tool is None and plain_name(self, name) in self.tools:
            name = plain_name(self, name)
            tool = self.tools[name]
        if tool is None:
            import difflib

            near = difflib.get_close_matches(str(name), list(self.tools), n=5, cutoff=0.5)
            prefix = str(name).split("_")[0] + "_"
            same = [n for n in self.tools if n.startswith(prefix)][:12] if not near else []
            if len(self.tools) <= 30:
                hint = f"the tools: {', '.join(self.tools)}"
            else:
                hint = f"near: {', '.join(near)}" if near else (f"its family: {', '.join(same)}" if same else "tool_groups lists them all")
            does = does_hits(self, name)
            if does:
                hint += f". By what it does, did you mean: {'; '.join(does)}? tool_find {{ tool: name }} gives its card"
            kh = kind_hint(self, name)
            if kh:
                hint = kh + ". Also " + hint
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
                # Measure before claim (agentlink/measured.py): the agent's own
                # document is saved only after its geometry was read since its
                # last change. In a batch or a fast block too: their calls come
                # through here, in order.
                said = s.measure_refusal() if hasattr(s, "measure_refusal") else None
                if said:
                    err = ToolError("invalid_input", said)
                    err.outcome = "not_started"
                    raise err
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
            if tool.name == "batch" and s is not None and getattr(s, "batch_now", None) is None:
                # The run's time line (AGENTLINK_TIME_LIMIT_MIN): once, on the
                # last health a batch's calls carry (agentlink/timelimit.py).
                try:
                    from . import health

                    health.time_on_batch(s, out)
                except Exception:
                    pass
            if s is not None and not as_job and (tool.changes or (tool.name == "batch" and getattr(s, "_applies_seq", 0) != changes0)):
                # Which tools apply to the document as it is now, read from their own leading checks: one short
                # line beside the health's next (agentlink/appliesnow.py). A batch's answer carries it once.
                try:
                    from . import appliesnow

                    with _ar.part("appliesNow"):
                        appliesnow.push(s, tool, out, count=tool.name != "batch")
                except Exception:
                    pass
                # The likely next steps as numbered, checked calls bound to the step (agentlink/options.py).
                try:
                    from . import options

                    with _ar.part("options"):
                        options.push(s, out)
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

                return self.refusal(e.code, staticbase.batch_hint(e.message), outcome=_outcome(tool, e), kind=getattr(e, "kind", None))
            msg = e.message
            try:
                msg = msg + example_words(tool, e.code, msg) + restart_words(self, e.code, args, msg)
            except Exception:  # noqa: BLE001 - words only
                pass
            return self.refusal(e.code, msg, outcome=_outcome(tool, e), left=getattr(e, "outcome_left", None), kind=getattr(e, "kind", None))
        except ValueError as e:
            return self.refusal("invalid_input", str(e), outcome=_outcome(tool, e), left=getattr(e, "outcome_left", None))
        except (SystemExit, KeyboardInterrupt) as e:
            # Code a tool ran (an add-on's, an approved cookbook entry's)
            # called sys.exit or raised KeyboardInterrupt: FreeCAD stays up.
            # Session.execute has already taken the step back.
            out_of = _outcome(tool, e)
            if out_of is None:
                kept = "it is a read, so nothing changed"
            else:
                kept = "nothing was kept" if out_of in ("rolled_back", "not_started") else "some objects stay (left)"
            what = "called exit" if isinstance(e, SystemExit) else "was interrupted (KeyboardInterrupt)"
            return self.refusal("failed", f"{name}: the add-on's code {what}; {kept}. FreeCAD and Agent Link go on.",
                                outcome=out_of, left=getattr(e, "outcome_left", None))
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            return self.refusal("failed", failed_words(name, e), _test_trace(), outcome=_outcome(tool, e), left=getattr(e, "outcome_left", None))
        if read_as and isinstance(out, dict):
            # Fields given by another common name (FIELD_ALIASES): what was read.
            out["readAs"] = read_as_words(read_as)
        if isinstance(out, dict) and not self._oriented and getattr(self.session, "batch_now", None) is None:
            # The first answer of a conversation says where the agent is,
            # once (a session_state is that read itself).
            self._oriented = True
            if name != "session_state" and self.orient is not None:
                try:
                    out["whereYouAre"] = self.orient()
                except Exception:  # noqa: BLE001
                    pass
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
        if isinstance(out, dict):
            # The live names last, so the answer ends on them (agentlink/livenames.py).
            try:
                now = self._live_names(name, tool, args)
                if now:
                    out[LIVE_KEY if LIVE_KEY not in out else LIVE_KEY_ELSE] = now
            except Exception:  # noqa: BLE001 - words only
                pass
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
    def refusal(code, message, trace=None, outcome=None, left=None, kind=None):
        err = set_kind({"code": code, "message": message}, kind)
        if outcome:
            # What the refused call left in the document: not_started (no
            # change was made: safe to call again), rolled_back (taken back
            # whole), cleanup_incomplete (left: the objects that stay).
            err["status"] = outcome
        if left:
            err["left"] = list(left)
        if trace:
            err["trace"] = trace
        return {"content": [{"type": "text", "text": compact({"error": err})}], "isError": True}


# ---- the same changing call again: refused ----------------------------------
#
# Blind QA, 24 Nov: a small local model sent the same sketch_add 13 times; each
# answered ok and added the same geometry again (DoF 32 → 274), and the repeat
# stop counts only refusals. Another sent a whole batch again, doc_new too, and
# had a second document. So a changing call with the same tool and the same
# arguments (canonical_call) as one of the last AGAIN_WINDOW changing calls that
# went through and made something (objects, sketch geometry, a document) is
# refused, and the refusal counts toward the repeat stop. Not for the tools
# where the same call again is normal (AGAIN_FREE); and an undo, a redo, a
# restore, a rollback, a removal or another document (AGAIN_CLEARS) clears the
# record, as does a new conversation. A record whose objects are gone counts
# no more. The person's calls (session.by "person") are not looked at.
# The same arguments are the same call only on the same thing (_same_target):
# the same document; the sketch the call took (named, or the default it would
# take now); with no sketch, nothing new made in the document since.

AGAIN_WINDOW = 10
# How the refusal of a call sent again starts (a batch's note reads it: tools.ran_before).
AGAIN_WORDS = "This call ran before with the same tool and arguments"
# The same call again is normal: the history (undo, redo …), recompute, saves,
# the view and the window, toggles and settings, runners of other calls (each
# of their calls is looked at itself), and a new sketch (a second sketch on
# the same plane, for the next feature, is a common step).
AGAIN_FREE = frozenset(("recompute", "doc_save", "doc_save_all",
                        "selection", "show", "workbench", "menu_run", "cmd_run", "dialog_answer", "queue_go", "batch", "fast", "pick",
                        "cookbook_run", "sketch_new"))
AGAIN_FREE_PREFIXES = ("view_", "camera_", "gui_", "window_", "pref_", "history_", "app_", "approve_")
# A call that went through of one of these, or of any history_ tool (undo,
# redo, a restore), clears the record.
AGAIN_CLEARS = frozenset(("doc_new", "doc_switch", "doc_close", "doc_open", "doc_revert", "feature_remove", "object_delete", "sketch_edit"))
# Looked at though they change no open document: a new document is made.
AGAIN_ALSO = frozenset(("doc_new",))


def _again_looked_at(server, name, args):
    """Whether a call of tool name with args is one the record looks at."""
    if not isinstance(name, str) or name in AGAIN_FREE or name.startswith(AGAIN_FREE_PREFIXES):
        return False
    if name in AGAIN_ALSO:
        return True
    tool = server.tools.get(name)
    if tool is None:
        return False
    try:
        return bool(tool.changes_for(args if isinstance(args, dict) else {}))
    except Exception:  # noqa: BLE001
        return bool(getattr(tool, "changes", False))


def _by_person(s):
    return s is not None and getattr(s, "by", "agent") == "person"


def _still_there(made):
    """Whether what a recorded call made is all still there."""
    try:
        import FreeCAD

        docs = FreeCAD.listDocuments()
        for kind, doc, name, _label, ids in made:
            d = docs.get(doc)
            if d is None:
                return False
            if kind == "object" and d.getObject(name) is None:
                return False
            if kind == "geometry":
                sk = d.getObject(name)
                if sk is None or len(getattr(sk, "Geometry", None) or ()) <= max(ids):
                    return False
        return True
    except Exception:  # noqa: BLE001 - not known: kept
        return True


def _made_words(made):
    """What a recorded call made, short: labels, "Sketch geometry 4-7", a
    document's name."""
    parts = []
    for kind, _doc, _name, label, ids in made:
        if kind == "document":
            parts.append(f"document {label}")
        elif kind == "geometry":
            ids = sorted(ids)
            parts.append(f"{label} geometry {ids[0]}" + (f"-{ids[-1]}" if len(ids) > 1 else ""))
        else:
            parts.append(label)
    return ", ".join(parts[:4] + ([f"{len(parts) - 4} more"] if len(parts) > 4 else []))


def _remove_words(made):
    """The tools that take back what a recorded call made."""
    out = []
    geo = [(label, sorted(ids)) for kind, _d, _n, label, ids in made if kind == "geometry"]
    if geo:
        out.append(f"sketch_edit {{ sketch: \"{geo[0][0]}\", delete: {geo[0][1]} }}")
    if any(m[0] == "object" for m in made):
        out.append("feature_remove (a feature of a body) or object_delete")
    if any(m[0] == "document" for m in made):
        out.append("doc_close")
    return " or ".join(out) or "history_undo"


def _token(doc):
    """What tells a document's objects apart from a later state: how many,
    and the newest one's name."""
    try:
        objs = list(doc.Objects)
        return [len(objs), objs[-1].Name if objs else None]
    except Exception:  # noqa: BLE001
        return None


def _default_sketch(s, doc):
    """The sketch a call that names none would take now (pd_common.sketch_of:
    the one open in edit, the one the agent made last, the only one), or None."""
    try:
        from .families import pd_common as pc

        sk = [o for o in doc.Objects if getattr(o, "TypeId", "") == "Sketcher::SketchObject"]
        for o in (pc.sketch_in_edit(doc), pc.made_sketch(s, doc)):
            if o is not None and any(o is x for x in sk):
                return o
        return sk[0] if len(sk) == 1 else None
    except Exception:  # noqa: BLE001
        return None


def _same_target(s, rec):
    """Whether a call with a recorded call's arguments acts on the same thing
    now: the same document; the same sketch (the named one, or the one it
    takes when none is named); else nothing made in the document since it."""
    if rec["name"] in AGAIN_ALSO:
        return True
    doc = getattr(s, "doc", None)
    if doc is None or getattr(doc, "Name", None) != rec.get("doc"):
        return False
    if rec.get("sketch"):
        if not rec.get("filled"):
            return True  # named in the arguments: the same sketch
        now = _default_sketch(s, doc)
        return now is not None and now.Name == rec["sketch"]
    return rec.get("token") is not None and _token(doc) == rec["token"]


def again_before(server, params):
    """Before a call: the refusal of a changing call sent again exactly
    (refusal), or what again_after needs to record it. None when the call
    is not looked at."""
    s = server.session
    name = plain_name(server, params.get("name"))
    if s is None or _by_person(s) or name in LIVE_NAMES_TOOLS:
        return None
    server._seq = getattr(server, "_seq", 0) + 1
    args = params.get("arguments") or {}
    if not _again_looked_at(server, name, args):
        return {"seq": server._seq, "name": name, "looked": False}
    call = canonical_call(args)
    ran = getattr(server, "_ran", None) or []
    for rec in reversed(ran):
        if rec["name"] == name and rec["call"] == call and rec["made"] and _same_target(s, rec) and _still_there(rec["made"]):
            ago = server._seq - rec["seq"]
            msg = (f"{AGAIN_WORDS}, and answered ok (made: {_made_words(rec['made'])}; "
                   f"calls since then: {ago - 1}). If it runs again, it adds the same again. Nothing was done. "
                   f"Change it, or remove what you do not want: {_remove_words(rec['made'])}.")
            return {"refusal": server.refusal("invalid_state", msg, outcome="not_started")}
    doc = getattr(s, "doc", None)
    try:
        names0 = {o.Name for o in doc.Objects} if doc is not None else set()
    except Exception:  # noqa: BLE001
        names0 = None
    return {"seq": server._seq, "name": name, "looked": True, "call": call, "doc": doc, "names0": names0}


def _answer_body(result):
    content = (result or {}).get("content") or []
    if not content or content[0].get("type") != "text":
        return None
    try:
        body = json.loads(content[0]["text"])
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


def again_after(server, params, result, seen):
    """After a call: the record cleared (AGAIN_CLEARS, a rollback) or the
    call put on it with what it made."""
    if not seen or seen.get("refusal") or not isinstance(result, dict) or result.get("isError"):
        return
    name = seen["name"]
    ran = getattr(server, "_ran", None)
    if ran is None:
        ran = server._ran = []
    body = _answer_body(result) if name in AGAIN_ALSO or seen.get("looked") else None
    if name in AGAIN_CLEARS or name.startswith("history_"):
        del ran[:]
        server._batch_kept = []
    if not seen.get("looked"):
        return
    s = server.session
    made = []
    doc = seen.get("doc")
    if name in AGAIN_ALSO:
        if body and isinstance(body.get("document"), str):
            made.append(("document", body["document"], body["document"], body.get("label") or body["document"], ()))
    elif doc is not None and doc is getattr(s, "doc", None) and seen.get("names0") is not None:
        try:
            made += [("object", doc.Name, o.Name, o.Label, ()) for o in doc.Objects if o.Name not in seen["names0"]]
        except Exception:  # noqa: BLE001
            pass
    if body and doc is not None and isinstance(body.get("added"), list) and isinstance(body.get("sketch"), str):
        sk = next((o for o in getattr(doc, "Objects", ()) if o.Label == body["sketch"] and o.TypeId == "Sketcher::SketchObject"), None)
        ids = [i for r in body["added"] if isinstance(r, dict) for i in (r.get("ids") or []) if isinstance(i, int)]
        if sk is not None and ids:
            made.append(("geometry", doc.Name, sk.Name, sk.Label, ids))
    filled, sk = getattr(server, "_acted", None) or ([], None)
    now = getattr(s, "doc", None)
    ran.append({"name": name, "call": seen["call"], "seq": seen["seq"], "made": made, "doc": getattr(now, "Name", None),
                "sketch": getattr(sk, "Name", None) if sk is not None else None, "filled": bool(filled), "token": _token(now) if now is not None else None,
                "step": body.get("step") if isinstance(body, dict) and isinstance(body.get("step"), int) else None})
    del ran[:-AGAIN_WINDOW]


def again_clear(server):
    """The record cleared: a batch's or a block's rollback took calls back."""
    if server is not None and getattr(server, "_ran", None):
        del server._ran[:]
    if server is not None:
        server._batch_kept = []


# ---- the same refusal again: a stop by progress ----------------------------
#
# The server, not the model, says when to stop (research on small local
# models, 22 Nov; it replaces the model-side "stop after 3 refusals" rule).
# Per tool (its plain name) it keeps the failing keys of the last refusal
# (failing_keys: what the message names, with the code) and the call as
# sent (canonical: the same call with its keys in another order is the same
# call). A refusal with other or fewer failing keys is progress: the count
# starts again. The same code and keys again (or the same call with the same
# words): the count goes up.
# At REPEAT_SAME the words say so and point to the card; at REPEAT_HINT
# they give something new to try; at REPEAT_STOP the kind is stop. A call of
# that tool that goes through clears it. Reads (FORGIVING_READS) never stop.

REPEAT_SAME = 2
REPEAT_HINT = 3
REPEAT_STOP = 5

# What a message names as the place of the problem, in the forms the
# refusals use: input.<field>, constraints[i], calls.<i>, step do.<n>.
_PLACES = re.compile(r"\b(input\.[A-Za-z_][\w]*|constraints\[\d+\]|calls\.\d+(?:\.arguments)?|(?:step )?do\.\d+(?:\.\w+)?)")
# Else the field the message starts with ("rectangle: …", "edges: …").
_LEAD = re.compile(r"^([A-Za-z_][\w.\[\]]{0,40}):\s")


def failing_keys(message):
    """The places a refusal's message names (_PLACES), in order, each once;
    else the field it starts with; else its words with the numbers taken
    out (so the same words with other numbers are the same problem)."""
    m = strip_kind(message)
    got = list(dict.fromkeys(x.replace("step ", "") for x in _PLACES.findall(m)))
    if got:
        return tuple(got)
    lead = _LEAD.match(m)
    if lead:
        return (lead.group(1),)
    return (re.sub(r"\d+(\.\d+)?", "#", m)[:120],)


def canonical_call(args):
    """The call's arguments as one text, keys sorted at every level."""
    try:
        return json.dumps(args if args is not None else {}, sort_keys=True, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return repr(args)


def _first_sentence(message):
    m = strip_kind(message)
    got = re.match(r"(.+?[.!?])(\s|$)", m, re.S)
    first = (got.group(1) if got else m).strip()
    return first if len(first) <= 200 else first[:197] + "…"


def example_words(tool, code, message):
    """" Example: edges: {…}." for a refusal of a bad input, when the tool's
    card data has a ready value of that input (examples.field_example), once;
    else "" (26 Nov QA: a refusal listed filter names, and the model did not
    find the card's ready form)."""
    if code != "invalid_input" or tool is None or "Example: " in str(message or ""):
        return ""
    props = (getattr(tool, "schema", None) or {}).get("properties") or {}
    field = None
    for k in failing_keys(message):
        got = re.match(r"(?:input\.)?([A-Za-z_]\w*)", k)
        if got and got.group(1) in props:
            field = got.group(1)
            break
    if field is None:
        return ""
    from . import examples

    val = examples.field_example(getattr(tool, "name", None), field)
    if val is None:
        return ""
    shown = compact(val)
    if len(shown) > 160 and isinstance(val, list) and val:
        shown = "[" + compact(val[0]) + ", …]"
    if len(shown) > 160 or shown in str(message):
        return ""
    return f" Example: {field}: {shown}."


# ---- FreeCAD started again (26 Nov QA) ---------------------------------------
#
# A client that goes on after the server (and its FreeCAD) started again
# names documents and objects that are gone: "no object 'LidBody'" did not
# say why. The process cannot know the conversation before it; it can know
# that it started a short time ago and that no open document has anything
# in it yet.

STARTED = time.time()
RESTART_WINDOW = 300.0  # seconds after the start that a missing name is read as from before it
NAME_FIELDS = ("document", "doc", "body", "sketch", "object", "feature", "objects", "what", "of")


def restart_words(server, code, args, message=""):
    """" FreeCAD started at HH:MM and nothing is made in it yet: documents
    and objects from before then are not open." for a refusal that names a
    document or an object the call gave, while this FreeCAD started less
    than RESTART_WINDOW ago and no open document has an object; else ""."""
    if code not in ("not_found", "invalid_input", "invalid_state") or time.time() - STARTED > RESTART_WINDOW:
        return ""
    if not isinstance(args, dict):
        return ""
    names = []
    for k in NAME_FIELDS:
        v = args.get(k)
        names += [x for x in (v if isinstance(v, list) else [v]) if isinstance(x, str) and x.strip()]
    # The refusal names one of them: it is that name that is not there.
    if not any(n.split(".")[0] in str(message or "") for n in names):
        return ""
    try:
        import FreeCAD as _fc

        if any(list(d.Objects) for d in _fc.listDocuments().values()):
            return ""
    except Exception:  # noqa: BLE001 - not known: no words
        return ""
    # True also on a first start: the words say when it started, not that it started again.
    return (f" FreeCAD started at {time.strftime('%H:%M', time.localtime(STARTED))} and nothing is made in it yet: "
            "documents and objects from before then are not open (session_state lists what is open).")


def _field(keys):
    """The input field a key names (input.depth → depth), else None."""
    for k in keys:
        if k.startswith("input."):
            return k[len("input."):]
    return None


def _try_next(server, name, keys, n, card):
    """The words at REPEAT_HINT and after: the place again, and something
    new to try (the card's example, its value of the field when it has one)."""
    place = keys[0] if keys and len(keys[0]) <= 60 else "the same problem"
    words = f" Refused the same way {n} times: {place} is still wrong."
    example = None
    try:
        from . import examples

        if examples.load().get(name):
            example = (examples.for_tool(name, {}) or {}).get("example")
    except Exception:  # noqa: BLE001
        example = None
    field = _field(keys)
    if example is not None:
        val = (example.get("arguments") or {}).get(field) if field else None
        if val is not None:
            shown = compact(val)
            words += f" Try this: the card's example gives {field} as {shown if len(shown) <= 160 else shown[:157] + '…'}. Use that form."
        else:
            words += f" Try this: copy the card's example ({card}) and change only its values."
    else:
        words += f" Try this: read the form of {field or place} on the card ({card}), or use another tool for this step."
    left = REPEAT_STOP - n
    if left > 0:
        words += f" After {left} more {'try' if left == 1 else 'tries'} with no progress, the server tells you to stop."
    return words


def repeat_words(server, name, result, args=None):
    """The progress-based stop (see above) applied to a tools/call result,
    in place. Words only on a refusal; a call that went through clears."""
    state = getattr(server, "_repeats", None)
    if state is None:
        state = server._repeats = {}
    name = plain_name(server, name) if isinstance(name, str) else name
    if getattr(server, "_repeat_quiet", False):
        # A call of a batch with stopOnError: false that runs after an
        # earlier call of it was refused: its refusal most often follows
        # from that one, so it is not counted (24 Nov QA: cascades).
        return
    if not result.get("isError"):
        state.pop(name, None)
        return
    content = result.get("content") or []
    if not content or content[0].get("type") != "text":
        return
    body = json.loads(content[0]["text"])
    err = body.get("error") if isinstance(body, dict) else None
    if not isinstance(err, dict):
        return
    msg = strip_kind(err.get("message", ""))
    keys = failing_keys(msg)
    code = err.get("code")
    call = canonical_call(args)
    last = state.get(name)
    progress = ""
    # The same refusal: the same code and the same failing keys. The same
    # call counts only when its words (numbers out) are the same too: the
    # document can change under the same call, and a new reason is progress
    # (1i, 24 Nov).
    words = re.sub(r"\d+(\.\d+)?", "#", strip_kind(msg))
    if last is not None and last["code"] == code and (last["keys"] == keys or (last["call"] == call and last.get("words") == words)):
        n = last["n"] + 1
        first = last["first"]
    else:
        n = 1
        first = msg
        if last is not None and last["code"] == code and set(keys) < set(last["keys"]) and _PLACES.match(last["keys"][0]):
            fixed = len(set(last["keys"]) - set(keys))
            progress = f" Progress: {fixed} of {len(last['keys'])} named problems fixed."
    state[name] = {"code": code, "keys": keys, "call": call, "words": words, "n": n, "first": first}
    kind = err.get("kind") or refusal_kind(code, msg)
    if progress:
        err["message"] = msg + progress
        set_kind(err, kind)
        content[0]["text"] = compact(body)
        return
    if n < REPEAT_SAME:
        return
    err["repeat"] = n
    card = f'tool_find {{ tool: "{name}" }}' if name and name in server.tools else "tool_find { words }"
    if n >= REPEAT_STOP and name not in FORGIVING_READS:
        err["message"] = f"{STOP_MARK}{REPEAT_STOP} tries of {name}. Do not call it again. Report it: {_first_sentence(first)}"
        set_kind(err, "stop")
    elif kind == "fixable":
        if n == REPEAT_SAME:
            try:
                from . import examples

                has_ex = bool(examples.load().get(name))
            except Exception:  # noqa: BLE001
                has_ex = False
            msg += f" This is the same refusal as before: change what it names. {card} gives the card" + (" and a worked example." if has_ex else ".")
        else:
            msg += _try_next(server, name, keys, n, card)
        err["message"] = msg
        set_kind(err, kind)
    content[0]["text"] = compact(body)


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
