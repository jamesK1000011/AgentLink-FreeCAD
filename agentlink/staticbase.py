# SPDX-License-Identifier: LGPL-2.1-or-later
"""The static minimal tool list: the default since 17 Nov 2026 (arm C of
the A/B/C test won; classic stays one switch away).

ToolListMode (preference, Mod/AgentLink, text) or AGENTLINK_TOOLLIST:
    classic            the lean list, as before.
    static (default)   only BASE is listed: session_state, batch, guide_read,
                       tool_find, approve_file and approve_code (the person sets
                       the two approval tools in the client's permissions, so
                       the client must list them), then run (one step, a full
                       answer: a client that sends only listed tools reaches
                       every tool with it). With the fast path on, fast and get
                       come before run. Every other tool is found with
                       tool_find and called by name, or as a step of run, batch or fast. The list never
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
# run is listed after them, with the fast path on or off: it is not part of
# the fast path (owner, 26 Nov). Seven tools off, nine on.
RUN = ("run",)
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
    """BASE, plus the fast path's two tools when it is on and they are here,
    plus run when it is here."""
    try:
        from . import fastpath

        on = fastpath.enabled()
    except Exception:  # noqa: BLE001 - a server without the fast path
        on = False
    out = BASE + FAST if on and all(t in (tools or {}) for t in FAST) else BASE
    return out + RUN if all(t in (tools or {}) for t in RUN) else out


# The schema a client sees for run, batch and fast with the short descriptions
# (owner decision 9, 26 Nov): only what a first call needs. A step is one flat
# object: tool, and the tool's inputs beside it. The server checks each step
# against the named tool's own schema, as it checks a direct call. No
# additionalProperties: false here: a client that checks a call against the
# listed schema must let the inputs through.
_STEP_ITEM = {"type": "object",
              "properties": {"tool": {"type": "string", "description": "The tool's plain name, as tool_find gives it (pd_pad). Its inputs stand beside it."}},
              "required": ["tool"]}
LISTED_SCHEMAS = {
    "run": copy.deepcopy(_STEP_ITEM),
    "batch": {"type": "object",
              "properties": {"calls": {"type": "array", "minItems": 1, "description": "The calls, run one at a time, in order.", "items": _STEP_ITEM},
                             "rollback": {"type": "boolean", "description": "true: at a refusal, take back the whole batch."},
                             "stopOnError": {"type": "boolean", "description": "false: run every call, also after a refusal."}},
              "required": ["calls"]},
    "fast": {"type": "object",
             "properties": {"calls": {"type": "array", "minItems": 1, "description": "The calls, run one at a time, in order.", "items": _STEP_ITEM},
                            "rollback": {"type": "boolean", "description": "true: at a refusal, take back the whole block."},
                            "check": {"type": "boolean", "description": "true: check every step, run nothing."}},
             "required": ["calls"]},
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


GUIDE_HINT = ' guide_read { topic: "batch" } has the rules (chaining with $from, writeTo, lines, start/next).'


NOTHING_RAN = "Nothing was run."
BASIC_FORM = ' The basic form: batch { calls: [{ "tool": "sketch_new", "plane": "XY" }] }.'


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
