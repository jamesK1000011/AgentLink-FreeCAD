# SPDX-License-Identifier: LGPL-2.1-or-later
# Findings 52, 41, 45, 40, 62, 66 and "no prejudging" (18 Nov): the window
# restart seen without a mark file, calls that move themselves to the
# background, the hang rule by CPU work, the pinned document after a
# restart, a discard with no save dialog, and part_boolean's fuzzy retry.
# Stand-ins only: no FreeCAD, no macOS.

import json
import os
import sys
import threading
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agentlink import sup_jobs, supervise, window_watch  # noqa: E402


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


def reply(mid, body, err=False):
    out = {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": json.dumps(body)}]}}
    if err:
        out["result"]["isError"] = True
    return json.dumps(out)


class WatchTest(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.hb = {"pid": 11, "t": self.clock.t, "pairing": 1}
        self.alive = {11}
        self.w = window_watch.Watch(lambda: dict(self.hb), alive=lambda p: p in self.alive, clock=self.clock, sleep=self.clock.sleep)

    def test_no_restart_no_wait(self):
        self.assertIsNone(self.w.wait(lambda: False))
        self.assertFalse(self.w.pending())

    def test_waits_for_new_pid_then_ready(self):
        self.w.expect(11, pinned={"name": "A", "label": "A", "file": ""})
        self.assertTrue(self.w.pending())
        calls = {"n": 0}

        def ready():
            calls["n"] += 1
            return True

        # The old window still beats: not back.
        self.assertIsNone(self.w.back())
        # It quits, a new pid pairs after 3 s.
        orig = self.clock.sleep

        def step(s):
            orig(s)
            if self.clock.t > 1003:
                self.alive.discard(11)
                self.hb = {"pid": 22, "t": self.clock.t, "pairing": 1}
        self.w.sleep = step
        self.assertIs(self.w.wait(ready, limit=45), True)
        rec = self.w.done()
        self.assertEqual(rec["pinned"]["name"], "A")
        self.assertFalse(self.w.pending())

    def test_limit_gives_clear_words(self):
        self.w.expect(11)
        self.alive.discard(11)
        got = self.w.wait(lambda: True, limit=5)
        self.assertIsInstance(got, str)
        self.assertIn("FreeCAD is starting again", got)
        self.assertIn("no window yet after 5 s", got)
        self.assertIn("never go to the hidden FreeCAD", got)
        # Still pending: the next call waits again (never headless quietly).
        self.assertTrue(self.w.pending())

    def test_new_heartbeat_without_pairing_is_not_back(self):
        self.w.expect(11)
        self.hb = {"pid": 22, "t": self.clock.t + 1}
        self.assertIsNone(self.w.back())

    def test_give_up_said_once(self):
        self.w.expect(11)
        self.clock.t += window_watch.GIVE_UP + 1
        self.assertFalse(self.w.pending())
        lost = self.w.take_lost()
        self.assertIsNotNone(lost)
        self.assertIn("did not come back", window_watch.Watch.lost_words(lost))
        self.assertIsNone(self.w.take_lost())

    def test_mac_events_launch_and_quit(self):
        self.w.expect(11)
        self.w.terminated(11)
        self.assertTrue(self.w.restart["quit"])
        self.w.launched(22)
        self.assertEqual(self.w.restart["launched"], 22)
        self.assertIn("link has not paired yet", self.w.waiting_words(3))

    def test_launch_seen_without_restart_waits(self):
        self.hb = {"pid": 11, "t": self.clock.t - 100, "pairing": 1}
        self.w.launched(33)
        self.assertTrue(self.w.pending())

    def test_restart_from_env(self):
        self.assertIsNone(window_watch.restart_from_env(""))
        self.assertIsNone(window_watch.restart_from_env("{bad"))
        got = window_watch.restart_from_env(json.dumps({"pid": 5, "t": 1, "pinned": {"name": "X"}}))
        self.assertEqual(got["pid"], 5)

    def test_is_freecad(self):
        self.assertTrue(window_watch.is_freecad({"bundle": "org.freecad.FreeCAD"}))
        self.assertTrue(window_watch.is_freecad({"name": "FreeCAD"}))
        self.assertFalse(window_watch.is_freecad({"bundle": "com.apple.Safari"}))

    def test_no_pyobjc_falls_back(self):
        # This container has no AppKit: the polling covers it.
        self.assertFalse(window_watch.mac_events(self.w))


class PinTest(unittest.TestCase):
    def test_pinned_of(self):
        hb = {"pinned": "Lesson", "docs": [{"name": "Lesson", "label": "bike-stem-1", "file": "/x/l.FCStd"}]}
        self.assertEqual(window_watch.pinned_of(hb), {"name": "Lesson", "label": "bike-stem-1", "file": "/x/l.FCStd"})
        self.assertIsNone(window_watch.pinned_of({}))

    def test_pin_target_by_file_label_and_copy(self):
        pin = {"name": "Lesson", "label": "bike-stem-1", "file": "/x/l.FCStd"}
        docs = [{"name": "Other", "label": "Other", "file": "/x/o.FCStd"}, {"name": "Lesson001", "label": "bike-stem-1", "file": "/x/l.FCStd"}]
        self.assertEqual(window_watch.pin_target(pin, docs), "Lesson001")
        pin2 = {"name": "M", "label": "Shell", "file": ""}
        self.assertEqual(window_watch.pin_target(pin2, [{"name": "M001", "label": "Shell (recovered 12:00)", "file": "/tmp/a"}]), "M001")
        self.assertIsNone(window_watch.pin_target(pin2, [{"name": "Z", "label": "Z"}]))


class JobsTest(unittest.TestCase):
    def setUp(self):
        self.out = []
        self.clock = Clock()
        self.j = sup_jobs.Jobs(self.out.append, clock=self.clock, after=60)

    def body(self, i=-1):
        return json.loads(json.loads(self.out[i])["result"]["content"][0]["text"])

    def test_fast_call_answers_as_ever(self):
        self.j.came(1, "export")
        self.clock.t += 0.5
        self.assertEqual(self.j.tick(), [])
        self.j.write(reply(1, {"file": "a.stl"}))
        self.assertEqual(self.body(), {"file": "a.stl"})

    def test_slow_call_moves_to_background_and_keeps_answer(self):
        self.j.came(7, "part_loft")
        self.clock.t += 61
        got = self.j.tick()
        self.assertEqual(got, ["call-1"])
        b = self.body()
        self.assertEqual(b["job"], "call-1")
        self.assertEqual(b["status"], "running")
        self.assertIn("job_status", b["next"])
        # The real answer comes later: kept, not written.
        n = len(self.out)
        self.j.write(reply(7, {"body": "Loft"}))
        self.assertEqual(len(self.out), n)
        st, err = self.j.status({"job": "call-1"})
        self.assertFalse(err)
        self.assertEqual(st["status"], "done")
        self.assertEqual(st["result"], {"body": "Loft"})

    def test_answer_before_client_drop(self):
        # The job answer goes well under the client's 80 s.
        self.assertLess(sup_jobs.DETACH_AFTER, 80)
        self.assertLess(window_watch.WAIT, sup_jobs.DETACH_AFTER)

    def test_failed_answer_kept_as_error(self):
        self.j.came(2, "part_boolean")
        self.clock.t += 61
        self.j.tick()
        self.j.write(reply(2, {"error": {"code": "failed", "message": "OCC"}}, err=True))
        st, _ = self.j.status({"job": "call-1"})
        self.assertEqual(st["status"], "failed")
        self.assertEqual(st["error"]["code"], "failed")

    def test_wait_false_at_once(self):
        self.j.came(3, "export", after=0)
        self.assertEqual(self.j.tick(), ["call-1"])
        self.assertIn("this answer does not wait", self.body()["note"])

    def test_queued_call_says_behind(self):
        self.j.came(1, "export")
        self.clock.t += 10
        self.j.came(2, "body_check")
        self.clock.t += 55
        self.j.tick()  # 1 detaches
        self.clock.t += 10
        self.j.tick()  # 2 detaches, behind call-1
        self.assertIn("waits behind export (call-1)", self.body()["note"])

    def test_status_waits_and_unknown(self):
        self.j.came(9, "insp_run")
        self.clock.t += 61
        self.j.tick()
        threading.Timer(0.05, lambda: self.j.write(reply(9, {"ok": True}))).start()
        st, _ = self.j.status({"job": "call-1", "wait": 5})
        self.assertEqual(st["status"], "done")
        st, err = self.j.status({"job": "call-99"})
        self.assertTrue(err)
        self.assertEqual(st["error"]["code"], "not_found")
        st, err = self.j.status({"job": "call-1", "wait": -1})
        self.assertTrue(err)

    def test_drop_mode(self):
        self.j.came(4, "job_status", after=5, mode="drop")
        self.clock.t += 6
        self.j.tick(words=lambda c: "late")
        self.assertIn("late", self.out[-1])
        n = len(self.out)
        self.assertFalse(self.j.write(reply(4, {"x": 1})))
        self.assertEqual(len(self.out), n)

    def test_job_start_inner(self):
        self.assertEqual(sup_jobs.job_start_inner({"job": "export", "arguments": {"format": "stl"}, "wait": False}), ("export", {"format": "stl"}, 0.0))
        self.assertEqual(sup_jobs.job_start_inner({"job": "batch", "arguments": {}})[2], None)
        self.assertIsNone(sup_jobs.job_start_inner({"job": "job_status"}))
        self.assertIsNone(sup_jobs.job_start_inner({"job": "app_restart"}))
        self.assertIsNone(sup_jobs.job_start_inner({}))


class HangRuleTest(unittest.TestCase):
    def test_clock_secs(self):
        self.assertEqual(supervise._clock_secs("01:02"), 62)
        self.assertEqual(supervise._clock_secs("1:00:00"), 3600)
        self.assertEqual(supervise._clock_secs("2-00:00:01"), 2 * 86400 + 1)
        self.assertAlmostEqual(supervise._clock_secs("0:01.50"), 1.5)
        self.assertIsNone(supervise._clock_secs("x"))

    def test_cpu_tree_counts_children(self):
        rows = [(1, 0, 5.0), (10, 1, 2.0), (11, 10, 3.0), (12, 99, 7.0)]
        self.assertEqual(supervise.cpu_tree(10, rows), 5.0)
        self.assertIsNone(supervise.cpu_tree(55, rows))

    def test_progress_and_stalled(self):
        clock = Clock(0.0)
        cpu = {"v": 0.0}
        p = supervise.Progress(table=lambda: [(7, 1, cpu["v"])], clock=clock)
        self.assertEqual(p.idle_for(7), 0.0)
        clock.t = 100
        cpu["v"] = 50.0  # busy: OCC working
        self.assertEqual(p.idle_for(7), 0.0)
        clock.t = 300
        cpu["v"] = 50.1  # no work for 200 s
        idle = p.idle_for(7)
        self.assertEqual(idle, 200)
        # A slow call that keeps working is never hung, however long.
        self.assertFalse(supervise.stalled(1000, 0, 0, 120, 0.0))
        # No heartbeat and no CPU work past STALL: hung.
        self.assertTrue(supervise.stalled(1000, 0, 0, 120, supervise.STALL))
        # Within its limit, or with a fresh heartbeat: never.
        self.assertFalse(supervise.stalled(100, 0, 0, 120, 999))
        self.assertFalse(supervise.stalled(1000, 0, 990, 120, 999))
        # CPU unreadable: only the ceiling.
        self.assertFalse(supervise.stalled(1000, 0, 0, 120, None))
        self.assertTrue(supervise.stalled(supervise.HANG_CEILING + 10, 0, 0, 120, None))

    def test_deadline_reads_no_estimate(self):
        if supervise.keep is None:
            self.skipTest("no keep")
        self.assertEqual(supervise.deadline_for("part_loft", {}), supervise.keep.deadline("change"))
        self.assertEqual(supervise.deadline_for("addon_test", {"timeout": 600}), 660.0)


class WindowRestartTest(unittest.TestCase):
    """supervise.Window: app_restart's answer starts the wait; a call in
    the gap is refused with words, never sent headless."""

    def make(self):
        out = []
        w = supervise.Window(out.append)
        clock = Clock()
        hb = {"v": {"pid": 11, "t": clock.t, "pairing": 1, "pinned": "Lesson", "docs": [{"name": "Lesson", "label": "L", "file": ""}]}}
        alive = {11}
        w.watch = window_watch.Watch(lambda: dict(hb["v"]), alive=lambda p: p in alive, clock=clock, sleep=clock.sleep)
        return w, out, clock, hb, alive

    def test_note_restart_from_answer(self):
        w, _out, _c, hb, _a = self.make()
        w.last_reply = reply(1, {"restarting": True})
        w._note_restart("app_restart", hb["v"])
        self.assertTrue(w.watch.pending())
        self.assertEqual(w.watch.restart["pinned"]["name"], "Lesson")
        w2, _o, _c2, hb2, _a2 = self.make()
        w2.last_reply = reply(1, {"error": {"code": "invalid_state"}}, err=True)
        w2._note_restart("app_restart", hb2["v"])
        self.assertFalse(w2.watch.pending())

    def test_call_in_gap_is_refused_not_headless(self):
        w, out, clock, hb, alive = self.make()
        w.watch.expect(11, why="agentlink_update")
        alive.discard(11)
        w._open = lambda: False
        w.watch.wait = (lambda real: (lambda ready, limit=None, step=0.5: real(ready, limit=2, step=step)))(w.watch.wait)
        got = w.call(json.dumps({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "session_state", "arguments": {}}}))
        self.assertTrue(got)  # answered here: the hidden FreeCAD did not take it
        msg = json.loads(json.loads(out[-1])["result"]["content"][0]["text"])["error"]["message"]
        self.assertIn("FreeCAD is starting again (agentlink_update)", msg)

    def test_back_restores_pinned(self):
        w, _out, clock, hb, alive = self.make()
        w.watch.expect(11, pinned={"name": "Lesson", "label": "L", "file": ""})
        hb["v"] = {"pid": 22, "t": clock.t, "pairing": 1, "pinned": "Unnamed", "docs": [{"name": "Unnamed", "label": "Unnamed"}, {"name": "Lesson", "label": "L"}]}
        asked = []
        w.ask = lambda tool, args, timeout=0: asked.append((tool, args)) or {"document": args["document"]}
        orig = supervise.heartbeat_any
        supervise.heartbeat_any = lambda: dict(hb["v"])
        try:
            self.assertEqual(w._back_from_restart(), "Lesson")
        finally:
            supervise.heartbeat_any = orig
        self.assertEqual(asked, [("doc_switch", {"document": "Lesson"})])


class CloseConfirmTest(unittest.TestCase):
    def setUp(self):
        from test_gui_link_dialog import _gui_link

        self.gl = _gui_link()
        self.d = {"class": "QMessageBox", "title": "Unsaved Document", "text": "Save all changes to document 'Lesson' before closing? Otherwise, all changes will be lost.",
                  "buttons": ["Save", "Cancel", "Don't Save"], "name": "confirmSave"}

    def test_unsafe_under_a_close(self):
        words = self.gl.unsafe_close_press(self.d, "Don't Save", ["batch", "doc_close", "dialog_answer"])
        self.assertIn("Press Cancel", words)
        self.assertIn("discard: true", words)
        self.assertIsNotNone(self.gl.unsafe_close_press(self.d, "Save", ["doc_close", "dialog_answer"]))

    def test_safe_cases(self):
        self.assertIsNone(self.gl.unsafe_close_press(self.d, "Cancel", ["doc_close", "dialog_answer"]))
        self.assertIsNone(self.gl.unsafe_close_press(self.d, "Don't Save", ["dialog_answer"]))
        other = dict(self.d, title="Preferences", text="x", name="")
        self.assertIsNone(self.gl.unsafe_close_press(other, "OK", ["doc_close"]))


class UnmarkTest(unittest.TestCase):
    def test_unmark_modified(self):
        from agentlink import gui_input

        gd = types.SimpleNamespace(Modified=True)
        gui = types.SimpleNamespace(getDocument=lambda n: gd)
        self.assertTrue(gui_input.unmark_modified(gui, "Lesson"))
        self.assertFalse(gd.Modified)
        self.assertFalse(gui_input.unmark_modified(types.SimpleNamespace(getDocument=lambda n: None), "X"))


class LauncherWordTest(unittest.TestCase):
    def test_launcher_passes_restart(self):
        src = open(os.path.join(os.path.dirname(__file__), "..", "packaging", "mcpb", "server", "index.js"), encoding="utf-8").read()
        self.assertIn("AGENTLINK_WINDOW_RESTART", src)
        self.assertIn("restartWord(hbBefore)", src)


if __name__ == "__main__":
    unittest.main()
