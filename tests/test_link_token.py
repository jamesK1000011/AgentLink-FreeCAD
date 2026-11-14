# SPDX-License-Identifier: LGPL-2.1-or-later
# The window link's pairing token: made once with owner-only rights, read
# by the clients, checked on a connection's first line; the relay and the
# supervisor say hello first. Pure Python.
import json
import os
import socket
import stat
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agentlink import link_token  # noqa: E402


class Token(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="agentlink-tok-")
        self.old = os.environ.get("AGENTLINK_TOKEN_FILE")
        os.environ["AGENTLINK_TOKEN_FILE"] = os.path.join(self.d, "sub", "link-token")

    def tearDown(self):
        if self.old is None:
            os.environ.pop("AGENTLINK_TOKEN_FILE", None)
        else:
            os.environ["AGENTLINK_TOKEN_FILE"] = self.old

    def test_made_once_owner_only(self):
        self.assertIsNone(link_token.read())
        with self.assertRaises(link_token.Refused):
            link_token.client_pair(None)
        t = link_token.ensure()
        self.assertGreaterEqual(len(t), 40)
        self.assertEqual(link_token.ensure(), t)
        self.assertEqual(stat.S_IMODE(os.stat(link_token.path()).st_mode), 0o600)
        os.chmod(link_token.path(), 0o644)
        link_token.ensure()
        self.assertEqual(stat.S_IMODE(os.stat(link_token.path()).st_mode), 0o600)

    def _pair_over(self, server_secret, client_secret):
        """A client pairing with a window that holds server_secret, over a
        socket pair: (client error or None, window paired)."""
        a, b = socket.socketpair()
        fa = a.makefile("rw", encoding="utf-8", newline="\n")
        fb = b.makefile("rw", encoding="utf-8", newline="\n")
        out = {}

        def window():
            reply, w = link_token.window_greet(fb.readline(), server_secret)
            if reply is None:
                out["ok"] = False
                b.close()
                return
            fb.write(reply)
            fb.flush()
            out["ok"] = link_token.window_check(fb.readline(), server_secret, w)

        t = threading.Thread(target=window)
        t.start()
        err = None
        try:
            link_token.client_pair(fa, client_secret)
        except (link_token.Refused, OSError, ValueError) as e:
            err = e
            a.close()
        t.join(5)
        return err, out.get("ok")

    def test_both_sides_prove_it_and_the_secret_never_crosses(self):
        t = link_token.ensure()
        sent = []
        real = link_token._msg
        link_token._msg = lambda *x, **k: sent.append(real(*x, **k)) or sent[-1]
        try:
            err, ok = self._pair_over(t, t)
        finally:
            link_token._msg = real
        self.assertIsNone(err)
        self.assertTrue(ok)
        self.assertFalse(any(t in line for line in sent))

    def test_a_fake_window_is_found_out(self):
        # Something else took the port: it does not know the secret.
        t = link_token.ensure()
        err, _ = self._pair_over("not-the-secret", t)
        self.assertIsInstance(err, link_token.Refused)

    def test_a_client_without_the_secret_is_refused(self):
        t = link_token.ensure()
        err, ok = self._pair_over(t, "guess")
        self.assertIsInstance(err, link_token.Refused)
        self.assertFalse(ok)

    def test_junk_and_calls_before_pairing_are_refused(self):
        t = link_token.ensure()
        for line in ("POST / HTTP/1.1\n", json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "macro_run"}}),
                     json.dumps({"jsonrpc": "2.0", "method": link_token.HELLO, "params": {"nonce": "short"}})):
            self.assertEqual(link_token.window_greet(line, t), (None, None), line)
        self.assertEqual(link_token.window_greet(json.dumps({"jsonrpc": "2.0", "method": link_token.HELLO, "params": {"nonce": "a" * 32}}), ""), (None, None))

    def test_supervisor_pairs_first(self):
        from agentlink import supervise

        t = link_token.ensure()
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        got = []

        def serve():
            c, _ = srv.accept()
            f = c.makefile("rw", encoding="utf-8", newline="\n")
            reply, w = link_token.window_greet(f.readline(), t)
            f.write(reply)
            f.flush()
            got.append(link_token.window_check(f.readline(), t, w))
            call = json.loads(f.readline())
            f.write(json.dumps({"jsonrpc": "2.0", "id": call["id"], "result": {}}) + "\n")
            f.flush()

        threading.Thread(target=serve, daemon=True).start()
        old = supervise.WINDOW_PORT
        supervise.WINDOW_PORT = srv.getsockname()[1]
        try:
            w = supervise.Window(lambda line: None)
            self.assertTrue(w.call(json.dumps({"jsonrpc": "2.0", "id": 7, "method": "tools/call"})))
        finally:
            supervise.WINDOW_PORT = old
        self.assertEqual(got, [True])


if __name__ == "__main__":
    unittest.main()


class WindowSide(unittest.TestCase):
    """The window's reading of new connections (gui_link.Link._read) with a
    stand-in FreeCAD: squatters cannot lock the person's agent out."""

    def setUp(self):
        import types

        self.d = tempfile.mkdtemp(prefix="agentlink-win-")
        self.old = os.environ.get("AGENTLINK_TOKEN_FILE")
        os.environ["AGENTLINK_TOKEN_FILE"] = os.path.join(self.d, "link-token")
        fake = types.ModuleType("FreeCAD")
        fake.Console = types.SimpleNamespace(PrintWarning=lambda *a: None, PrintMessage=lambda *a: None)
        self._had = {k: sys.modules.get(k) for k in ("FreeCAD", "agentlink.tools", "agentlink.gui_link")}
        sys.modules["FreeCAD"] = fake
        if self._had["agentlink.tools"] is None:
            tools = types.ModuleType("agentlink.tools")
            tools.Session = tools.build_server = None
            sys.modules["agentlink.tools"] = tools
        sys.modules.pop("agentlink.gui_link", None)
        from agentlink import gui_link

        self.gl = gui_link
        self.link = self.gl.Link.__new__(self.gl.Link)
        self.link.token = link_token.ensure()
        self.link._pending, self.link._pending_lock = [], threading.Lock()
        import queue

        self.link.inbox = queue.Queue()

    def tearDown(self):
        if self.old is None:
            os.environ.pop("AGENTLINK_TOKEN_FILE", None)
        else:
            os.environ["AGENTLINK_TOKEN_FILE"] = self.old
        for k, v in self._had.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v

    def connect(self):
        a, b = socket.socketpair()
        threading.Thread(target=self.link._read, args=(b,), daemon=True).start()
        return a

    def test_squatters_are_pushed_out_and_the_agent_pairs(self):
        squat = [self.connect() for _ in range(4)]
        for s in squat:
            s.sendall(b"\n")  # a blank line before pairing ends it
        a = self.connect()
        f = a.makefile("rw", encoding="utf-8", newline="\n")
        link_token.client_pair(f, self.link.token)
        f.write(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "x"}}) + "\n")
        f.flush()
        line, _, _ = self.link.inbox.get(timeout=5)
        self.assertEqual(json.loads(line)["id"], 1)

    def test_idle_squatters_cannot_hold_the_slots(self):
        idle = [self.connect() for _ in range(6)]  # never send anything
        a = self.connect()
        f = a.makefile("rw", encoding="utf-8", newline="\n")
        link_token.client_pair(f, self.link.token)
        self.assertLessEqual(len(self.link._pending), 4)
        del idle

    def test_long_or_blank_lines_before_pairing_end_it(self):
        for junk in (b"x" * 5000 + b"\n", b"\n"):
            a = self.connect()
            a.sendall(junk)
            a.settimeout(3)
            self.assertEqual(a.recv(10), b"")  # closed
