# SPDX-License-Identifier: LGPL-2.1-or-later
# The sheet writers (SVG, DXF, PDF) and the layout, plain Python (moved from
# Agent Link's drawing tests).
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentlink import sheets  # noqa: E402


class Writers(unittest.TestCase):
    def sheet(self):
        s = sheets.Sheet(297, 210, "Test (1)")
        s.frame()
        s.line([(20, 20), (60, 20), (60, 50)], "visible")
        s.line([(20, 30), (40, 30)], "hidden")
        s.dimension((20, 50), (60, 50), 8, "40")
        s.dimension((60, 50), (60, 20), 8, "30")
        s.text(100, 100, 3, "FRONT — A&B", "middle")
        return s

    def test_svg(self):
        svg = self.sheet().svg()
        self.assertTrue(svg.startswith("<?xml"))
        self.assertIn('width="297mm"', svg)
        self.assertIn("stroke-dasharray", svg)
        self.assertIn("A&amp;B", svg)
        self.assertIn("rotate(-90", svg)

    def test_pdf(self):
        pdf = self.sheet().pdf()
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertTrue(pdf.rstrip().endswith(b"%%EOF"))
        xref = int(pdf[pdf.rindex(b"startxref") + 9:].split()[0])
        self.assertEqual(pdf[xref:xref + 4], b"xref")
        self.assertIn(b"/MediaBox [0 0 841.89 595.28]", pdf)



    def test_dxf(self):
        d = self.sheet().dxf()
        self.assertIn("AC1009", d)
        self.assertIn("VISIBLE", d)
        self.assertTrue(d.rstrip().endswith("EOF"))


if __name__ == "__main__":
    unittest.main()
