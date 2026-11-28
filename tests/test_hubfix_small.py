# SPDX-License-Identifier: LGPL-2.1-or-later
# Small faults seen live, without FreeCAD: a batch { to } reply keeps the
# batch's own note (where it stopped and how to go on) beside the file's;
# background: true is refused by what the call is — a read inside a batch,
# a read that writes a file inside a batch, a change.
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import batchrec, jobs, paths  # noqa: E402
from agentlink.protocol import Server, Tool  # noqa: E402


class BatchTo(unittest.TestCase):
    def test_a_stopped_batch_keeps_its_note(self):
        got = {"results": [{"tool": "pd_pad", "ok": True, "result": {"feature": "Pad", "health": {"recompute": "ok", "fault": False}}},
                           {"tool": "sketch_state", "ok": False, "error": {"code": "not_found", "message": "no sketch X"}}],
               "ran": 2, "notRun": 3, "next": 7, "heavy": {"index": 7, "tool": "wall_read", "arguments": {}},
               "note": "Stopped before calls.7 (wall_read): a heavy read … then batch again with the calls from index 8 on."}
        out = batchrec.to_reply(got, 5, "run.json", 1234)
        self.assertEqual(out["note"], got["note"], "how to go on is still said")
        self.assertEqual(out["toNote"], batchrec.TO_NOTE)
        self.assertEqual((out["next"], out["notRun"], out["heavy"]["tool"]), (7, 3, "wall_read"))
        self.assertEqual(out["written"], {"path": "run.json", "bytes": 1234})
        self.assertEqual(out["results"], [{"i": 5, "tool": "pd_pad", "ok": True, "health": {"recompute": "ok", "fault": False}},
                                          {"i": 6, "tool": "sketch_state", "ok": False, "error": "not_found: no sketch X"}])

    def test_a_budget_stop_keeps_its_note_too(self):
        got = {"results": [], "ran": 0, "notRun": 4, "next": 0, "note": "Stopped after 61 s (budget 60 s): … batch again with the calls from index 0 on."}
        out = batchrec.to_reply(got, 0, "r.json", 2)
        self.assertIn("budget", out["note"])
        self.assertIn("toNote", out)

    def test_a_whole_run_says_the_files_note(self):
        out = batchrec.to_reply({"results": [{"tool": "a", "ok": True, "result": {}, "written": {"path": "a.json"}}], "ran": 1}, 0, "r.json", 2)
        self.assertEqual(out["note"], batchrec.TO_NOTE)
        self.assertNotIn("toNote", out)
        self.assertEqual(out["results"][0]["written"], "a.json")


def tool(name, changes=False, reads=None):
    t = Tool(name, "does", {"type": "object", "properties": {"action": {"type": "string"}, "path": {"type": "string"}}}, lambda a: {"ok": 1}, changes=changes)
    if reads:
        t.reads = reads
    return t


class Background(unittest.TestCase):
    def setUp(self):
        self.added = "mesh_writer_t"
        paths.WRITERS.add(self.added)

    def tearDown(self):
        paths.WRITERS.discard(self.added)

    def test_what_is_said_by_what_the_call_is(self):
        writer, read, change, shot = tool(self.added), tool("plain_read_t"), tool("maker_t", changes=True), tool("view_shot_t")
        # A file writer changes nothing in the document: a job on its own.
        self.assertTrue(jobs.eligible(writer, {}))
        self.assertTrue(jobs.writes_file(writer, {}))
        self.assertTrue(jobs.writes_file(read, {"action": "export"}))
        self.assertFalse(jobs.writes_file(read, {}))
        w = jobs.background_refusal(writer, {}, True)
        self.assertIn("writes a file", w)
        self.assertIn("leave background out", w)
        self.assertIn("job_status", w)  # on its own: the file is whole only when the job is done
        r = jobs.background_refusal(read, {}, True)
        self.assertIn("call plain_read_t on its own with background: true", r)
        self.assertNotIn("writes a file", r)
        # A change is never a job, in a batch or out: not told to call it on its own.
        for in_batch in (True, False):
            c = jobs.background_refusal(change, {}, in_batch)
            self.assertIn("changes the document", c)
            self.assertIn("cannot run as a job", c)
            self.assertNotIn("on its own with background", c)
        self.assertIn("cannot run as a job", jobs.background_refusal(shot, {}, False))
        self.assertIn("Leave background out", jobs.background_refusal(shot, {}, True))

    def test_through_the_server_inside_a_batch(self):
        srv = Server("t", "1", [tool(self.added), tool("maker_t", changes=True)])
        srv.session = type("S", (), {"batch_now": {"i": 0, "n": 1}, "doc": None})()

        def call(name):
            r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": {"background": True}}})["result"]
            self.assertTrue(r.get("isError"))
            return r["content"][0]["text"]

        self.assertIn("writes a file", call(self.added))
        self.assertIn("changes the document", call("maker_t"))


if __name__ == "__main__":
    unittest.main()
