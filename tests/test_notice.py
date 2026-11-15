# SPDX-License-Identifier: LGPL-2.1-or-later
# The notice service: an add-on's line rides once on the next answer.
import json
import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentlink import hooks  # noqa: E402
from agentlink.protocol import Server, Tool, ToolError  # noqa: E402


def server():
    def refuse(a):
        raise ToolError("not_found", "nothing here")

    tools = [Tool("echo", "Echo.", {"type": "object", "properties": {}}, lambda a: {"said": "hi"}),
             Tool("refuse", "Refuse.", {"type": "object", "properties": {}}, refuse)]
    return Server("t", "0", tools, "hi")


def answer(s, name="echo"):
    r = s.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": {}}})
    return json.loads(r["result"]["content"][0]["text"])


class Notice(unittest.TestCase):
    def setUp(self):
        self.state = hooks.saved()
        hooks.reset()

    def tearDown(self):
        hooks.restore(self.state)

    def test_line_once_on_next_answer(self):
        s = server()
        self.assertNotIn("notice", answer(s))
        lines = ["The person took a screenshot."]
        hooks.provide("notice", lambda: lines.pop() if lines else None)
        got = answer(s)
        self.assertEqual(got["notice"], "The person took a screenshot.")
        self.assertEqual(got["said"], "hi")
        self.assertNotIn("notice", answer(s))
        lines.append("Another.")
        self.assertEqual(answer(s, "refuse")["notice"], "Another.")

    def test_no_provider_no_change(self):
        self.assertEqual(set(answer(server())), {"said", "ms"})

    def test_raising_provider_ignored(self):
        def boom():
            raise RuntimeError("boom")

        hooks.provide("notice", boom)
        got = answer(server())
        self.assertEqual(got["said"], "hi")
        self.assertNotIn("notice", got)

    def test_slow_provider_rides_on_the_next(self):
        go = threading.Event()

        def slow():
            go.wait(5)
            return "Late line."

        hooks.provide("notice", slow)
        s = server()
        self.assertNotIn("notice", answer(s))
        go.set()
        for _ in range(50):
            if hooks._notice["late"]:
                break
            threading.Event().wait(0.02)
        self.assertEqual(answer(s)["notice"], "Late line.")


if __name__ == "__main__":
    unittest.main()
