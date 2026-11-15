# SPDX-License-Identifier: LGPL-2.1-or-later
# The output folder's clear-up (agentlink/outputs.py): only what a tool was
# recorded making goes; the person's files, anything moved in or renamed,
# what a document links to, what is open, and install / settings / crash /
# checkpoints / autosave stay. No FreeCAD needed.
import json
import os
import shutil
import sys
import tempfile
import time
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agentlink import outputs, paths  # noqa: E402

DAY = 86400.0


class T:
    def __init__(self, name):
        self.name = name


def write(p, data=b"x" * 100):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)
    return p


def age(p, days, now):
    t = now - days * DAY
    os.utime(p, (t, t))


class Outputs(unittest.TestCase):
    def setUp(self):
        self.out = os.path.realpath(tempfile.mkdtemp())
        self.s = types.SimpleNamespace(out_dir=self.out)
        self.now = time.time()
        self.removed = []

    def tearDown(self):
        shutil.rmtree(self.out, ignore_errors=True)

    def call(self, tool, fn):
        return outputs.track(self.s, T(tool), fn)

    def made(self, tool, rel, kind=None, days=0.0, isdir=False):
        """A tool's output made `days` ago, recorded as it would be."""
        def fn():
            p = paths.local(self.s, rel, kind=kind)
            if isdir:
                os.makedirs(p, exist_ok=True)
                write(os.path.join(p, "job.inp"))
            else:
                write(p)
            return p
        p = self.call(tool, fn)
        self.backdate(p, days)
        age(p, days, self.now)
        return p

    def backdate(self, p, days):
        rows = outputs.read(self.out)
        rows[os.path.realpath(p)]["time"] = self.now - days * DAY
        outputs._write_all(self.out, list(rows.values()))

    def clean(self, **kw):
        kw.setdefault("now", self.now)
        kw.setdefault("open_", lambda ps: set())
        kw.setdefault("prefs", {"CountBackupFiles": 1})
        return outputs.clean(self.out, remove=lambda p: (self.removed.append(p), outputs.trash(p))[1], **kw)

    # ---- the manifest ----

    def test_manifest_round_trip(self):
        p = self.made("view_render", "render_iso.png")
        d = self.made("fea_solve", "fea_Box", isdir=True)
        e = self.made("export_file", "Box.step")
        rows = outputs.read(self.out)
        self.assertEqual(rows[p]["kind"], "shot")
        self.assertEqual(rows[p]["tool"], "view_render")
        self.assertEqual(rows[p]["size"], 100)
        self.assertEqual(rows[d]["kind"], "run")
        self.assertTrue(rows[d]["dir"])
        self.assertEqual(rows[e]["kind"], "export")
        for r in rows.values():
            self.assertTrue({"path", "kind", "tool", "time", "size"} <= set(r))
        with open(outputs.manifest_path(self.out), encoding="utf-8") as f:
            self.assertEqual(len([json.loads(x) for x in f]), 3)

    def test_kind_passed_wins(self):
        p = self.made("anything", "pic.png", kind="shot")
        self.assertEqual(outputs.read(self.out)[p]["kind"], "shot")

    def test_person_file_not_recorded(self):
        mine = write(os.path.join(self.out, "mine.step"))
        self.call("export_file", lambda: write(paths.local(self.s, "mine.step")))
        self.assertNotIn(mine, outputs.read(self.out))

    def test_read_path_not_recorded(self):
        self.call("mesh_import", lambda: paths.local(self.s, "missing.stl"))
        self.assertEqual(outputs.read(self.out), {})

    def test_outside_out_dir_not_recorded(self):
        other = tempfile.mkdtemp()
        try:
            self.call("export_file", lambda: write(paths.local(self.s, os.path.join(other, "a.stl"))))
            self.assertEqual(outputs.read(self.out), {})
        finally:
            shutil.rmtree(other)

    def test_backups_beside_a_saved_document(self):
        def save():
            p = paths.local(self.s, "Part.FCStd")
            write(p)
            write(os.path.join(self.out, "Part.FCBak"))
        self.call("doc_save", save)
        rows = outputs.read(self.out)
        self.assertEqual(rows[os.path.join(self.out, "Part.FCBak")]["kind"], "fcbak")

    # ---- what never goes ----

    def test_never_touch_list(self):
        for top in outputs.NEVER:
            self.call("view_render", lambda: write(paths.local(self.s, os.path.join(top, "x.png"))))
        self.assertEqual(outputs.read(self.out), {})
        # Even when written into the manifest by hand.
        for top in outputs.NEVER:
            p = write(os.path.join(self.out, top, "old.png"))
            age(p, 30, self.now)
            outputs.record(self.out, p, "shot", "view_render", now=self.now - 30 * DAY)
        res = self.clean(dry_run=False)
        self.assertEqual(self.removed, [])
        self.assertEqual(res["total"]["count"], 0)
        for top in outputs.NEVER:
            self.assertTrue(os.path.exists(os.path.join(self.out, top, "old.png")))

    def test_unknown_path_left_alone(self):
        p = write(os.path.join(self.out, "fea_mine", "x.inp"))
        age(p, 60, self.now)
        age(os.path.dirname(p), 60, self.now)
        q = write(os.path.join(self.out, "old.png"))
        age(q, 60, self.now)
        self.clean(dry_run=False)
        self.assertTrue(os.path.exists(p) and os.path.exists(q))
        self.assertEqual(self.removed, [])

    def test_moved_in_under_our_name_stays(self):
        p = self.made("fea_solve", "fea_Box", days=30, isdir=True)
        held = os.path.join(self.out, "hold")
        os.rename(p, held)  # keeps its inode in use, as a move away does
        os.makedirs(p)  # the person's own folder now, under that name
        age(p, 30, self.now)
        res = self.clean(dry_run=False)
        self.assertTrue(os.path.isdir(p))
        self.assertEqual(res["skipped"].get("replaced"), 1)

    def test_file_replaced_by_another_stays(self):
        p = self.made("export_file", "a.stl", days=30)
        os.unlink(p)
        write(p, b"mine, longer than the tool's file" * 10)
        res = self.clean(dry_run=False, kinds=["export"], older_than_days=0)
        self.assertTrue(os.path.exists(p))
        self.assertEqual(res["skipped"].get("replaced"), 1)

    def test_renamed_stays(self):
        p = self.made("view_render", "a.png", days=30)
        q = os.path.join(self.out, "kept.png")
        os.rename(p, q)
        self.clean(dry_run=False, prefs={"ShotKeep": 0, "CountBackupFiles": 1})
        self.assertTrue(os.path.exists(q))

    def test_linked_and_open_stay(self):
        a = self.made("fea_solve", "fea_A", days=30, isdir=True)
        b = self.made("fea_solve", "fea_B", days=30, isdir=True)
        c = self.made("fea_solve", "fea_C", days=30, isdir=True)
        res = self.clean(dry_run=False, linked=[os.path.join(a, "job.inp")], open_=lambda ps: {b} & set(ps))
        self.assertTrue(os.path.isdir(a) and os.path.isdir(b))
        self.assertFalse(os.path.exists(c))
        self.assertEqual(res["skipped"], {"linked": 1, "open": 1})

    # ---- age and count ----

    def test_shots_keep_last_count_or_days(self):
        ps = [self.made("window_snapshot", f"s{i:02}.png", days=10 + i * 0.01) for i in range(55)]
        new = self.made("window_snapshot", "fresh.png", days=1)
        res = self.clean(dry_run=False)
        # 56 shots: the newest 50 stay (fresh among them), the 6 oldest go.
        self.assertEqual(res["went"]["shot"]["count"], 6)
        self.assertTrue(os.path.exists(new))
        self.assertTrue(all(os.path.exists(p) for p in ps[:49]))
        self.assertFalse(any(os.path.exists(p) for p in ps[49:]))

    def test_shots_within_days_stay_past_count(self):
        for i in range(60):
            self.made("view_snapshot", f"s{i:02}.png", days=1)
        res = self.clean(dry_run=False)
        self.assertEqual(res["total"]["count"], 0)

    def test_runs_after_14_days(self):
        old = self.made("fea_solve", "fea_Old", days=15, isdir=True)
        young = self.made("fea_solve", "elmer_Young", days=13, isdir=True)
        res = self.clean(dry_run=False)
        self.assertFalse(os.path.exists(old))
        self.assertTrue(os.path.exists(young))
        self.assertEqual(res["went"]["run"]["names"], ["fea_Old"])

    def test_exports_never_on_their_own(self):
        e = self.made("export_file", "Box.stl", days=400)
        res = self.clean(dry_run=False)
        self.assertTrue(os.path.exists(e))
        self.assertEqual(res["exports"]["count"], 1)
        self.assertEqual(res["exports"]["names"], ["Box.stl"])
        # Only with kinds export and an age chosen.
        self.clean(dry_run=False, kinds=["export"], older_than_days=30)
        self.assertFalse(os.path.exists(e))

    def test_backups_beyond_count_after_7_days(self):
        def save(name, days):
            def fn():
                write(paths.local(self.s, "Part.FCStd"))
                write(os.path.join(self.out, name))
            self.call("doc_save", fn)
            p = os.path.join(self.out, name)
            self.backdate(p, days)
            age(p, days, self.now)
            return p
        newest = save("Part.FCBak", 9)
        older = save("Part1.FCBak", 10)
        young = save("Part2.FCBak", 3)
        self.clean(dry_run=False)
        # The newest one (FreeCAD's own count, 1) stays whatever its age.
        self.assertTrue(os.path.exists(young))
        self.assertFalse(os.path.exists(newest) and os.path.exists(older))
        self.assertFalse(os.path.exists(older))

    def test_older_than_days_narrows(self):
        a = self.made("fea_solve", "fea_A", days=5, isdir=True)
        res = self.clean(dry_run=True, kinds=["run"], older_than_days=2)
        self.assertEqual(res["wouldGo"]["run"]["count"], 1)
        self.assertTrue(os.path.exists(a))

    # ---- dry run ----

    def test_dry_run_changes_nothing(self):
        p = self.made("fea_solve", "fea_Old", days=30, isdir=True)
        q = self.made("view_render", "old.png", days=30)
        with open(outputs.manifest_path(self.out), "rb") as f:
            before = f.read()
        res = self.clean(prefs={"ShotKeep": 0, "CountBackupFiles": 1})
        self.assertTrue(res["dryRun"])
        self.assertEqual(res["total"]["count"], 2)
        self.assertTrue(os.path.exists(p) and os.path.exists(q))
        self.assertEqual(self.removed, [])
        with open(outputs.manifest_path(self.out), "rb") as f:
            self.assertEqual(f.read(), before)

    def test_manifest_drops_what_went(self):
        p = self.made("fea_solve", "fea_Old", days=30, isdir=True)
        keep = self.made("export_file", "a.step")
        self.clean(dry_run=False)
        rows = outputs.read(self.out)
        self.assertNotIn(p, rows)
        self.assertIn(keep, rows)

    # ---- when it runs on its own ----

    def test_auto_once_a_day_and_held_by_queue(self):
        self.made("fea_solve", "fea_Old", days=30, isdir=True)
        q = {"held": "the person is working"}
        orig = outputs.queue_free
        try:
            outputs.queue_free = lambda: not q.get("held")
            self.assertIsNone(outputs.auto(self.s, now=self.now))
            q.clear()
            res = outputs.auto(self.s, now=self.now)
            self.assertEqual(res["went"]["run"]["count"], 1)
            self.made("fea_solve", "fea_Next", days=30, isdir=True)
            self.assertIsNone(outputs.auto(self.s, now=self.now + 3600))
            self.assertIsNotNone(outputs.auto(self.s, now=self.now + DAY + 1))
        finally:
            outputs.queue_free = orig


if __name__ == "__main__":
    unittest.main()
