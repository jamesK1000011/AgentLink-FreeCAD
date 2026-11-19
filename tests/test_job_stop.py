# SPDX-License-Identifier: LGPL-2.1-or-later
# Fault 89: job_status { job, stop: true }. A job-… job (a read on a worker
# thread) gets a stop at its next Python step and fails with code stopped;
# a call-N job (on FreeCAD's own thread) cannot stop in the middle, and the
# answer gives the next steps. Stand-ins only: no FreeCAD.

import json
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import jobs, keep, sup_jobs  # noqa: E402
from agentlink.protocol import Tool, ToolError  # noqa: E402


class Doc:
    Name, Objects = "D", ()


class Ses:
    def __init__(self, out):
        self.out_dir, self.doc = out, Doc()


class Home(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home, True)
        self._env = os.environ.get("AGENTLINK_HOME")
        os.environ["AGENTLINK_HOME"] = self.home

    def tearDown(self):
        if self._env is None:
            os.environ.pop("AGENTLINK_HOME", None)
        else:
            os.environ["AGENTLINK_HOME"] = self._env


class WorkerJobStop(Home):
    def start(self, fn, name="standin_read"):
        return jobs.start(Tool(name, "A stand-in read for the stop test.", {"type": "object"}, fn), {}, Ses(self.home))

    def test_a_python_loop_stops(self):
        steps = []
        go = threading.Event()

        def loop(a):
            go.set()
            while True:
                steps.append(1)
                time.sleep(0.01)

        job = self.start(loop)
        self.assertTrue(go.wait(5))
        got = jobs.status({"job": job["job"], "stop": True, "wait": 5})
        self.assertEqual(got["status"], "failed", got)
        self.assertEqual(got["error"]["code"], "stopped")
        self.assertIn("changed nothing", got["error"]["message"])
        self.assertIn("Sent", got["stop"])
        self.assertEqual(jobs.running(), [])
        n = len(steps)
        time.sleep(0.1)
        self.assertEqual(len(steps), n, "the loop still runs")

    def test_a_tool_that_catches_exception_still_stops(self):
        go = threading.Event()

        def stubborn(a):
            go.set()
            while True:
                try:
                    time.sleep(0.01)
                except Exception:  # noqa: BLE001 — the stop is no Exception
                    pass

        job = self.start(stubborn)
        self.assertTrue(go.wait(5))
        got = jobs.status({"job": job["job"], "stop": True, "wait": 5})
        self.assertEqual(got["error"]["code"], "stopped", got)

    def test_stopping_while_one_long_step_runs(self):
        # A long step (here a sleep, as a C++ step would be) ends first: the
        # job says stopping until then.
        go = threading.Event()

        def long_step(a):
            go.set()
            time.sleep(0.8)
            while True:
                time.sleep(0.01)

        job = self.start(long_step)
        self.assertTrue(go.wait(5))
        jobs.stop_job(job)
        self.assertEqual(job["status"], "stopping")
        self.assertIn(job, jobs.running())
        self.assertIn("next Python step", jobs.summary(job)["note"])
        self.assertIn("before", jobs.stop_job(job))
        got = jobs.status({"job": job["job"], "wait": 5})
        self.assertEqual(got["error"]["code"], "stopped", got)

    def test_a_job_that_ended_has_nothing_to_stop(self):
        job = self.start(lambda a: {"read": 1})
        self.assertTrue(jobs.wait_for(job, 5))
        got = jobs.status({"job": job["job"], "stop": True})
        self.assertEqual(got["status"], "done")
        self.assertEqual(got["result"], {"read": 1})
        self.assertIn("Nothing to stop", got["stop"])

    def test_a_writer_job_says_its_file_may_be_part(self):
        go = threading.Event()

        def writing(a):
            go.set()
            while True:
                time.sleep(0.01)

        job = jobs.start(Tool("export", "A stand-in export for the stop test.", {"type": "object"}, writing), {"path": "x.step"}, Ses(self.home))
        self.assertTrue(go.wait(5))
        got = jobs.status({"job": job["job"], "stop": True, "wait": 5})
        self.assertIn("not whole", got["error"]["message"])

    def test_stop_must_be_true_or_left_out(self):
        job = self.start(lambda a: {"read": 1})
        jobs.wait_for(job, 5)
        with self.assertRaises(ToolError):
            jobs.status({"job": job["job"], "stop": "yes"})


class CallJobStop(Home):
    def setUp(self):
        super().setUp()
        self.out = []
        self.t = [1000.0]
        self.j = sup_jobs.Jobs(self.out.append, clock=lambda: self.t[0], after=60)
        self.j.came(7, "part_loft")
        self.t[0] += 61
        self.assertEqual(self.j.tick(), ["call-1"])

    def test_a_call_job_cannot_stop_in_the_middle(self):
        st, err = self.j.status({"job": "call-1", "stop": True, "wait": 25})
        self.assertFalse(err)
        self.assertEqual(st["status"], "running")
        self.assertIn("cannot stop in the middle", st["stop"])
        self.assertIn("Nothing was stopped", st["stop"])
        self.assertIn("job_status { job: \"call-1\", wait: 25 }", st["stop"])
        self.assertIn("app_force_restart", st["stop"])
        self.assertIn("Unsaved work", st["stop"])
        self.assertNotIn("app_recover", st["stop"])

    def test_the_checkpoint_is_named(self):
        keep.mark_call_checkpoint("part_loft", "cp-12", t=1000.5)
        st, _ = self.j.status({"job": "call-1", "stop": True})
        self.assertIn("checkpoint cp-12", st["stop"])
        keep.clear_call_checkpoint()
        self.assertIsNone(keep.call_checkpoint(0))

    def test_an_old_checkpoint_is_not_named(self):
        keep.mark_call_checkpoint("part_loft", "cp-old", t=500.0)
        st, _ = self.j.status({"job": "call-1", "stop": True})
        self.assertNotIn("cp-old", st["stop"])

    def test_a_call_job_that_ended(self):
        self.j.write(json.dumps({"jsonrpc": "2.0", "id": 7, "result": {"content": [{"type": "text", "text": json.dumps({"body": "Loft"})}]}}))
        st, _ = self.j.status({"job": "call-1", "stop": True})
        self.assertEqual(st["status"], "done")
        self.assertIn("Nothing to stop", st["stop"])

    def test_stop_must_be_true_or_left_out(self):
        st, err = self.j.status({"job": "call-1", "stop": 1})
        self.assertTrue(err)
        self.assertEqual(st["error"]["code"], "invalid_input")


if __name__ == "__main__":
    unittest.main()
