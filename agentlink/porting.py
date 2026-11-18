# SPDX-License-Identifier: LGPL-2.1-or-later
"""The port scaffold: a draft Agent Link port of an installed FreeCAD add-on
(docs/design/porting-2026-11-18.md, guide_read { topic: "porting" }).

It reads the add-on's Python files as text (ast). It never imports and never
runs the add-on's code. It finds each Gui.addCommand(name, obj) and the
GetResources of the command's class (MenuText, ToolTip), and the add-on's
workbench class. It writes a draft port in ~/AgentLink/ports/<name>/ only,
never in the add-on and never in Agent Link:

    README.md                  what is there, the next steps
    hook/agentlink_families.py the hook file
    hook/fam_<group>.py        the family: tools bound to the core
    hook/api.py                the core (no agentlink import)
    hook/data/tools.json       one draft entry for each command
    tests/test_port.py         format, handlers, import and lint checks
    scripts/ste_lint.py        the lint, plain Python
    cookbook.json              a draft cookbook: one command recipe a command

Plain Python, no FreeCAD and no other Agent Link module:

    python3 -m agentlink.porting <addon folder> [--name N] [--out ROOT] [--overwrite]
    python3 <hub>/agentlink/porting.py <addon folder>
"""
import ast
import datetime
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
HUB = os.path.dirname(HERE)
MAX_FILES = 400
MAX_FILE_BYTES = 1024 * 1024
SKIP_DIRS = {".git", "__pycache__", "tests", "test", "node_modules", ".github", "build", "dist"}
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,47}$")
MAX_WORDS = 20


class Refused(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def home():
    return os.environ.get("AGENTLINK_HOME") or os.path.expanduser("~/AgentLink")


def ports_root():
    return os.path.join(home(), "ports")


def _inside(path, root):
    p, r = os.path.realpath(path), os.path.realpath(root)
    return p == r or p.startswith(r.rstrip(os.sep) + os.sep)


def _tilde(p):
    h = os.path.expanduser("~")
    p = os.path.realpath(p)
    return "~" + p[len(h):] if h and h != "/" and (p == h or p.startswith(h + os.sep)) else p


# ---- names and words -----------------------------------------------------------------------

def snake(text):
    t = re.sub(r"[^A-Za-z0-9]+", "_", str(text or ""))
    t = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", t)
    t = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", t)
    t = re.sub(r"_+", "_", t).strip("_").lower()
    if t and not t[0].isalpha():
        t = "x_" + t
    return t[:48]


def plain_name(text):
    """A folder or group name: lower case, words joined by _ (no camelCase split)."""
    t = re.sub(r"[^a-z0-9]+", "_", str(text or "").lower()).strip("_")
    if t and not t[0].isalpha():
        t = "x_" + t
    return t[:48]


def clean(text, cap=300):
    """One plain line: no accelerator &, no control characters, no tags."""
    t = str(text or "").replace("&&", "\0").replace("&", "").replace("\0", "&")
    t = re.sub(r"<[^>]{0,200}>", " ", t)
    t = "".join(c if ord(c) >= 32 and c not in "  ‮‭​" else " " for c in t)
    t = " ".join(t.split())
    return t[:cap]


def sentences(text):
    t = " ".join(str(text or "").split())
    return [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9`\"(])", t) if s.strip()]


def words(s):
    return len(re.sub(r'"[^"]*"|`[^`]*`', "X", s).split())


def draft_description(cmd, menu, tip):
    """A short STE draft: what the command is, then its tool tip when each
    sentence of it has 20 words or fewer."""
    label = clean(menu, 60).rstrip(".…") or cmd
    first = f"Run the FreeCAD command {cmd} ({label}), as its button does."
    if words(first) > MAX_WORDS:
        first = f"Run the FreeCAD command {cmd}, as its button does."
    tip = clean(tip, 300)
    keep = []
    for s in sentences(tip):
        if words(s) > MAX_WORDS or len(" ".join(keep + [s])) > 240:
            break
        keep.append(s if s.endswith((".", "!", "?")) else s + ".")
    return " ".join([first] + keep)


# ---- reading the add-on --------------------------------------------------------------------

def _str(node, consts):
    """A string from a constant, a known name, or the last string argument
    of a call (QT_TRANSLATE_NOOP("ctx", "text"), translate(...))."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name) and node.id in consts:
        return consts[node.id]
    if isinstance(node, ast.Call):
        for a in reversed(node.args):
            v = _str(a, consts)
            if v is not None:
                return v
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str)) or None
    return None


def _resources(cls, consts):
    """MenuText, ToolTip and Pixmap from a command class's GetResources."""
    for fn in cls.body:
        if isinstance(fn, ast.FunctionDef) and fn.name == "GetResources":
            for n in ast.walk(fn):
                if isinstance(n, ast.Return) and isinstance(n.value, ast.Dict):
                    out = {}
                    for k, v in zip(n.value.keys, n.value.values):
                        key = _str(k, consts) if k is not None else None
                        if key in ("MenuText", "ToolTip", "Pixmap"):
                            val = _str(v, consts)
                            if val is not None:
                                out[key] = val
                    return out
    return None


def _is_workbench(cls):
    for b in cls.bases:
        name = b.attr if isinstance(b, ast.Attribute) else getattr(b, "id", "")
        if name == "Workbench":
            return True
    return False


_CMD_LIKE = re.compile(r"^([A-Z][A-Za-z0-9]+)_[A-Z][A-Za-z0-9_]*$")


def _named(tree):
    """Command-like strings ("Prefix_Name") among a file's module-level
    constants, in file order, of the prefix most of them share."""
    found = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            for c in ast.walk(node.value) if node.value is not None else ():
                if isinstance(c, ast.Constant) and isinstance(c.value, str) and _CMD_LIKE.match(c.value) and c.value not in found:
                    found.append(c.value)
    if not found:
        return []
    prefixes = [_CMD_LIKE.match(c).group(1) for c in found]
    prefixes = [x for x in prefixes if x != "Std"]
    if not prefixes:
        return []
    top = max(set(prefixes), key=prefixes.count)
    return [c for c in found if _CMD_LIKE.match(c).group(1) == top][:100]


def py_files(folder):
    out = []
    for root, dirs, files in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
        for f in sorted(files):
            if f.endswith(".py"):
                p = os.path.join(root, f)
                if os.path.islink(p) or not _inside(p, folder):
                    continue
                out.append(p)
                if len(out) >= MAX_FILES:
                    return out
    return out


def read_addon(folder):
    """What the add-on's files say: { name, package, licence, workbench,
    commands [{ command, menu, tip, file }], unread [why] }. Text only."""
    folder = os.path.realpath(os.path.expanduser(str(folder)))
    if not os.path.isdir(folder):
        raise Refused("not_found", f"folder: no such folder ({_tilde(folder)}). Give an add-on's folder, for example one in FreeCAD's Mod folder.")
    if not any(os.path.isfile(os.path.join(folder, f)) for f in ("InitGui.py", "Init.py", "package.xml")):
        raise Refused("invalid_input", f"folder: {_tilde(folder)} has no InitGui.py, Init.py or package.xml. Give the add-on's top folder.")
    name, licence = os.path.basename(folder), None
    pkg_xml = os.path.join(folder, "package.xml")
    if os.path.isfile(pkg_xml) and os.path.getsize(pkg_xml) < MAX_FILE_BYTES:
        with open(pkg_xml, encoding="utf-8", errors="replace") as f:
            text = f.read()
        m = re.search(r"<name>\s*([^<]{1,80}?)\s*</name>", text)
        if m:
            name = clean(m.group(1), 80)
        m = re.search(r"<license[^>]*>\s*([^<]{1,60}?)\s*</license>", text)
        if m:
            licence = clean(m.group(1), 60)
    classes, cmds, unread, workbench = {}, [], [], None
    trees = []
    for p in py_files(folder):
        rel = os.path.relpath(p, folder)
        if os.path.getsize(p) > MAX_FILE_BYTES:
            unread.append(f"{rel}: larger than 1 MB, not read")
            continue
        with open(p, encoding="utf-8", errors="replace") as f:
            src = f.read()
        if "addCommand" not in src and "GetResources" not in src and "Workbench" not in src:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            unread.append(f"{rel}: not read ({e.msg}, line {e.lineno})")
            continue
        consts = {}
        for n in tree.body:
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                v = _str(n.value, {}) if isinstance(n.value, ast.Constant) else None
                if v is not None:
                    consts[n.targets[0].id] = v
        for n in ast.walk(tree):
            if isinstance(n, ast.ClassDef):
                res = _resources(n, consts)
                if res is not None:
                    classes.setdefault(n.name, res)
                if workbench is None and _is_workbench(n):
                    workbench = n.name
        trees.append((rel, tree, consts))
    seen = set()
    for rel, tree, consts in trees:
        made = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Call):
                f = n.value.func
                made[n.targets[0].id] = f.id if isinstance(f, ast.Name) else getattr(f, "attr", None)
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "addCommand" and len(n.args) >= 2):
                continue
            cmd = _str(n.args[0], consts)
            if not cmd or not re.match(r"^[A-Za-z][A-Za-z0-9_]{0,79}$", cmd):
                # A loop over a table of names: the file's command-like
                # string constants stand in for them, by name only.
                guess = [c for c in _named(tree) if c not in seen]
                unread.append(f"{rel}:{n.lineno}: addCommand with a name made at run time" +
                              (f"; {len(guess)} names taken from the file's constants, without words" if guess else ", not read"))
                for c in guess:
                    seen.add(c)
                    cmds.append({"command": c, "menu": "", "tip": "", "file": rel, "class": None})
                continue
            o = n.args[1]
            cls = None
            if isinstance(o, ast.Call):
                cls = o.func.id if isinstance(o.func, ast.Name) else getattr(o.func, "attr", None)
            elif isinstance(o, ast.Name):
                cls = made.get(o.id, o.id)
            res = classes.get(cls) or {}
            if cmd in seen:
                continue
            seen.add(cmd)
            cmds.append({"command": cmd, "menu": clean(res.get("MenuText", ""), 80), "tip": clean(res.get("ToolTip", ""), 300), "file": rel,
                         "class": cls})
            if not res:
                unread.append(f"{rel}:{n.lineno}: {cmd}: no GetResources found for {cls}; its words are left empty")
    package = None
    for d in sorted(os.listdir(folder)):
        p = os.path.join(folder, d)
        if os.path.isfile(os.path.join(p, "__init__.py")) and d.isidentifier() and not d.startswith("_") and d not in SKIP_DIRS:
            if any(c["file"].startswith(d + os.sep) for c in cmds) or package is None:
                package = d
    return {"folder": folder, "name": name, "package": package, "licence": licence, "workbench": workbench, "commands": cmds, "unread": unread}


def hub_tool_names():
    """Agent Link's own tool names, from its data (no import)."""
    out = set()
    try:
        with open(os.path.join(HERE, "data", "tools.json"), encoding="utf-8") as f:
            out |= set(json.load(f)["entries"])
    except (OSError, ValueError, KeyError):
        pass
    return out


# ---- drafting ------------------------------------------------------------------------------

_REFUSED_LIKE = re.compile(r"^(Std_Dlg|Std_Macro|Std_RecentMacros|Std_AddonMgr|Std_Quit|Std_ToggleBreakpoint)")


def refused_command(cmd):
    """Why cmd_run refuses cmd, or None (its list where FreeCAD is; else its
    patterns: this file also runs on its own, with no FreeCAD)."""
    try:
        from agentlink.families.app import refused

        return refused(cmd)
    except Exception:  # noqa: BLE001
        return "it runs a macro or opens a dialog of the person's" if _REFUSED_LIKE.match(str(cmd)) else None


def plan(info, group=None, taken=()):
    """The draft tools: [{ tool, command, description }]."""
    group = group or plain_name(info["name"]).split("_")[0][:20] or "addon"
    if not NAME_RE.match(group):
        group = "addon"
    taken, out, used = set(taken), [], set()
    for c in info["commands"]:
        # A command cmd_run refuses (a macro, a modal dialog, quit) gets no
        # drafted tool: the draft calls runCommand itself (red team, 2026-11-18).
        if refused_command(c["command"]):
            info.setdefault("unread", []).append(f"{c['command']}: not drafted — cmd_run refuses it ({refused_command(c['command'])})")
            continue
        prefix, _, rest = c["command"].partition("_")
        t = f"{group}_{snake(rest)}" if rest and plain_name(prefix) == group else f"{group}_{snake(c['command'])}"
        t = t[:48]
        base, i = t, 2
        while t in taken or t in used:
            t = f"{base[:44]}_{i}"
            i += 1
        used.add(t)
        out.append({"tool": t, "command": c["command"], "description": draft_description(c["command"], c["menu"], c["tip"])})
    return group, out


def tools_json(info, group, tools, date):
    ents = {}
    for t in tools:
        e = {"group": group, "description": t["description"],
             "inputSchema": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
             "changes": True, "source": f"drafted by port_scaffold from {t['command']}", "date": date, "commands": [t["command"]]}
        if info.get("workbench"):
            e["workbench"] = info["workbench"]
        ents[t["tool"]] = e
    return {"dataVersion": "1.0.0", "licence": "CC-BY-4.0", "about": f"{clean(info['name'], 80)}'s tools for Agent Link (a draft by port_scaffold).",
            "entries": ents}


def cookbook_json(info, name, tools, date):
    ents = {t["tool"]: {"description": t["description"], "recipe": {"command": t["command"]}} for t in tools}
    doc = {"cookbookVersion": "1.0.0", "name": name, "about": f"Commands of {clean(info['name'], 80)}, run by cmd_run (a draft by port_scaffold).",
           "source": "drafted by port_scaffold", "date": date, "entries": ents}
    if info.get("package"):
        doc["addon"] = {"package": info["package"], "name": clean(info["name"], 80)}
    return doc


HOOK = '''# SPDX-License-Identifier: {licence}
# The hook file. Agent Link loads this module when it is installed.
# Without Agent Link, nothing imports it. Drafted by port_scaffold on {date}.
# Put this folder's files in the add-on's package. Check each line.
AGENTLINK_API = ">=1,<2"
CREDIT = None  # or "Based on <work> by <author>": shown with the tools.
LICENSE = "{licence}"

from . import fam_{group}

FAMILIES = [fam_{group}]
'''

FAMILY = '''# SPDX-License-Identifier: {licence}
# The {group} tools for agents. The definitions are in data/tools.json.
# The work is in api.py, which never imports Agent Link. Only this module
# and agentlink_families.py import Agent Link. Drafted by port_scaffold.
import os

from agentlink import hooks

from . import api

GROUP = "{group}"
INFO = {info!r}
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

# The live echo: the bench that comes up and the button that lights.
WORKBENCHES = {workbenches!r}
COMMANDS = {commands!r}
AREAS = {{"{group}_": {area!r}}}


def tools(session):
    handlers = {{name: (lambda a, _n=name: api.run(_n, a)) for name in api.COMMANDS}}
    return hooks.tools_from_data(DATA, GROUP, handlers, {area!r})
'''

API = '''# SPDX-License-Identifier: {licence}
# The core of the port: plain functions on FreeCAD. This module never
# imports Agent Link. A refusal is Refused(code, message): a code and a
# message that says what to do next. Drafted by port_scaffold: each tool
# runs its command as the button does. Write real functions with arguments
# where you can, and change the tool data to match.

# Each tool and the FreeCAD command it runs.
COMMANDS = {commands!r}
CODES = ("invalid_input", "not_found", "invalid_state", "unavailable", "failed")


class Refused(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def run(tool, args):
    cmd = COMMANDS.get(tool)
    if cmd is None:
        raise Refused("not_found", f"{{tool}}: no such tool in this add-on.")
    if args:
        raise Refused("invalid_input", f"{{tool}} takes no arguments yet. Call it with {{{{}}}}.")
    try:
        import FreeCADGui
    except ImportError:
        raise Refused("unavailable", f"{{tool}} needs the FreeCAD window. Open FreeCAD with its window.")
    if getattr(FreeCADGui, "getMainWindow", None) is None or cmd not in FreeCADGui.listCommands():
        raise Refused("unavailable", f"{{cmd}} is not loaded. Activate the add-on's workbench once, then call {{tool}} again.")
    FreeCADGui.runCommand(cmd, 0)
    return {{"ran": cmd}}
'''

TEST = '''# SPDX-License-Identifier: {licence}
# Checks of the port, drafted by port_scaffold. Run: python3 -m unittest discover -s tests
# 1. The tool data passes Agent Link's format check (skipped without Agent Link).
# 2. Every tool has a handler, and every handler a tool.
# 3. The core (api.py) imports nothing named agentlink, in a fresh Python.
# 4. Each description passes the STE lint (scripts/ste_lint.py).
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "hook")
sys.path.insert(0, HOOK)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import api  # noqa: E402
import ste_lint  # noqa: E402


def data():
    with open(os.path.join(HOOK, "data", "tools.json"), encoding="utf-8") as f:
        return json.load(f)


class Port(unittest.TestCase):
    def test_format(self):
        try:
            from agentlink import tooldata
        except ImportError:
            self.skipTest("Agent Link is not on the path")
        self.assertEqual(tooldata.check(data()), [])

    def test_every_tool_has_a_handler(self):
        self.assertEqual(sorted(data()["entries"]), sorted(api.COMMANDS))

    def test_core_imports_no_agentlink(self):
        code = "import sys; sys.path.insert(0, %r); import api; print([m for m in sys.modules if m.split('.')[0] == 'agentlink'])" % HOOK
        r = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "[]")

    def test_refusal_has_code_and_next_step(self):
        with self.assertRaises(api.Refused) as e:
            api.run("no_such_tool", {{}})
        self.assertIn(e.exception.code, api.CODES)

    def test_ste_lint(self):
        self.assertEqual(ste_lint.faults(ROOT), [])


if __name__ == "__main__":
    unittest.main()
'''

LINT = '''#!/usr/bin/env python3
# SPDX-License-Identifier: {licence}
# The STE lint of the port's descriptions, plain Python (drafted by
# port_scaffold; the rules are Agent Link's scripts/ste_check.py):
# - each sentence has 20 words or fewer (text in quotes or backticks is one word);
# - a description says what the tool does and when to use it (20 characters or more);
# - one line, no control characters.
# Run: python3 scripts/ste_lint.py   (exit 1 on a fault)
import json
import os
import re
import sys

MAX_WORDS = 20
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sentences(text):
    t = " ".join(str(text or "").split())
    return [s for s in re.split(r"(?<=[.!?])\\s+(?=[A-Z0-9`\\"(])", t) if s.strip()]


def words(s):
    return len(re.sub(r'"[^"]*"|`[^`]*`', "X", s).split())


def lint(name, text):
    out = []
    if not isinstance(text, str) or len(text) < 20:
        out.append(f"{{name}}: say what it does and when to use it")
        return out
    if any(ord(c) < 32 for c in text):
        out.append(f"{{name}}: one line, no control characters")
    for s in sentences(text):
        if words(s) > MAX_WORDS:
            out.append(f"{{name}}: {{words(s)}} words: {{s[:80]}}")
    return out


def faults(root=ROOT):
    out = []
    for rel in (os.path.join("hook", "data", "tools.json"), "cookbook.json"):
        p = os.path.join(root, rel)
        if not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8") as f:
            doc = json.load(f)
        for name, e in doc.get("entries", {{}}).items():
            out += [f"{{rel}}: {{x}}" for x in lint(name, e.get("description"))]
    return out


if __name__ == "__main__":
    found = faults()
    print("\\n".join(found) or "STE lint: no faults")
    sys.exit(1 if found else 0)
'''

README = '''# Draft port: {name}

Drafted by Agent Link's port_scaffold on {date}, from the add-on in
`{folder}`. Nothing in the add-on or in Agent Link was changed. The scaffold
read the add-on's files as text. It did not run them.

Commands found: {n}. Items not read: {u}.

## What is here

- `hook/agentlink_families.py`: the hook file.
- `hook/fam_{group}.py`: the family. It binds each tool to the core.
- `hook/api.py`: the core. It never imports Agent Link.
- `hook/data/tools.json`: one draft tool for each command.
- `tests/test_port.py`: the checks. `scripts/ste_lint.py`: the lint.
- `cookbook.json`: a draft cookbook with one command recipe a command.

## Next steps

1. Read the porting guide: `guide_read {{ topic: "porting" }}`.
2. Read each draft description. Make it say what the tool does and when to use it.
3. Give each tool its real arguments in `inputSchema` and in `api.py`.
4. Set `changes` to false for each tool that only reads.
5. Run `python3 scripts/ste_lint.py` and `python3 -m unittest discover -s tests`.
6. Copy the `hook/` files into the add-on's package.
7. For a quick start with no port, import the cookbook:
   `cookbook_import {{ path: "~/AgentLink/ports/{port}/cookbook.json" }}`.
   The person then approves it once.

## Not read

{unread}
'''


def scaffold(addon_folder, name=None, out_root=None, overwrite=False, taken=None, date=None):
    """Write the draft port. Answers what was found and written."""
    info = read_addon(addon_folder)
    port = plain_name(name or info["name"]) or "addon"
    if not NAME_RE.match(port):
        raise Refused("invalid_input", f"name: lower_case letters, digits and _, 2 to 48 characters. Got {str(name or info['name'])[:60]!r}.")
    root = os.path.realpath(os.path.expanduser(out_root or ports_root()))
    out = os.path.join(root, port)
    for what, there in (("the add-on", info["folder"]), ("Agent Link", HUB)):
        if _inside(out, there) or _inside(there, out):
            raise Refused("invalid_input", f"The port goes in {_tilde(out)}, which is inside {what} or holds it. A port is written apart from both. Nothing was written.")
    if os.path.exists(out) and not overwrite:
        raise Refused("invalid_state", f"{_tilde(out)} is there already. overwrite: true writes the draft files again (other files stay).")
    if not info["commands"]:
        raise Refused("not_found", f"No Gui.addCommand found in {_tilde(info['folder'])}. The add-on may make its commands at run time. "
                                   "Read the porting guide and write the tool data by hand.")
    date = date or datetime.date.today().isoformat()
    group, tools = plan(info, taken=hub_tool_names() | set(taken or ()))
    commands = {t["tool"]: t["command"] for t in tools}
    lic = info.get("licence") or "LGPL-2.1-or-later"
    if not re.match(r"^[A-Za-z0-9.+ ()-]{1,60}$", lic):
        lic = "LGPL-2.1-or-later"
    area = clean(info["name"], 40) or group
    wbs = {group + "_": info["workbench"]} if info.get("workbench") else {}
    files = {
        "README.md": README.format(name=clean(info["name"], 80), date=date, folder=_tilde(info["folder"]), n=len(tools), u=len(info["unread"]), group=group,
                                   port=port, unread="\n".join(f"- {x}" for x in info["unread"]) or "Nothing."),
        os.path.join("hook", "agentlink_families.py"): HOOK.format(licence=lic, date=date, group=group),
        os.path.join("hook", f"fam_{group}.py"): FAMILY.format(licence=lic, group=group, info=f"{area}: its commands as tools (a draft port).",
                                                              workbenches=wbs, commands=commands, area=area),
        os.path.join("hook", "api.py"): API.format(licence=lic, commands=commands),
        os.path.join("hook", "data", "tools.json"): json.dumps(tools_json(info, group, tools, date), indent=1, ensure_ascii=False) + "\n",
        os.path.join("tests", "test_port.py"): TEST.format(licence=lic),
        os.path.join("scripts", "ste_lint.py"): LINT.format(licence=lic),
        "cookbook.json": json.dumps(cookbook_json(info, port, tools, date), indent=1, ensure_ascii=False) + "\n",
    }
    for rel, text in files.items():
        p = os.path.join(out, rel)
        if not _inside(p, out):
            raise Refused("invalid_input", f"{rel}: leads out of the port folder. Nothing more was written.")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
    return {"port": port, "folder": _tilde(out), "addon": clean(info["name"], 80), "group": group, "package": info["package"],
            "workbench": info["workbench"], "tools": [{"tool": t["tool"], "command": t["command"]} for t in tools],
            "unread": info["unread"][:20], "files": sorted(f.replace(os.sep, "/") for f in files),
            "next": "Read README.md there, then guide_read { topic: \"porting\" }. Edit the drafts, then run the lint and the tests."}


def main(argv):
    import argparse

    ap = argparse.ArgumentParser(description="Draft an Agent Link port of an installed FreeCAD add-on (output in ~/AgentLink/ports/<name>/).")
    ap.add_argument("folder")
    ap.add_argument("--name")
    ap.add_argument("--out", help="the ports folder (default ~/AgentLink/ports)")
    ap.add_argument("--overwrite", action="store_true")
    a = ap.parse_args(argv)
    try:
        r = scaffold(a.folder, a.name, a.out, a.overwrite)
    except Refused as e:
        print(f"refused ({e.code}): {e.message}", file=sys.stderr)
        return 1
    print(json.dumps(r, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
