# SPDX-License-Identifier: LGPL-2.1-or-later
# 25 Nov owner decisions, after the blind QA of small local models (they read
# the top of an ok answer and move on; facts were buried in repeated text):
#  1. the health check runs after every changing step, but its words come
#     only when they differ from the last ones given, or when something is
#     wrong ("nothing new" otherwise); explicit reads keep the full verdict;
#     a feature's answer adds changed: what moved since the body's last
#     reading, right after where;
#  2. the likely-next hints (health next, numbered options) go behind the
#     NextHints preference and AGENTLINK_NEXT_HINTS;
#  3. scripts/next_hint_use.py measures their use from an OpenCode export.
# Plain Python with stand-ins: no FreeCAD here.
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from agentlink import nexthint, once  # noqa: E402
from agentlink.protocol import Tool  # noqa: E402

CLEAN = {"facts": "shape: Body: valid, closed, 1 solid"}


def changing(name="pd_pad"):
    return Tool(name, "d", {"type": "object", "properties": {}}, None, changes=True)


def reading(name="body_check"):
    return Tool(name, "d", {"type": "object", "properties": {}}, None, changes=False)


def answer(h, **more):
    return {"feature": "Pad", "health": dict(h), **more}


class HealthNews(unittest.TestCase):
    def setUp(self):
        self.s = types.SimpleNamespace()

    def test_the_same_clean_health_is_nothing_new(self):
        first = once.thin_reply(self.s, changing(), answer(CLEAN))
        self.assertEqual(first["health"], CLEAN)
        second = once.thin_reply(self.s, changing(), answer({**CLEAN, "ms": 240, "statusBar": "Pad002"}))
        self.assertEqual(second["health"], once.NOTHING_NEW)
        self.assertLess(len(json.dumps(second)), len(json.dumps(first)))

    def test_sketch_and_feature_calls_in_turn_are_quiet_per_subject(self):
        # live, 25 Nov: sketch, pad, sketch, pad in one batch; one "last given"
        # never matched, so every answer repeated the whole verdict.
        sk = {"facts": "solver: Sketch 2: 4 DoF left on the start of lines 0, 1, 2, 3"}
        once.thin_reply(self.s, changing(), answer(CLEAN))
        once.thin_reply(self.s, changing("sketch_add"), answer(sk))
        self.assertEqual(once.thin_reply(self.s, changing(), answer(CLEAN))["health"], once.NOTHING_NEW)
        self.assertEqual(once.thin_reply(self.s, changing("sketch_add"), answer(sk))["health"], once.NOTHING_NEW)
        sk3 = {"facts": "solver: Sketch 3: empty"}
        self.assertEqual(once.thin_reply(self.s, changing("sketch_new"), answer(sk3))["health"], sk3)

    def test_a_change_is_given_whole(self):
        once.thin_reply(self.s, changing(), answer(CLEAN))
        two = {"facts": "shape: Body: valid, closed, 2 solids"}
        self.assertEqual(once.thin_reply(self.s, changing(), answer(two))["health"]["facts"], two["facts"])
        # and the new one is then the one last given
        self.assertEqual(once.thin_reply(self.s, changing(), answer(two))["health"], once.NOTHING_NEW)
        task = {**CLEAN, "taskPanel": ["Pad parameters"]}
        self.assertEqual(once.thin_reply(self.s, changing(), answer(task))["health"]["taskPanel"], ["Pad parameters"])

    def test_something_wrong_is_always_given(self):
        bad = {"facts": "window: a dialog is open: Missing link"}
        for _ in range(3):
            h = once.thin_reply(self.s, changing(), answer(bad))["health"]
            self.assertIsInstance(h, dict)
            self.assertIn("a dialog is open", h["facts"])
        failed = {"facts": "the health check did not run (KeyError: x)"}
        for _ in range(2):
            self.assertIsInstance(once.thin_reply(self.s, changing(), answer(failed))["health"], dict)

    def test_explicit_reads_keep_the_full_verdict(self):
        once.thin_reply(self.s, changing(), answer(CLEAN))
        for _ in range(2):
            self.assertEqual(once.thin_reply(self.s, reading(), answer(CLEAN))["health"], CLEAN)

    def test_the_lines_beside_it_move_to_the_answer(self):
        once.thin_reply(self.s, changing(), answer(CLEAN))
        got = once.thin_reply(self.s, changing(), answer({**CLEAN, "options": "step 3: 1 pd_pocket", "appliesNow": {"groups": {"pd": 3}}}))
        self.assertEqual(got["health"], once.NOTHING_NEW)
        self.assertEqual(got["options"], "step 3: 1 pd_pocket")
        self.assertEqual(got["appliesNow"], {"groups": {"pd": 3}})

    def test_a_new_conversation_says_it_again(self):
        once.thin_reply(self.s, changing(), answer(CLEAN))
        once.reset(self.s)
        self.assertEqual(once.thin_reply(self.s, changing(), answer(CLEAN))["health"], CLEAN)

    def test_the_check_still_runs_after_every_change(self):
        # Only the reporting changed: health.attach runs on every changing
        # call (protocol._with_health), and quiet_health reads its finding.
        with open(os.path.join(ROOT, "agentlink", "protocol.py"), encoding="utf-8") as f:
            src = f.read()
        body = src[src.index("def _with_health("):src.index("class ToolError")]
        self.assertIn("health.attach(session, tool, m, out, args)", body)
        with open(os.path.join(ROOT, "agentlink", "health.py"), encoding="utf-8") as f:
            self.assertNotIn("NOTHING_NEW", f.read())


CHILD = '''
import json, sys
sys.path.insert(0, %r); sys.path.insert(0, %r)
import _datapd_standin
fc = _datapd_standin.install()
fc.patch()
import types
from agentlink.families import pd_common as pc
s = types.SimpleNamespace()
body = types.SimpleNamespace(Name="Body", Label="Body", Document=types.SimpleNamespace(Name="D"))
first = {"feature": "Pad", "type": "Pad", "where": "added x 0..30", "valid": True, "body": "Body", "volume": 750.0, "faces": 6, "solids": 1,
         "box": [30, 5, 5], "bounds": "x 0..30, y 0..5, z 0..5", "volumeChange": 750.0}
a = pc.with_changed(s, body, dict(first), 0.0)
second = {"feature": "Pad001", "type": "Pad", "where": "added x 0..5, z 5..40", "valid": True, "body": "Body", "volume": 6000.0, "faces": 14,
          "solids": 1, "box": [30, 5, 40], "bounds": "x 0..30, y 0..5, z 0..40", "volumeChange": 5250.0}
b = pc.with_changed(s, body, dict(second), 750.0)
c = pc.with_changed(s, body, dict(second, feature="Pad002"), 100.0)   # the body changed another way since
print(json.dumps({"a": a, "b": b, "bkeys": list(b), "c": c}))
''' % (ROOT, HERE)


class Changed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r = subprocess.run([sys.executable, "-c", CHILD], capture_output=True, text=True, timeout=120, cwd=HERE)
        if r.returncode != 0:
            raise AssertionError(r.stderr[-3000:])
        cls.got = json.loads(r.stdout.strip().splitlines()[-1])

    def test_no_line_on_the_first_reading(self):
        self.assertNotIn("changed", self.got["a"])

    def test_the_line_says_what_moved_right_after_where(self):
        self.assertEqual(self.got["b"]["changed"], "volume +5250, box z 5→40, faces 6→14")
        self.assertEqual(self.got["bkeys"][:4], ["feature", "type", "where", "changed"])
        for k in ("volume", "faces", "solids", "box", "bounds", "volumeChange"):  # the full fields stay
            self.assertIn(k, self.got["b"])

    def test_no_line_when_the_body_changed_another_way(self):
        self.assertNotIn("changed", self.got["c"])


class NextHintsSwitch(unittest.TestCase):
    def setUp(self):
        os.environ.pop(nexthint.ENV, None)
        self.addCleanup(os.environ.pop, nexthint.ENV, None)

    def test_on_by_default_and_off_by_env(self):
        self.assertTrue(nexthint.on())
        os.environ[nexthint.ENV] = "0"
        self.assertFalse(nexthint.on())
        os.environ[nexthint.ENV] = "1"
        self.assertTrue(nexthint.on())

    def test_the_preference(self):
        group = types.SimpleNamespace(GetBool=lambda name, default: False if name == "NextHints" else default)
        fake = types.SimpleNamespace(ParamGet=lambda path: group)
        keep = sys.modules.get("FreeCAD")
        sys.modules["FreeCAD"] = fake
        try:
            self.assertFalse(nexthint.on())
        finally:
            if keep is None:
                sys.modules.pop("FreeCAD", None)
            else:
                sys.modules["FreeCAD"] = keep

    def test_off_gives_no_options_and_no_next(self):
        from test_options import body_with, call, doc_of, facts_reader, make, sketch

        sk = sketch("Sketch")
        s, server = make(doc_of(body_with("Body", sk), sk))
        facts_reader(self, s)
        got, _ = call(server, "pd_pad", {"length": 3})
        self.assertIn("options", got["health"])
        os.environ[nexthint.ENV] = "0"
        for _ in range(2):
            got, _ = call(server, "pd_pad", {"length": 3})
            self.assertNotIn("options", got)
            self.assertNotIn("options", got["health"] if isinstance(got["health"], dict) else {})
        got, _ = call(server, "session_state", {})
        self.assertNotIn("options", got)

    def test_the_health_and_session_state_read_the_switch(self):
        with open(os.path.join(ROOT, "agentlink", "health.py"), encoding="utf-8") as f:
            src = f.read()
        step = src[src.index("# 7. What the window is in the middle of"):src.index('_last["fault"] = bool(red)')]
        self.assertIn("nexthint.on()", step)
        with open(os.path.join(ROOT, "agentlink", "tools.py"), encoding="utf-8") as f:
            src = f.read()
        body = src[src.index("def next_state(session):"):src.index("def _modal_up(")]
        self.assertIn("nexthint.on()", body)

    def test_documented(self):
        with open(os.path.join(ROOT, "SETUP.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn(nexthint.ENV, text)
        self.assertIn(nexthint.PREF, text)


def tool_part(tool, inp, out, status="completed"):
    return {"type": "tool", "tool": tool, "callID": "c", "state": {"status": status, "input": inp, "output": json.dumps(out)}}


SESSION = {"info": {"id": "ses_x"}, "messages": [
    {"info": {"role": "assistant"}, "parts": [
        {"type": "text", "text": "I start."},
        tool_part("agentlink-freecad_sketch_new", {"plane": "XY"}, {"sketch": "Sketch", "health": {"facts": "recompute: FreeCAD reports no recompute error",
                                                  "next": "sketch Sketch is open in edit, 4 DoF left; likely next: sketch_add (draw the outline, a box), sketch_constrain (fix it); workbench Sketcher"}}),
        tool_part("agentlink-freecad_sketch_add", {"shapes": []}, {"added": 4, "health": {"facts": "recompute: FreeCAD reports no recompute error", "options": "step 2: 1 pd_pad sketch=Sketch ask length mm; 2 pd_pocket sketch=Sketch"}}),
    ]},
    {"info": {"role": "assistant"}, "parts": [
        tool_part("agentlink-freecad_pd_pad", {"length": 5}, {"error": {"code": "invalid_input", "message": "length: a number"}}),
        tool_part("agentlink-freecad_pd_pad", {"length": 5}, {"feature": "Pad", "health": "nothing new", "options": "step 3: 1 pd_fillet edges=?"}),
        tool_part("agentlink-freecad_batch", {"calls": [{"tool": "pick", "arguments": {"option": 1}}]}, {"results": [{"ok": True}]}),
        tool_part("agentlink-freecad_session_state", {}, {"options": {"step": 4, "list": [{"n": 1, "tool": "pd_chamfer"}]}}),
        tool_part("agentlink-freecad_view_fit", {}, {"ok": True}),
    ]},
]}


class NextHintUse(unittest.TestCase):
    def test_counts_a_tiny_session(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import next_hint_use

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "session.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(SESSION, f)
            with open(path, encoding="utf-8") as f:
                got = next_hint_use.measure(json.load(f))
            self.assertEqual(next_hint_use.main([path, "--json"]), 0)
        # offered: sketch_new (next), sketch_add (options), the second pd_pad (options), session_state (options)
        # used: sketch_add after sketch_new; pd_pad after sketch_add (refused: not first try); batch of pick after pd_pad
        self.assertEqual(got, {"calls": 7, "offered": 4, "used": 3, "firstTry": 2})

    def test_the_parsers(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import next_hint_use as u

        self.assertEqual(u.likely_tools("a dialog is in front; likely next: pd_pad (a closed sketch, no feature), pd_pocket; workbench X"), ["pd_pad", "pd_pocket"])
        self.assertEqual(u.option_tools("step 7: 1 pd_pad sketch=Sketch; 2 pd_hole d=5"), ["pd_pad", "pd_hole"])
        self.assertEqual(u.tool_parts({"messages": [{"parts": [{"type": "text"}, {"type": "tool", "tool": "x", "state": {"input": "{bad"}}]}]})[0]["input"], {})
        self.assertEqual(u.measure([]), {"calls": 0, "offered": 0, "used": 0, "firstTry": 0})


if __name__ == "__main__":
    unittest.main()
