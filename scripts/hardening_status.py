# SPDX-License-Identifier: LGPL-2.1-or-later
"""The hardening pass's per-tool status list (docs/hardening): one data file,
status.json, and the table generated from it, STATUS.md.

    python3 scripts/hardening_status.py mark sketch_new,sketch_add --docs --health --description --headless --live --model SketcherTutorial --note "…" [--gap "why it is short"]
    python3 scripts/hardening_status.py render      # rewrite STATUS.md
    python3 scripts/hardening_status.py bars        # the counts as bars

A flag is only set by something that was done and measured: docs (checked
against FreeCAD's wiki and source), health (the shared health check seen on
its answer, or a read that needs none), description (rewritten), headless
(proven through the MCP tools on a test model), live (proven in the FreeCAD
window), model (the test model that proved it). gap: why a tool is not
proven, headless or live (from the findings, the notes or the code; else
"Not tested yet."). liveFormat2: proven live only on a cookbook format 2
draft, which is V2, so it does not count.

V1 only: inventory.json's groups hold the V1 tools. Tools that are not in
V1 are under notInV1 and are not counted.
"""
import json
import os
import sys

HERE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "hardening")
INV, STATUS, TABLE = (os.path.join(HERE, n) for n in ("inventory.json", "status.json", "STATUS.md"))
FLAGS = ("docs", "health", "description", "headless", "live")


def load():
    with open(INV, encoding="utf-8") as f:
        groups = json.load(f)["groups"]
    status = {}
    if os.path.isfile(STATUS):
        with open(STATUS, encoding="utf-8") as f:
            status = json.load(f)
    return groups, status


def load_inventory():
    with open(INV, encoding="utf-8") as f:
        return json.load(f)


def save_inventory(inv):
    """inventory.json in its own layout: one line for each group."""
    def one(x):
        return json.dumps(x, ensure_ascii=False)

    out = ["{", f'"about": {one(inv["about"])},', '"groups": {']
    items = list(inv["groups"].items())
    for i, (g, d) in enumerate(items):
        head = ", ".join(f"{one(k)}: {one(v)}" for k, v in d.items() if k != "tools")
        out.append(f'{one(g)}: {{{head}, "tools": {json.dumps(d["tools"], separators=(",", ":"))}}}' + ("," if i < len(items) - 1 else ""))
    out.append("}" + ("," if len(inv) > 2 else ""))
    rest = [k for k in inv if k not in ("about", "groups")]
    for i, k in enumerate(rest):
        out.append(f"{one(k)}: {json.dumps(inv[k], indent=1, ensure_ascii=False)}" + ("," if i < len(rest) - 1 else ""))
    out.append("}")
    with open(INV, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def save(status):
    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=1, sort_keys=True)
        f.write("\n")


def bar(n, total, width=20):
    k = round(width * n / total) if total else 0
    return "█" * k + "░" * (width - k)


# The sections of V1, in order: the hub first, then each add-on of the V1
# bundle (packaging/addons.json). A tool's section is its inventory repo.
SECTIONS = (("AgentLink-FreeCAD", "Agent Link (core)"), ("Workshop-FreeCAD", "Workshop"), ("ScanRuler-FreeCAD", "ScanRuler for FreeCAD"),
            ("Texturizer-FreeCAD", "Texturizer"), ("Tutor-FreeCAD", "Tutor"), ("AgentLink-OrcaSlicer", "Agent Link for OrcaSlicer"))
ROWS = (("proven", "proven on a test model"), ("headless", "  headless"), ("live", "  live in the window"), ("docs", "docs checked"),
        ("health", "health check seen"), ("description", "description rewritten"))
W = 26  # label width


def proven(s):
    return bool(s.get("headless") or s.get("live"))


def count(names, status):
    out = {f: sum(1 for t in names if status.get(t, {}).get(f)) for f in FLAGS}
    out["proven"] = sum(1 for t in names if proven(status.get(t, {})))
    out["total"] = len(names)
    return out


def counts(groups, status):
    tools = [(t, g, d["workbench"]) for g, d in groups.items() for t in d["tools"]]
    c = count([t for t, _g, _w in tools], status)
    return c.pop("total"), c, tools


def sections(groups, status):
    """[{repo, title, counts, parts: [{name, proven, total}]}]: the hub's parts
    are its workbenches, an add-on's parts are its groups."""
    out = []
    for repo, title in SECTIONS:
        mine = [(g, d) for g, d in groups.items() if d["repo"] == repo]
        names = [t for _g, d in mine for t in d["tools"]]
        parts = []
        for g, d in mine:
            key = d["workbench"] if repo == "AgentLink-FreeCAD" else d.get("listedIn", g)
            p = next((x for x in parts if x["name"] == key), None)
            if p is None:
                p = {"name": key, "proven": 0, "total": 0}
                parts.append(p)
            p["total"] += len(d["tools"])
            p["proven"] += sum(1 for t in d["tools"] if proven(status.get(t, {})))
        out.append({"repo": repo, "title": title, "counts": count(names, status), "parts": parts})
    return out


def row(label, n, total):
    return f"{label:<{W}}{bar(n, total)} {n:>3}/{total}"


def bars(groups, status):
    total, c, _tools = counts(groups, status)
    lines = ["Per-tool status, all of V1 (measured: counted from docs/hardening/status.json)"]
    lines += [row(label, c[key], total) for key, label in ROWS]
    secs = sections(groups, status)
    lines += ["", "By section (tools proven / total)"]
    lines += [row(s["title"], s["counts"]["proven"], s["counts"]["total"]) for s in secs]
    lines += ["", f"{secs[0]['title']} by workbench (tools proven / total)"]
    lines += [row(p["name"], p["proven"], p["total"]) for p in secs[0]["parts"]]
    return "\n".join(lines)


def render(groups, status):
    y = lambda v: "yes" if v else "–"  # noqa: E731
    out = ["# Hardening pass: per-tool status", "",
           "Generated by `scripts/hardening_status.py render` from `status.json` and `inventory.json`. Do not edit by hand.", "",
           "```", bars(groups, status), "```", ""]
    last = None
    for g, d in groups.items():
        if d["workbench"] != last:
            last = d["workbench"]
            out += [f"## {last}", ""]
        out += [f"### {g} ({d['repo']})", "", "| tool | docs | health | description | headless | live | model | note |", "|---|---|---|---|---|---|---|---|"]
        for t in d["tools"]:
            s = status.get(t, {})
            note = " ".join(x for x in (s.get("note", ""), f"Gap: {s['gap']}" if s.get("gap") else "") if x)
            out.append(f"| `{t}` | {y(s.get('docs'))} | {y(s.get('health'))} | {y(s.get('description'))} | {y(s.get('headless'))} | {y(s.get('live'))} | {s.get('model', '')} | {note} |")
        out.append("")
    inv = load_inventory()
    if inv.get("notInV1") or inv.get("unlisted"):
        out += ["## Not in V1 (not counted)", "", "| tool | repo | why |", "|---|---|---|"]
        out += [f"| `{t}` | {e['repo']} | {e['why']} |" for t, e in inv.get("notInV1", {}).get("tools", {}).items()]
        out += [f"| {e['name']} | – | {e['why']} |" for e in inv.get("notInV1", {}).get("features", [])]
        out += ["", "## Callable, not listed (not counted)", "", "| tool | why |", "|---|---|"]
        out += [f"| `{t}` | {why} |" for t, why in inv.get("unlisted", {}).items()]
        out.append("")
    with open(TABLE, "w", encoding="utf-8") as f:
        f.write("\n".join(out))


def main(argv):
    groups, status = load()
    known = {t for d in groups.values() for t in d["tools"]}
    if argv[:1] == ["mark"] and len(argv) >= 2:
        names = [n for n in argv[1].split(",") if n]
        bad = [n for n in names if n not in known]
        if bad:
            sys.exit(f"not in the inventory: {', '.join(bad)}")
        rest = argv[2:]
        for n in names:
            s = status.setdefault(n, {})
            i = 0
            while i < len(rest):
                a = rest[i]
                if a.lstrip("-") in FLAGS:
                    s[a.lstrip("-")] = True
                elif a in ("--model", "--note", "--gap") and i + 1 < len(rest):
                    i += 1
                    s[a[2:]] = rest[i]
                else:
                    sys.exit(f"unknown: {a}")
                i += 1
        save(status)
        render(groups, status)
    elif argv[:1] == ["render"]:
        render(groups, status)
    elif argv[:1] == ["bars"]:
        print(bars(groups, status))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
