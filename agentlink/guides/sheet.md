<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Spreadsheets and design tables

## workflow
1. `sheet_new { name }`, or use the `Params` sheet `param_set` keeps. `sheet_list` shows every sheet.
2. Write cells as if typed: `sheet_set { sheet, cells: { A1: 40, B1: "=A1 / 2", C1: "3 mm" }, aliases: { A1: "length" } }`. A block at once: `rows: [[…], …]` from `at`.
3. Read them back with `sheet_read { sheet, range }`: what each cell holds, its value and unit, and any error.
4. Drive the part: `param_bind { target: "Pad.Length", expression: "Spreadsheet.length" }`. Then a `sheet_set` on that cell changes the part, and its answer lists what it drives.

## design tables (variants)
1. `sheet_table { action: "make", params: ["length", "width"], configs: [{ name: "S", values: [40, 20] }, { name: "L", values: [80, 40] }] }`. Numbers are mm unless `units` says otherwise (`"deg"`, `""`).
2. Bind each property to `<Sheet>.<param>` with `param_bind`.
3. Switch with `sheet_table { action: "use", config: "L" }`. Its answer gives the bodies. `add { config, values }` adds a variant.
4. The table is FreeCAD's own configuration table. In FreeCAD, the person switches it by hand through the owner's `Configuration` property (the part's Body when there is one, else a group holding the sheet, unless `owner` names another object).

## formatting and files
- `sheet_format { range, style: ["bold"], background: "#eeeeee", align: ["center"], displayUnit: "in", width, merge }`.
- `sheet_rows { action: "insert", rows: 5, count: 2 }`, or `columns: "C"`. References move with the cells.
- `sheet_import { path }` reads a CSV or TSV into a new sheet. `sheet_export { sheet }` writes the computed values out.

## names and references
- An alias starts with a letter, then letters, digits and `_`. FreeCAD refuses a cell address (`A1`), a unit (`m`, `mm`, `s`, `N`, `W`, `A`, `K`, `g`, `h`, `t`, `l`, `in`, `ft`, `deg` and the rest) and the constants `e` and `pi`. Short names collide with units: use `width`, not `W`.
- An expression reads a cell as `Spreadsheet.width` or `Spreadsheet.B2` (the object's name, from `sheet_new`), or as `<<My label>>.width` by the label.
- Inside a formula, a function's arguments are separated by `;` (`=max(A1; B1)`).
- Removing or renaming an alias rewrites the expressions that use it.

## traps
- A string that reads as a number or an expression is taken as one, as in FreeCAD. Use `text: true` to keep it as text.
- FreeCAD keeps a formula it cannot parse as plain text and reports no error. `sheet_set` refuses it instead.
- A failed cell holds `ERR: <reason>` in FreeCAD. `sheet_read` shows it as `error`.
- An empty cell has no value: `sheet_read` answers `empty: true` for it.
- A design table's active row is bound. Change the variants' rows, or switch with `use`. Don't `sheet_set` the active row.
- An error anywhere after a change (a bad expression, a feature that cannot take the value) is refused, and nothing is kept.
- `sheet_clear` refuses a range whose aliases are in use. Unbind them first, or pass `force: true`.
- Merging keeps the top-left cell and clears the others, their aliases too.
- `sheet_export` writes values only, and a quantity as its bare number in mm, deg, kg or s. An export read back with `sheet_import` has no formulas, aliases or units.
- `sheet_chart` draws a sheet's columns as an SVG chart (line, bar or scatter), with a legend and labels.
