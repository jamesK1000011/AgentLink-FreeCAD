# SPDX-License-Identifier: LGPL-2.1-or-later
# Vocabulary renames of 24 Nov (rule R5: a renamed field keeps no alias).
# Per renamed field: the card has the new name and not the old; a call with
# the old name is refused like any unknown field; the tool's steps read the
# new name; protocol.py and fastpath.py keep no fallback for the old name;
# and the new name runs on the data tests' stand-in FreeCAD (a child
# process each: the stand-in must not be seen by the other tests).
#   set 4  pd_helix, pd_loft, pd_pipe: profile -> sketch
#   set 7  pd_linear_pattern, pd_polar_pattern: occurrences -> count
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

# (tool, old name, new name)
RENAMED = [
    ("pd_helix", "profile", "sketch"),
    ("pd_loft", "profile", "sketch"),
    ("pd_pipe", "profile", "sketch"),
    ("pd_linear_pattern", "occurrences", "count"),
    ("pd_polar_pattern", "occurrences", "count"),
]

# One case of each tool that answers, from the data tests' cases: (stand-in
# prefix, the case's name). Its arguments are given with the new names.
RUNS = {
    "pd_helix": ("sk2", "model call 75"),
    "pd_loft": ("pd", "model call 83"),
    "pd_pipe": ("pd", "model call 89"),
    "pd_linear_pattern": ("pd", "model call 26"),
    "pd_polar_pattern": ("pd", "model call 57"),
}


def _entries():
    with open(os.path.join(ROOT, "agentlink", "data", "tools.json"), encoding="utf-8") as f:
        return json.load(f)["entries"]


def _valid_args(schema, new):
    """The fewest arguments the card takes: each required field, a value of
    its type."""
    props = schema.get("properties") or {}
    out = {}
    for k in schema.get("required") or []:
        t = (props.get(k) or {}).get("type")
        t = t[0] if isinstance(t, list) else t
        out[k] = {"array": ["A"], "integer": 2, "number": 1.0, "boolean": True, "object": {}}.get(t, "A")
    return out


class OldNamesRefused(unittest.TestCase):
    def test_the_card_has_the_new_name_only(self):
        e = _entries()
        for tool, old, new in RENAMED:
            props = e[tool]["inputSchema"]["properties"]
            self.assertIn(new, props, tool)
            self.assertNotIn(old, props, tool)
            self.assertNotIn(old, e[tool]["inputSchema"].get("required", []), tool)

    def test_a_call_with_the_old_name_is_refused_by_name(self):
        from agentlink import protocol

        e = _entries()
        for tool, old, new in RENAMED:
            schema = e[tool]["inputSchema"]
            args = _valid_args(schema, new)
            args.pop(new, None)
            args[old] = "A"
            with self.assertRaises(protocol.ToolError) as cm:
                protocol.check_input(schema, args, tool)
            self.assertIn(f"input.{old}: not a known field", cm.exception.message, tool)
            self.assertIn(new, cm.exception.message, tool)
            # The new name passes the check.
            ok = _valid_args(schema, new)
            protocol.check_input(schema, ok, tool)

    def test_the_steps_read_the_new_name(self):
        e = _entries()
        for tool, old, new in RENAMED:
            text = json.dumps({k: e[tool].get(k) for k in ("rules", "steps", "answer", "args")})
            for form in (f"a.{old})", f"a.{old},", f"a.{old} ", f"a.get('{old}'", f'a.get(\\"{old}\\"'):
                self.assertNotIn(form, text, f"{tool}: {form}")
            self.assertTrue(f"a.{new}" in text or f"a.get('{new}'" in text, tool)

    def test_no_alias_is_left_for_the_old_names(self):
        from agentlink import fastpath, protocol

        for tool, old, new in RENAMED:
            self.assertNotIn(old, protocol.FIELD_ALIASES.get(tool, {}), tool)
            self.assertNotIn(old, protocol.GOES_WITH.get(tool, {}), tool)
            self.assertNotIn(old, protocol.SYNONYMS.get(new, ()), tool)
        # profile no longer fills from the session's sketch (the PartDesign tools take sketch)
        self.assertNotIn("profile", fastpath.REQUIRED_FROM)


CHILD = r'''
import importlib, json, os, sys, tempfile
root, prefix, tool, case_name, files = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5].split(",")
sys.path.insert(0, root); sys.path.insert(0, os.path.join(root, "tests"))
import _meant
standin = importlib.import_module(f"_data{prefix}_standin")
cases = importlib.import_module(f"_data{prefix}_cases")
fc = standin.install()
from agentlink.protocol import ToolError
fc.patch()
mods = {m: importlib.import_module(f"agentlink.families.{m}") for m in files}
try:
    cs = cases.cases(fc, tempfile.mkdtemp(), mods, mods)
except TypeError:
    cs = cases.cases(fc, tempfile.mkdtemp())
hit = [(p, a) for t, c, p, a in cs if t == tool and c == case_name]
prepare, args = hit[0]
fc.state["flags"] = {}
s = fc.Session(tempfile.mkdtemp())
prepare(s)
t = [x for m in files for x in mods[m].tools(s) if x.name == tool][0]
new = _meant.args_as_meant(tool, args)
from agentlink import protocol
try:
    call = json.loads(json.dumps(new))
    protocol.check_input(t.schema, call, tool)  # as a call to the server: the card's fields only
    res = ["ok", t.fn(call)]
except ToolError as e:
    res = ["refused", e.code, e.message]
print(json.dumps({"args": new, "result": res}, default=repr))
'''

FILES = {"pd": "feature,std_more,sketch"}


def _run(tool):
    prefix, case = RUNS[tool]
    files = FILES.get(prefix)
    if files is None:
        mod = __import__(f"_data{prefix}_cases")
        files = ",".join(mod.FILES)
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(CHILD)
    try:
        r = subprocess.run([sys.executable, f.name, ROOT, prefix, tool, case, files], capture_output=True, text=True, timeout=300)
    finally:
        os.unlink(f.name)
    if r.returncode != 0:
        raise AssertionError(f"{tool}: child failed:\n{r.stderr[-3000:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


class NewNamesRun(unittest.TestCase):
    def test_each_tool_answers_with_the_new_name(self):
        for tool in sorted(RUNS):
            with self.subTest(tool=tool):
                got = _run(tool)
                for t, old, new in RENAMED:
                    if t == tool:
                        self.assertIn(new, got["args"], tool)
                        self.assertNotIn(old, got["args"], tool)
                self.assertEqual(got["result"][0], "ok", got)


if __name__ == "__main__":
    unittest.main()
