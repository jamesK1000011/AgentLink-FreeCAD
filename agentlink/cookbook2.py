# SPDX-License-Identifier: LGPL-2.1-or-later
"""Cookbook schema v2: an add-on as data, one entry for each thing it does
(docs/design/porting-2026-11-18.md part D, guide_read { topic: "porting" }).

A socket with instructions. Each entry has a level. Try the levels in this
order; "not supported" is the last one:

    1 data      a Python function of the add-on, typed inputs, headless
    2 form      a task panel; its fields are filled from data, no clicks
    3 tree      branches: what each path needs, so the agent can choose
    4 window    the command, pressed in the window (cmd_run)
    5 none      not supported; blocker says exactly why. Try again for
                each new add-on version.

File header:

    {"cookbookVersion": "2.0.0", "name": "mine", "about": "...",
     "addon": {"package": "mine", "name": "Mine", "version": "1.2.0",
               "workbench": "MineWorkbench", "licence": "LGPL-2.1", "credit": "..."},
     "coverage": {...},           the author's bars: shown, never trusted
     "entries": {NAME: ENTRY}}

ENTRY:

    level          1..5
    description    the author's words: data, capped, one line
    call           {"function": {"module": "mine.api", "name": "fit", "document": "doc"}}
                   {"command": "Mine_Fit", "index": 0}
                   {"form": {"command": "Mine_Fit", "fields": {WIDGET: FILL}, "accept": "OK"}}
                   (no call for a tree, or for level 5)
    inputs         {NAME: {"type", "unit", "min", "max", "default", "required",
                           "choices", "count", "maxLength", "description"}}
    preconditions  {"workbench", "document": "open"|"none"|"any",
                    "selection": {"kind", "min", "max"}, "objects": {"type", "min"}}
    result         {"makes": words, "check": {"newObjects": {"min", "type"},
                    "changedObjects": {"min"}, "returns": TYPE, "valid": true}}
    tree           [{"when": COND, "next": ENTRY or "stop", "say": words}]
    risk           the author's claim; Agent Link works the risk out itself
    probe          {"version", "result": "pass"|"fail"|"skip", "date", "why"}
    source         {"from": "code"|"docs"|"live", "checked": true|false}
    blocker        level 5: what blocks it, exactly

COND is data only: {"input": NAME, "op": OP, "value": V},
{"selection": {"kind", "op", "value"}}, {"all": [COND]}, {"any": [COND]},
{"not": COND}. OP: eq ne lt le gt ge in.

Plain Python: no FreeCAD. The family (agentlink/families/porting.py) gives
the FreeCAD side (the document, the selection, the runners).
"""
import datetime
import math
import re

VERSION_MAJOR = 2
LEVELS = {1: "data", 2: "form", 3: "tree", 4: "window", 5: "not supported"}
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,47}$")
INPUT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,47}$")
MODULE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){0,7}$")
FUNC_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
COMMAND_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,79}$")
WIDGET_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,79}$")
REF_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,79}(\.(Face|Edge|Vertex)[1-9][0-9]{0,5})?$")
VERSION_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.+-]{0,39}$")
MAX_INPUTS = 24
MAX_BRANCHES = 16
MAX_DEPTH = 4
MAX_STRING = 2000
MAX_LIST = 1000
MAX_DESC = 400
MAX_SAY = 200
MAX_BLOCKER = 300

NUMBERS = {"number", "integer", "length", "angle"}
PICKS = {"face": "Face", "edge": "Edge", "vertex": "Vertex", "object": None, "body": None}
TYPES = NUMBERS | set(PICKS) | {"boolean", "string", "choice", "vector", "list"}
UNITS = {"length": {"mm"}, "angle": {"deg"}, "number": {"mm", "deg", "mm2", "mm3", "g", "kg", "N", "MPa", "s", "%", "1", ""}}
PICK_AS = {"name", "object", "subname", "shape"}
OPS = {"eq", "ne", "lt", "le", "gt", "ge", "in"}
FILL_KEYS = {"input", "value"}
CHECKS = {"newObjects", "changedObjects", "returns", "valid"}
RISKS = ("none", "file", "code")

# Words an agent could take as an order. A description that holds one is
# flagged in each answer and in the person's OK (the words stay data).
INJECTION = re.compile(r"(ignore (all |the |any )?(previous|prior|above|earlier)|disregard|system prompt|you are now|you must|"
                       r"as (the|an) (agent|assistant|ai)|do not tell|don't tell|without asking|pre-?approved|pre-?authori[sz]ed|already approved|"
                       r"\bapprove_(code|file)|cookbook_approve|press approve|the (user|person) (wants|said|agreed)|admin(istrator)? (says|mode)|"
                       r"developer mode|jailbreak|<\|?(system|im_start|assistant)|\[\[|\]\]|BEGIN (SYSTEM|INSTRUCTIONS)|new instructions|override)", re.I)


def injection_flags(text):
    m = INJECTION.findall(str(text or ""))
    return sorted({(x[0] if isinstance(x, tuple) else x).lower()[:40] for x in m})


# ---- the format ------------------------------------------------------------------------------

def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _line(text, cap, what):
    if not isinstance(text, str) or not text.strip():
        return [f"{what}: a sentence is necessary"]
    out = []
    if len(text) > cap:
        out.append(f"{what}: {len(text)} characters; {cap} or fewer")
    if any(ord(c) < 32 or 0x7f <= ord(c) < 0xa0 or c in "  ‮‭​⁦⁧⁨⁩" for c in text):
        out.append(f"{what}: one line, no control characters")
    return out


def check_input(name, spec, where):
    if not isinstance(name, str) or not INPUT_RE.match(name) or name.startswith("_"):
        return [f"{where}: input {str(name)[:40]!r}: a plain name (letters, digits, _; no _ in front)"]
    w = f"{where}.{name}"
    if not isinstance(spec, dict):
        return [f"{w}: an object with type"]
    out = []
    allowed = {"type", "unit", "min", "max", "default", "required", "choices", "count", "maxLength", "description", "as", "items"}
    if set(spec) - allowed:
        out.append(f"{w}: unknown fields {sorted(set(spec) - allowed)}")
    t = spec.get("type")
    if t not in TYPES:
        return out + [f"{w}.type: one of {', '.join(sorted(TYPES))}"]
    if "unit" in spec and (t not in UNITS or spec["unit"] not in UNITS[t]):
        out.append(f"{w}.unit: {', '.join(sorted(UNITS.get(t, {'(none)'}))) if t in UNITS else 'none for a ' + t}")
    for k in ("min", "max"):
        if k in spec and (t not in NUMBERS or not _num(spec[k])):
            out.append(f"{w}.{k}: a number, for a number input only")
    if _num(spec.get("min")) and _num(spec.get("max")) and spec["min"] > spec["max"]:
        out.append(f"{w}: min is more than max")
    if "required" in spec and not isinstance(spec["required"], bool):
        out.append(f"{w}.required: true or false")
    if t == "choice":
        ch = spec.get("choices")
        if not isinstance(ch, list) or not 1 <= len(ch) <= 64 or not all(isinstance(c, (str, int)) and not isinstance(c, bool) for c in ch):
            out.append(f"{w}.choices: a list of 1 to 64 strings or integers")
        elif any(isinstance(c, str) and len(c) > 80 for c in ch):
            out.append(f"{w}.choices: 80 characters or fewer each")
    elif "choices" in spec:
        out.append(f"{w}.choices: for a choice input only")
    if "maxLength" in spec and (t != "string" or not isinstance(spec["maxLength"], int) or not 1 <= spec["maxLength"] <= MAX_STRING):
        out.append(f"{w}.maxLength: 1 to {MAX_STRING}, for a string input")
    if "count" in spec:
        c = spec["count"]
        if t not in PICKS and t != "list" or not (isinstance(c, list) and len(c) == 2 and all(isinstance(x, int) and not isinstance(x, bool) for x in c)
                                                  and 0 <= c[0] <= c[1] <= MAX_LIST):
            out.append(f"{w}.count: [min, max] picks or items, for a pick or a list")
    if "as" in spec and (t not in PICKS or spec["as"] not in PICK_AS):
        out.append(f"{w}.as: one of {', '.join(sorted(PICK_AS))}, for a pick")
    if t == "list":
        it = spec.get("items")
        if not isinstance(it, dict) or it.get("type") not in (NUMBERS | {"boolean", "string"}):
            out.append(f"{w}.items: {{type}} of a number, boolean or string")
    elif "items" in spec:
        out.append(f"{w}.items: for a list input only")
    if "description" in spec:
        out += _line(spec["description"], 200, f"{w}.description")
    if "default" in spec and not out:
        try:
            coerce(name, spec, spec["default"])
        except ValueError as e:
            out.append(f"{w}.default: {e}")
    return out


def _check_cond(c, inputs, where, depth=0):
    if depth > MAX_DEPTH:
        return [f"{where}: {MAX_DEPTH} levels of all/any/not or fewer"]
    if not isinstance(c, dict) or len(c) != 1:
        return [f"{where}: one of input, selection, all, any, not"]
    (k, v), = c.items()
    if k in ("all", "any"):
        if not isinstance(v, list) or not 1 <= len(v) <= 8:
            return [f"{where}.{k}: a list of 1 to 8 conditions"]
        return [p for i, x in enumerate(v) for p in _check_cond(x, inputs, f"{where}.{k}[{i}]", depth + 1)]
    if k == "not":
        return _check_cond(v, inputs, f"{where}.not", depth + 1)
    if k == "input":
        return [f"{where}: input conditions are {{input, op, value}}"]
    if k == "selection":
        if not isinstance(v, dict) or set(v) - {"kind", "op", "value"} or v.get("kind", "any") not in (set(PICKS) | {"any"}) \
                or v.get("op", "ge") not in OPS - {"in"} or not isinstance(v.get("value", 1), int) or isinstance(v.get("value"), bool):
            return [f"{where}.selection: {{kind, op, value}}: kind a pick type or any, op eq ne lt le gt ge, value an integer"]
        return []
    return [f"{where}: one of input, selection, all, any, not"]


def check_cond(c, inputs, where, depth=0):
    if isinstance(c, dict) and set(c) == {"input", "op", "value"}:
        out = []
        if c["input"] not in inputs:
            out.append(f"{where}.input: {str(c['input'])[:40]} is not an input of this entry")
        if c["op"] not in OPS:
            out.append(f"{where}.op: one of {', '.join(sorted(OPS))}")
        v = c["value"]
        plain = lambda x: x is None or isinstance(x, (bool, str)) and len(str(x)) <= 200 or _num(x)  # noqa: E731
        if c["op"] == "in":
            if not isinstance(v, list) or len(v) > 64 or not all(plain(x) for x in v):
                out.append(f"{where}.value: a list of up to 64 plain values")
        elif not plain(v):
            out.append(f"{where}.value: a number, string, boolean or null")
        return out
    if isinstance(c, dict) and len(c) == 1 and next(iter(c)) in ("all", "any"):
        v = c[next(iter(c))]
        if not isinstance(v, list) or not 1 <= len(v) <= 8:
            return [f"{where}: a list of 1 to 8 conditions"]
        if depth >= MAX_DEPTH:
            return [f"{where}: {MAX_DEPTH} levels of all/any/not or fewer"]
        return [p for i, x in enumerate(v) for p in check_cond(x, inputs, f"{where}[{i}]", depth + 1)]
    if isinstance(c, dict) and set(c) == {"not"}:
        if depth >= MAX_DEPTH:
            return [f"{where}: {MAX_DEPTH} levels of all/any/not or fewer"]
        return check_cond(c["not"], inputs, f"{where}.not", depth + 1)
    return _check_cond(c, inputs, where, depth)


def check_call(call, level, where, package):
    if level in (3, 5):
        if call is not None:
            return [f"{where}: a level {level} entry has no call"]
        return []
    if not isinstance(call, dict) or len(call) != 1:
        return [f"{where}: one of function, command, form"]
    (k, v), = call.items()
    if level == 1 and k != "function":
        return [f"{where}: a level 1 entry calls a function"]
    if level == 2 and k != "form":
        return [f"{where}: a level 2 entry fills a form"]
    if level == 4 and k != "command":
        return [f"{where}: a level 4 entry runs a command"]
    out = []
    if k == "function":
        if not isinstance(v, dict) or set(v) - {"module", "name", "document"}:
            return [f"{where}.function: {{module, name, document}}"]
        mod, fn = v.get("module"), v.get("name")
        if not isinstance(mod, str) or not MODULE_RE.match(mod):
            out.append(f"{where}.function.module: a dotted module name")
        elif not package:
            out.append(f"{where}.function: addon.package is necessary")
        elif not (mod == package or mod.startswith(package + ".")):
            out.append(f"{where}.function.module: {mod} is not in the add-on's package {package}")
        elif any(x.startswith("_") for x in mod.split(".")):
            out.append(f"{where}.function.module: {mod} has a private part (a name with _ in front)")
        if not isinstance(fn, str) or not FUNC_RE.match(fn):
            out.append(f"{where}.function.name: a public function name (no _ in front)")
        elif re.search(r"approv|grant|person_ok|confirm|consent", f"{fn}.{mod}", re.I):
            out.append(f"{where}.function: {fn} looks like an OK of the person's; a cookbook never calls one")
        if "document" in v and not (isinstance(v["document"], str) and INPUT_RE.match(v["document"])):
            out.append(f"{where}.function.document: the name of the function's document argument (doc)")
        return out
    if k == "command":
        if not isinstance(v, str) or not COMMAND_RE.match(v):
            return [f"{where}.command: a FreeCAD command name (letters, digits and _)"]
        return []
    if k == "form":
        if not isinstance(v, dict) or set(v) - {"command", "fields", "accept", "ui"}:
            return [f"{where}.form: {{command, fields, accept, ui}}"]
        if not isinstance(v.get("command"), str) or not COMMAND_RE.match(v["command"]):
            out.append(f"{where}.form.command: the command that opens the task panel")
        if v.get("accept", "OK") not in ("OK", "Apply", "Close"):
            out.append(f"{where}.form.accept: OK, Apply or Close")
        if "ui" in v and not (isinstance(v["ui"], str) and re.match(r"^[A-Za-z0-9_][A-Za-z0-9_./-]{0,119}\.ui$", v["ui"]) and ".." not in v["ui"]):
            out.append(f"{where}.form.ui: the .ui file's path in the add-on")
        f = v.get("fields")
        if not isinstance(f, dict) or len(f) > 40:
            out.append(f"{where}.form.fields: an object of up to 40 widget names")
        else:
            for wname, fill in f.items():
                if not isinstance(wname, str) or not WIDGET_RE.match(wname):
                    out.append(f"{where}.form.fields: {str(wname)[:40]!r}: a widget's objectName")
                elif not isinstance(fill, dict) or len(fill) != 1 or set(fill) - FILL_KEYS:
                    out.append(f"{where}.form.fields.{wname}: {{input: NAME}} or {{value: V}}")
        return out
    return [f"{where}: one of function, command, form"]


def check_entry(name, e, package, names):
    where = name
    if not isinstance(e, dict):
        return [f"{where}: an object"]
    out = []
    allowed = {"level", "description", "call", "inputs", "preconditions", "result", "tree", "risk", "probe", "source", "blocker", "notes"}
    if set(e) - allowed:
        out.append(f"{where}: unknown fields {sorted(set(e) - allowed)}")
    lv = e.get("level")
    if lv not in LEVELS or isinstance(lv, bool):
        return out + [f"{where}.level: 1 (data), 2 (form), 3 (tree), 4 (window) or 5 (not supported)"]
    out += _line(e.get("description"), MAX_DESC, f"{where}.description")
    if isinstance(e.get("description"), str) and len(e["description"]) < 20:
        out.append(f"{where}.description: say what it does and when to use it")
    out += check_call(e.get("call"), lv, f"{where}.call", package)
    inputs = e.get("inputs", {})
    if not isinstance(inputs, dict) or len(inputs) > MAX_INPUTS:
        out.append(f"{where}.inputs: an object of up to {MAX_INPUTS} inputs")
        inputs = {}
    for k, spec in inputs.items():
        out += check_input(k, spec, f"{where}.inputs")
    call = e.get("call") if isinstance(e.get("call"), dict) else {}
    if "form" in call and isinstance(call["form"], dict) and isinstance(call["form"].get("fields"), dict):
        for wname, fill in call["form"]["fields"].items():
            if isinstance(fill, dict) and "input" in fill and fill["input"] not in inputs:
                out.append(f"{where}.call.form.fields.{wname}: input {str(fill['input'])[:40]} is not an input of this entry")
            if isinstance(fill, dict) and "value" in fill and not (fill["value"] is None or isinstance(fill["value"], (bool, str)) and len(str(fill["value"])) <= 200
                                                                     or _num(fill["value"])):
                out.append(f"{where}.call.form.fields.{wname}.value: a number, string or boolean")
    if "function" in call and isinstance(call["function"], dict) and call["function"].get("document") in inputs:
        out.append(f"{where}.call.function.document: {call['function']['document']} is an input too")
    out += check_preconditions_spec(e.get("preconditions", {}), f"{where}.preconditions")
    out += check_result_spec(e.get("result"), f"{where}.result")
    tree = e.get("tree")
    if lv == 3 and not tree:
        out.append(f"{where}.tree: a level 3 entry has branches")
    if tree is not None:
        if not isinstance(tree, list) or not 1 <= len(tree) <= MAX_BRANCHES:
            out.append(f"{where}.tree: a list of 1 to {MAX_BRANCHES} branches")
        else:
            for i, b in enumerate(tree):
                w = f"{where}.tree[{i}]"
                if not isinstance(b, dict) or set(b) - {"when", "next", "say", "needs"} or "next" not in b:
                    out.append(f"{w}: {{when, next, say, needs}}")
                    continue
                if "when" in b:
                    out += check_cond(b["when"], inputs, f"{w}.when")
                if b["next"] != "stop" and (not isinstance(b["next"], str) or b["next"] not in names):
                    out.append(f"{w}.next: an entry of this cookbook, or stop")
                if b["next"] == name:
                    out.append(f"{w}.next: a branch never leads to its own entry")
                if "say" in b:
                    out += _line(b["say"], MAX_SAY, f"{w}.say")
                if "needs" in b and not (isinstance(b["needs"], list) and len(b["needs"]) <= 12 and all(isinstance(x, str) and len(x) <= 80 for x in b["needs"])):
                    out.append(f"{w}.needs: a list of up to 12 short words")
    if "risk" in e and e["risk"] not in RISKS:
        out.append(f"{where}.risk: none, file or code")
    p = e.get("probe")
    if p is not None and (not isinstance(p, dict) or set(p) - {"version", "result", "date", "why"} or p.get("result") not in ("pass", "fail", "skip")):
        out.append(f"{where}.probe: {{version, result (pass, fail, skip), date, why}}")
    s = e.get("source")
    if s is not None and (not isinstance(s, dict) or set(s) - {"from", "checked"} or s.get("from") not in ("code", "docs", "live")
                          or not isinstance(s.get("checked", False), bool)):
        out.append(f"{where}.source: {{from (code, docs, live), checked (true, false)}}")
    if lv == 5:
        out += _line(e.get("blocker"), MAX_BLOCKER, f"{where}.blocker")
    elif "blocker" in e:
        out.append(f"{where}.blocker: for a level 5 entry only")
    if "notes" in e and not (isinstance(e["notes"], list) and len(e["notes"]) <= 12 and all(isinstance(x, str) and len(x) <= 200 for x in e["notes"])):
        out.append(f"{where}.notes: a list of up to 12 short lines")
    return out


def check_preconditions_spec(pre, where):
    if pre in (None, {}):
        return []
    if not isinstance(pre, dict) or set(pre) - {"workbench", "document", "selection", "objects"}:
        return [f"{where}: {{workbench, document, selection, objects}}"]
    out = []
    if "workbench" in pre and not (isinstance(pre["workbench"], str) and COMMAND_RE.match(pre["workbench"])):
        out.append(f"{where}.workbench: a workbench class name")
    if pre.get("document", "any") not in ("open", "none", "any"):
        out.append(f"{where}.document: open, none or any")
    s = pre.get("selection")
    if s is not None and (not isinstance(s, dict) or set(s) - {"kind", "min", "max"} or s.get("kind", "any") not in (set(PICKS) | {"any"})
                          or not all(isinstance(s.get(k, 0), int) and not isinstance(s.get(k), bool) and 0 <= s.get(k, 0) <= MAX_LIST for k in ("min", "max"))):
        out.append(f"{where}.selection: {{kind, min, max}}")
    o = pre.get("objects")
    if o is not None and (not isinstance(o, dict) or set(o) - {"type", "min"} or not (isinstance(o.get("type"), str) and re.match(r"^[A-Za-z]+::[A-Za-z0-9]+$", o["type"]))
                          or not isinstance(o.get("min", 1), int)):
        out.append(f"{where}.objects: {{type (Part::Feature), min}}")
    return out


def check_result_spec(r, where):
    if r is None:
        return []
    if not isinstance(r, dict) or set(r) - {"makes", "check"}:
        return [f"{where}: {{makes, check}}"]
    out = []
    if "makes" in r:
        out += _line(r["makes"], 200, f"{where}.makes")
    c = r.get("check")
    if c is not None:
        if not isinstance(c, dict) or set(c) - CHECKS:
            return out + [f"{where}.check: {{{', '.join(sorted(CHECKS))}}}"]
        for k in ("newObjects", "changedObjects"):
            if k in c and (not isinstance(c[k], dict) or set(c[k]) - {"min", "type"} or not isinstance(c[k].get("min", 1), int)
                           or "type" in c[k] and not (isinstance(c[k]["type"], str) and re.match(r"^[A-Za-z]+::[A-Za-z0-9]+$", c[k]["type"]))):
                out.append(f"{where}.check.{k}: {{min, type}}")
        if "returns" in c and c["returns"] not in ("number", "string", "boolean", "object", "list", "dict", "none"):
            out.append(f"{where}.check.returns: number, string, boolean, object, list, dict or none")
        if "valid" in c and c["valid"] is not True:
            out.append(f"{where}.check.valid: true")
    return out


def check(doc, tool_names=(), blocked_package=None):
    """What is wrong with a v2 cookbook, as a list ([] when fine)."""
    out = []
    addon = doc.get("addon")
    package = None
    if not isinstance(addon, dict) or set(addon) - {"package", "name", "version", "workbench", "licence", "license", "credit"}:
        out.append("addon: {package, name, version, workbench, licence, credit}")
    else:
        package = addon.get("package")
        if package is not None and (not isinstance(package, str) or not MODULE_RE.match(package) or "." in package or package.startswith("_")
                                    or (blocked_package and blocked_package(package))):
            out.append("addon.package: the add-on's top package name (not the standard library, FreeCAD or Agent Link)")
            package = None
        if "workbench" in addon and not (isinstance(addon["workbench"], str) and COMMAND_RE.match(addon["workbench"])):
            out.append("addon.workbench: the add-on's workbench class name (MineWorkbench)")
        if "version" in addon and not (isinstance(addon["version"], str) and VERSION_RE.match(addon["version"])):
            out.append("addon.version: the add-on's version (1.2.0)")
        for k in ("name", "credit", "licence", "license"):
            if k in addon:
                out += _line(addon[k], 200, f"addon.{k}")
    if "coverage" in doc and not isinstance(doc["coverage"], dict):
        out.append("coverage: an object (Agent Link measures it again)")
    ents = doc.get("entries")
    if not isinstance(ents, dict) or not ents:
        return out + ["entries: an object of entries by name"]
    taken = set(tool_names)
    for name, e in ents.items():
        if not isinstance(name, str) or not NAME_RE.match(name):
            out.append(f"{str(name)[:48]!r}: names are lower_case, 2 to 48 characters")
            continue
        if name in taken:
            out.append(f"{name}: a tool has this name already; an entry never takes a tool's name")
        out += check_entry(name, e, package, set(ents))
    return out


# ---- inputs ----------------------------------------------------------------------------------

def coerce(name, spec, v):
    """The value of one input, checked against its type and limits. Raises
    ValueError with the words of the fault."""
    t = spec.get("type")
    if t in NUMBERS:
        if not _num(v):
            raise ValueError(f"{name}: a number" + (f" in {spec['unit']}" if spec.get("unit") else ""))
        if t == "integer" and (not isinstance(v, int) and not float(v).is_integer()):
            raise ValueError(f"{name}: a whole number")
        v = int(v) if t == "integer" else float(v)
        if _num(spec.get("min")) and v < spec["min"]:
            raise ValueError(f"{name}: {v} is less than {spec['min']}" + (f" {spec['unit']}" if spec.get("unit") else ""))
        if _num(spec.get("max")) and v > spec["max"]:
            raise ValueError(f"{name}: {v} is more than {spec['max']}" + (f" {spec['unit']}" if spec.get("unit") else ""))
        if abs(v) > 1e9:
            raise ValueError(f"{name}: {v} is out of range")
        return v
    if t == "boolean":
        if not isinstance(v, bool):
            raise ValueError(f"{name}: true or false")
        return v
    if t == "string":
        if not isinstance(v, str):
            raise ValueError(f"{name}: a string")
        cap = spec.get("maxLength", 200)
        if len(v) > cap:
            raise ValueError(f"{name}: {len(v)} characters; {cap} or fewer")
        if any(ord(c) < 32 and c not in "\t" for c in v):
            raise ValueError(f"{name}: one line, no control characters")
        return v
    if t == "choice":
        if isinstance(v, bool) or v not in spec.get("choices", []):
            raise ValueError(f"{name}: one of {', '.join(map(str, spec.get('choices', [])[:20]))}")
        return v
    if t == "vector":
        if not isinstance(v, list) or len(v) != 3 or not all(_num(x) and abs(x) <= 1e9 for x in v):
            raise ValueError(f"{name}: [x, y, z], three numbers")
        return [float(x) for x in v]
    if t == "list":
        lo, hi = spec.get("count", [0, MAX_LIST])
        if not isinstance(v, list) or not lo <= len(v) <= hi:
            raise ValueError(f"{name}: a list of {lo} to {hi} items")
        it = spec.get("items", {"type": "number"})
        return [coerce(f"{name}[{i}]", it, x) for i, x in enumerate(v)]
    if t in PICKS:
        refs = v if isinstance(v, list) else [v]
        lo, hi = spec.get("count", [1, 1])
        if not lo <= len(refs) <= hi:
            raise ValueError(f"{name}: {lo} to {hi} picks")
        sub = PICKS[t]
        for r in refs:
            if not isinstance(r, str) or not REF_RE.match(r):
                raise ValueError(f"{name}: a pick like \"Box.Face3\" (object name, then Face, Edge or Vertex and a number)")
            if sub and not r.split(".", 1)[-1].startswith(sub) or not sub and "." in r:
                want = f"\"Object.{sub}N\"" if sub else "an object name with no sub-element"
                raise ValueError(f"{name}: {r}: a {t} pick is {want}")
        return refs if isinstance(v, list) else refs[0]
    raise ValueError(f"{name}: unknown type {t}")


def check_inputs(inputs, args):
    """The checked values of args against the entry's inputs: types, limits,
    defaults, required. Raises ValueError."""
    if not isinstance(args, dict):
        raise ValueError("args: an object of the entry's inputs")
    inputs = inputs or {}
    extra = sorted(set(args) - set(inputs))
    if extra:
        raise ValueError(f"args: {', '.join(extra[:8])} not in this entry's inputs ({', '.join(inputs) or 'none'})")
    out = {}
    for k, spec in inputs.items():
        if k in args:
            out[k] = coerce(k, spec, args[k])
        elif "default" in spec:
            out[k] = coerce(k, spec, spec["default"])
        elif spec.get("required", True):
            raise ValueError(f"args.{k}: necessary for this entry ({spec.get('type')})")
    return out


def picks_of(inputs, values):
    """[(kind, ref)] of the pick inputs, for the selection precondition."""
    out = []
    for k, spec in (inputs or {}).items():
        if spec.get("type") in PICKS and k in values:
            for r in values[k] if isinstance(values[k], list) else [values[k]]:
                out.append((spec["type"], r))
    return out


# ---- preconditions, conditions, results -------------------------------------------------------

def unmet(pre, state):
    """The preconditions not met, as words. state: {document: bool,
    workbench: name or None, workbenches: [names] or None, selection:
    [(kind, ref)], types: {TypeId: n}}."""
    pre = pre or {}
    out = []
    doc = pre.get("document", "any")
    if doc == "open" and not state.get("document"):
        out.append("a document must be open: doc_new or doc_open first")
    if doc == "none" and state.get("document"):
        out.append("no document may be open")
    s = pre.get("selection")
    if s:
        kind = s.get("kind", "any")
        n = sum(1 for k, _r in state.get("selection", []) if kind == "any" or k == kind or kind in ("object", "body") and k in ("object", "body"))
        lo, hi = s.get("min", 0), s.get("max", MAX_LIST)
        if not lo <= n <= hi:
            what = f"{kind} picks" if kind != "any" else "picks"
            out.append(f"the entry needs {lo} to {hi} {what}; there are {n}")
    o = pre.get("objects")
    if o:
        n = sum(v for t, v in (state.get("types") or {}).items() if t == o["type"])
        if n < o.get("min", 1):
            out.append(f"the document needs {o.get('min', 1)} or more {o['type']} objects; it has {n}")
    return out


def _cmp(op, a, b):
    try:
        if op == "eq":
            return a == b
        if op == "ne":
            return a != b
        if op == "in":
            return a in b
        if not (_num(a) and _num(b)):
            return False
        return {"lt": a < b, "le": a <= b, "gt": a > b, "ge": a >= b}[op]
    except (TypeError, KeyError):
        return False


def holds(c, values, selection, depth=0):
    """A data condition, evaluated: compare a value, count a selection."""
    if depth > MAX_DEPTH or not isinstance(c, dict):
        return False
    if "all" in c:
        return all(holds(x, values, selection, depth + 1) for x in c["all"])
    if "any" in c:
        return any(holds(x, values, selection, depth + 1) for x in c["any"])
    if "not" in c:
        return not holds(c["not"], values, selection, depth + 1)
    if "input" in c:
        return _cmp(c["op"], values.get(c["input"]), c["value"])
    if "selection" in c:
        s = c["selection"]
        kind = s.get("kind", "any")
        n = sum(1 for k, _r in selection if kind == "any" or k == kind)
        return _cmp(s.get("op", "ge"), n, s.get("value", 1))
    return False


def choose(tree, values, selection):
    """The first branch whose condition holds (a branch with no when always
    holds), or None."""
    for b in tree or []:
        if "when" not in b or holds(b["when"], values, selection):
            return b
    return None


def result_faults(check, before, after, returned):
    """What the result check finds wrong ([] when it worked). before and
    after: {name: {type, touched?, valid?}} of the document's objects."""
    if not check:
        return []
    out = []
    new = [n for n in after if n not in before]
    if "newObjects" in check:
        c = check["newObjects"]
        got = [n for n in new if "type" not in c or after[n].get("type") == c["type"]]
        if len(got) < c.get("min", 1):
            out.append(f"it made {len(got)} new {c.get('type', 'objects')}; {c.get('min', 1)} or more expected")
    if "changedObjects" in check:
        ch = [n for n in after if n in before and after[n] != before[n]] + new
        if len(ch) < check["changedObjects"].get("min", 1):
            out.append(f"it changed {len(ch)} objects; {check['changedObjects'].get('min', 1)} or more expected")
    if "returns" in check:
        t = check["returns"]
        ok = {"none": returned is None, "number": _num(returned), "string": isinstance(returned, str), "boolean": isinstance(returned, bool),
              "list": isinstance(returned, list), "dict": isinstance(returned, dict), "object": returned is not None and not isinstance(returned, (bool, int, float, str, list, dict))}
        if not ok.get(t, False) and not (t == "object" and isinstance(returned, str)):
            out.append(f"it returned {type(returned).__name__}; {t} expected")
    if check.get("valid"):
        bad = [n for n in new if after[n].get("valid") is False]
        if bad:
            out.append(f"shapes not valid: {', '.join(bad[:6])}")
    return out


# ---- what Agent Link works out -----------------------------------------------------------------

def coverage(doc, probes=None, version=None):
    """Counts per level, measured: declared (the entries) and proven (a
    pass of Agent Link's own probe at the add-on's version)."""
    probes = probes or {}
    version = version if version is not None else (doc.get("addon") or {}).get("version")
    declared = {LEVELS[k]: 0 for k in LEVELS}
    proven = {LEVELS[k]: 0 for k in LEVELS}
    for name, e in (doc.get("entries") or {}).items():
        lv = e.get("level") if isinstance(e, dict) else None
        if lv not in LEVELS:
            continue
        declared[LEVELS[lv]] += 1
        p = probes.get(name)
        if lv != 5 and isinstance(p, dict) and p.get("result") == "pass" and (version is None or p.get("version") == version):
            proven[LEVELS[lv]] += 1
    total = sum(declared.values())
    return {"total": total, "declared": declared, "proven": proven, "bars": bars(declared, proven, total)}


def bars(declared, proven, total, width=20):
    out = []
    for k in LEVELS.values():
        d, p = declared.get(k, 0), proven.get(k, 0)
        frac = d / total if total else 0
        fill = round(frac * width)
        pf = round((p / total if total else 0) * width)
        bar = "#" * pf + "+" * max(0, fill - pf) + "." * (width - fill)
        out.append(f"{k:<14}[{bar}] {d:>3} ({round(frac * 100):>3} %), proven {p}")
    return out


def retry_due(e, version):
    """A level 5 entry is tried again on a new add-on version."""
    p = e.get("probe") if isinstance(e, dict) else None
    return e.get("level") == 5 and (not isinstance(p, dict) or p.get("version") != version)


def today():
    return datetime.date.today().isoformat()
