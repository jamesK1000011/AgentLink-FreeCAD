# Materials, FEM and strength as data (tag: datafem, 2026-11-16)

Checkout `wt3/d10`, base `2097f32`. Patch: `datafem.patch` (`git add -A -N`, `git diff 2097f32`, FILES
excluded; `git apply --check` on a clean `2097f32` passes). Nothing committed or pushed, no network.
**Nothing ran on FreeCAD, Gmsh or CalculiX**: every proof here is plain Python on a stand-in that solves
nothing.

## Where it stopped

All three files are finished, each whole. Nothing remains of the task.

| File | State |
|---|---|
| `families/material.py` (4) | all 4 are data; no `Tool(...)` and no handler left |
| `families/fem_more.py` (3) | all 3 are data; no `Tool(...)` and no handler left |
| `families/strength.py` (16) | all 16 are data; 2054 → 1583 lines, no `Tool(...)` and no handler left |

## Counts

- **Converted: 23. Kept as code: 0.** Thin entries: none is one helper call; the thinnest are listed below.
- `agentlink/data/tools.json`: 209 → 232 entries, appended at the end in each file's old listing order,
  all `steps`. The diff of the file is 1161 added lines, 0 removed (the generator asserts the 209 before
  are the same bytes). No `family` key: each of the three groups (`material`, `fem_more`, `strength`) has
  one file.
- **No change to `runners.py`, `expr.py`, `tooldata.py` or the schema.**
- Full suite (`timeout 290 python3 -m pytest -q tests`): **908 passed, 338 skipped, 0 failed** in 217 s.
  `tests/test_files.py` did not complain here, though the brief expected it to; FILES was left alone.
- `scripts/tool_index.py --check` and `scripts/tool_summary.py --check`: both exit 0.
- `python3.11 -m py_compile` passes on the three family files and the four new test files.
- `docs/data-tools.md`: one paragraph added.
- `health.register("strength", _health)` is still made in `strength.tools()`; `NOT_SOLVERS`, `ccx_hint`,
  `gmsh_run`, `self_weight`, `fem_route_why`, `unmatched`, `_setup_said`, `_same_in`, `_query_words`,
  `unheld_words`, `mark_helper`, `solid_holder` are unchanged (tests/test_fem_route.py and
  test_hidden_parts.py use them). Removed as unused: `_need_study` (its refusal is now a step of each
  entry), `TRAPS` (its words are in the two descriptions), the `Tool` / `obj` imports.

## Per tool

Each entry holds the description and schema (from the snapshot of the code at `2097f32`), the checks with
their refusals word for word as `refuse` steps (131 in the 23 entries), the order, and the answer's
fields and words.

### material.py

| Tool | As data | Helpers |
|---|---|---|
| `material_list` | the search, the order (named first), limit, both notes | `search_words`, `all_cards`, `haystack`, `brief`, `has_library` |
| `material_get` | the card's fields, missing, the "typical figures" note in the entry | `card` |
| `material_set` | 10 refusals; custom card built in the entry; the owning add-on's early answer; mass, notes, missing | `custom_id`, `defs`, `write`, `owner`, `library_id`, `shape_material`, `masses` |
| `material_clear` | owner's early answer, hadNone | `owner`, `read_materials`, `write` |

### fem_more.py

| Tool | As data | Helpers |
|---|---|---|
| `fem_add` | kind and availability checks, the analysis (new or found, `picks.one_of` with the site's three texts kept in the entry), the maker by need (`choose`), refs parsed in an `each` with its refusals, the answer | `objects_fem`, `KINDS` (table), `analyses`, `ref_parts`, `face_names`, `set_props`, `settable`, `shown` |
| `fem_mesh` | netgen (the fallback run as a `try`, the object removed in `refuse.first`), to_mesh, clear_groups, the order of the mesh checks | `recompute_quietly`, `netgen_run`, `surface_maker`, `fem_surface`, `mesh_module`, `set_props` |
| `fem_linearize` | both sources (pipeline, CalculiX result), 7 refusals, the answer and its note ("FEA is a feasibility check, not a sign-off", byte for byte) | `point`, `nearest_samples`, `membrane_bending` |

### strength.py

| Tool | As data | Solver / reading helpers it calls |
|---|---|---|
| `fea_setup` | solid checks (both codes), default mesh, element estimate, material, keep / reset, every note | `solid_holder`, `of_body`, `setup_said`, `unmatched` |
| `fea_hold` | `choose` by kind with each kind's checks and note | `pick_both`, `faces_normal`, `same_in` |
| `fea_load` | `choose` by kind, 13 refusals | `pick_both`, `faces_normal`, `alpha_of`, `vector`, `same_in` |
| `fea_refine`, `fea_clear`, `fea_results` | whole | `forget`, `stats` |
| `fea_export` | formats, the no-elements refusal, the answer | `write_vtu`, `write_csv` |
| `fea_probe` | points, line, faces, each refusal, the answer's shape | `Probe` (at, ends, along, on_faces), `solved_body` |
| `fea_chart` | histogram / line / table, rows, titles, the CSV and SVG steps; the line's sampling refusal and warning are repeated here (the handler called `fea_probe`) | `Probe`, `field_values`, `histogram`, `distance`, `chart_svg`, `csv_text`, `write_text` |
| `fea_modes` | checks, held / free wording, note, warnings | `modes_run`, `mode_rows` |
| `fea_buckle` | checks, verdict and note by factor | `buckle_run`, `bulge_rows` |
| `fea_heat` | checks; the temperatures, heat and air loops with their refusals; warnings by softening point | `meshed`, `hold_temperature`, `heated`, `rest_faces`, `film_faces`, `heat_solve`, `keep_heat`, `where` |
| `fea_shell` | 12 refusals, the holds loop, the answer and its warning | `binaries`, `shell_of`, `shell_meshed`, `shell_elements`, `boundary_edges`, `nearest_edges`, `edge_nodes`, `shell_deck`, `shell_solve`, `shell_peaks` |
| `fea_parts` | checks per part, the study, touching, both warnings, the contact note | `parts_holder`, `touching`, `overlapping` |
| `fea_native` | solver and equation checks, each hold and load as a step with its `skipped` words, the answer | `new_analysis`, `native_material`, `native_mesh`, `fixed_on`, `pressure_on`, `temperature_on`, `gravity_on`, `force_on`, `elmer_conditions`, `elmer_write` |
| `fea_solve` | the five study checks, the no-results refusal with its three clauses, `solvedBy`, safety, every warning, parts and joined, the kept field | `solve_run` (route choice and both routes), `peaks`, `plastic_strain`, `part_rows`, `keep_solve`, `unheld_solids` |

**Thinnest entries:** `fea_modes` and `fea_buckle` (checks, one run helper, one reading helper, the
answer). Allowed by the brief for solver runs; said here so it is not missed.

### Words that are still in code, not in an entry

- **Solver-run refusals** (allowed by the brief): programs not found, Gmsh / CalculiX over time or
  refused, no volume elements, no tetrahedra, fewer than 3 held nodes, no element faces on a load, no
  elements in a part (`_meshed`, `_assemble`, `_run`, `_solve_own`, `_fem_build_and_run`, `gmsh_run`,
  `_elmer_write`).
- `fem_more.set_props`: its four refusals. Its own `except` wraps the inner three into the fourth, so it
  was kept as one helper (shared by `fem_add` and `fem_mesh`) rather than risk the wrapping.
- `fea_solve`'s unheld-solids refusal is `"=unheld_words(…)"` (the one refusal of 131 that is an
  expression): `tests/test_hidden_parts.py` pins that function's words.
- `fea_setup`'s kept / dropped notes come from `_setup_said`, and `unmatched`'s lines from `unmatched`:
  `tests/test_fem_route.py` pins both.
- `solvedBy`'s reason (`fem_route_why`, and "FreeCAD's FEM route failed here: …" in `solve_run`).
- `solid_holder`'s range refusal remains as a guard for a study read later; `fea_setup` checks it first
  in the entry.
- `_elmer_conditions` still has its three "need the … equation" refusals; the entry checks the same
  conditions first, so they are not reached.
- Shared readers as before: `picks.find`, `shaped`, `element`, `vec3`, `one_of`; `facepick.pick`;
  `session.body`.

## Behaviour differences

**None found: 0 of 424 cases differ.** Not identical in form, compared and equal:

- `fea_chart` no longer calls another tool's handler; it runs the same reading (`Probe`) itself.
- `fea_buckle` reads the mode shapes inside `bulge_rows`, after the no-factors check as before.
- `material_list` tests the words before the category (the handler: category first); same hits.
- Kept as they were, not fixed: `fea_native`'s force direction line (`fv.normalize().x, fv.y, fv.z`),
  `fea_shell` with no time limit handling on Gmsh (a slow Gmsh is a crash; a case), `fem_mesh` leaving its
  Netgen object when the bounded run is refused for time.

## Proof here

`tests/test_datafem_data.py` (the pattern of `test_datapart2_data.py`, `BASE = "2097f32"`), with
`_datafem_before.py`, `_datafem_cases.py`, `_datafem_standin.py`. The stand-in wraps
`_datapart_standin.install()` in the child process only; **no existing stand-in is changed**.

- **Identity**, 23 tools: name, description bytes, schema with key order, changes, reads, group.
- **Old handler against new entry, 424 cases** (188 answer, 231 refuse, 5 crash alike), each in a fresh
  session: the answer or refusal, every traced operation and property set in order, the objects left,
  **the files written** (decks, .geo, CSV, SVG, VTU: each one's first 600 characters) and **what is kept
  with the session** (`_agentlink_fea`, `_agentlink_heat`, CalculiX's tail). 0 differ. 36 answers and
  refusals are pinned to fixed text (`EXPECT`).
- **Every `refuse` step is reached**: `UNREACHED` is empty. (The expression-worded one is reached by two
  cases and pinned in `EXPECT`.)
- **Every helper present**: the `--helpers` child answers `{}`.
- No helper touches a FreeCAD module when `tools()` builds its dict (the full suite passing on other
  families' stand-ins is the check).

What the stand-in is not: Gmsh and CalculiX are functions that write the files a case says; `ccx_io`'s
readers answer a case's numbers and its deck writers are logged, not run; `facepick.pick` picks by face
name; a FEM mesh is ten fixed nodes. The proof is of order, words, files and answer shape, not of one
number of mechanics.

## Live models

`docs/hardening/models/sheetfem-fem-model.json` (43 calls, numbered from 1):

| Tool | Calls | | Tool | Calls |
|---|---|---|---|---|
| `material_set` | 2 | | `fea_buckle` | 30 |
| `fea_setup` | 3, 4 | | `fea_modes` | 31 |
| `fea_solve` | 5, 10, 28, 35, 38 | | `fea_heat` | 32 |
| `fea_hold` | 6, 7 | | `fea_refine` | 37, 39 |
| `fea_load` | 8, 9, 26, 29, 33, 34, 36 | | `fea_shell` | 40 |
| `fea_results` | 11, 27 | | `fea_parts` | 42 |
| `fea_probe` | 12 | | `fea_clear` | 43 |
| `fea_chart` | 13, 14, 15 | | `fem_linearize` | 17, 18 |
| `fea_export` | 16 | | `fem_mesh` | 19, 24 |
| `fea_native` | 25 | | `fem_add` | 20, 21, 22, 23 |

`docs/hardening/models/coredoc-model.json`: `material_list` 54, 59; `material_get` 55; `material_set` 56,
60; `material_clear` 61.

**No converted tool is without a live call.** One call only: `fea_probe`, `fea_export`, `fea_native`,
`fea_buckle`, `fea_modes`, `fea_heat`, `fea_shell`, `fea_parts`, `fea_clear`, `material_get`,
`material_clear`.

## Unproven, and risks

1. **Nothing ran on FreeCAD.** `sheetfem-fem-model.json` on FreeCAD 1.1.3 with Gmsh and CalculiX is the
   proof still owed, and matters most for `fea_solve` (the riskiest tool before this change, per
   `sheetfem-findings.md`; its route code was moved, not edited).
2. **Values set on FEM objects** are tuples and lists as the code had them (`References = [(o, (…))]`,
   `Direction = (line, ["Edge1"])`); the trace prints tuple and list alike, so tuple-ness was checked by
   reading. In `fem_add` the references are built in the entry (`(ro, tuple(subs))`).
3. **numpy types**: `Probe.on_faces` and `histogram` now hand plain floats to the entry, which rounds
   them; equal in every case here, since both are float64.
4. `time.time` is fixed in the stand-in, so `seconds` is compared as 0.0 only.
5. `fea_native`'s Elmer half and `_elmer_write` were not checked against FreeCAD's Elmer writer before
   (sheetfem-findings) and are not here either; they were moved unchanged.
6. FILES will need regenerating for the four new files under `tests/` when this is merged.
