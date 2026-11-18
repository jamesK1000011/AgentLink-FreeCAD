# SPDX-License-Identifier: LGPL-2.1-or-later
"""Live 18 Nov (93): with the window closed by the person, nothing could open
it again; app_open starts it in the background (open -g) and waits for its link."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from agentlink import supervise as S  # noqa: E402


class AppOpen(unittest.TestCase):
    def test_detects_alone_and_batch(self):
        self.assertTrue(S._is_app_open('{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"app_open","arguments":{}}}'))
        self.assertTrue(S._is_app_open('{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"batch","arguments":{"calls":[{"tool":"app_open","arguments":{}}]}}}'))
        self.assertFalse(S._is_app_open('{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"batch","arguments":{"calls":[{"tool":"app_open"},{"tool":"session_state"}]}}}'))

    def _window(self):
        w = S.Window.__new__(S.Window)
        w.off, w.f, w.last_hb = False, None, {}
        return w

    def test_already_open(self):
        w = self._window()
        with mock.patch.object(S.Window, "_open", return_value=True):
            got = w.open_window(wait=1)
        self.assertTrue(got["already"])
        self.assertFalse(got["opened"])

    def test_starts_in_the_background_and_pairs(self):
        w = self._window()
        calls = {"n": 0}

        def opened(self_):
            calls["n"] += 1
            if calls["n"] >= 3:
                self_.f = object()
                return True
            return False

        with mock.patch.object(S.Window, "_open", opened), mock.patch.object(S, "heartbeat", return_value={"app": "/Applications/FreeCAD.app"}), \
                mock.patch.object(S, "relaunch", return_value=True) as rl, mock.patch.object(S.time, "sleep"):
            got = w.open_window(wait=30)
        rl.assert_called_once_with("/Applications/FreeCAD.app", "app_open")
        self.assertTrue(got["opened"])

    def test_relaunch_is_background_on_macos(self):
        with mock.patch.object(S.sys, "platform", "darwin"), mock.patch.object(S.subprocess, "Popen") as po, \
                mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AGENTLINK_RELAUNCH", None)
            self.assertTrue(S.relaunch("/Applications/FreeCAD.app", "app_open"))
        self.assertEqual(po.call_args[0][0], ["open", "-g", "-a", "/Applications/FreeCAD.app"])

    def test_no_app(self):
        w = self._window()
        with mock.patch.object(S.Window, "_open", return_value=False), mock.patch.object(S, "heartbeat", return_value={}), \
                mock.patch.object(S, "FREECAD_APP", "/nowhere/FreeCAD.app"), mock.patch.object(S, "keep", None):
            got = w.open_window(wait=1)
        self.assertFalse(got["opened"])


if __name__ == "__main__":
    unittest.main()
