# SPDX-License-Identifier: LGPL-2.1-or-later
"""The static minimal tool list: the default since 17 Nov 2026 (arm C of
the A/B/C test won; classic stays one switch away).

ToolListMode (preference, Mod/AgentLink, text) or AGENTLINK_TOOLLIST:
    classic            the lean list, as before.
    static (default)   only BASE is listed: session_state, batch, guide_read,
                       tool_find, approve_file and approve_code (the person sets
                       the two approval tools in the client's permissions, so
                       the client must list them). Every other tool is found with
                       tool_find and called by name (in a batch where the
                       client sends only listed tools). The list never
                       changes by itself: no tools/list_changed, so every
                       client sees the same list. A group turned on with
                       tool_groups { enable } is listed too.
ToolDescStyle (preference, text) or AGENTLINK_DESC:
    full               the tools' own descriptions.
    ste (default)      the BASE tools' descriptions in ASD-STE100 from
                       data/ste.json; batch's full text is the batch guide
                       (guide_read { topic: "batch" }), and a refused batch
                       names it.
Both are read again at each tools/list, so a preference set while FreeCAD
runs takes effect when the client next lists the tools.
"""
import copy
import json
import os

BASE = ("session_state", "batch", "guide_read", "tool_find", "approve_file", "approve_code")
# With the fast path on (fastpath.enabled), its two tools are listed too:
# a client that sends only listed tools (OpenCode) can then call them
# directly, not only inside batch. Eight tools on, six off: the A/B test
# decides whether eight becomes the default for every client (owner, 22 Nov).
FAST = ("fast", "get")
PREFS = "User parameter:BaseApp/Preferences/Mod/AgentLink"
_STE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "ste.json")
_cache = {}


def _pref(name, env, default, allowed):
    v = os.environ.get(env, "").strip().lower()
    if v in allowed:
        return v
    try:
        import FreeCAD

        v = FreeCAD.ParamGet(PREFS).GetString(name, default).strip().lower()
    except Exception:  # noqa: BLE001 - no FreeCAD here
        v = default
    return v if v in allowed else default


def mode():
    return _pref("ToolListMode", "AGENTLINK_TOOLLIST", "static", ("classic", "static"))


def style():
    return _pref("ToolDescStyle", "AGENTLINK_DESC", "ste", ("full", "ste"))


def ste_descriptions():
    if "ste" not in _cache:
        try:
            with open(_STE, encoding="utf-8") as f:
                _cache["ste"] = json.load(f)["entries"]
        except Exception:  # noqa: BLE001
            _cache["ste"] = {}
    return _cache["ste"]


def apply(server):
    """Set server.static_base from the mode now (None in classic)."""
    # A server without tool_find (a test server, a small add-on server on
    # this protocol) keeps its own list: the base is no use without a find.
    tools = getattr(server, "tools", None) or {}
    has_find = "tool_find" in tools
    server.static_base = base(tools) if mode() == "static" and has_find else None
    return server.static_base


def base(tools=None):
    """BASE, plus the fast path's two tools when it is on and they are here."""
    try:
        from . import fastpath

        on = fastpath.enabled()
    except Exception:  # noqa: BLE001 - a server without the fast path
        on = False
    if on and all(t in (tools or {}) for t in FAST):
        return BASE + FAST
    return BASE


# The schema a client sees for batch and fast with the short descriptions
# (owner decision 2, 23 Nov): only what a first call needs, each step typed
# { tool, arguments }. The server still checks the tool's whole schema, so
# the other fields (file, from, to, lines, build, check, budget, title) work
# and the batch guide gives them. No additionalProperties here: a client
# that checks a call against the listed schema must let them through.
_CALL_ITEM = {"type": "object",
              "properties": {"tool": {"type": "string", "description": "The tool's plain name, as tool_find gives it (sketch_new)."},
                             "arguments": {"type": "object", "description": "Every input of the tool, by the names on its card. {} for none."}},
              "required": ["tool", "arguments"]}
LISTED_SCHEMAS = {
    "batch": {"type": "object",
              "properties": {"calls": {"type": "array", "minItems": 1, "description": "The calls, run one at a time, in order.", "items": _CALL_ITEM},
                             "rollback": {"type": "boolean", "description": "true: at a refusal, take back the whole batch."},
                             "stopOnError": {"type": "boolean", "description": "false: run every call, also after a refusal."}},
              "required": ["calls"]},
    "fast": {"type": "object",
             "properties": {"do": {"type": "array", "minItems": 1,
                                   "description": "The steps, in order. A tool step is { tool, arguments, as }; the other steps are on fast's card.",
                                   "items": {"type": "object",
                                             "properties": {**_CALL_ITEM["properties"],
                                                            "as": {"type": "string", "description": "A name for this call's answer, for later steps."}}}},
                            "rollback": {"type": "boolean", "description": "true: at a refusal, take back the whole block."},
                            "check": {"type": "boolean", "description": "true: check every step, run nothing."}},
             "required": ["do"]},
}


def listing(server, tools):
    """The tools/list entries, with the STE descriptions when asked for,
    and in the static list the short listed schemas (LISTED_SCHEMAS)."""
    out = [t.listing() for t in tools]
    if style() == "ste":
        ste = ste_descriptions()
        for e in out:
            if e.get("name") in ste:
                e["description"] = ste[e["name"]]
            if e.get("name") in LISTED_SCHEMAS and mode() == "static":
                e["inputSchema"] = copy.deepcopy(LISTED_SCHEMAS[e["name"]])
    return out


GUIDE_HINT = ' guide_read { topic: "batch" } has the rules (chaining with $from, to, lines, from/next).'


NOTHING_RAN = "Nothing was run."
BASIC_FORM = " The basic form: batch { calls: [{ tool, arguments }] }."


def batch_hint(message):
    """A batch refused whole (its own form: a refused call is a row of its
    answer, not this): the words say that nothing ran and give the basic
    form (local-model runs, 23 Nov: models put every field in a first
    batch); they name its guide when the short descriptions are listed."""
    m = message.rstrip()
    if "nothing was run" not in m.lower() and "nothing ran" not in m.lower():
        m += " " + NOTHING_RAN
    if BASIC_FORM.strip() not in m:
        m += BASIC_FORM
    if style() == "ste" and GUIDE_HINT.strip() not in m:
        m += GUIDE_HINT
    return m
