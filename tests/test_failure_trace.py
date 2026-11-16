# SPDX-License-Identifier: LGPL-2.1-or-later
# A tool's own failure carries its traceback under the tests only
# (AGENTLINK_TEST=1), and an error raised while TechDraw's wait pumps Qt's
# loop (someone else's timer) is logged, not raised into the TechDraw call.
import json
import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from agentlink import td_wait  # noqa: E402
from agentlink.protocol import Server, Tool  # noqa: E402


def boom(a):
    raise AttributeError("module 'FreeCADGui' has no attribute 'getMainWindow'")


class Trace(unittest.TestCase):
    def call(self):
        s = Server.__new__(Server)
        s.tools = {"td_view": Tool("td_view", "A view.", {"type": "object", "properties": {}}, boom)}
        r = s.handle_light({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "td_view", "arguments": {}}})["result"]
        return json.loads(r["content"][0]["text"])["error"]

    def test_trace_under_the_tests(self):
        with mock.patch.dict(os.environ, {"AGENTLINK_TEST": "1"}), mock.patch("sys.stderr"):
            e = self.call()
        self.assertEqual(e["code"], "failed")
        self.assertIn("in boom", e["trace"])
        self.assertIn("getMainWindow", e["trace"])

    def test_no_trace_otherwise(self):
        with mock.patch.dict(os.environ, {"AGENTLINK_TEST": "0"}), mock.patch("sys.stderr"):
            e = self.call()
        self.assertNotIn("trace", e)


class Pump(unittest.TestCase):
    def test_a_foreign_error_is_logged_not_raised(self):
        def bad():
            raise AttributeError("module 'FreeCADGui' has no attribute 'getMainWindow'")
        app = types.SimpleNamespace(processEvents=bad)
        n = len(td_wait.PUMP_ERRORS)
        with mock.patch("sys.stderr"):
            td_wait.pump(app)
        self.assertIn("getMainWindow", td_wait.PUMP_ERRORS[-1])
        self.assertLessEqual(len(td_wait.PUMP_ERRORS), max(n + 1, 5))

    def test_a_quiet_pump(self):
        ran = []
        td_wait.pump(types.SimpleNamespace(processEvents=lambda: ran.append(1)))
        self.assertEqual(ran, [1])


if __name__ == "__main__":
    unittest.main()
