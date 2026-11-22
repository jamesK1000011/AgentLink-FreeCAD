# SPDX-License-Identifier: LGPL-2.1-or-later
# Usage kept on this side: calls and lists metered, the report read back.
import json
import os
import struct
import sys
import tempfile
import time
import unittest
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentlink import protocol, usage  # noqa: E402
from agentlink.protocol import Server, Tool  # noqa: E402


def png(w, h):
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IEND", b"")


class Usage(unittest.TestCase):
    def test_estimates(self):
        self.assertEqual(usage.est_tokens(350), 100)
        self.assertEqual(usage.png_tokens(png(750, 100)), 100)
        self.assertEqual(usage.png_tokens(png(3136, 1568)), round(1568 * 784 / 750))
        self.assertEqual(usage.png_tokens(b"nope"), 0)

    def test_meter_and_report(self):
        where = tempfile.mkdtemp()
        tools = [Tool("echo", "Say it back.", {"type": "object", "properties": {"x": {"type": "string"}}}, lambda a: {"x": a.get("x"), "_png": png(750, 100)}),
                 Tool("fail", "Refuse.", {"type": "object", "properties": {}}, lambda a: (_ for _ in ()).throw(protocol.ToolError("invalid_input", "no")))]
        srv = Server("t", "1", tools, "be brief")
        srv.meter = usage.Meter(where)
        srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        for _ in range(3):
            srv.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "echo", "arguments": {"x": "a" * 700}}})
        srv.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "fail", "arguments": {}}})
        t = srv.meter.session_totals()
        self.assertEqual(t["calls"], 4)
        self.assertEqual(t["errors"], 1)
        self.assertEqual(t["imageTokens"], 300)
        self.assertEqual(t["byTool"][0]["tool"], "echo")
        self.assertEqual(t["toolList"]["tools"], 2)
        r = usage.report(1, where)
        self.assertEqual(r["calls"], 4)
        self.assertEqual(r["sessions"], 1)
        self.assertGreater(r["toolListTokens"], 0)
        self.assertEqual(r["perDay"][0]["calls"], 4)
        json.dumps(r)


def _tools():
    def find(a):
        if "nothing" in str(a.get("words")):
            return {"tools": [{"tool": "make_sphere"}]}
        return {"tools": [{"tool": "make_box"}, {"tool": "make_cyl"}]}

    def batch(a):
        return {"results": [], "undone": 2} if a.get("rollback") else {"results": []}

    def bg(a):
        return {"job": "j-7", "status": "running"}

    def fail(a):
        raise protocol.ToolError("not_found", "No file " + os.path.join(os.path.expanduser("~"), "secret", "plan.FCStd") + " and none at /opt/x/y.step")

    obj = {"type": "object"}
    return [Tool("tool_find", "Find.", obj, find), Tool("tool_groups", "Groups.", obj, lambda a: {"ok": True}), Tool("make_box", "Box.", obj, lambda a: {"ok": 1}, group="part"),
            Tool("make_cyl", "Cyl.", obj, lambda a: {"ok": 1}, group="part"), Tool("history_undo", "Undo.", obj, lambda a: {"ok": 1}), Tool("batch", "Batch.", obj, batch),
            Tool("slow_read", "Read.", obj, bg, group="mesh"), Tool("fail", "Refuse.", obj, fail, group="mesh"),
            Tool("dialog_answer", "Press.", obj, lambda a: {"pressed": a.get("button")})]


class Log(unittest.TestCase):
    """The usage log at the MCP layer (private records: usage-log-2026-11-18.md)."""

    def setUp(self):
        self.where = tempfile.mkdtemp()
        self.home_was = os.environ.get("AGENTLINK_HOME")
        os.environ["AGENTLINK_HOME"] = tempfile.mkdtemp()  # watchdog.log is read from here
        self.srv = Server("t", "1", _tools())
        self.srv.meter = usage.Meter(self.where, version="9.9.9")
        self.n = 0

    def tearDown(self):
        if self.home_was is None:
            os.environ.pop("AGENTLINK_HOME", None)
        else:
            os.environ["AGENTLINK_HOME"] = self.home_was

    def call(self, name, args=None, meta=None):
        self.n += 1
        p = {"name": name, "arguments": args or {}}
        if meta:
            p["_meta"] = meta
        return self.srv.handle({"jsonrpc": "2.0", "id": self.n, "method": "tools/call", "params": p})

    def rows(self):
        out = []
        for n in os.listdir(self.where):
            with open(os.path.join(self.where, n), encoding="utf-8") as f:
                out += [json.loads(x) for x in f]
        return out

    def test_rows_marks_and_report(self):
        self.srv.handle({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {}})
        self.call("tool_find", {"words": "box shape"})
        self.call("make_box", {"length": 10})
        self.call("make_box", {"length": 12})  # a retry: same tool soon, other arguments
        self.call("tool_find", {"words": "nothing used"})
        self.call("tool_groups", {"enable": ["mesh"]})
        self.call("fail", {"path": "x"})
        self.call("history_undo")
        self.call("batch", {"calls": [{"tool": "make_cyl", "arguments": {"r": 1}}, {"tool": "make_box"}], "rollback": True})
        self.call("slow_read")
        rows = self.rows()
        jobs = [r for r in rows if r["kind"] == "job"]
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["why"], "initialize")
        self.assertEqual(jobs[0]["agentlink"], "9.9.9")
        self.assertEqual(jobs[0]["mode"], "headless")
        calls = [r for r in rows if r["kind"] == "call"]
        self.assertEqual([r["n"] for r in calls], list(range(1, 10)))
        self.assertTrue(all(r["job"] == jobs[0]["job"] for r in calls))
        by = {(r["tool"], r["n"]): r for r in calls}
        self.assertEqual(by[("tool_find", 1)]["find"], {"words": ["box shape"], "hits": ["make_box", "make_cyl"]})
        self.assertTrue(by[("make_box", 3)].get("retry"))
        self.assertNotIn("retry", by[("make_box", 2)])
        self.assertIn("gap", by[("make_box", 2)])
        self.assertEqual(by[("make_box", 2)]["grp"], "part")
        self.assertEqual(by[("tool_groups", 5)]["groups"], {"enable": ["mesh"]})
        self.assertEqual(by[("fail", 6)]["err"], "not_found")
        self.assertEqual(by[("fail", 6)]["why"], "No file ~/<path>.FCStd and none at <path>.step")
        self.assertEqual(by[("history_undo", 7)]["undo"], "undo")
        b = by[("batch", 8)]
        self.assertEqual((b["steps"], b["rollback"], b["batch"]), (["make_cyl", "make_box"], 2, jobs[0]["job"] + "-b1"))
        self.assertEqual(by[("slow_read", 9)]["background"], "j-7")
        self.assertGreater(by[("make_box", 2)]["bytes"], 0)
        # Privacy: no argument value and no full user path is on disk.
        with open(os.path.join(self.where, os.listdir(self.where)[0]), encoding="utf-8") as f:
            text = f.read()
        self.assertNotIn(os.path.expanduser("~") + os.sep, text)
        self.assertNotIn('"length"', text)
        self.assertNotIn("/opt/x", text)
        r = usage.log_report(1, self.where)
        self.assertEqual(r["calls"], 9)
        self.assertEqual(r["toolFind"]["searches"], 2)
        self.assertEqual(r["toolFind"]["used"], 1)
        self.assertEqual(r["toolFind"]["unused"], [{"words": ["nothing used"], "hits": ["make_sphere"]}])
        self.assertEqual(r["retries"]["count"], 1)
        self.assertEqual(r["errorsByTool"][0]["tool"], "fail")
        self.assertEqual(r["errorsByTool"][0]["reasons"][0]["count"], 1)
        self.assertEqual(r["groupSwitches"]["enableDisable"], 1)
        self.assertEqual(r["undos"], {"undo": 1})
        self.assertEqual(r["rollbacks"], {"count": 1, "stepsUndone": 2})
        self.assertEqual(r["background"]["handoffs"], 1)
        self.assertEqual(r["lastJobs"][0]["steps"], 11)  # 9 calls, and the batch's 2 steps
        self.assertEqual(r["modes"], {"headless": 1})
        json.dumps(r)

    def test_a_retry_after_a_batch_row(self):
        """Live 73: a refused call in one batch, the same tool again in the
        next batch with changed arguments: a retry (the batch's own row
        between them does not count)."""
        m = self.srv.meter
        m.call("object_get", "{}", '{"error":{"code":"not_found","message":"Box001: no such object"}}', error="not_found", args={"object": "Box001"})
        m.call("batch", "{}", "{}", args={"calls": [{"tool": "object_get"}]})
        m.call("object_get", "{}", "{}", args={"object": "Box"})
        r = usage.log_report(1, self.where)
        self.assertEqual((r["retries"]["count"], r["retries"]["afterError"]), (1, 1))
        self.assertEqual(r["errorsByTool"][0]["reasons"], [{"why": "<name>: no such object", "count": 1}])

    def test_error_words_keep_no_label_or_file_name(self):
        """Fault 72: the log keeps the error code and cleaned words: no
        document label, no file name, home paths as ~."""
        home = os.path.expanduser("~")
        cases = {
            "No file " + home + "/secret/plan.FCStd": "No file ~/<path>.FCStd",
            "asm_joint failed: 'M8x25-Screw219'": "asm_joint failed: '<name>'",
            "Pad002 is not a solid in \"Rear bracket\"": "<name> is not a solid in \"<name>\"",
            "export: lid.stl is there; overwrite: true": "export: <file>.stl is there; overwrite: true",
            "at /Users/someone/Desktop/a.step": "at ~/<path>.step",
            "at /opt/freecad/lib/x.so": "at <path>.so",
            "wait: seconds to wait for it, 0 to 30.": "wait: seconds to wait for it, 0 to 30.",
            "op: one of fuse, cut, common": "op: one of fuse, cut, common",
        }
        for raw, want in cases.items():
            self.assertEqual(usage.clean_error(raw), want, raw)
        self.assertEqual(len(usage.clean_error("x" * 999)), usage.WORDS_MAX)

    def test_error_rows_on_disk_and_in_the_report(self):
        m = self.srv.meter
        msg = "Body 'Secret lid' and Pad004 in " + os.path.expanduser("~") + "/Clients/acme/lid.FCStd: not a solid"
        m.call("part_check", "{}", json.dumps({"error": {"code": "invalid_state", "message": msg}}), error="invalid_state", ms=12)
        with open(os.path.join(self.where, os.listdir(self.where)[0]), encoding="utf-8") as f:
            text = f.read()
        for leak in ("Secret lid", "Pad004", "acme", "lid.FCStd", os.path.expanduser("~") + os.sep):
            self.assertNotIn(leak, text)
        row = [json.loads(x) for x in text.splitlines() if '"part_check"' in x][-1]
        self.assertEqual((row["tool"], row["err"], row["ms"]), ("part_check", "invalid_state", 12))
        self.assertEqual(row["why"], "Body '<name>' and <name> in ~/<path>.FCStd: not a solid")
        r = usage.log_report(1, self.where)
        e = [x for x in r["errorsByTool"] if x["tool"] == "part_check"][0]
        self.assertEqual(e["codes"], {"invalid_state": 1})
        self.assertEqual(e["reasons"][0]["why"], row["why"])

    def test_old_rows_are_cleaned_in_the_report(self):
        os.makedirs(self.where, exist_ok=True)
        day = time.strftime("%Y-%m-%d")
        with open(os.path.join(self.where, day + ".jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.time(), "s": "x", "kind": "call", "tool": "old_tool", "job": "j", "n": 1, "in": 2, "out": 2, "bytes": 2, "tok": 1,
                                "img": 0, "ms": 1, "err": "not_found", "why": "Bracket007: no such object in 'Kitchen plan'"}) + "\n")
        r = usage.log_report(1, self.where)
        e = [x for x in r["errorsByTool"] if x["tool"] == "old_tool"][0]
        self.assertEqual(e["reasons"][0]["why"], "<name>: no such object in '<name>'")

    def test_addons_in_the_mod_folder(self):
        """Live 71: every add-on beside this one in Mod, with its version
        and commit, not only those the ext loader imported."""
        mod = tempfile.mkdtemp()
        for name, ver in (("AgentLink", "0.3.0"), ("Tutor", "0.2.1"), ("ScanRulerFC", "1.0.0")):
            os.makedirs(os.path.join(mod, name))
            with open(os.path.join(mod, name, "package.xml"), "w", encoding="utf-8") as f:
                f.write(f"<package><name>{name}</name><version>{ver}</version><date>2026-11-18</date></package>")
        os.makedirs(os.path.join(mod, "Tutor", ".git", "refs", "heads"))
        with open(os.path.join(mod, "Tutor", ".git", "HEAD"), "w") as f:
            f.write("ref: refs/heads/main\n")
        with open(os.path.join(mod, "Tutor", ".git", "refs", "heads", "main"), "w") as f:
            f.write("c79b40d0123456789\n")
        os.makedirs(os.path.join(mod, "NotAnAddon"))
        here, usage._here = usage._here, lambda: os.path.join(mod, "AgentLink")
        usage._ADDONS.clear()
        try:
            got = usage._addons()
        finally:
            usage._here = here
            usage._ADDONS.clear()
        self.assertEqual(got, {"AgentLink": {"version": "0.3.0", "date": "2026-11-18"}, "ScanRulerFC": {"version": "1.0.0", "date": "2026-11-18"},
                               "Tutor": {"version": "0.2.1", "date": "2026-11-18", "commit": "c79b40d"}})

    def test_a_socket_thread_call_is_logged(self):
        self.srv.handle_light({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "make_box", "arguments": {}}})
        self.assertEqual([r["tool"] for r in self.rows() if r["kind"] == "call"], ["make_box"])

    def test_a_pause_starts_a_new_job(self):
        m = self.srv.meter
        self.call("make_box")
        m.last = (m.last[0] - usage.JOB_GAP - 5, m.last[1], m.last[2])
        self.call("make_box")
        jobs = [r for r in self.rows() if r["kind"] == "job"]
        self.assertEqual([j["why"] for j in jobs], ["start", "pause"])
        calls = [r for r in self.rows() if r["kind"] == "call"]
        self.assertNotEqual(calls[0]["job"], calls[1]["job"])
        self.assertEqual(calls[1]["n"], 1)

    def test_dialogs(self):
        m = self.srv.meter
        T = time.time() - 1000
        d = {"class": "QMessageBox", "title": "Save?", "text": "Save " + os.path.expanduser("~/x.FCStd") + "?", "buttons": ["Yes", "No"], "since": T + 100.0}
        m.dialog_seen(d, now=T + 100.0)
        m.refused("make_box", "{}", '{"error":{"code":"invalid_state","message":"Blocked by a dialog"}}', "invalid_state")
        m.dialog_seen(d, now=T + 101.0)  # the same dialog: one record
        self.call("dialog_answer", {"button": "No"})
        m.dialog_seen(None, now=T + 104.0)
        m.dialog_seen(dict(d, title="Other", since=T + 200.0), now=T + 200.0)
        m.dialog_pressed("agentlink")
        m.dialog_seen(None, now=T + 201.0)
        m.dialog_seen(dict(d, title="Third", since=T + 300.0), now=T + 300.0)
        m.dialog_seen(None, now=T + 310.0)
        ds = [r for r in self.rows() if r["kind"] == "dialog"]
        self.assertEqual([(x["title"], x["by"], x["secs"], x["blocked"]) for x in ds], [("Save?", "agent", 4.0, 1), ("Other", "agentlink", 1.0, 0), ("Third", "person", 10.0, 0)])
        self.assertEqual(ds[0]["text"], "Save ~/<path>.FCStd?")
        r = usage.log_report(1, self.where)["dialogs"]
        self.assertEqual((r["count"], r["callsBlocked"], r["answeredBy"]), (3, 1, {"agent": 1, "agentlink": 1, "person": 1}))

    def test_clean(self):
        self.assertEqual(usage.clean(os.path.expanduser("~") + "/a/b.step"), "~/a/b.step")
        self.assertEqual(usage.clean("at /usr/lib/freecad/x.so now"), "at <path> now")
        self.assertEqual(usage.clean("ratio 3/4 and a/b"), "ratio 3/4 and a/b")
        self.assertEqual(len(usage.clean("x" * 999)), usage.WORDS_MAX)


class Progress(unittest.TestCase):
    """The echo's step text as notifications/progress: sent only with a
    progressToken, before the reply, and the answer is the same either way."""

    def run_lines(self, msgs):
        tools = [Tool("step", "Step.", {"type": "object"}, lambda a: (protocol.progress("Agent: Pad 5 mm"), protocol.progress("Agent: recompute"), {"ok": 1})[-1])]
        srv = Server("t", "1", tools)
        lines = iter([json.dumps(m) + "\n" for m in msgs] + [""])
        out = []
        protocol.serve_lines(srv, lambda: next(lines), out.append)
        return [json.loads(x) for x in out]

    def test_progress(self):
        call = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "step", "arguments": {}}}
        plain = self.run_lines([call])
        self.assertEqual(len(plain), 1)  # no token: no notification
        withtok = self.run_lines([dict(call, params={"name": "step", "arguments": {}, "_meta": {"progressToken": "p1"}})])
        self.assertEqual([m.get("method") for m in withtok], ["notifications/progress", "notifications/progress", None])
        self.assertEqual(withtok[0]["params"], {"progressToken": "p1", "progress": 1, "message": "Agent: Pad 5 mm"})
        self.assertEqual(withtok[1]["params"]["progress"], 2)
        # The answer is the same: progress adds no tokens to it.
        a, b = plain[0]["result"], withtok[-1]["result"]
        strip = lambda r: json.loads(r["content"][0]["text"]).get("ok")  # noqa: E731 (ms may differ)
        self.assertEqual((strip(a), len(a["content"]), a.get("isError")), (strip(b), len(b["content"]), b.get("isError")))
        self.assertNotIn("progress", b["content"][0]["text"])
        self.assertFalse(protocol.progress("outside a call"))  # no call in hand: nothing sent

    def test_the_echo_sends_its_status_words(self):
        """echo.say: the status bar's words, the same text as progress."""
        import types

        from agentlink import echo

        shown = []
        bar = types.SimpleNamespace(showMessage=lambda text, ms: shown.append(text))
        gui = types.ModuleType("FreeCADGui")
        gui.getMainWindow = lambda: types.SimpleNamespace(statusBar=lambda: bar)
        had, cap = sys.modules.get("FreeCADGui"), echo.caption
        sys.modules["FreeCADGui"] = gui
        echo.caption = lambda *a: None
        try:
            sent = []
            srv = Server("t", "1", [Tool("pad", "Pad.", {"type": "object"}, lambda a: {"said": echo.say("Pad 5 mm", where=" (in Part)")})])
            srv.notify = sent.append
            srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "pad", "arguments": {}, "_meta": {"progressToken": 7}}})
            srv.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "pad", "arguments": {}}})
        finally:
            echo.caption = cap
            if had is None:
                sys.modules.pop("FreeCADGui", None)
            else:
                sys.modules["FreeCADGui"] = had
        self.assertEqual(shown, ["Agent (in Part): Pad 5 mm"] * 2)
        self.assertEqual([m["params"] for m in sent], [{"progressToken": 7, "progress": 1, "message": "Agent (in Part): Pad 5 mm"}])


if __name__ == "__main__":
    unittest.main()
