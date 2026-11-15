# SPDX-License-Identifier: LGPL-2.1-or-later
# Crash evidence copied (never moved) before Document Recovery's Cleanup.
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from agentlink import crash_logs as C  # noqa: E402


class Collect(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="agentlink-crash-")
        self.temp = os.path.join(self.tmp, "T")
        self.home = os.path.join(self.tmp, "home")
        self.out = os.path.join(self.tmp, "out")
        for name, files in (("FreeCAD_Doc_aaa_111", ["fc_recovery_file.xml", "Document.xml"]),
                            ("FreeCAD_Doc_bbb_222", ["Document.xml"]),
                            ("FreeCAD_Doc_ccc_999", ["fc_recovery_file.fcstd"])):
            os.makedirs(os.path.join(self.temp, name))
            for f in files:
                open(os.path.join(self.temp, name, f), "w").write("x")
        rep = os.path.join(self.home, "Library", "Logs", "DiagnosticReports")
        os.makedirs(rep)
        open(os.path.join(rep, "FreeCAD-2026-11-15-140000.ips"), "w").write("{}")
        old = os.path.join(rep, "FreeCAD-2025-01-01-000000.ips")
        open(old, "w").write("{}")
        os.utime(old, (time.time() - 90 * 86400,) * 2)

    def run_collect(self):
        with mock.patch.object(C, "_user_dir", return_value=""), mock.patch.object(C.sys, "platform", "darwin"):
            return C.collect(self.out, temp=self.temp, home=self.home, skip_pid=999)

    def test_copies_recovery_folders_and_new_reports_only(self):
        got = self.run_collect()
        self.assertEqual([os.path.basename(p) for p in got["recovery"]], ["FreeCAD_Doc_aaa_111"])
        self.assertEqual([os.path.basename(p) for p in got["reports"]], ["FreeCAD-2026-11-15-140000.ips"])
        # Copies only: the originals are where they were.
        self.assertTrue(os.path.isfile(os.path.join(self.temp, "FreeCAD_Doc_aaa_111", "fc_recovery_file.xml")))

    def test_a_report_is_copied_once(self):
        self.run_collect()
        time.sleep(1.1)
        got = self.run_collect()
        self.assertEqual(got["reports"], [])
        self.assertEqual(len(got["recovery"]), 1)

    def test_nothing_to_keep(self):
        with mock.patch.object(C, "_user_dir", return_value=""):
            self.assertEqual(C.collect(self.out, temp=os.path.join(self.tmp, "none"), home=os.path.join(self.tmp, "nohome"), skip_pid=1), {})


if __name__ == "__main__":
    unittest.main()
