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
import time
import traceback

PROTOCOL = "2025-06-18"




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


def bad(msg):
    """The usual refusal: invalid_input with msg."""
    return ToolError("invalid_input", msg)


class Tool:
    def __init__(self, name, description, schema, fn, changes=False, group="core", reads=None, activity=None):
        self.name = name
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


def check_input(schema, args):
    """Unknown keys and missing required ones refused by name, as the
    answers name them: what the agent got wrong and what is allowed."""
    if not isinstance(args, dict):
        raise ToolError("invalid_input", "arguments: an object.")
    props = schema.get("properties", {})
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
        return [t for t in self.tools.values() if (self.groups is None or t.group in self.groups) and not getattr(t, "alias_of", None)]

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

    def handle(self, msg):
        """One message in; the reply, or None for a notification."""
        mid = msg.get("id")
        method = msg.get("method")
        if method is None:
            return None
        try:
            if method == "initialize":
                result = {
                    "protocolVersion": PROTOCOL,
                    "capabilities": {"tools": {"listChanged": True}, **({"resources": {}} if self.resources else {})},
                    "serverInfo": {"name": self.name, "version": self.version},
                    "instructions": self.instructions,
                }
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": [t.listing() for t in self.listed()]}
                self.note_listed()
                if self.meter is not None:
                    self.meter.list(result["tools"], self.instructions)
            elif method == "resources/list" and self.resources:
                result = {"resources": self.resources.list()}
            elif method == "resources/read" and self.resources:
                result = {"contents": [self.resources.read((msg.get("params") or {}).get("uri", ""))]}
            elif method == "tools/call":
                result = self.call(msg.get("params") or {})
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
        before = (getattr(s, "tx", None), getattr(s, "doc", None)) if s is not None else None
        from . import around

        with _as_user(s), _acting(s), _hang_trace(s, params.get("name")):
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
                img = next((c for c in content if c.get("type") == "image"), None)
                import base64

                data = base64.b64decode(img["data"][:64]) if img else None
                err = None
                if result.get("isError"):
                    err = (json.loads(text).get("error") or {}).get("code", "error")
                self.meter.call(str(params.get("name")), compact(params.get("arguments") or {}), text, data, err, (time.time() - t0) * 1000)
            except Exception:
                pass
            around.add("meter", time.time() - tm)
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
        try:
            # background: true on any read the tool does not take itself:
            # run it as a job (agentlink/jobs.py).
            asked = False
            if "background" in args and "background" not in (tool.schema.get("properties") or {}):
                asked = args.pop("background") in (True, "true")
            from . import around as _ar

            check_input(tool.schema, args)
            if self.guard is not None:
                with _ar.part("guard"):
                    self.guard(tool, args)
            from . import jobs

            s = self.session
            as_job = False
            if s is not None:
                with _ar.part("jobCheck"):
                    jobs.guard_change(tool, args, s)
                    as_job = jobs.wanted(tool, args, s, asked=asked)
            elif asked:
                raise ToolError("invalid_input", "background: a job needs a session.")
            if asked and not as_job:
                # Inside a batch nothing runs as a job (the batch is one
                # answer): said so, where the general reason read as if a
                # plain read (meshobj_info) were not one — and by what the
                # call is (jobs.background_refusal): a read that writes a
                # file belongs in the batch's order, a change is never a job.
                raise ToolError("invalid_input", jobs.background_refusal(tool, args, getattr(s, "batch_now", None) is not None))
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
                if gate is not None:
                    gate.after(tool, args, False)
                raise
            if gate is not None:
                # A job logs its own time when it ends (the call may have
                # answered before it did).
                with _ar.part("gateAfter"):
                    gate.after(tool, args, not as_job)
            if s is not None and not as_job:
                jobs.note_slow(tool, args, s, time.time() - t0)
            if self.on_call is not None:
                try:
                    with _ar.part("onCall"):
                        self.on_call(tool, args)
                except Exception:
                    pass
        except ToolError as e:
            return self.refusal(e.code, e.message)
        except ValueError as e:
            return self.refusal("invalid_input", str(e))
        except Exception as e:
            traceback.print_exc(file=sys.stderr)
            return self.refusal("failed", failed_words(name, e), _test_trace())
        image = None
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
        if jobs.wait_for(job, jobs.JOB_WAIT if wait is None else wait):
            if job["status"] == "failed":
                raise ToolError(job["error"]["code"], job["error"]["message"])
            out = job["result"]
            if isinstance(out, dict):
                out = dict(out)
                out.setdefault("job", job["job"])
            return out
        return {**jobs.summary(job), "note": f"{tool.name} is still running (past {jobs.JOB_WAIT:.0f} s, longer than a call may wait): it goes on as a job; nothing else was changed."}

    @staticmethod
    def refusal(code, message, trace=None):
        err = {"code": code, "message": message}
        if trace:
            err["trace"] = trace
        return {"content": [{"type": "text", "text": compact({"error": err})}], "isError": True}


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
    """While a call runs: should it still be running after 60 s, Python's
    own stack of every thread is written to <outDir>/crash/hang-<tool>.txt
    (faulthandler: it writes from a watchdog thread, so a call stuck inside
    FreeCAD on the GUI thread still leaves where it was). A call that ends
    in time leaves nothing. Nested calls (a batch's) each re-arm it; the
    outer one is armed again as an inner one ends."""

    _stack = []

    def __init__(self, session, name):
        self.session, self.name, self.f = session, str(name or "call"), None

    def __enter__(self):
        try:
            import faulthandler
            import os
            import re

            out = getattr(self.session, "out_dir", None)
            if not out or self.name == "batch":
                return self
            d = os.path.join(out, "crash")
            os.makedirs(d, exist_ok=True)
            self.path = os.path.join(d, "hang-" + re.sub(r"[^A-Za-z0-9_]", "_", self.name) + ".txt")
            self.f = open(self.path, "w")
            faulthandler.dump_traceback_later(60, repeat=False, file=self.f)
        except Exception:
            self.f = None
        return self

    def __exit__(self, *exc):
        if self.f is None:
            return False
        try:
            import faulthandler
            import os

            faulthandler.cancel_dump_traceback_later()
            empty = self.f.tell() == 0
            self.f.close()
            if empty:
                os.remove(self.path)
        except Exception:
            pass
        return False


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


def serve_lines(server, readline, write):
    """Read a message a line until the input ends; write each reply a line."""
    while True:
        line = readline()
        if not line:
            return
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            write(compact({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "not JSON"}}) + "\n")
            continue
        reply = server.handle(msg)
        if reply is not None:
            write(compact(reply) + "\n")
        while server.outbox:
            write(compact(server.outbox.pop(0)) + "\n")
