# Part, compound and Surface tools as data (tag: datapart, 2026-11-16)

Checkout `<work>/`, base `99489bb` (main when the work started; not rebased). Patch:
`<work>/datapart.patch` (`git add -A -N`, `git diff`, FILES left out; it applies clean to
the base). Nothing committed or pushed. **Nothing ran on FreeCAD**: every proof here is plain Python on a
stand-in. The run was stopped once by a usage limit before anything was written, and started again from
a clean checkout.

## Where it stopped

Three family files are finished, each whole. **Draft was not started**, so the order given was not
followed to its end:

| File | State |
|---|---|
| `families/model.py` (11 `part_*`) | done: all 11 are data |
| `families/std_more.py` (`part_container`, `part_join`, `part_import_curves`, `compound_explode`, `compound_filter`, and Surface's `surface_polynomial`) | done: all 6 are data; the file's other tools (`pd_*`, links, doc, …) untouched |
| `families/surface.py` (6 `surface_*`) | done: all 6 are data |
| `families/draft.py` (`draft_text`, `draft_outline`, `draft_array`, `draft_fonts`, and Surface's `surface_fill`, `surface_loft`, `surface_points`, `surface_thicken`) | **not started** |
| `families/draft_more.py` (13 `draft_*`) | **not started** |
| `families/model_more.py` (10 `part_*`), `families/part_more.py` (6 `part_*`) | **not started** (Part's, but not in the list of files I was given) |

`surface.py` was done ahead of Draft: it is one small file that could be finished whole in what was left,
where Draft's two files (about 1,300 lines of handlers, needing a stand-in Draft module, fonts and SVG/DXF
reading) could not. So Surface is half done as a family: `surface.py` and `surface_polynomial` are data,
the four surface tools in `draft.py` are still code.

## Counts

- **Converted: 23 tools. Kept as code: 0** of the three files' Part / compound / Surface tools.
- `agentlink/data/tools.json`: 50 → 73 entries (23 appended at the end, all `steps`; the 50 before them
  are byte for byte the same prefix of the file).
- Family code: `model.py` 1333 → 900 lines, `std_more.py` 998 → 884, `surface.py` 246 → 111. No
  `Tool(...)` and no handler is left in `model.py` or `surface.py`.
- Suite: 844 passed / 338 skipped before; **851 passed / 338 skipped** after (3 min 44 s), the 7 new
  tests of `tests/test_datapart_data.py` included. Every changed or new file compiles with
  `python3.11 -m py_compile`.
- `scripts/tool_index.py --check` and `scripts/tool_summary.py --check`: current, nothing to change (both
  by name). Echo, activity, heavy (`keep.py`), `paths.GEOMETRIC` (`part_sweep`) tables are by name and
  untouched.
- **No change to `runners.py`, `expr.py`, `tooldata.py` or the schema.** The constructs there covered
  all 23.

## Per tool

Every entry holds the description, schema, the checks with their refusals word for word, the order of
steps and the answer's fields. "Helpers" are what it calls in the family module.

### `model.py`

| Tool | As data | Helpers of note |
|---|---|---|
| `part_primitive` | converted: `choose` by kind, each kind's checks and properties in the entry | `tube` (FreeCAD's BasicShapes tube, or a plain shape where the build has none), `status_said` |
| `part_boolean` | converted: every refusal a `refuse` step, the answer's kept/removed/hidden fields by `when` | `boolean`, `baked` (bake + the labels it hid), `unsound_tool`, `fuse_dropped`, `changed` |
| `part_transform` | converted: `when` for move/rotate, `choose` for mirror/scale/linear/polar, three early `answer` steps | `scaled_each` (the per-axis scale matrix) |
| `part_fillet`, `part_chamfer` | converted (two entries, same steps) | `pick_edges` |
| `part_offset` | converted | none of its own |
| `part_thickness` | converted: the `open` list is an `each` with its refusals | `queried` |
| `part_extrude`, `part_revolve`, `part_sweep` | converted | `profile`, `as_face`, `profile_normal`, `finish` |
| `part_loft` | converted, **thin in its middle** (below) | `loft_clock`, `loft_route`, `align_profiles`, `strays`, `spans_said` |

### `std_more.py`

| Tool | As data | Helpers of note |
|---|---|---|
| `part_container` | converted | `objs` |
| `compound_explode` | converted | `tool_module` |
| `compound_filter` | converted: both `items` refusals, the four "keeps nothing" reasons in the entry | `FILTER_KINDS` (a table), `tool_module` |
| `part_join` | converted: `choose` connect / embed / cutout | `join_feature` |
| `part_import_curves` | converted | `in_file`, `read_shape`, `stem` |
| `surface_polynomial` | converted, **thin** (below) | `cloud_points`, `quadric_patch` |

My helpers are in their own dict (`part_helpers`, added with `helpers.update(part_helpers)` just before
the return) so the other agent's edits to `helpers` and the `pd_*` tools in this file should merge
without touching the same lines. I also removed the six `Tool(...)` lines and handlers; the
"PartDesign" section heading is kept where it was.

### `surface.py`

| Tool | As data | Helpers of note |
|---|---|---|
| `surface_sections`, `surface_extend`, `surface_cut`, `surface_blend` | converted | `new`, `done`, `edge_ref` |
| `surface_boundary` | converted: the Coons/curved fallback to a Surface Filling is two `try` steps in the entry | `chained` |
| `surface_sew` | converted: the solid and its "not made" reason are the answer's `then` steps | `free_edges`, `make_solid` |

`chain` became `chained`: it answers `(flags, None)` or `(None, "open" | "corner" | "order")` and the
entry holds the three refusal texts, as docs/data-tools.md asks of a helper. Nothing else imported
`surface.chain`.

### Thin entries, and helpers that still refuse in their own words

- **`part_loft`**: the entry has every input check (9 refusals and the final "not kept" one), the profiles loop, the refusal's hint
  for each of its three causes, and the answer's `aligned` / `route` / `maxDegree` / `strays`. The
  try-again strategy (as given, rebuilt as B-splines, degree 5 → 3 → 2, span by span, two profiles
  ruled, all against a clock) is one helper, `loft_route`, with `segmented` beside it: about 110 lines
  moved unchanged. It is one algorithm with state and a deadline; as JSON it would be longer and no
  clearer. Say so if it should be broken up further.
- **`surface_polynomial`**: two checks and the answer in the entry; the least-squares fit and the
  Bézier patch are one helper, `quadric_patch` (numpy, one algorithm).
- **Shared readers that keep their own refusals** (they are reference reading, used by several tools,
  and were helpers of the handlers before): `profile` and `as_face` (extrude, revolve, loft, sweep),
  `pick_edges` (fillet, chamfer), `finish` in `model.py` (the `op` / `into` step, with "op …: into
  names the body" and "changed nothing"), `edge_ref` (four surface tools), `objs`. These texts are
  unchanged and are compared in the cases, but they are in code, not in an entry.

## Fixes of today's hardening passes, where they now live

I did not go through `docs/hardening/part-findings.md` and `draftmesh-findings.md` fix by fix. The
handlers at `99489bb` already held those fixes; every branch of each was carried over and is compared
old against new, so a fix is lost only if a case misses its branch. Those I can name from the code:
`part_boolean`'s unsound-tool, invalid-result, dropped-tool and hidden-inputs handling (refuse steps,
`unsound_tool`, `fuse_dropped`, `baked`); `part_thickness`'s several-solids and 0.002 mm refusals;
`part_revolve`'s angle range; the cone's base radius of 0; the wedge's ridge rule; a surface answering
as a surface (`report_surface`, unchanged, reached through `finish`); `part_loft`'s time budget and
`unchecked`; `compound_filter`'s FreeCAD filter names; `part_join` and `compound_filter` made in the
session's document; `surface_boundary`'s chain order and its Filling fallback; `surface_sew` sewing
only the faces listed.

## Proof here

`tests/test_datapart_data.py` (the BIM pattern), with `_datapart_before.py`, `_datapart_cases.py`,
`_datapart_standin.py`:

- **Identity**, 23 tools: name, description bytes, schema with key order, changes, reads, group, against
  a snapshot of what the code made at `99489bb`; the snapshot itself is checked against that commit's
  source.
- **Old handler against new entry, 295 cases** (110 answer, 183 refuse, 2 crash alike), each run in a
  fresh session on the stand-in: the answer or refusal, every shape operation, object added or removed
  and property set in order, and the objects left must be equal. 0 differ. 45 answers and refusals are
  also pinned to fixed text (`EXPECT`).
- **Every `refuse` in the 23 entries is reached** by at least one case (`UNREACHED` is empty).
- Every name an entry calls is in its family's helpers.
- Where numpy is missing the four side-by-side tests skip (`std_more.py` needs it to import): under this
  machine's `python3.11` they skip, under `python3` they run.

What the stand-in is not: FreeCAD's geometry. A shape there is a kind, a box, a volume and counts; a
fuse adds volumes. For `part_loft` the module-level geometry (`align_profiles`, `as_polygons`,
`as_matching_bsplines`, `loft_problem`, `loft_overshoot`, `loft_spans`, `strays`), which the conversion
did not touch, is replaced in both old and new by stand-ins a case steers, and `shape_query`'s filter and
`geometry.stats` / `soundness` likewise. So the proof is of order, words and answer shape.

## Live models

Calls that exercise each converted tool (call numbers from 1):

- `part-model.json`: `part_primitive` 2, 3, 6, 7, 8, 11, 14, 16, 17, 33, 40, 44, 61, 73, 78, 85, 86, 89,
  90, 92–96; `part_boolean` 9, 10, 15, 18, 19, 20, 91; `part_transform` 12, 13, 43, 46–49;
  `part_fillet` 32, 37; `part_chamfer` 38; `part_offset` 45; `part_thickness` 41, 42; `part_extrude`
  35, 36, 79; `part_revolve` 50, 51; `part_loft` 54; `part_sweep` 53; `part_container` 88;
  `compound_explode` 31; `compound_filter` 28, 29, 30; `part_join` 87; `part_import_curves` 98.
- `draftmesh-surface-model.json`: `surface_boundary` 6, 7, 35, 36; `surface_sections` 12, 13, 41;
  `surface_extend` 14, 15, 16; `surface_cut` 18, 20; `surface_sew` 22, 23, 24; `surface_blend` 29, 30,
  44; `surface_polynomial` 51, 52; `part_primitive` 17, 21.
- `draftmesh-draft-model.json`: `part_primitive` 69, 76 only.
- Others also call `part_primitive` / `part_boolean` / `part_transform` (assembly, techdraw, cam, points,
  coredoc, mesh, fem models).

**No converted tool is without a model call.** Thinly covered live: `part_loft` (one call: none of its
retry routes), `part_sweep`, `part_chamfer`, `part_offset`, `part_container`, `compound_explode`,
`part_join`, `part_import_curves` (one call each).

## Unproven, and risks

1. **Nothing ran on FreeCAD.** The live models above are the proof still owed, `part-model.json` and
   `draftmesh-surface-model.json` first.
2. **`part_loft`** is the largest risk: 110 lines moved into `loft_route`, with the clock now an object
   (`Clock`) instead of closures. All 40 loft cases agree on the stand-in, including late and
   out-of-time ones, but real OCC lofts, real timing and the heavy gate's `call_budget` were not run.
3. **Dict and tuple values** set on properties (`o.Face = (obj, [sub])`, `NSections`, `BoundaryEdges`,
   `ShapeList`) are tuples in the entries as in the code; the stand-in's trace prints a tuple and a list
   alike, so this was checked by reading, not by the test.
4. **Listing order**: in `std_more` the six moved tools now come first in the group's list (data before
   code), as `pd_clone` already did. `model` and `surface` keep their order.
5. **Module loading**: `compound_explode`, `compound_filter`, `part_join` and `surface_polynomial` load
   their FreeCAD module (or numpy) as their first step through `tool_module`, to keep the handler's
   order (import, then checks). An import failure is still a crash, as before.
6. Evaluator edge: `part_primitive` with a `kind` that is a list crashes the same way old and new
   (unhashable in a dict test); kept so, with a case.
7. `docs/data-tools.md` still says only the BIM family is data. I left it alone because other agents
   are writing to it in parallel; one sentence there is owed once the patches are merged.
8. FILES was not regenerated (four new test files).
