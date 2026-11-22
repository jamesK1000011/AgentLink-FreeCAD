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


# The hardening records are private since 22 Nov 2026 (scripts/hardening_status.py):
# the checks that read them run where the owner's archive is beside this repo.
NEED_RECORDS = unittest.skipUnless(hardening_status.available(), "the hardening records are private (not beside this repo)")

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

    @NEED_RECORDS
    def test_bars_are_hardening_status_bars(self):
        groups, status = hardening_status.load()
        self.assertEqual("\n".join(stats.coverage_lines(self.s["coverage"])), hardening_status.bars(groups, status))

    def test_stats_md_numbers_come_from_stats_json(self):
        with open(stats.STATS_JSON, encoding="utf-8") as f:
            s = json.load(f)
        with open(stats.STATS_MD, encoding="utf-8") as f:
            self.assertEqual(f.read(), stats.render_md(s))

    @NEED_RECORDS
    def test_inventory_and_the_real_tools_are_in_step(self):
        # inventory.json holds the V1 tools: the hub's (tool_summary) and the add-ons' (addons.json snapshot),
        # each under the repository that has its code. A tool that is gone from the tool data fails here:
        # drop it from the inventory, or move it under notInV1 with the reason.
        inv = hardening_status.load_inventory()
        groups, status = hardening_status.load()
        real = {n: "AgentLink-FreeCAD" for v in tool_summary.groups().values() for n in v["tools"]}
        for repo, a in (stats.load_json(stats.ADDONS_JSON, {}) or {}).get("addons", {}).items():
            for n in a["tools"]:
                real.setdefault(n, repo)
        listed = {t: d["repo"] for d in groups.values() for t in d["tools"]}
        unlisted = set(inv.get("unlisted", {}))
        not_v1 = set(inv.get("notInV1", {}).get("tools", {}))
        self.assertEqual(sorted(set(listed) - set(real)), [], "in the inventory, but no such tool in the hub or the add-on data")
        self.assertEqual(sorted(set(real) - set(listed) - unlisted), [], "a real tool that the inventory does not have")
        self.assertEqual(sorted(t for t, r in listed.items() if real[t] != r), [], "inventory repo is not the repo with the code")
        self.assertEqual(sorted(not_v1 & set(real)), [], "a notInV1 tool is in the V1 tool data")
        self.assertEqual(sorted(unlisted - set(real)), [])
        self.assertEqual(sorted(set(status) - set(listed) - unlisted - not_v1), [], "status.json has a tool that is in no list")
        self.assertEqual({r for r, _t in hardening_status.SECTIONS}, set(listed.values()))

    @NEED_RECORDS
    def test_sections_add_up(self):
        cov = self.s["coverage"]
        for k in ("total", "proven", "headless", "live", "docs", "health", "description"):
            self.assertEqual(sum(x[k] for x in cov["sections"]), cov[k], k)
        self.assertEqual(cov["sections"][0]["title"], "Agent Link (core)")
        # The hub's declared tools are its counted tools and its tools that are not counted.
        hub_nc = sum(x["total"] for x in cov["notCounted"] if x["repos"] == ["AgentLink-FreeCAD"])
        self.assertEqual(cov["sections"][0]["total"] + hub_nc, self.s["hubTools"]["total"])
        for x in cov["sections"] + cov["notCounted"]:
            self.assertEqual(sum(p["total"] for p in x["parts"]), x["total"], x["title"])
        groups, status = hardening_status.load()
        self.assertEqual(cov["total"] + sum(x["total"] for x in cov["notCounted"]), sum(len(d["tools"]) for d in groups.values()))

    @NEED_RECORDS
    def test_developer_tools_are_not_counted(self):
        # The owner (19 Nov 2026): the porting tools are a developer tool, not a FreeCAD function.
        # They have their own section and lines, and they are not in the core or the V1 totals.
        cov = self.s["coverage"]
        groups, status = hardening_status.load()
        self.assertEqual(groups["porting"].get("notCounted"), "developer")
        dev = {x["key"]: x for x in cov["notCounted"]}
        self.assertIn("developer", dev)
        self.assertIn("not counted", dev["developer"]["title"])
        self.assertTrue(dev["developer"]["why"].strip())
        porting = set(groups["porting"]["tools"])
        self.assertIn("port_scaffold", porting)
        self.assertEqual(dev["developer"]["total"], len(porting))
        self.assertEqual(sum(p["total"] for p in cov["sections"][0]["parts"] if p["name"] == "Porting"), 0)
        self.assertEqual(cov["sections"][0]["total"], sum(len(d["tools"]) for d in groups.values() if d["repo"] == "AgentLink-FreeCAD" and not d.get("notCounted")))
        self.assertFalse(porting & {g["tool"] for g in cov["gaps"]}, "a porting gap is in the counted gaps")
        self.assertEqual({g["tool"] for g in dev["developer"]["gaps"]}, {t for t in porting if not (status.get(t, {}).get("headless") and status.get(t, {}).get("live"))})
        hub = [x for x in cov["sections"] if x["repo"] == "AgentLink-FreeCAD"][0]
        self.assertEqual(hub["proven"], sum(1 for d in groups.values() if d["repo"] == "AgentLink-FreeCAD" and not d.get("notCounted")
                                           for t in d["tools"] if hardening_status.proven(status.get(t, {}))))
        bars = hardening_status.bars(groups, status)
        self.assertIn(dev["developer"]["title"], bars)
        with open(stats.STATS_MD, encoding="utf-8") as f:
            self.assertIn(f"### {dev['developer']['title']}", f.read())

    @NEED_RECORDS
    def test_every_gap_has_a_reason(self):
        groups, status = hardening_status.load()
        short = {t for d in groups.values() for t in d["tools"]
                 if not (status.get(t, {}).get("headless") and status.get(t, {}).get("live"))}
        nc_gaps = [g for x in self.s["coverage"]["notCounted"] for g in x["gaps"]]
        self.assertEqual({g["tool"] for g in self.s["coverage"]["gaps"] + nc_gaps}, short)
        for g in self.s["coverage"]["gaps"] + nc_gaps:
            self.assertTrue(g["why"].strip(), g["tool"])
        # A proof on cookbook format 2 (V2) is not a V1 proof.
        for t, st in status.items():
            if st.get("liveFormat2"):
                self.assertNotIn("live", st, t)

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
