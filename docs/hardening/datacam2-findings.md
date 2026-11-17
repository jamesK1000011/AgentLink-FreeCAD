# Tools as data: CAM (cam.py, 12 of 12) and points_structure (tag datacam, 2026-11-16)

Checkout `wt3/d7`, base `b408a91`. Patch: `<work>/datacam.patch` (`git add -A -N`,
`git diff b408a91`, FILES left out; `git apply --check` on a clean `b408a91` passes). Nothing
committed or pushed. **FreeCAD did not run here**: everything below is proven on a stand-in.

## Where I stopped

- **Done, whole file:** `agentlink/families/cam.py` — all 12 handlers are `steps` entries.
- **Done:** `points_structure` (`std_more.py`).
- **Not started: the five TechDraw handlers** (`td_list`, `td_export`, `td_cosmetic`, `td_view_more`,
  `td_lines`). `techdraw.py` is untouched; they are still registered with `Tool(...)` as before. I
  stopped at this boundary for room, not because they cannot be data.
- `cam_more.py` untouched, as told (it still imports `_job` from `cam.py`; that name is kept).

## Counts

- Converted: **13** (cam 12, std_more 1), all `steps`. Kept as code: **0** of those asked in cam.py.
- `agentlink/data/tools.json`: 167 → 180 entries, appended at the end in the old code order
  (cam_job, cam_op, cam_list, cam_tool, cam_tool_add, cam_library, cam_dressup, cam_setup, cam_edit,
  cam_remove, cam_sim, cam_post, points_structure). The existing text is the same byte for byte but
  for the one comma after `draft_array`'s closing brace. Layout as the file's: a step on one line
  where it fits 200 columns, else opened one level.
- `cam.py`: 1060 → 593 lines; no `Tool(...)`, no handler; 37 named helpers, each with a docstring,
  plus the tables (`OPS`, `POSTS`, `SHAPES`, `BIT_PROPS`, `DRESSUPS`, `HINTS`, `CUTS`) handed to the
  entries by name.
- `std_more.py`: the `points_structure` handler and its `Tool(...)` line removed. **It needed no new
  helper** (`find`, `unique`, `done`, `doc` were already in the dict), so there is no separate dict
  and no `helpers.update(...)` added.
- **No change to `runners.py`, `expr.py`, `tooldata.py`.**
- Suite (`timeout 280 python3 -m pytest -q tests`): **886 passed, 338 skipped, 1 failed:
  `tests/test_files.py`** (FILES does not list the four new test files; expected, FILES left alone).
  Before `git add -N` the same run was 887 passed, 0 failed. `scripts/tool_index.py --check` and
  `scripts/tool_summary.py --check`: current. Every changed or new file compiles with `python3.11`.
- `docs/data-tools.md`: one sentence added after the TechDraw one.

## Per tool

| Tool | In the entry | Named helpers it calls |
|---|---|---|
| cam_job | tool and stock checks with their words, the job, the preferences-stock replacement (a `try` whose error becomes the note), margins, first tool, answer | `body`, `num`, `path_module`, `tc_of`, `set_tool`, `merged`, `stock_out`, `tool_out` |
| cam_op | every check, the tool by name, base / faces / props loops with their refusals, per-kind settings, holes, depths, recompute, the two "made no …" refusals, answer and warning; the whole run in a `try` (`on: failure`) whose `except` removes what was made and refuses "would not compute" | `job_of`, `num`, `path_module`, `with_tool`, `make_op`, `face_names`, `find`, `ref_list`, `setprop`, `enum_of`, `qty`, `commands`, `path_stats`, `where` |
| cam_list | rows and total | `commands`, `op_type`, `path_stats`, `tc_for`, `stock_out`, `tool_out` |
| cam_tool | order and answer | `tc_of`, `set_tool`, `tool_out` |
| cam_tool_add | checks, the two ways of making a bit with their refusals, the sizes loop and `skipped`, controller, labels, answer | `bit_factory`, `shape_file`, `toolbit`, `setprop`, `unique`, `set_tool`, `merged`, `tool_out` |
| cam_library | `choose` by action; import's checks, the loop over records, answer | `out_path`, `in_out`, `isabs`, `bit_of`, `write_tools`, `read_tools`, `one_tool` |
| cam_dressup | the stack lookup, kind, import refusal, make (errors to a refusal), listing, tags / boundary / dogbone settings, props loop, the two refusals that take the dressup back (`first`), answer | `stack_of`, `path_module`, `dress`, `undress`, `setprop`, `commands`, `path_stats`, `tc_for` |
| cam_setup | all of it | `base_op`, `num` |
| cam_edit | one op lookup, `choose` by action, the custom operation's steps, order, answer | `custom_module`, `custom_create`, `with_tool`, `place`, `tc_for`, `unique`, `setprop`, `vector`, `snapshot` |
| cam_remove | lookup, removal loop with a boundary's own stock, answer | `stack_of` |
| cam_sim | checks, default resolution, the findings' words, verdict, note, the file | `sim_tool`, `sim_run`, `sim_picture`, `out_path`, `in_out`, `write_bytes` |
| cam_post | checks, job post then script with their four refusals, the file, tools, warnings, answer | `post_path`, `in_out`, `post_factory`, `by_job`, `post_script`, `postables`, `tc_for`, `path_stats`, `qty`, `write_text`, `stock_out` |
| points_structure | all of it | `find`, `unique`, `done` |

**Thin entries:** none in the strict sense. **Closest: `cam_sim`** — the height-map run
(`sim_run`) and the picture (`sim_picture`) are one algorithm each over numpy; the entry keeps the
checks, the default resolution, each finding's words, the verdict and the answer. `cam_list` and
`cam_tool` are short because the tools are.

**Helpers that still refuse in their own words** (shared readers and finders, as `mesh_of` /
`apply_tol` are): `job_of` (picks.one_of: no job / say which / not there), `set_tool` (the five
tool inputs; shared by cam_job, cam_tool, cam_tool_add and through it cam_library), `body`
(the session's), `find` and `num` (picks), `doc` ("No document"). The refusals that were inside
`make_bit`, `by_script`, `faces_of`, `op_of`, `custom` and `undo` are now `refuse` steps in the
entries; those functions became `bit_factory` / `shape_file` / `toolbit`, `post_script` /
`postables`, `face_names`, an expression, `custom_module` / `custom_create`, `undress`.

**State put back in code on purpose** (no `finally` in steps): `with_tool` (FreeCAD's
`findToolController` answers the chosen controller for one call), `by_job` (the job's post
arguments and touched state).

`cam_library` import calls `cam_tool_add`: helper `one_tool` runs that entry (`runners.run_steps`),
as `td_dimset` does with `td_dim`.

## Proof here

`tests/test_datacam_data.py` (pattern of `test_datatd_data.py`, `BASE = "b408a91"`) with
`tests/_datacam_standin.py`, `_datacam_cases.py`, `_datacam_before.py`:

- identity of all 13 (name, description bytes, schema with key order, changes, reads, group)
  against the snapshot, and the snapshot against git `b408a91`;
- no handler or `Tool(...)` left in `cam.py`; `points_structure` not in `std_more.py`'s code; every
  name an entry calls is among its family's helpers;
- **236 cases**, old handler (from git) against new entry: result or refusal (code and words),
  every traced call in order, objects left. **0 differ.** 110 answer, 125 refuse, 1 crash compared
  as a crash (`cam_tool` on a job with no tool controller: the same AttributeError both sides).
  Per tool: cam_op 51, cam_dressup 29, cam_edit 25, cam_post 25, cam_job 20, cam_tool_add 16,
  cam_setup 15, cam_library 13, cam_sim 12, cam_list 8, points_structure 8, cam_tool 7, cam_remove 7.
- **every `refuse` step in the 13 entries is reached** by a case. Unreachable: none (`UNREACHED = []`).
  Not reached, and not an entry's: `doc`'s "No document: doc_new first." (the harness reads the
  document after each call).

The stand-in (`_datacam_standin.py`, on `_datamesh_standin.py`'s FreeCAD, which is not changed):
jobs with stock, model, setup sheet and tool controllers; ten operation modules (Profile,
PocketShape, Adaptive, MillFace, Drilling, Engrave, Helix, Probe, Custom, Slot; the other nine kinds
are absent, which is the "not in this FreeCAD's CAM" path); Tags, DogboneII, Boundary, RampEntry
dressups (Array has no maker, LeadInOut is absent); tool bits both ways (1.0 factory, later
`ToolBit`); the job post-processor factory and two scripts. `millsim`, `render`, `picks`, `paths`
are the real ones. An operation's path is a fixed handful of moves bent by flags. It proves order
and words, not CAM.

## The live model (`docs/hardening/models/bimcam-cam-model.json`, calls from 0)

Every converted CAM tool is called:

cam_job 6, 7 · cam_op 8, 9, 10, 11, 19 · cam_list 12, 33 · cam_sim 13 · cam_post 14, 15, 16, 24 ·
cam_tool_add 17, 18 · cam_dressup 20 · cam_setup 21 · cam_edit 22, 23, 25 · cam_library 26 ·
cam_tool 27 · cam_remove 32.

Still code (`cam_more.py`): cam_path 28, 29 · cam_property_bag 30 · cam_template_export 31.

`points_structure`: `bimcam-points-model.json` calls 28, 29.

Converted tools no model call exercises: none. Branches the model does not reach (mapped by tool,
not by branch): cam_library import, cam_edit copy / comment / start, dressups other than tags, the
script post, FreeCAD 1.0's bit factory and hole operations, most refusals.

## Behaviour differences

None in the 236 cases. By reading:

- `cam_op` "would not compute: … (file:line)": for an error raised inside FreeCAD the file and line
  are the same; for one raised in Agent Link's own code they now name the runner or a helper, where
  they named a line of the handler.
- `cam_sim` imported numpy, millsim and render at the top of the handler; now where they are used.
  A FreeCAD without numpy failed before the job lookup and now after the checks.
- `cam_job` and `cam_tool_add` reach `Path.Main.Job.Create` and `Path.Tool.Controller.Create` by
  dotted name (`make`). `cam.py` still imports both modules at load, so a FreeCAD without them has
  no cam family, as before.
- `cam_edit` looks the op up once before the branch; same order of refusals.
- A `try` with `on: error` round `setprop`, `dress`, `toolbit` would also catch a refusal, as the
  handlers' `except Exception` did; none of those raises one.

## Found, not changed

- **`cam_sim` with a relative `path` writes into FreeCAD's working directory, not the output
  folder** (`paths.made` on the path as given; `cam_post` and `cam_library` do put a relative path
  in the output folder). Kept as it was; a case first wrote `sim.png` into the checkout, which is
  how I saw it (removed, the case now uses an absolute path).
- `cam_op`'s refusals that end "Nothing was kept." after the operation is made (no holes, no
  cutting moves, no G-code, count below 1 in `cam_dressup`) remove nothing themselves; only the
  "would not compute" path does. Unchanged; whether the hub's undo covers them was not checked.

## Risks

- **Not run on FreeCAD.** Run `bimcam-cam-model.json` on the Mac before trusting it.
- `cam_op` is one long entry with the whole body inside a `try`; read it for whether it still reads
  as the tool. `cam_dressup` and `cam_post` are the next longest.
- The old-vs-new tests need git commit `b408a91` and numpy; without either 4 of the 7 skip.
- `tests/test_datacam_data.py` has one small change from the TechDraw pattern: `WHOLE` in the cases
  file names the family files with nothing left in code (`cam`); for `std_more` only the converted
  name is checked.

## To do on merge (not in the patch)

- `FILES` must gain `tests/_datacam_before.py`, `tests/_datacam_cases.py`,
  `tests/_datacam_standin.py`, `tests/test_datacam_data.py`.
- `tools.json`: 13 entries appended after `draft_array`; merge by key.
- `tests/_datatd_cases.py` still says the five TechDraw tools wait on "datacam-findings": still true.

## Next

1. The five left in `techdraw.py`: td_export and td_list first, then td_lines, td_view_more,
   td_cosmetic.
2. `cam_more.py` (cam_path, cam_property_bag, cam_template_export, and its three non-CAM tools);
   this stand-in already has jobs, operations and controllers for the first three.
