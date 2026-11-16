# SPDX-License-Identifier: LGPL-2.1-or-later
# Spreadsheet cell addresses and ranges as FreeCAD's Spreadsheet writes
# them (A1, ZZ16384; "A1:C4"), and what a JSON value becomes as a cell's
# contents. No FreeCAD here.

import re

MAX_COL = 702  # ZZ
MAX_ROW = 16384
CELL = re.compile(r"^\$?([A-Za-z]{1,2})\$?([0-9]+)$")
COL = re.compile(r"^[A-Za-z]{1,2}$")
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# What FreeCAD's expression parser reads as a unit or a constant (App/Expression.l,
# FreeCAD 1.1): Sheet.setAlias and the VarSet dialog refuse these as names
# ("Invalid alias"), since Sheet.mm in an expression would read as a unit.
UNITS = frozenset("""nm um mm cm dm m km l ml Hz kHz MHz GHz THz ug mg g kg t s min h A mA kA MA K mK uK mol mmol cd
in ft thou mil yd mi mph sqft cft lb lbm oz st cwt lbf N mN kN MN Pa kPa MPa GPa bar mbar Torr mTorr uTorr psi ksi Mpsi
W mW kW VA V kV mV MS kS S mS uS Ohm kOhm MOhm C T G Wb F mF uF nF pF H mH uH nH J mJ kJ Nm VAs CV Ws kWh eV keV MeV
cal kcal deg rad gon M AS""".split())
CONSTANTS = frozenset(("pi", "e", "None", "True", "true", "False", "false"))
ALIAS = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")  # PropertySheet::isValidAlias: a letter first


class AddressError(ValueError):
    pass


def alias_problem(name):
    """Why FreeCAD would refuse this as a cell's alias (or a variable's
    name), in words, or None: the rules of PropertySheet::isValidAlias."""
    if not isinstance(name, str) or not ALIAS.match(name):
        return "letters, digits and _, starting with a letter"
    if is_cell(name):
        return "it reads as a cell address"
    if name in UNITS:
        return f"{name} is a unit in FreeCAD's expressions (a longer name: {name}_size, {name}1x)"
    if name in CONSTANTS:
        return f"{name} is a constant in FreeCAD's expressions"
    return None


def col_num(letters):
    """A → 1, Z → 26, AA → 27, ZZ → 702."""
    n = 0
    for ch in letters.upper():
        n = n * 26 + (ord(ch) - 64)
    return n


def col_name(n):
    if not 1 <= n <= MAX_COL:
        raise AddressError(f"column {n} is outside A..ZZ")
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def parse(addr):
    """'b12' → (12, 2): row and column, 1-based."""
    m = CELL.match(str(addr).strip())
    if not m:
        raise AddressError(f"{addr!r} is not a cell address (A1 … ZZ16384)")
    c, r = col_num(m.group(1)), int(m.group(2))
    if not (1 <= r <= MAX_ROW and 1 <= c <= MAX_COL):
        raise AddressError(f"{addr!r} is outside A1 … ZZ16384")
    return r, c


def name(row, col):
    if not 1 <= row <= MAX_ROW:
        raise AddressError(f"row {row} is outside 1..{MAX_ROW}")
    return f"{col_name(col)}{row}"


def is_cell(s):
    try:
        parse(s)
        return True
    except AddressError:
        return False


def parse_range(rng):
    """'A1:C3' or 'B2' → ((r0, c0), (r1, c1)), corners sorted."""
    parts = str(rng).split(":")
    if len(parts) == 1:
        a = parse(parts[0])
        return a, a
    if len(parts) != 2:
        raise AddressError(f"{rng!r} is not a range like A1:C3")
    (r0, c0), (r1, c1) = parse(parts[0]), parse(parts[1])
    return (min(r0, r1), min(c0, c1)), (max(r0, r1), max(c0, c1))


def range_text(a, b):
    s, e = name(*a), name(*b)
    return s if s == e else f"{s}:{e}"


def cells_in(rng):
    (r0, c0), (r1, c1) = parse_range(rng)
    return [name(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]


def size(rng):
    (r0, c0), (r1, c1) = parse_range(rng)
    return (r1 - r0 + 1) * (c1 - c0 + 1)


def offset(addr, drow, dcol):
    r, c = parse(addr)
    return name(r + drow, c + dcol)


def bounds(addrs):
    """The smallest range holding every address, or None."""
    rc = [parse(a) for a in addrs]
    if not rc:
        return None
    return range_text((min(r for r, _ in rc), min(c for _, c in rc)), (max(r for r, _ in rc), max(c for _, c in rc)))


def sort_key(addr):
    return parse(addr)


def content(value, text=False):
    """A JSON value as the contents FreeCAD's Sheet.set takes, as if typed:
    a number as itself, "=…" an expression, "10 mm" a quantity, other
    strings as text. text: true keeps a string as text even when it would
    read as a number or an expression ("'" in front, as FreeCAD does)."""
    if value is None:
        return ""
    if isinstance(value, bool):
        raise AddressError("a cell takes a number, a string or null, not true/false")
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            r = repr(value)
            # 2.0 -> "2"; an exponent's own zeros stay (1e-10 is not 1e-1)
            return r.rstrip("0").rstrip(".") if "." in r and "e" not in r and "n" not in r else r
        return str(value)
    if not isinstance(value, str):
        raise AddressError("a cell takes a number, a string or null")
    if text and value and not value.startswith("'"):
        return "'" + value
    return value


def grid(at, rows):
    """[[v, …], …] laid out from `at`: {address: value}, None kept (it clears)."""
    r0, c0 = parse(at)
    out = {}
    for i, row in enumerate(rows):
        if not isinstance(row, list):
            raise AddressError("rows: a list of lists, one per row")
        for j, v in enumerate(row):
            out[name(r0 + i, c0 + j)] = v
    return out


def hex_rgba(s):
    """'#rrggbb' or '#rrggbbaa' → (r, g, b, a) floats 0..1."""
    m = re.match(r"^#?([0-9a-fA-F]{6})([0-9a-fA-F]{2})?$", str(s or ""))
    if not m:
        raise AddressError(f"colour {s!r}: #rrggbb or #rrggbbaa")
    h = m.group(1) + (m.group(2) or "ff")
    return tuple(round(int(h[i:i + 2], 16) / 255.0, 4) for i in range(0, 8, 2))


def rgba_hex(t):
    if not t:
        return None
    vals = [max(0, min(255, int(round(float(x) * 255)))) for x in list(t)[:4]]
    while len(vals) < 4:
        vals.append(255)
    s = "#" + "".join(f"{v:02x}" for v in vals[:3])
    return s if vals[3] == 255 else s + f"{vals[3]:02x}"
