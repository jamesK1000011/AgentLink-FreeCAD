# The hub's own core tools as data (tag: datacore, 2026-11-16)

Checkout `wt3/d15`, base `effbcc7`. Patch: `datacore.patch` (`git add -A -N`, `git diff effbcc7`; FILES not
touched; `git apply --check` on a clean `effbcc7` passes). Nothing committed or pushed, no network.
**Nothing ran on FreeCAD**: every proof here is plain Python on a stand-in.

## Where it stopped

At a file boundary, files consistent. Four of the five files are done; **`families/app.py` (17 tools) was
not started** and is untouched: all 17 of its tools remain code, `cmd_run`'s `Sketcher_LeaveSketch` case
included.

| File | Tools | Data | Kept as code |
|---|---|---|---|
| `families/view.py` | 3 | `view_maps`, `view_snapshot` | `view_render` |
| `families/dev.py` | 4 | `addon_test`, `gui_unstick` | `gui_input`, `live_run` |
| `families/unattended.py` | 5 | `dialog_answer`, `crash_collect`, `doc_switch`, `queue_go` | `addon` |
| `families/doc.py` | 13 | all 13 | none |
| `families/app.py` | 17 | not started | all 17, for now |

## Counts

- **Converted: 21. Kept as code: 4 (reasons below). Thin entries: 2** (`gui_unstick`, `crash_collect`: each
  is one call and the answer; they were one-line handlers).
- `agentlink/data/tools.json`: 264 → 285 entries, appended at the end in the old listing order, all `steps`;
  the file's diff is 424 added lines and 0 removed. No `family` key was needed: each of the four files is
  the only one of its group.
- **No change to `runners.py`, `expr.py`, `tooldata.py` or the schema.**
- Suite (`timeout 290 python3 -m pytest -q tests`): **977 passed, 347 skipped, 0 failed** in 214 s, run
  before the new test files were intent-added. With them added (`git add -A -N`, as the patch is made),
  `tests/test_files.py` fails on the stale FILES, as expected (re-run alone: 1 failed, 1 passed); FILES left
  alone. So after the patch: 976 passed, 1 failed (that one).
- `scripts/tool_index.py --check` and `scripts/tool_summary.py --check`: both exit 0.
- `python3.11 -m py_compile` passes on the four family files and the four new test files.
- `docs/data-tools.md`: one paragraph added.
- Family files: view 763 → 703 lines, dev 293 → 279, unattended 420 → 384, doc 1366 → 1084.

## Kept as code, and why

| Tool | Reason |
|---|---|
| `view_render` | The picture itself: numpy over every layer's triangles, a render sized and timed against past renders, marked heavy for the watchdog and unmarked in a `finally`, an image answered. `docs/data-tools.md` already names it as code. |
| `gui_input` | One algorithm over Qt widgets (`gui_input.Run`): events sent step by step inside the window's event loop, the link's deadline set and lifted around it, the person's input stood in for inside a context manager with a `finally`. As data it would be one helper holding the whole handler. |
| `live_run` | A replay that calls the server's own tools from closures, with a guard ticking inside nested Qt event loops and state put back in a `finally`. Same: one helper would hold it all. |
| `addon` | An installer: the add-on is moved aside and put back when the install or the smoke test fails. Its refusal for a missing confirm has the code `not_allowed`, which a `refuse` step does not take (`runners.CODES`), so converting it needs a runner change; I did not make one. |

## Per tool

Every entry holds the description and schema (from the snapshot of the code at `effbcc7`), every check with
its refusal word for word as a `refuse` step, the order of steps and the answer's fields.

| Tool | As data | Helpers it calls |
|---|---|---|
| `view_maps` | answer only | `maps`, `layers`, `views` |
| `view_snapshot` | the old inner `snap_views` is steps (3 refusals); one view or a grid as `when`; the grid's answer built by `put` | `alias`, `gui_up`, `active_view`, `turn`, `snap_fit`, `snap_empty`, `nothing_shown`, `snap_size`, `shots`, `snap_combine`, `fit_png`, `png_size`, `out_file`, `filesize`, `read_bytes` |
| `gui_unstick` | thin: `answer.via` | `unstick` |
| `addon_test` | job / listing as early answers; the four checks | `job_wait`, `listing`, `test_timeouts`, `fits`, `mod_dir`, `installed_names`, `test_root`, `find_cmd`, `started` |
| `queue_go` | | `queue_state`, `lifted`, `preset` |
| `crash_collect` | thin | `crash_kept` |
| `dialog_answer` | task panel or dialog as `when`; `fill`'s ValueError turned into the refusal by a `try` | `modal`, `task_panel`, `press`, `press_task`, `fill`, `back_out`, `log_watchdog`, `crash_kept` |
| `doc_switch` | | `current`, `docs`, `open_row`, `doc_by`, `doc_names`, `moved_to`, `gui_up`, `bring_front`, `bodies` |
| `doc_new` | | `new_doc`, `current`, `switch` |
| `doc_close` | the loop over names with its two refusals; the unsaved check; `open_labels` called as it was | `ref_list`, `listed_docs`, `doc_hits`, `own_doc`, `doc_names`, `unsaved`, `touched_marks`, `current_name`, `close_doc`, `back_to`, `switch`, `open_labels` |
| `doc_open` | recent as an early answer; open as a `try` | `recent_files`, `where`, `isfile`, `basename`, `open_at`, `open_doc`, `is_changed`, `unchanged`, `switch`, `bodies`, `errors` |
| `doc_save` | the three ways as `when` / `else` | `where`, `abspath`, `exists`, `makedirs`, `dirname`, `free_name`, `saved`, `filesize`, `modified_state` |
| `object_list` | the row built by `put` in an `each` | `once`, `is_shape`, `shape_row` |
| `object_get` | the filter as one expression | `find`, `SKIP_PROPS`, `prop_entry` |
| `object_set` | both loops, the scoped recompute, own / others' errors | `find`, `near`, `readonly`, `json_safe`, `read`, `errors`, `set_value`, `recompute_scoped`, `built_from`, `snapshot`, `steps` |
| `object_delete` | `answer.late` through `finish`, as the handler's lambda | `ref_list`, `find`, `along`, `removed`, `shown_again`, `finish`, `errors` |
| `object_rename` | | `find`, `meta_moved`, `snapshot` |
| `object_group` | list and link as early answers; add / remove / dissolve by `choose` | `group_row`, `is_group`, `find`, `vec3`, `unique`, `placement`, `rotation`, `ref_list`, `snapshot`, `doc` |
| `recompute` | force with its TypeError fallback as a `try` | `errors`, `snapshot` |
| `import_file` | `choose` by kind of file (12 refusals) | `where`, `isfile`, `fmt_of`, `stem`, `core_scene`, `read_shape`, `mesh_module`, `mesh_read`, `mesh_solid`, `import_dxf`, `svg_insert`, `jt_reader`, `image_plane`, `unique`, `recompute_scoped`, `is_holder`, `import_row`, `summarised` |
| `export` | format choice and its two refusals; meshes as an early answer; `picks.number(…, msg=)` became `num` + a `refuse` step | `ref_list`, `export_pick`, `body`, `fmt_of`, `is_mesh`, `out_path`, `compound`, `mesh_modules`, `num`, `solid_written`, `flat_write`, `scene_written`, `mesh_written`, `scene_of_meshes`, `merged_meshes`, `filesize` |

Kept exactly as asked: `open_labels` in `doc.py` is not touched and is called by `doc_close`'s entry.
`_bring_front`, `_modified`, `_snap_empty`, `_snap_shown`, `snap_fit`, `snap_combine`, `fit_png`, `to_value`,
`to_placement`, `flat_write`, `import_dxf`, `core_scene`, `image_plane`, `switch`, `where` are unchanged code.

`shots` (view) holds a loop on purpose: it must put the person's camera back in a `finally`.

### Helpers that still refuse in their own words

Unchanged and compared in the cases, but in code: `where` ("path: a file path …", shared by five tools);
picks' `find`, `shaped`, `num`, `vec3`, `ref_list` (object_delete's message is passed from the entry);
`to_value` / `to_placement` (object_set's per-type refusals); `flat_write` and `view_matrix` (export's
section and view); `colour`; `image_plane`; `import_dxf`; `session.body`; `testrun.find` / `root_for`.

## Behaviour differences

None found: 0 of 271 cases differ. Not identical in form:

- **Listing order.** Each mixed file now returns its code tools first, then its data tools
  (`[…] + runners.tools(…)`). `tool_index` and `tool_summary` are current; anything that reads the raw
  order of `tools/list` sees these tools in a new order.
- **`addon_test`'s description** was built from `testrun.TIMEOUT`, `TIMEOUT_MAX`, `START_WAIT` and
  `STATUS_WAIT`; as data it is fixed text. A new test fails if a limit changes without the entry.
  `gui_input`'s description (kept as code) is still built.
- `object_group` add: the groups an object leaves are listed before any is left (the handler walked
  `InList` while removing). The same in FreeCAD, where `InList` is a new list each time.
- `import_file` and `export` load FreeCAD's Mesh / MeshPart as a step of their own (`mesh_module`,
  `mesh_modules`) to keep the handler's order: import, then checks.

## Proof here

`tests/test_datacore_data.py` (the pattern of `test_datapart2_data.py`, `BASE = "effbcc7"`), with
`_datacore_before.py`, `_datacore_cases.py`, `_datacore_standin.py`. The stand-in wraps
`_datapart2_standin.install()` in the child process only; no existing stand-in is changed.

- **Identity**, 21 tools: name, description bytes, schema with key order, changes, reads, group, against a
  snapshot of the code at `effbcc7`; the snapshot is checked against that commit's source.
- **Old handler against new entry, 271 cases** (145 answer, 124 refuse, 2 crash alike), each in a fresh
  session: the answer or refusal, every traced call, object added or removed and property set in order, the
  objects left, the session's document and the open documents. **0 differ.** 51 are pinned to fixed text.
- **Every `refuse` step is reached**: 62 in the 21 entries, `UNREACHED` is empty. Weak spot:
  `dialog_answer`'s `"=str(error)"` has no fixed words to match, so it is held by its pinned case instead.
- **Every helper present** (`--helpers` answers `{}`). No handler or `Tool(...)` of a converted name is left.

What the stand-in is not: FreeCAD, Qt or the link. `gui_link`, `keep`, `testrun`, `crash_logs` and `store`
are stubs that write down what they were asked; `snap_combine` and `_snap_empty` are replaced in some
cases (no PySide here), so `fit_png` and `snap_combine` always fail in the others; the 3D view saves a PNG
header. `meshformats`, `flat2d`, `emptywhy`, `paths` and `picks` are real.

## Live models

| Tool | `coredoc-model.json` (calls, from 1) | `coredoc-gui-model.json` (steps, from 0) | `hubrest-model.json` (calls, from 1) |
|---|---|---|---|
| `doc_new` | 1, 101 | | |
| `object_list` | 4, 5 | | |
| `object_get` | 6, 7, 20 | 4 | |
| `object_set` | 8, 9, 10, 11 | 8 | |
| `object_rename` | 15, 16 | | |
| `object_group` | 17, 18, 19, 21 | | |
| `recompute` | 36, 38 | 8 | |
| `doc_save` | 96, 103 | | |
| `export` | 97 | | |
| `import_file` | 98, 99, 100 | | |
| `doc_close` | 105, 112, 113 | | |
| `object_delete` | 108, 109 | | |
| `doc_open` | 111, 114 | | |
| `doc_switch` | | 0 | 3 |
| `gui_unstick` | | 7 | 18 |
| `addon_test` | | 13 | 40 |
| `view_maps` | | | 20 |
| `view_snapshot` | | | 22 |
| `crash_collect` | | | 41 |
| `dialog_answer` | | | 42 |

**No live call: `queue_go`.** Thin live (one call): `export`, `view_maps`, `view_snapshot`, `crash_collect`,
`dialog_answer`.

## Unproven, and risks

1. **Nothing ran on FreeCAD.** The three models above on FreeCAD 1.1.3 are the proof still owed, the window
   ones most of all: `view_snapshot`, `dialog_answer`, `doc_switch { front }` and `gui_unstick`.
2. **`gui_unstick` is answered on the link's socket thread** (`hooks.register_thread_tool`, still called in
   `dev.tools`). Its function is now the runner's closure over `unstick`; nothing else changed, but that
   path is exercised only live (hubrest call 18, coredoc-gui step 7).
3. `view_snapshot`'s one-picture grid (`snap_combine`) and resizing (`fit_png`) need Qt: here only their
   failing branch and a replaced `snap_combine` ran.
4. The values `export` and `import_file` hand to Part, Mesh, MeshPart and TechDraw are as in the code; the
   stand-in checks their order, not their geometry.
5. Extensions that read `doc.tools`-local names cannot have: nothing outside imported them. The module-level
   names other files import (`colour`, `errors`, `saved`, `modified_state`, `doc_names`, `went_from`,
   `installed_names`, `mod_dir`) are unchanged.
