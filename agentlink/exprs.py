# SPDX-License-Identifier: LGPL-2.1-or-later
# Expressions as a person writes them: a parameter by its bare name ("size",
# "size / 2 + 1") taken as the Params sheet's alias (Params.size), as
# param_set answers it. FreeCAD reads a bare name as a property of the object
# the expression is on, so "size" bound to BaseSketch.reach was refused
# ("Property 'size' not found"). Pure Python: no FreeCAD here.

import re

from .cells import CONSTANTS, UNITS

IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# FreeCAD's own words in an expression (its parser's units and constants):
# never a parameter, whatever the sheet holds (units after a number are
# caught by position as well).
RESERVED = set(UNITS) | set(CONSTANTS)


def qualify(expr, names, sheet, keep=()):
    """(expression, {bare: qualified}) with every bare name in names written
    as sheet.name: not one after a "." or "#" (a member, a document), not
    one before "." or "(" (an object, a function), not inside <<…>> or
    quotes, not a unit right after a number, not one in keep (the
    expression's own names: an alias in the sheet it is in)."""
    if not isinstance(expr, str) or not names:
        return expr, {}
    names = set(names) - set(keep) - RESERVED
    out, done, i, n = [], {}, 0, len(expr)
    while i < n:
        c = expr[i]
        if expr.startswith("<<", i):
            j = expr.find(">>", i + 2)
            j = n if j < 0 else j + 2
            out.append(expr[i:j])
            i = j
            continue
        if c in "\"'":
            j = expr.find(c, i + 1)
            j = n if j < 0 else j + 1
            out.append(expr[i:j])
            i = j
            continue
        m = IDENT.match(expr, i)
        if m and (i == 0 or not (expr[i - 1].isalnum() or expr[i - 1] == "_")):
            word = m.group(0)
            j = m.end()
            before = expr[:i].rstrip()
            after = expr[j:].lstrip()
            member = before.endswith((".", "#"))
            owner = after.startswith((".", "("))
            unit = bool(before) and (before[-1].isdigit() or before.endswith(".")) and word in RESERVED
            if word in names and not member and not owner and not unit and not re.search(r"\d$", before[-1:] if before else ""):
                q = f"{sheet}.{word}"
                out.append(q)
                done[word] = q
            else:
                out.append(word)
            i = j
            continue
        if c.isdigit():
            # A number with its letters (1e3, 0x10) stays whole.
            m = re.match(r"\d+(?:\.\d*)?(?:[eE][+-]?\d+)?", expr[i:])
            out.append(m.group(0))
            i += len(m.group(0))
            continue
        out.append(c)
        i += 1
    return "".join(out), done
