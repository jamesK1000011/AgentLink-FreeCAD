# SPDX-License-Identifier: LGPL-2.1-or-later
"""A ready call on a tool's card (owner, 22 Nov): the arguments filled from
the open document, as the options fill theirs, and the values the agent
must give marked. Small models copy and change a call better than they
build one from the card (local runs, 22 Nov: sketch constraints).

The marker of a value to give: null (default; a null fails the schema
check, and the refusal names the field) or angle ("<length: mm>").
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


def for_tool(name, facts, table=None, how=None):
    """{ example: { tool, arguments }, fill: [words] } for the tool, or None
    (no entry, or switched off)."""
    if not enabled():
        return None
    e = (load() if table is None else table).get(name)
    if not isinstance(e, dict):
        return None
    how = how or mark()
    facts = facts or {}
    args = {}
    for k, v in (e.get("arguments") or {}).items():
        got = _value(v, facts)
        if got is not None and got != []:
            args[k] = got
    words = []
    for f in e.get("fill") or ():
        arg, what = f.get("arg"), f.get("what", "")
        if f.get("unless") and _value(f["unless"], facts) not in (None, []):
            continue
        if f.get("keep"):
            words.append(f"{arg}: {what}. Change it to yours.")
            continue
        args[arg] = None if how == "null" else f"<{arg}>"
        words.append(f"{arg}: {what}. Put the value in place of " + ("null." if how == "null" else f"<{arg}>."))
    out = {"example": {"tool": name, "arguments": args}}
    if words:
        out["fill"] = words
    return out


def to_give(name):
    """{ arg: what } of the values the tool's example marks to give."""
    e = load().get(name)
    if not isinstance(e, dict):
        return {}
    return {f["arg"]: f.get("what", "") for f in e.get("fill") or () if not f.get("keep") and f.get("arg")}
