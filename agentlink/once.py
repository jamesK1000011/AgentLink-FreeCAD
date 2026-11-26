# SPDX-License-Identifier: LGPL-2.1-or-later
"""Standing words said once a conversation (plain Python; used by protocol.py).

Many answers carry a sentence that is the same on every call of a tool: an
explanation written into the tool itself (doc_new's "The previous document
stays open …", sketch_new's "Coordinates are the sketch's …", part_wire's
use), a batch { to } reply's own note, the
health check's advice on an overlap. Measured over a full run of every
family's test model (private records: tokens-findings.md) they were among
the largest repeated parts of the replies, and none carries anything new the
second time.

Such a value is given the first time a tool answers with it in a
conversation (since the client's initialize). Later answers of that tool
with the very same value leave the key out and name it in saidBefore — so
the answer still says the note applies (not for QUIET keys, whose name
carries nothing); a value that differs is a new one and is given whole. tool_groups { tool: name } gives the words again
(said), so nothing becomes unreachable.

What counts as standing is decided from the tool itself, never guessed from
the answer:
  - a data tool (tools.json, an add-on's too): a top-level answer value that
    is a literal string of the tool's own entry (not an expression, not a
    fmt template), at least MIN_CHARS long — it cannot carry a fact of the
    call, only one of the branches the entry wrote out;
  - a tool written in code: the keys CODED names, with the values listed
    there (or any value, where the key's value is constant by what it is);
  - health: the advice HEALTH_TODOS names, and the standing part of the
    verdict (the objects still failing from before), given again when it
    changes; and a changing call's whole health, as "nothing new", when
    its finding is the one last given and all is well (quiet_health).
A refusal is never touched: its words are what to do next.
"""
import json
import re

MIN_CHARS = 60

# A changing call's health whose finding is the one last given (quiet_health):
# the check ran, and there is nothing new to say (owner, 25 Nov: a small
# model reads the top of an ok answer, and a verdict given again on each
# step buried the one that changed).
NOTHING_NEW = "nothing new"
# Keys of a health reading that are not its finding: timing, the hints put
# beside it, the status bar's text.
HEALTH_ASIDE = {"ms", "msBy", "overlapPairs", "saidBefore", "options", "appliesNow", "statusBar", "next"}

# Coded tools' standing keys: { tool: { key: values or None (any value) } }.
# Filled with the literal texts where a key also carries words that change.
CODED = {
    # Filled by register() where the words are written: tool_groups' notes
    # (tools.py), usage_report's (usage.py), a batch reply's own (batchrec.py).
    "tool_groups": {},
    "usage_report": {},
    "batch": {},
}

# health.todo parts that are advice, not a reading: the same words whatever
# the objects (agentlink/health.py words them).
HEALTH_TODOS = {
    "overlap": "an overlap is right for a boolean's tool or a press fit; if it is not meant, part_transform moves the part and clearance reads the gap",
    "failing": "recompute lists them with FreeCAD's reasons",
}
STANDING = re.compile(r"^\d+ objects? still failing from before this call: ")
# A sketch reading's note (agentlink/families/sketch.py) when it is ready for
# a feature but not fully constrained: its count is the reading's dof, the
# rest is standing. Inside any answer's state (sketch_add, sketch_edit,
# sketch_constrain …), and sketch_state's own answer.
DOF_NOTE = "it pads as drawn. Its sizes are not constraints yet: an edit can move it. dims: true on an item adds its sizes as constraints."
DOF_LINE = re.compile(r"^\d+ degrees of freedom: " + re.escape(DOF_NOTE) + "$")

# Left-out words that are not named in saidBefore: they say how Agent Link
# itself works (a batch's own notes), or their reading stays in
# the answer (a sketch's dof), so the name carries nothing for the model
# (24 Nov blind QA: saidBefore ["order"] on every batch). tool_groups
# { tool } still gives them again (said).
QUIET = {("batch", "order"), ("batch", "toNote"), ("batch", "note"), ("batch", "healthNote")}

_literals = {}


def register(tool, key, *texts):
    """Words of a coded tool's key that are standing (batchrec's notes)."""
    CODED.setdefault(tool, {}).setdefault(key, set()).update(texts)


def literals(entry):
    """The literal strings of a data tool's entry, at least MIN_CHARS long:
    not its description or schema, not an expression (=…, $…), not a fmt
    template, not a refusal's words."""
    out = set()

    def walk(v, key=None):
        if isinstance(v, dict):
            for k, x in v.items():
                if k in ("description", "inputSchema", "fmt", "refuse", "code"):
                    continue
                walk(x, k)
        elif isinstance(v, list):
            for x in v:
                walk(x, key)
        elif isinstance(v, str) and len(v) >= MIN_CHARS and not v.startswith(("=", "$")):
            out.add(v)

    walk(entry)
    return out


def standing(tool):
    """{ key: set of words, or None for any value } that are standing in
    this tool's answers. tool: a Tool (with .entry for a data tool) or a name."""
    name = getattr(tool, "name", tool)
    coded = CODED.get(name)
    if coded is not None:
        return coded
    entry = getattr(tool, "entry", None)
    if not isinstance(entry, dict):
        return {}
    key = id(entry)
    if key not in _literals:
        _literals[key] = (entry, literals(entry))
    return {"*": _literals[key][1]}


def state(session):
    """This conversation's record: { (tool, key): [values said] } and the
    health's own."""
    st = getattr(session, "_said", None)
    if not isinstance(st, dict):
        st = {"keys": {}, "todo": set(), "failing": None}
        try:
            session._said = st
        except Exception:
            pass
    return st


def reset(session):
    """A new conversation (initialize): everything is said again."""
    try:
        session._said = {"keys": {}, "todo": set(), "failing": None}
    except Exception:
        pass


def _is_standing(rule, key, value):
    if key in rule:
        allowed = rule[key]
        return allowed is None or (isinstance(value, str) and value in allowed)
    allowed = rule.get("*")
    return bool(allowed) and isinstance(value, str) and value in allowed


def thin(st, tool, out, rule=None):
    """out (a tool's answer, a dict) with the standing values already said
    in this conversation left out and named in saidBefore; the rest recorded
    as said. Changes out in place and returns it."""
    if not isinstance(out, dict):
        return out
    name = getattr(tool, "name", tool)
    rule = standing(tool) if rule is None else rule
    gone = []
    if rule:
        for k in list(out):
            if k in ("saidBefore", "health", "error"):
                continue
            v = out[k]
            if not _is_standing(rule, k, v):
                continue
            said = st["keys"].setdefault((name, k), [])
            if v in said:
                del out[k]
                gone.append(k)
            elif len(said) < 8:
                said.append(v)
    named = [k for k in gone if (name, k) not in QUIET]
    if named:
        out["saidBefore"] = sorted(set(out.get("saidBefore") or []) | set(named))
    if isinstance(out.get("health"), dict) and not quiet_health(st, tool, out):
        thin_health(st, out["health"])
    for reading in (out.get("state"), out):
        if isinstance(reading, dict) and "dof" in reading:
            thin_dof(st, reading)
    return out


def health_content(h):
    """The part of a health reading that is the check's own finding: the
    key a repeat is told by (no timing, no hints beside it, no status bar
    text, which changes as the window does)."""
    return json.dumps({k: v for k, v in h.items() if k not in HEALTH_ASIDE}, sort_keys=True, default=str)


def quiet_health(st, tool, out):
    """A changing tool's health given as NOTHING_NEW when its finding is
    the one last given in this conversation and all is well (ok true). The
    check itself ran: only its words are left out. A reading that differs,
    or one that is not ok (a failure, a broken object, a dialog), is given
    whole and is then the last one given. The lines beside it (options,
    appliesNow) move to the answer itself. Explicit reads (body_check,
    session_state …) do not change the document, and keep theirs whole.
    True when the health was left out."""
    h = out.get("health")
    if not isinstance(h, dict) or not getattr(tool, "changes", False) or getattr(tool, "name", tool) == "batch":
        return False
    key = health_content(h)
    # Per subject (the verdict's head: "Body", "Sketch 2"): a build that
    # goes sketch, feature, sketch, feature alternates two verdicts, so one
    # "last given" never matched (live, 25 Nov: no answer in a batch was quiet).
    v = h.get("verdict")
    head = v.split("; ", 1)[0] if isinstance(v, str) else ""
    subject = head.split(":", 1)[0].strip() if ":" in head else ""
    last = st.setdefault("healthBy", {})
    if h.get("ok") is not True or key != last.get(subject):
        last[subject] = key
        st["health"] = key
        return False
    out["health"] = NOTHING_NEW
    for k in ("options", "appliesNow", "next"):
        if k in h and k not in out:
            out[k] = h[k]
    return True


def thin_dof(st, reading):
    """A sketch reading's DoF note left out once said: its count is dof."""
    note = reading.get("note")
    if not (isinstance(note, str) and DOF_LINE.match(note)):
        return
    if "dof" in st["todo"]:
        del reading["note"]  # its count stays, as dof: nothing to name in saidBefore
    else:
        st["todo"].add("dof")


def thin_health(st, h):
    """A health reading with its standing advice left out once said, and
    the standing part of its verdict ("N objects still failing from before
    this call: …") left out while it is what was last said; each named in
    health.saidBefore (overlap, failing)."""
    gone = []
    todo = h.get("todo")
    if isinstance(todo, str):
        for tag, words in HEALTH_TODOS.items():
            if words not in todo:
                continue
            if tag in st["todo"]:
                todo = todo.replace("; " + words, "").replace(words + "; ", "").replace(words, "").strip()
                gone.append(tag)
            else:
                st["todo"].add(tag)
        if todo:
            h["todo"] = todo
        else:
            h.pop("todo", None)
    v = h.get("verdict")
    if isinstance(v, str):
        parts = v.split("; ")
        part = next((p for p in parts if STANDING.match(p)), None)
        if part is None:
            st["failing"] = None
        elif part != st["failing"]:
            st["failing"] = part
        else:
            rest = [p for p in parts if p is not part]
            h["verdict"] = "; ".join(rest) if rest else "as before"
            gone.append("failing")
    if gone:
        h["saidBefore"] = sorted(set(h.get("saidBefore") or []) | set(gone))
    return h


def thin_reply(session, tool, out, tools=None):
    """The reply in hand thinned (thin): a batch's own keys and each of its
    calls' answers in order, else the tool's answer. tools: { name: Tool }
    for a batch's calls. Never raises."""
    try:
        st = state(session)
        name = getattr(tool, "name", tool)
        if name == "batch" and isinstance(out, dict):
            for row in out.get("results") or []:
                if isinstance(row, dict) and row.get("ok") and isinstance(row.get("result"), dict):
                    t = (tools or {}).get(row.get("tool"), row.get("tool"))
                    thin(st, t, row["result"])
        return thin(st, tool, out)
    except Exception:
        return out


def said(session, name):
    """{ key: words } a tool has given in this conversation and leaves out
    since (a key with several, the list); the health's advice under health."""
    st = getattr(session, "_said", None)
    if not isinstance(st, dict):
        return {}
    out = {}
    for (t, k), vals in st["keys"].items():
        if t == name and vals:
            out[k] = vals[0] if len(vals) == 1 else list(vals)
    return out


def health_said(session):
    """The health's standing advice given in this conversation."""
    st = getattr(session, "_said", None)
    if not isinstance(st, dict):
        return {}
    out = {tag: HEALTH_TODOS[tag] for tag in sorted(st["todo"]) if tag in HEALTH_TODOS}
    if "dof" in st["todo"]:
        out["sketchNote"] = "N degrees of freedom (the reading's dof): " + DOF_NOTE
    if st.get("failing"):
        out["failingNow"] = st["failing"]
    return out
