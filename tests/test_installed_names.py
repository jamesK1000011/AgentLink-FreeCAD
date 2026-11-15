# SPDX-License-Identifier: LGPL-2.1-or-later
# The Addon Manager leaves alone what the launcher installed: the names in
# <Mod>/AgentLink/.installed-names, plus AddonManager; AgentLink and AddonManager alone when the
# list is missing or unreadable.
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fc import HAVE  # noqa: E402

if HAVE:
    from agentlink.families import unattended


@unittest.skipUnless(HAVE, "FreeCAD is not importable here")
class InstalledNames(unittest.TestCase):
    def test_list_read(self):
        with tempfile.TemporaryDirectory() as mod:
            os.makedirs(os.path.join(mod, "AgentLink"))
            with open(os.path.join(mod, "AgentLink", ".installed-names"), "w") as f:
                json.dump(["AgentLink", "MineAddon", 3], f)
            self.assertEqual(unattended.ours(mod), {"AgentLink", "MineAddon", "AddonManager"})

    def test_fallback(self):
        with tempfile.TemporaryDirectory() as mod:
            self.assertEqual(unattended.ours(mod), set(unattended.OURS_FALLBACK))
            os.makedirs(os.path.join(mod, "AgentLink"))
            with open(os.path.join(mod, "AgentLink", ".installed-names"), "w") as f:
                f.write("{not json")
            self.assertEqual(unattended.ours(mod), set(unattended.OURS_FALLBACK))


if __name__ == "__main__":
    unittest.main()
