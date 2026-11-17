#!/usr/bin/env python3
# SPDX-License-Identifier: LGPL-2.1-or-later
"""Merge batch chunk files into one batch file, keeping chained references right.

    python3 merge_chunks.py -o all-srm.json srm-00.json srm-01-heavy.json srm-02.json ...
    python3 merge_chunks.py --self-test [--chain /path/to/agentlink/chain.py]

Why. Agent Link's batch numbers its calls from 0 through the whole list it is
given, and { "$from": n, "$at": "a.0.b" } names call n of THAT list
(agentlink/chain.py _from_call; docs/hardening/chain-findings.md: "$from
counts calls through the whole list (as from/next do)"). A `from: k`
continuation does not renumber: the calls keep their indices in the whole
list. So a chunk file written to run as its own batch counts from its own
first call, and pasted behind other chunks every $from in it points too
early (run 3: five calls read doc_new's answer, call 0, and were refused).
This script adds each chunk's offset in the merged list to the $from
indices inside it.

What is rewritten: every object holding "$from" anywhere inside a call's
arguments (the only place the hub resolves references). "$file" references
and per-call "to" are left as they are. Nothing else in a call is touched.

Each chunk is a JSON list of calls or an object { "calls": [...] } (rollback
and stopOnError beside it are carried over when the chunks agree).

Checked, and refused with the place named: a $from that is not a whole
number from 0, one that does not point at an earlier call of its own chunk
(the hub would refuse it), and an object with both $file and $from.
--absolute: the chunks were cut out of one list and their $from indices
already count through that whole list: nothing is shifted, only checked
against the merged list.

Not solved here: a merged batch that the hub answers in parts (its time
budget; `from: next` goes on) cannot follow a $from into an earlier part:
the hub refuses with invalid_state and asks for to: "file.json" + $file. The
summary lists every reference with its span so the long ones can be given a
file instead.
"""
import argparse
import copy
import json
import os
import sys
import tempfile

FILE, FROM, AT = "$file", "$from", "$at"


class Bad(Exception):
    pass


def load_chunk(path):
    """(calls, settings) of one chunk file."""
    with open(path, encoding="utf-8-sig") as f:
        data = json.load(f)
    settings = {}
    if isinstance(data, dict):
        if not isinstance(data.get("calls"), list):
            raise Bad(f"{path}: an object without a calls list")
        settings = {k: data[k] for k in ("rollback", "stopOnError") if k in data}
        data = data["calls"]
    if not isinstance(data, list):
        raise Bad(f"{path}: a list of calls or {{ calls: [...] }}")
    calls = []
    for i, c in enumerate(data):
        if isinstance(c, str):  # the hub takes a call sent as its JSON text
            try:
                c = json.loads(c)
            except ValueError:
                raise Bad(f"{path}: calls.{i} is text that is not a call's JSON") from None
        if not isinstance(c, dict) or not isinstance(c.get("tool"), str):
            raise Bad(f"{path}: calls.{i} is not {{ tool, arguments }}")
        calls.append(c)
    return calls, settings


def shift_refs(value, offset, index, limit_low, where, found, path="arguments"):
    """value with every $from inside moved by offset (a new value).

    index: this call's index in the numbering the references use (its chunk's,
    or the whole list's with --absolute); limit_low: the lowest index a
    reference may name (0 in a chunk). found gets (path, old, new, at)."""
    if isinstance(value, dict):
        if FROM in value:
            if FILE in value:
                raise Bad(f"{where} {path}: {FILE} and {FROM} in one reference (the hub refuses it)")
            n = value[FROM]
            if isinstance(n, bool) or not isinstance(n, int) or n < 0:
                raise Bad(f"{where} {path}: {FROM} must be a call's index, a whole number from 0, not {n!r}")
            if n >= index:
                raise Bad(f"{where} {path}: {FROM} {n} is not before this call (index {index} in its numbering): a call takes only an earlier call's answer")
            if n < limit_low:
                raise Bad(f"{where} {path}: {FROM} {n} lies before index {limit_low}")
            out = dict(value)
            out[FROM] = n + offset
            found.append((path, n, n + offset, value.get(AT)))
            return out
        return {k: shift_refs(v, offset, index, limit_low, where, found, f"{path}.{k}") for k, v in value.items()}
    if isinstance(value, list):
        return [shift_refs(v, offset, index, limit_low, where, found, f"{path}.{i}") for i, v in enumerate(value)]
    return value


def merge(chunks, absolute=False):
    """chunks: [(name, calls, settings)]. Returns (batch, report)."""
    merged, rows, refs, settings = [], [], [], {}
    total = sum(len(c) for _, c, _ in chunks)
    for name, calls, sets in chunks:
        offset = len(merged)
        for k, v in sets.items():
            if k in settings and settings[k] != v:
                raise Bad(f"{name}: {k} is {v!r} here and {settings[k]!r} in an earlier chunk: give one value for the merged batch")
            settings[k] = v
        for i, c in enumerate(calls):
            where = f"{name} calls.{i} ({c['tool']})"
            c = copy.deepcopy(c)
            args = c.get("arguments")
            if isinstance(args, str) and args.strip():
                try:
                    parsed = json.loads(args)
                except ValueError:
                    raise Bad(f"{where}: arguments is text that is not JSON") from None
                if FROM in args:
                    args = parsed  # rewritten below, and kept as an object
            if isinstance(args, (dict, list)):
                found = []
                if absolute:
                    args = shift_refs(args, 0, offset + i, 0, where, found)
                else:
                    args = shift_refs(args, offset, i, 0, where, found)
                c["arguments"] = args
                for path, old, new, at in found:
                    refs.append({"call": offset + i, "tool": c["tool"], "chunk": name, "inChunk": i, "where": path, "was": old, "now": new, "at": at, "span": offset + i - new})
            merged.append(c)
        rows.append({"chunk": name, "offset": offset, "calls": len(calls)})
    assert len(merged) == total
    # Two calls writing the same to-file: the later one wins; a $file read
    # in between still gets the earlier one. Said, not refused.
    seen, twice = {}, []
    for i, c in enumerate(merged):
        if c.get("to") is not None:
            if c["to"] in seen:
                twice.append({"to": c["to"], "calls": [seen[c["to"]], i]})
            seen[c["to"]] = i
    batch = {**settings, "calls": merged}
    return batch, {"calls": total, "chunks": rows, "references": refs, **({"sameTo": twice} if twice else {})}


# ---- a check that needs no FreeCAD: follow the references ---------------------------------


def follow(value, answers, index):
    """value with its $from references replaced from answers { index: answer }:
    what the hub's chain.resolve does, for the self-test."""
    if isinstance(value, dict):
        if FROM in value:
            cur = answers[value[FROM]]
            assert value[FROM] < index
            for part in str(value.get(AT, "")).split("."):
                if part == "":
                    continue
                cur = cur[int(part)] if isinstance(cur, list) else cur[part]
            return cur
        return {k: follow(v, answers, index) for k, v in value.items()}
    if isinstance(value, list):
        return [follow(v, answers, index) for v in value]
    return value


def self_test(chain_path=None):
    tmp = tempfile.mkdtemp(prefix="merge-chunks-")

    def put(name, data):
        p = os.path.join(tmp, name)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return p

    # Three chunks as run 3 had them: each counts from its own first call.
    a = put("a.json", [
        {"tool": "doc_new", "arguments": {"name": "T"}},
        {"tool": "part_primitive", "arguments": {"kind": "box", "name": "Block"}},
        {"tool": "object_get", "arguments": {"object": {FROM: 1, AT: "body"}}},
    ])
    b = put("b.json", {"rollback": False, "calls": [
        {"tool": "section_to_sketch", "arguments": {"section": "Mid"}},
        {"tool": "pd_pad", "arguments": {"body": {FROM: 0, AT: "body"}, "sketch": "MidProfile", "length": 5}},
        {"tool": "doc_save", "arguments": {}, "to": "saved.json"},
    ]})
    c = put("c.json", [
        {"tool": "flat_edges", "arguments": {}},
        {"tool": "flat_curvature", "arguments": {"chains": [{FROM: 0, AT: "chains.1.chain"}], "note": {FILE: "saved.json", AT: "path"}}},
        {"tool": "flat_profile", "arguments": {"chains": [{FROM: 0, AT: "chains.-1.chain"}], "about": {"deep": [{"x": {FROM: 1, AT: "unit"}}]}}},
    ])
    names = [a, b, c]
    chunks = [(os.path.basename(p), *load_chunk(p)) for p in names]

    def answer(chunk, i, tool):
        tag = f"{chunk}:{i}:{tool}"
        return {"body": f"body of {tag}", "unit": f"unit of {tag}", "path": tag, "chains": [{"chain": f"{tag}/c0"}, {"chain": f"{tag}/c1"}]}

    # What each chunk's calls get when it runs as its own batch …
    alone = []
    for name, calls, _ in chunks:
        ans = {i: answer(name, i, c["tool"]) for i, c in enumerate(calls)}
        alone += [follow(c.get("arguments"), ans, i) for i, c in enumerate(calls)]
    # … and what the same calls get in the merged batch.
    batch, report = merge(chunks)
    flat = [(name, i, c["tool"]) for name, calls, _ in chunks for i, c in enumerate(calls)]
    ans = {k: answer(*flat[k]) for k in range(len(flat))}
    together = [follow(c.get("arguments"), ans, k) for k, c in enumerate(batch["calls"])]
    assert together == alone, "a merged reference reads another call's answer"

    calls = batch["calls"]
    assert [c["tool"] for c in calls] == [t for _, _, t in flat]
    assert calls[2]["arguments"]["object"] == {FROM: 1, AT: "body"}  # first chunk: offset 0
    assert calls[4]["arguments"]["body"] == {FROM: 3, AT: "body"}  # 0 + 3
    assert calls[7]["arguments"]["chains"] == [{FROM: 6, AT: "chains.1.chain"}]  # 0 + 6
    assert calls[7]["arguments"]["note"] == {FILE: "saved.json", AT: "path"}  # $file untouched
    assert calls[8]["arguments"]["about"]["deep"][0]["x"] == {FROM: 7, AT: "unit"}  # nested, 1 + 6
    assert calls[5]["to"] == "saved.json" and batch["rollback"] is False
    assert [r["offset"] for r in report["chunks"]] == [0, 3, 6]
    assert [(r["call"], r["was"], r["now"]) for r in report["references"]] == [(2, 1, 1), (4, 0, 3), (7, 0, 6), (8, 0, 6), (8, 1, 7)]
    # The chunk files themselves are not changed.
    assert load_chunk(c)[0][1]["arguments"]["chains"] == [{FROM: 0, AT: "chains.1.chain"}]

    # --absolute: one list cut in pieces, its indices already whole-list ones.
    whole = copy.deepcopy(batch["calls"])
    pieces = [("p0", whole[:4], {}), ("p1", whole[4:], {})]
    again, _ = merge(pieces, absolute=True)
    assert again["calls"] == batch["calls"]

    # Refused, with the place named.
    def refused(chunk_calls, words, **kw):
        try:
            merge([("x.json", chunk_calls, {})], **kw)
        except Bad as e:
            assert words in str(e), str(e)
            return
        raise AssertionError(f"not refused: {words}")

    refused([{"tool": "t", "arguments": {"a": {FROM: 0}}}], "not before this call")
    refused([{"tool": "s", "arguments": {}}, {"tool": "t", "arguments": {"a": {FROM: True}}}], "whole number")
    refused([{"tool": "s", "arguments": {}}, {"tool": "t", "arguments": {"a": {FROM: -1}}}], "whole number")
    refused([{"tool": "s", "arguments": {}}, {"tool": "t", "arguments": {"a": {FROM: 0, FILE: "f.json"}}}], "in one reference")
    try:
        merge([("a", [{"tool": "t"}], {"rollback": True}), ("b", [{"tool": "t"}], {"rollback": False})])
        raise AssertionError("two rollback values not refused")
    except Bad:
        pass

    # Arguments sent as JSON text are rewritten too; text with no reference stays text.
    got, _ = merge([("s", [{"tool": "u", "arguments": "{}"}], {}), ("t", [{"tool": "s", "arguments": {}}, {"tool": "t", "arguments": json.dumps({"a": {FROM: 0, AT: "k"}})}], {})])
    assert got["calls"][0]["arguments"] == "{}" and got["calls"][2]["arguments"] == {"a": {FROM: 1, AT: "k"}}

    checked = "this script's own follower"
    if chain_path:
        # The same proof through the hub's own resolver (plain Python, no FreeCAD).
        import importlib.util

        spec = importlib.util.spec_from_file_location("al_chain", chain_path)
        chain = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(chain)

        def no_file(name):  # the $file reference is not what is under test
            return {"path": f"file {name}"}

        hub_alone = []
        for name, cs, _ in chunks:
            an = {i: {"ok": True, "tool": c["tool"], "size": 1, "answer": answer(name, i, c["tool"])} for i, c in enumerate(cs)}
            hub_alone += [chain.resolve(c.get("arguments"), no_file, {k: v for k, v in an.items() if k < i}, i, 0) for i, c in enumerate(cs)]
        an = {k: {"ok": True, "tool": flat[k][2], "size": 1, "answer": answer(*flat[k])} for k in range(len(flat))}
        hub_together = [chain.resolve(c.get("arguments"), no_file, {k: v for k, v in an.items() if k < i}, i, 0) for i, c in enumerate(batch["calls"])]
        assert hub_together == hub_alone, "the hub's resolver reads another call's answer after the merge"
        # Unshifted (what run 3 did), the hub reads call 0 instead: the fault this script is for.
        raw = [c for _, cs, _ in chunks for c in cs]
        wrong = chain.resolve(raw[4]["arguments"], no_file, an, 4, 0)
        assert wrong["body"] == answer(*flat[0])["body"] != hub_together[4]["body"]
        # And across a `from:` part the hub refuses, as the docstring says.
        try:
            chain.resolve(batch["calls"][7]["arguments"], no_file, an, 7, 7)
            raise AssertionError("a reference into an earlier part was followed")
        except chain.Miss as e:
            assert e.code == "invalid_state"
        checked = f"the hub's resolver ({chain_path})"
    print(f"self-test passed: 9 calls in 3 chunks, 5 references ({checked}); files in {tmp}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Merge batch chunk files into one batch file, shifting $from references by each chunk's offset.")
    ap.add_argument("chunks", nargs="*", help="chunk files, in the order they run")
    ap.add_argument("-o", "--out", help="the merged batch file ({ calls: [...] })")
    ap.add_argument("--absolute", action="store_true", help="the chunks' $from indices already count through the whole list: check them, shift nothing")
    ap.add_argument("--map", help="write what went where (offsets, every reference) to this JSON file")
    ap.add_argument("--self-test", action="store_true", help="merge a tiny example and prove each reference still reads the same call")
    ap.add_argument("--chain", help="with --self-test: agentlink/chain.py, to prove it through the hub's own resolver too")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test(a.chain)
    if not a.chunks or not a.out:
        ap.error("give the chunk files and -o OUT (or --self-test)")
    try:
        chunks = [(os.path.basename(p), *load_chunk(p)) for p in a.chunks]
        batch, report = merge(chunks, a.absolute)
    except (Bad, OSError, ValueError) as e:
        print(f"merge_chunks: {e}", file=sys.stderr)
        return 1
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(batch, f, ensure_ascii=False, indent=1)
    if a.map:
        with open(a.map, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
    print(f"{a.out}: {report['calls']} calls from {len(chunks)} chunks, {len(report['references'])} $from references" + (" checked" if a.absolute else " shifted"))
    for r in report["references"]:
        print(f"  calls.{r['call']} ({r['tool']}) {r['where']}: $from {r['was']} -> {r['now']} ($at {r['at']!r}; {r['span']} calls back; {r['chunk']} calls.{r['inChunk']})")
    for t in report.get("sameTo", []):
        print(f"  note: calls {t['calls'][0]} and {t['calls'][1]} both write to {t['to']!r}: the later one replaces the file")
    return 0


if __name__ == "__main__":
    sys.exit(main())
