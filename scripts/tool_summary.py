# SPDX-License-Identifier: LGPL-2.1-or-later
"""The README's "What the agent can do" table, generated from the source:
each group Agent Link itself brings (agentlink/tools.py, the families in
agentlink/families, the data tools in agentlink/data/tools.json), what it
holds, how many tools and whether the lean list shows it. Read with ast,
so it runs in plain Python without FreeCAD. Add-ons' groups are not
counted: they come when the add-on is installed.

    python3 scripts/tool_summary.py           # rewrite the table in README.md
    python3 scripts/tool_summary.py --check   # exit 1 when README.md is stale
"""
import ast
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PKG = os.path.join(ROOT, "agentlink")
README = os.path.join(ROOT, "README.md")
BEGIN, END = "<!-- tools:begin (scripts/tool_summary.py) -->", "<!-- tools:end -->"


def _consts(tree, names):
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id in names:
            try:
                out[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                pass
    return out


def _tool_names(tree):
    out = []
    for node in ast.walk(tree):
        f = getattr(node, "func", None)
        if isinstance(node, ast.Call) and (getattr(f, "id", None) == "Tool" or getattr(f, "attr", None) == "Tool"):
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                out.append(node.args[0].value)
    return out


def _parse(path):
    with open(path, encoding="utf-8") as f:
        return ast.parse(f.read())


def groups():
    """{group: {"info", "tools": [names], "lean"}} in the order they are listed."""
    core_tree = _parse(os.path.join(PKG, "tools.py"))
    lean = set(_consts(core_tree, {"LEAN"}).get("LEAN", ()))
    info = _consts(core_tree, {"GROUP_INFO"}).get("GROUP_INFO", {})
    group_of = _consts(core_tree, {"GROUP_OF"}).get("GROUP_OF", {})
    aliases = set(_consts(core_tree, {"ALIASES"}).get("ALIASES", {}))
    # A tool of tools.py that GROUP_OF puts in its own group (tool_find: "find") is not core's.
    core_names = _tool_names(core_tree)
    out = {"core": {"info": info.get("core", ""), "tools": [n for n in core_names if group_of.get(n, "core") == "core"]}}
    for n in core_names:
        if group_of.get(n, "core") != "core":
            out.setdefault(group_of[n], {"info": info.get(group_of[n], ""), "tools": []})["tools"].append(n)
    moved = []
    fam_tree = _parse(os.path.join(PKG, "families", "__init__.py"))
    for name in _consts(fam_tree, {"NAMES"})["NAMES"]:
        t = _parse(os.path.join(PKG, "families", name + ".py"))
        c = _consts(t, {"GROUP", "INFO", "LEAN"})
        g = out.setdefault(c["GROUP"], {"info": c.get("INFO", ""), "tools": []})
        for n in _tool_names(t):
            if group_of.get(n, c["GROUP"]) == c["GROUP"]:
                g["tools"].append(n)
            else:
                moved.append((group_of[n], n))
        if c.get("LEAN"):
            lean.add(c["GROUP"])
    with open(os.path.join(PKG, "data", "tools.json"), encoding="utf-8") as f:
        for name, e in json.load(f)["entries"].items():
            grp = group_of.get(name, e["group"])
            if grp in out:
                out[grp]["tools"].append(name)
    # Tools GROUP_OF puts in another group (core's, or their own family's).
    for grp, n in moved:
        out.setdefault(grp, {"info": "", "tools": []})["tools"].append(n)
    for g, v in out.items():
        # An alias is callable but not listed: not counted.
        v["tools"] = sorted(set(v["tools"]) - aliases)
        v["lean"] = g in lean
    return out


def table():
    gs = groups()
    n = sum(len(v["tools"]) for v in gs.values())
    rows = [
        f"Agent Link itself declares {n} tools in {len(gs)} groups; a FreeCAD build without a workbench (FEM, CAM …)",
        "serves fewer, and each installed add-on adds its own groups.",
        "Groups marked *lean* are listed from the start; the agent turns on the rest with `tool_groups`.",
        "",
        "| Group | Tools | What it holds |",
        "|---|---:|---|",
    ]
    for g, v in gs.items():
        info = " ".join(v["info"].split()).replace("|", "/")
        rows.append(f"| `{g}`{' *lean*' if v['lean'] else ''} | {len(v['tools'])} | {info} |")
    return "\n".join(rows)


def render(readme):
    a, b = readme.index(BEGIN) + len(BEGIN), readme.index(END)
    return readme[:a] + "\n" + table() + "\n" + readme[b:]


def main(argv):
    with open(README, encoding="utf-8") as f:
        cur = f.read()
    new = render(cur)
    if "--check" in argv:
        if new != cur:
            sys.stderr.write("README.md's tool table is stale: run python3 scripts/tool_summary.py\n")
            return 1
        return 0
    with open(README, "w", encoding="utf-8") as f:
        f.write(new)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
