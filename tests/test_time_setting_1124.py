# SPDX-License-Identifier: LGPL-2.1-or-later
# Decision 7 (24 Nov): the runner passes the run's time limit as a setting,
# AGENTLINK_TIME_LIMIT_MIN (minutes), read at start. The time counts from
# the first tools/call. Set: session_state says "N of M minutes used"; the
# health verdict of a changing answer says "time: N of M minutes used" only
# from half the limit on (24 Nov blind QA: noise before). Not set: nothing shows.
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from agentlink import timelimit  # noqa: E402
from test_local_fixes_1123 import run  # noqa: E402

BODY = '''
    import time
    from agentlink import timelimit
    before = timelimit._first[0]
    call("session_state", {})
    first = timelimit._first[0]
    if first is not None:
        timelimit._first[0] = first - 125      # two minutes and a bit since the first call
    early = tools._time_state()
    early_verdict = call("probe_make", {"name": "E"})[1]["health"]["verdict"]
    if first is not None:
        timelimit._first[0] = first - 965      # sixteen minutes and a bit: past half of 30
    state = tools._time_state()   # session_state's own field (session_state needs FreeCAD's version: not on the stand-in)
    made = call("probe_make", {"name": "A"})[1]
    inside = call("batch", {"calls": [mk("B"), mk("C")]})[1]
    print(json.dumps({"before": before, "started": first is not None, "state": state.get("time"),
                      "early": early.get("time"), "earlyVerdict": early_verdict,
                      "verdict": made["health"]["verdict"], "batch": inside.get("health", {}).get("verdict"),
                      "rows": [r.get("result", {}).get("health", {}).get("verdict") for r in inside.get("results", []) if isinstance(r, dict)]}))
'''


def run_with(env):
    keep = {k: v for k, v in os.environ.items() if k != timelimit.ENV}
    with mock.patch.dict(os.environ, {**keep, **env}, clear=True):
        return run(BODY)


class TimeSet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.got = run_with({timelimit.ENV: "30"})

    def test_counts_from_the_first_call(self):
        self.assertIsNone(self.got["before"])
        self.assertTrue(self.got["started"])

    def test_session_state_shows_it(self):
        self.assertEqual(self.got["early"], "2 of 30 minutes used")
        self.assertEqual(self.got["state"], "16 of 30 minutes used")
        with open(os.path.join(ROOT, "agentlink", "tools.py"), encoding="utf-8") as f:
            src = f.read()
        body = src[src.index("    def session_state(self, a):"):src.index("    def _front_state(self):")]
        self.assertIn("**_time_state(),", body)

    def test_the_health_verdict_shows_it_from_half_the_limit(self):
        self.assertNotIn("time:", self.got["earlyVerdict"])
        self.assertTrue(self.got["verdict"].endswith("; time: 16 of 30 minutes used") or self.got["verdict"] == "time: 16 of 30 minutes used",
                        self.got["verdict"])
        self.assertEqual(self.got["verdict"].count("time:"), 1)

    def test_a_batch_says_it_once(self):
        # On the last call's health only: the batch's answer has no health of its own.
        self.assertIsNone(self.got["batch"])
        self.assertEqual(len(self.got["rows"]), 2)
        self.assertNotIn("time:", self.got["rows"][0])
        self.assertEqual(self.got["rows"][1], "nothing red; time: 16 of 30 minutes used")


class TimeNotSet(unittest.TestCase):
    def test_nothing_shows(self):
        got = run_with({})
        self.assertIsNone(got["state"])
        self.assertNotIn("time:", got["verdict"])
        self.assertNotIn("time:", got["batch"] or "")
        for v in got["rows"]:
            self.assertNotIn("time:", v)


class TheSetting(unittest.TestCase):
    def tearDown(self):
        timelimit.configure("")

    def test_values(self):
        for raw, want in (("30", 30.0), (" 12.5 ", 12.5), ("0", None), ("-5", None), ("abc", None), ("", None), ("nan", None), ("inf", None)):
            self.assertEqual(timelimit.configure(raw), want, raw)

    def test_the_words(self):
        timelimit.configure("12.5")
        self.assertEqual(timelimit.line(), "time: 0 of 12.5 minutes used")  # before the first call
        timelimit.started(now=1000.0)
        timelimit.started(now=5000.0)  # a later call changes nothing
        self.assertEqual(timelimit.used(now=1000.0 + 59), "0 of 12.5 minutes used")
        self.assertEqual(timelimit.used(now=1000.0 + 61 * 7), "7 of 12.5 minutes used")
        self.assertEqual(timelimit.line(now=1000.0 + 60 * 20), "time: 20 of 12.5 minutes used")

    def test_off_says_nothing(self):
        timelimit.configure("")
        timelimit.started(now=1.0)
        self.assertIsNone(timelimit.line())
        self.assertEqual(timelimit.state(), {})
        h = {"ok": True, "verdict": "nothing red"}
        self.assertEqual(timelimit.mark_health(h), {"ok": True, "verdict": "nothing red"})

    def test_the_verdict_gets_it_once_from_half_the_limit(self):
        timelimit.configure("30")
        self.assertEqual(timelimit.mark_health({"ok": True, "verdict": "nothing red"})["verdict"], "nothing red")  # before the first call
        timelimit.started(now=1000.0)
        self.assertEqual(timelimit.mark_health({"ok": True, "verdict": "nothing red"}, now=1000.0 + 60 * 14)["verdict"], "nothing red")
        h = timelimit.mark_health(timelimit.mark_health({"ok": True, "verdict": "nothing red"}, now=1000.0 + 60 * 15), now=1000.0 + 60 * 15)
        self.assertEqual(h["verdict"], "nothing red; time: 15 of 30 minutes used")

    def test_documented_with_the_other_settings(self):
        for doc in ("SETUP.md", "README.md", os.path.join("docs", "clients", "README.md")):
            with open(os.path.join(ROOT, doc), encoding="utf-8") as f:
                self.assertIn("AGENTLINK_TIME_LIMIT_MIN", f.read(), doc)


if __name__ == "__main__":
    unittest.main()
