#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Check the hardening models before an unattended run on the Mac.

    python3 scripts/model_check.py [--answers DIR] [PATH ...]

PATH: model files or folders of them (default: this checkout's
docs/hardening/models, its models/alone and docs/hardening/*-model.json).
A folder gives every *.json in it.

Checked for each file, with the call's index:

  json        the file is JSON
  shape       a list of calls or { calls } (a live script, { steps }, is
              said and skipped: live_run runs it, not batch); extra lists of
              calls under needsPerson / restartsLast are checked the same way
  placeholder text a person had to fill in, left in a call's arguments
              ("<NOTE_ID>", "<the name from the call above>", "the
              reference copy: …"), keys included
  $from       a whole number before this call (agentlink/chain.py)
  $file       names the to: of an earlier call in the same list
  $at         where a live answer of the source call is at hand (--answers:
              files { results: [{ tool, ok, result | error }] }), the path is
              there in it, read as chain.py reads it (keys, list indices,
              -1 the last). A live answer is matched to the model by the order
              of its tools (difflib), so a model that gained a call still
              lines up.
  paths       no /home/… or /Users/… in the file (~/AgentLink/… instead)
  references  a doc_open of a file under hardening/refs/ is followed at once
              by doc_save { path: …hardening/work/… }: Agent Link's auto-save
              writes to the document's own file, so the reference itself
              must never be the document worked on

Exit 1 when anything but a $at without a live answer is wrong. Plain
Python: nothing is run on FreeCAD.
"""
import argparse
import difflib
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FILE, FROM, AT = "$file", "$from", "$at"
# "<the name from the call above>"; not FreeCAD's own <<Label>> in an expression.
PLACEHOLDER = re.compile(r"(?<!<)<[^<>]{2,}>(?!>)")
WORDS = re.compile(r"reference copy|from the call above|the call above answered", re.I)
PERSONAL = re.compile(r"/(home|Users)/")
EXTRA_LISTS = ("needsPerson", "restartsLast")


def is_ref(v):
    return isinstance(v, dict) and (FILE in v or FROM in v)


def walk(v, where="arguments"):
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


def follow(value, path):
    """(found, value or what is there instead) as chain.at reads path."""
    if path is None or path == "":
        return True, value
    cur = value
    for part in str(path).split("."):
        if isinstance(cur, dict):
            if part not in cur:
                return False, f"no key {part!r} (keys: {', '.join(list(map(str, cur))[:12])})"
            cur = cur[part]
        elif isinstance(cur, list):
            try:
                i = int(part)
            except ValueError:
                return False, f"{part!r} is not a list index"
            if not -len(cur) <= i < len(cur):
                return False, f"no index {i} in a list of {len(cur)}"
            cur = cur[i]
        else:
            return False, f"nothing under {part!r}"
    return True, cur


def load_answers(folder):
    out = {}
    for p in sorted(glob.glob(os.path.join(folder, "*.json"))):
        try:
            with open(p, encoding="utf-8-sig") as f:
                rows = json.load(f).get("results")
        except (OSError, ValueError, AttributeError):
            continue
        if isinstance(rows, list) and rows:
            out[os.path.basename(p)] = rows
    return out


def line_up(calls, answers):
    """{ model index: [(answer file, row)] } for every answer file whose tools
    run in the model's order (most of the file matched, in runs of 3 or more)."""
    tools = [c.get("tool") for c in calls]
    got = {}
    for name, rows in answers.items():
        a = [r.get("tool") for r in rows]
        sm = difflib.SequenceMatcher(None, a, tools, autojunk=False)
        blocks = [b for b in sm.get_matching_blocks() if b.size >= 3]
        if sum(b.size for b in blocks) < max(4, 0.6 * len(a)):
            continue
        for b in blocks:
            for k in range(b.size):
                got.setdefault(b.b + k, []).append((name, rows[b.a + k]))
    return got


class Report:
    def __init__(self):
        self.errors, self.warnings, self.lines = 0, 0, []

    def bad(self, words):
        self.errors += 1
        self.lines.append("  ERROR " + words)

    def warn(self, words):
        self.warnings += 1
        self.lines.append("  note  " + words)

    def ok(self, words):
        self.lines.append("  ok    " + words)


def check_calls(label, calls, answers, rep):
    if not isinstance(calls, list):
        rep.bad(f"{label}: no list of calls")
        return
    lined = line_up(calls, answers) if answers else {}
    tos = {}
    refs = 0
    for i, c in enumerate(calls):
        where = f"{label} calls.{i}"
        if not isinstance(c, dict) or not isinstance(c.get("tool"), str):
            rep.bad(f"{where}: not {{ tool, arguments }}")
            continue
        args = c.get("arguments") or {}
        if not isinstance(args, dict):
            rep.bad(f"{where} ({c['tool']}): arguments is no object")
            continue
        for w, v in walk(args):
            if isinstance(v, str) and (PLACEHOLDER.search(v) or WORDS.search(v)):
                rep.bad(f"{where} ({c['tool']}): placeholder at {w}: {v[:80]!r}")
        for w, v in walk(args):
            if not is_ref(v):
                continue
            refs += 1
            if FILE in v and FROM in v:
                rep.bad(f"{where} {w}: $file or $from, not both")
                continue
            extra = sorted(k for k in v if k not in (FILE, FROM, AT))
            if extra:
                rep.bad(f"{where} {w}: only $at beside the reference, not {', '.join(extra)}")
            if FROM in v:
                n = v[FROM]
                if isinstance(n, bool) or not isinstance(n, int) or n < 0 or n >= i:
                    rep.bad(f"{where} {w}: $from {n!r} is not an earlier call")
                    continue
                src = n
            else:
                src = tos.get(v[FILE])
                if src is None:
                    rep.bad(f"{where} {w}: $file {v[FILE]!r} is written by no earlier call's to:")
                    continue
            said = f"{where} ({c['tool']}) {w} <- calls.{src} ({calls[src].get('tool')}) $at {v.get(AT, '')!r}"
            rows = [(n_, r) for n_, r in lined.get(src, []) if r.get("tool") == calls[src].get("tool")]
            okrows = [(n_, r) for n_, r in rows if r.get("ok")]
            if not answers:
                continue
            if not okrows:
                rep.warn(f"{said}: no live answer of the source to read ({'refused in ' + rows[0][0] if rows else 'not in the answers'})")
                continue
            hits = [(n_, follow(r.get("result"), v.get(AT))) for n_, r in okrows]
            good = [(n_, val) for n_, (found, val) in hits if found]
            if good:
                n_, val = good[0]
                rep.ok(f"{said}: there in {n_} ({json.dumps(val, ensure_ascii=False)[:60]})")
            else:
                n_, (_f, why) = hits[0]
                rep.bad(f"{said}: not there in {n_}: {why}")
        if isinstance(c.get("to"), str):
            tos[c["to"]] = i
        p = args.get("path") if isinstance(args.get("path"), str) else ""
        if c["tool"] == "doc_open" and "hardening/refs/" in p:
            nxt = calls[i + 1] if i + 1 < len(calls) else {}
            np = (nxt.get("arguments") or {}).get("path", "") if isinstance(nxt, dict) else ""
            if nxt.get("tool") != "doc_save" or "hardening/work/" not in str(np):
                rep.bad(f"{where}: opens the reference {p} without doc_save {{ path: ~/AgentLink/hardening/work/… }} right after it")
            else:
                rep.ok(f"{where}: reference {p} worked on as {np}")
    return refs


def check_file(path, answers):
    rep = Report()
    name = os.path.relpath(path)
    try:
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
        data = json.loads(text)
    except (OSError, ValueError) as e:
        rep.bad(f"not JSON: {e}")
        return name, rep, "invalid"
    if PERSONAL.search(text):
        rep.bad("a /home/… or /Users/… path: write ~/AgentLink/… instead")
    if isinstance(data, dict) and isinstance(data.get("steps"), list) and "calls" not in data:
        return name, rep, f"a live script ({len(data['steps'])} steps): live_run runs it, not batch"
    calls = data.get("calls") if isinstance(data, dict) else data
    n = check_calls("", calls, answers, rep)
    kind = f"{len(calls) if isinstance(calls, list) else 0} calls, {n or 0} references"
    if isinstance(data, dict):
        for key in EXTRA_LISTS:
            extra = data.get(key)
            if isinstance(extra, dict):
                extra = extra.get("calls")
            if extra is not None:
                m = check_calls(key, extra, answers, rep)
                kind += f"; {key}: {len(extra)} calls, {m or 0} references"
        flags = [k for k in ("direct", "restarts", "sendAsIs") if data.get(k)]
        if flags:
            kind += "; " + ", ".join(flags)
    return name, rep, kind


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check hardening models: JSON, placeholders, references and their $at paths against live answers.")
    ap.add_argument("paths", nargs="*", help="model files or folders (default: this checkout's models)")
    ap.add_argument("--answers", help="a folder of live answers ({ results: [...] } per file)")
    ap.add_argument("--quiet", action="store_true", help="leave out the ok lines")
    a = ap.parse_args(argv)
    paths = a.paths or [os.path.join(ROOT, "docs", "hardening", "models"), os.path.join(ROOT, "docs", "hardening", "models", "alone")] + \
        sorted(glob.glob(os.path.join(ROOT, "docs", "hardening", "*-model.json")))
    files = []
    for p in paths:
        files += sorted(glob.glob(os.path.join(p, "*.json"))) if os.path.isdir(p) else [p]
    answers = load_answers(a.answers) if a.answers else {}
    errors = warnings = 0
    for f in files:
        name, rep, kind = check_file(f, answers)
        errors += rep.errors
        warnings += rep.warnings
        print(f"{name}: {kind}; {rep.errors} errors, {rep.warnings} notes")
        for ln in rep.lines:
            if not (a.quiet and ln.startswith("  ok")):
                print(ln)
    print(f"{len(files)} files, {errors} errors, {warnings} notes" + (f"; live answers: {len(answers)} files" if a.answers else "; no live answers given ($at not read)"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
