# SPDX-License-Identifier: LGPL-2.1-or-later
"""Where a sketch lies in the world, in words (plain Python: no FreeCAD).

Small local models did not read the four frame vectors of a sketch answer
(25 Nov orientation audit): no model made the cross product that says
"y [0, 0, -1] is down", and the one note was said only once. So every answer
that makes or moves a sketch says its frame in one line (axes_line). The
same rules choose the axes of a face sketch (face_axes) and of a sketch
turned by sketch_new's up input (up_axes).

Inspired by Stefan Hermann (CNC Kitchen) ScanRuler: its frame said in words
and its up input on a standing plane. The code and the words here are Agent
Link's own.
"""
import math

AXES = (("X", (1.0, 0.0, 0.0)), ("Y", (0.0, 1.0, 0.0)), ("Z", (0.0, 0.0, 1.0)))
UNIT = dict(AXES)
EXACT = math.cos(math.radians(0.5))   # a direction this close to an axis is that axis
STANDING = math.cos(math.radians(45.0)) - 1e-9  # |normal . Z| under this: a standing face
LEAST = 0.1   # up's part in the plane (sin of its angle to the normal) below this: refused
UP_KEYS = ("x", "y", "z")


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(v):
    k = math.sqrt(_dot(v, v))
    return None if k < 1e-12 else tuple(c / k for c in v)


def num(x):
    """A coordinate in words: 2 places at most, no "-0"."""
    x = round(float(x), 2) + 0.0
    return str(int(x)) if x == int(x) else f"{x:g}"


def axis_word(v):
    """"+X", "-Z" for a direction along a world axis; else "mostly +Z (12° off)"."""
    u = _unit(v)
    if u is None:
        return "[0, 0, 0]"
    i = max(range(3), key=lambda k: abs(u[k]))
    word = ("+" if u[i] > 0 else "-") + "XYZ"[i]
    if abs(u[i]) >= EXACT:
        return word
    off = math.degrees(math.acos(min(1.0, abs(u[i]))))
    return f"mostly {word} ({off:.0f}° off)"


def _updown(v):
    """" (up)" or " (down)" for a direction along world Z, else "" ("mostly
    -Z" says it already)."""
    w = axis_word(v)
    return {"+Z": " (up)", "-Z": " (down)"}.get(w, "")


def axes_line(fr):
    """A sketch's frame { origin, xAxis, yAxis, normal } in one line:
    "x runs +X; y runs +Z (up); the normal points -Y: a pad grows toward -Y,
    a pocket or hole cuts toward +Y. [0, 0] is at world (0, -15, 0)." """
    n = fr["normal"]
    nw, back = axis_word(n), axis_word(tuple(-c for c in n))
    way = (f"a pad grows toward {nw}, a pocket or hole cuts toward {back}" if not nw.startswith("mostly")
           else "a pad grows along it, a pocket or hole cuts against it")
    o = fr["origin"]
    return (f"x runs {axis_word(fr['xAxis'])}{_updown(fr['xAxis'])}; y runs {axis_word(fr['yAxis'])}{_updown(fr['yAxis'])}; "
            f"the normal points {nw}: {way}. [0, 0] is at world ({', '.join(num(c) for c in o)}).")


def axes_rec(fr):
    """A sketch's frame { origin, xAxis, yAxis, normal } as a record: { x:
    "+X", y: "+Z", normal: "-Y" } (axis_word of each)."""
    return {"x": axis_word(fr["xAxis"]), "y": axis_word(fr["yAxis"]), "normal": axis_word(fr["normal"])}


def up_key(up):
    """The world axis an up input names, as a unit tuple; ValueError for another value."""
    k = up.strip().lower() if isinstance(up, str) else None
    if k not in UP_KEYS:
        raise ValueError(f"up: x, y or z (the world axis that sketch y runs along), not {up!r}.")
    return UNIT[k.upper()]


def up_axes(n, up):
    """(x, y) of a sketch whose normal is n and whose y runs along the world
    axis up (as near as the plane lets it): y is up with its part along n
    taken off, x = y × n, so x, y, n is right-handed and n is unchanged.
    ValueError when up is (nearly) the normal: it has no direction in the plane."""
    n = _unit(n)
    u = up_key(up) if isinstance(up, str) else _unit(up)
    d = _dot(u, n)
    y = (u[0] - n[0] * d, u[1] - n[1] * d, u[2] - n[2] * d)
    if math.sqrt(_dot(y, y)) < LEAST:
        name = up if isinstance(up, str) else "that"
        raise ValueError(f"up {name}: that axis is along this plane's normal ({axis_word(n)}), so it does not lie in the plane. "
                         f"Give an axis that lies in it, or leave up out.")
    y = _unit(y)
    return _cross(y, n), y


def standing(n):
    """A face whose normal is nearer level than upright (more than 45° from Z)."""
    u = _unit(n)
    return u is not None and abs(u[2]) < STANDING


def face_axes(n, up=None):
    """(x, y) of a sketch on a face with outward normal n. up given: up_axes.
    A standing face: y runs up world +Z (up_axes with z), so its y is never
    down; x is then level, to the right as one looks at the face. Else x is
    the world axis that lies most in the face (X before Y before Z on a tie),
    and y = n × x."""
    if up is not None:
        return up_axes(n, up)
    if standing(n):
        return up_axes(n, "z")
    n = _unit(n)
    best = max((e for _, e in AXES), key=lambda e: 1 - abs(_dot(e, n)))
    d = _dot(best, n)
    x = _unit((best[0] - n[0] * d, best[1] - n[1] * d, best[2] - n[2] * d))
    return x, _cross(n, x)
