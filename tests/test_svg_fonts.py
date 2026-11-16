# SPDX-License-Identifier: LGPL-2.1-or-later
# The SVGs Agent Link writes (charts, drawing sheets, GD&T symbols) name one
# font family that exists on macOS, never the generic sans-serif: Qt's SVG
# renderer, which draws them in TechDraw and the panel, warned of a missing
# "Sans-serif" family in the Report view (seen on the Mac).
import os
import re
import unittest

PKG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agentlink")


class SvgFonts(unittest.TestCase):
    def test_no_generic_family(self):
        hits = []
        for d, _dirs, files in os.walk(PKG):
            for f in files:
                if f.endswith(".py"):
                    p = os.path.join(d, f)
                    with open(p, encoding="utf-8") as fh:
                        for i, line in enumerate(fh, 1):
                            if re.search(r"font-family=[^>]*sans-serif", line, re.I):
                                hits.append(f"{os.path.relpath(p, PKG)}:{i}")
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
