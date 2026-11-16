# SPDX-License-Identifier: LGPL-2.1-or-later
# scripts/sync_shared.py copies Agent Link's shared files over the copies in
# other checkouts, keeping each copy's own licence line, and touches nothing
# that does not say it is a copy. On folders of its own, never a real checkout.
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import sync_shared  # noqa: E402

MARK = "same in every add-on"


def write(p, text):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)


class Sync(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.other = tempfile.mkdtemp()
        write(os.path.join(self.root, "pkg", "layout.py"), f"# LGPL\n# {MARK}\nWIDTH = 354\n")
        self.copy = os.path.join(self.other, "addon", "layout.py")
        write(self.copy, f"# AGPL\n# {MARK}\nWIDTH = 640\n")
        self.lookalike = os.path.join(self.other, "other", "layout.py")
        write(self.lookalike, "# someone else's layout\nWIDTH = 1\n")
        self.in_tests = os.path.join(self.other, "tests", "layout.py")
        write(self.in_tests, f"# AGPL\n# {MARK}\nWIDTH = 640\n")
        self.shared = {"pkg/layout.py": MARK}

    def read(self, p):
        with open(p, encoding="utf-8") as f:
            return f.read()

    def test_check_writes_nothing(self):
        differ, written = sync_shared.sync([self.other], check=True, root=self.root, shared=self.shared)
        self.assertEqual((differ, written), ([self.copy], []))
        self.assertIn("640", self.read(self.copy))

    def test_copies_keeping_the_licence_line(self):
        sync_shared.sync([self.other], root=self.root, shared=self.shared)
        self.assertEqual(self.read(self.copy), f"# AGPL\n# {MARK}\nWIDTH = 354\n")
        self.assertIn("WIDTH = 1", self.read(self.lookalike))
        self.assertIn("640", self.read(self.in_tests))
        self.assertEqual(sync_shared.sync([self.other], check=True, root=self.root, shared=self.shared), ([], []))

    def test_layout_is_listed_and_marked(self):
        self.assertIn("agentlink/layout.py", sync_shared.SHARED)
        with open(os.path.join(ROOT, "agentlink", "layout.py"), encoding="utf-8") as f:
            self.assertIn(sync_shared.SHARED["agentlink/layout.py"], f.read())


if __name__ == "__main__":
    unittest.main()
