# SPDX-License-Identifier: LGPL-2.1-or-later
# The release statistics (scripts/stats.py): made from the data, the same
# numbers as the scripts they come from, and the committed files current.
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import hardening_status  # noqa: E402
import stats  # noqa: E402
import tool_summary  # noqa: E402


class Stats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = stats.build()

    def test_script_runs_and_committed_files_are_current(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "stats.py"), "--check"], capture_output=True, text=True, timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_hub_total_is_tool_summarys(self):
        gs = tool_summary.groups()
        self.assertEqual(self.s["hubTools"]["total"], sum(len(v["tools"]) for v in gs.values()))
        self.assertEqual(len(self.s["hubTools"]["groups"]), len(gs))

    def test_bars_are_hardening_status_bars(self):
        groups, status = hardening_status.load()
        self.assertEqual("\n".join(stats.coverage_lines(self.s["coverage"])), hardening_status.bars(groups, status))

    def test_stats_md_numbers_come_from_stats_json(self):
        with open(stats.STATS_JSON, encoding="utf-8") as f:
            s = json.load(f)
        with open(stats.STATS_MD, encoding="utf-8") as f:
            self.assertEqual(f.read(), stats.render_md(s))

    def test_four_listing_combinations(self):
        combos = {(c["mode"], c["style"]): c for c in self.s["tokens"]["combos"]}
        self.assertEqual(set(combos), {("static", "ste"), ("static", "full"), ("classic", "ste"), ("classic", "full")})
        self.assertTrue(combos[("static", "ste")]["default"])
        self.assertLessEqual(combos[("static", "ste")]["tokens"], combos[("static", "full")]["tokens"])
        self.assertLess(combos[("static", "full")]["tokens"], combos[("classic", "full")]["tokens"])

    def test_addon_not_installed_costs_nothing(self):
        for a in self.s["tokens"]["addons"]:
            self.assertEqual(a["notInstalledTokens"], 0)
            self.assertEqual(a["staticTokens"], 0)
        self.assertEqual(self.s["tokens"]["totalAllInstalled"], self.s["hubTools"]["total"] + self.s["tokens"]["addonToolsLoaded"])

    def test_timings_importer_reads_usage_rows(self):
        rows = [{"kind": "job", "job": "j1"},
                {"kind": "call", "tool": "session_state", "grp": "core", "ms": 10},
                {"kind": "call", "tool": "session_state", "grp": "core", "ms": 30},
                {"kind": "call", "tool": "batch", "ms": 999},
                {"kind": "call", "tool": "not_a_tool", "ms": 5}]
        with tempfile.TemporaryDirectory() as d:
            log, out = os.path.join(d, "day.jsonl"), os.path.join(d, "timings.json")
            with open(log, "w", encoding="utf-8") as f:
                f.write("\n".join(json.dumps(r) for r in rows) + "\n")
            old = stats.TIMINGS_JSON
            stats.TIMINGS_JSON = out
            try:
                t = stats.import_timings(log, stats.family_map({}))
            finally:
                stats.TIMINGS_JSON = old
            self.assertTrue(os.path.isfile(out))
        fam = {f["family"]: f for f in t["families"]}
        self.assertEqual(t["calls"], 3)
        self.assertEqual(fam["core"]["count"], 2)
        self.assertEqual(fam["core"]["medianMs"], 20)
        self.assertEqual(fam["other"]["count"], 1)

    def test_timings_importer_reads_queue(self):
        with tempfile.TemporaryDirectory() as d:
            q, out = os.path.join(d, "queue.json"), os.path.join(d, "timings.json")
            with open(q, "w", encoding="utf-8") as f:
                json.dump({"running": [], "timings": {"fem_solve": [[1000, 2.5], [2000, 4.5]]}}, f)
            old = stats.TIMINGS_JSON
            stats.TIMINGS_JSON = out
            try:
                t = stats.import_timings(q, lambda tool, grp: "fem")
            finally:
                stats.TIMINGS_JSON = old
        self.assertEqual(t["families"], [{"family": "fem", "count": 2, "medianMs": 3500, "maxMs": 4500}])


if __name__ == "__main__":
    unittest.main()
