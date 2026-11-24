# SPDX-License-Identifier: LGPL-2.1-or-later
"""State → options → checked run (efficiency design A, 22 Nov).

After every changing call, and in session_state, the likely next steps come
as numbered options: ready calls, bound to the step number.

    step 76: 1 pd_pad sketch=Sketch001 body=Body ask length mm;
             2 pd_pocket sketch=Sketch001 body=Body ask length mm|through_all;
             3 sketch_new body=Body plane=XY or XZ or YZ

Each option has the tool, the arguments the document's state settles, the
open inputs (ask) and why. They come from the same rules as the "next"
hint (data/nexthint.json): a suggested tool with "args" is an option. Its
arguments are filled from the real names the state gives (nexthint.facts():
bodyName, sketchName, editSketch, pickedEdges …) by the hub's checked
expression language (agentlink/expr.py; never eval). The live choices (the
real bodies, sketches, picked faces) are in the option, never in the tool
list: tools/list does not change with the document.

Every option is checked before it is shown: its filled arguments (with
each ask's sample in its place) by the tool's own schema and its leading
checks (agentlink/needs.py, as tool_groups { needs, arguments } reads
them). An option they refuse is left out. A refusal that names an ask
without a sample does not count (the input is the person's to give). A
tool whose checks cannot be read dry (a Python tool) is not refused by
them, and stays.

pick { option, fill } runs one through the normal call path (the echo, the
health check, the undo step): fill gives the asks, by name ({ length: 4 })
or in order ("4mm", [4]). Plain text works too: pick { option: "1, 4mm" },
"2, through_all". A number with a unit is read in the ask's unit (mm or
deg: "1 in" is 25.4 mm). When the document is no longer at the options'
step, pick refuses and gives the new options.

Cheap and never in the way: the options are built from cheap reads and at
most BUDGET_MS of checks; on any error they are left out, and a call never
fails for them. The switch: preference Mod/AgentLink Options (bool, on)
and AGENTLINK_OPTIONS=off (for the A/B benchmark).
"""
import copy
import json
import os
import re
import time

from . import expr, nexthint

PREFS = "User parameter:BaseApp/Preferences/Mod/AgentLink"
MAX_OPTIONS = 4
MAX_CHOICES = 4
MAX_CANDIDATES = 8      # suggestions read before the checks pick the first MAX_OPTIONS
BUDGET_MS = 120         # every check of one build together
ONE_S = 0.05            # one option's check
MAX_LINE = 360          # the line a changing answer carries
MAX_VALUE = 40          # one argument's value in the line
PICK_HOW = "pick { option: 1, fill: { length: 4 } } runs option 1; the text \"1, 4mm\" also works"
# A value for an ask with no sample of its own, by its name (pick_how).
ASK_SAMPLE = {"name": "Part"}

_UNITS = {"mm": {"": 1.0, "mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "inch": 25.4, '"': 25.4},
          "deg": {"": 1.0, "deg": 1.0, "°": 1.0}}
_NUM = re.compile(r'^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*(mm|cm|m|inch|in|"|deg|°)?\s*$')


# ---- the switch ---------------------------------------------------------------------------

def enabled():
    """Whether options are built and pick runs: AGENTLINK_OPTIONS=off, or the
    Options preference (Mod/AgentLink, bool, on), turns them off."""
    if os.environ.get("AGENTLINK_OPTIONS", "on").strip().lower() in ("0", "false", "off", "no"):
        return False
    try:
        import FreeCAD

        return bool(FreeCAD.ParamGet(PREFS).GetBool("Options", True))
    except Exception:  # noqa: BLE001 - no FreeCAD here, or a stand-in without settings
        return True


# ---- the state ----------------------------------------------------------------------------

def key(session):
    """What the options are bound to: the step, the undo count of the
    session, the document and how many objects it holds."""
    doc = getattr(session, "doc", None)
    try:
        n = len(doc.Objects)
    except Exception:  # noqa: BLE001
        n = None
    return [len(getattr(session, "steps", None) or ()), getattr(session, "tx", None), str(getattr(doc, "Name", "")), n]


def step(session):
    return len(getattr(session, "steps", None) or ())


def _read(session):
    """(facts, state) of the document now, from cheap reads (tools.now_state
    and nexthint.facts); None while a dialog is in front (answering it is
    the next step)."""
    from . import tools

    doc = getattr(session, "doc", None)
    state = tools.now_state(doc, ())
    gui = None
    if state.get("window"):
        import FreeCADGui as gui

        try:
            if tools._modal_up():
                return None
        except Exception:  # noqa: BLE001
            pass
        try:
            o = getattr(gui.ActiveDocument.getInEdit(), "Object", None)
            if o is not None and o.isDerivedFrom("Sketcher::SketchObject"):
                state["sketch"] = {"name": str(o.Label), "obj": str(o.Name), "dof": int(o.DoF)}
        except Exception:  # noqa: BLE001
            pass
    state["gui"] = gui
    return nexthint.facts(doc, state, gui), state


# ---- building ------------------------------------------------------------------------------

def _value(v, facts):
    if isinstance(v, str) and v.startswith("="):
        return expr.evaluate(v[1:], {"facts": facts})
    return copy.deepcopy(v)


def suggestions(facts, table=None):
    """[(pick, item)]: the ranked suggestions (nexthint.rank) whose rule item
    has args, likeliest first."""
    table = nexthint.rules() if table is None else table
    out = []
    for p in nexthint.rank(facts, table, limit=nexthint.MAX_PICKS):
        rule = table.get(p["rule"]) or {}
        item = next((s for s in rule.get("suggest") or () if s.get("tool") == p["tool"]), None)
        if isinstance(item, dict) and isinstance(item.get("args"), dict):
            out.append((p, item))
    return out


def fill(item, facts):
    """(args, ask, choices) of one suggestion against the facts. An
    argument that comes out None is left out (the tool's own default)."""
    args = {}
    for k, v in item["args"].items():
        got = _value(v, facts)
        if got is not None and got != []:
            args[k] = got
    choices = {}
    for k, v in (item.get("choices") or {}).items():
        got = _value(v, facts)
        if not isinstance(got, list):
            continue
        got = [x for x in got if isinstance(x, (str, int, float)) and not isinstance(x, bool)]
        if k in args and args[k] in got:
            got = [args[k]] + [x for x in got if x != args[k]]
        if len(got) > 1:
            choices[k] = got[:MAX_CHOICES]
    ask = [dict(a) for a in item.get("ask") or ()]
    return args, ask, choices


def check(server, name, args, ask, budget=ONE_S):
    """Whether an option may be shown: its filled arguments, with each ask's
    sample in its place, pass the tool's own schema and leading checks
    (needs.of_tool). A refusal that names an ask without a sample does not
    count; a tool whose checks cannot be read dry is not refused by them."""
    from . import needs
    from .protocol import ToolError, check_input

    t = (getattr(server, "tools", None) or {}).get(name)
    if t is None:
        return False
    trial = copy.deepcopy(args)
    open_ = []
    for a in ask:
        if "sample" in a:
            trial.setdefault(a["arg"], copy.deepcopy(a["sample"]))
        else:
            open_.append(a["arg"])
    schema = dict(getattr(t, "schema", None) or {})
    if open_:
        schema["required"] = [k for k in schema.get("required") or () if k not in open_]
    try:
        check_input(schema, trial, name)
    except ToolError:
        return False
    r = needs.of_tool(t, trial, budget=budget)
    if r.get("applies") is False:
        words = " ".join(str(x.get("words", "")) for x in r.get("wouldRefuse") or ())
        return any(re.search(r"\b" + re.escape(k) + r"\b", words) for k in open_)
    return True


def theirs_first(session, server):
    """The doc_new option, when the document in front is the person's (not
    one an agent made), or None."""
    try:
        doc = getattr(session, "doc", None)
        if doc is None or "doc_new" not in server.tools or doc.Name in (getattr(session, "agent_docs", None) or ()):
            return None
        return {"n": 1, "tool": "doc_new", "args": {}, "ask": [{"arg": "name"}],
                "why": f"new work in a document of its own: {doc.Label} is the person's"}
    except Exception:  # noqa: BLE001
        return None


def build(session, facts=None, state=None, table=None):
    """{ step, key, list: [{ n, tool, args, ask, choices, why }] } — at most
    MAX_OPTIONS, every one checked — or None (switched off, a dialog in
    front, nothing to offer, or any error). Never raises."""
    try:
        if not enabled():
            return None
        server = getattr(session, "server", None)
        if server is None:
            return None
        if facts is None:
            got = _read(session)
            if got is None:
                return None
            facts, state = got
        cands = suggestions(facts, table)[:MAX_CANDIDATES]
        # The person's document in front: a document of its own first, so the
        # likeliest pick is not a change to their file (owner, 22 Nov).
        theirs = theirs_first(session, server)
        if not cands:
            return {"step": step(session), "key": key(session), "list": [theirs]} if theirs else None
        gui = (state or {}).get("gui")
        if gui is not None:
            try:
                from . import tools

                tools.ask_active(gui, nexthint.commands_of([p for p, _ in cands]), state)
            except Exception:  # noqa: BLE001
                pass
        avail = {id(p) for p in nexthint.available([p for p, _ in cands], state, lambda n: n in server.tools, n=len(cands))}
        deadline = time.time() + BUDGET_MS / 1000.0
        out = [theirs] if theirs else []
        for p, item in cands:
            if id(p) not in avail:
                continue
            now = time.time()
            if now >= deadline:
                break
            try:
                args, ask, choices = fill(item, facts)
                if not check(server, p["tool"], args, ask, min(ONE_S, deadline - now)):
                    continue
            except Exception:  # noqa: BLE001 - one bad option never stops the others
                continue
            opt = {"n": len(out) + 1, "tool": p["tool"], "args": args, "why": p.get("why") or ""}
            if ask:
                opt["ask"] = ask
            if choices:
                opt["choices"] = choices
            out.append(opt)
            if len(out) >= MAX_OPTIONS:
                break
        if not out:
            return None
        return {"step": step(session), "key": key(session), "list": out}
    except Exception:  # noqa: BLE001 - the options never fail the call they follow
        return None


# ---- the words ------------------------------------------------------------------------------

def _val(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return f"{v:g}"
    if isinstance(v, str) and re.search(r"[\s,;=]", v):
        return json.dumps(v, ensure_ascii=False)  # a label with a space ("Sketch 2") stays one value in the line
    if isinstance(v, (int, str)):
        return str(v)
    if isinstance(v, list):
        return "[" + ",".join(_val(x) for x in v) + "]"
    return json.dumps(v, separators=(",", ":"), ensure_ascii=False)


def ask_words(a):
    """"length mm|through_all"."""
    return " ".join(x for x in (a["arg"], a.get("unit")) if x) + "".join(f"|{w}" for w in (a.get("or") or {}))


def option_words(o):
    """"1 pd_pad sketch=Sketch001 body=Body ask length mm"."""
    parts = [str(o["n"]), o["tool"]]
    choices = o.get("choices") or {}
    for k, v in o["args"].items():
        w = _val(v)
        if k in choices:
            w += "".join(f" or {_val(x)}" for x in choices[k][1:])
        parts.append(f"{k}={w[:MAX_VALUE]}")
    for k, v in choices.items():
        if k not in o["args"]:
            parts.append(f"{k}={' or '.join(_val(x) for x in v)}"[:MAX_VALUE])
    if o.get("ask"):
        parts.append("ask " + ", ".join(ask_words(a) for a in o["ask"]))
    return " ".join(parts)


def line(opts, limit=MAX_LINE):
    """The one short line a changing answer carries: "step 76: 1 … ; 2 …".
    Options at the end are left out to keep it under limit."""
    if not opts or not opts.get("list"):
        return None
    head = f"step {opts['step']}: "
    words = [option_words(o) for o in opts["list"]]
    while words and len(head) + len("; ".join(words)) > limit:
        words.pop()
    if not words:
        return None
    return head + "; ".join(words)


def public(opts):
    """The options as session_state and a stale pick's refusal give them."""
    if not opts:
        return None
    rows = []
    for o in opts["list"]:
        r = {"n": o["n"], "tool": o["tool"], "args": o["args"]}
        if o.get("ask"):
            r["ask"] = [ask_words(a) for a in o["ask"]]
        if o.get("choices"):
            r["choices"] = o["choices"]
        if o.get("why"):
            r["why"] = o["why"]
        rows.append(r)
    return {"step": opts["step"], "list": rows, "pick": pick_how(opts)}


def pick_how(opts, static=None):
    """How to run the first option, made from that option itself (its own
    ask and that ask's sample), so the example fits the option it names
    (local-model runs, 23 Nov: option 1 was doc_new, which asks for name,
    and the fixed example gave length). PICK_HOW when there is no option.
    static: pick is not listed (the static list, the default): the example
    is a batch call, which a client that sends only listed tools can make;
    classic keeps the short form (design 1h, 24 Nov). None: read the mode."""
    rows = (opts or {}).get("list") or []
    if static is None:
        static = pick_unlisted()
    if not rows:
        return as_batch(PICK_ARGS, 1, PICK_TAIL) if static else PICK_HOW
    o = rows[0]
    n = o.get("n", 1)
    ask = o.get("ask") or []
    if not ask:
        args, tail = f"{{ option: {n} }}", ""
    else:
        a = ask[0]
        v = a.get("sample", ASK_SAMPLE.get(a.get("arg")))
        if v is None:
            args, tail = f"{{ option: {n}, fill: {{ {a['arg']}: your value }} }}", ""
        else:
            args = f"{{ option: {n}, fill: {{ {a['arg']}: {json.dumps(v, ensure_ascii=False)} }} }}"
            tail = ""
            if not isinstance(v, bool) and isinstance(v, (int, float, str)):
                text = f"{_val(v)}{a.get('unit') or ''}" if a.get("unit") == "mm" else _val(v)
                tail = (f"; option: \"{n}, {text}\" also works" if static else f"; the text \"{n}, {text}\" also works")
    return as_batch(args, n, tail) if static else f"pick {args} runs option {n}{tail}"


PICK_ARGS = "{ option: 1, fill: { length: 4 } }"
PICK_TAIL = "; option: \"1, 4mm\" also works"


def as_batch(args, n, tail=""):
    """The pick call inside a batch: batch { calls: [{ tool: "pick", arguments: … }] }."""
    return f'batch {{ calls: [{{ tool: "pick", arguments: {args} }}] }} runs option {n}{tail}'


def pick_unlisted():
    """True when the static list is on (staticbase.mode, the default): pick
    is then found by name, not listed. Never raises."""
    try:
        from . import staticbase

        return staticbase.mode() == "static" and "pick" not in staticbase.BASE + staticbase.FAST
    except Exception:  # noqa: BLE001
        return False


# ---- after a call, and in session_state ----------------------------------------------------

def remember(session, opts):
    try:
        session._options = opts
    except Exception:  # noqa: BLE001
        pass
    return opts


def push(session, out):
    """After a changing call that answered: the options built and kept on
    the session, and their line put beside the health's next (on a batch's
    answer itself: never inside a batch). Never raises."""
    try:
        if getattr(session, "batch_now", None) is not None or not isinstance(out, dict) or not enabled():
            return out
        ln = line(remember(session, build(session)))
        if not ln:
            return out
        h = out.get("health")
        if isinstance(h, dict):
            h["options"] = ln
        else:
            out["options"] = ln
    except Exception:  # noqa: BLE001
        pass
    return out


def state_field(session):
    """{ options } for session_state, or {}. Never raises."""
    try:
        got = public(remember(session, build(session)))
        return {"options": got} if got else {}
    except Exception:  # noqa: BLE001
        return {}


# ---- pick ------------------------------------------------------------------------------------

def _word(w):
    return re.sub(r"[\s-]+", "_", str(w).strip().lower())


def read_value(a, v):
    """{ arg: value } for one ask from what was given: a word of its "or",
    a number (with a unit: read in the ask's unit), or the value as it is."""
    from .protocol import ToolError

    words = {_word(k): x for k, x in (a.get("or") or {}).items()}
    if isinstance(v, str) and _word(v) in words:
        return copy.deepcopy(words[_word(v)])
    unit = a.get("unit")
    if isinstance(v, str):
        m = _NUM.match(v)
        if m:
            num, u = float(m.group(1)), (m.group(2) or "")
            if unit:
                factors = _UNITS[unit]
                if u not in factors:
                    raise ToolError("invalid_input", f"{a['arg']}: {v!r} — a number in {unit}" + (", or " + " | ".join(a["or"]) if a.get("or") else "") + ".")
                num *= factors[u]
            elif u:
                raise ToolError("invalid_input", f"{a['arg']}: {v!r} — a plain number, no unit.")
            v = int(num) if num == int(num) and not unit else num
        else:
            v = v.strip()
    return {a["arg"]: v}


def parse_text(text):
    """"1, 4mm" -> (1, ["4mm"]); "2, through_all" -> (2, ["through_all"])."""
    m = re.match(r"^\s*(\d+)\s*[,;:]?\s*(.*)$", str(text), re.S)
    if not m:
        return None, []
    rest = [x.strip() for x in m.group(2).split(",") if x.strip()]
    return int(m.group(1)), rest


def _stale(session, words):
    """A refusal that carries the options of the document now."""
    from .protocol import ToolError

    fresh = remember(session, build(session))
    e = ToolError("invalid_state", words + (" The options now are in options." if fresh else " There are no options now: session_state reads the document."))
    e.options = public(fresh)
    return e


def resolve(session, a):
    """(option, args) of a pick, or a ToolError (one of a stale pick carries
    the options now in .options)."""
    from .protocol import ToolError

    if not enabled():
        raise ToolError("unavailable", "options are off (the Options preference, or AGENTLINK_OPTIONS=off): call the tool itself.")
    if not isinstance(a, dict):
        raise ToolError("invalid_input", "arguments: an object.")
    other = [k for k in a if k not in ("option", "fill")]
    if other:
        raise ToolError("invalid_input", f"input.{other[0]}: not a known field — the fields here: option, fill")
    n, given = a.get("option"), a.get("fill")
    if isinstance(n, str):
        n, values = parse_text(n)
        if n is None:
            raise ToolError("invalid_input", "option: a number (1-4), or the text \"1, 4mm\".")
        if values:
            if given is not None:
                raise ToolError("invalid_input", "fill: give the values in option's text or in fill, not both.")
            given = values
    if isinstance(n, bool) or not isinstance(n, int):
        raise ToolError("invalid_input", "option: a number (1-4), or the text \"1, 4mm\".")
    opts = getattr(session, "_options", None)
    if not opts:
        raise _stale(session, "There were no options given before this pick.")
    if opts.get("key") != key(session):
        raise _stale(session, f"The options of step {opts['step']} are old: the document is at step {step(session)} now, or it changed.")
    o = next((x for x in opts["list"] if x["n"] == n), None)
    if o is None:
        raise ToolError("invalid_input", f"option {n}: step {opts['step']} has options 1 to {len(opts['list'])}.")
    args = copy.deepcopy(o["args"])
    asks = o.get("ask") or []
    by = {x["arg"]: x for x in asks}
    filled = set()
    if isinstance(given, str):
        given = [x.strip() for x in given.split(",") if x.strip()]
    elif isinstance(given, (int, float)) and not isinstance(given, bool):
        given = [given]
    if isinstance(given, list):
        if len(given) > len(asks):
            raise ToolError("invalid_input", f"fill: {len(given)} values, option {n} asks {len(asks)}" + (f" ({', '.join(ask_words(x) for x in asks)})." if asks else "."))
        for x, v in zip(asks, given):
            args.update(read_value(x, v))
            filled.add(x["arg"])
    elif isinstance(given, dict):
        for k, v in given.items():
            if k in by:
                args.update(read_value(by[k], v))
                filled.add(k)
            else:
                args[k] = copy.deepcopy(v)  # a choice, or another input: the tool's own schema checks it
    elif given is not None:
        raise ToolError("invalid_input", "fill: { arg: value }, a list of values in the asks' order, or the text \"4mm\".")
    missing = [x for x in asks if x["arg"] not in filled and x["arg"] not in args
               and not any(w in filled or set(v) & set(args) for w, v in (x.get("or") or {}).items())]
    if missing:
        raise ToolError("invalid_input", f"option {n} ({o['tool']}) asks {', '.join(ask_words(x) for x in missing)}: "
                                         f"pick {{ option: {n}, fill: {{ {missing[0]['arg']}: … }} }}, or the text \"{n}, …\".")
    return o, args


def pick_call(server, params):
    """A tools/call of pick: the option's call run through the normal path
    (server.call: the echo, the health check, the undo step), with picked
    on its answer. A refused pick answers as any refusal does; a stale one
    carries the options now."""
    from .protocol import ToolError, compact, set_kind

    s = getattr(server, "session", None)
    try:
        o, args = resolve(s, params.get("arguments") or {})
    except ToolError as e:
        err = set_kind({"code": e.code, "message": e.message})
        if getattr(e, "options", None):
            err["options"] = e.options
        return {"content": [{"type": "text", "text": compact({"error": err})}], "isError": True}
    result = server.call({"name": o["tool"], "arguments": copy.deepcopy(args)})
    try:
        c = result["content"][0]
        body = json.loads(c["text"])
        if isinstance(body, dict):
            c["text"] = compact({"picked": option_words({"n": o["n"], "tool": o["tool"], "args": args}), **body})
    except Exception:  # noqa: BLE001 - the answer stays as the tool gave it
        pass
    return result


def pick_fn(a):
    """pick's own handler: reached only where a call does not pass through
    Server.call (a job)."""
    from .protocol import ToolError

    raise ToolError("invalid_input", "pick runs as a call of its own, or in a batch: not as a job.")
