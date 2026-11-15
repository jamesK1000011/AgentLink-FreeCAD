# SPDX-License-Identifier: LGPL-2.1-or-later
# quit_guard: once armed, a C-level exit() (the one -[NSApplication
# terminate:] makes while Python still runs) ends the process with status 0
# before later teardown can crash it.
import os
import subprocess
import sys
import textwrap
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(code):
    return subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=ROOT, capture_output=True, text=True, timeout=30)


class QuitGuard(unittest.TestCase):
    def test_armed_exit_ends_with_status_zero(self):
        r = run("""
            import ctypes
            from agentlink import quit_guard
            assert quit_guard.arm()
            assert not quit_guard.arm()
            ctypes.CDLL(None).exit(5)
        """)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_unarmed_exit_keeps_its_status(self):
        self.assertEqual(run("import ctypes; ctypes.CDLL(None).exit(5)").returncode, 5)

    def test_install_does_nothing_off_macos_or_without_the_gui(self):
        r = run("""
            import sys, types
            sys.modules['FreeCAD'] = types.SimpleNamespace(GuiUp=False)
            from agentlink import quit_guard
            print(quit_guard.install(object()))
        """)
        self.assertEqual(r.stdout.strip(), "False", r.stderr)


if __name__ == "__main__":
    unittest.main()
