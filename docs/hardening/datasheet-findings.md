# Spreadsheets and the document-level tools as data (tag: datasheet, 2026-11-16)

Checkout `wt3/d14`, base `effbcc7`. Patch: `datasheet.patch` (`git add -A -N`, `git diff effbcc7`, FILES not
touched; `git apply --check` on a clean `effbcc7` passes). Nothing committed or pushed, no network.
**Nothing ran on FreeCAD**: every proof here is plain Python on a stand-in.

## Where it stopped

Both files are finished, each whole. Nothing remains of the task.

| File | State |
|---|---|
| `families/sheet.py` (11 `sheet_*`) | all 11 are data; 872 -> 427 lines, no `Tool(...)` and no handler left |
| `families/std_more.py` (the 16 still in code) | all 16 are data; 774 -> 385 lines, no `Tool(...)` and no handler left in the file |

## Counts

- **Converted: 27. Kept as code: 0. Thin entries: 0.**
- `agentlink/data/tools.json`: 264 -> 291 entries, appended at the end in the old listing order (sheet's 11, then
  std_more's 16), all `steps`; the file's diff is 2010 added lines, 0 removed. No `family` key: `sheet.py` is the
  only file of group `sheet`, and std_more's earlier entries have none either.
- `sheet.py` ends `runners.tools(GROUP, s, helpers)`; `std_more.py` has its new helpers in their own dict
  `doc_helpers`, added with `helpers.update(doc_helpers)` just before the return. Everything in it that reaches
  FreeCAD or Part is a lambda or a function that imports when called.
- **No change to `runners.py`, `expr.py`, `tooldata.py` or the schema.**
- Suite (`timeout 290 python3 -m pytest -q tests`): **976 passed, 347 skipped, 0 failed** in 257 s, run before
  `git add -N`. With the new test files added to the index, `tests/test_files.py` fails (FILES stale), as expected;
  FILES left alone. That full run was before the paragraph in `docs/data-tools.md`; after it,
  test_files, test_tool_index, test_tooldata, test_runners, test_declared and test_datasheet_data were run again
  (55 passed, the FILES one failing).
- `scripts/tool_index.py --check` and `scripts/tool_summary.py --check`: both exit 0.
- `python3.11 -m py_compile` passes on the two family files and the four new test files.
- `docs/data-tools.md`: one paragraph added.

## Per tool

Every entry holds the description and schema (from the snapshot at `effbcc7`), each check with its refusal word
for word as a `refuse` step (108 in the 27 entries), the order of steps and the answer's fields.

### `sheet.py`

| Tool | As data | Helpers it calls |
|---|---|---|
| `sheet_new` | | `unique`, `name_ok`, `done` |
| `sheet_list` | the row per sheet is an `each` | `sheets`, `filled`, `aliases`, `users`, `tables`, `bounds` |
| `sheet_read` | range / cells narrowing, the 400-cell cap, bound ranges, tables | `find`, `filled`, `range_of`, `address`, `cell_reading`, `bindings`, `tables`, `table_reading` |
| `sheet_set` | the old inner `write_cells` and `alias_or_refuse` are steps: each cell's content, the Params qualifying, the formula kept as text, each alias rule; the failing-cell refusal undoes in `refuse.first` | `address`, `grid`, `content`, `params_sheet`, `qualified`, `alias_problem`, `alias_cell`, `check`, `cell_reading`, `users`, `bodies_now`, `done` |
| `sheet_clear` | | `small_range`, `range_of`, `filled`, `aliases`, `users`, `check`, `done` |
| `sheet_format` | each of the eight formats is a `when` block; colour and background are one `each` over (key, setter, clearer) | `call_on`, `hex_rgba`, `parse_range`, `col_name`, `check`, `cell_reading`, `done` |
| `sheet_rows` | `picks.choice` became a `refuse` step | `col_ok`, `MAX_ROW`, `check`, `done` |
| `sheet_import` | new sheet or one to fill as `when` / `else` | `path_of`, `isfile`, `DELIM`, `stem`, `basename`, `filled`, `check`, `done` |
| `sheet_export` | | `path_of`, `DELIM`, `folder_for`, `isfile`, `line_count`, `getsize` |
| `sheet_chart` | the series loop is steps | `ref_list`, `column`, `chart_svg`, `chart_path`, `write_text` |
| `sheet_table` | `choose` by action; make's 19 checks, the cells written, the switch and its binding in order; the old `table_of` is steps once, before `use` and `add` | `address`, `parse`, `range_text`, `cell`, `content`, `cell_content`, `set_prop`, `bind_row`, `table_at`, `table_reading`, `tables`, `value_of`, `offset`, `check`, `bodies_now`, `users`, `done` |

New named helpers, each with a docstring: `said` (a cells function's answer or what it says is wrong: behind
`content`, `grid`, `hex_rgba`), `alias_cell`, `bind_row`, `line_count`, `write_text`, `qualified`, `params_sheet`,
`chart_path`, `column`, `chart_svg`, `table_at`, `call_on` (a lambda). Docstrings added to the ones that had none.

### `std_more.py`

| Tool | As data | Helpers it calls |
|---|---|---|
| `doc_graph` | counts, roots, uses are expressions | `dot_path`, `dot_text`, `write_text`, `which`, `dot_draw` |
| `object_freeze` | | `objs`, `gui_up`, `frozen`, `toggle_freeze`, `snapshot` |
| `units_convert` | the two quantities in a `try` | `quantity` |
| `object_align` | the checks and the answer; the fit is one algorithm | `tool_module`, `objs`, `pair_points`, `rigid_fit`, `moved_by`, `degrees`, `done` |
| `link_make` | group as an early `answer`; the link's answer is `late` (read after the recompute, as the handler's lambda) | `objs`, `split_ref`, `find`, `element`, `placed`, `placement`, `placement_json`, `done` |
| `link_edit` | import as an early `answer`, then `choose` replace / unlink | `objs`, `link_target`, `find`, `get_shape`, `repoint`, `snapshot`, `done` |
| `object_duplicate` | | `objs`, `get_shape`, `unique`, `done` |
| `doc_merge` | | `local`, `isfile`, `basename`, `is_records`, `errors`, `snapshot` |
| `doc_info` | | `INFO_PROPS` (a table), `set_prop`, `getsize`, `isfile` |
| `doc_revert` | | `isfile`, `close_document`, `open_document`, `as_its_file`, `switch` |
| `doc_save_all` | | `documents`, `mark_saved` |
| `text_document` | | `unique`, `done` |
| `object_appearance` | colour, faces, transparency per object in order | `objs`, `colour`, `random_colour`, `keep_colour`, `hex_of` |
| `scad_tidy` | color_code as an early `answer`, then `choose` by action | `objs`, `shape_kind`, `SCAD_COLOURS`, `colour`, `keep_untouched`, `tool_module`, `no_placement`, `set_prop`, `find`, `done` |
| `robot_tool` | | `find`, `shaped`, `placed`, `placement`, `done` |
| `sheet_cells` | | `find`, `tidy_range`, `done` |

### Helpers that still refuse in their own words

Shared readers, unchanged, compared in the cases, but in code and not counted among the 108: sheet's `find`
(no sheet / say which / not here), `address`, `range_of`, `small_range`; **`check`** (the guard seven sheet tools
end with: "<what> breaks <cells or objects> — nothing was kept.", with its undo); picks' `find`, `shaped`,
`element`, `objs` / `ref_list` (the message is an argument in the entry for `sheet_chart`'s y); `colour`
(doc.py); `doc` in std_more ("No document open").

## Behaviour differences

None found: 0 of 269 cases differ. Not identical in form:

- `sheet_table` make and use: the design table is found again with `table_at` (the handler's `next(...)`, same
  code, so the same StopIteration if FreeCAD lost the table).
- `sheet_table` make no longer writes `values` back into the caller's `configs` (the handler replaced a
  `{param: value}` by a list in the arguments it was given); the cells written are the same.
- `object_align` loads numpy as its first step (`tool_module('numpy')`) to keep the handler's order: import,
  then checks.
- `scad_tidy`'s OpenSCAD modules are loaded with `importlib.import_module` (`tool_module`, as the compound
  tools already do) where the handler had `import x`; a missing module is still a crash (one case).
- `units_convert`: `'1 ' + str(to)` for the handler's f-string.
- Kept as they were, not fixed: `sheet_set`'s rows refusal reads "rows: rows: a list of lists, one per row.";
  `sheet_table` add with `true` for a value crashes (AddressError not caught there; a case); a config that is
  not an object crashes (a case).

## Proof here

`tests/test_datasheet_data.py` (the pattern of `test_datapart2_data.py`, `BASE = "effbcc7"`), with
`_datasheet_before.py`, `_datasheet_cases.py`, `_datasheet_standin.py`. The stand-in wraps
`_datapart_standin.install()` in the child process only; no existing stand-in file is changed.

- **Identity**, 27 tools: name, description bytes, schema with key order, changes, reads, group, against a
  snapshot of what the code made at `effbcc7`; the snapshot is checked against that commit's source.
- **Old handler against new entry, 269 cases** (140 sheet, 129 std_more: 110 answer, 156 refuse, 3 crash
  alike), each in a fresh session: the answer or refusal, every call on a sheet / document / object, object
  added or removed and property set in order, and the objects left. **0 differ.** 47 are also pinned to fixed
  text (`EXPECT`).
- **Every `refuse` step is reached**: 108 in the 27 entries, `UNREACHED` is empty.
- **Every helper present** (`--helpers` answers `{}`).
- No handler or `Tool(...)` of a converted name is left in either file.

What the stand-in is not: FreeCAD. Its sheet keeps cells, aliases and formats and works out plain arithmetic,
quantities, a bound row and a hiddenref; an expression it cannot work out is "ERR: …"; a formula with "((" is
kept as text. Enumerations, links, merge, revert, save, the freeze command, the OpenSCAD modules, GraphViz
and units answer by simple rules a case steers. numpy is real. The proof is of order, words and answer shape.
Weak spots of the cases: `link_edit` unlink never showed `repointed` (the stand-in's group did not count as a
user for `picks.repoint`); a Document's own properties set by `doc_info` are not in the trace (read back in
the answer only).

## Live models (calls numbered from 1)

`docs/hardening/models/sheetfem-sheet-model.json` (55 calls):

| Tool | Calls |
|---|---|
| `sheet_new` | 6 |
| `sheet_set` | 7, 8, 9, 10, 11, 12, 17, 49 |
| `sheet_read` | 18, 19, 24 |
| `sheet_list` | 20 |
| `sheet_format` | 21, 22, 28 |
| `sheet_rows` | 23, 25 |
| `sheet_cells` | 26, 27 |
| `sheet_clear` | 29, 55 |
| `sheet_export` | 30 |
| `sheet_import` | 31 |
| `sheet_table` | 43, 48, 50, 51, 52, 53 |
| `sheet_chart` | 54 |

`docs/hardening/models/coredoc-model.json` (114 calls):

| Tool | Calls |
|---|---|
| `units_convert` | 12, 13, 14 |
| `link_make` | 22, 23 |
| `link_edit` | 24, 25 |
| `object_duplicate` | 26 |
| `object_align` | 27, 28 |
| `text_document` | 29, 30 |
| `doc_info` | 31 |
| `doc_graph` | 32 |
| `object_appearance` | 33, 34 |
| `object_freeze` | 35, 37 |
| `scad_tidy` | 78, 79, 80, 81 |
| `robot_tool` | 93 |
| `doc_save_all` | 104 |
| `doc_merge` | 106, 107 |
| `doc_revert` | 110 |

`hubrest-model.json` (46 calls) calls none of the 27. `asmtd-techdraw-model.json` calls `sheet_new` and
`sheet_set` once each. **No converted tool is without a live call.** One call only: `sheet_new`, `sheet_list`,
`sheet_export`, `sheet_import`, `sheet_chart`, `object_duplicate`, `doc_info`, `doc_graph`, `robot_tool`,
`doc_save_all`, `doc_revert`.

## Unproven, and risks

1. **Nothing ran on FreeCAD.** The two models above on FreeCAD 1.1.3 are the proof still owed.
2. `link_make` sets `LinkedObject` to a tuple `(object, [sub])` as the code did; the trace prints a tuple and a
   list alike, so tuple-ness was checked by reading.
3. `sheet_format`'s setters are called through `call_on(ss, name, …)` (getattr by name, as the handler's
   `getattr(ss, setter)`); `set_prop` is `setattr` (the enumeration's items, then its value: the order is the
   entry's).
4. The window-only paths (`object_freeze` on objects, view colours in `object_appearance` / `scad_tidy`) ran
   on a stand-in window only.
