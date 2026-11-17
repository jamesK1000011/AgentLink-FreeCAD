# Run 2 — the six models' answers, read one by one (16 Nov 2026)

Read: every answer in `out2/all-answers.json` against its model's `expect`: 364 model answers
(srm 119, srr 57, srt 64, srf 64, wsdoc 23, wsel 15) and the 22 helper answers (saves, reads).
Nothing here was run in FreeCAD: the fixes are proven by reading FreeCAD 1.1 source and by tests on
stand-ins, and every fixed tool is listed in `run2-marks.sh` as to be run again.

Counts: 13 tool bugs fixed (12 seen in the answers, A1–A12; 1 met while testing, A13), 13 answers
whose expectation was wrong or loose (7 causes), 6 things undecided. Everything else read right; where an
answer is right but tells too little, too much or something misleading it is under "Right, but".

Patches: `scanruler3.patch` (checkout sr3), `workshop3.patch` (checkout ws3). Marks: `run2-marks.sh`.

---

## A. Tool bugs (fixed, with tests)

### A1. ScanRuler's state was the session's, not the document's (the known item A)
- Seen: srt call 7 `scan_open` refused "WornScan is open with 9 elements…" in a new document; srf call 1
  `flat_edges` answered a section sheet in a new document (expected: refused); and, not known before:
  the helper `doc_save` after srr call 4 wrote **6,017,729 bytes for a document holding one block**
  (ScanMeshModel 3.9 MB with a 12-triangle scan, ScanFlatModel 3.2 MB with a 300-triangle one) — the
  measure document's whole state (the dense WornScan, its elements, the deviation reference) was
  **written into the other documents' files**; srr call 52 shows a body labelled "Block001" because
  the leaked reference mesh "Block" had taken the label; srr call 50 counts 10 objects where the
  reverse model made 6.
- Cause: Agent Link's `doc_new`, `doc_open`, `doc_close` set `session.doc` and leave
  `session.family_state` (hub: `agentlink/families/doc.py` `switch`; only `Session.switch`, used by
  doc_switch and revert, empties it). `scanstate.state` handed out `family_state["scanruler"]`
  whatever the document, and `docstate.mark` wrote it into `session.doc` — the new one. The manifest's
  "doc_open empties the session's family state" is not so.
- Fix (ScanRuler only; the hub is not touched): `scanstate.settle(session)` runs before any state is
  handed out and before any write. When the session's document is not the one the state belongs to,
  the state is written into its own document (if still open, on the document's thread), set aside
  under that document, and the new document's own state is taken from where it was set aside, else
  read from the document (`docstate.read`), else starts empty. One Python object per open document
  (FreeCAD 1.1 source: `src/App/Document.cpp`, `DocumentPythonObject`), so a document closed and
  another made under the same name is not mistaken for it; a closed document's state is let go.
  `docstate.mark_doc(doc, st)` writes a given state into a given document, and `scanstate.touched`
  binds both when the call ends, so a write handed to the GUI thread (the job-thread rule, unchanged)
  still lands in its own document if the session has moved on.
- Tests: `tests/test_freecad_owned.py` `StatePerDocument` (7): a new document has no scan, no sheet
  and gets nothing written; switching back gives the very state; what a job left unwritten is written
  into its own document on leaving; a queued GUI-thread write lands in its own document; same name
  reopened; closed document let go; `mark` never writes across.
- Not covered: the reverse build's scan context (`reverse/scan_context.py`) asks the session that
  last edited a document for its scan; with the fix it gets the state of the document that session
  is in at that moment. Not seen live; left.

### A2. scan_scale took a datum alignment off, one call late (the known item C)
- Seen: srm calls 100–102. After align_auto + align_symmetry, `scan_scale { factor: 2 }` answered the
  box −60…60 (aligned, right); `scan_scale { factor: 0.5 }` answered 0…60 (scan coordinates: the
  alignment gone); `align_clear` was then refused "in scan coordinates already".
- Verdict: **the model is right, the tool was wrong.** scan_scale's and align_clear's descriptions
  say a scale drops the *deviation* alignment only and "a scan_scale stays" under align_clear.
- Cause: `docstate.attach_scan` wrote the scan object's Placement and then its new, scaled mesh. A
  `Mesh::Feature` given a new mesh takes that mesh's placement (none) as its own (FreeCAD 1.1 source:
  `src/Mod/Mesh/App/MeshFeature.cpp`, `Feature::onChanged`). The object stood at the origin; the next
  ScanRuler call read that as a move made by the person (`pull_pose`) and undid the alignment — on
  the scan and on every element.
- Fix: the mesh first, then the Placement. Test: `test_a_scale_keeps_the_alignment` (the stand-in
  document now resets Placement on a new mesh as FreeCAD does). scan_scale's description now says the
  datum alignment stays.

### A3. thickness_measure: 221 s (the known item B)
- The ray casting was already numpy, not a Python loop. The cost was the search: rays went in runs
  of 256 (neighbours along a Morton curve of their origins), each run tried against every leaf of 16
  triangles whose box met the box the run's 25 mm segments swept, and the leaves cut along a Morton
  curve have loose boxes. Measured here on a 218,700-triangle 60 × 40 × 20 block, 20,000 rays of
  25 mm: 2,700 leaves a run on average (6,300 at most, of 13,669), opened eight at a time — about
  280 rounds of numpy per run. 66 s here; 221 s on the Mac.
- Fix: `NominalSurface.raycast_first` walks every ray through a uniform grid of cells together, a
  cell a round (3D DDA): only the triangles whose boxes reach the cell are tried, a hit counts once
  it lies inside the cell walked. Cells are sized by the median triangle; up to 128 very large
  triangles are kept out of the grid and tried directly. The old search is kept as
  `raycast_first_leaves` for the tests.
- Speed, measured here: thickness 66 s → 0.36 s (about 180×); scan_qa on the same mesh 7.3 s → 1.7 s
  (its thickness reading and its ray grid use the same call); scan_heightmap uses it too. Expect the
  Mac's 221 s to come down to a few seconds at most — **not measured on the Mac**.
- Answers: on the benchmark the thickness array is bit-identical. Against the old search on seven
  meshes × six ray sets (inward, outward, unbounded, axis, random, non-unit): the same rays hit;
  the distance equal except where a ray passes through an edge two triangles share (differences up
  to 1.6e-13 mm: t read off either triangle); the face differs only in those ties, where the old
  choice depended on the order leaves were opened and the new one is the lowest index.
- deviation_measure: its search (`NominalSurface.closest`) is numpy, best-first over leaves: 2.4 s
  here for 109,000 scan points against a 588-triangle reference, 2.9 s for 50,000 points against
  219,000 triangles. Not changed.
- Tests: `tests/test_thickness_maths.py` `Speed` (grid against leaves, inward rays on four meshes,
  a large triangle among small ones, the live case under 20 s with the same numbers).

### A4. mesh_reduce gave a wrecked mesh, and mesh_apply_reduced applied it without a word
- Seen: srt call 39 `mesh_reduce { tolerance: 0.05, maxTriangles: 2000 }`: 2,136 triangles (over the
  cap), max 14.27 mm, rms 5.33 mm, held false. Call 42 `mesh_apply_reduced` made it the edited copy:
  volume 8,829.6 mm³ where it was 22,429.2, bounds −3.76…42.84. Calls 44–47 then exported and used it.
- Cause: `Mesh.decimate(tolerance, 1.0)`. FreeCAD's tolerance is not a bound in millimetres: it only
  stops the simplifier once no triangle's quadric error is under it, and a flat face's is 0, so with
  reduction 1.0 (target 0 triangles) it runs its 100 passes with a growing threshold (FreeCAD 1.1
  source: `src/Mod/Mesh/App/Core/Simplify.h` `simplify_mesh`, `Decimation.cpp`). The old description
  called this a "trap"; in fact the call could not hold a tolerance on any part with a flat face.
- Fix: the count form `decimate(targetSize)` is used and the count searched
  (`mesh_core.lightest_within`): a quarter at a time while the measured deviation holds (99.9 % of
  4,000 sampled points within tolerance both ways), then four bisections; the cap first, and when the
  cap cannot hold the tolerance the reply says so (`capped`, `held: false`, `warning`). A count
  FreeCAD stops above is asked again lower, so the cap is kept. When nothing lighter holds, the mesh
  as it is, with a `note`. `mesh_apply_reduced` adds a `warning` when the reduction did not hold.
  The distance checks use `NominalSurface.closest` instead of a Python loop per point.
- Tests: `tests/test_meshtools_added.py` `Reduce` (the search; the handler on a stand-in decimator
  that behaves as the source reads). **FreeCAD's decimator itself was not run**: live re-run needed
  (how many tries, the time, whether a decimated closed mesh stays closed).

### A5. manual_check: two bodies in the same place read "blocked 19.25 mm short"
- Seen: srm call 114; expected `overlapsInPlace`. The sweep ran from far to near and stopped at the
  first contact, so a part that overlaps where it sits always read as blocked on the way.
- Fix: the place is read first (`manual_core.way_in`): overlapsInPlace, and the way in not swept;
  else blocked or clear as before. Tests: `tests/test_manual.py` `WayIn`.

### A6. align_symmetry settled on a plane that is not a mirror of the whole part, and did not say
- Seen: srm call 98. It used the element Mirror (call 28: the z 10 plane, 3,968 of 4,000 samples
  matched, hidden since call 44) and moved the zero point 10 mm in z; note: "mirror RMS 0.0000 mm".
- Fix: the reply carries `symmetry { rms, matchedShare, from }`, and the note says what share of the
  samples has no mirror image and how to make the plane meant. (The expectation — Y, 0 mm — is also
  wrong for the Mac: see B.) Description updated.

### A7. Reverse engineer: a body's box was its triangulation's, not its own
- Seen: every `bodies[].box` in srr: Block −1.0000000355e-07…40.0000001; after the bore z −0.0365…
  20.0365; Ring x −15.109…15.109 (radius 15). `optimalBoundingBox()` reads the triangulation once the
  shape has one (a body shown in the view has), grown by its deflection (FreeCAD 1.1 source:
  `src/Mod/Part/App/TopoShapePyImp.cpp`, `BRepBndLib::AddOptimal`).
- Fix: `optimalBoundingBox(False, False)` (off the geometry) for a body of up to 400 faces, the old
  reading above that; coordinates rounded to 1e-7; volumes in body rows to 1e-6
  (999.9999999999998 → 1000). Not timed in FreeCAD. `reverse_body_describe`'s face and edge rows
  keep their raw numbers (they are fingerprints an agent may pass back; matching is by tolerance).

### A8. reverse_body_check answered the other name
- Seen: srr call 33 `{ body: "Dowel" }` → `name: "Peg"`. Fix: `shownAs: "Dowel"` beside it.

### A9. wear_prewarp: "the print is within 0.05 mm RMS of the target" with a 1 mm pocket in it
- Seen: srm call 86: rms 0.0, largest 0.0, stop true. The error is read at the target's own vertices,
  and the target (Block's CAD tessellation, 648 triangles) has none in the middle of its top face.
- Fix: the same error read from the print's points (`seenFromPrint`); when they lie further off than
  the tolerance and than three times anything the target's vertices show: `warning`, `stop: false`.
  Tests: `tests/test_wear.py`. Description updated.

### A10. patent_figures: numerals named by the object's name were "not among the bodies drawn"
- Seen: wsdoc call 12 `{ bodies: ["Body"], numerals: { Body: 0 } }` → not_found "Body is not among the
  bodies drawn — Tut" (expected invalid_input: a whole number over 0). `bodies` takes an object's
  name; `numerals` went by label only.
- Fix: a numeral's key is a label or an object name (`_numerals`); the same body named twice is
  refused; `true` is not a number. Test in `tests/documents/test_drawing_page_dims.py`.

### A11. patent_figures: every figure's files came from Workshop's sheet writer, wrongly
- Seen: wsdoc call 10: filesFrom "Workshop's sheet writer: TechDraw left the template out of its
  export (no frame or title block in it)" for both figures. The pages are on TechDraw's blank
  template, which has no frame or title block to find: `template_in_svg` looked for a title block's
  words and found none.
- Fix: a template with no editable texts and none of the words in its own file has nothing to be
  left out. Test in `tests/documents/test_drawing_sheet_fit.py`. Live re-run needed (the page's own
  SVG and PDF were never used for a patent figure before).

### A12. drawing_make left its page's template and dimensions marked as changed
- Seen: wsdoc call 5 (the call after the section drawing): health "6 objects not recomputed yet …
  Template001, Dimension003 … Dimension007", todo "recompute". The shared health check leaves out
  what the call itself changed (hub `health.py`), so each drawing's leftovers show one call late.
- Fix: after the export, what on the page is still marked changed and is not a view of a part is
  recomputed once (`td_wait.settle_page`); a part view is left alone (recomputing one starts its
  lines afresh). Test in `tests/documents/test_drawing_views_ready.py`.
- **Not proven**: what marks them was not found in the code (the first drawing, call 2, left none
  that call 4's own recompute did not clear). If the mark comes after the call returns (TechDraw's
  section cut finishing on its thread), this does not catch it. Re-run and read the next call's health.

### A13. align_datum { primary: "Top" } failed with "AttributeError: 'str' object has no attribute 'get'"
- Met while writing A2's test (an existing test made this call and did not look at the answer).
  Now refused (invalid_input) with the shapes a slot takes.

---

## B. Wrong or loose expectations (the tool is right)

| Model call | Expectation | Answer | Why the expectation is wrong |
|---|---|---|---|
| srm 10 scan_qa | thickness p50 20 (p5 19) | p50 20.048, p5 14.05, axis tilted 4° | on the 608-triangle mesh the axis is read off few large triangles; the answer says sparse and to densify. After densifying (call 16): 20 / 19 / 20, tilt 0 |
| srm 16 scan_qa | spacing about 0.37 | 0.292 | the figure of the numpy-built mesh (137,000 triangles); the Mac's has 219,600 |
| srm 69 scan_cloud | about 68,000 points | 109,800 | same |
| srm 74 deviation_align | matchedShare over 0.98 | 0.914 | the fit cuts pairs further than 3 × the median distance, floor 1e-5 of the diagonal (0.00075 mm): on an exact CAD scan the bore polygon's 0.001 mm and the pocket fall outside. rms 0.0002, identity transform, no warning: right |
| srm 76, 79 | withinTolerancePct about 99.2 | 99.5 | same mesh difference |
| srm 98 align_symmetry | Y turned 0°, moved 0 | Z, moved 10 mm in z | follows from call 28's answer on the Mac (the mid-height plane), which the model itself allows. The model should build the mirror with `seed: "XZ"` at call 28 if it wants Y. (The tool's silence about the 0.8 % is A6.) |
| srt 39, 40 | inputTriangles / edited.triangles about 8,800 | 10,022 | the subtract's and fill's triangle counts on the Mac's mesher |
| wsdoc 0, 1 | the TechDraw tutorial file, one Body, two pages | PartDesignTutorial, 13 bodies | the run opened another file (the manifest's substitution); the body is the object "Body", labelled "Tut", so every later answer names "Tut" where the model says "Body" (calls 10, 13, 16, 17, 19) |
| wsdoc 22 history_undo | takes back the Base plate or a page | undid "drawing_exploded", nothing gone | drawing_exploded outside an Assembly adds nothing but is one (empty) undo step; see C3 |
| wsel 6 printed_channel | a channel in the enclosure's floor, or refused | refused "cut nothing" | the run file's path (y −19) lies outside the 56 × 36 box (y −18…18): right, and the model accepts it — but a channel inside an enclosure is **not proven** by this run |

srm 102 (align_clear) and srf 1 (flat_edges), the two the script flagged, are tool bugs: A2 and A1.

---

## C. Undecided

1. **Every changing ScanRuler call costs 1.2–1.6 s once the scan is dense** (srm: `dimension_remove`
   1,573 ms, `element_rename` 1,500, `element_set_visible` 3,947; before densifying the same calls
   take tens of ms; about 310 ms a call in the flat model). After each call the whole state is
   packed again (arrays compressed) and copied into the document. Packing takes 0.3 s here for a
   comparable state; the rest (FreeCAD's file copy, the health check) is not measured. A1 removes
   the cost from documents the state does not belong to. Writing only what changed would be a
   redesign: not done.
2. **wsdoc call 4 (drawing_make with a section) carries no `health`** though it changes the
   document; calls 2 and 5 do. Hub side or a time budget: not found.
3. **An empty undo step.** drawing_exploded is declared `changes: true` (it adds an Exploded View
   when the bodies are in an Assembly) and adds nothing otherwise; the hub still commits a step. The
   description now says so. A step that changed nothing could be dropped by the hub.
4. **srr call 56 history_undo of the clear**: nothing after it reads the bodies back; the answer's
   own `bodies` lists FreeCAD bodies only. Unproven either way.
5. **srm call 53 section_fit**: chain 0 reads scatter 0.0469 mm on four exact straight lines (points
   0.9375 mm apart). The fit is right (rms 0, corners exact); what "scatter" measures there was not
   read.
6. **Hub, seen in passing**: `doc_close` (srr 49) lists "ScanMeasureModel" twice under `open` (two
   documents of one label, the manifest's warning); the helper `session_state` in wsdoc answered
   null in the file; `health.next` reads "workbench TechDrawWorkbench" after kicad_import (wsel 1).

---

## D. Right, but…

Too little
- `align_clear` (srm 95) answers `appliedAlignment: null, elements` — not the box the agent then
  needs (`scan_info` gives it).
- `kicad_import` (wsel 1) does not give the board's volume (the model wanted 2365.9 ± 1); health says
  valid and closed.
- `thickness_measure` (srm 71) is in the file only as the runner's note of its job (min 10.0, max
  24.848, mean 18.897, 16,647 of 20,000 measured): right against the expectation, but its own reply
  was not kept.

Too much
- `flat_dimension_add` (srf 24–28, 56) answers the whole 2D state and the whole report text each
  time (2.2 → 2.7 kB, growing with every element); the new dimension is the last row of
  `flat.dimensions`. `flat_edit`, `flat_remove`, `flat_set_alignment` likewise answer the whole state.
- `element_construct { method: "plane-symmetry" }` (srm 28) carries its note twice (`element.note`
  and `symmetry.note`).
- Mesh Tools rows carry unrounded numbers (`largestIsland 3.4641019298095532`, `maxMove
  1.7320508075688772`) and `-0.0` in bounds.

Misleading
- `thickness_settings { limit: 12 }` (srm 72): `stats.belowLimit 21` beside `thinSpots.count 119`.
  Both right — the statistics are of the 16,647 measured points, the patches count every scan point
  with the reading it took from a neighbour — but they read as a contradiction. thickness_measure's
  description now says so.
- A shadow section (srm 57) answers `offset: 10.0`, which means nothing for a shadow.
- `scan_snapshot_wait` (srm 118) was called with `timeout` and its `next` names `timeoutSeconds`:
  the same input under its other name (the schema takes both).
- `mesh_reduce`'s `capped: true` with 2,136 triangles for a cap of 2,000 (A4 fixes the count).

Read and right, worth saying
- srm: the dimensions (20.000 in band, bore 11.9985, −20.000, 1.000 with the no-overlap warning,
  flatness 0, 90.00°, angularity 1.047 mm at basic 89), the sections (200.0 and 37.696; four lines
  and one arc at the corners and [20, 20, 10]), section_to_sketch → pd_pad 11,434.65, the heightmaps,
  outline, hotspot (one patch, 112.9 mm², −1.0), deviation_volume (excess 93.0 mm³ of the 100),
  wear_diff −1.0 and wear_rebuild, fit_scan (scale 1.000, hole 0.0007), align_datum (−20 in x, the
  datums own y), the refusals' words, catalog, pack (zip with six files, 608.step left out),
  manual_render.
- srr: every volume to the digit (24,000; 12,000; 22,429.20; 22,274.69; 1,000; 480.69 overlap;
  1,963.50; 23,845.49 with the rounds found again by fingerprint), ids and order, the fillet by
  fingerprints (the route the manifest could not try), save / close / open / recompute with no body
  empty.
- srt: densify 8,192, cut 18,000, boolean −1,570.6, islands, offset 28,462, mirror, flip, delete and
  fill (22,429.4 back), smooth, trim 499.0 / mating 100.0, shell 9,049.1, wrap 24,000.0 and 29,467.8,
  every undo.
- srf: the section sheet after densifying (140.0 and 31.4057), fits, dimensions (30.000, 20.000,
  90.00°, 25.000), alignment (Corner 0, 30; bore centre 20, 15), exports, the image (6 chains,
  objects 201.08 and 60.0 mm²), calibration ×2 with the note carried to [8, 52].
- wsdoc: drawing_make (A3, 2:1, four views, three extents with 53.00; the section B-B with the two
  hole callouts; files-only), the seven refusals, patent_draft, drawing_exploded's manual and BOM,
  library_pack and its two licence refusals.
- wsel: kicad_import (50 × 30 × 1.6, three holes, J1 and C1 tall, moved [−125, 115]),
  board_enclosure (56 × 36 × 21.6, M3 standoffs, the J1 opening), the parametric-object refusal with
  its way out, the channel (46.14 mm, 4,406 Ω of filament, awg 22 fits), awg said before the cut,
  pcb_order_package.

---

## E. What the patches change

scanruler3.patch (ScanRuler-FreeCAD, sr3)
- `scanrulerfc/scanstate.py`, `docstate.py`: A1, A2.
- `scanrulerfc/dev_surface.py`: A3.
- `scanrulerfc/mesh_core.py`, `handlers/meshtools.py`: A4.
- `scanrulerfc/manual_core.py`, `handlers/manual.py`: A5.
- `scanrulerfc/model.py`: A6, A13.
- `scanrulerfc/reverse/kernel.py`, `reverse/handlers.py`: A7, A8.
- `scanrulerfc/wear_core.py`, `handlers/wear.py`: A9.
- `scanrulerfc/data/tools.json`: descriptions of mesh_reduce, mesh_apply_reduced, align_symmetry,
  manual_check, scan_scale, reverse_body_check, reverse_body_names, thickness_measure, scan_qa,
  wear_prewarp. No tool renamed, no input removed. Credits to Stefan Hermann / CNC Kitchen untouched.
- Tests: `tests/test_freecad_owned.py`, `test_thickness_maths.py`, `test_meshtools_added.py`,
  `test_manual.py`, `test_wear.py`, `fakedoc.py` (a Mesh::Feature's Placement follows a new mesh).

workshop3.patch (Workshop-FreeCAD, ws3)
- `workshop_documents/handlers/drawing.py`, `td_wait.py`: A10, A11, A12.
- `workshop_documents/data/tools.json`: patent_figures (numerals by label or object name),
  drawing_exploded (the empty undo step).
- Tests in `tests/documents/`.

Tests here: ScanRuler file by file with Agent Link importable — all pass except
`test_flat_sheet.py` (1) and `test_heightmap.py::test_tiers`, which fail the same way without the
patch (they need Agent Link's renderer, which needs FreeCAD). Workshop per folder: all pass.
Every changed file compiles with Python 3.11. FILES is not touched (no file added).
