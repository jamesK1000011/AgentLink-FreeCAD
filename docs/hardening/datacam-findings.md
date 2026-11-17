# Tools as data: TechDraw (27 of 32); CAM not started (tags datatd / datacam, 2026-11-16)

Checkout `<work>/`. Base for this patch: local commit `9054d0f` (Mesh and Points as
data, on top of `99489bb`; made with `alcommit.sh`, privacy check passed, **not pushed**).
Patch: `<work>/datatd.patch` (`git diff 9054d0f`, new files included, FILES left out).
**FreeCAD did not run here**: everything below is proven on a stand-in.

## Where I stopped

Inside `agentlink/families/techdraw.py`, at a tool boundary, not at the end of the file:

- **Data (27):** td_page, td_title, td_view, td_bim, td_centermarks, td_hatch, td_weld, td_projection,
  td_section, td_detail, td_geometry, td_dim, td_dimset, td_tolerance, td_gdt, td_datum, td_note,
  td_balloon, td_table, td_leader, td_finish, td_area, td_dim_format, td_dim_special, td_dim_align,
  td_dim_repair, td_section_position.
- **Still handlers in techdraw.py (5), not because they cannot be data but because I ran out of room:**
  td_list, td_export, td_cosmetic, td_view_more, td_lines. They are the five most algorithmic of the
  family (57 to 120 lines each; cosmetic thread and centreline geometry, the view-kind switch, the
  cold-view warm-up, the sheet writer). They are unchanged, still registered with `Tool(...)`, and the
  module returns the data tools plus these five. The file is consistent and the suite passes with it
  so; `tests/_datatd_cases.py` lists them in `KEPT` with that reason.
- **CAM: not started.** `cam.py` and `cam_more.py` are untouched. **There is no `datacam.patch`.**
- **`points_structure` (std_more.py): not taken.** `surface_polynomial` left alone as told.
  `std_more.py` is untouched.

## Counts

- TechDraw handlers: 32. **Converted 27, all `steps`. Not converted 5 (above). Thin: 0.**
- `agentlink/data/tools.json`: 78 → 105 entries, appended at the end only (after my Mesh and Points
  entries), in the order converted.
- `techdraw.py`: 2952 → 2291 lines.
- **No change to `runners.py`, `expr.py`, `tooldata.py`.**
- Suite: 857 passed, 338 skipped, **1 failed: `tests/test_files.py`** — only because the local base
  commit tracks my four datamesh test files and FILES (kept out of the patches) does not list them.
  It passes once FILES gains them (see "on merge"). `scripts/tool_index.py --check` and
  `tool_summary.py --check`: current. All changed and new files compile with `python3.11`.

## What the entries hold, what the helpers hold

The 1200 lines of module helpers the family already had (`resolve_ref`, `frame_of`, `page_sheet`, …)
are unchanged and are now called by name. New named helpers, each with a docstring: `proxy_name`,
`try_set`, `setprop`, `own_prop`, `edge_on`, `weld_wrong`, `face_front`, `template_path`,
`clear_samples`, `axis_vector`, `section_frame`, `hide_cut`, `curve_name`, `figure`, `next_balloon`,
`anchor_at`, `one_dim`, `extent_dim`, `chamfer_angle`, `nearest_vertices`, `axo_angles`, `area_text`,
`without_prefix`, `with_decimals`, `more_decimals`, `prefixed`, and the sheet helpers (`sheet_find`,
`filled_bounds`, `range_corners`, `cell_name`, `range_text`).

Points to know:

- **`td_dimset` calls `td_dim`**: the handler called the other handler; the entry calls helper
  `one_dim`, which runs the `td_dim` entry (`runners.run_steps`). Same steps, same step count.
- **Shared helpers that still refuse in their own words** (finders and input readers used by many
  tools, as `mesh_of` is): `page_of`, `view_of`, `obj_of`, `dims_of`, `bodies_for`, `direction`,
  `place_xy`, `pt2`, `vec`, `resolve_ref`, `ref_point`, `paper_of3d`, `set_enum`, `apply_tol`
  ("fit: …", shared by td_dim and td_tolerance), `sheet_find`.
- GD&T, weld and finish wording errors come from `agentlink/gdt.py`: helpers `figure` / `weld_wrong`
  answer the words and the entry refuses with them (`"refuse": "=wrong"`), so the refusal is in its
  place in the order but its text is gdt's, as before.
- Today's fixes kept where they were: clockwise/first-angle order in `td_projection` (`face_front`
  before the other projections), the detail anchor (`anchor_at`), the special dimensions' re-read
  (`special_length`, `refresh_special`), arcs versus whole circles in `td_dim` (`whole_circles`,
  `arc_turn`), Agent Link's own notes not marking views touched (`own_prop`).

## Proof here

`tests/test_datatd_data.py` with `tests/_datatd_standin.py` (built on `_datamesh_standin.py`),
`_datatd_cases.py`, `_datatd_before.py`:

- identity of the 27 (name, description bytes, schema with key order, changes, reads, group) against
  the snapshot, and the snapshot against git `9054d0f` (techdraw.py is the same there and at `99489bb`);
- no handler or `Tool(...)` left for a converted tool; the five left are exactly `KEPT`; every name an
  entry calls is among the family's helpers;
- **268 cases**, old handler (from git) against new entry: result or refusal, every traced call in
  order, objects left. **0 differ**, no crash. 140 answer, 128 refuse.
- every `refuse` in the 27 entries is reached, except one listed in `UNREACHED`
  (`td_dim_special` "… could not be read.": the arc was read a few steps earlier).

The stand-in: a view is the body's box from the front with one hole (four lines, one circle), so
references resolve on real edges through the family's own `resolve_ref` / `frame_of`; `gdt`, `iso286`,
`cells`, the sheet finder and the presets files are real. Its circle reads as an arc to
`whole_circles`, so `td_dim` diameter is proven with the arc note, and `{ circle: { diameter } }`
as its refusal; the plain whole-circle path differs only by having no note.
`tests/_datamesh_standin.py` gained three small things for it (an extension point for object kinds,
`PropertiesList`, enumerations); the 330 Mesh and Points cases still match.

## The live model (`docs/hardening/models/asmtd-techdraw-model.json`, calls from 0)

Every converted tool is called:

td_page 4, 14, 28 · td_view 5, 29 · td_geometry 6, 30 · td_dim 7, 8, 16, 31–34 · td_dim_special 9, 10,
17, 37 · td_title 11, 12 · td_note 13 · td_projection 15 · td_tolerance 35 · td_dimset 36 ·
td_centermarks 38 · td_section 39 · td_section_position 40 · td_detail 41 · td_datum 42 · td_gdt 43,
44 · td_balloon 45 · td_leader 46 · td_finish 47 · td_weld 48 · td_hatch 50 · td_area 51 ·
td_dim_format 55 · td_dim_align 56 · td_dim_repair 57 · td_table 60.

**Converted but in no model call: `td_bim`** (needs a BIM section plane).

Still code, for reference: td_list 2, 3, 18, 64 · td_export 19, 65 · td_cosmetic 52 · td_lines 53, 54 ·
td_view_more 61–63.

CAM (`bimcam-cam-model.json`): nothing converted, so nothing to map.

## Risks

- **Not run on FreeCAD.** The stand-in proves order and words, not TechDraw: view geometry timing
  (`recompute` / `wait`), enumerations and what TechDraw refuses to measure are only imitated. Run the
  model on the Mac before trusting it.
- A mixed file: 27 data tools and 5 handlers share one helpers dict and closures. Nothing is
  duplicated, but whoever converts the last five should expect to add to the same `helpers` dict.
- Tool order in `tools/list` for the group changed: the data tools come first, then the five.
- `td_table` imported the sheet family at the top of the handler; now where it is used. A FreeCAD
  without the Spreadsheet family would have crashed before the page check and now after it.
- Long entries to read for whether they still read as the tool: `td_dim`, `td_dim_special`,
  `td_title`, `td_section`.
- The old-vs-new tests need git commit `9054d0f` (my local base) and numpy; without the commit 4 of
  the 7 skip. If the merge squashes or rebases that commit away, point `BASE` in
  `tests/test_datatd_data.py` at a commit that still has the 32 handlers (`99489bb` has the same
  techdraw.py).

## To do on merge (not in the patch)

- `FILES` must gain: `tests/_datamesh_before.py`, `_datamesh_cases.py`, `_datamesh_standin.py`,
  `test_datamesh_data.py` (from datamesh.patch) and `tests/_datatd_before.py`, `_datatd_cases.py`,
  `_datatd_standin.py`, `test_datatd_data.py`.
- `tools.json`: 27 entries appended after `points_export`; merge by key.
- `docs/data-tools.md`: one sentence added after the Mesh/Points one.
- `datatd.patch` also touches `tests/_datamesh_standin.py` (three additive hunks).

## Next, in order

1. The five left in techdraw.py: td_export and td_list first (smallest), then td_lines, td_view_more,
   td_cosmetic (per-kind helpers for the centreline and thread geometry; the refusals between them
   stay in the entry).
2. CAM: `cam.py` (12 tools) needs a Path stand-in (jobs, tool controllers, the 19 op modules, posts,
   tool bits, dressups); `cam_more.py` (cam_path, cam_property_bag, cam_template_export, and
   draft_fix, asm_rigid_group, asm_new_part) also needs Draft.heal and the Assembly finders.
3. `points_structure`, with its helpers in a separate dict as asked.
