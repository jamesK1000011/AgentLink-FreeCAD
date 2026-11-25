# SPDX-License-Identifier: LGPL-2.1-or-later
"""How much the likely-next hints are used, read from OpenCode session
exports (opencode export <session> > session.json). Plain Python, no FreeCAD.

For each run (one file) it counts:
  offered    answers that offered next steps: numbered options ("step N:
             1 tool …; 2 tool …", or session_state's { options { list } }),
             or a "likely next: tool (why), …" line;
  used       of those, how many times the very next tool call was one of the
             offered tools, or pick (a batch counts by its first call);
  firstTry   of those used, how many succeeded the first time (no refusal).

    python3 scripts/next_hint_use.py session.json [more.json …] [--json]

The export is read defensively: messages[] (or { messages }), each with
parts[] (at the top or under the message), and a part of type "tool" with
tool, state.status, state.input and state.output. A tool name may carry the
MCP server's prefix (agentlink-freecad_pd_pad): it is matched by its end.
"""
import json
import re
import sys

STEP = re.compile(r"^step \d+: ")
OPTION = re.compile(r"(?:^|; )\d+ ([A-Za-z_][A-Za-z0-9_]*)")
LIKELY = "likely next: "
PAREN = re.compile(r"\([^()]*\)")
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _load(text):
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


def tool_parts(session):
    """The tool parts of an export, in order: [{ tool, input, output, status }]."""
    msgs = session.get("messages") if isinstance(session, dict) else session
    out = []
    for m in msgs if isinstance(msgs, list) else []:
        if not isinstance(m, dict):
            continue
        parts = m.get("parts")
        if parts is None and isinstance(m.get("info"), dict):
            parts = m["info"].get("parts")
        for p in parts if isinstance(parts, list) else []:
            if not isinstance(p, dict) or p.get("type") != "tool":
                continue
            st = p.get("state") if isinstance(p.get("state"), dict) else {}
            inp = st.get("input")
            if isinstance(inp, str):
                inp = _load(inp) or {}
            out.append({"tool": str(p.get("tool") or ""), "input": inp if isinstance(inp, dict) else {},
                        "output": st.get("output"), "status": st.get("status")})
    return out


def _answer(output):
    """The tool's answer as a dict, when it is one (the MCP text content)."""
    if isinstance(output, dict):
        return output
    if isinstance(output, list):  # content blocks
        output = " ".join(str(b.get("text", "")) for b in output if isinstance(b, dict))
    got = _load(output) if isinstance(output, str) else None
    return got if isinstance(got, dict) else None


def likely_tools(line):
    """The tools of a "likely next: a (why), b (why); workbench …" line."""
    if not isinstance(line, str) or LIKELY not in line:
        return []
    rest = line.split(LIKELY, 1)[1]
    while PAREN.search(rest):
        rest = PAREN.sub("", rest)
    rest = rest.split(";", 1)[0]
    return [w.strip() for w in rest.split(",") if NAME.match(w.strip())]


def option_tools(value):
    """The tools of options: the "step N: 1 tool …; 2 tool …" line, or
    session_state's { step, list: [{ n, tool }] }."""
    if isinstance(value, str) and STEP.match(value):
        return OPTION.findall(STEP.sub("", value, count=1))
    if isinstance(value, dict):
        return [str(r["tool"]) for r in value.get("list") or [] if isinstance(r, dict) and r.get("tool")]
    return []


def offered(answer):
    """Every tool an answer offered as a next step (options and the next
    line, anywhere in it: a batch's calls too)."""
    found = []

    def walk(v):
        if isinstance(v, dict):
            for k, x in v.items():
                if k == "options":
                    found.extend(option_tools(x))
                elif k == "next":
                    found.extend(likely_tools(x))
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(answer)
    return set(found)


def _is(name, tool):
    return name == tool or name.endswith("_" + tool)


def call_tool(part):
    """The tool a call ran: a batch's first call's, else its own."""
    name = part["tool"]
    if _is(name, "batch"):
        calls = part["input"].get("calls")
        if isinstance(calls, list) and calls and isinstance(calls[0], dict) and calls[0].get("tool"):
            return str(calls[0]["tool"])
    return name


def succeeded(part):
    """The call answered, and not with a refusal."""
    if part.get("status") not in (None, "completed"):
        return False
    a = _answer(part.get("output"))
    if a is None:
        return isinstance(part.get("output"), str) and not part["output"].lstrip().startswith('{"error"')
    return "error" not in a and not a.get("isError")


def measure(session):
    """{ calls, offered, used, firstTry } for one export."""
    parts = tool_parts(session)
    got = {"calls": len(parts), "offered": 0, "used": 0, "firstTry": 0}
    for i, p in enumerate(parts):
        tools = offered(_answer(p.get("output")) or {})
        if not tools:
            continue
        got["offered"] += 1
        if i + 1 >= len(parts):
            continue
        nxt = parts[i + 1]
        name = call_tool(nxt)
        if _is(name, "pick") or any(_is(name, t) for t in tools):
            got["used"] += 1
            if succeeded(nxt):
                got["firstTry"] += 1
    return got


def main(argv):
    as_json = "--json" in argv
    files = [a for a in argv if a != "--json"]
    if not files:
        print(__doc__.strip())
        return 2
    rows = {}
    for path in files:
        with open(path, encoding="utf-8") as f:
            rows[path] = measure(json.load(f))
    if as_json:
        print(json.dumps(rows, indent=1))
    else:
        for path, r in rows.items():
            print(f"{path}: {r['calls']} calls, {r['offered']} offered next steps, {r['used']} next calls used one, "
                  f"{r['firstTry']} of those first try")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
