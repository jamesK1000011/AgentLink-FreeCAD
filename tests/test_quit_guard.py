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

    def test_normal_quit_after_python_finalized_does_not_crash(self):
        # 17 Nov, Mac crash report: armed at the window's Close, then the
        # quit went the normal way (Py_Finalize, then exit()); the old ctypes
        # callback entered the dead interpreter (SIGSEGV). Now only C runs.
        r = run("""
            from agentlink import quit_guard
            assert quit_guard.arm()
            import sys
            sys.exit(5)
        """)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_registers_plain_c_functions_only(self):
        # Fake CDLL: __cxa_atexit must get libc's own _exit and fflush
        # addresses (no Python callback), _exit first so it runs last.
        r = run("""
            import ctypes, sys, types
            from agentlink import quit_guard
            saved = []
            sys.modules['FreeCAD'] = types.SimpleNamespace(saveParameter=lambda: saved.append(1))
            real = ctypes.CDLL(None)
            calls = []
            class Reg:
                argtypes = restype = None
                def __call__(self, fn, arg, dso):
                    calls.append((fn, arg, dso))
                    return 0
            class Fake:
                _exit = real._exit
                fflush = real.fflush
            setattr(Fake, "__cxa_atexit", Reg())  # no name mangling
            quit_guard._state["lib"] = Fake()
            assert quit_guard.arm()
            assert not quit_guard.arm()
            want = [ctypes.cast(real._exit, ctypes.c_void_p).value, ctypes.cast(real.fflush, ctypes.c_void_p).value]
            assert [c[0] for c in calls] == want, (calls, want)
            assert all(isinstance(c[0], int) and c[1] is None and c[2] is None for c in calls)
            assert saved == [1], saved
            print("ok")
        """)
        self.assertEqual(r.stdout.strip(), "ok", r.stderr)

    def test_refuses_when_libc_lacks_the_calls(self):
        r = run("""
            from agentlink import quit_guard
            quit_guard._state["lib"] = object()
            print(quit_guard.arm(save=False), quit_guard._state["armed"])
        """)
        self.assertEqual(r.stdout.strip(), "False False", r.stderr)

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
