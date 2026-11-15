# SPDX-License-Identifier: LGPL-2.1-or-later
# app_extensions installs a repository whose root is the add-on (package.xml
# at the top) as Mod/<its name>, marked, and puts it on the path; it never
# writes over a folder another add-on owns. Plain Python, a local git repo.
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentlink import ext  # noqa: E402


@unittest.skipUnless(shutil.which("git"), "git is not installed here")
class RootAddon(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.mod = os.path.join(self.tmp, "Mod")
        self.here = os.path.join(self.mod, "AgentLink")
        os.makedirs(os.path.join(self.here, "agentlink"))
        src = os.path.join(self.tmp, "src")
        os.makedirs(os.path.join(src, "home_code"))
        open(os.path.join(src, "package.xml"), "w").write("<package><name>Home</name></package>")
        open(os.path.join(src, "home_code", "__init__.py"), "w").write("")
        os.makedirs(os.path.join(src, "tests"))
        g = ["git", "-C", src, "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
        subprocess.run(["git", "init", "-q", "-b", "main", src], check=True)
        subprocess.run(g + ["add", "-A"], check=True)
        subprocess.run(g + ["commit", "-q", "-m", "x"], check=True)
        self.src = src
        self._file, self._repos = ext.__file__, ext.repos
        ext.__file__ = os.path.join(self.here, "agentlink", "ext.py")
        ext.repos = lambda: ["file://" + src]

    def tearDown(self):
        ext.__file__, ext.repos = self._file, self._repos
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_installed_marked_and_on_the_path(self):
        out = ext.sync(cache=os.path.join(self.tmp, "cache"))
        self.assertEqual(out["failed"], [], out)
        self.assertEqual(out["installed"][0]["folders"], ["Home"])
        home = os.path.join(self.mod, "Home")
        self.assertTrue(os.path.isfile(os.path.join(home, ext.MARK)))
        self.assertFalse(os.path.exists(os.path.join(home, "tests")))
        ext._paths()
        self.assertIn(home, sys.path)
        sys.path.remove(home)

    def test_never_over_another_add_on(self):
        os.makedirs(os.path.join(self.mod, "Home"))
        out = ext.sync(cache=os.path.join(self.tmp, "cache"))
        self.assertEqual(out["installed"], [])
        self.assertIn("already there", out["failed"][0]["why"])


if __name__ == "__main__":
    unittest.main()
