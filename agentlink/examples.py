# SPDX-License-Identifier: LGPL-2.1-or-later
"""Two example calls on a tool's card (owner, 22 Nov, 26 Nov): plain, every
input with no context, and ready, the same call filled from the open
document as the options fill theirs. Each is one flat step that goes into
run, batch or fast as it is. A value that the agent must give is marked in
both. Small models copy and change a call better than they build one from
the card (local runs, 22 Nov: sketch constraints).

The marker of a value to give: null (default; a null fails the schema
check, and the refusal names the field) or angle ("<length>").
AGENTLINK_EXAMPLE_MARK=null|angle picks it; AGENTLINK_EXAMPLES=0 turns
the examples off. Data: data/examples.json. Never raises."""
import copy
import json
import os

from . import expr

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "examples.json")
_cache = {}


def enabled():
    return os.environ.get("AGENTLINK_EXAMPLES", "1").strip().lower() not in ("0", "off", "false", "no")


def mark():
    m = os.environ.get("AGENTLINK_EXAMPLE_MARK", "null").strip().lower()
    return m if m in ("null", "angle") else "null"


def load(path=None):
    path = path or DATA
    if path not in _cache:
        try:
            with open(path, encoding="utf-8") as f:
                _cache[path] = json.load(f).get("entries", {})
        except (OSError, ValueError):
            _cache[path] = {}
    return _cache[path]


def _value(v, facts):
    if isinstance(v, str) and v.startswith("="):
        try:
            return expr.evaluate(v[1:], {"facts": facts})
        except Exception:  # noqa: BLE001 - an example never fails the card
            return None
    return copy.deepcopy(v)


def _marked(arg, how):
    return None if how == "null" else f"<{arg}>"


def for_tool(name, facts, table=None, how=None):
    """{ plain, ready, fill } for the tool, or None (no entry, or switched off).

    plain and ready are each one flat step ({ "tool": name, <inputs> }) that
    can go into run, batch or fast as it is. plain has every input of the
    entry with no context: a value that the document gives, and a value to
    give, are marked; a worked value stays. ready is the same call filled
    from the open document: an input that the document does not give is still
    there, marked. fill: words for the inputs of the entry that the agent
    gives (a worked value to change, or a marked one)."""
    if not enabled():
        return None
    e = (load() if table is None else table).get(name)
    if not isinstance(e, dict):
        return None
    how = how or mark()
    facts = facts or {}
    plain, ready = {}, {}
    for k, v in (e.get("arguments") or {}).items():
        if isinstance(v, str) and v.startswith("="):
            got = _value(v, facts)
            plain[k] = _marked(k, how)
            ready[k] = got if got is not None and got != [] else _marked(k, how)
        else:
            plain[k] = ready[k] = copy.deepcopy(v)
    words = []
    for f in e.get("fill") or ():
        arg, what = f.get("arg"), f.get("what", "")
        if f.get("keep"):
            words.append(f"{arg}: {what}. Change it to yours.")
            continue
        if arg in ready and ready[arg] != _marked(arg, how):
            continue  # the open document gave it: ready has the value, and there is nothing to give
        if arg not in plain:
            plain[arg] = ready[arg] = _marked(arg, how)
        words.append(f"{arg}: {what}.")
    out = {"plain": {"tool": name, **plain}, "ready": {"tool": name, **ready}}
    if words:
        out["fill"] = words
    return out


def to_give(name):
    """{ arg: what } of the values the tool's example marks to give."""
    e = load().get(name)
    if not isinstance(e, dict):
        return {}
    return {f["arg"]: f.get("what", "") for f in e.get("fill") or () if not f.get("keep") and f.get("arg")}


def field_example(name, field):
    """A ready value of one input of the tool, from its card's data: the
    entry's forms (a value its card gives), else its example's worked value
    (not one filled from the document, not one the agent must give). None
    when there is none."""
    if not enabled() or not isinstance(field, str):
        return None
    e = load().get(name)
    if not isinstance(e, dict):
        return None
    forms = e.get("forms") or {}
    if field in forms:
        return copy.deepcopy(forms[field])
    v = (e.get("arguments") or {}).get(field)
    if v is None or (isinstance(v, str) and v.startswith("=")) or field in to_give(name):
        return None
    return copy.deepcopy(v)
