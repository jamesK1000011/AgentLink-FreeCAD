# SPDX-License-Identifier: LGPL-2.1-or-later
# Shape building and reading on FreeCAD's Part module: AddonKit's
# addonkit.geo, which every add-on shares. This module is that one, so Agent
# Link and the add-ons read and write the same.
import sys

from . import _addonkit  # noqa: F401 — AddonKit at a version this Agent Link accepts

from addonkit import geo as _impl  # noqa: E402

sys.modules[__name__] = _impl
