# The Assembly tools as data (tag: dataasm, 2026-11-16)

Checkout `wt3/d9`, base `2097f32`. Patch: `dataasm.patch` (`git add -A -N`, `git diff 2097f32`, FILES not
touched; `git apply --check` on a clean `2097f32` passes). Nothing committed or pushed, no network.
**Nothing ran on FreeCAD**: every proof here is plain Python on a stand-in that has no solver.

## Where it stopped

Both files are finished, each whole. Nothing remains of the task.

| File | State |
|---|---|
| `families/assembly.py` (8 `asm_*`) | all 8 are data; 844 → 617 lines, no `Tool(...)` and no handler left |
| `families/assembly_more.py` (8 `asm_*`) | all 8 are data; 763 → 602 lines, no `Tool(...)` and no handler left |

## Counts

- **Converted: 16. Kept as code: 0.** Thin entries: none whole, but four tools lean on one algorithm helper
  each (below).
- `agentlink/data/tools.json`: 209 → 225 entries, appended at the end in the old listing order, all
  `steps`; 797 lines added, 0 removed (the 209 before are byte for byte as they were). Layout: the file's
  simpler one (a step a line, the answer on one line), as the mesh and points entries have it.
- `assembly.py` ends `runners.tools(GROUP, s, helpers)` (no family); `assembly_more.py`'s entries say
  `"family": "assembly_more"` and it ends `runners.tools(GROUP, s, helpers, family="assembly_more")`.
- **No change to `runners.py`, `expr.py`, `tooldata.py` or the schema.** No other family file touched
  (`cam_more.py` still imports `_assembly`, `_joints`, `_part` from `assembly.py`: all kept).
- Suite (`timeout 290 python3 -m pytest -q tests`): **908 passed, 338 skipped, 0 failed** in 195 s, run
  before `git add -N`. With the new files known to git, `tests/test_files.py` fails (FILES stale: four new
  test files), as expected; FILES left alone. The 7 tests of `tests/test_dataasm_data.py` pass.
- `python3 scripts/tool_index.py --check` and `scripts/tool_summary.py --check`: both exit 0.
- `python3.11 -m py_compile` passes on the two family files and the four new test files.
- `docs/data-tools.md`: one paragraph added.

## Per tool

Every entry holds the description and schema (from the snapshot of the code at `2097f32`), its checks with
their refusals word for word as `refuse` steps, the order of steps and the answer's fields in their order.

### `assembly.py` (group `assembly`, no family)

| Tool | As data | Helpers it calls |
|---|---|---|
| `asm_new` | the "already in an assembly" check is an `each` inside an `each`; the grounding is steps | `body`, `typed`, `joints`, `part_of`, `grounded_joint`, `view_provider`, `grounded` |
| `asm_add` | the skip of parts already in is a `when` | `assembly`, `body`, `parts` |
| `asm_ground` | hold and let go as two `when` steps | `assembly`, `part_of`, `joints`, `grounded_joint`, `view_provider`, `grounded` |
| `asm_joint` | 12 refusals; the two ends as an `each`; the couplings' figures with one refusal a kind (was a dict of messages); connect, frames and clearUndo as three `try` steps; reverse and the automatic turn-over (kept only when it overlaps less, else put back) as steps; the two "unsolved" hints as two refusals; `moved` one expression | `typed`, `assembly`, `grounded`, `part_of`, `element`, `parts`, `joints`, `joint_proxy`, `view_provider`, `num`, `radius_of`, `placement`, `rotation`, `V`, `joint_refs`, `status`, `turn_over`, `overlaps`, `vec`, `placement_of`; tables `OFFERED`, `KINDS`, `REVERSIBLE` |
| `asm_list` | a row a joint as a `push` | `assembly`, `joints`, `ref_label`, `status`, `parts`, `placement_of`, `grounded` |
| `asm_joint_remove` | | `assembly`, `joints`, `status` |
| `asm_sweep` | the checks, the limits as defaults, which side moves, the answer and its note are the entry; the sweep itself is `sweep_run` | `assembly`, `joints`, `ref_pair`, `grounded`, `joint_axis`, `unit`, `carried`, `driven_parts`, `sweep_run` |
| `asm_check` | the answer's eleven fields, seven of them conditional | `assembly`, `num`, `status`, `check_parts`, `overlaps`, `grounded` |

### `assembly_more.py` (`"family": "assembly_more"`)

| Tool | As data | Helpers it calls |
|---|---|---|
| `asm_fits` | pairs or joints as `when` / `else`; a joint with nothing round skipped by a `try` on refusal, a named one not; the verdict | `assembly`, `part_of`, `element`, `joint_of`, `joints`, `ref_pair`, `pair_fit` |
| `asm_motion` | list, delete, save as early `answer`s; play's frames, start and verdict; the file written in `answer.then` | `motions`, `keep_motions`, `snapshot`, `assembly`, `joint_of`, `key_frames`, `standing`, `play`, `noted`, `in_session`, `expanduser`, `write_json` |
| `asm_export` | | `assembly`, `noted`, `expanduser`, `in_session`, `isfile`, `filesize` |
| `asm_pose` | 9 refusals in order; the counted fallback; target, wrap and limits; the solver-moved-it-back and overlap checks | `assembly`, `is_exploded`, `joint_of`, `joint_value`, `prop`, `wrap180`, `limits_of`, `moving_group`, `pose_move`, `status`, `overlaps`, `parts`, `snapshot`, `r4`, `vec`, `placement_of`, `step`; table `POSE` |
| `asm_limits` | each end set by name through the runner's `{"set": [object, name, value]}` in a `do` | `assembly`, `joint_of`, `prop`, `status`, `settled`, `limits_of` |
| `asm_explode` | collapse as an early `answer`; axis or middle as `when` / `else`; FreeCAD's view or the placements moved here | `assembly`, `parts`, `is_exploded`, `collapse`, `status`, `settled`, `grounded`, `part_of`, `bounds`, `where_parts_sit`, `axis_dir`, `unit`, `stacked`, `spread`, `exploded_view`, `placement`, `joints_off`, `keep_exploded`, `snapshot`, `vec`, `step` |
| `asm_sub` | AssemblyLink, else App::Link, as a `try`; Rigid or the refusal as `when` / `else` | `assembly`, `unique`, `status`, `snapshot`, `step` |
| `asm_bom` | FreeCAD's BOM or a plain sheet as `when` / `else` | `assembly`, `bom_object`, `unique`, `materials`, `bom_row`, `parts`, `fill_native`, `fill_sheet`, `snapshot`, `step` |

### Kept as code inside a data tool, with the reason

- `sweep_run` (asm_sweep) and `play` (asm_motion): a `try … finally` that puts every part back whatever
  happened. The steps have no `finally` on purpose (docs/data-tools.md, "state that must be put back").
  `play` calls asm_pose itself (the data tool, found in the list the module just built).
- `pair_fit` (asm_fits): one algorithm (the hole and the shaft on an axis, nearest in size, held to ISO
  286). It is the thinnest spot: asm_fits' entry is the loops, the skip and the verdict round it.
- `carried`, `driven_parts` (asm_sweep), `moving_group`, `pose_move` (asm_pose), `stacked`, `spread`
  (asm_explode), `fill_native`, `fill_sheet` (asm_bom): graph walks and arithmetic over the model.
- `_exploded_view`, `_check_parts`, `_overlaps`, `_thread_engagement`, `_element`, `_part`: unchanged.

### Helpers that still refuse in their own words

Unchanged text, compared in the cases, but in code, not in an entry: `_assembly` (picks.one_of's three),
`_part` (2), `_element` (4), `joint_of` (1, shared by five tools; was a closure, now module-level),
`pair_fit` (2, plus `fit_of`'s and ISO 286's "fit: …"), picks' `num`, the session's `body`, and
`assembly.py`'s `doc` ("No document: doc_new first.").

One refusal moved the other way: asm_pose's "The axis of … could not be read from its elements." was raised
inside `moving_group`; the helper now answers `(None, None)` and the entry has the words.

## Behaviour differences

None found: 0 of 213 cases differ. Differences of form, and one real one:

1. **asm_joint's `kind` enum is now fixed text.** The code built it from this FreeCAD's
   `JointObject.JointTypes` (the four couplings only "where this FreeCAD has them"). The entry lists all
   13, which is what FreeCAD 1.1 gives (and the stand-in). On a FreeCAD without a coupling kind the schema
   would still list it; the entry's own check still uses the live `OFFERED` table, so the refusal words
   and what is accepted are unchanged.
2. asm_export called a bound `exportAsASMT` fetched before the check; the entry asks whether it is there,
   then calls `asm.exportAsASMT(p)`. Same call.
3. asm_motion's play read `clearance` inside its loop (inside the `try`); the value is now handed to `play`
   raw and made a float there, in the same place, so a bad clearance still fails after the same poses.
4. asm_limits, asm_explode collapse: the answer is read by `picks.finish` after its snapshot (`late`), as
   the lambda was.
5. Not fixed, kept as they were (asmtd-findings.md's open items): asm_sweep and asm_check are still reads
   that move parts and solve; asm_list still solves; asm_sweep's zero still differs from asm_pose's;
   asm_joint and asm_ground still cannot take a sub-assembly.

## Proof here

`tests/test_dataasm_data.py` (the pattern of `test_datapart2_data.py`, `BASE = "2097f32"`), with
`_dataasm_before.py`, `_dataasm_cases.py`, `_dataasm_standin.py`. The stand-in wraps
`_datapart_standin.install()` and adds to it in the child process only; **no existing stand-in is changed**.

- **Identity**, 16 tools: name, description bytes, schema with key order, changes, reads, group, against
  a snapshot of what the code made at `2097f32`; the snapshot is checked against that commit's source.
- **Old handler against new entry, 213 cases** (117 answer, 92 refuse, 4 crash alike), each in a fresh
  session: the answer or refusal, every call logged, object added or removed and property set in order,
  and the objects left. **0 differ.** 39 answers and refusals are also pinned to fixed text (`EXPECT`).
- **Every `refuse` step is reached**: 49 in the 16 entries (20 in assembly.py's, 29 in
  assembly_more.py's), `UNREACHED` is empty.
- **Every helper present**: each name an entry calls is in its family's dict (`--helpers` answers `{}`).
- No handler or `Tool(...)` of a converted name is left in either file.

What the stand-in is not, and what it leaves unproven:

- **No solver.** `solve()` answers what a case says (a code, a list of codes, or throws); a joint, a flip
  and a solve put a part where a case says. Which part FreeCAD moves, and whether a turn-over helps, is not
  tested: only that old and new ask the same things in the same order.
- Rotations are about z only; a part's box follows its placement's base, not its turn. Overlap is by
  boxes (half the smaller volume where they meet).
- Round faces, the BOM's regeneration, Exploded View, UtilsAssembly's frames and the records store are
  written by simple rules.
- **The window is not exercised**: every case has `GuiUp` false, so `_view_provider` (joints' view
  providers, the healing in `_joints`) and the exploded view's providers are called but do nothing.
  That code is unchanged, but its place in the order is unproven here.
- No case has a session without a document.

## Live model: `docs/hardening/models/asmtd-assembly-model.json` (73 calls, numbered from 1)

| Tool | Calls |
|---|---|
| `asm_new` | 32, 70 |
| `asm_add` | 62 |
| `asm_ground` | 33, 35 |
| `asm_joint` | 31, 34, 36, 44, 49, 52, 64, 71 |
| `asm_list` | 50, 53 |
| `asm_joint_remove` | 65 |
| `asm_sweep` | 42 |
| `asm_check` | 54, 63, 73 |
| `asm_fits` | 55 |
| `asm_motion` | 45, 46, 47, 48 |
| `asm_export` | 60 |
| `asm_pose` | 39, 40, 41, 58 |
| `asm_limits` | 37, 38, 43 |
| `asm_explode` | 57, 59 |
| `asm_sub` | 72 |
| `asm_bom` | 56 |

No converted tool is without a model call. One call only: `asm_add`, `asm_joint_remove`, `asm_sweep`,
`asm_fits`, `asm_export`, `asm_sub`, `asm_bom`. (Calls 66 and 67 are `asm_rigid_group` and `asm_new_part`,
still handlers in `cam_more.py`, not part of this task.)

## Unproven, and risks

1. **Nothing ran on FreeCAD.** The model above on FreeCAD 1.1.3 is the proof still owed. asm_joint is the
   one to watch: it is the longest entry and the path asmtd changed today (Type "Assembly", clearUndo).
2. **Tuples and lists**: the joint's references are lists `[part, [el, el]]` from `joint_refs` (code, as
   before); `ends` holds tuples. The stand-in's trace prints both alike.
3. **Dynamic property names** in asm_limits (`EnableAngleMin` …) and asm_pose (`AgentLinkPose`) are set
   through the runner's `{"set": [object, name, value]}` form in a `do` step; each name has a case.
4. **The schema enum** of asm_joint (difference 1).
5. asm_motion's play depends on asm_pose being in the same module's list; a build that dropped asm_pose's
   entry would fail at play, not at load.
6. `tests/test_files.py` fails until FILES is regenerated (four new files under `tests/`).
7. The older tests that call these tools on real FreeCAD (`tests/test_assembly.py`,
   `tests/test_assembly_more.py`) are among the 338 skipped here.
