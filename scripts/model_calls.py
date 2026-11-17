#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""A hardening model (docs/hardening/models/*.json) as a batch file the hub accepts.

    python3 scripts/model_calls.py model.json -o model-batch.json
    python3 scripts/model_calls.py --all docs/hardening/models [--out-dir DIR]

A model is a list of { tool, arguments, expect } or an object { calls: [...] }
with notes beside it. batch { file } wants [{ tool, arguments }] or { calls,
rollback, stopOnError } and nothing else in a call but to and profile
(agentlink/tools.py batch(): a call is rebuilt from tool, arguments, profile
and to; whatever else it carries is dropped without a word). This writes

    { "calls": [{ tool, arguments, to?, profile? }], "rollback": false, "stopOnError": false }

rollback false: a model runs past its refusals and uses history_undo,
history_redo and history_restore, which a batch that rolls back refuses.

Checked on the way, each with the call's index (the index batch's calls.N,
from and $from count by), in the order the hub would meet them:

  the batch's own   a call that is no object, a tool that is no name, arguments
                    that are no object, a to that is no .json path, a batch
                    inside the batch: the hub refuses the WHOLE list for one
                    of these ("Nothing was run")
  placeholders      "<the name from the call above>" left in the arguments
  references        { $from } / { $file }: both in one, another key beside
                    them, a $from that is no index or not before its call
                    (agentlink/chain.py)
  the tool's input  for a tool in agentlink/data/tools.json, what the hub's
                    check_input refuses (agentlink/protocol.py): a field the
                    schema does not have (after the hub's synonyms: body for
                    object, path for file …), a required field missing, a
                    top-level value of the wrong type or outside its enum. A
                    reference stands for its value, so its type is not
                    checked. "nested" lines go one level further than the hub
                    does (a list's items, an object's fields): the hub lets
                    those through to the tool, which may refuse them itself.

A tool that is not in tools.json (the hub's core tools in code, an add-on's)
is listed under "not checked", never as a violation. A violation on a call
whose expect begins with REFUSED (refused, REFUSAL) is listed as expected and
does not count. Exit 1 when a violation counts, else 0. Plain Python: no
FreeCAD, nothing run.
"""
import argparse
import ast
import glob
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLS_JSON = os.path.join(ROOT, "agentlink", "data", "tools.json")
PROTOCOL = os.path.join(ROOT, "agentlink", "protocol.py")
FILE, FROM, AT = "$file", "$from", "$at"
KEPT = ("tool", "arguments", "to", "profile")
# "<the name from the call above>"; not FreeCAD's own <<Label>> in an expression.
PLACEHOLDER = re.compile(r"(?<!<)<[^<>]{3,}>(?!>)")
EXPECTS_REFUSAL = re.compile(r"^\s*(REFUS|refus)")
_PY = {"string": (str,), "number": (int, float), "integer": (int,), "boolean": (bool,), "array": (list,), "object": (dict,)}
_SAID = {"string": "text", "number": "a number", "integer": "a whole number", "boolean": "true or false", "array": "a list", "object": "an object"}


def synonyms():
    """protocol.py's SYNONYMS, read from the source (it imports nothing here)."""
    try:
        with open(PROTOCOL, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "SYNONYMS" for t in node.targets):
                return ast.literal_eval(node.value)
    except (OSError, ValueError, SyntaxError):
        pass
    return {}


def load_schemas(path=TOOLS_JSON):
    with open(path, encoding="utf-8") as f:
        return {n: e.get("inputSchema") or {} for n, e in json.load(f)["entries"].items()}


def is_ref(v):
    return isinstance(v, dict) and (FILE in v or FROM in v)


def kind(v):
    if isinstance(v, bool):
        return "true/false"
    return {str: "text", int: "a number", float: "a number", list: "a list", dict: "an object", type(None): "null"}.get(type(v), type(v).__name__)


def type_ok(t, v):
    """As protocol._typed takes it: the type itself, or the same thing in
    another dress (a number or boolean as text, a list or object as its JSON)."""
    if not isinstance(t, str) or t not in _PY:
        return True  # a list of types, or none: the hub does not check it
    ok = isinstance(v, _PY[t]) and not (t in ("number", "integer") and isinstance(v, bool))
    if ok and isinstance(v, float) and not math.isfinite(v):
        ok = False
    if not ok and isinstance(v, str):
        text = v.strip()
        try:
            if t == "number":
                ok = math.isfinite(float(text))
            elif t == "integer":
                ok = text.lstrip("-").isdigit()
            elif t == "boolean":
                ok = text.lower() in ("true", "false")
            elif t in ("array", "object"):
                ok = isinstance(json.loads(text), _PY[t])
        except ValueError:
            ok = False
    if not ok and t == "integer" and isinstance(v, float) and v.is_integer():
        ok = True
    return ok


def enum_ok(spec, v):
    if "enum" not in spec or v in spec["enum"]:
        return True
    return isinstance(v, str) and v.lower() in {str(e).lower() for e in spec["enum"]}


def value_said(where, spec, v):
    """What the hub would refuse about one top-level value, or None."""
    t = spec.get("type")
    if not type_ok(t, v):
        return f"{where}: {_SAID[t]}, not {kind(v)}"
    if not enum_ok(spec, v):
        return f"{where}: one of {', '.join(map(str, spec['enum']))} — not {v!r}"
    return None


def nested_said(where, spec, v):
    """One level below what the hub checks: a list's items, an object's own fields."""
    out = []
    if isinstance(v, list) and isinstance(spec.get("items"), dict) and spec["items"]:
        for i, x in enumerate(v):
            if x is None or is_ref(x):
                continue
            said = value_said(f"{where}.{i}", spec["items"], x)
            if said:
                out.append(said)
    if isinstance(v, dict) and isinstance(spec.get("properties"), dict):
        props = spec["properties"]
        if spec.get("additionalProperties") is False:
            out += [f"{where}.{k}: not a known field — the fields here: {', '.join(props) or 'none'}" for k in v if k not in props]
        out += [f"{where}.{k}: required" for k in spec.get("required", []) if k not in v]
        for k, x in v.items():
            if isinstance(props.get(k), dict) and x is not None and not is_ref(x):
                said = value_said(f"{where}.{k}", props[k], x)
                if said:
                    out.append(said)
    return out


def check_input(schema, args, syn):
    """(violations as the hub's check_input would refuse — it stops at the
    first; all are listed here — and the nested ones it does not look at)."""
    args = dict(args)
    props = schema.get("properties", {}) or {}
    if "background" not in props:
        args.pop("background", None)  # any read takes it: taken off before the check
    for k in [k for k in args if k not in props]:
        alt = next((s for s in syn.get(k, ()) if s in props and s not in args), None)
        if alt is not None:
            args[alt] = args.pop(k)
    bad, nested = [], []
    if schema.get("additionalProperties") is False:
        bad += [f"input.{k}: not a known field — the fields here: {', '.join(props) or 'none'}" for k in args if k not in props]
    bad += [f"input.{k}: required" for k in schema.get("required", []) if k not in args]
    for k, v in args.items():
        spec = props.get(k)
        if not isinstance(spec, dict) or v is None or is_ref(v):
            continue
        said = value_said(f"input.{k}", spec, v)
        if said:
            bad.append(said)
        else:
            nested += nested_said(f"input.{k}", spec, v)
    return bad, nested


def walk(v, where="arguments"):
    """Every (where, value) inside v, keys of objects too (as where + ' key')."""
    yield where, v
    if is_ref(v):
        return
    if isinstance(v, dict):
        for k, x in v.items():
            yield f"{where} key", k
            yield from walk(x, f"{where}.{k}")
    elif isinstance(v, list):
        for i, x in enumerate(v):
            yield from walk(x, f"{where}.{i}")


def refs_said(args, index):
    """What chain.py would refuse about the references in a call's arguments."""
    out = []
    for where, v in walk(args):
        if not is_ref(v):
            continue
        if FILE in v and FROM in v:
            out.append(f"{where}: {FILE} or {FROM}, not both in one reference")
            continue
        head = FILE if FILE in v else FROM
        extra = sorted(k for k in v if k not in (head, AT))
        if extra:
            out.append(f"{where}: {{ {head} }} takes only {AT} beside it, not {', '.join(extra)}")
        if AT in v and (isinstance(v[AT], bool) or not isinstance(v[AT], (str, int))):
            out.append(f"{where}: {AT} is a dotted path of keys and list indices")
        if head == FROM:
            n = v[FROM]
            if isinstance(n, bool) or not isinstance(n, int) or n < 0:
                out.append(f"{where}: {FROM} is the index of an earlier call, not {n!r}")
            elif n >= index:
                out.append(f"{where}: {FROM} {n} is not before this call (calls.{index})")
        elif not isinstance(v[FILE], str) or not v[FILE].strip():
            out.append(f"{where}: {FILE} is a .json file's path")
    return out


def placeholders(args):
    return [f"{where}: {v!r}" for where, v in walk(args) if isinstance(v, str) and PLACEHOLDER.search(v)]


def load_model(path):
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    calls = data.get("calls") if isinstance(data, dict) else data
    if not isinstance(calls, list):
        raise ValueError(f"{path}: no list of calls — [{{ tool, arguments }} …] or {{ calls: [...] }}")
    return calls


def convert(calls, schemas, syn):
    """(the batch's calls, report). report: violations [(index, tool, words)],
    expected (the same, on calls whose expect says REFUSED), nested, dropped
    { key: count }, unchecked { tool: [indices] }, refs [(index, source index)]."""
    out = []
    rep = {"violations": [], "expected": [], "nested": [], "dropped": {}, "unchecked": {}, "refs": []}

    def said(i, tool, words, expect):
        rep["expected" if isinstance(expect, str) and EXPECTS_REFUSAL.match(expect) else "violations"].append((i, tool, words))

    for i, c in enumerate(calls):
        if not isinstance(c, dict) or not isinstance(c.get("tool"), str):
            rep["violations"].append((i, "?", "the batch's own: each call is { tool, arguments } with tool a tool's name — the hub runs nothing of a list with this in it"))
            out.append({"tool": str(c.get("tool")) if isinstance(c, dict) else "?", "arguments": {}})
            continue
        tool, expect = c["tool"], c.get("expect")
        args = c.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args) if args.strip() else {}
            except ValueError:
                args = None
        if not isinstance(args, dict):
            rep["violations"].append((i, tool, "the batch's own: arguments is no object — the hub runs nothing of a list with this in it"))
            args = {}
        one = {"tool": tool, "arguments": args}
        if c.get("profile"):
            one["profile"] = True
        if c.get("to") is not None:
            to = c["to"]
            if not isinstance(to, str) or not to.strip() or not to.lower().endswith(".json"):
                rep["violations"].append((i, tool, f"the batch's own: to is a .json file's path, not {to!r} — the hub runs nothing of a list with this in it"))
            one["to"] = to
        for k in c:
            if k not in KEPT:
                rep["dropped"][k] = rep["dropped"].get(k, 0) + 1
        out.append(one)
        if tool == "batch":
            rep["violations"].append((i, tool, "the batch's own: a batch does not run another batch — the hub runs nothing of a list with this in it (run this call alone)"))
            continue
        for w in placeholders(args):
            said(i, tool, f"placeholder {w}", None)
        for w in refs_said(args, i):
            said(i, tool, w, expect)
        rep["refs"] += [(i, v[FROM], where) for where, v in walk(args) if is_ref(v) and isinstance(v.get(FROM), int) and not isinstance(v.get(FROM), bool)]
        if tool not in schemas:
            rep["unchecked"].setdefault(tool, []).append(i)
            continue
        bad, nested = check_input(schemas[tool], args, syn)
        for w in bad:
            said(i, tool, w, expect)
        rep["nested"] += [(i, tool, w) for w in nested]
    return out, rep


def report(name, calls, rep, quiet=False):
    lines = [f"{name}: {len(calls)} calls; {len(rep['violations'])} violations, {len(rep['expected'])} on calls that expect a refusal, {len(rep['nested'])} nested"]
    for label, key in (("VIOLATION", "violations"), ("expected", "expected"), ("nested", "nested")):
        lines += [f"  {label} calls.{i} ({tool}): {words}" for i, tool, words in rep[key]]
    if not quiet:
        if rep["refs"]:
            spans = ", ".join(f"{i}<-{n}" for i, n, _w in rep["refs"])
            far = max(i - n for i, n, _w in rep["refs"])
            lines.append(f"  $from references (call<-source): {spans}; the longest reaches {far} calls back — a batch answered in parts refuses one that reaches into an earlier part")
        if rep["unchecked"]:
            lines.append("  not checked (not in tools.json: the hub's own in code, or an add-on's): " + ", ".join(f"{t} x{len(ix)}" for t, ix in sorted(rep["unchecked"].items())))
        if rep["dropped"]:
            lines.append("  left out of each call: " + ", ".join(f"{k} x{n}" for k, n in sorted(rep["dropped"].items())))
    return "\n".join(lines)


def write(path, calls):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"calls": calls, "rollback": False, "stopOnError": False}, f, ensure_ascii=False, indent=1)
        f.write("\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="A hardening model as a batch file, its calls checked against the tools' input schemas.")
    ap.add_argument("model", nargs="?", help="a model file (a list of calls, or { calls })")
    ap.add_argument("-o", "--out", help="the batch file to write (default: <model>-batch.json beside the model)")
    ap.add_argument("--all", metavar="DIR", help="every *.json model in DIR: checked, and written only with --out-dir")
    ap.add_argument("--out-dir", help="with --all: write <name>-batch.json for each model here")
    ap.add_argument("--tools", default=TOOLS_JSON, help="tools.json (default: this checkout's agentlink/data/tools.json)")
    ap.add_argument("--quiet", action="store_true", help="only the summary line and the violations")
    a = ap.parse_args(argv)
    if bool(a.model) == bool(a.all):
        ap.error("a model file, or --all DIR")
    schemas, syn = load_schemas(a.tools), synonyms()
    bad = 0
    if a.all:
        if a.out_dir:
            os.makedirs(a.out_dir, exist_ok=True)
        for path in sorted(glob.glob(os.path.join(a.all, "*.json"))):
            name = os.path.basename(path)
            try:
                calls, rep = convert(load_model(path), schemas, syn)
            except ValueError as e:
                print(f"{name}: not a call list ({str(e).split(': ', 1)[-1]}) — skipped")
                continue
            print(report(name, calls, rep, a.quiet))
            bad += len(rep["violations"])
            if a.out_dir:
                write(os.path.join(a.out_dir, name[:-5] + "-batch.json"), calls)
    else:
        calls, rep = convert(load_model(a.model), schemas, syn)
        out = a.out or (a.model[:-5] if a.model.lower().endswith(".json") else a.model) + "-batch.json"
        write(out, calls)
        print(report(os.path.basename(a.model), calls, rep, a.quiet))
        print(f"written: {out}")
        bad = len(rep["violations"])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
