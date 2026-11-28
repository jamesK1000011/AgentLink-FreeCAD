# SPDX-License-Identifier: LGPL-2.1-or-later
"""Print the README tool table for Agent Link's data-defined tools
(agentlink/data/tools.json): one row per group, its tools by name, and the
runner each uses. Plain Python, no FreeCAD.

    python3 scripts/tool_tables.py            # markdown table
    python3 scripts/tool_tables.py --detail   # a row per tool, its description
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import tooldata  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agentlink", "data")


def groups(entries):
    out = {}
    for name, e in entries.items():
        out.setdefault(e["group"], []).append((name, e))
    return dict(sorted(out.items()))


def table(entries, detail=False):
    if detail:
        rows = ["| Tool | Group | Runner | What it does |", "|---|---|---|---|"]
        for g, ts in groups(entries).items():
            for name, e in sorted(ts):
                rows.append(f"| `{name}` | {g} | {e.get('runner', 'code')} | {tooldata.card_words(e).replace('|', '/')} |")
        return "\n".join(rows)
    rows = ["| Group | Tools (as data) |", "|---|---|"]
    for g, ts in groups(entries).items():
        rows.append(f"| {g} | " + ", ".join(f"`{n}`" for n, _ in sorted(ts)) + " |")
    return "\n".join(rows)


def main(argv):
    if not os.path.isfile(os.path.join(DATA, "tools.json")):
        print("No agentlink/data/tools.json yet.")
        return 0
    print(table(tooldata.load(DATA), detail="--detail" in argv))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
