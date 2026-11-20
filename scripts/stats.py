# SPDX-License-Identifier: LGPL-2.1-or-later
"""Release statistics for Agent Link, made from the data, never typed by hand.

Writes docs/stats/stats.json (every number), docs/stats/STATS.md (made from
stats.json only) and the block of README.md between the stats markers.
Plain Python, read with ast like scripts/tool_summary.py: no FreeCAD, no
network.

    python3 scripts/stats.py                  # write stats.json, STATS.md, README block
    python3 scripts/stats.py --check          # exit 1 when one of them is stale
    python3 scripts/stats.py --addons DIR     # read the add-ons' checkouts in DIR first,
                                              # into docs/stats/addons.json (their snapshot)
    python3 scripts/stats.py --timings FILE   # read a usage log (.jsonl, agentlink/usage.py rows)
                                              # or the heavy-job queue (queue.json) first,
                                              # into docs/stats/timings.json

Sources:
  coverage   docs/hardening/status.json and inventory.json (scripts/hardening_status.py)
  hub tools  agentlink/tools.py, agentlink/families, agentlink/data/tools.json (scripts/tool_summary.py)
  tokens     the same sources, agentlink/staticbase.py (BASE) and agentlink/data/ste.json;
             the estimate of scripts/ste_check.py and agentlink/usage.py (3.5 characters a token)
  add-ons    docs/stats/addons.json: a snapshot of each add-on's own tool data
             (data/tools.json files and Tool(...) calls in its family modules), with the
             add-on's commit. The add-ons are other repositories: the tests and --check
             read the snapshot, and --addons refreshes it.
  timings    docs/stats/timings.json, written by --timings only. Prose numbers in the
             findings files are not read.
"""
import ast
import glob
import json
import os
import statistics
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

import hardening_status  # noqa: E402
import ste_check  # noqa: E402
import tool_summary  # noqa: E402

PKG = os.path.join(ROOT, "agentlink")
OUT = os.path.join(ROOT, "docs", "stats")
STATS_JSON = os.path.join(OUT, "stats.json")
STATS_MD = os.path.join(OUT, "STATS.md")
ADDONS_JSON = os.path.join(OUT, "addons.json")
TIMINGS_JSON = os.path.join(OUT, "timings.json")
README = os.path.join(ROOT, "README.md")
BEGIN, END = "<!-- stats:begin (scripts/stats.py) -->", "<!-- stats:end -->"
CPT = ste_check.CHARS_PER_TOKEN
CARD_EXTRA = 40  # ste_check.card_tokens: the JSON keys and quotes of a card whose schema is not read as data

# (repository, folder name of its checkout)
ADDONS = (("AgentLink-OrcaSlicer", "agentlink-orcaslicer"), ("ScanRuler-FreeCAD", "scanruler-freecad"),
          ("Texturizer-FreeCAD", "texturizer-freecad"), ("Workshop-FreeCAD", "workshop-freecad"), ("Tutor-FreeCAD", "tutor-freecad"))
SKIP_DIRS = ("tests", "scripts", "tools", "docs", "packaging", "mcpb", ".git", "__pycache__", "node_modules")
COVER_ROWS = hardening_status.ROWS


def est(chars):
    return int(round(chars / CPT))


def _json_chars(x):
    return len(json.dumps(x, separators=(",", ":"), ensure_ascii=False))


def card(name, desc, schema=None, schema_chars=None):
    """(characters of one tools/list entry, exact?). The schema as data when
    it was read; else its source text's length plus CARD_EXTRA (ste_check)."""
    if schema is not None:
        return _json_chars({"name": name, "description": desc, "inputSchema": schema}), True
    return len(name) + len(desc) + int(schema_chars or 0) + CARD_EXTRA, False


def list_chars(cards):
    """A tools/list array: the cards, commas between, brackets."""
    return sum(cards) + max(len(cards) - 1, 0) + 2


# ---- 1. coverage ---------------------------------------------------------------------------------

def _short(st):
    out = []
    if not hardening_status.proven(st):
        return ["not proven"]
    if not st.get("headless"):
        out.append("not headless")
    if not st.get("live"):
        out.append("not live")
    return out


def coverage():
    groups, status = hardening_status.load()
    inv = hardening_status.load_inventory()
    total, c, _tools = hardening_status.counts(groups, status)
    secs = hardening_status.sections(groups, status)
    nc = hardening_status.not_counted(groups, status)

    def gaps_of(title, mine):
        out = []
        for g, d in mine:
            part = d["workbench"] if d["repo"] == "AgentLink-FreeCAD" else d.get("listedIn", g)
            for t in d["tools"]:
                st = status.get(t, {})
                short = _short(st)
                if short:
                    out.append({"tool": t, "section": title, "part": part, "short": short, "why": st.get("gap") or "Not tested yet.",
                                "format2Only": bool(st.get("liveFormat2"))})
        return out

    counted = hardening_status.counted(groups)
    gaps = []
    for sec in secs:
        gaps += gaps_of(sec["title"], [(g, d) for g, d in counted.items() if d["repo"] == sec["repo"]])
    nv = inv.get("notInV1", {})
    return {"total": total, **{k: c[k] for k, _l in COVER_ROWS},
            "sections": [{"repo": x["repo"], "title": x["title"], **x["counts"], "parts": x["parts"]} for x in secs],
            "gaps": gaps,
            "notCounted": [{"key": x["key"], "title": x["title"], "why": x["why"], **x["counts"], "parts": x["parts"],
                            "repos": sorted({d["repo"] for d in groups.values() if d.get("notCounted") == x["key"]}),
                            "gaps": gaps_of(x["title"], [(g, d) for g, d in groups.items() if d.get("notCounted") == x["key"]])} for x in nc],
            "notInV1": {"tools": [{"tool": t, **e} for t, e in nv.get("tools", {}).items()], "features": nv.get("features", [])},
            "unlisted": [{"tool": t, "why": w} for t, w in inv.get("unlisted", {}).items()]}


def _row(label, n, total):
    return f"{label:<{hardening_status.W}}{hardening_status.bar(n, total)} {n:>3}/{total}"


def total_lines(cov):
    """The V1 totals and the sections: the first lines of hardening_status.py bars."""
    lines = ["Per-tool status, all of V1 (measured: counted from docs/hardening/status.json)"]
    lines += [_row(label, cov[key], cov["total"]) for key, label in COVER_ROWS]
    lines += ["", "By section (tools proven / total)"]
    lines += [_row(x["title"], x["proven"], x["total"]) for x in cov["sections"]]
    for n in cov.get("notCounted", []):
        lines += ["", f"{n['title']}: not in the totals above"]
        lines += [_row(label, n[key], n["total"]) for key, label in COVER_ROWS[:3]]
    return lines


def section_lines(sec):
    hub = "AgentLink-FreeCAD" in ([sec["repo"]] if "repo" in sec else sec.get("repos", []))
    lines = [_row(label, sec[key], sec["total"]) for key, label in COVER_ROWS]
    lines += ["", f"{sec['title']} by {'workbench' if hub else 'group'} (tools proven / total)"]
    lines += [_row(p["name"], p["proven"], p["total"]) for p in sec["parts"]]
    return lines


def coverage_lines(cov):
    """The same lines as hardening_status.py bars, from stats.json's numbers."""
    hub = cov["sections"][0]
    return total_lines(cov) + ["", f"{hub['title']} by workbench (tools proven / total)"] + [_row(p["name"], p["proven"], p["total"]) for p in hub["parts"]]


# ---- reading tools ---------------------------------------------------------------------------------

def _module_consts(tree):
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, SyntaxError, TypeError):
                pass
    return out


def _static_text(node, names):
    """A description as far as it can be read without running it: an
    unknown part is " … " (approximated)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, ok1 = _static_text(node.left, names)
        b, ok2 = _static_text(node.right, names)
        return a + b, ok1 and ok2
    if isinstance(node, ast.Name) and isinstance(names.get(node.id), str):
        return names[node.id], True
    if isinstance(node, ast.JoinedStr):
        try:
            return ste_check._text(node, names), True
        except Exception:  # noqa: BLE001
            return "".join(v.value if isinstance(v, ast.Constant) else " … " for v in node.values), False
    return " … ", False


def _tool_calls(tree):
    for n in ast.walk(tree):
        fn = getattr(n, "func", None)
        if isinstance(n, ast.Call) and (getattr(fn, "id", None) == "Tool" or getattr(fn, "attr", None) == "Tool") and len(n.args) >= 3 \
                and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
            yield n


def _schema(node):
    try:
        s = ast.literal_eval(node)
        return s if isinstance(s, dict) else None
    except (ValueError, SyntaxError, TypeError):
        return None


def hub_cards():
    """{name: {"desc", "schema" (or None), "schemaChars"}} for every hub tool, read as ste_check.collect reads them."""
    out = {}
    with open(os.path.join(PKG, "data", "tools.json"), encoding="utf-8") as f:
        for name, e in json.load(f)["entries"].items():
            out[name] = {"desc": e["description"], "schema": e["inputSchema"], "schemaChars": None}
    ste_check.PKG = PKG
    env = ste_check._env()
    for path in ste_check.coded_files() + [os.path.join(PKG, "ext.py")]:  # ext.py: app_extensions, added by tools.py
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for n in _tool_calls(tree):
            out[n.args[0].value] = {"desc": ste_check._text(n.args[1], env), "schema": _schema(n.args[2]), "schemaChars": len(ast.unparse(n.args[2]))}
    return out


# ---- 2. tools --------------------------------------------------------------------------------------

def hub_tools():
    gs = tool_summary.groups()
    return {"total": sum(len(v["tools"]) for v in gs.values()), "groups": [{"group": g, "tools": len(v["tools"]), "lean": v["lean"]} for g, v in gs.items()]}


def _git_commit(folder):
    try:
        r = subprocess.run(["git", "-C", folder, "rev-parse", "--short=7", "HEAD"], capture_output=True, text=True, timeout=20)
        return r.stdout.strip() or None
    except Exception:  # noqa: BLE001
        return None


def _py_files(folder):
    for d, dirs, files in os.walk(folder):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS and not x.startswith("."))
        for f in sorted(files):
            if f.endswith(".py"):
                yield os.path.join(d, f)


def read_addon(folder):
    """One add-on's tools from its own tool data: every data/tools.json, and
    the Tool(...) calls of its family modules (a module with GROUP). Tool(...)
    calls in a module without GROUP belong to the add-on's own server
    (OrcaLink's server.py), not to Agent Link's list."""
    tools, own_server, lean = {}, [], set()
    for p in sorted(glob.glob(os.path.join(folder, "**", "data", "tools.json"), recursive=True)):
        rel = os.path.relpath(p, folder).split(os.sep)
        if any(x in SKIP_DIRS for x in rel[:-1]):
            continue
        with open(p, encoding="utf-8") as f:
            for name, e in json.load(f).get("entries", {}).items():
                chars, exact = card(name, e["description"], e["inputSchema"])
                tools[name] = {"group": e["group"], "chars": chars, "exact": exact}
    for p in _py_files(folder):
        with open(p, encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read())
            except SyntaxError:
                continue
        consts = _module_consts(tree)
        calls = list(_tool_calls(tree))
        group = consts.get("GROUP") if isinstance(consts.get("GROUP"), str) else None
        if group and consts.get("LEAN") is True:
            lean.add(group)
        if not calls:
            continue
        if not group:
            own_server += [n.args[0].value for n in calls]
            continue
        for n in calls:
            desc, ok = _static_text(n.args[1], consts)
            schema = _schema(n.args[2])
            chars, exact = card(n.args[0].value, desc, schema, len(ast.unparse(n.args[2])))
            tools[n.args[0].value] = {"group": group, "chars": chars, "exact": exact and ok}
    return {"tools": dict(sorted(tools.items())), "leanGroups": sorted(lean), "ownServerOnly": sorted(set(own_server) - set(tools))}


def snapshot_addons(where):
    snap = {"about": "Each add-on's tools as its own tool data declares them (scripts/stats.py --addons). chars: the tools/list entry's characters; "
                     "exact false: the entry is estimated (a schema or description written in code that cannot be read as data).",
            "addons": {}}
    for repo, dirname in ADDONS:
        folder = next((os.path.join(where, d) for d in os.listdir(where) if d.lower() == dirname), None)
        if folder is None or not os.path.isdir(folder):
            continue
        snap["addons"][repo] = {"commit": _git_commit(folder), **read_addon(folder)}
    with open(ADDONS_JSON, "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    return snap


def load_json(path, default=None):
    if not os.path.isfile(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---- 3. tokens -------------------------------------------------------------------------------------

def tokens(hub, hub_groups, addons):
    cards = hub_cards()
    core_tree = tool_summary._parse(os.path.join(PKG, "tools.py"))
    hub_group_info = set(tool_summary._consts(core_tree, {"GROUP_INFO"}).get("GROUP_INFO", {}))
    base = tool_summary._consts(tool_summary._parse(os.path.join(PKG, "staticbase.py")), {"BASE"})["BASE"]
    with open(os.path.join(PKG, "data", "ste.json"), encoding="utf-8") as f:
        ste = json.load(f)["entries"]
    gs = tool_summary.groups()
    listed_hub = {g: v["tools"] for g, v in gs.items()}
    lean = [g for g, v in gs.items() if v["lean"]]
    classic = [n for g in lean for n in listed_hub[g]]
    static = [n for n in base if n in cards]

    def entry(n, style):
        c = cards[n]
        desc = ste.get(n, c["desc"]) if style == "ste" else c["desc"]
        return card(n, desc, c["schema"], c["schemaChars"])

    combos = []
    for mode, names in (("static", static), ("classic", classic)):
        for style in ("ste", "full"):
            es = [entry(n, style) for n in names]
            ch = list_chars([c for c, _x in es])
            combos.append({"mode": mode, "style": style, "default": mode == "static" and style == "ste", "tools": len(names), "chars": ch,
                           "tokens": est(ch), "estimatedCards": sum(1 for _c, x in es if not x)})
    every = [entry(n, "full") for g in listed_hub for n in listed_hub[g]]
    all_hub = {"tools": len(every), "chars": list_chars([c for c, _x in every]), "estimatedCards": sum(1 for _c, x in every if not x)}
    all_hub["tokens"] = est(all_hub["chars"])
    approx_hub = sorted(n for n in cards if cards[n]["schema"] is None)

    # The add-ons: what each adds to the list when installed.
    hub_names = set(cards) | {n for v in listed_hub.values() for n in v}
    seen, per = set(), []
    for repo, a in (addons or {}).items():
        loaded = {n: t for n, t in a["tools"].items() if n not in hub_names and n not in seen}
        seen |= set(loaded)
        lean_here = set(lean) | {g for g in a.get("leanGroups", []) if g not in hub_group_info}
        cl = [t["chars"] for t in loaded.values() if t["group"] in lean_here]
        on = [t["chars"] for t in loaded.values()]
        per.append({"addon": repo, "commit": a.get("commit"), "declared": len(a["tools"]), "loaded": len(loaded),
                    "hubNamesLeftOut": sorted(n for n in a["tools"] if n in hub_names),
                    "groups": len({t["group"] for t in loaded.values()}), "ownServerOnly": a.get("ownServerOnly", []),
                    "estimatedCards": sum(1 for t in loaded.values() if not t["exact"]),
                    "notInstalledTokens": 0, "staticTokens": 0, "classicTools": len(cl), "classicTokens": est(sum(cl) + len(cl)) if cl else 0,
                    "allGroupsOnTokens": est(sum(on) + len(on)) if on else 0})
    addon_total = sum(p["loaded"] for p in per)
    return {"combos": combos, "allHubListed": all_hub, "base": list(static), "leanGroups": lean, "steEntries": sorted(ste),
            "estimatedHubCards": approx_hub, "addons": per, "addonToolsLoaded": addon_total, "totalAllInstalled": hub["total"] + addon_total}


# ---- 4. timings ------------------------------------------------------------------------------------

def import_timings(path, family_of):
    """docs/stats/timings.json from a usage log (agentlink/usage.py: rows with
    kind "call", tool, grp, ms) or the heavy-job queue (keep.py: timings
    {tool: [[size, seconds], …]}). Only tool names and times are kept."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    ms, source = {}, None
    try:
        doc = json.loads(text)
    except ValueError:
        doc = None
    if isinstance(doc, dict) and isinstance(doc.get("timings"), dict):
        source = "heavy-job queue (queue.json timings)"
        for tool, pts in doc["timings"].items():
            for p in pts or ():
                if isinstance(p, (list, tuple)) and len(p) == 2 and isinstance(p[1], (int, float)) and p[1] >= 0:
                    ms.setdefault((tool, family_of(tool, None)), []).append(float(p[1]) * 1000.0)
    else:
        source = "usage log (agentlink/usage.py call rows)"
        for line in text.splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if not isinstance(r, dict) or r.get("kind", "call") != "call" or not isinstance(r.get("tool"), str) or not isinstance(r.get("ms"), (int, float)):
                continue
            if r.get("tool") == "batch":
                continue  # a batch's own row holds its calls' time again
            ms.setdefault((r["tool"], family_of(r["tool"], r.get("grp"))), []).append(float(r["ms"]))
    fam = {}
    for (_tool, g), v in ms.items():
        fam.setdefault(g, []).extend(v)
    out = {"source": source, "calls": sum(len(v) for v in ms.values()),
           "families": [{"family": g, "count": len(v), "medianMs": int(round(statistics.median(v))), "maxMs": int(round(max(v)))} for g, v in sorted(fam.items())]}
    with open(TIMINGS_JSON, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write("\n")
    return out


def family_map(addons):
    m = {}
    for g, v in tool_summary.groups().items():
        for n in v["tools"]:
            m[n] = g
    for a in (addons or {}).values():
        for n, t in a["tools"].items():
            m.setdefault(n, t["group"])
    return lambda tool, grp: grp or m.get(tool, "other")


# ---- the whole -------------------------------------------------------------------------------------

def build():
    snap = load_json(ADDONS_JSON, {}) or {}
    addons = snap.get("addons", {})
    hub = hub_tools()
    tim = load_json(TIMINGS_JSON)
    return {
        "about": "Made by scripts/stats.py from the repository's data. Do not edit by hand.",
        "coverage": coverage(),
        "hubTools": hub,
        "tokens": tokens(hub, hub["groups"], addons),
        "timings": tim if tim else {"note": "no timing data in the repo yet"},
    }


def _fmt(n):
    return f"{n:,}"


SECTION_NOTE = {
    "AgentLink-FreeCAD": "What you get with the hub alone: the FreeCAD workbenches that Agent Link covers with no add-on installed.",
    "Workshop-FreeCAD": "Make, Parts, Documents, Electronics and the safety tools. Its groups `core` and `strength` add tools to the hub's groups of the same name.",
    "ScanRuler-FreeCAD": "Scans, meshes, reverse engineering and the panels. The features come from ScanRuler by Stefan Hermann (CNC Kitchen), under AGPL.",
    "Texturizer-FreeCAD": "Surface textures on a model.",
    "Tutor-FreeCAD": "Lessons that point at the window.",
    "AgentLink-OrcaSlicer": "OrcaSlicer through Agent Link. Its own MCP server also has tools that Agent Link does not list (section 2).",
}
TOKEN_WHAT = ("Each token number is the estimated size of the `tools/list` answer: the tool names, descriptions and input schemas that the client "
              "loads into the agent's context at the start of a session. The server instructions, the guides and the tool answers are not in it.")


def _sec_table(cov):
    L = ["| Section | Tools | Proven | Headless | Live | Docs checked | Health check seen | Description rewritten |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for x in cov["sections"]:
        L.append(f"| {x['title']} | {x['total']} | {x['proven']} | {x['headless']} | {x['live']} | {x['docs']} | {x['health']} | {x['description']} |")
    L.append(f"| **All of V1** | **{cov['total']}** | **{cov['proven']}** | **{cov['headless']}** | **{cov['live']}** | **{cov['docs']}** | **{cov['health']}** | **{cov['description']}** |")
    for n in cov.get("notCounted", []):
        L.append(f"| *{n['title']}* | *{n['total']}* | *{n['proven']}* | *{n['headless']}* | *{n['live']}* | *{n['docs']}* | *{n['health']}* | *{n['description']}* |")
    return L


def _nc_note(cov, repo):
    """The sentence for a section whose repo also has tools that are not counted."""
    ns = [n for n in cov.get("notCounted", []) if repo in n["repos"]]
    return "".join(f" The {n['title'].replace(' (not counted)', '').lower()} ({', '.join(p['name'] for p in n['parts'])}, {n['total']} tools) are not in this count." for n in ns)


def gap_lines(cov):
    L = ["Each line is one tool: the section, the workbench or group, what is short, and why. "
         "The reason comes from the tool's `gap` in `docs/hardening/status.json`, which cites the findings file in `docs/hardening/` that records it. "
         "A tool with no recorded reason says \"Not tested yet.\"", ""]
    for sec in cov["sections"]:
        mine = [g for g in cov["gaps"] if g["section"] == sec["title"]]
        L += [f"### {sec['title']}", ""]
        if not mine:
            L += ["Every tool is proven headless and live.", ""]
            continue
        part_short = [p for p in sec["parts"] if p["proven"] < p["total"]]
        if part_short:
            L += ["Rows under 100%: " + ", ".join(f"{p['name']} {p['proven']}/{p['total']}" for p in part_short) + ".", ""]
        L += [f"- `{g['tool']}` ({g['part']}): {', '.join(g['short'])}. {g['why']}" for g in mine]
        L.append("")
    n = cov["total"]
    L += ["### Review steps not done yet", "",
          f"These rows are under 100% too: docs checked {cov['docs']}/{n}, health check seen {cov['health']}/{n}, description rewritten {cov['description']}/{n}. "
          "They are review steps of the hardening pass, not proofs. The per-tool list is in `docs/hardening/STATUS.md`.", "",
          "### Not in V1 (not counted)", "",
          "These are not in the numbers above.", ""]
    by = {}
    for t in cov["notInV1"]["tools"]:
        by.setdefault((t["repo"], t["why"]), []).append(t["tool"])
    L += [f"- {', '.join('`' + n + '`' for n in names)} ({repo}, {len(names)} {'tool' if len(names) == 1 else 'tools'}): {why}" for (repo, why), names in by.items()]
    L += [f"- {f['name']}: {f['why']}" for f in cov["notInV1"]["features"]]
    L += [f"- `{u['tool']}` is counted in Workshop's declared tools (section 2) but not here. {u['why']}" for u in cov["unlisted"]]
    f2 = [g["tool"] for g in cov["gaps"] if g["format2Only"]]
    if f2:
        L.append(f"- The live proof of {', '.join('`' + t + '`' for t in f2)} was on a cookbook format 2 draft. Format 2 is V2, so that proof does not count.")
    for n in cov.get("notCounted", []):
        L += ["", f"### {n['title']}", "",
              f"{n['why']} They are in V1, but not in the numbers above. Their own numbers: {n['proven']}/{n['total']} proven, "
              f"{n['headless']}/{n['total']} headless, {n['live']}/{n['total']} live.", ""]
        L += [f"- `{g['tool']}` ({g['part']}): {', '.join(g['short'])}. {g['why']}" for g in n["gaps"]]
        f2 = [g["tool"] for g in n["gaps"] if g["format2Only"]]
        if f2:
            L.append(f"- The live proof of {', '.join('`' + t + '`' for t in f2)} was on a cookbook format 2 draft. Format 2 is V2, so that proof does not count. "
                     "These tools are V1 (cookbook format 1).")
    return L


def render_md(s):
    cov, hub, tok, tim = s["coverage"], s["hubTools"], s["tokens"], s["timings"]
    L = ["<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->", "# Agent Link release statistics", "",
         "The script `scripts/stats.py` makes this file from `stats.json`. Do not edit this file by hand.",
         "Each number comes from the data in this repository. To make the file again, run `python3 scripts/stats.py`.", "",
         "## 1. FreeCAD coverage, headless through MCP", "",
         "The source is `docs/hardening/status.json` and `inventory.json`. Only V1 counts: the hub and the add-ons of the V1 bundle (`packaging/addons.json`). "
         "A tool that is not in V1 is not in these numbers (see [What is not covered, and why](#what-is-not-covered-and-why)). "
         "Proven: the tool worked on a test model, headless through the MCP tools or live in the FreeCAD window.", "",
         *_sec_table(cov), ""]
    for sec in cov["sections"]:
        L += [f"### {sec['title']}", "", f"{SECTION_NOTE.get(sec['repo'], '')} {sec['total']} tools.{_nc_note(cov, sec['repo'])}", "", "```", *section_lines(sec), "```", ""]
    for n in cov.get("notCounted", []):
        L += [f"### {n['title']}", "", f"{n['why']} {n['total']} tools. They are not in the totals of V1.", "", "```", *section_lines(n), "```", ""]
    L += ["### All of V1 together", "",
          "The same lines as the start of `python3 scripts/hardening_status.py bars`.", "",
          "```", *total_lines(cov), "```", "",
          "## 2. Tools", "",
          f"Agent Link (core) declares {hub['total']} tools in {len(hub['groups'])} groups. The source is `scripts/tool_summary.py`. "
          "A lean group is in the classic list from the start.", "",
          "| Group | Tools | Lean |", "|---|---:|---|"]
    L += [f"| `{g['group']}` | {g['tools']} | {'yes' if g['lean'] else '–'} |" for g in hub["groups"]]
    L += ["", "### Add-ons", "",
          "The source is `docs/stats/addons.json`: each add-on's own tool data (its `data/tools.json` files and the `Tool(...)` calls of its family modules), at the commit shown. "
          "Declared: the tools that the add-on declares. Loaded: the tools that Agent Link adds. Agent Link does not load an add-on tool that has the name of a hub tool or of a tool of an add-on before it.", "",
          "| Add-on | Commit | Declared | Loaded | Groups | Only in its own server |", "|---|---|---:|---:|---:|---|"]
    for a in tok["addons"]:
        own = ", ".join(f"`{n}`" for n in a["ownServerOnly"]) or "–"
        L.append(f"| {a['addon']} | `{a['commit'] or '?'}` | {a['declared']} | {a['loaded']} | {a['groups']} | {own} |")
    L += ["", f"With all these add-ons installed, Agent Link has {tok['totalAllInstalled']} tools: {hub['total']} of the hub and {tok['addonToolsLoaded']} of the add-ons."]
    L += [f"`{u['tool']}` is in this count. {u['why']}" for u in cov["unlisted"]]
    L += ["", "## 3. Token cost of the tool list", "",
          TOKEN_WHAT + " The estimate is the estimate of the repository: 3.5 characters for each token "
          "(`scripts/ste_check.py`, `agentlink/usage.py`). It is not the count of the provider.", "",
          "| Mode | Style | Tools listed | Characters | Tokens (est.) of the `tools/list` answer |", "|---|---|---:|---:|---:|"]
    for c in tok["combos"]:
        mark = " (default)" if c["default"] else ""
        L.append(f"| {c['mode']}{mark} | {c['style']} | {c['tools']} | {_fmt(c['chars'])} | {_fmt(c['tokens'])} |")
    ah = tok["allHubListed"]
    d = tok["combos"][0]
    L += ["", f"So with the default (static, ste), the tool list costs about {_fmt(d['tokens'])} tokens for {d['tools']} tools. "
          f"With every hub group turned on, the list has {ah['tools']} tools, {_fmt(ah['chars'])} characters and about {_fmt(ah['tokens'])} tokens (style full).", "",
          f"- static: only the base is listed ({', '.join('`' + n + '`' for n in tok['base'])}). The agent finds the other tools with `tool_find`.",
          f"- classic: the lean groups are listed ({', '.join('`' + g + '`' for g in tok['leanGroups'])}).",
          f"- ste: the descriptions in `agentlink/data/ste.json` replace the full text for {', '.join('`' + n + '`' for n in tok['steEntries'])}. The other tools keep their full text.", "",
          "### Extra tokens for each add-on", "",
          "The extra tokens that an add-on adds to the `tools/list` answer. "
          "An add-on that is not installed adds 0 tokens. This is a rule of the project: Agent Link lists no tool of an add-on that is not installed. "
          "In static mode an installed add-on also adds 0 tokens, until the agent turns on one of its groups with `tool_groups`. "
          "The style has no effect on add-on tools: `ste.json` holds hub tools only.", "",
          "| Add-on | Not installed | Static | Classic (lean groups) | All its groups on |", "|---|---:|---:|---:|---:|"]
    for a in tok["addons"]:
        L.append(f"| {a['addon']} | {a['notInstalledTokens']} | {a['staticTokens']} | {_fmt(a['classicTokens'])} ({a['classicTools']} tools) | {_fmt(a['allGroupsOnTokens'])} |")
    est_addon = sum(a["estimatedCards"] for a in tok["addons"])
    L += ["", "### What is approximated", "",
          "- Each token number is an estimate: characters divided by 3.5.",
          f"- {len(tok['estimatedHubCards'])} hub tools have an input schema in code that the script cannot read as data. For these tools, the script uses the length of the schema source text plus {CARD_EXTRA} characters, as `ste_check.card_tokens` does. "
          f"The static base has {tok['combos'][0]['estimatedCards']} such tools. The classic list has {tok['combos'][2]['estimatedCards']} such tools.",
          f"- {est_addon} add-on tools have such an estimated entry (a schema or a description in code).",
          "- The script counts a FreeCAD build with every workbench. A build without a workbench (FEM, CAM …) serves fewer tools.",
          "- The add-on numbers come from the snapshot. Run `python3 scripts/stats.py --addons <folder with the add-on checkouts>` to make it again.",
          "", "## 4. Timings", ""]
    if "families" in tim:
        L += [f"The source is `docs/stats/timings.json` ({tim['source']}). It holds {tim['calls']} timed calls.", "",
              "| Tool family | Calls | Median (ms) | Longest (ms) |", "|---|---:|---:|---:|"]
        L += [f"| `{f['family']}` | {f['count']} | {_fmt(f['medianMs'])} | {_fmt(f['maxMs'])} |" for f in tim["families"]]
    else:
        L += [f"{tim['note'][0].upper()}{tim['note'][1:]}. The findings files give times in prose only, and the script does not read prose.", "",
              "To add timings, run `python3 scripts/stats.py --timings <file>`. The file is one day of the Agent Link usage log (`~/AgentLink/usage/<day>.jsonl`) "
              "or the heavy-job queue (`queue.json`). The script keeps the tool names and the times only. It writes `docs/stats/timings.json`, and this section shows the median for each tool family."]
    L += ["", "## What is not covered, and why", "", *gap_lines(cov)]
    while L and L[-1] == "":
        L.pop()
    return "\n".join(L) + "\n"


def readme_block(s):
    cov, hub, tok = s["coverage"], s["hubTools"], s["tokens"]
    md = "https://github.com/jamesK1000011/AgentLink-FreeCAD/blob/main/docs/stats/STATS.md"
    L = [f"Release statistics for V1, made by `scripts/stats.py` from the data (all of them: [docs/stats/STATS.md]({md})).", "",
         "```", *total_lines(cov), "```", "",
         "| Section | Tools | Proven | Headless | Live |", "|---|---:|---:|---:|---:|"]
    L += [f"| {x['title']} | {x['total']} | {x['proven']} | {x['headless']} | {x['live']} |" for x in cov["sections"]]
    L += [f"| **All of V1** | **{cov['total']}** | **{cov['proven']}** | **{cov['headless']}** | **{cov['live']}** |"]
    L += [f"| *{n['title']}* | *{n['total']}* | *{n['proven']}* | *{n['headless']}* | *{n['live']}* |" for n in cov.get("notCounted", [])]
    L += [""]
    gaps = cov["gaps"]
    np_ = [g for g in gaps if g["short"] == ["not proven"]]
    nh = [g for g in gaps if "not headless" in g["short"]]
    nl = [g for g in gaps if "not live" in g["short"]]
    nv = len(cov["notInV1"]["tools"])
    L += [f"Known gaps: {len(np_)} tools are not proven, {len(nh)} more are proven live only and {len(nl)} more headless only. "
          "The main reasons: a program, a FreeCAD version or a printer that the test Mac does not have; a step that needs the person (a restart, an install, a go); "
          + ("proof only on cookbook format 2, which is V2; " if any(g["format2Only"] for g in gaps) else "") + "or not tested yet. "
          f"Each tool and its reason: [What is not covered, and why]({md}#what-is-not-covered-and-why). "
          f"Not in V1 and not counted: {nv} tools of private add-ons (Home-FreeCAD, agentlink-collab), cookbook format 2 and PrintLoop."
          + "".join(f" In V1 but not counted: {n['title'].replace(' (not counted)', '').lower()} ({n['total']} tools: {', '.join(p['name'] for p in n['parts'])}), not FreeCAD functions."
                    for n in cov.get("notCounted", [])), "",
          f"Tools: {hub['total']} in Agent Link (core), {tok['totalAllInstalled']} with all add-ons installed"
          + (f" ({', '.join('`' + u['tool'] + '`' for u in cov['unlisted'])} in this count is callable but not listed)." if cov["unlisted"] else "."), "",
          TOKEN_WHAT + " Estimate: 3.5 characters for each token.", "",
          "| Tool list | Tools listed | Tokens (est.) of the `tools/list` answer |", "|---|---:|---:|"]
    for c in tok["combos"]:
        L.append(f"| {c['mode']}{' (default)' if c['default'] else ''}, {c['style']} | {c['tools']} | {_fmt(c['tokens'])} |")
    return "\n".join(L)


def render_readme(cur, s):
    if BEGIN not in cur:
        raise SystemExit("README.md has no stats markers")
    a, b = cur.index(BEGIN) + len(BEGIN), cur.index(END)
    return cur[:a] + "\n" + readme_block(s) + "\n" + cur[b:]


def outputs():
    s = build()
    sj = json.dumps(s, indent=1, ensure_ascii=False) + "\n"
    with open(README, encoding="utf-8") as f:
        cur = f.read()
    return {STATS_JSON: sj, STATS_MD: render_md(json.loads(sj)), README: render_readme(cur, json.loads(sj))}, s


def headline(s):
    t = s["tokens"]
    out = total_lines(s["coverage"])
    out.append(f"tools: hub {s['hubTools']['total']}, add-ons {t['addonToolsLoaded']}, all installed {t['totalAllInstalled']}")
    out += [f"tool list {c['mode']}/{c['style']}: {c['tools']} tools, ~{c['tokens']} tokens" for c in t["combos"]]
    out.append("timings: " + (f"{s['timings']['calls']} calls" if "calls" in s["timings"] else s["timings"]["note"]))
    return "\n".join(out)


def main(argv):
    if "--addons" in argv:
        i = argv.index("--addons")
        if i + 1 >= len(argv):
            sys.exit("--addons needs the folder that holds the add-on checkouts")
        snap = snapshot_addons(argv[i + 1])
        print("add-ons read:", ", ".join(f"{k} {len(v['tools'])}" for k, v in snap["addons"].items()))
    if "--timings" in argv:
        i = argv.index("--timings")
        if i + 1 >= len(argv):
            sys.exit("--timings needs a usage log (.jsonl) or queue.json")
        t = import_timings(argv[i + 1], family_map((load_json(ADDONS_JSON, {}) or {}).get("addons")))
        print(f"timings: {t['calls']} calls in {len(t['families'])} families")
    files, s = outputs()
    if "--check" in argv:
        stale = []
        for p, text in files.items():
            cur = None
            if os.path.isfile(p):
                with open(p, encoding="utf-8") as f:
                    cur = f.read()
            if cur != text:
                stale.append(os.path.relpath(p, ROOT))
        if stale:
            sys.stderr.write(f"stale: {', '.join(stale)}: run python3 scripts/stats.py\n")
            return 1
        return 0
    os.makedirs(OUT, exist_ok=True)
    for p, text in files.items():
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
    print(headline(s))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
