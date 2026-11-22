# SPDX-License-Identifier: LGPL-2.1-or-later
"""The echo's tests from before co-work (design E5) check the camera's
frames and FreeCAD's selection. They run in the old behaviour, which is
still a choice of the person: FollowAgent on (the person not working the
view) and EchoSelects "select". The co-work defaults have their own tests
(test_cowork.py)."""
from agentlink import cowork

_saved = {}


def on():
    if _saved:
        return
    _saved.update(mode=cowork.mode, follows=cowork.follows, follow_on=cowork.follow_on)
    cowork.mode = lambda: "select"
    cowork.follows = lambda: True
    cowork.follow_on = lambda: True


def off():
    for k, v in _saved.items():
        setattr(cowork, k, v)
    _saved.clear()
