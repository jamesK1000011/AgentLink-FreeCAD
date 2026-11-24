# SPDX-License-Identifier: LGPL-2.1-or-later
# Part Design renames of 24 Nov (rule R5: a renamed field keeps no alias).
# Set 3: pd_pad and pd_pocket type -> extent, upToFace -> face. A call with
# an old name is refused like any unknown field; the new names work, on the
# stand-in FreeCAD (tests/_datapd_standin.py, in a process of its own).
import json
import os
import subprocess
import sys
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from agentlink import protocol, runners  # noqa: E402
from agentlink.protocol import ToolError  # noqa: E402

RUN = '''
import json, sys, tempfile
sys.path.insert(0, %r); sys.path.insert(0, %r)
import _datapd_standin
fc = _datapd_standin.install()
fc.patch()
from agentlink.families import feature
from agentlink.protocol import ToolError

def padded(s):
    b = fc.body(s)
    sk = fc.sketch(s, b, "Sketch")
    fc.feature(s, b, "Pad", Profile=sk, Length=10.0)
    fc.sketch(s, b, "Top", geometry=("Circle",), dof=2)
    fc.feature(s, b, "Plane", "Mid")
    fc.settle(s)

def call(tool, args):
    del fc.trace[:]
    fc.state["flags"] = {}
    s = fc.Session(tempfile.mkdtemp())
    padded(s)
    t = [t for t in feature.tools(s) if t.name == tool][0]
    try:
        return ["ok", t.fn(args), list(fc.trace)]
    except ToolError as e:
        return ["refused", e.code, e.message]
'''


def run(body):
    code = RUN % (ROOT, HERE) + textwrap.dedent(body)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise AssertionError(r.stderr[-3000:])
    return json.loads(r.stdout.strip().splitlines()[-1])


def schema(tool):
    return runners.entries()[tool]["inputSchema"]


def refused_field(tool, args):
    try:
        protocol.check_input(schema(tool), dict(args), tool)
    except ToolError as e:
        return e.message
    return None


class PadPocketExtent(unittest.TestCase):
    def test_the_old_names_are_refused_as_unknown_fields(self):
        for tool in ("pd_pad", "pd_pocket"):
            props = schema(tool)["properties"]
            self.assertIn("extent", props, tool)
            self.assertIn("face", props, tool)
            self.assertNotIn("type", props, tool)
            self.assertNotIn("upToFace", props, tool)
            for old in ({"type": "up_to_first"}, {"upToFace": "Face8"}):
                msg = refused_field(tool, {"sketch": "Top", **old})
                self.assertIsNotNone(msg, (tool, old))
                self.assertIn(f"input.{next(iter(old))}: not a known field", msg)
                self.assertIn("extent", msg)
            self.assertIsNone(refused_field(tool, {"sketch": "Top", "extent": "up_to_face", "face": "Face8"}), tool)
        for table in (protocol.FIELD_ALIASES, protocol.GOES_WITH):
            for tool in ("pd_pad", "pd_pocket"):
                self.assertFalse({"type", "upToFace"} & set(table.get(tool) or {}), tool)

    def test_the_new_names_work(self):
        got = run('''
            print(json.dumps({
                "pad up to first": call("pd_pad", {"sketch": "Top", "extent": "up_to_first"}),
                "pocket through all": call("pd_pocket", {"sketch": "Top", "extent": "through_all"}),
                "pad up to a face": call("pd_pad", {"sketch": "Top", "face": "Body.Face8"}),
                "pocket extent wrong": call("pd_pocket", {"sketch": "Top", "extent": "up_to_last"}),
                "pad face missing": call("pd_pad", {"sketch": "Top", "extent": "up_to_face"}),
            }))
        ''')
        self.assertEqual(got["pad up to first"][0], "ok", got["pad up to first"])
        self.assertIn("Pad001.Type = 'UpToFirst'", got["pad up to first"][2])
        self.assertEqual(got["pocket through all"][0], "ok", got["pocket through all"])
        self.assertIn("Pocket.Type = 'ThroughAll'", got["pocket through all"][2])
        self.assertEqual(got["pad up to a face"][0], "ok", got["pad up to a face"])
        self.assertTrue(any("UpToFace" in ln for ln in got["pad up to a face"][2]), got["pad up to a face"][2])
        self.assertEqual(got["pocket extent wrong"][:2], ["refused", "invalid_input"])
        self.assertTrue(got["pocket extent wrong"][2].startswith("extent 'up_to_last': one of length"), got["pocket extent wrong"])
        self.assertTrue(got["pad face missing"][2].startswith("extent up_to_face: give face — "), got["pad face missing"])

    def test_the_words_say_extent_and_face(self):
        for tool in ("pd_pad", "pd_pocket"):
            e = runners.entries()[tool]
            text = json.dumps(e, ensure_ascii=False)
            self.assertNotIn("upToFace", text.replace("UpToFace", ""), tool)
            self.assertNotIn("a.type", text, tool)
            self.assertIn("extent:", e["description"], tool)
        with open(os.path.join(ROOT, "agentlink", "guides", "feature.md"), encoding="utf-8") as f:
            guide = f.read()
        self.assertIn("- `extent`: `length` (default)", guide)
        self.assertNotIn("upToFace", guide)
        with open(os.path.join(ROOT, "agentlink", "data", "examples.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["entries"]["pd_pocket"]["fill"][0]["what"], "mm: 5 is a worked value; or extent: \"through_all\" in its place")


if __name__ == "__main__":
    unittest.main()
