# Measure, inspection, notes, robot and IFC tools as data (tag: datamisc, 2026-11-16)

Checkout `wt3/d11`, base `2097f32`. Patch: `datamisc.patch` (`git add -A -N`, `git diff 2097f32`, FILES
left out and not touched; `git apply --check` on a clean `2097f32` passes). Nothing committed or pushed, no network. **Nothing ran on FreeCAD**: every proof
here is plain Python on a stand-in.

## Where it stopped

| File | State |
|---|---|
| `families/measure.py` (6) | all 6 are data; no `Tool(...)` and no handler left |
| `families/inspection.py` (6) | all 6 are data; no `Tool(...)` and no handler left |
| `families/notes.py` (7) | all 7 are data; no `Tool(...)` and no handler left |
| `families/robot.py` (6) | all 6 are data; no `Tool(...)` and no handler left |
| `families/ifc.py` (6, "if room") | all 6 are data; no `Tool(...)` and no handler left |

All five files are finished, each whole. Nothing remains of the task.

## Counts

- **Converted: 31. Kept as code: 0. Thin entries: 4** (insp_read, insp_list, steps_list, ifc_find; see below).
- `agentlink/data/tools.json`: 209 → 240 entries. The 31 are appended at the end, each file's in its old
  listing order, all `steps`; the file's diff is 1305 added lines and 0 removed (the 209 before are byte for
  byte as they were). measure, inspection, notes and robot have a group each, so no `family` key; ifc.py
  shares the group `bim`, so its six say `"family": "ifc"` and the file ends
  `runners.tools(GROUP, s, helpers, family="ifc")`.
- **One line changed in an existing test, `tests/test_bim_data.py`** (not a stand-in): its helper check took
  every entry of group `bim` to be bim.py's, bim_more.py's or bim_gaps.py's, and so failed on ifc.py's six.
  It now leaves `"family": "ifc"` entries to `tests/test_datamisc_data.py`. Say if you would rather have it
  another way; without it that one test fails.
- **No change to `runners.py`, `expr.py`, `tooldata.py` or the schema.**
- Suite (`timeout 290 python3 -m pytest -q tests`): **907 passed, 338 skipped, 1 failed** in 207 s (the final state, ifc included). The one
  failure is `tests/test_files.py` (FILES stale: the four new test files), as expected; FILES left alone.
  (A first run also failed two of `tests/test_no_addon_names.py`, which wants the service name
  `mass_properties` in `families/measure.py` and nowhere else: the name is kept in a helper, `addon_mass`,
  instead of the entry.)
- `python3 scripts/tool_index.py --check` and `scripts/tool_summary.py --check`: both exit 0.
- `python3.11 -m py_compile` passes on the five family files and the four new test files.
- `docs/data-tools.md`: one paragraph added.
- `tests/test_no_addon_names.py` and every existing stand-in are unchanged.
- Family files, lines before → after: measure 547 → 363, inspection 445 → 358, notes 539 → 457, robot 360 → 181, ifc 326 → 193.

## Per tool

Every entry holds the description and schema (from the snapshot of the code at `2097f32`), its checks with
their refusals word for word as `refuse` steps (81 in the 31 entries), the order of its steps and its answer.

### `measure.py`

| Tool | As data | Helpers it calls |
|---|---|---|
| `shape_query` | the query, the limit check (`picks.number(…, msg=)` became `num` + a `refuse`), the answer with `more` | `query`, `num` |
| `measure` | a alone as an early `answer`; the same-thing refusal; angle by what the two are (flat/flat with gap, line/line, face/line), centres | `resolve`, `describe`, `angle_between`, `vector`, `vec`, `r` |
| `section` | plane, cut, the miss refusal before the tolerance and maxPoints checks (the handler's order), the outlines as two `each`, the answer's plane | `solid_body`, `direction`, `vec3`, `num`, `plane_through`, `box_of`, `vec`, `r` |
| `measure_mass` | the add-on's answer as an early `answer`; density / stock / recorded / printed-so-PLA / card as branches with their 4 refusals; principal axes in a `try` | `solid_body`, `addon_mass`, `recorded`, `printed`, `card`, `inertia`, `MASS_DENSITY` (a table), `num`, `vec`, `r` |
| `clearance` | distance, then state by the common volume, `meets` | `solid_body`, `box_of`, `num`, `vec`, `r` |
| `measure_keep` | kind, count, each element's 3 checks in an `each`, the object made in a `try` (unavailable), the links by count, the invalid result removed and refused | `KEEP`, `TAKES` (tables), `wrong`, `ref_list`, `resolve`, `find`, `prop`, `unique`, `snapshot`, `step` |

### `inspection.py`

| Tool | As data | Helpers it calls |
|---|---|---|
| `insp_run` | file or object (mesh / points by extension), a body meshed first, nominals checked in an `each`, radius and band, the feature, the empty-result refusal, the notes after the reading (12 refusals) | `in_file`, `isfile`, `file_ext`, `file_stem`, `read_mesh`, `points_module`, `read_points`, `find`, `kind_of`, `mesh_of_body`, `tol_of`, `tol_props`, `reading`, `num`, `unique` |
| `insp_update` | everything checked before anything is set, then the sets in order; `finish` with a late reading | `ins_of`, `band`, `tol_of`, `find`, `kind_of`, `tol_props`, `reading`, `finish`, `num` |
| `insp_read` | **thin**: the inspection, its reading | `ins_of`, `reading` |
| `insp_list` | **thin**: each reading cut to the list's eight fields; the note when empty | `inspections`, `reading` |
| `insp_faces` | the 4 refusals, the bodies with faces, reach, limit, failing | `ins_of`, `lined_up`, `has_faces`, `find`, `band`, `faces_mesh`, `by_face` |
| `insp_export` | names, the two files, the answer's files and summary | `ins_of`, `reading`, `made`, `point_rows`, `write_csv`, `write_json` |

### `notes.py`

| Tool | As data | Helpers it calls |
|---|---|---|
| `note_add` | text, faces or at (3 refusals), the note | `body`, `pick_faces`, `add_note`, `note_view`, `notes` |
| `note_list` | follow in a `try`, the moved ones, open, waiting, the answer's optional fields | `follow`, `error_words`, `notes`, `save_notes`, `note_view` |
| `note_answer`, `note_done`, `note_delete` | the note found, changed, saved | `notes`, `find_note`, `save_notes`, `note_view` |
| `steps_list` | **thin**: the body, its steps | `body_pd`, `steps_of` |
| `steps_render` | the 3 refusals, the folder, a picture a step in an `each`, the sheet and `_png` | `body_pd`, `steps_of`, `local`, `make_folder`, `framing`, `step_picture`, `caption`, `png`, `write_bytes`, `join`, `contact_sheet`, `VIEWS` |

### `robot.py`

| Tool | As data | Helpers it calls |
|---|---|---|
| `robot_new` | model / kinematics refusals, the three sources of kinematics as branches, base and tool, `finish` with a late state | `local`, `isfile`, `basename`, `lib_file`, `placement`, `settle`, `state`, `finish`, `unique`, `MODELS` |
| `robot_move` | one-of check, axes / tcp / home as branches (each axis set by name), reached / off_mm | `robot`, `placement`, `tool_of`, `prop`, `state`, `settled` |
| `robot_path` | edges (each checked, one object, the two type names tried in an `each`) or waypoints (each checked in an `each`) | `ref_list`, `resolve`, `find`, `placement`, `waypoint`, `trajectory_of`, `num`, `unique`, `settled` |
| `robot_run` | checks, the sweep, the axes put back, verdict and misses | `robot`, `trajectory`, `axes_of`, `sweep` |
| `robot_trajectory` | `choose` join / dress, the dress-up's settings, the bad `add` removed in `refuse.first` | `trajectory`, `posed`, `unique`, `snapshot`, `step` |
| `robot_export` | the path, the exporter in a `try` (failed), the two no-file refusals | `robot`, `trajectory`, `isabs`, `join`, `out_dir`, `made`, `make_folder`, `dirname`, `krl`, `isfile`, `read_text` |

### `ifc.py` (`"family": "ifc"`)

| Tool | As data | Helpers it calls |
|---|---|---|
| `ifc_open` | the 3 refusals (the unreadable file in a `try`), the counts by class, the answer | `where`, `isfile`, `ifc_file`, `opened` |
| `ifc_find` | **thin**: the selection, the limit, `more` | `model`, `select`, `row` |
| `ifc_edit` | the 5 checks in the handler's order, properties grouped by set in an `each` (refusal), material found or made, the storey (refusal), then per element: attributes in a `try` (refusal), each set found or added, material and storey with the older one-product call as a `try` on TypeError, the classification or its property-set fallback | `model`, `select`, `api`, `get_pset`, `real_classification`, `row` |
| `ifc_remove` | ids needed, each removed | `model`, `select`, `api`, `row` |
| `ifc_save` | the copy's name or overwrite | `model`, `where`, `file_stem`, `make_folder`, `dirname`, `file_size` |
| `ifc_diff` | both files in an `each` (2 refusals each way), added / removed by id, the changed ones | `where`, `isfile`, `ifc_file`, `row`, `differences`, `both` |

### New named helpers (each with a docstring)

- measure: `wrong` (was nested), `recorded`, `printed`, `card`, `addon_mass`, `prop`; `KEEP`, `TAKES` moved to
  module level; docstrings added to `r`, `surface_type`, `curve_type`, `line_dir`, `describe_face`,
  `describe_edge`, `rng`, `describe`, `angle_between`.
- inspection: `has_faces`, `faces_mesh`, `by_face`, `lined_up`, `point_rows`, `write_csv`, `write_json`,
  `read_points`, `points_module`; docstrings added to `kind_of`, `inspections`, `band`, `find`, `ins_of`,
  `tol_of`, `mesh_of_body`, `reading`.
- notes: `framing`, `step_picture`, `contact_sheet`, `write_bytes`, `error_words`, `body_pd` (was `_body_pd`);
  docstrings added to `notes_of`, `save_notes`, `note_view`, `find_note`.
- robot: `sweep` (the sampling loop of robot_run), `posed`, `krl`, `read_text`, `prop`; docstrings added to
  `lib_file`, `placement`, `pl_out`, `axes_of`, `robots`, `robot`, `trajectory`, `state`.

- ifc: `differences` (the per-element comparison of ifc_diff), `opened`, `both` (the ids two files share:
  the expressions have no `&`); docstrings added to `run`, `storey_of`, `psets_of`, `material_of`, `row`,
  `classifications`, `model`, `where`, `select`.

Every FreeCAD / Part / Mesh / Robot / IfcOpenShell attribute in the five helper dicts is behind a lambda or inside a
function, so nothing is touched when `tools()` builds the list.

### Algorithms kept as one helper (the entry still has the checks, order and answer)

`by_face` (points sorted to the nearest face, numpy), `faces_mesh`, `reading` (the statistics every
inspection tool answers), `point_rows`, `sweep` (inverse kinematics along a trajectory), `step_picture` and
`contact_sheet` (drawing), `inertia`, `query` / `filter_shape` (the filter other families share), IFC's
`select` (the filters three tools share), `differences` and `real_classification`.

### Helpers that still refuse in their own words

Not in an entry, unchanged and compared in the cases: the finders several tools share — `ins_of` (3 texts,
4 tools), inspection's `find`, `find_note`, `body_pd` (2), `robot` (2), `trajectory` (1); the argument readers
`tol_of` (2), robot's `placement` (2), measure's `rng`; `query` / `filter_shape` (kind, of, normal, inside,
sort); `inertia` ("No solid…", not reachable through measure_mass, whose body always has a solid); picks'
`num`, `vec3`, `direction`, `find`, `shaped`, `solid_body`, `resolve`, `element`; `session.body`;
`facepick.pick`; `paths.in_file`; the add-on's own refusal passed on by `addon_mass`; IFC's `model` (no file
open, 5 tools) and `select` (an id, a class, a where key: 3 texts, 3 tools).

## Behaviour differences

None found: **0 of 463 cases differ.** Not identical in form, compared and equal:

- `picks.number(…, msg=)` (shape_query limit, section tolerance and maxPoints, robot_path speed) is `num`
  then a `refuse` step: the same two refusals in the same order.
- `picks.choice` in measure_keep is a `refuse` with the kinds written out; a kind that is a list still
  crashes the same way (a case).
- measure_keep's result property and robot_move's axes are read through `prop` (plain `getattr`), so a
  missing one fails as before.
- insp_export, insp_faces: the helpers read the distances and points again instead of being handed them;
  nothing changes between the two reads.
- Kept as they were, not fixed: `insp_run` leaves the hidden mesh of a body and a file's object in the
  document when a later check refuses (the call's transaction takes them back); `robot_new` with a
  kinematics that is not a text answers not_found with the value; `note_done { done: "yes" }` ticks;
  `ifc_edit` refuses a bad property key or storey after a new material was already added to the open file.
- ifc_diff's added, removed and changed lists come in a set's order, as before (`both` and the entry's
  `ib.keys() - ia.keys()` are the handler's own expressions).

## Proof here

`tests/test_datamisc_data.py` (the pattern of `test_datapart2_data.py`, `BASE = "2097f32"`), with
`_datamisc_before.py`, `_datamisc_cases.py`, `_datamisc_standin.py`. The stand-in wraps
`_datapart_standin.install()` in the child process only; **no existing stand-in is changed**.

- **Identity**, 31 tools: name, description bytes, schema with key order, changes, reads, group, against a
  snapshot of what the code made at `2097f32`; the snapshot is checked against that commit's source.
- **Old handler against new entry, 463 cases** (218 answer, 224 refuse, 21 crash alike), each in a fresh
  session: the answer or refusal, every logged operation, object added or removed and property set in order,
  the objects left, and (new in this test) every file the call wrote, by content. **0 differ.** 60 answers
  and refusals are also pinned to fixed text (`EXPECT`).
- **Every `refuse` step is reached**: 81 in the 31 entries, `UNREACHED` is empty.
- **Every helper present**: each name an entry calls is in its family's dict.
- No handler or `Tool(...)` of a converted name is left in the five files.

Per tool (cases / answer / refuse / crash): shape_query 18/10/8/0, measure 24/17/7/0, section 20/6/13/1,
measure_mass 24/13/10/1, clearance 14/7/6/1, measure_keep 30/10/19/1, insp_run 36/11/22/3, insp_update
23/8/15/0, insp_read 11/7/3/1, insp_list 3/3/0/0, insp_faces 13/5/6/2, insp_export 6/4/2/0, note_add
17/7/10/0, note_list 6/6/0/0, note_answer 8/4/3/1, note_done 5/3/2/0, note_delete 4/2/1/1, steps_list
9/5/4/0, steps_render 15/7/8/0, robot_new 16/10/6/0, robot_move 22/9/13/0, robot_path 20/6/13/1, robot_run
16/7/8/1, robot_trajectory 23/13/8/2, robot_export 11/5/6/0, ifc_open 5/2/3/0, ifc_find 14/9/4/1, ifc_edit
26/11/13/2, ifc_remove 7/2/4/1, ifc_save 5/4/1/0, ifc_diff 12/5/6/1.

What the stand-in is not: FreeCAD. Faces and edges say what a case tells them to be; distances are box
gaps; a cutting plane gives a square; Inspection's distances are a fixed ripple or a case's list; a robot is
three sliding axes with a reach; rendering, face picking, the body tessellation and the KRL exporter are
stubs that log; IfcOpenShell is a stand-in whose files are JSON (entities with ids, classes, sets,
materials, storeys) and whose API knows the eleven usages the tools call. numpy, `agentlink.store`, `meshdist.nearest`, `picks` and `paths` are the real ones. The
proof is of order, words and answer shape.

## Live models (calls numbered from 1)

`docs/hardening/models/coredoc-model.json` (114 calls):

| Tool | Calls |
|---|---|
| `shape_query` | 39, 40, 41 |
| `measure` | 42, 43, 44 |
| `measure_keep` | 45, 46, 47, 48 |
| `section` | 49, 50 |
| `clearance` | 51, 52 |
| `measure_mass` | 53, 57, 58, 62 |
| `insp_run` | 63 |
| `insp_read` | 64 |
| `insp_list` | 65 |
| `insp_faces` | 66 |
| `insp_update` | 67, 68, 69 |
| `insp_export` | 70 |
| `robot_new` | 82 |
| `robot_move` | 83, 84, 85 |
| `robot_path` | 86, 88, 92 |
| `robot_run` | 87, 89 |
| `robot_trajectory` | 90, 91 |
| `robot_export` | 94, 95 |

`docs/hardening/models/hubrest-model.json` (46 calls, in the window): `note_add` 23, `note_list` 24,
`note_answer` 25, `note_done` 26, `note_delete` 27, 28, `steps_list` 29, `steps_render` 30.

`docs/hardening/models/bimcam-bim-model.json` (69 calls): `ifc_open` 62, `ifc_find` 63, `ifc_edit` 64, 65,
`ifc_save` 66, `ifc_diff` 67, `ifc_remove` 68.

Also: `shape_query` in `asmtd-assembly-model.json` (51), `asmtd-techdraw-model.json` (2, 50) and
`part-model.json` (34, 80); `coredoc-gui-model.json` (a steps list, not calls) names note_add, note_list,
steps_list and steps_render.

**No converted tool is without a live call.** One call only: insp_run, insp_read, insp_list, insp_faces,
insp_export, robot_new, note_add, note_list, note_answer, note_done, steps_list, steps_render, ifc_open,
ifc_find, ifc_save, ifc_diff, ifc_remove.

## Unproven, and risks

1. **Nothing ran on FreeCAD.** `coredoc-model.json`, `hubrest-model.json` and calls 62–68 of
   `bimcam-bim-model.json` on FreeCAD 1.1.3 are the proof still owed.
2. **Values set on properties**: measure_keep's links are tuples `(object, [sub])`, robot_path's `Source` a
   tuple from `first(refs.items())`. The stand-in's trace prints a tuple and a list alike, so tuple-ness was
   checked by reading, not by the test.
3. **Dynamic property names** (`Axis1` … `Axis6`) are set through the runner's `{"set": [object, name,
   value]}` value form inside a `do`, as part_attach does.
4. **Late answers**: insp_update, robot_new and robot_path give `picks.finish` the fields as a callable
   (`"late": true`), read after its snapshot as the handlers' lambdas were.
5. `steps_render` answers `_png` (bytes) from an entry; the stand-in's renderer is a stub, so the picture
   itself is unproven here.
6. `tests/test_files.py` fails until FILES is regenerated (four new files under `tests/`).
7. The older tests that call these tools on real FreeCAD are among the skipped here.
8. **IFC**: the real IfcOpenShell was never loaded. `api(f, usage, product=…)` passes keywords from an
   expression to `ifcopenshell.api.run`; the TypeError fallbacks for an older API are `try` steps on
   `["TypeError"]`. Both have cases on the stand-in only.
9. The work was interrupted twice by the environment restarting; files on disk carried it, and every check
   above was run again on the final state.
