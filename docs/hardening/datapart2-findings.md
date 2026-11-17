# The rest of the Part tools as data (tag: datapart2, 2026-11-16)

Checkout `wt3/d6`, base `b408a91`. Patch: `datapart2.patch` (`git add -A -N`, `git diff`; FILES not
touched; `git apply --check` on a clean `b408a91` passes). Nothing committed or pushed, no network.
**Nothing ran on FreeCAD**: every proof here is plain Python on a stand-in.

## Where it stopped

Both files are finished, each whole. Nothing remains of the task.

| File | State |
|---|---|
| `families/model_more.py` (10 `part_*`) | all 10 are data; 553 → 175 lines, no `Tool(...)` and no handler left |
| `families/part_more.py` (6 `part_*`) | all 6 are data; 421 → 159 lines, no `Tool(...)` and no handler left |

## Counts

- **Converted: 16. Kept as code: 0. Thin entries: 0.**
- `agentlink/data/tools.json`: 167 → 183 entries. The 16 are appended at the end in the old listing
  order, all `steps`, each with `"family": "model_more"` or `"family": "part_more"`; the diff of the file
  is 827 added lines and 0 removed (the 167 before are byte for byte as they were).
- Each family file ends `runners.tools(GROUP, s, helpers, family="model_more" | "part_more")`, as
  `draft.py` and `bim_more.py` do (`model.py` asks with no family, so it does not pick these up).
- **No change to `runners.py`, `expr.py`, `tooldata.py` or the schema.**
- Suite (`timeout 290 python3 -m pytest -q tests`): **886 passed, 338 skipped, 1 failed** in 200 s. The
  one failure is `tests/test_files.py` (FILES stale: the four new test files), as expected; FILES left
  alone. The 7 tests of `tests/test_datapart2_data.py` are among the passed.
- `python3 scripts/tool_index.py --check` and `scripts/tool_summary.py --check`: both exit 0, nothing to
  change.
- `python3.11 -m py_compile` passes on the two family files and the four new test files.
- `docs/data-tools.md`: one paragraph added (Part's three files are data; the `family` keys; the two
  proofs). The earlier note said this sentence was owed.

## Per tool

Every entry holds the description and schema (from the snapshot of the code at `b408a91`), every check
with its refusal word for word as a `refuse` step, the order of steps and the answer's fields.

### `model_more.py` (`"family": "model_more"`)

| Tool | As data | Helpers it calls |
|---|---|---|
| `part_wire` | `choose` by kind (arc shares circle's steps); 26 refusals; `picks.number(…, msg=)` became `num` + a `refuse` step so the words are in the entry; the points / points_file choice is steps | `new_obj`, `frame`, `outline_file`, `bspline`, `as_wire`, `fit_of`, `added` |
| `part_split` | `choose` slice / fragments / xor; the "is an element" check is an `each` for bodies and for tools; the failed feature removed in `refuse.first`; `next` in `answer.then` | `split_features`, `bop_feature`, `explode_into`, `settled` |
| `part_compound` | explode as an early `answer` | `explode_into`, `new_obj`, `added`, `settled` |
| `part_refine` | the PartDesign tip route as an early `answer`; fix and shell→solid as `try` steps | `solid_body`, `as_shell`, `as_solid`, `bake`, `soundness`, `settled` |
| `part_attach` | the default mode by element and the modes check in the entry | `find`, `resolve`, `split_ref`, `placement`, `rotation`, `placement_json`, `settled` |
| `part_face` | | `shaped`, `in_order`, `as_wire`, `flat_face`, `new_obj`, `added` |
| `part_ruled` | the old inner `curve(key)` is an `each` over a, b with its three refusals | `shaped`, `split_ref`, `element`, `new_obj`, `added` |
| `part_project` | the per-wire projection loop with its `try` is steps; the two "nothing landed" texts are two `refuse` steps | `resolve`, `direction`, `as_wire`, `compound`, `empty_shape`, `added` |
| `part_slices` | the reach along the normal, the distances and the row per slice are expressions | `solid_body`, `direction`, `num`, `section_area`, `compound`, `added` |
| `part_from_mesh` | file or object, limits, sewing, largest shell, refine, the several-shells note | `mesh_module`, `local`, `isfile`, `read_mesh`, `stem`, `find`, `empty_shape`, `make_shell`, `as_solid`, `soundness`, `added` |

### `part_more.py` (`"family": "part_more"`)

| Tool | As data | Helpers it calls |
|---|---|---|
| `part_section` | parametric or plain as `when` / `else`; the face as a `try` | `plane_face`, `shape_stats`, `add_shape`, `sort_edges`, `as_wire`, `flat_face` |
| `part_offset2d` | the closed-wire route as an early `answer`; Part::Offset2D removed in `refuse.first` | `flat_face`, `compound`, `add_shape`, `shape_stats` |
| `part_extract` | `choose` by build (solid shares shell's steps); the old `elements()` is a `refuse` step plus `picked` | `ref_list`, `picked`, `make_shell`, `sewn`, `as_solid`, `sort_edges`, `as_wire`, `flat_face`, `add_shape`, `shape_stats` |
| `part_defeature` | faces loop as `each` | `solid_body`, `split_ref`, `element`, `bake` |
| `part_fix` | `choose` by op | `sewn`, `make_shell`, `as_solid`, `compound`, `add_shape`, `bake`, `shape_stats` |
| `part_datum` | the type fallback loop, the plain-shape stand-in, the default mode table by (kind, element), both attachment refusals | `DATUMS` (a table), `datum_shape`, `is_round`, `placement_of`, `resolve`, `find` |

New named helpers, each with a docstring: `added`, `settled`, `new_obj`, `outline_file`, `fit_of`,
`split_features`, `bop_feature`, `explode_into`, `section_area`, `mesh_module`, `stem`, `isfile`
(model_more); `picked`, `datum_shape`, `is_round`, and docstrings added to `shape_stats`, `add`,
`stats_of` (part_more / model_more). `frame`, `_sew`, `plane_face` are unchanged. Every FreeCAD / Part
attribute in the two helper dicts is behind a lambda (`Part.sortEdges`, `Part.makeShell`,
`FreeCAD.Placement` …), so another family's stand-in that lacks one can still build the tool list; the
full suite passing is the check of that.

### Helpers that still refuse in their own words

Shared readers, unchanged and compared in the cases, but in code, not in an entry: picks' `vec3`, `num`,
`direction`, `find`, `shaped`, `solid_body`, `resolve`, `element`, `placement`; `added`'s "FreeCAD
refused it: {msg} — nothing was kept." (picks.finish's `refuse`, shared by seven tools here);
`outline_file` (pointfiles' and paths' refusals); `plane_face` (plane.normal / plane.at through picks).

## Behaviour differences

None found: 0 of 305 cases differ. Things that are not identical in form, all compared and equal:

- Where the old handler gave `picks.finish` a lambda (read after the snapshot) for `part_compound`
  explode, `part_refine` and `part_attach`, the entry's fields are read just before it. Nothing changes
  between the two points (`recompute=False`), and `added` still reads label, type and stats after its
  recompute as before.
- `part_from_mesh` and `part_split` load their FreeCAD module as their first step (`mesh_module`,
  `split_features`), to keep the handler's order: import, then checks. A missing module is still a crash,
  as before (a case each).
- Kept as they were, not fixed (the brief asked for identical behaviour): a B-spline that does not close,
  a parametric `part_section` of bodies that do not meet and a `part_datum` that will not attach are
  refused with their object still added by the handler's own code (the call's transaction is what takes
  it back); a plain-shape `part_section` of two bodies that do not meet answers with the "plane misses"
  words. Each has a case.

## Proof here

`tests/test_datapart2_data.py` (the pattern of `test_datapart_data.py`, `BASE = "b408a91"`), with
`_datapart2_before.py`, `_datapart2_cases.py`, `_datapart2_standin.py`. The stand-in file wraps
`_datapart_standin.install()` and adds to it in the child process only; **`_datapart_standin.py` itself
is not changed**.

- **Identity**, 16 tools: name, description bytes, schema with key order, changes, reads, group, against
  a snapshot of what the code made at `b408a91`; the snapshot is checked against that commit's source.
- **Old handler against new entry, 305 cases** (148 answer, 150 refuse, 7 crash alike), each in a fresh
  session: the answer or refusal, every shape operation, object added or removed and property set in
  order, and the objects left. **0 differ.** 35 answers and refusals are also pinned to fixed text
  (`EXPECT`).
- **Every `refuse` step is reached**: 89 in the 16 entries, `UNREACHED` is empty.
- **Every helper present**: each name an entry calls is in its family's dict (the `--helpers` child
  answers `{}`).
- No handler or `Tool(...)` of a converted name is left in either file.

What the stand-in is not: FreeCAD's geometry. Slices, sections, projection, defeaturing, 2D offsets,
BOPTools' split features, attachment modes and the Mesh module answer by simple rules a case steers
(flags). The proof is of order, words and answer shape.

## Live model: `docs/hardening/models/part-model.json` (98 calls, numbered from 1)

| Tool | Calls |
|---|---|
| `part_wire` | 22, 52, 55, 58, 59 |
| `part_section` | 23, 24 |
| `part_slices` | 25 |
| `part_split` | 26 |
| `part_compound` | 27 |
| `part_refine` | 39 |
| `part_face` | 56 |
| `part_offset2d` | 57 |
| `part_ruled` | 60, 62 |
| `part_project` | 63 |
| `part_extract` | 64, 65 |
| `part_fix` | 66, 67, 68 |
| `part_datum` | 69, 70, 71, 72 |
| `part_attach` | 74, 75, 76, 77 |
| `part_defeature` | 81 |
| `part_from_mesh` | 83, 84 |

No converted tool is without a model call. Also: `draftmesh-surface-model.json` calls `part_wire` 8
times, `draftmesh-mesh-model.json` `part_wire` and `part_from_mesh` once each. Thinly covered live (one
call): `part_slices`, `part_split`, `part_compound`, `part_refine`, `part_face`, `part_offset2d`,
`part_project`, `part_defeature`.

## Unproven, and risks

1. **Nothing ran on FreeCAD.** `part-model.json` on FreeCAD 1.1.3 is the proof still owed.
2. **Values set on properties**: `Curve1` / `Curve2` are tuples `(object, [sub])`, the attachment support
   a list of one tuple, `Nodes` a list of vectors, as in the code. The stand-in's trace prints a tuple and
   a list alike, so tuple-ness was checked by reading, not by the test.
3. **`part_datum`'s default mode** is one long expression (a dict keyed by (kind, element)); all eleven
   pairs and the ObjectXY fallback have a case, but FreeCAD's attacher was not asked.
4. **Dynamic property name** (`AttachmentSupport` or `Support`) is set through the runner's existing
   `{"set": [object, name, value]}` value form inside a `do` step, in `part_attach` and `part_datum`; both
   names have a case.
5. `tests/test_files.py` fails until FILES is regenerated (four new files under `tests/`).
6. The two older tests that call these tools on real FreeCAD (`tests/test_more_families.py`
   `test_part_more`, `tests/test_gaps_redteam.py` H4) are among the 338 skipped here.
