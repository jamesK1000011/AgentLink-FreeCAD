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



# Live: live_run { script: "agentlink" } came back as a bare batch result
# when a gui_input step left a "Note" dialog open (the step typing into it
# never ran); reset failed on doc_close not_found; texturizer was answered
# busy with nothing open.
class FakeWindow:
    """A batch and a window: gui_input with open: true opens a dialog that
    holds its call — its answer goes to the replay (live.push) from inside
    the dialog's loop, and the call returns only once the dialog is closed."""

    def __init__(self, busy_first=0):
        self.cont, self.dialog, self.log, self.batch_now = [], None, [], None
        self.busy_first = busy_first
        self.unstuck = 0

    def call(self, tool, args):
        if tool == "batch":
            mine = {"results": [], "i": 0, "answered": False}
            prev, self.batch_now = self.batch_now, mine
            try:
                for i, c in enumerate(args["calls"]):
                    mine["i"] = i
                    r = self.call(c["tool"], c.get("arguments") or {})
                    if mine["answered"]:
                        return {"tool": "batch", "ok": True, "result": {"results": mine["results"], "answered_early": True}}
                    mine["results"].append(r)
                return {"tool": "batch", "ok": True, "result": {"results": mine["results"]}}
            finally:
                self.batch_now = prev
        self.log.append(tool)
        if tool == "gui_unstick":
            self.dialog = None
            self.unstuck += 1
            return {"tool": tool, "ok": True, "result": {"closed": ["Note"]}}
        if tool == "flaky" and self.busy_first:
            self.busy_first -= 1
            return {"tool": tool, "ok": False, "error": {"code": "busy", "message": "held"}}
        if tool == "doc_close":
            return {"tool": tool, "ok": False, "error": {"code": "not_found", "message": "no such document"}}
        if tool == "gui_input" and args.get("open"):
            self.dialog = "Note"
            body = {"steps": [{"i": 0, "dialog": "Note"}], "open": {"kind": "dialog", "title": "Note"}}
            taken = bool(self.cont) and self.cont[-1]("gui_input", body)
            assert taken, "the replay should take a held gui_input's answer"
            assert self.dialog is None, "the dialog is still open when its loop ends"
            return {"tool": tool, "ok": True, "result": body}
        if tool == "dialog_answer":
            self.dialog = None
            return {"tool": tool, "ok": True, "result": {"pressed": "OK"}}
        return {"tool": tool, "ok": True, "result": {"done": tool}}

    def live(self):
        import types

        return types.SimpleNamespace(push=self.cont.append, pop=self.cont.pop, batch_now=lambda: self.batch_now,
                                     front=lambda: ({"kind": "dialog", "title": self.dialog} if self.dialog else None),
                                     unstick=lambda: self.call("gui_unstick", {"all": True}), sleep=lambda s: None)


class LiveReplay(unittest.TestCase):
    def script(self, steps):
        return {"name": "t", "steps": steps}

    def test_a_dialog_does_not_end_the_replay(self):
        w = FakeWindow()
        sc = self.script([
            {"name": "open the note", "calls": [{"tool": "cmd_run"}, {"tool": "gui_input", "arguments": {"open": True}}, {"tool": "after_in_step"}],
             "expect": [{"call": 1, "path": "result.open.title", "equals": "Note"}, {"call": 2, "path": "result.done", "equals": "after_in_step"}]},
            {"name": "type into it", "calls": [{"tool": "dialog_answer"}], "expect": [{"call": 0, "path": "result.pressed", "equals": "OK"}]},
            {"name": "after", "calls": [{"tool": "session_state"}]},
        ])
        out = ls.run(sc, list(enumerate(sc["steps"])), w.call, live=w.live())
        self.assertEqual(out["total"], {"passed": 3, "failed": 0, "skipped": 0, "run": 3}, out)
        self.assertEqual([s["step"] for s in out["steps"]], [0, 1, 2])
        self.assertIn("dialog", out["steps"][0])
        self.assertNotIn("leftOpen", out)
        self.assertEqual(w.log, ["cmd_run", "gui_input", "after_in_step", "dialog_answer", "session_state"])
        self.assertEqual(w.cont, [])

    def test_left_open_is_closed_and_said(self):
        w = FakeWindow()
        sc = self.script([{"name": "open", "calls": [{"tool": "gui_input", "arguments": {"open": True}}]}, {"name": "next", "calls": [{"tool": "x"}]}])
        out = ls.run(sc, list(enumerate(sc["steps"])), w.call, live=w.live())
        self.assertEqual(out["total"]["passed"], 2)
        self.assertEqual(out["leftOpen"][0]["open"]["title"], "Note")
        self.assertEqual(w.unstuck, 1)

    def test_direct_step_with_a_dialog(self):
        w = FakeWindow()
        sc = self.script([{"name": "d", "direct": True, "calls": [{"tool": "gui_input", "arguments": {"open": True}}, {"tool": "dialog_answer"}]}])
        out = ls.run(sc, list(enumerate(sc["steps"])), w.call, live=w.live())
        self.assertEqual(out["total"]["passed"], 1, out)
        self.assertEqual(w.log, ["gui_input", "dialog_answer"])

    def test_busy_is_retried_once(self):
        w = FakeWindow(busy_first=1)
        sc = self.script([{"name": "f", "calls": [{"tool": "flaky"}]}])
        out = ls.run(sc, list(enumerate(sc["steps"])), w.call, live=w.live())
        self.assertEqual(out["steps"][0]["result"], "pass", out)
        self.assertIn("retried", out["steps"][0])
        w = FakeWindow(busy_first=2)
        out = ls.run(sc, list(enumerate(sc["steps"])), w.call, live=w.live())
        self.assertEqual(out["steps"][0]["result"], "fail")

    def test_allowed_refusal(self):
        w = FakeWindow()
        sc = self.script([{"name": "close", "calls": [{"tool": "doc_close", "allow": ["not_found"]}]},
                          {"name": "close strict", "calls": [{"tool": "doc_close"}]}])
        out = ls.run(sc, list(enumerate(sc["steps"])), w.call, live=w.live())
        self.assertEqual([s["result"] for s in out["steps"]], ["pass", "fail"])
        self.assertEqual(out["steps"][0]["allowedRefusals"][0]["error"]["code"], "not_found")

    def test_reset_allows_closing_what_is_not_open(self):
        with open(os.path.join(ROOT, "scripts", "live", "reset.json")) as f:
            d = json.load(f)
        closes = [c for st in d["steps"] for c in st["calls"] if c["tool"] == "doc_close"]
        self.assertTrue(closes and all("not_found" in c.get("allow", []) for c in closes))


class LinkDeadlines(unittest.TestCase):
    def test_a_finished_gui_input_lifts_its_deadline_and_progress_holds_nothing(self):
        import types

        import agentlink_state

        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from test_gui_link_dialog import gui_link

        link = gui_link.Link.__new__(gui_link.Link)
        link.calls = [{"id": 1, "name": "batch", "answered": False}]
        link.session = types.SimpleNamespace(live_now=None)
        old = getattr(agentlink_state, "link", None)
        agentlink_state.link = link
        try:
            link.expect = types.MethodType(lambda self, tool, sec: self.calls[-1].update(deadline=1.0, expected=tool), link)
            gui_link.expect("gui_input", 3)
            self.assertIn("deadline", link.calls[-1])
            self.assertIsNotNone(link._stuck())  # past it: busy
            gui_link.expect_done("gui_input")
            self.assertNotIn("deadline", link.calls[-1])
            self.assertIsNone(link._stuck())
            link.front = {"kind": "progress", "title": "Texturing"}
            self.assertIsNone(link._stuck())
            # inside a live_run its own gui_input sets no client deadline
            link.session.live_now = True
            gui_link.expect("gui_input", 3)
            self.assertNotIn("deadline", link.calls[-1])
        finally:
            agentlink_state.link = old

if __name__ == "__main__":
    unittest.main()
