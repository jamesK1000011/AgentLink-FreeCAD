# Tools as data, round 3: the last five of TechDraw, cam_more.py, openscad.py (tag datatd2, 2026-11-16)

Checkout `wt3/d12`, base `2097f32`. Patch: `datatd2.patch` (`git add -A -N; git diff 2097f32`, FILES left out).
Nothing committed, nothing pushed, no network. **FreeCAD did not run here: everything below is proven on
stand-ins only. There is no live proof.**

## Where I stopped

At the end of the third file. All three assigned files are done; none is half-way.

## Counts

- Converted: **16 tools, all `steps`** — techdraw.py 5 (td_list, td_export, td_cosmetic, td_view_more, td_lines),
  cam_more.py 6 (cam_path, cam_property_bag, cam_template_export, draft_fix, asm_rigid_group, asm_new_part),
  openscad.py 5 (scad_status, scad_import, scad_code, scad_export, scad_op).
- Kept as code: **0**. Thin entries: **0** (see "helpers" for the nearest to thin).
- `agentlink/data/tools.json`: 209 → 225 entries, appended at the end in that order; the first 209 are
  byte-identical (the file is the base's text plus the new tail). No `family` key: none of the three groups
  (`techdraw`, `cam_more`, `openscad`) is shared with another converted file.
- techdraw.py 2291 → 1987 lines, cam_more.py 304 → 146, openscad.py 443 → 361. No `Tool(...)` left in any of them.
- **No change to `runners.py`, `expr.py`, `tooldata.py`.**
- Full suite: **908 passed, 338 skipped** (193 s). After `git add -N`, `tests/test_files.py` fails for FILES
  only, as the brief expects. `scripts/tool_index.py --check` and `tool_summary.py --check`: current.
  Every changed and new .py compiles under python3.11. No absolute home paths or personal names in repo files.

## One existing test file was modified (needed)

`tests/_datatd_cases.py`: `KEPT` is now `{}`. `tests/test_datatd_data.py` asserts that the `Tool(...)` calls
left in techdraw.py are exactly `KEPT`, so it could not stay as it was once the five were converted. Nothing
else in the first TechDraw proof changed, and no existing stand-in was modified.

## Proof (`tests/test_datatd2_data.py`, BASE = "2097f32")

With `_datatd2_before.py`, `_datatd2_cases.py`, and one stand-in per family file, each built on an existing
one inside its own child process: `_datatd2_standin.py` (on `_datatd_standin`), `_datatd2_cam_standin.py`
(on `_datacam_standin`), `_datatd2_scad_standin.py` (on `_datapart2_standin`). The test runs one child per file.

- Identity of all 16 (name, description bytes, schema with key order, changes, reads, group) against the
  snapshot, and the snapshot against git `2097f32`.
- **254 cases, old handler against new entry: 0 differences** (result or refusal, every traced call in order,
  objects left). techdraw 117 (67 answer, 47 refuse, 3 crash alike), cam_more 79 (33 / 44 / 2),
  openscad 58 (24 / 33 / 1). The 6 crash cases are deliberate (`crash:` in their name): bad input the handler
  never checked, compared as the same crash.
- **Every `refuse` step in the 16 entries is reached. `UNREACHED` is empty.**
- Every name an entry calls is in its family's helpers dict.

## Helpers: what stayed code

techdraw.py (new, each with a docstring): `mark_not_ready`, `turn_to_align`, `stretched`, `erase_tag`,
`circle_points`, `mid_line`, `thread_arc`, `side_outline`, `root_lines`, `stack_of`, `read_text`, `drawn`,
`write_out`, `colour`, and the constant `LINE_STYLES`. `warm` and `page_sheet` were already there.
The thread standard's arithmetic (pitch, 0.6134 P, nominal size) is in the td_cosmetic entry, not a helper.

cam_more.py: `has_cam`, `from_module`, `proxied`, `gcode`, `setprop`, `write_template`, `has_rigid_groups`,
`rigid_group`, `draft_ready`, `heal`, `assembly`, `joints`, `part_of`, `job_of`, `BAG_KINDS`.
`set_props` and `ops_of` are gone: their checks and words are now steps (written out in each cam_path kind
that used them, so the same refusal text appears twice in that entry).

openscad.py: `version_of`, `has_ply`, `has_shape`, `said`, `read_text`, `drop_file`, `make_folder`,
`scad_utils`, `run_code`, `via_openscad`, `export_csg`; `exe`, `csg_needs`, `hull_here`, `console_mode`,
`read_in`, `tidy_view`, `made_since` unchanged. `need_exe` and `where` are gone (their words are in the entries).
`exe` is called through the module at call time, so `tests/test_core_readers.py`'s `S.exe = …` still takes.

Helpers that still refuse in their own words (finders and readers shared with other tools, as before):
techdraw `page_of`, `view_of`, `obj_of`, `resolve_ref`, `paper_of3d`, `place_xy`, `pt2`; `picks.find`,
`picks.shaped`, `picks.resolve`, `picks.placement`; cam's `_job`; assembly's `_assembly`, `_part`;
the session's `body`. **One more worth knowing: `hull_here` still raises "objects: {hull3d's reason}." itself**
— no case reaches it (the one I wrote crashed inside qhull with a run id in the message, so I dropped it).

## Behaviour differences

None found by the cases. Differences I know of by reading, none reachable in normal use:

- scad_op, minkowski without OpenSCAD: if the program appeared between the tool's two looks for it, the
  handler crashed with UnboundLocalError; the entry would crash with NameError.
- scad_code: the top object is found with `first(...)` where the handler used `next(...)`; they differ only
  if the object just listed is gone.
- Tool order inside a group follows tools.json (techdraw: the 27, then the five in the order above; before,
  the five came in the order td_list, td_cosmetic, td_view_more, td_lines, td_export).
- td_lines' style refusal is now the literal text; the handler built the same text from its table.

## Live models (calls from 0); nothing here was run

- `asmtd-techdraw-model.json`: td_list 2, 3, 18, 64 · td_export 19, 65 · td_cosmetic 52 · td_lines 53, 54 ·
  td_view_more 61, 62, 63.
- `bimcam-cam-model.json`: cam_path 28, 29 · cam_property_bag 30 · cam_template_export 31.
- `draftmesh-draft-model.json`: draft_fix 23, 79.
- `asmtd-assembly-model.json`: asm_rigid_group 65 · asm_new_part 66.
- `coredoc-model.json`: scad_status 70 · scad_export 71 · scad_import 72, 73 · scad_op 74, 75 · scad_code 76.
- **Converted tools with no live call: none.** (Not every branch is called: I did not map kinds.)

## Risks

- **Not run on FreeCAD.** The stand-ins prove order and words. TechDraw's cosmetic edges, CAM's proxy classes,
  Draft.heal, Assembly's joint group and the CSG reader are imitations. Run the five models on the Mac.
- td_export's drawing code (`page_sheet`) runs for real in the test, but on stand-in views most items are
  skipped with a note, so the drawn output is thinly exercised; the DXF branch and file writing are covered.
- td_list's `computed` time reads "0 s" in both runs; a slow machine could make the two runs differ by 0.01 s
  and fail the comparison spuriously.
- cam_more's stand-in imports the real `agentlink.families.assembly` on a fake `JointObject`.
- Long entries to read for whether they still read as the tool: td_cosmetic, td_view_more, td_lines, cam_path.

## On merge (not in the patch)

- `FILES` must gain: `tests/_datatd2_before.py`, `_datatd2_cases.py`, `_datatd2_standin.py`,
  `_datatd2_cam_standin.py`, `_datatd2_scad_standin.py`, `test_datatd2_data.py`.
- `tools.json`: 16 entries appended after `points_structure`; merge by key.
- `docs/data-tools.md`: the TechDraw and CAM sentences near the top were rewritten.
