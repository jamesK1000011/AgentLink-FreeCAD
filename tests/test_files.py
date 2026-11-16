# SPDX-License-Identifier: LGPL-2.1-or-later
# FILES lists the add-on's files, so the Claude extension's launcher can
# fetch them as plain files instead of asking GitHub's API (60 calls an
# hour). A file added or removed without FILES following fails here:
# The repository's own CI and git files (.github/, .gitignore …) are not the
# add-on's, nor is packaging/ (the Claude extension's launcher, build and
# pins: built into the .mcpb, never installed into FreeCAD's Mod folder).
# Regenerate it with
#   git ls-files | grep -v -E '(^|/)__pycache__/|^FILES$|^\.|^packaging/' | sort > FILES
import os
import subprocess
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Files(unittest.TestCase):
    def test_files_list_is_current(self):
        try:
            out = subprocess.run(["git", "ls-files"], cwd=HERE, capture_output=True, text=True, check=True).stdout
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a git checkout")
        tracked = sorted(p for p in out.splitlines() if p != "FILES" and "__pycache__/" not in p and not p.startswith(".") and not p.startswith("packaging/"))
        with open(os.path.join(HERE, "FILES"), encoding="utf-8") as f:
            listed = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
        self.assertEqual(listed, tracked, "FILES is stale: regenerate it (see the comment at the top of this test)")

    def test_packaging_is_not_installed(self):
        # The launcher fetches what FILES lists into Mod/AgentLink: the
        # extension's own files stay out of the add-on copy.
        with open(os.path.join(HERE, "FILES"), encoding="utf-8") as f:
            listed = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
        self.assertEqual([p for p in listed if p.startswith("packaging/")], [], "FILES lists packaging/: the add-on copy would carry the extension's launcher and pins")


if __name__ == "__main__":
    unittest.main()
