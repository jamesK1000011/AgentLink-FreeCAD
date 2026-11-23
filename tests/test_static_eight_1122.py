# SPDX-License-Identifier: LGPL-2.1-or-later
"""With the fast path on, the static list also has fast and get, so a client
that sends only listed tools (OpenCode) can call them directly; off, the six."""
import os
import unittest
from unittest import mock

from agentlink import staticbase


class Eight(unittest.TestCase):
    tools = {n: object() for n in staticbase.BASE + staticbase.FAST}

    def test_on_lists_eight(self):
        with mock.patch.dict(os.environ, {"AGENTLINK_FASTPATH": "on"}):
            self.assertEqual(staticbase.base(self.tools), staticbase.BASE + ("fast", "get"))

    def test_off_lists_six(self):
        with mock.patch.dict(os.environ, {"AGENTLINK_FASTPATH": "off"}):
            self.assertEqual(staticbase.base(self.tools), staticbase.BASE)

    def test_without_the_tools_six(self):
        with mock.patch.dict(os.environ, {"AGENTLINK_FASTPATH": "on"}):
            self.assertEqual(staticbase.base({n: 1 for n in staticbase.BASE}), staticbase.BASE)


if __name__ == "__main__":
    unittest.main()
