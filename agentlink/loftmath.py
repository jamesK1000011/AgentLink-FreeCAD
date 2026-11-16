# SPDX-License-Identifier: LGPL-2.1-or-later
# The numbers behind part_loft's checks and rebuilds, on plain (x, y, z)
# tuples so they need no FreeCAD: outlines resampled by arc length, the
# best cyclic shift of one outline against the one before (seams lined up),
# which span between two profiles a point of the result lies in, and how
# far each span bulges beyond its own two profiles.

import math


def tup(p):
    """(x, y, z) from a FreeCAD vector, a list or a tuple."""
    if hasattr(p, "x"):
        return (float(p.x), float(p.y), float(p.z))
    return tuple(float(v) for v in p)


def _d(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def resample(pts, n, closed=True):
    """n points spread evenly by arc length along pts (a closed loop when
    closed, the first point not repeated at the end; else a run from the
    first point to the last, both kept). Starts at pts[0]."""
    pts = [tup(p) for p in pts]
    if closed and len(pts) > 2 and _d(pts[0], pts[-1]) < 1e-12:
        pts = pts[:-1]
    if len(pts) < 2 or n < 2:
        return pts[:max(n, 0)]
    loop = pts + [pts[0]] if closed else pts
    seg = [_d(loop[i], loop[i + 1]) for i in range(len(loop) - 1)]
    total = sum(seg)
    if total <= 1e-12:
        return [pts[0]] * n
    out, i, run = [], 0, 0.0
    count = n if closed else n - 1
    for k in range(n):
        target = total * k / count
        while i < len(seg) - 1 and run + seg[i] < target - 1e-12:
            run += seg[i]
            i += 1
        t = 0.0 if seg[i] <= 1e-15 else min(1.0, max(0.0, (target - run) / seg[i]))
        out.append(_lerp(loop[i], loop[i + 1], t))
    return out


def centroid(pts):
    n = float(len(pts))
    return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n, sum(p[2] for p in pts) / n)


def best_shift(prev, cur):
    """The cyclic shift k of cur (cur[k:] + cur[:k]) whose points, each
    taken from its own outline's centre, lie nearest prev's: the seam that
    matches, whatever the planes' offset. Same length both."""
    n = len(cur)
    if n != len(prev) or n == 0:
        return 0
    cp, cc = centroid(prev), centroid(cur)
    a = [(p[0] - cp[0], p[1] - cp[1], p[2] - cp[2]) for p in prev]
    b = [(p[0] - cc[0], p[1] - cc[1], p[2] - cc[2]) for p in cur]
    best, bk = None, 0
    for k in range(n):
        s = 0.0
        for i in range(n):
            q = b[(i + k) % n]
            p = a[i]
            s += (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2
            if best is not None and s >= best:
                break
        if best is None or s < best:
            best, bk = s, k
    return bk


def shifted(pts, k):
    return pts[k:] + pts[:k]


def line_up(outlines):
    """Each outline (same point count) turned to start where it matches
    the one before best; answers the outlines and how many were turned."""
    out = [list(outlines[0])]
    turned = 0
    for o in outlines[1:]:
        k = best_shift(out[-1], o)
        turned += bool(k)
        out.append(shifted(list(o), k))
    return out, turned


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _unit(a):
    ln = math.sqrt(_dot(a, a))
    return (a[0] / ln, a[1] / ln, a[2] / ln) if ln > 1e-12 else (0.0, 0.0, 0.0)


def directions(centres):
    """The way the loft runs at each profile: from the centre before to
    the centre after (one-sided at the ends)."""
    n = len(centres)
    return [_unit(_sub(centres[min(i + 1, n - 1)], centres[max(i - 1, 0)])) for i in range(n)]


def span_index(p, centres, dirs):
    """Which span (between profiles i and i + 1) the point p lies in: past
    the plane through profile i (across the loft's way there) and not yet
    past the next. Before the first: 0; after the last: the last span."""
    n = len(centres)
    last = 0
    for i in range(n):
        if _dot(_sub(p, centres[i]), dirs[i]) >= -1e-9:
            last = i
        else:
            break
    return min(last, n - 2)


def box_of(pts):
    xs, ys, zs = [p[0] for p in pts], [p[1] for p in pts], [p[2] for p in pts]
    return (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def joint(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), min(a[2], b[2]), max(a[3], b[3]), max(a[4], b[4]), max(a[5], b[5]))


def reach_beyond(inner, outer, reach):
    """How far box inner reaches beyond box outer, as a share of outer's
    size along that axis (never under a quarter of its longest side), and
    the axis; (0, None) while within reach (a share) everywhere."""
    lens = [outer[3] - outer[0], outer[4] - outer[1], outer[5] - outer[2]]
    longest = max(max(lens), 1e-9)
    worst, axis = 0.0, None
    for k, ax in enumerate("xyz"):
        size = max(lens[k], 0.25 * longest)
        over = max(outer[k] - inner[k], inner[k + 3] - outer[k + 3], 0.0)
        if over > reach * size + 1e-6:
            share = over / size
            if share > worst:
                worst, axis = share, ax
    return worst, axis


def span_bulges(points, profile_boxes, centres, reach):
    """Each span whose part of the result reaches beyond its own two
    profiles' box by more than reach: [{span: [i, i + 1], share, axis}],
    worst first. points: the result's (a tessellation); profile_boxes:
    (xmin, ymin, zmin, xmax, ymax, zmax) for each profile, in order."""
    n = len(centres)
    if n < 2:
        return []
    dirs = directions(centres)
    boxes = {}
    for p in points:
        i = span_index(p, centres, dirs)
        b = boxes.get(i)
        boxes[i] = (p[0], p[1], p[2], p[0], p[1], p[2]) if b is None else (min(b[0], p[0]), min(b[1], p[1]), min(b[2], p[2]), max(b[3], p[0]), max(b[4], p[1]), max(b[5], p[2]))
    out = []
    for i, b in sorted(boxes.items()):
        share, axis = reach_beyond(b, joint(profile_boxes[i], profile_boxes[i + 1]), reach)
        if share:
            out.append({"span": [i, i + 1], "share": round(share, 3), "axis": axis})
    out.sort(key=lambda x: -x["share"])
    return out


def pieces(n, ruled_spans):
    """The profiles 0 … n - 1 cut into runs for a loft span by span: each
    span in ruled_spans a run of its own two profiles, ruled; the profiles
    between them smooth runs. [(first, last, ruled)], in order."""
    bad = sorted(set(i for i in ruled_spans if 0 <= i < n - 1))
    out, start = [], 0
    for i in bad:
        if i > start:
            out.append((start, i, False))
        out.append((i, i + 1, True))
        start = i + 1
    if start < n - 1:
        out.append((start, n - 1, False))
    return out
