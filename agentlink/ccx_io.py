# SPDX-License-Identifier: LGPL-2.1-or-later
# CalculiX's input decks and results: AddonKit's addonkit.ccx, which Agent
# Link's strength tools and the add-ons' own solvers (frames, beams) share.
# This module is that one.
import sys

from . import _addonkit  # noqa: F401 — AddonKit at a version this Agent Link accepts

from addonkit import ccx as _impl  # noqa: E402

sys.modules[__name__] = _impl
