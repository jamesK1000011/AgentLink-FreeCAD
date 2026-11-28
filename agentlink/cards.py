# SPDX-License-Identifier: LGPL-2.1-or-later
"""Tool cards as records: one kind of fact per field (owner, 28 Nov 2026).

A card is data, small and typed, that code and an agent both read. Every
kind can be asked for alone, and one subject of a kind:
tool_find { card: "pd_chamfer", what: ["inputNotes.size2"] }.

The kinds (an entry's "card" in agentlink/data/tools.json, or a hub
tool's card in agentlink/data/hubcards.json):
  does          one line: what the tool does.
  inputNotes    { input: { means, unit, default, min, max, values, forms } }:
                what one input means; only means is required.
  links         [ { inputs: [a, b, ...], rel, when, line } ]: a fact between
                inputs. rel: excludes | needs | with | overrides | order.
  effects       [ line ]: what the tool does to the model or the document
                that is not an input, a link, a refusal or an answer key.
  returns       { key: { means, unit } }: the answer's keys.
  refusalNotes  [ line ]: refusal facts that are not one of the tool's own
                refuse steps.
  hints         [ line ]: method advice only.
Made by code, never stored twice:
  inputs        the bare schema: types, enums, required; no description.
  refusals      the tool's own refuse steps: [ { code, when, message } ].
  examples      { plain, ready, fill } (agentlink/examples.py).

Default (owner, 28 Nov): every kind comes back except hints and refusals
(refusals and refusalNotes); those come when what names them, and hints
also at help level 1 and up (agentlink/helplevel.py)."""

KINDS = ("does", "inputNotes", "links", "effects", "returns", "refusalNotes", "hints")
MADE = ("inputs", "refusals", "examples")
BY_EXCEPTION = ("hints", "refusals", "refusalNotes")
NOTE_KEYS = ("means", "unit", "default", "min", "max", "values", "forms")
RELS = ("excludes", "needs", "with", "overrides", "order")
# The order of the kinds in an answer.
ORDER = ("tool", "group", "changes", "does", "inputs", "inputNotes", "links", "effects", "returns", "examples",
         "refusals", "refusalNotes", "hints")


def check(name, c, schema=None):
    """What is wrong with a card's records (an empty list: nothing)."""
    if not isinstance(c, dict):
        return [f"{name}.card: an object of {', '.join(KINDS)}"]
    out = []
    extra = set(c) - set(KINDS)
    if extra:
        out.append(f"{name}.card: unknown kinds {sorted(extra)}")
    if not isinstance(c.get("does"), str) or len(c["does"]) < 6:
        out.append(f"{name}.card.does: one line on what the tool does")
    props = ((schema or {}).get("properties") or {}) if schema is not None else None
    notes = c.get("inputNotes", {})
    if not isinstance(notes, dict):
        out.append(f"{name}.card.inputNotes: an object by input name")
        notes = {}
    for k, n in notes.items():
        if props is not None and k not in props:
            out.append(f"{name}.card.inputNotes.{k}: not an input")
        if not isinstance(n, dict) or not isinstance(n.get("means"), str) or not n["means"]:
            out.append(f"{name}.card.inputNotes.{k}: means, one line")
        elif set(n) - set(NOTE_KEYS):
            out.append(f"{name}.card.inputNotes.{k}: unknown keys {sorted(set(n) - set(NOTE_KEYS))}")
    for i, L in enumerate(c.get("links", []) or []):
        ins = L.get("inputs") if isinstance(L, dict) else None
        if (not isinstance(L, dict) or L.get("rel") not in RELS or not isinstance(L.get("line"), str)
                or not isinstance(ins, list) or len(ins) < 2 or (props is not None and not all(x in props for x in ins))):
            out.append(f"{name}.card.links.{i}: inputs (2 or more), rel ({' | '.join(RELS)}), line")
    for k, r in (c.get("returns") or {}).items():
        if not isinstance(r, dict) or not isinstance(r.get("means"), str) or not r["means"]:
            out.append(f"{name}.card.returns.{k}: means, one line")
    for kind in ("effects", "refusalNotes", "hints"):
        v = c.get(kind, [])
        if not isinstance(v, list) or not all(isinstance(x, str) and x for x in v):
            out.append(f"{name}.card.{kind}: a list of lines")
    if props is not None:
        for k, p in props.items():
            if isinstance(p, dict) and "description" in p:
                out.append(f"{name}.inputSchema.{k}: no description (its meaning is in card.inputNotes)")
    return out


def bare(schema):
    """The schema with no description at any level (its meanings are in
    inputNotes). Property names are kept as they are, also an input named
    description."""
    if isinstance(schema, list):
        return [bare(x) for x in schema]
    if not isinstance(schema, dict):
        return schema
    out = {}
    for k, v in schema.items():
        if k == "description":
            continue
        if k == "properties" and isinstance(v, dict):
            out[k] = {name: bare(p) for name, p in v.items()}
        elif k in ("items", "anyOf", "oneOf", "allOf", "not", "additionalProperties") and isinstance(v, (dict, list)):
            out[k] = bare(v)
        else:
            out[k] = v
    return out


HUB = "hubcards.json"


def hub_cards():
    """The cards of the hub tools written in code (agentlink/data/hubcards.json)."""
    import json
    import os

    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", HUB)
    with open(p, encoding="utf-8") as f:
        return json.load(f)["entries"]


def attach_hub(tools):
    """Give each hub tool its card from hubcards.json (tools: name → Tool)."""
    try:
        got = hub_cards()
    except Exception:  # noqa: BLE001 - no file: the tools keep their descriptions
        return 0
    n = 0
    for name, c in got.items():
        t = tools.get(name)
        if t is not None and not getattr(t, "fields", None):
            t.fields = dict(c)
            n += 1
    return n


def refusals(entry):
    """The tool's own refusals, read from its refuse steps:
    [ { code, when, message } ], in the order of the steps."""
    out = []

    def walk(x):
        if isinstance(x, dict):
            if "refuse" in x:
                m = x["refuse"]
                out.append({"code": x.get("code", "invalid_input"), **({"when": x["when"]} if x.get("when") else {}),
                            "message": m if isinstance(m, str) else (m.get("fmt") if isinstance(m, dict) else str(m))})
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    if isinstance(entry, dict):
        walk(entry.get("steps") or [])
        walk(entry.get("rules") or [])
    return out


def lines(c):
    """Every line of a card's records, in kind order: for the search index
    and other readers of the words (never shown as one text)."""
    if not isinstance(c, dict):
        return []
    out = [c.get("does", "")]
    for k, n in (c.get("inputNotes") or {}).items():
        out.append(f"{k}: {n.get('means', '')}")
        out += [f"{k}: {f}" for f in n.get("forms", []) or []]
    out += [L.get("line", "") for L in c.get("links", []) or []]
    out += list(c.get("effects", []) or [])
    out += [f"{k}: {r.get('means', '')}" for k, r in (c.get("returns") or {}).items()]
    out += list(c.get("refusalNotes", []) or [])
    out += list(c.get("hints", []) or [])
    return [x for x in out if x]


def serve(t, extra=None, want=None):
    """The card of tool t as tool_find answers it: every kind by default
    but hints and refusals; those when want names them (or hints at help
    level 1). extra: the made fields (examples, said, ...)."""
    from . import helplevel

    want = set(want or ())
    asked = {w.split(".", 1)[0] for w in want}
    c = getattr(t, "fields", None) or {}
    out = {"tool": t.name, "group": t.group, "changes": bool(t.changes)}
    out["does"] = c.get("does", "")
    out["inputs"] = bare(t.schema)
    for k in ("inputNotes", "links", "effects", "returns"):
        if c.get(k):
            out[k] = c[k]
    if extra:
        ex = {k: extra[k] for k in ("plain", "ready", "fill") if k in extra}
        if ex:
            out["examples"] = ex
        for k, v in extra.items():
            if k not in ("plain", "ready", "fill"):
                out[k] = v
    if "refusals" in asked:
        r = refusals(getattr(t, "entry", None))
        if r:
            out["refusals"] = r
    if "refusalNotes" in asked and c.get("refusalNotes"):
        out["refusalNotes"] = c["refusalNotes"]
    if c.get("hints") and ("hints" in asked or helplevel.shown("hint")):
        out["hints"] = c["hints"]
    return {k: out[k] for k in sorted(out, key=lambda k: ORDER.index(k) if k in ORDER else len(ORDER))}
