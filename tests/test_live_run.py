# SPDX-License-Identifier: LGPL-2.1-or-later
# live_run replays a live window script (scripts/live/README.md): the
# expect checks and the path walk against small made-up answers, $names,
# two-role steps skipped, and every shipped script loads and names its
# checks in the kinds the evaluator knows.
import glob
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentlink import livescript as ls  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")

ANS = [
    {"tool": "gui_input", "ok": True, "result": {"steps": [{"selected": ["Pad.Face6"], "hit": {"text": "Pin"}}, {"selected": []}], "as": "person"}},
    {"tool": "report_read", "ok": True, "result": {"lines": ["(qt.qpa.fonts) missing font family \"Sans\" Error", "all fine"], "next": 7}},
    {"tool": "session_state", "ok": True, "result": {"bodies": [{"volume": 24000.0}], "document": "WindowTest", "where": "window"}},
]


class Walk(unittest.TestCase):
    def test_paths(self):
        self.assertEqual(ls.walk(ANS[0], "result.steps.0.selected.0"), ["Pad.Face6"])
        self.assertEqual(ls.walk(ANS[0], "result.steps[-1].selected"), [[]])
        self.assertEqual(ls.walk(ANS[0], "result.steps.-1.selected"), [[]])
        self.assertEqual(ls.walk(ANS[0], "result.steps[*].selected"), [["Pad.Face6"], []])
        self.assertEqual(ls.walk(ANS[0], "result.nope.x"), [])
        self.assertEqual(ls.walk(ANS[0], "result.steps.5"), [])


class Checks(unittest.TestCase):
    def ev(self, *e):
        return ls.evaluate(ANS, list(e))

    def test_each_kind(self):
        r = self.ev({"call": 0, "path": "result.steps.0.selected.0", "equals": "Pad.Face6"},
                    {"call": 2, "path": "result.bodies.0.volume", "equals": 24000},
                    {"call": 0, "path": "result.steps.0.selected", "contains": "Face"},
                    {"call": 0, "path": "result.steps.0.hit.text", "contains": "Pi"},
                    {"call": 2, "path": "result.bodies.0.volume", "atLeast": 23999, "atMost": 24001},
                    {"call": 0, "path": "result.as", "exists": True},
                    {"call": 0, "path": "result.lost", "exists": False},
                    {"call": 1, "path": "result.lines", "noneContain": ["Error"], "ignoreLinesWith": ["(qt.qpa.fonts)"]},
                    {"call": 0, "path": "result.steps[*].selected", "equals": []})
        self.assertTrue(all(c["ok"] for c in r), [c for c in r if not c["ok"]])

    def test_failures_say_path_wanted_and_got(self):
        r = self.ev({"call": 2, "path": "result.document", "equals": "Other"})[0]
        self.assertEqual((r["ok"], r["path"], r["wanted"], r["got"]), (False, "result.document", {"equals": "Other"}, "WindowTest"))
        r = self.ev({"call": 1, "path": "result.lines", "noneContain": ["Error"]})[0]
        self.assertFalse(r["ok"])
        self.assertIn("Sans", r["got"][0])
        r = self.ev({"call": 2, "path": "result.bodies.0.volume", "atMost": 100})[0]
        self.assertFalse(r["ok"])
        r = self.ev({"call": 0, "path": "result.missing", "equals": 1})[0]
        self.assertEqual(r["got"], "(missing)")
        r = self.ev({"call": 9, "path": "result", "equals": 1})[0]
        self.assertFalse(r["ok"])
        self.assertIn("only 3", r["got"])


class Run(unittest.TestCase):
    def script(self):
        return {"name": "t", "conventions": {"$next": "the next of the last answer (0 at first)", "$X,$Y": "pixels read from a shot"},
                "steps": [
                    {"name": "batched", "calls": [{"tool": "a", "arguments": {}}, {"tool": "b", "arguments": {}}],
                     "expect": [{"call": 1, "path": "result.n", "equals": 2}]},
                    {"name": "direct with $next", "direct": True, "calls": [{"tool": "w", "arguments": {"since": "$next"}}],
                     "expect": [{"call": 0, "path": "result.since", "equals": 7}]},
                    {"name": "student", "role": "student", "calls": [{"tool": "gui_input", "arguments": {}}], "expect": []},
                    {"name": "needs pixels", "calls": [{"tool": "gui_input", "arguments": {"steps": [{"click": {"window": ["$X", "$Y"]}}]}}], "expect": []},
                    {"name": "fails", "calls": [{"tool": "a", "arguments": {}}], "expect": [{"call": 0, "path": "result.n", "equals": 5}]},
                ]}

    def fake(self):
        sent = []

        def one(tool, args):
            if tool == "a":
                return {"tool": tool, "ok": True, "result": {"n": 1, "next": 7}}
            if tool == "b":
                return {"tool": tool, "ok": True, "result": {"n": 2}}
            if tool == "w":
                return {"tool": tool, "ok": True, "result": {"since": args["since"], "next": 9}}
            return {"tool": tool, "ok": False, "error": {"code": "not_found"}}

        def call(tool, args):
            sent.append((tool, args))
            if tool == "batch":
                self.assertEqual((args["rollback"], args["stopOnError"]), (False, False))
                return {"tool": "batch", "ok": True, "result": {"results": [one(c["tool"], c["arguments"]) for c in args["calls"]]}}
            return one(tool, args)

        return call, sent

    def test_steps_pass_fail_skip(self):
        call, sent = self.fake()
        sc = self.script()
        out = ls.run(sc, ls.pick_steps(sc["steps"], None), call)
        res = [s["result"] for s in out["steps"]]
        self.assertEqual(res, ["pass", "pass", "skipped", "skipped", "fail"])
        self.assertIn("two agents", out["steps"][2]["why"])
        self.assertIn("$X", out["steps"][3]["why"])
        self.assertEqual(out["steps"][4]["failed"][0]["got"], 1)
        self.assertEqual(out["total"], {"passed": 2, "failed": 1, "skipped": 2, "run": 3})
        self.assertEqual(sent[1], ("w", {"since": 7}))  # $next from the batch's answer
        self.assertEqual(out["vars"]["next"], 7)  # the latest answer with next: the last step's

    def test_vars_given_and_steps_picked(self):
        call, sent = self.fake()
        sc = self.script()
        out = ls.run(sc, ls.pick_steps(sc["steps"], ["needs pixels", 4]), call, {"X": 10, "Y": 20}, stop_on_fail=True)
        # gui_input is refused by the stand-in: the step fails, and the run stops there.
        self.assertEqual([s["result"] for s in out["steps"]], ["fail"])
        self.assertEqual(out["steps"][0]["refused"][0]["tool"], "gui_input")
        self.assertEqual(sent[0][1]["calls"][0]["arguments"]["steps"][0]["click"]["window"], [10, 20])

    def test_find_script(self):
        self.assertTrue(ls.find_script("reset", [ROOT]).endswith("reset.json"))
        self.assertIsNone(ls.find_script("nope", [ROOT]))


class ShippedScripts(unittest.TestCase):
    def test_every_expect_is_a_known_check(self):
        for f in glob.glob(os.path.join(ROOT, "scripts", "live", "*.json")):
            sc = ls.load(f)
            for st in sc["steps"]:
                for e in st.get("expect") or []:
                    self.assertTrue(any(k in e for k in ls.CHECKS), f"{os.path.basename(f)} {st.get('name')}: {json.dumps(e)}")


if __name__ == "__main__":
    unittest.main()
