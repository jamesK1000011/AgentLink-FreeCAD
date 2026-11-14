# SPDX-License-Identifier: LGPL-2.1-or-later
# The records kept in the document (setups, spec, materials per body,
# calibrations): AddonKit's addonkit.records, which every add-on shares.
# This module is that one, so Agent Link and the add-ons read and write the
# same.
import sys

from . import _addonkit  # noqa: F401 — AddonKit at a version this Agent Link accepts

from addonkit import records as _impl  # noqa: E402

sys.modules[__name__] = _impl
