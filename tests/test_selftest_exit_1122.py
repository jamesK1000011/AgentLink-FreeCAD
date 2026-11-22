# SPDX-License-Identifier: LGPL-2.1-or-later
"""The self-test tool exists only with its marker file, and its exit is caught."""
import os
import tempfile
import unittest

from agentlink import selftest


class SelfTest(unittest.TestCase):
    def test_off_without_the_marker(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(selftest.tools(d), [])

    def test_on_with_the_marker_and_it_exits(self):
        with tempfile.TemporaryDirectory() as d:
            open(os.path.join(d, selftest.MARK), "w").close()
            got = selftest.tools(d)
            self.assertEqual([t.name for t in got], ["selftest_exit"])
            self.assertFalse(got[0].changes)
            with self.assertRaises(SystemExit):
                got[0].fn({})


if __name__ == "__main__":
    unittest.main()
