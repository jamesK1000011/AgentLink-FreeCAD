# SPDX-License-Identifier: LGPL-2.1-or-later
# ISO 286 limits of size for the common fits (IT5 to IT11; F G H JS holes, f g h js k n p shafts; up to 500 mm). AddonKit's addonkit.iso286, which Agent Link's TechDraw tools and
# Workshop Documents share. This module is that one.
import sys

from . import _addonkit  # noqa: F401 — AddonKit at a version this Agent Link accepts

from addonkit import iso286 as _impl  # noqa: E402

sys.modules[__name__] = _impl
