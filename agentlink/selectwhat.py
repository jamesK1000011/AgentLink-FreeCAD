# SPDX-License-Identifier: LGPL-2.1-or-later
"""what: one hub-level key that any tool call accepts (owner, 27 Nov).

No what gives every fact. what: a name or a list of names keeps only those
parts of the answer; the hub never leaves out a fact by itself
(decision 1). It is not in any tool's schema (decision 9): the call layer
takes it off the arguments before the tool sees them, and narrows the
answer after.

- A tool's answer: its top-level keys. A name that is not a key of this
  answer: the whole answer comes back, with whatNotFound and whatNames,
  because the call has already run (a change is not taken back for a
  name).
- tool_find: the fields of each card (does, inputs, rules, returns, hint,
  plain, ready, fill ...). An unknown name is refused with the list, as
  for session_state, because tool_find changes nothing.
- health with a fault always comes back, also when what leaves it out
  (decision 11). health is dropped only when it says no fault.
- $from / $at read the whole stored answer, not the narrowed one
  (decision 10): batch takes what off before the call and narrows only
  the row it shows.
- A tool whose own schema has an input called what (session_state) keeps
  its own meaning; the call layer does not touch it."""
from .protocol import ToolError

KEY = "what"
ALWAYS = ("tool",)          # a card keeps its tool name
# Every field a card can have (agentlink/cards.py ORDER, the old card's
# fields, the words the hub adds); a name among them is never refused,
# also where this card has no such field (a tool with no hints).
from .cards import ORDER as _ORDER

CARD_FIELDS = tuple(_ORDER) + ("said", "applies", "fits", "readAs", "description", "inputSchema", "plain", "ready", "fill")
CARD_KEYS = ("tools", "card", "cards")


def names(what):
    """The names asked for, or a refusal of the form."""
    if isinstance(what, str) and what.strip():
        return [what.strip()]
    if isinstance(what, list) and what and all(isinstance(x, str) and x.strip() for x in what):
        return [x.strip() for x in what]
    raise ToolError("invalid_input", "what: a name or a list of names of the answer's parts.")


def takes_own(tool):
    """Whether the tool's own schema has an input called what."""
    return KEY in ((getattr(tool, "schema", None) or {}).get("properties") or {})


def take(tool, args):
    """what, taken off the arguments when the tool does not take it itself;
    None when the call has none."""
    if not isinstance(args, dict) or KEY not in args or takes_own(tool):
        return None
    return names(args.pop(KEY))


def health_has_fault(h):
    """Whether a health part holds a fault: the health check's own reading
    (agentlink/health.py last_fault: a recompute error, a shape that is not
    valid or not closed, conflicting, redundant or malformed constraints,
    an open dialog), or failed or not-recomputed objects named in it. A
    health that the check did not read is kept."""
    from . import health as _health

    if not isinstance(h, dict):
        return h is not None
    if h.get("errors") or h.get("needRecompute") or h.get("taskPanel"):
        return True
    facts = str(h.get("facts") or "")
    if facts.startswith(_health.NOT_READ) or "did not run" in facts:
        return True
    return _health.last_fault()


def answer(body, want):
    """The answer narrowed to want (see the module's words)."""
    if not isinstance(body, dict) or not want:
        return body
    missing = [w for w in want if w not in body]
    if missing:
        return {**body, "whatNotFound": missing, "whatNames": sorted(body)}
    out = {k: body[k] for k in body if k in want}
    if "health" in body and "health" not in out and health_has_fault(body["health"]):
        out["health"] = body["health"]
    return out


def card(c, want):
    """One card narrowed: a kind ("inputNotes") or one subject of a kind
    ("inputNotes.size2", "returns.volume", "links.size2": the links of
    that input)."""
    if not isinstance(c, dict):
        return c
    out = {k: v for k, v in c.items() if k in ALWAYS}
    for w in want:
        kind, _, sub = w.partition(".")
        if kind not in c:
            continue
        v = c[kind]
        if not sub:
            out[kind] = v
        elif out.get(kind) is v:
            continue  # the whole kind is in already
        elif isinstance(v, dict):
            if sub in v:
                part = out.get(kind) if isinstance(out.get(kind), dict) else {}
                out[kind] = {**part, sub: v[sub]}
        elif isinstance(v, list):
            part = list(out.get(kind) or [])
            part += [x for x in v if isinstance(x, dict) and sub in (x.get("inputs") or []) and x not in part]
            if part:
                out[kind] = part
    return out


def cards(body, want):
    """tool_find's answer with each card narrowed; an unknown field name
    is refused with the names."""
    if not isinstance(body, dict) or not want:
        return body
    seen = set()

    def every(b):
        for k in CARD_KEYS:
            v = b.get(k)
            if isinstance(v, list):
                for c in v:
                    if isinstance(c, dict) and ("does" in c or "description" in c or "inputs" in c or "inputSchema" in c):
                        yield c
            elif isinstance(v, dict) and ("does" in v or "description" in v):
                yield v
        for r in b.get("results") or []:
            if isinstance(r, dict):
                yield from every(r)

    for c in every(body):
        seen.update(c)
    if not seen:
        return body
    bad = [w for w in want if w.split(".", 1)[0] not in seen and w.split(".", 1)[0] not in CARD_FIELDS]
    if bad:
        shown = sorted((set(seen) | set(CARD_FIELDS)) - {"description", "inputSchema"}) if any("does" in c for c in every(body)) else sorted(seen)
        raise ToolError("invalid_input", "what: " + ", ".join(bad) + " is not a card field. The fields: " + ", ".join(shown) + ".")

    def narrow(b):
        b = dict(b)
        for k in CARD_KEYS:
            v = b.get(k)
            if isinstance(v, list):
                b[k] = [card(c, want) if isinstance(c, dict) and ("does" in c or "description" in c or "inputs" in c or "inputSchema" in c) else c
                        for c in v]
            elif isinstance(v, dict) and ("does" in v or "description" in v):
                b[k] = card(v, want)
        if isinstance(b.get("results"), list):
            b["results"] = [narrow(r) if isinstance(r, dict) else r for r in b["results"]]
        return b

    return narrow(body)


def apply(tool_name, body, want):
    if want is None:
        return body
    if tool_name == "tool_find":
        return cards(body, want)
    return answer(body, want)
