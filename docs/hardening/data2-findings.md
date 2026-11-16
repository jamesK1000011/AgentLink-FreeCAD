# Tools as data, second pass: richer constructs, the whole BIM family (2026-11-16)

Checkout `(the agent workspace)`, base `9b4bc52` (main when the work started; main has moved since, not
rebased). Patch: `(the agent workspace)` (`git add -A -N`, `git diff`, FILES left out).
Nothing committed or pushed. FreeCAD did not run here. The session was restarted once mid-run; the work
was picked up from the files and finished.

## Counts

- BIM handlers looked at: 40 (`bim.py` 18, `bim_more.py` 9, `bim_gaps.py` 13).
- **Converted: 40** (the 3 of the earlier held commit 79936a8, brought in first, plus 37 with the new
  steps runner). **Kept as code: 0.** With steps, expressions and named helpers none of the 40 is
  unusable as data. Three entries are thin (two or three helper calls and the answer's shape):
  `bim_quantities`, `bim_schedule`, `bim_library`. Say so if that is not what "data" should mean; they
  are easy to turn back.
- `agentlink/data/tools.json`: 10 → 50 entries (13 wrappers, 37 steps). The hub's 405 tools: 50 data,
  355 code.
- Family code: `bim.py` 1040 → 501 lines, `bim_more.py` 575 → 210, `bim_gaps.py` 403 → 204. No
  `Tool(...)` and no handler is left in the three files; what remains is the helpers.
- Suite: 789 passed / 337 skipped before; **800 passed / 337 skipped** after (about 3 min). New tests
  also pass under `python3.11`; every changed file compiles with `python3.11 -m py_compile`.
- `scripts/tool_index.py --check` and `tool_summary.py --check`: current, no change needed (both are
  by name). Echo and activity tables untouched (by name).

## Constructs added

- **`agentlink/expr.py`** (new, 318 lines): one evaluator shared by rules, args, steps and answers.
  A value starting with `=` is an expression in Python's own syntax, parsed with `ast.parse` and walked
  by a whitelist interpreter: arithmetic, comparisons, and/or/not, conditionals, lists/dicts/sets,
  comprehensions, lambda (for `sorted`), attributes and methods of values, listed functions, the
  family's helpers. No `eval`/`exec`. Names and attributes starting with `_`, assignment, import,
  f-strings and star-args are refused when the entry is loaded. `fmt()` fills messages with f-string
  style fields (`{sill + height:g}`, `{path!r}`, `{{ }}`), so refusal texts carry over verbatim.
- **`steps` runner** (`runners.py`): `let`, `refuse` (with `code`, `first` = undo steps), `make`
  (dotted maker, `headless`), `add`, `set`, `do`, `put`, `push`, `each`, `when`/`then`/`else`,
  `choose`, `try` (`on`: error | refusal | named Python errors), `answer` (ends the run; `late`: the
  finishing helper reads the fields after its recompute; `then`: after-the-answer steps). `when` on any
  step.
- **Named helpers**: each family's dict, three sorts (finishing code, FreeCAD's own under short names,
  small geometry/API functions with docstrings: `wall_side`, `wall_run`, `roof_ridge`, `roof_runs`,
  `window_shape`, `prism`, `plain_bars`, `tile_grid`, `lay_tiles`, `counted`, `takeoff`, `unclone`,
  `depth_along`, `nest_run`, `emptied` …). A test checks every name an entry calls against its
  family's dict.
- **`family`** (entry field): `bim.py` and `bim_more.py` share group `bim`; an entry says whose
  helpers it calls.
- Load-time checking: `tooldata.check` parses every expression and template and validates every step.
- Written up in `agentlink/tooldata.py`'s docstring, `agentlink/data/tools.schema.json` (tools.json
  validates against it with jsonschema) and `docs/data-tools.md` (what each construct is for, a real
  example each, the line where code is still right).

Today's fixes, where they now live: hip roof ridge → helper `roof_ridge`, called in `bim_roof`'s
`answer.then`; clockwise roofs → `ccw` + the `flip` steps in the entry; `bim_opening`'s wall side →
helper `wall_side`; `bim_ifc`'s classification rule → a `refuse` step in the entry; `bim_export`'s
guard → a `refuse` step, its where-it-stopped message → the `try`'s `refuse` with helper `stopped`;
`bim_quantities` not double counting → helper `counted`; grids → `bim_grid`'s steps.

## Proof here

- `tests/test_runners.py` (+8 tests): the evaluator (about 45 expressions, 20 refused forms),
  messages, each step kind, early/late/after answers, reads, format checks, families.
- `tests/test_bim_data.py`: identity of all 40 (name, description bytes, schema incl. key order,
  changes, reads, group) against `tests/_bim_before.py`, itself checked against git `b2d3dbd` (the three
  family files are identical there and at `9b4bc52`); no handler left; helpers present; and
  **431 cases** run old handler vs new entry on a stand-in FreeCAD (`tests/_bim_standin.py`): result or
  refusal (code and words), every maker call / object added or removed / property set in order, objects
  left. **0 differ.** Every `refuse` text in the 40 entries is reached by at least one case. A
  deliberate change to three entries was caught (then reverted).
- The proof found one real hole in my own evaluator (a `{o.__class__}` field in a template got
  through); fixed and tested.

## The live model (`docs/hardening/models/bimcam-bim-model.json`, `calls` from 0)

Exercised (33 of 40):

| Tool | Calls | Tool | Calls |
|---|---|---|---|
| bim_wall | 1, 2 | bim_layers | 26 |
| bim_opening | 3, 4, 5, 6 (refusal), 7 | bim_ifc | 27, 28, 29 (refusal) |
| bim_structure | 8, 9, 10, 11, 12, 38 | bim_rebar | 30 |
| bim_profiles | 13 | bim_covering | 31 |
| bim_member | 14 | bim_schedule | 32, 33 |
| bim_roof | 15, 16 (clockwise hip) | bim_quantities | 34 |
| bim_stairs | 17 | bim_edit | 35 (cut), 36 (clone) |
| bim_space | 18, 19 (refusal) | bim_grid | 37 |
| bim_building | 22 | bim_section | 41 |
| bim_material | 24, 25 | bim_views | 42 |
| bim_truss | 43 | bim_fence | 44 |
| bim_frame | 45 | bim_curtain_wall | 46 |
| bim_panel | 47 | bim_panel_out | 48 (cut) |
| bim_component | 54 | bim_ifc_brep | 55 |
| bim_trash | 56 (put), 57 (list) | bim_reorder | 58 |
| bim_preflight | 59 | bim_export | 60 |
| bim_import | 68 | | |

**Not exercised (7):** `bim_reference`, `bim_nest`, `bim_image_plane`, `bim_library`, `bim_reextrude`,
`bim_rewire`, `bim_glue`. Also not in the model: `bim_edit` add / subtract / join, `bim_panel_out`
sheet, `bim_component` clone / unclone, `bim_trash` empty, `bim_structure` on a base sketch, and most
refusals. `tests/test_bim_gaps.py` (FreeCAD only, skipped here) covers some of the seven on the Mac.

Already data before, also in the model and untouched: `bim_level` 20–21, `bim_list` 23,
`bim_structural_system` 39–40, `bim_pipe` 49–50, `bim_pipe_connector` 51, `bim_equipment` 53.

## Does it scale? The other families (355 code tools)

A quick survey: tool names and descriptions, each family's header and its handlers' sizes (median and
longest), not a read of every handler. Treat the numbers as ± 20.

| Would convert (steps + helpers) | of | Family |
|---|---|---|
| 17 / 5 | 19 / 7 | feature, feature_more (pd_ makers; pd_gear stays) |
| 9 / 9 / 5 / 6 | 11 / 10 / 6 / 6 | model, model_more, part_more, surface |
| 6 / 12 | 8 / 13 | draft, draft_more |
| 5 / 10 | 8 / 12 | sketch, sketch_more |
| 28 | 32 | techdraw |
| 24 | 27 | std_more |
| 6 / 4 / 9 / 5 | 6 / 4 / 11 / 7 | param, material, sheet, notes |
| 16 / 6 | 20 / 8 | meshobj, points |
| 4 / 4 | 6 / 6 | inspection, measure |
| 6 / 4 | 8 / 8 | assembly, assembly_more |
| 8 / 5 / 5 | 12 / 6 / 6 | cam, cam_more, robot |
| 5 / 3 | 6 / 5 | ifc, openscad |
| 8 | 13 | doc |
| 8 / 1 | 16 / 3 | strength (FEA), fem_more |
| 6 | 17 | app |
| 0 | 28 | tools.py (hub), dev, unattended, view, ext |

**About 250 of 355 (70%)**, so with BIM about 300 of the hub's 405. About 60 handlers are over 60
lines; most of those would be helper-heavy entries or stay code.

The three hardest:
1. `sketch_edit` (`sketch.py`, 214 lines, with a 203-line `build`): geometry and constraints edited
   against the solver's state, index by index. An algorithm over the sketch; code.
2. `view_render` / `view_snapshot` (`view.py`, 206 / 98 lines): the window and the offscreen renderer,
   pictures out. GUI; code.
3. `fea_solve` and `fea_native` (`strength.py`, a 146-line build-and-run and a 150-line handler):
   meshing and a solver run as a long job. Heavy solver; code. `batch` (`tools.py`, 170 + 179 lines)
   is the same class for the hub itself.

## Risks

- **Not run on FreeCAD.** The stand-in proves order and words, not Arch. The 337 skipped tests include
  `tests/test_more_families.py::test_bim*` and `tests/test_bim_gaps.py`: run them and the live model on
  the Mac before this is trusted.
- **Expression syntax is Python's**, read by `ast.parse`. It is not eval, but an entry author can call
  any method of a value in the run (`doc().removeObject(…)`), as `{"do": […]}` already allowed. The
  data file is the hub's own; add-ons do not get runners. If an add-on were ever given the steps
  runner, method calls would need a whitelist.
- **Readability varies.** Most entries read as the tool. `bim_preflight` (nested `when`s),
  `bim_covering` and `bim_edit` are long; three are thin (above). tools.json is 4114 lines; steps are
  laid out one per line, the older entries keep `indent=1`, so the file has two layouts.
- **Small behaviour differences, all in states that do not occur:** where the handler did
  `import ArchProfile` and crashed without it, `bim_frame` now answers a `failed` refusal; a `try`
  without `on` catches any error where two handlers caught the same; nothing else known.
- **Tool order** in `tools/list` within the group changes (all data now, in the old code order).
- Speed: an expression is parsed once and cached, then interpreted; per call that is microseconds
  against FreeCAD's milliseconds. `bim_preflight` and `bim_schedule`'s sheet loop interpret per object:
  not measured on a large model.
- Old-vs-new tests need git commit `b2d3dbd`; without it 4 of the 7 tests skip (identity still runs
  against the snapshot).

## To do on merge (not in the patch)

- `FILES` must gain `agentlink/expr.py`, `docs/data-tools.md`, `tests/_bim_before.py`,
  `tests/_bim_cases.py`, `tests/_bim_standin.py`, `tests/test_bim_data.py`, or `tests/test_files.py`
  fails once they are tracked.
- `CHANGELOG.md` not touched. `docs/hardening/data-findings.md` of the held commit was left out.
- Main moved (tools.py, protocol.py, echo.py, nexthint data): the patch touches none of those; expect
  a clean 3-way apply, then re-run `scripts/tool_index.py --check`.

## Where I stopped

At the end: every file is complete, the suite passes. Nothing is half-converted.
