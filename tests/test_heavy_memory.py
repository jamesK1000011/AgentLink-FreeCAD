# SPDX-License-Identifier: LGPL-2.1-or-later
# The memory guard for heavy jobs: it learns what each job adds to the peak,
# needs two runs before it refuses anything, and never extrapolates far past
# the sizes it has seen. (A single 263 ms texture job once read as 32.7 GB.)

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentlink import heavy  # noqa: E402


class MemoryEstimate(unittest.TestCase):
    def test_one_run_is_not_enough(self):
        q = {heavy.MEMORY_KEY: {"texture_apply": [[6.0, 1700.0]]}}
        self.assertIsNone(heavy.memory_estimate(q, "texture_apply", 517))

    def test_old_whole_process_entries_are_ignored(self):
        q = {"memory": {"texture_apply": [[6.0, 1700.0], [7.0, 1800.0]]}}
        self.assertIsNone(heavy.memory_estimate(q, "texture_apply", 517))

    def test_extrapolation_is_capped(self):
        q = {heavy.MEMORY_KEY: {"fea_solve": [[100.0, 200.0], [200.0, 400.0]]}}
        # A line through (100, 200) and (200, 400) gives 2 MB per unit; at
        # size 100000 that would be 200 GB, but the reach stops at 4 x 200.
        self.assertAlmostEqual(heavy.memory_estimate(q, "fea_solve", 100000), 1600.0)
        self.assertAlmostEqual(heavy.memory_estimate(q, "fea_solve", 300), 600.0)


class AfterRecordsWhatTheJobAdded(unittest.TestCase):
    def test_delta_not_lifetime_peak(self):
        saved = {}
        calls = iter([(1700.0, 0.0)])

        class Tool:
            name = "texture_apply"

        orig = (heavy._maxrss_mb, heavy.keep.is_heavy, heavy.keep.queue_state, heavy.keep.save_queue)
        try:
            heavy._maxrss_mb = lambda: next(calls)
            heavy.keep.is_heavy = lambda name: True
            heavy.keep.queue_state = lambda: {}
            heavy.keep.save_queue = lambda q: saved.update(q)
            g = heavy.Gate.__new__(heavy.Gate)
            g.start = (0.0, 6, (1650.0, 0.0))
            g.after(Tool(), {}, True)
        finally:
            heavy._maxrss_mb, heavy.keep.is_heavy, heavy.keep.queue_state, heavy.keep.save_queue = orig
        self.assertEqual(saved[heavy.MEMORY_KEY]["texture_apply"], [[6.0, 50.0]])
        self.assertNotIn("memory", saved)

    def test_a_job_under_an_earlier_peak_is_not_logged(self):
        saved = {}

        class Tool:
            name = "texture_apply"

        orig = (heavy._maxrss_mb, heavy.keep.is_heavy, heavy.keep.queue_state, heavy.keep.save_queue)
        try:
            heavy._maxrss_mb = lambda: (1700.0, 0.0)
            heavy.keep.is_heavy = lambda name: True
            heavy.keep.queue_state = lambda: {}
            heavy.keep.save_queue = lambda q: saved.update(q)
            g = heavy.Gate.__new__(heavy.Gate)
            g.start = (0.0, 6, (1700.0, 0.0))
            g.after(Tool(), {}, True)
        finally:
            heavy._maxrss_mb, heavy.keep.is_heavy, heavy.keep.queue_state, heavy.keep.save_queue = orig
        self.assertNotIn(heavy.MEMORY_KEY, saved)


if __name__ == "__main__":
    unittest.main()
