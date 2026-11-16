# SPDX-License-Identifier: LGPL-2.1-or-later
# Points read from a file instead of pasted into a call: a profile's or a
# wire's points, or every profile of a loft at once. Many sections of 20+
# points each are kilobytes of numbers an agent would otherwise send (and
# pay for) inline, often twice. The file is read once, on this side.
#
# JSON: a list of [x, y, z] (one outline); a list of such lists (several);
# an object whose key names one ({"S0": [...], "S1": [...]}, or
# {"profiles": [[...], ...]}). CSV: x, y, z on each row (a header is
# skipped); several outlines either apart by a blank line or with their
# name or number in a first column (name, x, y, z).

import csv
import io
import json
import os

from .protocol import ToolError

MAX_BYTES = 20 * 1024 * 1024


def _is_point(p):
    return isinstance(p, (list, tuple)) and len(p) in (2, 3) and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in p)


def _is_outline(o):
    return isinstance(o, (list, tuple)) and len(o) >= 2 and all(_is_point(p) for p in o)


def _pt(p):
    return [float(v) for v in p] + ([0.0] if len(p) == 2 else [])


def _num(s):
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


def read_text(path, key):
    if not os.path.isfile(path):
        raise ToolError("not_found", f"{key}: {path} — no such file (a relative path is in the session's folder).")
    if os.path.getsize(path) > MAX_BYTES:
        raise ToolError("invalid_input", f"{key}: {path} is over {MAX_BYTES // (1024 * 1024)} MB.")
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


def parse_csv(text):
    """[(name, [[x, y, z] …])] in file order."""
    groups, order = {}, []
    blank_groups = [[]]
    named = None
    for row in csv.reader(io.StringIO(text)):
        cells = [c.strip() for c in row]
        if not cells or all(c == "" for c in cells):
            if blank_groups[-1]:
                blank_groups.append([])
            continue
        if cells[0].startswith("#"):
            continue
        cells = [c for c in cells if c != ""]
        if not all(_num(c) for c in cells[-3:]) or len(cells) < 2:
            continue  # a header
        if len(cells) >= 4:
            named = True
            name, xyz = cells[0], cells[-3:]
            if name not in groups:
                groups[name] = []
                order.append(name)
            groups[name].append([float(v) for v in xyz])
        else:
            blank_groups[-1].append(_pt([float(v) for v in cells[-3:]]))
    if named:
        return [(n, groups[n]) for n in order]
    return [(str(i), g) for i, g in enumerate(x for x in blank_groups if x)]


def outlines(path, key=None, what="points_file"):
    """Every outline in the file, [(name, points)] in file order, or the one
    key names (a name, or a number counting from 0)."""
    text = read_text(path, what)
    if path.lower().endswith(".csv"):
        found = parse_csv(text)
    else:
        try:
            data = json.loads(text)
        except ValueError as e:
            raise ToolError("invalid_input", f"{what}: {os.path.basename(path)} is not JSON ({e}); a .csv file is read as x, y, z rows.")
        if isinstance(data, dict):
            if key is not None and not isinstance(key, int):
                if key not in data:
                    raise ToolError("invalid_input", f"key: {key!r} is not in {os.path.basename(path)} — it holds {', '.join(map(str, list(data)[:12]))}.")
                data, key = data[key], None
            elif "profiles" in data:
                data = data["profiles"]
            elif "points" in data:
                data = data["points"]
        if isinstance(data, dict):
            found = [(str(k), v) for k, v in data.items()]
        elif _is_outline(data):
            found = [("0", data)]
        elif isinstance(data, list):
            found = [(str(i), v) for i, v in enumerate(data)]
        else:
            found = []
        for name, o in found:
            if not _is_outline(o):
                raise ToolError("invalid_input", f"{what}: {os.path.basename(path)}[{name}] is not a list of [x, y, z] points.")
        found = [(n, [_pt(p) for p in o]) for n, o in found]
    if not found:
        raise ToolError("invalid_input", f"{what}: no points in {os.path.basename(path)} — a list of [x, y, z] (or of such lists), or x, y, z rows in a .csv.")
    if key is None:
        return found
    if isinstance(key, bool):
        raise ToolError("invalid_input", "key: an outline's name, or its number from 0.")
    if isinstance(key, int):
        if not -len(found) <= key < len(found):
            raise ToolError("invalid_input", f"key: {key} — {os.path.basename(path)} holds {len(found)} outline{'s' if len(found) != 1 else ''} (0 … {len(found) - 1}).")
        return [found[key]]
    hit = [x for x in found if x[0] == str(key)]
    if not hit:
        raise ToolError("invalid_input", f"key: {key!r} is not in {os.path.basename(path)} — it holds {', '.join(n for n, _ in found[:12])}.")
    return hit


def one_outline(path, key=None, what="points_file"):
    """The points of the one outline the file (or key) gives."""
    found = outlines(path, key, what)
    if len(found) != 1:
        raise ToolError("invalid_input", f"{what}: {os.path.basename(path)} holds {len(found)} outlines — key picks one (a name or a number from 0), or part_loft {{ profiles_file }} takes them all.")
    return found[0][1]
