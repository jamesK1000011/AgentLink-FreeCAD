# SPDX-License-Identifier: LGPL-2.1-or-later
# Efficiency design, round 2 (reliability):
#   E7  an answer that holds a control character or a lone surrogate goes out and is valid JSON.
#   E3  a queued call is answered busy BUSY_AFTER s after the hold began, not after it was queued.
#   E6  a call answered busy keeps its late answer: job_status lists it under late and gives it by id.
#   E2  after a quiet restart of the hidden FreeCAD, only calls it never took are sent again;
#       a changing call it took is answered with outcome unknown.
#   E10 the link tries a call once more by itself: a read, or a change not started, for a
#       transient cause; never a change whose outcome is unknown. The answer says retried: 1.
import io
import json
import os
import socket
import subprocess
import sys
import textwrap
import threading
import time
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from test_gui_link_dialog import gui_link  # noqa: E402

import agentlink_state  # noqa: E402
from agentlink import jobs, protocol  # noqa: E402
from agentlink.protocol import compact, retry_once_ok  # noqa: E402

ODD = "esc \x1b and lone \ud800 end"


def reply_with(text_body, mid=5):
    return {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": compact(text_body)}]}}


def line_for(name, mid=5, t=None):
    line = gui_link._Line(json.dumps({"jsonrpc": "2.0", "id": mid, "method": "tools/call", "params": {"name": name, "arguments": {}}}))
    line.ticket = {"state": "queued", "t": time.time() if t is None else t}
    return line


def bare_link():
    link = gui_link.Link.__new__(gui_link.Link)
    link.calls, link.front, link.going = [], None, False
    return link


class E7Wire(unittest.TestCase):
    def check_line(self, raw):
        msg = json.loads(raw.decode("utf-8"))  # valid UTF-8, valid JSON
        body = json.loads(msg["result"]["content"][0]["text"])
        self.assertEqual(body["name"], ODD)

    def test_strict_fails_and_wire_errors_sends(self):
        line = compact(reply_with({"name": ODD})) + "\n"
        with self.assertRaises(UnicodeEncodeError):
            line.encode("utf-8")
        self.assertIn("\\u001b", line)  # JSON escapes the control character itself
        buf = io.BytesIO()
        w = io.TextIOWrapper(buf, encoding="utf-8", errors=protocol.WIRE_ERRORS, newline="\n")
        w.write(line)
        w.flush()
        self.check_line(buf.getvalue())

    def test_window_socket_write(self):
        a, b = socket.socketpair()
        try:
            f = a.makefile("rw", encoding="utf-8", errors=gui_link.WIRE_ERRORS, newline="\n")
            link = bare_link()
            self.assertTrue(link._write(f, reply_with({"name": ODD})))
            b.settimeout(5)
            got = b""
            while not got.endswith(b"\n"):
                got += b.recv(65536)
            self.check_line(got)
        finally:
            a.close()
            b.close()

    def test_every_wire_opening_uses_wire_errors(self):
        for rel in ("agentlink/gui_link.py", "agentlink/server.py", "agentlink/supervise.py"):
            src = open(os.path.join(ROOT, rel), encoding="utf-8").read()
            for marker in ("makefile(", "os.fdopen(os.dup(1)", "subprocess.Popen([sys.executable, script"):
                start = 0
                while True:
                    i = src.find(marker, start)
                    if i < 0:
                        break
                    stmt = src[i:src.find("\n", i)]
                    self.assertIn("errors=WIRE_ERRORS", stmt, f"{rel}: {stmt}")
                    start = i + 1


class FakeClock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class Clocked(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self._had = gui_link._clock
        gui_link._clock = self.clock

    def tearDown(self):
        gui_link._clock = self._had

    def settle(self):
        time.sleep(0.12)  # the watch ticks every 0.01 s


class E3BusyFromHold(Clocked):
    def test_counted_from_the_hold_start(self):
        link, f = bare_link(), io.StringIO()
        link.calls.append({"id": 1, "name": "fem_run", "f": io.StringIO(), "answered": False})  # a long call in hand: waited for
        line = line_for("session_state", t=self.clock.t)
        th = link._arm_busy(line, f, after=10.0, tick=0.01)
        self.clock.t += 30  # queued 30 s behind the long call, no hold yet
        self.settle()
        self.assertEqual(f.getvalue(), "")
        link.front = {"kind": "dialog", "title": "Insert Radius", "buttons": ["OK"]}  # the hold begins now
        self.settle()
        self.clock.t += 5
        self.settle()
        self.assertEqual(f.getvalue(), "")  # 35 s after queued, 5 s into the hold: not yet
        self.clock.t += 5.1
        self.settle()
        self.assertEqual(f.getvalue(), "")  # due, but tried once more first (E10)
        self.assertEqual(line.retried, 1)
        self.clock.t += gui_link.RETRY_DELAY + 0.1
        th.join(2)
        reply = json.loads(f.getvalue())
        self.assertEqual(reply["result"]["_meta"], {"retried": 1})
        err = json.loads(reply["result"]["content"][0]["text"])["error"]
        self.assertEqual((err["code"], err["outcome"]), ("busy", "not_started"))
        self.assertIn("Insert Radius", err["message"])

    def test_hold_that_ends_starts_again(self):
        link, f = bare_link(), io.StringIO()
        line = line_for("session_state", t=self.clock.t)
        th = link._arm_busy(line, f, after=10.0, tick=0.01)
        link.front = {"kind": "menu", "title": "a menu"}
        self.settle()
        self.clock.t += 8
        self.settle()
        link.front = None  # closed before the time: the count ends
        self.settle()
        link.front = {"kind": "menu", "title": "a menu"}
        self.settle()
        self.clock.t += 8
        self.settle()
        self.assertEqual(f.getvalue(), "")  # 16 s since queued, but 8 s into this hold
        self.assertTrue(link._claim(line))
        th.join(1)


class E10Retry(Clocked):
    def test_rules(self):
        busy_ns = {"code": "busy", "outcome": "not_started"}
        self.assertTrue(retry_once_ok(False, {"code": "busy"}))  # a read
        self.assertTrue(retry_once_ok(False, {"code": "busy", "outcome": "unknown"}))  # a read changes nothing
        self.assertTrue(retry_once_ok(True, busy_ns))
        self.assertFalse(retry_once_ok(True, {"code": "busy", "outcome": "unknown"}))
        self.assertFalse(retry_once_ok(True, {"code": "busy"}))
        self.assertFalse(retry_once_ok(True, {"code": "busy", "outcome": "rolled_back"}))
        self.assertFalse(retry_once_ok(False, {"code": "invalid_input"}))
        self.assertFalse(retry_once_ok(True, {"code": "failed", "outcome": "not_started"}))
        self.assertFalse(retry_once_ok(False, None))

    def test_hold_closed_during_retry_runs_the_call(self):
        link, f = bare_link(), io.StringIO()
        link.front = {"kind": "dialog", "title": "Save changes?", "buttons": ["Save"]}
        line = line_for("make_box", t=self.clock.t)
        th = link._arm_busy(line, f, after=10.0, tick=0.01)
        self.settle()
        self.clock.t += 10.1
        self.settle()
        self.assertEqual(line.retried, 1)
        link.front = None  # the dialog closed before the call began
        self.settle()
        self.clock.t += gui_link.RETRY_DELAY + 1
        self.settle()
        self.assertEqual(f.getvalue(), "")
        self.assertTrue(link._claim(line))  # the GUI thread takes it; its answer says retried
        th.join(1)

    def test_retried_once_only(self):
        link, f = bare_link(), io.StringIO()
        link.front = {"kind": "menu", "title": "a menu"}
        line = line_for("session_state", t=self.clock.t)
        line.retried = 1  # tried once already
        th = link._arm_busy(line, f, after=10.0, tick=0.01)
        self.settle()
        self.clock.t += 10.1
        th.join(2)
        reply = json.loads(f.getvalue())
        self.assertEqual(reply["result"]["_meta"], {"retried": 1})

    def test_change_in_hand_past_its_time_says_unknown_and_is_not_retried(self):
        link, f = bare_link(), io.StringIO()
        call = {"id": 9, "name": "gui_input", "f": f, "answered": False, "changes": True}
        link.calls.append(call)
        link.expect("gui_input", 0.03, tick=0.01).join(2)
        reply = json.loads(f.getvalue())
        err = json.loads(reply["result"]["content"][0]["text"])["error"]
        self.assertEqual(err["outcome"], "unknown")
        self.assertNotIn("_meta", reply["result"])
        self.assertIn('job_status { job: "9" }', err["message"])
        self.assertFalse(retry_once_ok(True, err))


class StubServer:
    def __init__(self, link, handle):
        self.link, self._handle, self.outbox, self.tools, self.notify = link, handle, [], {}, None

    def handle(self, msg, client=None):
        return self._handle(msg)


class E6LateAnswers(unittest.TestCase):
    def setUp(self):
        self._state = getattr(agentlink_state, "link", None)
        self._guiup = getattr(gui_link.FreeCAD, "GuiUp", None)
        gui_link.FreeCAD.GuiUp = False

    def tearDown(self):
        agentlink_state.link = self._state
        if self._guiup is None:
            try:
                del gui_link.FreeCAD.GuiUp
            except AttributeError:
                pass
        else:
            gui_link.FreeCAD.GuiUp = self._guiup

    def run_link(self, handle, f, mid=7, name="session_state", line=None):
        link = bare_link()
        link.busy, link.in_call, link.busy_since, link.session = None, False, None, None
        link._ready = lambda: None
        link.server = StubServer(link, handle)
        agentlink_state.link = link
        line = line or line_for(name, mid=mid)
        link._run_one(line, f, object())
        return link

    def test_answered_busy_keeps_the_late_answer(self):
        f = io.StringIO()

        def handle(msg):
            c = agentlink_state.link.calls[-1]
            c["answered"], c["answeredAs"] = True, "busy"  # the busy watch answered it meanwhile
            return reply_with({"made": "Box", "name": ODD}, mid=msg["id"])

        link = self.run_link(handle, f)
        self.assertEqual(f.getvalue(), "")  # the agent had its busy answer already
        listed = jobs.status({})
        self.assertEqual(listed["late"], [{"id": 7, "tool": "session_state", "finished": listed["late"][0]["finished"], "answeredAs": "busy", "outcome": "done"}])
        self.assertNotIn("note", listed)
        got = jobs.status({"job": "7"})
        self.assertEqual((got["status"], got["late"], got["outcome"], got["answeredAs"]), ("done", True, "done", "busy"))
        self.assertEqual(got["result"]["made"], "Box")
        self.assertEqual(len(link.late), 1)

    def test_lost_connection_keeps_the_answer_and_errors_keep_outcome(self):
        class Gone(io.StringIO):
            def flush(self):
                raise OSError("closed")

        def handle(msg):
            return {"jsonrpc": "2.0", "id": msg["id"], "result": {"content": [{"type": "text", "text": compact({"error": {"code": "failed", "message": "x", "outcome": "rolled_back"}})}], "isError": True}}

        self.run_link(handle, Gone(), mid="a1", name="make_box")
        got = jobs.status({"job": "a1"})
        self.assertEqual((got["status"], got["outcome"], got["answeredAs"]), ("failed", "rolled_back", "lost"))
        self.assertEqual(got["error"]["code"], "failed")

    def test_ring_keeps_the_last_twenty(self):
        link = bare_link()
        for i in range(25):
            jobs.keep_late(link, i, "session_state", reply_with({"i": i}, mid=i), "busy")
        self.assertEqual(len(link.late), jobs.LATE_KEEP)
        self.assertEqual([e["id"] for e in jobs.late_list(link)], list(range(5, 25)))
        self.assertIsNone(jobs.late_get("2", link))
        self.assertEqual(jobs.late_get(24, link)["result"], {"i": 24})

    def test_unknown_id_is_still_not_found(self):
        agentlink_state.link = bare_link()
        with self.assertRaises(protocol.ToolError):
            jobs.status({"job": "nothing-here"})

    def test_retried_answer_carries_meta(self):
        f = io.StringIO()
        line = line_for("session_state", mid=3)
        line.retried = 1
        self.run_link(lambda msg: reply_with({"ok": 1}, mid=msg["id"]), f, line=line)
        self.assertEqual(json.loads(f.getvalue())["result"]["_meta"], {"retried": 1})


TOOK_HIDDEN = textwrap.dedent('''
    import json, os, sys, time
    home = os.environ["AGENTLINK_HOME"]
    json.dump({"pid": os.getpid(), "docs": []}, open(os.path.join(home, "hidden.json"), "w"))
    def say(m):
        sys.stdout.write(json.dumps(m) + "\\n")
        sys.stdout.flush()
    for line in sys.stdin:
        m = json.loads(line)
        if m.get("id") is None:
            continue
        if m.get("method") != "tools/call":
            say({"jsonrpc": "2.0", "id": m["id"], "result": {}})
            continue
        name = m["params"]["name"]
        open(os.path.join(home, "took.log"), "a").write(name + "\\n")
        # As protocol.serve_lines says it: before the call begins.
        say({"jsonrpc": "2.0", "method": "notifications/agentlink/took", "params": {"id": m["id"], "changes": name != "read_cut"}})
        once = os.path.join(home, name + ".once")
        if name == "settings_restart" or (name in ("change_cut", "read_cut") and not os.path.exists(once)):
            open(once, "w").write("1")
            json.dump({"why": "settings"}, open(os.path.join(home, ".hidden-restart"), "w"))
            if name == "settings_restart":
                say({"jsonrpc": "2.0", "id": m["id"], "result": {"content": [{"type": "text", "text": json.dumps({"rolledBackTo": "x"})}]}})
            os._exit(0)
        if name == "slow_change":
            time.sleep(0.3)
        say({"jsonrpc": "2.0", "id": m["id"], "result": {"content": [{"type": "text", "text": json.dumps({"ok": name})}]}})
''')


from test_supervise_unattended import Sup  # noqa: E402


class E2NoResend(Sup):
    def setUp(self):
        super().setUp()
        self.sup.kill()
        script = os.path.join(self.tmp, "took_hidden.py")
        open(script, "w").write(TOOK_HIDDEN)
        code = f"import sys; sys.path.insert(0, {ROOT!r}); from agentlink import supervise; supervise.run({script!r}, [])"
        self.sup = subprocess.Popen([sys.executable, "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=self.env, text=True, bufsize=1)

    def took(self):
        return open(os.path.join(self.home, "took.log")).read().split()

    def test_queued_behind_rollback_is_sent_once(self):
        q = self._lines()
        for mid, name in ((101, "settings_restart"), (102, "slow_change")):
            self.sup.stdin.write(json.dumps({"jsonrpc": "2.0", "id": mid, "method": "tools/call", "params": {"name": name, "arguments": {}}}) + "\n")
        self.sup.stdin.flush()
        got, end = {}, time.time() + 30
        while len(got) < 2 and time.time() < end:
            m = json.loads(q.get(timeout=max(0.1, end - time.time())))
            self.assertNotEqual(m.get("method"), "notifications/agentlink/took")  # never passed to the client
            if m.get("id") in (101, 102):
                self.assertNotIn(m["id"], got)  # one answer each
                got[m["id"]] = json.loads(m["result"]["content"][0]["text"])
        self.assertEqual(got[101], {"rolledBackTo": "x"})
        self.assertEqual(got[102], {"ok": "slow_change"})
        self.assertEqual(self.took().count("slow_change"), 1)

    def test_change_taken_then_cut_is_unknown_not_sent_again(self):
        err, out = self.call("change_cut", timeout=30)
        self.assertTrue(err)
        self.assertEqual((out["error"]["code"], out["error"]["outcome"]), ("failed", "unknown"))
        self.assertEqual(self.call("ping")[1], {"ok": "ping"})
        self.assertEqual(self.took().count("change_cut"), 1)

    def test_read_taken_then_cut_is_sent_again(self):
        err, out = self.call("read_cut", timeout=30)
        self.assertFalse(err)
        self.assertEqual(out, {"ok": "read_cut"})
        self.assertEqual(self.took().count("read_cut"), 2)


class E2ChildSaysTook(unittest.TestCase):
    def test_serve_lines_says_took_before_the_call_when_supervised(self):
        seen = []

        class T:
            def changes_for(self, a):
                return False

        class S:
            tools = {"session_state": T()}
            outbox = []
            notify = None

            def handle(self, msg):
                seen.append(("handle", msg["id"]))
                return {"jsonrpc": "2.0", "id": msg["id"], "result": {"content": [{"type": "text", "text": "{}"}]}}

        srv = S()
        srv.notify = lambda m: seen.append(("note", m))
        lines = iter([json.dumps({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "session_state", "arguments": {}}}) + "\n", ""])
        had = os.environ.get("AGENTLINK_SUPERVISED")
        os.environ["AGENTLINK_SUPERVISED"] = "1"
        try:
            protocol.serve_lines(srv, lambda: next(lines), lambda text: seen.append(("out", text)))
        finally:
            if had is None:
                os.environ.pop("AGENTLINK_SUPERVISED", None)
            else:
                os.environ["AGENTLINK_SUPERVISED"] = had
        self.assertEqual(seen[0], ("note", {"jsonrpc": "2.0", "method": protocol.TOOK, "params": {"id": 4, "changes": False}}))
        self.assertEqual(seen[1], ("handle", 4))


if __name__ == "__main__":
    unittest.main()


class RetriedInTheAnswer(unittest.TestCase):
    """Owner, 22 Nov: the retry mark is in the answer itself, not only in _meta."""

    def test_success_text_carries_retried(self):
        from agentlink import gui_link
        r = {"content": [{"type": "text", "text": json.dumps({"ok": True})}]}
        gui_link.mark_retried(r)
        self.assertEqual(json.loads(r["content"][0]["text"])["retried"], 1)

    def test_plain_text_stays(self):
        from agentlink import gui_link
        r = {"content": [{"type": "text", "text": "plain"}]}
        gui_link.mark_retried(r)
        self.assertEqual(r["content"][0]["text"], "plain")

    def test_busy_error_carries_retried(self):
        from agentlink import gui_link
        rep = gui_link.Link.busy_reply(7, "a dialog", outcome="not_started", retried=1) if hasattr(gui_link, "Link") else None
        if rep is None:
            self.skipTest("no Link class")
        body = json.loads(rep["result"]["content"][0]["text"])
        self.assertEqual(body["error"]["retried"], 1)
