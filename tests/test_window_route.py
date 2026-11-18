# SPDX-License-Identifier: LGPL-2.1-or-later
# The supervisor's window-first routing: a tool call goes to the FreeCAD
# window's link when one listens, and to the hidden FreeCAD when none does.
import json
import os
import socket
import sys
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agentlink import supervise  # noqa: E402

# A token of its own, so the supervisor says hello first, as on the Mac.
import tempfile  # noqa: E402

_TOKEN_DIR = tempfile.mkdtemp(prefix="agentlink-token-")
os.environ["AGENTLINK_TOKEN_FILE"] = os.path.join(_TOKEN_DIR, "link-token")
with open(os.environ["AGENTLINK_TOKEN_FILE"], "w") as _f:
    _f.write("route-test-token\n")


from agentlink import link_token  # noqa: E402


def _pair(f):
    """The window's side of the pairing, as the real window does it."""
    reply, w = link_token.window_greet(f.readline(), "route-test-token")
    f.write(reply)
    f.flush()
    assert link_token.window_check(f.readline(), "route-test-token", w)


def _call(f):
    """Paired, then the next line (a call)."""
    _pair(f)
    return f.readline()


class WindowRoute(unittest.TestCase):
    def test_no_window_means_hidden(self):
        supervise.WINDOW_PORT = _free_port()
        w = supervise.Window(lambda line: self.fail("nothing should be written"))
        self.assertFalse(w.call(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call"})))

    def test_window_answers(self):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        supervise.WINDOW_PORT = srv.getsockname()[1]

        def serve():
            conn, _ = srv.accept()
            f = conn.makefile("rw", encoding="utf-8", newline="\n")
            _pair(f)
            for line in f:
                mid = json.loads(line)["id"]
                f.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"}) + "\n")
                f.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": {"where": "window"}}) + "\n")
                f.flush()

        threading.Thread(target=serve, daemon=True).start()
        got = []
        w = supervise.Window(got.append)
        self.assertTrue(w.call(json.dumps({"jsonrpc": "2.0", "id": 7, "method": "tools/call"})))
        self.assertEqual(len(got), 2)
        self.assertEqual(json.loads(got[1])["result"]["where"], "window")
        self.assertTrue(w.call(json.dumps({"jsonrpc": "2.0", "id": 8, "method": "tools/call"})))
        srv.close()

    def test_window_gone_is_said_once_not_answered_by_the_hidden_one(self):
        """The window answered, then went (the person quit, a crash): the
        next call is answered with that, not run on the hidden FreeCAD's
        empty document; the one after goes there."""
        import tempfile

        mark = os.path.join(tempfile.mkdtemp(), "mark")
        os.environ["AGENTLINK_RESTART_MARK"] = mark

        def clear_own():
            # This test's mark by its own path: the env may name the next
            # test's by the time this thread gets here.
            try:
                os.remove(mark)
            except OSError:
                pass

        try:
            srv = socket.socket()
            srv.bind(("127.0.0.1", 0))
            srv.listen(1)
            supervise.WINDOW_PORT = srv.getsockname()[1]

            def once():
                conn, _ = srv.accept()
                f = conn.makefile("rw", encoding="utf-8", newline="\n")
                line = _call(f)
                f.write(json.dumps({"jsonrpc": "2.0", "id": json.loads(line)["id"], "result": {}}) + "\n")
                f.flush()
                conn.close()
                srv.close()

            threading.Thread(target=once, daemon=True).start()
            got = []
            w = supervise.Window(got.append)
            self.assertTrue(w.call(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call"})))
            # The connection went with the window, mid-session, no restart mark.
            self.assertTrue(w.call(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call"})))
            self.assertTrue(json.loads(got[-1])["result"]["isError"])
            self.assertIn("may or may not", got[-1])
            self.assertFalse(w.call(json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call"})))
        finally:
            os.environ.pop("AGENTLINK_RESTART_MARK", None)

    def _watch(self, w, beat, alive=lambda p: False):
        from agentlink import window_watch

        w.watch = window_watch.Watch(lambda: dict(beat["v"]), alive=alive)
        return w.watch

    def test_restarting_window_is_waited_for(self):
        """A restart in hand (no mark file, finding 52): the call waits for
        the first heartbeat of a new pid that pairs, instead of going to the
        hidden FreeCAD."""
        import time

        port = _free_port()
        supervise.WINDOW_PORT = port
        beat = {"v": {"pid": 111, "t": time.time(), "pairing": 1}}

        def late():
            time.sleep(1.2)
            srv = socket.socket()
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", port))
            srv.listen(1)
            beat["v"] = {"pid": 222, "t": time.time(), "pairing": 1}
            conn, _ = srv.accept()
            f = conn.makefile("rw", encoding="utf-8", newline="\n")
            _pair(f)
            for line in f:
                f.write(json.dumps({"jsonrpc": "2.0", "id": json.loads(line)["id"], "result": {"where": "window"}}) + "\n")
                f.flush()

        threading.Thread(target=late, daemon=True).start()
        got = []
        t0 = time.time()
        w = supervise.Window(got.append)
        self._watch(w, beat).expect(111, why="agentlink_update")
        ok = w.call(json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call"}))
        self.assertTrue(ok, got)
        self.assertGreater(time.time() - t0, 1.0)
        self.assertEqual(json.loads(got[0])["result"]["where"], "window")
        self.assertFalse(w.watch.pending())

    def test_restart_given_up_is_said_once(self):
        from agentlink import window_watch

        supervise.WINDOW_PORT = _free_port()
        got = []
        w = supervise.Window(got.append)
        beat = {"v": {"pid": 111, "t": 0, "pairing": 1}}
        self._watch(w, beat).expect(111, t=0.0)  # long ago: past GIVE_UP
        self.assertTrue(w.call(json.dumps({"jsonrpc": "2.0", "id": 4, "method": "tools/call"})))
        self.assertIn("did not come back", got[-1])
        # Said once: the hidden FreeCAD takes the next call.
        self.assertFalse(w.call(json.dumps({"jsonrpc": "2.0", "id": 5, "method": "tools/call"})))
        self.assertGreater(window_watch.GIVE_UP, 60)

    def test_dropped_connection_waits_for_the_restart(self):
        """The window answers app_restart "restarting" and quits under a
        kept connection: the next call waits for the new pid and goes to the
        window once it is back, not to the hidden one."""
        import time

        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        supervise.WINDOW_PORT = port
        beat = {"v": {"pid": 111, "t": time.time(), "pairing": 1}}

        def first():
            conn, _ = srv.accept()
            f = conn.makefile("rw", encoding="utf-8", newline="\n")
            line = _call(f)
            body = json.dumps({"restarting": True})
            f.write(json.dumps({"jsonrpc": "2.0", "id": json.loads(line)["id"], "result": {"content": [{"type": "text", "text": body}]}}) + "\n")
            f.flush()
            srv.close()
            time.sleep(0.3)
            f.close()
            conn.close()
            time.sleep(1.0)
            again = socket.socket()
            again.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            again.bind(("127.0.0.1", port))
            again.listen(1)
            beat["v"] = {"pid": 222, "t": time.time(), "pairing": 1}
            c2, _ = again.accept()
            g = c2.makefile("rw", encoding="utf-8", newline="\n")
            _pair(g)
            for ln in g:
                g.write(json.dumps({"jsonrpc": "2.0", "id": json.loads(ln)["id"], "result": {"where": "window"}}) + "\n")
                g.flush()

        threading.Thread(target=first, daemon=True).start()
        got = []
        w = supervise.Window(got.append)
        self._watch(w, beat)
        real = supervise.heartbeat_any
        supervise.heartbeat_any = lambda: dict(beat["v"])
        try:
            self.assertTrue(w.call(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "app_restart", "arguments": {}}})))
        finally:
            supervise.heartbeat_any = real
        self.assertTrue(w.watch.pending())
        time.sleep(0.6)
        self.assertTrue(w.call(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call"})))
        self.assertEqual(json.loads(got[-1])["result"]["where"], "window")


_USED = set()


def _free_port():
    """A port no test here has had yet: a server thread of an earlier test
    can still hold the one the system offers again."""
    while True:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        p = s.getsockname()[1]
        s.close()
        if p not in _USED:
            _USED.add(p)
            return p


if __name__ == "__main__":
    unittest.main()
