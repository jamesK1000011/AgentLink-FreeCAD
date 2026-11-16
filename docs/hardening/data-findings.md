# Tools as data: the BIM family (resumed 2026-11-16)

Checkout `(the agent workspace)`, base `b2d3dbd`. Patch: `(the agent workspace)`
(`git add -A -N`, `git diff`, FILES left out). Nothing committed or pushed. FreeCAD did not run here.

## Counts

- Looked at: 40 handler tools in `bim.py` (18), `bim_more.py` (9), `bim_gaps.py` (13).
- **Converted: 3** — `bim_wall`, `bim_section`, `bim_reference`.
- **Kept as code: 37** (reasons below). Of the survey's twelve named candidates, 2 converted and 10 stay.
- `agentlink/data/tools.json`: 10 → 13 entries.
- Plain-Python suite: 784 passed / 337 skipped before; **789 passed / 337 skipped** after (4 new tests in
  `tests/test_bim_data.py`, 1 in `tests/test_runners.py`). `scripts/tool_index.py --check`: current, no change to
  `tool_index.json` (the index is by name; names did not change). Echo tables untouched (by name too).

This is fewer than the survey hoped. Under the rule as written (checks must fit `rules`, no one-off special
cases, nothing bent into data) most of the named candidates are not plain wrappers in today's code.

## Converted

| Tool | Runner | Maker | Description bytes before / after | Schema |
|---|---|---|---|---|
| `bim_wall` | make | `Arch.makeWall(base, width=, height=, align=)` | 337 / 337, identical | identical, same property order |
| `bim_section` | make | `Arch.makeSectionPlane(objects)` via `headless_call` | 234 / 234, identical | identical |
| `bim_reference` | make | `Arch.makeReference(file, part)` via `headless_call` | 201 / 201, identical | identical |

Name, changes (true), reads ({}), group (`bim`, `bim`, `bim_gaps`) are the same as the code made. Refusal
messages are in the data word for word; two are format templates where the code had an f-string
(`{base.Label}`, `{path!r}`) and render the same text (tested).

What each keeps from the handler, in the same order:

- `bim_wall`: width, height (`pos`), align (map, refused when not one of three), name, then base by label
  (refused when it has no edges: not a Part shape, null, or edgeless) or a baseline from points (`closed`),
  refusal when neither; makeWall by keyword (today's fix: 1.1 has `offset` before `face`); named; `finish`
  with length (sum of the base's edges), width, height, align, base. `finish` is the family's own, so
  today's `min` in the answer is kept.
- `bim_section`: no-maker refusal, objects (named, else every BIM object not in a container), normal
  (zero refused), "Nothing to cut", make, placement (at is read after the make, as before), named, the
  answer with today's corrected note (`td_bim`).
- `bim_reference`: file check (`not_found`), make, named when a name is given, recompute, snapshot, answer
  without `step` (as before).

## Kept as code, and why

`bim.py`
- `bim_opening` — today's wall-side fix: finds the straight run, works out the side from Align and Offset, builds the hole and the frame.
- `bim_structure` — four kinds, each its own geometry (outline to face, squat prism, beam frame).
- `bim_profiles` — not a FreeCAD object read: filters the section library's rows (lists by index), limit, "more". The read runner reads document objects.
- `bim_member` — library lookup with near names, placement frame, mass.
- `bim_roof` — today's ridge reading from the built roof's underside; per-edge angles and runs, clockwise flip.
- `bim_stairs` — default step count, direction flattened and framed into a placement, riser/going/Blondel arithmetic and its note. Would need three one-off helpers or arithmetic in JSON.
- `bim_space` — three ways in, the space-type lookup with near names, and removal of what it made when the use is refused.
- `bim_building` — two objects: the building, then a site made after the step is recorded, added to the answer afterwards. Only this tool would use an "after the answer" step, so no runner feature was added for it.
- `bim_curtain_wall` — extrudes the line to a face and computes section counts from the mean stretch.
- `bim_rebar` — bar layout arithmetic and the fallback that builds bars itself.
- `bim_panel` — two different maker calls by input (outline face vs length × width at a point), the outline-to-face step has its own refusal.
- `bim_grid` — a loop over two directions, gap lists, the quarter turn.
- `bim_material` — find or make, edits the material dictionary, checks every object first.
- `bim_schedule` — Agent Link's own take-off and sheet writer; wraps no command.
- `bim_export` — today's guard (bare classification named before the exporter is tried), the stop-point message, read-back.
- `bim_import` — fallback reader.

`bim_more.py` (all nine stay; none is a one-command wrapper)
- `bim_frame` (library profile, path or points, mass), `bim_truss` (pattern mapping, set/skipped), `bim_fence` (builds post and panel), `bim_covering` (tiling), `bim_layers` (loop over layers and objects), `bim_ifc` (today's classification rule, property sets), `bim_quantities`, `bim_preflight` (own checks), `bim_edit` (five ops).

`bim_gaps.py`
- `bim_component` (three kinds; unclone copies properties), `bim_panel_out` (two kinds, loops), `bim_nest` (nester set-up, rotations swapped and restored), `bim_ifc_brep` (toggles a dictionary per object), `bim_views` (two objects per level), `bim_image_plane` (aspect from the file), `bim_library` (search and insert), `bim_reextrude`, `bim_rewire`, `bim_glue` (builds a compound itself, deletes originals), `bim_trash` (three actions), `bim_reorder`.
- Already data before this run: `bim_remove_shape`, `bim_structural_system`, `bim_pipe_connector` (untouched).

## Runner capabilities added (`agentlink/runners.py`, +15 −3)

1. A rule may carry `"when": expression`; it is checked only when that is truthy (and is used up either way). For a check that belongs to one way of calling a tool (`bim_wall`'s base).
2. `{"sum": e}` — adds a list (the wall's length from its edges; `Shape.Length` was not used because it differs from the sum of edges on some shapes).
3. An argument's `"then"` step sees `$value` (the argument, its default when left out) and `$key`. So a value can be read after the object is made, as the handler did (`bim_section`'s `at`).

All three are general, tested in `tests/test_runners.py::test_rule_when_sum_and_a_step_value`, and change nothing for the ten existing entries (none uses `when`, `sum`, or `$value` in a `then`). No one-off cases.

Family helpers added (small, shared code the entries name): `bim.py` — `vec`, `edges` (module function), `loose`, `facing`, `done`; `finds` now takes an optional "what" (its one existing user, `bim_level`, calls it as before). `bim_gaps.py` — `file` (module function), `basename`, `snapshot`.

## Lines

- Handler code removed: `bim.py` −40 lines (two handlers, two `Tool(...)` blocks), `bim_gaps.py` −13 (one handler, one `Tool(...)`). Added back as helpers: +9 and +8. Net family code −36.
- `tools.json` +442 lines (indent 1). `tests/test_bim_data.py` +452, `tests/_bim_before.py` +118, `tests/test_runners.py` +28.

## Proof here

- `tests/test_bim_data.py`
  - each converted tool built from data equals the snapshot of the code's tool: name, description (bytes), inputSchema (and property order), changes, reads, group;
  - no handler or `Tool("…")` of a converted name is left in the three family files;
  - the snapshot (`tests/_bim_before.py`) equals what `b2d3dbd`'s source builds (skipped where git lacks that commit);
  - **49 cases** run the old handler (from `git show b2d3dbd:…`) and the new entry on a stand-in FreeCAD/Part/Arch in a child process: answer or refusal (code and words), every call and property set in order, and the objects left are the same. 28 `bim_wall`, 14 `bim_section`, 7 `bim_reference`; refusal precedence included. It caught one real difference during the work (`at` validated before the make), fixed with capability 3.
- Health: unchanged path. The entries have `changes: true`, so calls go through the session's transaction and the shared check as before.

## The live model (`docs/hardening/models/bimcam-bim-model.json`, `calls` counted from 0)

- `bim_wall`: `calls[1]` (closed outline, align right, "Outer walls") and `calls[2]` ("Inner wall", align center). Every later call that names those walls depends on them (openings 3–7, level 20, material 24, layers 26, ifc 27, edit 35).
- `bim_section`: `calls[41]` ("Plan cut", cuts = the site).
- `bim_reference`: **not exercised** (the model has no second file to reference).
- Already-data tools the model also runs, unchanged here: `bim_level` 20–21, `bim_list` 23, `bim_structural_system` 39–40, `bim_pipe` 49–50, `bim_pipe_connector` 51, `bim_equipment` 53. `bim_remove_shape` is not in the model.

## Unproven

- Nothing here ran on FreeCAD. The family tests that need it (`tests/test_more_families.py::test_bim*`, `tests/test_bim_gaps.py`) are among the 337 skipped, the same count as before; they are unchanged and should be run on the Mac.
- The stand-in proves order and words, not Arch's behaviour: real `Vector.Length`, real edges of a sketch, `makeReference` on a real file.
- `bim_wall { base }` (a wall along a sketch) is not in the live model; only points are. `bim_reference` is not in it at all. No refusal of the three tools is in it.
- `tools/list` order within the group changes: data tools come first, so `bim_wall` and `bim_section` now sit with the other data tools ahead of `bim_opening`. Nothing in the suite depends on it.
- Not touched: `CHANGELOG.md` (left to avoid clashing with other patches). `FILES` is out of the patch and must gain `tests/_bim_before.py` and `tests/test_bim_data.py` or `tests/test_files.py` fails.
- `BASE = "b2d3dbd"` is pinned in the test; two of its four tests skip where that commit is not reachable.
