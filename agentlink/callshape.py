# SPDX-License-Identifier: LGPL-2.1-or-later
"""One flat step for run, batch and fast (owner decisions, 26 and 27 Nov):

  { "tool": "pd_pad", "sketch": "Sketch", "length": 6 }

All three tools take the same list: { "calls": [ step, … ] } (27 Nov: a
client can force additionalProperties: false on the top level of a tool, so
the steps stand one level down). run runs the first step only.

The tool's name is tool. Its inputs stand beside it, by the names on its
card. There is no arguments wrapper.

Three keys of a step are the step's own and are never a tool's input:
tool, each and writeTo (RESERVED).

  * each: { "x": [15, 45] } runs the step once for each value, in order.
    "$x" in the inputs (also inside a list) is that value. One variable.
    Each pass is one call. A writeTo does not go with each.
  * writeTo: a .json file for the call's whole answer. A batch step only.
  * In run, each runs the step as a batch of its passes (the answer is
    batch's), as before 27 Nov.

The old forms are refused with the new form in the words (rule R5: no
alias, nothing is read silently): { tool, arguments }, { call, … }, do,
as, when, then, else, let, try, choose, and each with in and steps.
arguments is refused as the old form only when the named tool has no
input called arguments (cookbook_run has one).

No tool has an input with a reserved name (tests/test_flat_call_1126.py
checks tools.json). A tool that has one cannot be given it in a step.

Plain Python: reads the tools' schemas only."""
import copy
import re

RESERVED = ("tool", "each", "writeTo")
OLD_KEYS = ("arguments", "as", "when", "then", "else", "let", "try", "choose")
MAX_EACH = 200  # the values of one each (a block takes at most 200 calls)
EXAMPLE = '{ "tool": "sketch_new", "plane": "XY" }'
RUN_EXAMPLE = '{ "tool": "pd_pad", "sketch": "Sketch", "length": 6 }'
RUN_FORM = 'run { "calls": [ ' + RUN_EXAMPLE + ' ] }'
LOOP_EXAMPLE = '{ "tool": "sketch_add", "each": { "x": [15, 45] }, "kind": "circle", "center": ["$x", 15], "radius": 5 }'
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_VAR = re.compile(r"^\$[A-Za-z_][A-Za-z0-9_]*$")


def card_fields(server, name):
    t = getattr(server, "tools", {}).get(name) if isinstance(name, str) else None
    if t is None:
        return None
    return list(((getattr(t, "schema", None) or {}).get("properties") or {}))


class Refused(Exception):
    def __init__(self, words, no_tool=False):
        super().__init__(words)
        self.words = words
        self.no_tool = no_tool  # the step has no tool at all


def _form(name="pd_pad"):
    return f'{{ "tool": "{name}", <the inputs> }}'


def old_words(key, where, name=None):
    """The words for an old key of a step: what to write now."""
    n = name if isinstance(name, str) and name else "sketch_new"
    if key == "arguments":
        return (f"{where}: arguments is the old form. Put the inputs beside tool: {{ \"tool\": \"{n}\", \"plane\": \"XY\" }}. "
                "There is no arguments wrapper.")
    if key == "call":
        return (f"{where}: {{ call, … }} is the old form of a step. A step is {_form(n)}, "
                "with the inputs beside tool.")
    if key == "as":
        return (f"{where}: as is not part of a step. To use an earlier call's answer in a batch, give "
                "{ \"$from\": 0, \"$at\": \"feature\" } where the value goes.")
    if key in ("when", "then", "else", "try", "choose"):
        return (f"{where}: {key} is not part of a step. A step is {_form(n)}. "
                "Send only the calls that you want to run.")
    if key == "let":
        return (f"{where}: let is not part of a step. Write the value in the inputs, or use each for a list of values: "
                f"{LOOP_EXAMPLE}.")
    if key == "do":
        return "do is now calls: { \"calls\": [{ \"tool\": \"sketch_new\", \"plane\": \"XY\" }] }. Nothing was run."
    return f"{where}: {key} is not part of a step."


def _each_old(c, where):
    """The old loop { each: name, in, steps }: refused."""
    return (f"{where}: each is now a key of the step, an object with one variable: {LOOP_EXAMPLE}. "
            "The step runs once for each value, and \"$x\" is the value. Steps inside steps are not part of a step.")


def _name_ok(n):
    return isinstance(n, str) and bool(_NAME.match(n))


def _show(v):
    import json

    try:
        t = json.dumps(v, ensure_ascii=False)
    except (TypeError, ValueError):
        t = repr(v)
    return t if len(t) <= 40 else t[:37] + "…"


def put_in(v, var, value):
    """v with every string "$var" put at value (a new copy)."""
    if isinstance(v, str):
        return copy.deepcopy(value) if v == f"${var}" else v
    if isinstance(v, list):
        return [put_in(x, var, value) for x in v]
    if isinstance(v, dict):
        return {k: put_in(x, var, value) for k, x in v.items()}
    return v


def _loose_vars(v, var, out):
    if isinstance(v, str):
        if _VAR.match(v) and v != f"${var}":
            out.append(v)
    elif isinstance(v, list):
        for x in v:
            _loose_vars(x, var, out)
    elif isinstance(v, dict):
        for x in v.values():
            _loose_vars(x, var, out)
    return out


def inputs_of(c):
    """The inputs of a flat step: every key but the reserved ones."""
    return {k: v for k, v in c.items() if k not in RESERVED}


def steps_of(server, c, where, runner="batch"):
    """The calls of one step as a list of { tool, inputs, writeTo, pass,
    of }, or Refused. c: the step as sent. where: "calls.2". runner: run,
    batch or fast. A step without each is one call. The inputs are copies."""
    if not isinstance(c, dict):
        from .protocol import describe

        # What it is, never its own text (an echo of a failed call makes the same call again more likely).
        raise Refused(f"{where} is {describe(c)}, not an object. A step is {EXAMPLE}.")
    if "tool" not in c:
        if "call" in c:
            raise Refused(old_words("call", where, c["call"] if isinstance(c["call"], str) else None))
        if isinstance(c.get("each"), str):
            raise Refused(_each_old(c, where))
        if isinstance(c.get("arguments"), dict):
            raise Refused(old_words("arguments", where))
        for k in ("let", "when", "try", "choose"):
            if k in c:
                raise Refused(old_words(k, where))
        for k in ("get", "refuse", "push"):
            if k in c:
                raise Refused(f"{where}: {k} is not a step. A step is {_form('get')}: a read is the tool get, "
                              "for example { \"tool\": \"get\", \"what\": \"Body.volume\" }.")
        keys = [k for k in c if k not in RESERVED]
        raise Refused(f"{where}: a step has no \"tool\". A step is {_form()}, with the tool's plain name"
                      + (f" (it has: {', '.join(str(k) for k in list(c)[:6])})." if keys else "."), no_tool=True)
    name = c["tool"]
    if not isinstance(name, str) or not name.strip():
        from .protocol import describe

        raise Refused(f"{where} has a tool that is {describe(name)}, not a tool's name (text). A step is {EXAMPLE}.")
    label = f"{where} ({name})"
    fields = card_fields(server, name)
    held = set(fields or ())
    for k in OLD_KEYS:
        if k in c and k not in held:
            raise Refused(old_words(k, label, name))
    loop = None
    if "each" in c:
        e = c["each"]
        if isinstance(e, str):
            raise Refused(_each_old(c, label))
        if not isinstance(e, dict) or not e:
            raise Refused(f"{label}: each is an object with one variable and its list of values: {LOOP_EXAMPLE}.")
        if len(e) > 1:
            raise Refused(f"{label}: each takes one variable, not {len(e)} ({', '.join(str(k) for k in e)}). "
                          "Send one step for each variable, or one each with one list.")
        var, vals = next(iter(e.items()))
        if not _name_ok(var):
            raise Refused(f"{label}: each's variable is a plain name (letters, digits, _; a letter first), not {_show(var)}.")
        if not isinstance(vals, list) or not vals:
            raise Refused(f"{label}: each.{var} is a list of values, at least one: \"each\": {{ \"{var}\": [15, 45] }}.")
        if len(vals) > MAX_EACH:
            raise Refused(f"{label}: each.{var} has {len(vals)} values. At most {MAX_EACH}: split the step.")
        loose = _loose_vars(inputs_of(c), var, [])
        if loose:
            raise Refused(f"{label}: {loose[0]} is not the variable of each (\"${var}\" is). Use \"${var}\" where the value goes.")
        loop = (var, vals)
    if "writeTo" in c:
        if runner != "batch":
            raise Refused(f"{label}: writeTo is a key of batch steps. {runner} gives its own answer; "
                          "use batch { calls: [{ tool, …, writeTo }] } to write a call's answer to a file.")
        if loop is not None:
            raise Refused(f"{label}: writeTo does not go with each: every pass would write the same file. Send one step for each file.")
    base = inputs_of(c)
    if loop is None:
        return [{"tool": name, "inputs": copy.deepcopy(base), "writeTo": c.get("writeTo") if "writeTo" in c else None, "pass": None, "of": None}]
    var, vals = loop
    return [{"tool": name, "inputs": put_in(copy.deepcopy(base), var, v), "writeTo": None, "pass": i, "of": len(vals)} for i, v in enumerate(vals)]


NOT_IN_RUN = ("approve_file", "approve_code", "run", "batch", "fast")


def _step_name(c):
    t = c.get("tool") if isinstance(c, dict) else None
    return t if isinstance(t, str) and t.strip() else "no tool"


def extra_notice(calls):
    """The fact about the steps after the first: run takes one call."""
    rest = [f"{i} ({_step_name(c)})" for i, c in enumerate(calls) if i > 0]
    n = len(rest)
    return (f"run takes one call. It ran calls.0 only. {n} step{'s were' if n != 1 else ' was'} not run and not checked: {', '.join(rest)}. "
            "batch runs several calls.")


def with_notice(r, notice):
    """The answer r (an MCP result) with notice put after result, near the top."""
    import json

    from .protocol import compact

    try:
        body = json.loads(r["content"][0]["text"])
    except Exception:  # noqa: BLE001 - an answer that is not one JSON object stays as it is
        return r
    if not isinstance(body, dict):
        return r
    out = {}
    for k in ("result", "error"):
        if k in body:
            out[k] = body[k]
    out["notice"] = notice
    out.update({k: v for k, v in body.items() if k not in out})
    r = dict(r)
    r["content"] = [dict(r["content"][0], text=compact(out))] + list(r["content"][1:])
    return r


def run_call(server, params):
    """A call of run: { calls: [step, …] }, the same list as batch and fast.
    The first step runs as a call of the named tool, through the normal
    path, so the answer is the one a direct call gives. The steps after the
    first are not run and not checked: the answer says so (notice, after
    result). A step with each runs as a batch of its passes. Refused: the
    old flat form, an empty list, the approvals, run, batch and fast."""
    a = params.get("arguments")
    if not isinstance(a, dict):
        return server.refusal("invalid_input", f"run: the input is {RUN_FORM}.")
    if "calls" not in a:
        if "tool" in a:
            return server.refusal("invalid_input", f"run: the call goes in calls now. Send {RUN_FORM}. The inputs stand beside tool, inside the step. Nothing was run.")
        return server.refusal("invalid_input", f"run: calls is the list of calls. Send {RUN_FORM}. Nothing was run.")
    others = [k for k in a if k != "calls"]
    if others:
        return server.refusal("invalid_input", f"run takes only calls, not {', '.join(str(k) for k in others[:4])}. "
                                               f"Send {RUN_FORM}. batch has rollback and stopOnError. Nothing was run.")
    calls = a["calls"]
    if not isinstance(calls, list) or not calls:
        return server.refusal("invalid_input", f"run: calls is a list of one step at least. Send {RUN_FORM}. Nothing was run.")
    step = calls[0]
    try:
        parts = steps_of(server, step, "calls.0", runner="run")
    except Refused as e:
        return server.refusal("invalid_input", e.words)
    from .protocol import plain_name

    name = plain_name(server, parts[0]["tool"])
    if name in NOT_IN_RUN:
        if name == "run":
            return server.refusal("invalid_input", "run: tool is the tool to run, not run.")
        if name in ("batch", "fast"):
            return server.refusal("invalid_input", f"run: {name} is not a step of run. A step of run is one tool's call. Call {name} by its own name. Nothing was run.")
        return server.refusal("not_allowed", f"run: {name} takes only a direct call from the client, which asks the person first. "
                                              f"A step of run, batch or fast cannot call it. Call {name} by its own name. Nothing was approved.")
    if parts[0]["pass"] is not None:
        r = server.call({"name": "batch", "arguments": {"calls": [step]}})
    else:
        r = server.call({"name": parts[0]["tool"], "arguments": parts[0]["inputs"]})
    return with_notice(r, extra_notice(calls)) if len(calls) > 1 else r
