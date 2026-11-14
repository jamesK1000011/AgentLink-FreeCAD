# SPDX-License-Identifier: LGPL-2.1-or-later
# Drawing sheets as plain Python: paper sizes, view layout, title blocks, and the sheet written as SVG, DXF and PDF. AddonKit's addonkit.sheets, which Agent Link's TechDraw tools and
# Workshop Documents share. This module is that one.
import sys

from . import _addonkit  # noqa: F401 — AddonKit at a version this Agent Link accepts

from addonkit import sheets as _impl  # noqa: E402

sys.modules[__name__] = _impl
