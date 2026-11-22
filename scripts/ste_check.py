# SPDX-License-Identifier: LGPL-2.1-or-later
"""ASD-STE100 check of the hub's tool descriptions (branch explore/full-ste).

Every hub tool: the data tools (agentlink/data/tools.json) and the tools
written in code (Tool("name", description, schema, ...) in agentlink/tools.py
and agentlink/families/*.py). Read with ast, so it runs without FreeCAD.

Two checks:
  lint          each sentence has at most MAX_WORDS words. Words inside
                quotes, backticks or {...} / [...] literals, and a list of
                three or more input or tool names, are not counted (the
                allowance). Passive "is/are/was/were/be/been + -ed" is a
                warning count only.
  preservation  against the original text of main (scripts/ste_originals.json):
                every number, unit token, input name of the tool's schema,
                other hub tool name and guard word of the original is still
                in the new text. WAIVERS lists the rare token that truly does
                not belong, with a reason.

    python3 scripts/ste_check.py --originals   # write ste_originals.json from the tree (run on main)
    python3 scripts/ste_check.py               # report lint and preservation; exit 1 on a fault
    python3 scripts/ste_check.py --measure     # token measurements, before and after
"""
import ast
import json
import os
import re
import statistics
import sys
import types

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PKG = os.path.join(ROOT, "agentlink")
ORIGINALS = os.path.join(ROOT, "scripts", "ste_originals.json")
MAX_WORDS = 20
CHARS_PER_TOKEN = 3.5

UNITS = ("mm", "cm", "m", "µm", "um", "in", "deg", "°", "°C", "C", "K", "N", "kN", "Nm", "N·m", "MPa", "GPa", "Pa", "kPa", "s", "ms",
         "min", "h", "px", "dpi", "%", "kg", "g", "g/cm³", "mm²", "mm³", "rpm", "W", "V", "A", "Hz", "MB", "GB", "KB", "kB", "bytes")
# A stem of the original that the new text must keep (regex, matched case-insensitive at a word start).
GUARDS = {"copy": r"\bcop(?:y|ies|ied)\b", "undo": r"\bundo", "refuse": r"\brefus", "never": r"\bnever\b", "only": r"\bonly\b",
          "must": r"\bmust\b", "approval": r"\bapprov", "restart": r"\brestart", "sign-off": r"\bsign[- ]?off", "feasibility": r"\bfeasib"}

# (tool, token): reason. Keep it short: a token is waived only when it truly does not belong.
WAIVERS = {
    ("export", "20"): "the 20 s estimate that sent an export to a job is gone (no prejudging, 18 Nov); a call past about 60 s moves to the background",
    ("export", "batch"): "the batch-only estimate question is gone with the estimates (18 Nov)",
    ("asm_joint", "get"): "the English verb in the original text, not the get tool that came on 22 Nov",
}


# ---- reading the tools ------------------------------------------------------------------------

def _consts(path):
    out = {}
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                names = [t] if isinstance(t, ast.Name) else (t.elts if isinstance(t, ast.Tuple) else [])
                vals = [node.value] if isinstance(t, ast.Name) else (node.value.elts if isinstance(node.value, ast.Tuple) else [])
                for n, v in zip(names, vals):
                    if isinstance(n, ast.Name):
                        try:
                            out[n.id] = ast.literal_eval(v)
                        except ValueError:
                            pass
    return out


def _env():
    """The names the f-string descriptions use, from their modules' constants."""
    core = _consts(os.path.join(PKG, "tools.py"))
    gi = _consts(os.path.join(PKG, "gui_input.py"))
    ls = _consts(os.path.join(PKG, "livescript.py"))
    env = dict(core)
    env.update(gi_steps=gi.get("DRAG_STEPS"), gi_wait=gi.get("MAX_WAIT"), ls=types.SimpleNamespace(**ls))
    return env


def _text(node, env):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                out.append(v.value)
            else:
                val = eval(compile(ast.Expression(v.value), "<desc>", "eval"), {}, env)  # noqa: S307 - our own constants
                spec = _text(v.format_spec, env) if v.format_spec else ""
                out.append(format(val, spec))
        return "".join(out)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _text(node.left, env) + _text(node.right, env)
    raise ValueError(f"not a text: {ast.unparse(node)[:60]}")


def _schema_names(node):
    """Input names in a schema written in code: keys of every "properties" dict."""
    out = []
    for n in ast.walk(node):
        if isinstance(n, ast.Dict):
            for k, v in zip(n.keys, n.values):
                if isinstance(k, ast.Constant) and k.value == "properties" and isinstance(v, ast.Dict):
                    out += [x.value for x in v.keys if isinstance(x, ast.Constant) and isinstance(x.value, str)]
    return out


def _json_names(schema):
    out = []
    if isinstance(schema, dict):
        for k, v in (schema.get("properties") or {}).items():
            out.append(k)
            out += _json_names(v)
        for k in ("items", "additionalProperties"):
            out += _json_names(schema.get(k))
        for k in ("anyOf", "oneOf", "allOf"):
            for v in schema.get(k) or ():
                out += _json_names(v)
    elif isinstance(schema, list):
        for v in schema:
            out += _json_names(v)
    return out


def coded_files():
    fam = os.path.join(PKG, "families")
    return [os.path.join(PKG, "tools.py")] + sorted(os.path.join(fam, n) for n in os.listdir(fam) if n.endswith(".py"))


def collect(root=ROOT):
    """{name: {"description", "inputs", "kind", "file"}} for every hub tool."""
    global PKG
    PKG = os.path.join(root, "agentlink")
    out = {}
    with open(os.path.join(PKG, "data", "tools.json"), encoding="utf-8") as f:
        for name, e in json.load(f)["entries"].items():
            out[name] = {"description": e["description"], "inputs": sorted(set(_json_names(e["inputSchema"]))), "kind": "data", "file": "agentlink/data/tools.json"}
    env = _env()
    for path in coded_files():
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for n in ast.walk(tree):
            fn = getattr(n, "func", None)
            if isinstance(n, ast.Call) and (getattr(fn, "id", None) == "Tool" or getattr(fn, "attr", None) == "Tool") and len(n.args) >= 3 \
                    and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
                out[n.args[0].value] = {"description": _text(n.args[1], env), "inputs": sorted(set(_schema_names(n.args[2]))), "kind": "coded",
                                        "file": os.path.relpath(path, root), "schemaChars": len(ast.unparse(n.args[2]))}
    return out


# ---- lint ---------------------------------------------------------------------------------------

_ABBR = re.compile(r"\b(e\.g|i\.e|etc|vs|approx|incl|no)$", re.I)
_PASSIVE = re.compile(r"\b(?:is|are|was|were|be|been|being)\s+(?:not\s+)?\w+ed\b", re.I)
_LIT = re.compile(r'"[^"]*"|`[^`]*`|“[^”]*”')


def sentences(text):
    """Sentences, split at . ! ? before a space (never in a decimal, e.g. or a literal)."""
    t = " ".join(str(text or "").split())
    # A full stop inside a quote or a {...}/[...] literal is not an end: mask them first.
    masked = list(t)
    depth, quote = 0, None
    for i, c in enumerate(t):
        if quote:
            if c == quote:
                quote = None
            masked[i] = "x" if c in ".!?" else c
            continue
        if c in "\"`":
            quote = c
        elif c in "{[":
            depth += 1
        elif c in "}]" and depth:
            depth -= 1
        elif depth and c in ".!?":
            masked[i] = "x"
    m_text = "".join(masked)
    out, start = [], 0
    for m in re.finditer(r"[.!?](?=\s+\S|$)", m_text):
        if _ABBR.search(t[start:m.start()]):
            continue
        out.append(t[start:m.end()].strip())
        start = m.end()
    if t[start:].strip():
        out.append(t[start:].strip())
    return [s for s in out if s]


def _strip_literals(s):
    s = _LIT.sub(" ", s)
    out, depth = [], 0
    for c in s:
        if c in "{[":
            depth += 1
            continue
        if c in "}]" and depth:
            depth -= 1
            continue
        if not depth:
            out.append(c)
    return "".join(out)


def _words(s):
    return [w for w in s.split() if re.search(r"[A-Za-z0-9]", w)]


def count(s, names=()):
    """Words of a sentence that count: literals left out, and a list of three or
    more names (inputs, tools, code words) counted as one word."""
    names = set(names)

    def is_name(w):
        w = w.strip(",;:()?.!")
        return w in names or bool(re.fullmatch(r"[a-z][a-z0-9]*_[a-z0-9_]*|[a-z]+[A-Z]\w*", w))

    out, run, glue = 0, 0, 0
    for w in _words(_strip_literals(s)) + ["."]:
        if w != "." and is_name(w):
            run += 1
            continue
        if run and w in ("or", "and"):
            glue += 1
            continue
        out += 1 if run >= 3 else run + glue
        run = glue = 0
        if w != ".":
            out += 1
    return out


def lint(text, names=()):
    """([(sentence, words)] over MAX_WORDS, passive count)."""
    long = []
    for s in sentences(text):
        n = count(s, names)
        if n > MAX_WORDS:
            long.append((s, n))
    return long, len(_PASSIVE.findall(text))


# ---- preservation --------------------------------------------------------------------------------

_NUM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")


def numbers(text):
    return set(_NUM.findall(_digits_only(text)))


def _digits_only(text):
    # "3MF", "2D", "x2" keep their digits: a number is a digit run not inside a word of letters around it.
    return re.sub(r"(?<=[A-Za-z_])\d+|\d+(?=[A-Za-z_]{2,}\w*\b(?<!mm)(?<!ms)(?<!deg))", " ", text)


def units(text):
    """Unit tokens: a long unit anywhere as a word, a one-letter unit after a number or as "(u)" / "in u"."""
    out = set()
    for u in UNITS:
        e = re.escape(u)
        if u == "in":  # the inch only where no word follows it: "1 in", "(in)", "mm | in"
            rx = r"(?:\d\s?|\(|\| )in(?=\s*[,.;:)\]\"|]|$)"
        elif len(u) >= 2:
            rx = r"(?:(?<=\d)|(?<![\w°/]))" + e + r"(?![\w²³/])"
        else:
            rx = r"\d\s?" + e + r"(?![\w²³/])|\(" + e + r"\)|\bin " + e + r"(?![\w²³/])"
        if re.search(rx, text):
            out.add(u)
    return out


def mentioned(text, names):
    return {n for n in names if re.search(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])", text)}


def guards(text):
    return {g for g, rx in GUARDS.items() if re.search(rx, text, re.I)}


def lost(name, old, new, inputs, tools):
    """[(kind, token)] of the original the new text lost, less the waivers."""
    out = []
    for kind, fn in (("number", numbers), ("unit", units), ("guard", guards)):
        for tok in sorted(fn(old) - fn(new)):
            out.append((kind, tok))
    for tok in sorted(mentioned(old, inputs) - mentioned(new, inputs)):
        out.append(("input", tok))
    others = [t for t in tools if t != name]
    for tok in sorted(mentioned(old, others) - mentioned(new, others)):
        out.append(("tool", tok))
    return [x for x in out if (name, x[1]) not in WAIVERS]


# ---- reports -------------------------------------------------------------------------------------

def card_tokens(name, e):
    if e["kind"] == "data":
        return None
    return int(round((len(name) + len(e["description"]) + e["schemaChars"] + 40) / CHARS_PER_TOKEN))


def check(root=ROOT):
    with open(ORIGINALS, encoding="utf-8") as f:
        orig = json.load(f)["tools"]
    now = collect(root)
    tools = sorted(now)
    faults, long, passive = [], [], 0
    for name in tools:
        e = now[name]
        names = set(e["inputs"]) | set(tools)
        ls, p = lint(e["description"], names)
        long += [(name, s, n) for s, n in ls]
        passive += p
        if name in orig:
            for kind, tok in lost(name, orig[name]["description"], e["description"], orig[name]["inputs"], tools):
                faults.append((name, kind, tok))
    missing = sorted(set(orig) - set(now))
    return {"tools": len(tools), "long": long, "passive": passive, "lost": faults, "missing": missing}


def write_originals(root=ROOT):
    now = collect(root)
    doc = {"about": "The hub's tool descriptions as on main before the ASD-STE100 rewrite (scripts/ste_check.py --originals).",
           "tools": {n: {"description": e["description"], "inputs": e["inputs"], "kind": e["kind"]} for n, e in sorted(now.items())}}
    with open(ORIGINALS, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
        f.write("\n")
    return len(now)


def measure(root=ROOT):
    """Token measures, before (originals) and after (the tree)."""
    with open(os.path.join(root, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
        entries = json.load(f)["entries"]
    with open(ORIGINALS, encoding="utf-8") as f:
        orig = json.load(f)["tools"]
    now = collect(root)

    def tok(x):
        text = x if isinstance(x, str) else json.dumps(x, separators=(",", ":"), ensure_ascii=False)
        return int(round(len(text) / CHARS_PER_TOKEN))

    out = {}
    for label, desc in (("before", {n: orig[n]["description"] for n in orig}), ("after", {n: now[n]["description"] for n in now})):
        cards = {}
        for n, e in now.items():
            if e["kind"] == "data":
                cards[n] = tok({"name": n, "description": desc[n], "inputSchema": entries[n]["inputSchema"]})
            else:
                cards[n] = int(round((len(n) + len(desc[n]) + e["schemaChars"] + 40) / CHARS_PER_TOKEN))
        vals = sorted(cards.values())
        dcards = sorted(v for n, v in cards.items() if now[n]["kind"] == "data")
        out[label] = {"tools": len(desc), "descChars": sum(len(v) for v in desc.values()), "descTokens": int(round(sum(len(v) for v in desc.values()) / CHARS_PER_TOKEN)),
                      "cardTokens": sum(vals), "cardMedian": statistics.median_low(vals), "cardLargest": vals[-1],
                      "largestTool": max(cards, key=cards.get), "dataCardMedian": dcards[len(dcards) // 2], "dataCardLargest": dcards[-1]}
    return out


def main(argv):
    if "--originals" in argv:
        print("originals:", write_originals())
        return 0
    if "--measure" in argv:
        print(json.dumps(measure(), indent=1))
        return 0
    r = check()
    for name, s, n in r["long"]:
        print(f"LONG {name} ({n}): {s}")
    for name, kind, tok in r["lost"]:
        print(f"LOST {name}: {kind} {tok!r}")
    print(f"tools {r['tools']}, long sentences {len(r['long'])}, lost tokens {len(r['lost'])}, missing {r['missing']}, passive warnings {r['passive']}, waivers {len(WAIVERS)}")
    return 1 if r["long"] or r["lost"] or r["missing"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
