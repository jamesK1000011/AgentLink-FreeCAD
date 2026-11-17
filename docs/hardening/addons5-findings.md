# Add-ons, pass 5: the four items from run 3 (16 Nov 2026)

Checkouts: ScanRuler-FreeCAD `sr5` at 9ac74d9, Workshop `ws5` at 18489e6. Patches: `scanruler5.patch`
(14 files) and `workshop5.patch` (6 files); both apply clean on those commits, no file added, FILES not
touched, nothing committed or pushed. The hub was read only.

Credit: the ScanRuler tools are Stefan Hermann's (CNC Kitchen) ScanRuler features, ported; every credit
line in the files stands.

Nothing here ran in FreeCAD. "Source" is FreeCAD's source as checked out (tag 1.1.0; the Mac runs 1.1.3).
"Tested" is plain Python on stand-ins. "Replay" is the measure model's ScanRuler calls run through the
add-on's own runner on a stand-in document with a 218,700-triangle box as the scan.

`sr5` held an earlier agent's uncommitted work on items 1 and 4 and a `timing` field. I read it against the
source and the live answers, kept it, and added to it: `timing` had no test and no word in any description;
item 4's second fix depended on a margin I could not show was wide enough; item 3 and all of item 2 were
not started.

Tests after the patches, with the hub importable. ScanRuler, the whole suite on the final tree: 1,067
passed, 138 skipped; one more fails exactly as it does without the patch and was left out of that run
(`test_tool_names.py::NoClash`: it looks for `snapshot_latest` in the hub's source, which this hub no
longer has there). Workshop per folder: documents 114, electronics 18, fasteners 15,
make 120, parts 17, safetynet 118, top level 62, none failing. Workshop's two changed test files also pass
under Python 3.11; ScanRuler's changed files compile under 3.11 (no numpy for 3.11 here, so its tests ran
on 3.13 only).

---

## 1. mesh_reduce: the cap not kept, the search not run, the warning untrue — fixed (tested, not live)

**Cause, three parts.**

- *The cap.* FreeCAD's decimator does not promise the count. `MeshPy::decimate`
  (`src/Mod/Mesh/App/MeshPyImp.cpp`) has two forms, `decimate(tolerance, reduction)` and
  `decimate(targetSize)`; both end in the same loop, `Simplify::simplify_mesh`
  (`src/Mod/Mesh/App/Core/Simplify.h`, called from `Core/Decimation.cpp`). The loop makes a hundred rounds
  at most (`for (int iteration=0;iteration<100;++iteration)`), never joins a rim vertex to an inner one
  (`v0.border != v1.border`) and never makes a collapse that would turn a triangle over (`flipped`). So a
  mesh has a count the loop will not go under. The handler's answer to that was to ask again for *less*,
  three times. That cannot help: the count only says when to stop, so every lower count walks the same
  collapses to the same mesh. Live: 2,142 each time.
- *The search.* `lightest_within` returned at once when the try at the cap did not hold the tolerance
  (`tries: 1`). Nothing looked for a count that would hold.
- *The words.* The warning was a fixed sentence with the cap in it, whatever `triangles` said.

A fourth fault showed in the same answer: `backMax 0.0099` on a mesh that had lost a quarter of its volume.
The way back was read at the reduced mesh's vertices only, and a triangle that cuts a corner off has all
three vertices on the original.

**Which decimate form.** `decimate(targetSize)`. The other form holds no tolerance in millimetres either:
its tolerance is only a reason to stop early, in the quadric's squared units, and a flat face's error is
always 0, so with `reduction` 1.0 it goes on to almost nothing (that was run 2's fault). The tolerance in
millimetres is held by measuring each try both ways, as before.

**Fix** (`scanrulerfc/mesh_core.py` `reduction_search`, `reduce_words`, `reduce_applied_words`;
`scanrulerfc/handlers/meshtools.py`).

- A try that stops above the count asked is run again *on what it left* (the rounds and the error measure
  start afresh), up to 6 runs, until one takes nothing off. `passes` says how many.
- Over the cap, the try at the cap comes first, then one of four outcomes, named in `won`:
  - `both`: at or under the cap and within tolerance; the search goes on down for the lightest.
  - `cap`: the cap is met and the tolerance is not. That mesh is the reply (`capped: true`,
    `held: false`). The search then climbs between the cap and the mesh as it is for the smallest count
    that holds (the gap halved each try, 8 tries, 30 s for the whole search): `holds { asked, triangles,
    passes, p999, max, backP999, backMax }`, `notHolding` the largest count tried that did not.
  - `tolerance`, `capMet: false`: the decimator stayed above the cap. `atCap` is what it left there (the
    true count and the measured deviation). The reply is the lightest mesh found that holds the tolerance,
    over the cap; or that try itself when it holds; or the mesh as it is.
  - `null`: the mesh was under the cap to begin with.
- `search { tries, ms, ended ("done" | "time"), seconds }`. A search cut short by the clock says so and
  keeps what it had.
- The way back is read at the vertices and at the middles of the triangles.
- The warning is built from the report: every count and distance in it is a figure of the reply (a test
  checks this by reading the numbers out of the sentence). `mesh_apply_reduced` warns from the same
  figures: over the cap and why, or not holding the tolerance and what count would.
- Both descriptions and `guides/mesh-tools.md` say all of this; nothing was shortened.

**Tests** (`tests/test_meshtools_added.py`, 19 on reduction): the search alone (both hold; the cap wins and
the holding count is found; the cap cannot be met; stopped above the cap where it holds; nothing lighter
holds; a decimator that gives nothing back; the clock ends it), and the tool on a decimator that stops
where the source says it can, including the live call again (asked 2,000, stops at about 2,142, a run on
its own result takes nothing off, 10 mm out below 2,500): `capMet false`, `won "tolerance"`, `held true`,
`atCap` with the true count, `tries` over 1, the warning's figures all in the report, and the same from
`mesh_apply_reduced`.

**Live.** Mesh Tools model, the `mesh_reduce { tolerance: 0.05, maxTriangles: 2000 }` call (srt 41) and
`mesh_apply_reduced` (srt 44). Expect one of two answers; the model's `expect` says how to tell them:

- (a) `capMet: false`, `won: "tolerance"`, `atCap { asked 2000, triangles about 2,142, passes 2–6, max
  about 10 }`, the reply held (`p999` and `backP999` at most 0.05), `triangles` over 2,000, warning
  starting "maxTriangles 2000 could not be met". After apply: volume within a few mm³ of 22,429.
- (b) `capMet: true`, `won: "cap"`, `triangles` at most 2,000, `held: false`, `holds { triangles }`,
  warning starting "The cap won over the tolerance".

**Not proven.** Whether a second run of FreeCAD's decimator on its own result gets under 2,000 on this
mesh (it decides between (a) and (b)); the time (a job answers no `ms`; `search.ms` now does); that a mesh
the decimator returns stays closed.

---

## 2. drawing_make 0.8 → 4.6–5.7 s, patent_figures 1.2 → 6.6 s — the split is in the answer; two repeats cut; the cause is not the wait alone, and is not proven

**What the code costs, by reading it.** One drawing with a page does, in order: Workshop's own projection
and layout; the TechDraw page (views, `doc.recompute()`, a wait for the views' lines, the dimensions, a
second look at the views); the export (a third look at the views, DXF, the page's tab shown and painted,
SVG, the SVG read back, PDF); the wait after the export.

- *The wait after the export* (0.95 and 1.49 s live) cannot be left out while the PDF is TechDraw's own.
  `PagePrinter::printPdf` ends with `dPage->redrawCommand()` (`src/Mod/TechDraw/Gui/PagePrinter.cpp`),
  which forces a redraw whatever the page's KeepUpdated says (`DrawPage::redrawCommand`: `forceRedraw(true);
  updateAllViews()`, `src/Mod/TechDraw/App/DrawPage.cpp`). Every part view works its lines out again on a
  thread, and the dimensions are recomputed when the faces are done (`DrawViewPart::postFaceExtractionTasks`).
  So the wait is about one more "views ready": it was 0.83 and 1.45 times `viewsReadyIn` live. That part of
  the cost is the price of the proven result.
- *The observer* is two Python slots, called once per property write or recompute in that document while
  the export and the wait run. Tens of calls, not seconds. `settled.seen` now counts them.
- *Repeats.* Two were real and are cut (below). Neither is seconds.
- *The echo opening the page tab* is the tool's own `page_scene_ready`, needed for the export to hold the
  views (proven in an earlier run); it is now timed as `export.scene`. The hub's echo before the call
  (1,829 ms on wsdoc 4) is outside the tool and outside this add-on.

**What the live numbers say.** The wait does not explain the rise, and neither does anything else in the
tool's code, which is run 2's code plus the wait:

| | run 2 | run 3 |
|---|---|---|
| wsdoc 4 `page.viewsReadyIn` (before any watch is on) | 0.20 s | 1.15 s |
| wsdoc 6 `page.viewsReadyIn` | 0.24 s | 1.03 s |
| wsdoc 4 whole call less the wait | 784 ms | 3,699 ms (×4.7) |
| wsdoc 6 whole call less the wait | 839 ms | 4,217 ms (×5.0) |
| wsdoc 0 `doc_open` | 474 ms | 2,234 ms (×4.7) |
| wsdoc 2, 14 `doc_save` (a small document) | 75, 70 ms | 444, 367 ms (×5.9, ×5.2) |

The same code took about five times as long in every part, and so did two hub tools that Workshop has no
hand in. Part of the small calls' rise is the hub's new share (wsdoc 18 `part_primitive`: 240 ms, of which
tool 50 as in run 2 and healthMark + snapshot + health 190). For `drawing_make` the hub's share is 272 of
4,649 ms, so that is not it. `patent_figures` also does more than in run 2: its SVG check failed there, so
no PDF was exported at all (A11 fixed that); each figure now pays a PDF export and its redraw.

So the honest reading: about 1–1.5 s a drawing is the wait, and the rest is something that made TechDraw's
own work and FreeCAD's saves about five times slower in that session. I could not find it by reading. Section
3 has the same factor on `doc_save`.

**Fix** (`workshop_documents/td_wait.py`, `workshop_documents/handlers/drawing.py`).

- The answer carries the split, in ms. `drawing_make`: `timing { sheet, page, export { wait, dxf, scene,
  svg, check, pdf }, settle, turns, turnMs, total }`. `patent_figures`: the same on every figure's row and
  `timing { figures, turns, turnMs, total }` on the reply.
- `page.settled` gains `exportMs` (the export as timed round it), `turns` and `turnMs` (the event loop's
  turns during the wait and the time inside them) and `seen { changed, recomputed }`.
- Every turn of the event loop run from this module is counted and timed (`turns_now`, `turns_since`).
  A turn runs whatever the window has waiting. `turnMs ÷ turns` is what one turn cost: that is the number
  that tells a slow window from a slow drawing.
- Cut: the three turns that draw the window's scene are no longer run by the second look at the views
  (dimensions go on geometry, not on the picture) nor by the look before the export (`page_scene_ready`
  readies the scene straight after with five turns of its own). That is 6 turns fewer a drawing, 3 a figure.
- Cut: the exported SVG was read back and every path in it counted twice; now once (again only if the file
  is written again).
- Unchanged: the wait after the export, what it clears, and when it gives up. `page.settled.cleared` is
  made exactly as before.

**One risk I took.** The look before the export used to run three turns before the tab was shown. If the
scene on the Mac needed those as well as `page_scene_ready`'s five, the SVG check fails, the export is made
again after eight more turns (as before), and the answer shows `exportSceneAgain`. So the result holds
either way, at the cost of a second export. Tell me if `exportSceneAgain` appears.

**Tests** (`tests/documents/test_drawing_views_ready.py`, `WhereTheTimeGoes`, 6): a wait that only asks
runs no turn when the views are ready and still waits for late lines; turns are counted and timed;
`settled` carries `exportMs`, `turns`, `turnMs`, `seen` with the page left unmarked as before; the export's
split has its six parts and reads the SVG once (twice when written again); a stand-in wait that knows no
`draw` still works; the shape of `timing`. The existing `PageSettled` tests (9) pass unchanged but for one
equality that now includes `exportMs`. `test_drawing.py` asserts `timing` end to end; it is skipped here
(it needs FreeCAD) and **has never run**.

**Live.** Documents model calls wsdoc 4, 6, 12, then 7 and 18 for the health line. Send `timing`,
`page.settled`, the call's `ms` and its `around` row whole. Expect:

- `page.settled.cleared` as in run 3 (template and three dimensions; template001 and five), no `late`, no
  `left`; wsdoc 7 "nothing red"; wsdoc 18 no needRecompute.
- `sheet + page + export.* + settle` within a few tens of ms of `total`.
- Then read where it went. If `turnMs ÷ turns` is tens of ms or more, the window is slow to turn and the
  cost is outside the drawing. If `export.svg` or `export.pdf` or `export.scene` carry it, it is TechDraw's
  painting. If `page` carries it with `viewsReadyIn` near 1 s again, it is the views' lines themselves.

**Not proven.** That anything here makes the Mac's drawings faster by more than the six turns: if a turn
costs 5 ms that is 30 ms. The split is what this pass delivers for item 2, not a speed-up.

---

## 3. doc_save / pack_write 2.4–2.7 s after scan_scale — one real leftover found and fixed; it is not what costs 2 s; the 2 s are explained only in part

**What the 2.8 s `afterChange` is.** Not ScanRuler. `around.inside.afterChange` is the hub's
`hooks.emit("after_change")` (`agentlink/tools.py`), and its one heavy listener is SafetyNet's auto-save:
`safetynet/autosave.py` `after_change` → `copy_now` → `d.saveCopy(f)`, due 10 changes after the last. So
srm 106's 2,811 ms, srm 108's `doc_save` 2,740 ms and (probably, see below) srm 118 are one thing three
times: a FreeCAD save of that document cost 2.4–2.8 s after the scale and 0.5 s before it. ScanRuler's own
write of its state is inside the tool's `ms`, not in `afterChange`.

**What scan_scale leaves in ScanRuler's state: looked for, by replay.**

- The packed-array cache is not thrown away. After `scan_scale` 6 of 56 arrays were packed again (the pose
  and the fits), 45–62 ms a write.
- The scan is not kept twice. Its points live in the mesh object; the state holds `k`, `R`, `t`.
- **One leftover was real.** The wall-thickness reading keeps `V`, the scan's own point array as it stood
  when the reading was taken, only to tell whether the scan has moved since
  (`handlers/thickness.py`, `tstate`). The state's encoder wrote that marker out as an array like any other:
  every vertex a second time, 2.6 MB raw at 109,800 vertices, and after a scale or an alignment the *old*
  points beside the moved scan, until the next thickness call noticed. It was also useless once read back:
  a copy is never the scan's own array, so every reopened document silently lost its thickness map.

**Fix** (`scanrulerfc/docstate.py`, `POSE_KEY`). The marker is written as what it says (`{"__pose__":
true | false}`) and comes back as the scan's own array or as an empty one. Replay: the state file 1,699,509
→ 1,391,011 bytes, a write after `scan_scale` 45–62 → 23–25 ms. A thickness map now survives save and
reopen; one taken before a move is still dropped. `thickness_measure`'s and `scan_scale`'s descriptions say
so. Older documents read as before (a stored array for `V` is a copy and reads as "moved": the map is
dropped once, as it always was).

**Why that is not the 2 s.** It is 0.3–2.6 MB less to write and some tens of ms. A save that goes from
0.5 to 2.7 s on a file that got 287 kB *smaller* (6,319,997 → 6,033,023 bytes) is not paying for bytes.
What FreeCAD writes for the scan is the same bytes before and after (`PropertyMeshKernel::SaveDocFile` →
`MeshKernel::Write`, `src/Mod/Mesh/App/MeshProperties.cpp`; the mesh is `k·V0` with `k` = 2 × 0.5 = 1
again).

**What is left, and how far I got.** Two readings fit; I cannot choose between them from here.

1. *The picture.* Every save with a window renders the document's 3D view for its thumbnail
   (`Gui::Document::Save` → `Thumbnail::SaveDocFile` → `View3DInventorViewer::imageFromFramebuffer`, 256 px,
   4 samples: `src/Gui/Document.cpp`, `src/Gui/Thumbnail.cpp`), and `saveCopy` goes the same way. `pack_write`
   renders `images/iso.png`. `scan_scale` gives the scan's mesh object a new mesh twice, and a view fit after
   it took 751 ms (srm 107) where others take 18 ms; srt 46's view fit took 1,834 ms. So the three slow calls
   are the three that draw the 219,600-triangle scan after its mesh object changed. Why drawing it would
   stay slow I did not find in the source (`SoFCIndexedFaceSet::GLRender`, `ViewProviderMeshFaceSet::updateData`
   show nothing that persists).
2. *The session.* Section 2's table: `doc_save` of a small Workshop document was also five to six times
   slower than in run 2, with no scan in it, and so was TechDraw. If the whole window was slower from about
   that point of the run, `scan_scale` is where it showed first, not what caused it.

Against 2: srr's saves right after srm were fast (26–39 ms). Against 1: wsdoc's document has no mesh.
Both may be true at once.

**Also added, to read it next time.** `scan_scale`, `align_datum`, `align_auto`, `align_symmetry` and
`align_clear` answer `timing { ms, object, mesh }` when the scan moved: the tool's own work, the part of it
spent writing the scan's mesh object, and whether the mesh was `rebuilt` (a scale) or `kept` (a Placement).
Run 3's 4.4 and 4.9 s of `scan_scale` had nothing to say where; in the replay the object write was 185–405
of 235–490 ms.

**Tests** (`tests/test_freecad_owned.py`, `WhatAScaleLeaves`, 5): the state holds no array the size of the
scan's points, before or after `scan_scale` and `align_datum`, and neither packs one again; a thickness
reading survives save and reopen; one taken before a move is not revived, in a new session or the old; the
codec alone (and a `V` that is plain data, a reference mesh's, stays an array); `timing` on a scale and an
alignment, none on a dry run or a refusal. Three of the five fail without the fix.

**Live, to settle it** (measure model, round srm 104–108):

1. `doc_save` just before the first `scan_scale`, then the two scales, then `doc_save` **twice in a row**.
   Both slow: a standing cost. Only the first slow: a one-time cost after the mesh changed.
2. `scan_scale`'s `timing`: `object` near the whole 4.4 s means the mesh object's rebuild is the tool's
   cost (then replacing the object, as `mesh_use_edited` does in 0.7 s, is the next thing to try).
3. With the scan hidden (the scan object's Visibility off), `doc_save` again. Fast: it is the picture.
4. With FreeCAD's `User parameter:BaseApp/Preferences/Document/SaveThumbnail` off, `doc_save` again. Fast:
   it is the thumbnail. Put it back on after.
5. `scan_info.kept` after the scale: `packedAgain` under 10 of about 800; `bytes` smaller than run 3's
   4,265,404 by the packed size of one copy of the points when a thickness map is in the state (0.3 MB in
   the replay, where the points pack well; up to 2.6 MB where they do not).

**Not proven.** Everything under "what is left". The fix is real and measured off the Mac; it does not make
the Mac's save 0.5 s again, and I do not claim it does.

**Seen and left alone.** `segCache.regions` (0.86 MB in the replay) is a cache and is written into the
state though the file's own header says caches are left out. `scale_all` scales the scan and the elements;
I did not check that sections, heightmaps and Mesh Tools' undo copies follow a scale. Neither was asked.

---

## 4. section_fit: spacing 0.0 on chains of 303 and 464 points — cause found by reading and reproduced in kind; fixed two ways (tested, not live)

**Cause.** The section "Half" is the plane through the fitted bore's axis, and the densified mesh has rows
of vertices on that plane. A fitted axis is not at 20 exactly: the plane passes those vertices at rounding
distance, not at 0. `slice_mesh` took a vertex as on the plane only at exactly 0 (slice.ts's rule), so each
of that vertex's edges was cut on its own: a cluster of points a rounding error apart for every vertex.
`geom2d` reads a chain's spacing as its median gap; with more than half the gaps inside clusters the median
is 0, and the default tolerance (0.6 × spacing) and the scatter's floor (0.05 × spacing) with it.

The live numbers agree in kind: chain 0's outline is 68 mm long, which at the mesh's 0.94 mm is about 73
points, and it had 303, a little over four to a vertex. Reproduced here on a regular box mesh: a plane
3e-13 mm off a row of vertices gives two points a vertex (513 for 257). That mesh's triangles give two, not
four, so the median there is not 0; the chain written three and four times over in the tests is what gives
0. **The exact distance of the live plane from the vertices is not known** (under 5e-7 mm, from the fit's
printed centre).

**Fix.**

- `scanrulerfc/section_core.py` `slice_mesh`: a vertex within a billionth of the mesh's box diagonal of the
  plane is on it (7.5e-8 mm on this part). The exact-zero rules below it are slice.ts's own and untouched.
  The earlier agent's.
- `scanrulerfc/geom2d.py` `_viewed`: when the median gap is under a ten-millionth of the chain's extent,
  the spacing is the median of the gaps that are not. The earlier agent's. **Added by me:** or under a
  thousandth of the chain's largest gap. Without that, clusters 1e-5 mm wide (a plane a hundredth of a
  micrometre off) still read a spacing of 1e-5, which the answer rounds to 0.0 again; the live plane may be
  in that band. A chain that really has short and long steps (1 to 50) keeps its median.
- `scanrulerfc/handlers/sections.py` `scatter_out`: `scatterFloor` is shown only when it reads larger than
  the scatter as answered (0.0 beside 0.0 said nothing). The earlier agent's.

**Tests** (`tests/test_sections.py`, `APlaneWithinRoundingOfTheVertices`, 5): the cut through a row of
vertices 3e-13 off is the cut through them (21 points for 61); the snap takes in half its width and not
fifty times it; a chain written three times has its real spacing, tolerance 0.3 for 0 before; clusters
1e-5 wide too; a chain of mixed steps unchanged; a floor that rounds to the scatter is not shown;
`section_fit` itself on the stand-in document.

**Live.** Measure model, `section_cut { across: { axis: "Bore" }, name: "Half" }` and `section_fit
{ section: "Half" }` (srm 57, 58). Expect spacing 0.3–1, tolerance 0.6 × spacing, scatter 0.0 with
scatterFloor 0.05 × spacing, the same lines as before. The points say which fix acted: near 75 and 115 if
the plane was within 7.5e-8 mm of the vertices; still 303 and 464 if further (then only the spacing is read
differently, and the chain still holds each point four times — tell me, the snap can be widened).

**Not proven.** That the live plane is as close as the reproduction assumes; that the lines' ends stay
exactly where they were (they were right in run 3 and the fits do not use the spacing for where a line
ends, only for how much scatter to allow).

---

## Model files

`expect` texts brought up to date, no call added or moved: `scanruler-meshtools-model.json` (`mesh_reduce`,
`mesh_apply_reduced`), `scanruler-measure-model.json` (`section_fit` on "Half", the two `scan_scale`
calls), `workshop-documents-model.json` (the two `drawing_make` calls and `patent_figures`).
