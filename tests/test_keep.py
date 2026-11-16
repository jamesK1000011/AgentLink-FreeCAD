# SPDX-License-Identifier: LGPL-2.1-or-later
# The unattended-use store (agentlink/keep.py) without FreeCAD: the watchdog,
# dialogs, the machine and the queue.
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentlink import keep  # noqa: E402


class Home(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._was = os.environ.get("AGENTLINK_HOME")
        os.environ["AGENTLINK_HOME"] = self.tmp.name

    def tearDown(self):
        # Put back what was there: other test modules set it for theirs.
        if self._was is None:
            os.environ.pop("AGENTLINK_HOME", None)
        else:
            os.environ["AGENTLINK_HOME"] = self._was
        self.tmp.cleanup()


class SavingFlag(Home):
    def test_saving_flag(self):
        # Written by an add-on saving a copy; the watchdog reads it.
        self.assertFalse(keep.saving())
        open(keep.saving_flag(), "w").write("x")
        self.assertTrue(keep.saving())
        os.remove(keep.saving_flag())
        self.assertFalse(keep.saving())


class Watchdog(unittest.TestCase):
    def test_deadlines(self):
        self.assertEqual(keep.deadline("read"), 30)
        self.assertEqual(keep.deadline("change"), 120)
        self.assertEqual(keep.deadline("heavy", 300), 900)
        self.assertEqual(keep.deadline("heavy", 10), 120)

    def test_hung_needs_missing_pings(self):
        self.assertFalse(keep.hung(1000, 0, 999, 120))  # long but alive
        self.assertTrue(keep.hung(1000, 0, 900, 120))
        self.assertFalse(keep.hung(100, 0, 0, 120))  # within its deadline

    def test_key(self):
        self.assertEqual(keep.call_key("a", {"x": 1, "y": 2}), keep.call_key("a", {"y": 2, "x": 1}))


class Dialogs(Home):
    REC = {"class": "QDialog", "title": "Document Recovery", "text": "Press Start Recovery", "buttons": ["Start Recovery", "Skip"]}

    def test_recovery_only_when_ours(self):
        self.assertEqual(keep.dialog_answer_for(self.REC, ours=True), ("press", "skip"))
        self.assertEqual(keep.dialog_answer_for(self.REC, ours=False)[0], "report")
        # FreeCAD 1.1's dialog has no Skip: closed as Escape closes it.
        rec11 = dict(self.REC, buttons=["Start Recovery", "Cleanup..."])
        self.assertEqual(keep.dialog_answer_for(rec11, ours=True), ("press", "Cancel"))
        self.assertEqual(keep.dialog_answer_for(rec11, ours=False)[0], "report")
        # Its question about the recovery files keeps them.
        q = {"class": "QMessageBox", "title": "Document Recovery", "text": "Remove the recovery files?", "buttons": ["Yes", "No"]}
        self.assertEqual(keep.dialog_answer_for(q, ours=True), ("press", "no"))

    def test_save_on_restart_follows_the_rule(self):
        d = {"class": "QMessageBox", "title": "Unsaved document", "text": "Do you want to save your changes to document 'Bracket' before closing?", "buttons": ["Save", "Discard", "Cancel"]}
        self.assertEqual(keep.dialog_answer_for(d, False, restarting=True, save_rule="agent", agent_docs=["Bracket"]), ("press", "save"))
        self.assertEqual(keep.dialog_answer_for(d, False, restarting=True, save_rule="agent", agent_docs=[]), ("press", "discard"))
        self.assertEqual(keep.dialog_answer_for(d, False, restarting=False)[0], "report")

    def test_harmless(self):
        self.assertTrue(keep.harmless({"class": "QMessageBox", "buttons": ["OK"]}))
        self.assertFalse(keep.harmless({"class": "QMessageBox", "buttons": ["Yes", "No"]}))
        self.assertFalse(keep.harmless({"class": "QFileDialog", "buttons": ["OK"]}))

    def test_launch_mark(self):
        self.assertFalse(keep.launched_by_us(42))
        keep.mark_launch(42, "crash")
        self.assertTrue(keep.launched_by_us(42))
        self.assertFalse(keep.launched_by_us(43))


class Machine(Home):
    AIR = {"machdep.cpu.brand_string": "Apple M4", "hw.perflevel0.physicalcpu": "4", "hw.ncpu": "10", "hw.memsize": str(16 * 1024 ** 3), "hw.model": "MacBookAir10,1"}

    def test_preset(self):
        m = keep.machine_from(self.AIR)
        self.assertEqual((m["fan"], m["heavySlots"], m["memoryGB"], m["memoryCeilingGB"]), (False, 1, 16.0, 8.0))
        pro = dict(self.AIR, **{"hw.model": "Mac16,5", "hw.perflevel0.physicalcpu": "12"})
        self.assertEqual(keep.machine_from(pro)["heavySlots"], 2)

    def test_readings(self):
        self.assertTrue(keep.thermal_limited("CPU_Scheduler_Limit = 100\nCPU_Speed_Limit = 80"))
        self.assertFalse(keep.thermal_limited("Note: No thermal warning level has been recorded"))
        self.assertEqual(keep.memory_pressure_level("kern.memorystatus_vm_pressure_level: 2"), "warn")
        self.assertEqual(keep.memory_pressure_level("System-wide memory free percentage: 45%"), "normal")
        self.assertAlmostEqual(keep.hid_idle_seconds('"HIDIdleTime" = 12500000000'), 12.5)

    def test_read_and_override(self):
        m = keep.read_machine()
        self.assertGreaterEqual(m["heavySlots"], 1)
        self.assertTrue(os.path.isfile(os.path.join(self.tmp.name, "machine.json")))
        self.assertEqual(keep.preset({"memoryCeilingGB": 2.5})["memoryCeilingGB"], 2.5)
        self.assertIn("fea_solve", keep.HEAVY)

    def test_queue(self):
        q = keep.queue_state()
        self.assertIsNone(keep.estimate(q, "fea_solve", 1000))
        keep.log_timing(q, "fea_solve", 1000, 10)
        keep.log_timing(q, "fea_solve", 3000, 30)
        self.assertAlmostEqual(keep.estimate(q, "fea_solve", 24000), 240, places=3)
        m = keep.machine_from(self.AIR)
        self.assertEqual(keep.admit(q, m, False, False, "normal"), (True, None))
        self.assertFalse(keep.admit(q, m, True, False, "normal")[0])
        self.assertFalse(keep.admit(q, m, False, True, "normal")[0])
        self.assertFalse(keep.admit(q, m, False, False, "warn")[0])
        q["running"] = [{"tool": "fea_solve"}]
        self.assertIn("at once", keep.admit(q, m, False, False, "normal")[1])
        keep.save_queue(q)
        self.assertEqual(keep.queue_state()["running"][0]["tool"], "fea_solve")


if __name__ == "__main__":
    unittest.main()
