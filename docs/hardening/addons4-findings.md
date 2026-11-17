# Add-ons, pass 4: the six undecided items (16 Nov 2026)

Checkouts: ScanRuler-FreeCAD `sr4` at 05de699, Workshop `ws4` at 6cbeaba. Patches: `scanruler4.patch`,
`workshop4.patch` (both apply clean on those commits; no file added, FILES not touched, nothing
committed). The hub was read only.

Nothing here ran in FreeCAD. "Source" is FreeCAD's source as checked out (tag 1.1.0; the Mac runs
1.1.3). "Tested" is plain Python on stand-ins. Qt is not installed here either: the two tests that need
it are written and unrun. Every changed file compiles under Python 3.11.

Tests after the patches, with the hub importable: ScanRuler file by file, 1,040 passed; three files fail
exactly as they do without the patch (`test_flat_sheet.py`, `test_heightmap.py::test_tiers`: the hub's
renderer needs FreeCAD; `test_tool_names.py`: it looks for `snapshot_latest` in the hub's source, which
this hub no longer has there). Workshop per folder: documents 108, electronics 18, fasteners 15, make
120, parts 17, safetynet 118, top level 62, none failing. The hub's `tests/test_hubfix2.py` with
ScanRuler on the path: 48 passed.

One thing to know first: the models are in `docs/hardening/` in both repos (there is no
`docs/hardening/models/` folder); the new calls are appended to the files there.

---

## 1. Every changing ScanRuler call cost 1.2–1.6 s on a dense scan — fixed (measured here, not on the Mac)

**Cause.** After every call that went through, `scanstate.touched` → `docstate.mark_doc` → `write` →
`encode` packed the whole state again: every array through `np.savez_compressed`, and that archive
deflated a second time by the zip round it. Reproduced here by replaying the measure model's path
(mesh_densify, mesh_use_edited, a fit, a rename) on a stand-in document:

| state | per rename before | after |
|---|---|---|
| 393,216 triangles after densify + use_edited (the scan, Mesh Tools' base and its undo copies: 57 MB of arrays, a 3.6 MB state file — run 2's was 3.9 MB) | 620 ms | 64 ms |
| 218,700 triangles, no Mesh Tools copy | 200–235 ms (profiled: 217 of 236 ms in zlib) | 18–20 ms |

The flat model's "310 ms a call" was the same thing: every one of its calls took 307–309 ms whatever it
did, the time to pack the measure document's leaked state (A1), which never changed.

What else runs per changing call, read and timed here: `signature` twice (4 ms: sums, no hashing of
the mesh), the scan's box (6 ms), `sync_objects` (nothing unless a mesh changed), no redraw and no
snapshot of ScanRuler's own; the dock redraws its page on a 100 ms timer, outside the call.
FreeCAD's side of `State = path` is a file copy, or a rename inside an undo step (source:
`src/App/PropertyFile.cpp`, `PropertyFileIncluded::setValue`, `aboutToSetValue`).

**Fix** (`scanrulerfc/docstate.py`). Each array is packed on its own (numpy's .npy, zlib) and stored in
the zip as it is; the packed bytes are kept per open document, by the array's content (BLAKE2 of type,
shape and bytes), for as long as the state holds that content (`Packs`, `_KEPT`). A call that changes
no array packs the JSON part and nothing else; a call that changes one array packs that one. Only what
the last write used is kept, and a document's record goes when it closes. A change made in place is
seen (content, not identity); two equal arrays share one packed copy.
- Format 2 on disk (`arrays/<key>.npy.z`); format 1 (`arrays.npz`) is still read. An older add-on
  refuses a format-2 state and starts empty; the refusal now says to update the add-on.
- An array of Python objects is left out and named in `dropped` (it was pickled on the way in and
  never unpickled on the way out, so one made the whole state unreadable).
- The state file is larger than before (3.6 → 4.1 MB above; arrays are no longer compressed twice).
  FreeCAD compresses the document again on save.
- Still proportional to the state, not the change: the content hash (about 1 GB/s) and the file
  write. That is the 64 ms.
- `scan_info` now answers `kept { bytes, ms, arrays, packedAgain }` for the last write, so the Mac
  run can read the cost off the tool. Description updated (nothing shortened).

**Agent Link's own keeping of state per document.** The two cannot fight, and the code says why
(`scanstate.py`, above `_BOOK`): the hub carries a key along untouched when its add-on settles itself,
which it learns from `hooks.own_document_state("scanruler")` — now called from `agentlink_families`,
skipped quietly on a hub without it — and would also learn from ScanRuler's book on the session. The
hub settles first (it hangs on reading `session.family_state` and `session.doc`, the first two lines
of ScanRuler's `settle`), so ScanRuler always works on the new document's dict. A document reopened
from a copy (SafetyNet's checkpoint restore puts the kept `family_state` back): ScanRuler lets the
kept state go and reads the copy's, so a restored checkpoint takes ScanRuler's state back with it and
a later state is never written over it.

**Tests** (`tests/test_freecad_owned.py`): `WhatAWriteCosts` (8: nothing packed again on a rename, one
array on an in-place change, only the last write's arrays kept, format 1 read, a newer format's
refusal, the object array, a rename in a document with `scan_info.kept`, a write that fails) and
`BesideAgentLinksOwnKeeping` (4, on the hub's real `docstates`: told or not told, set aside by one of
them only, another family's state untouched, the reopened copy). Skipped without the hub.

**Live.** Measure model calls 119–122: `scan_info` (kept), `element_rename`, `scan_info`,
`dimension_set_limit`. Expect the rename's ms well under 300 (1,500 in run 2), `kept.packedAgain` 0,
`kept.ms` a few tens. If a call is still slow, `kept.ms` says whether it is ScanRuler's write, and a
batch row's `around.inside` says the hub's share.

**Not explained by this.** Run 2's 3.5–3.9 s on four trivial calls (srm 24, 30, 34, 47: about 2.4 s
over the usual, and a document save took 2.4 s there). That fits SafetyNet's auto-save copy (5 minutes
or 10 changes after the last; `safetynet/autosave.py`), which runs inside the changing call. Not
proven: `around.inside.afterChange` will show it. It is by design; if 2.4 s a copy is too much on a
dense scan, the recommendation is to take the copy after the answer, not to drop it.

## 2. section_fit "scatter 0.0469" on exact straight lines — fixed (the wording, not the fit)

**Cause.** The figure was never measured. `geom2d.view_chain` returns
`max(measured, SCATTER_FLOOR × spacing)` with `SCATTER_FLOOR = 0.05`: 0.05 × 0.9375 mm = 0.046875. The
measured value (second differences) is 0 on those lines. The floor is viewChain's rule and the fits
use it (a circle is weighed against half of it in `chainsegment.classify`); it never sets the default
tolerance, since 3 × 0.05 × spacing is under 0.6 × spacing.

**Fix.** The fit is untouched (a port of Stefan Hermann's). `geom2d.chain_scatter` gives the measured
figure and the floor apart; `section_fit` and `section_to_sketch` answer `scatter` (measured: 0 on an
exact cut) and, only where that is under the floor, `scatterFloor`. Both descriptions say so.

**Tests** (`tests/test_sections.py` `Scatter`, 3): the live chain's kind (0.0 and 0.0469, `view_chain`
unchanged), a noisy chain (its own scatter alone), and `section_fit` itself on a dense block without
FreeCAD (four lines, rms 0, scatter 0, tolerance as before).

**Live.** Measure model call 53 again: `scatter 0.0`, `scatterFloor 0.0469`, `tolerance 0.5625`.

## 3. drawing_make left its template and dimensions marked — cause found in the source, fixed properly

The earlier fix (recompute each one by itself) could not work, and its test passed only because the
stand-in's `recompute()` cleared the mark, which FreeCAD's does not (`Document::recomputeFeature`
executes and signals; only `Document::recompute` calls `purgeTouched`: `src/App/Document.cpp`).

**The template.** Every time the window draws a page's template it writes the template's size back:
`QGISVGTemplate::draw` and `createClickHandles` call `DrawSVGTemplate::processTemplate`, which ends in
`extractTemplateAttributes`: `Width.setValue`, `Height.setValue`, `Orientation.setValue`
(`src/Mod/TechDraw/Gui/QGISVGTemplate.cpp`, `src/Mod/TechDraw/App/DrawSVGTemplate.cpp`). They are input
properties and a set marks the object whatever the value (`src/App/DocumentObject.cpp`, `onChanged`).
Both exports draw it (`QGSPage::saveSvg`, `PagePrinter::renderPage` →
`ViewProviderPage::setTemplateMarkers`), and so does the first showing of the page's tab. Certain.

**The dimensions.** `PagePrinter::printPdf` ends with `DrawPage::redrawCommand` → `updateAllViews`:
every part view is recomputed by itself (its lines start afresh on a thread), then every other view by
itself (`src/Mod/TechDraw/Gui/PagePrinter.cpp`, `App/DrawPage.cpp`). A dimension that executes checks
its references against its saved geometry — saved unscaled (`ReferenceEntry::asCanonicalTopoShape`),
compared against the view's geometry as drawn, scaled (`DimensionAutoCorrect::isMatchingGeometry`,
`ReferenceEntry::getGeometry`: "will be rotated and scaled"). On a view at any scale but 1:1 they never
match, the "repair" finds the same vertex and writes `References2D` again (`setReferences2d`), with
`SavedGeometry` and `BoxCorners` after it: marked. And when a restarted view's lines and faces are
done, a turn of the event loop later, TechDraw recomputes that view's dimensions by themselves once
more (`DrawViewPart::postHlrTasks`, `postFaceExtractionTasks`): marked again, often after the call has
answered. That is the "one call late", and why all five dimensions and no view. Run 2's drawings were
2:1. This part rests on 1.1.0's source; if 1.1.3 compares like with like, only the template is marked
and the fix clears only that.

**Fix** (`workshop_documents/td_wait.py` `PageExport`, used by drawing_make and patent_figures). A
FreeCAD document observer watches the export. Afterwards it waits, running the event loop, for each
dimension on a view the export restarted to be recomputed again in a turn of the loop (at most four
times what the views took to be drawn plus 2 s; 5 s at least, 30 s at most; a coarse view is not
waited for), then takes the mark off with `purgeTouched` — no execute, so nothing restarts — and only
where everything written to the object since the export began is one of TechDraw's own writes named
above. A mark from before the export, or any other property changed, stays for the health check. The
answer carries `page.settled { cleared, waited, late, left }` (a patent figure's row only when
something stayed or may follow). Both descriptions say what it does.

**Tests** (`tests/documents/test_drawing_views_ready.py` `PageSettled`, 9) on a stand-in that behaves
as the source reads: the old fix shown not to work; an export left unmarked with the late recompute
waited for and nothing arriving after; SVG only; 1:1; marks from before or from another change kept
and explained; a dimension not seen again in time named under `late`; a coarse view and no event loop;
an export that raises; the wait's size.

**Live.** Documents model calls 2, 4, 5, 10, 15. Expect `page.settled.cleared` to name the template
and the dimensions (six names at call 4), no `late`, no `left`, and call 5's health with no
"objects not recomputed yet". If `left` is there its `why` names the property; if `late` is there the
wait was too short for that part.

**Unproven, and one case not covered.** That 1.1.3 behaves as 1.1.0 reads. And: a view restarted twice
while its faces are still being found gets two late recomputes; the wait ends at the first.

**For the hub** (not edited; by reading, not seen live): the template is marked by anything that draws
it, not only by an export. The echo opens a page's tab after a td_ call
(`page.ViewObject.doubleClicked()` in `agentlink/echo.py`), and the first showing of a tab draws the
template (`ViewProviderPage::showMDIViewPage` → `updateTemplate(true)`): a td_ call that makes a page
may read "Template … not recomputed yet" one call late. The hub's `td_export` draws the page itself
and was not checked further.

## 4. history_undo after reverse_feature_clear — checked, a gap closed, the read-back added

**Against the hub's undo.** Under the hub, `doc.HasPendingTransaction` is still false when
`reverse/doc.py` `edit` asks (the hub's `openTransaction` only names the step; `src/App/Document.cpp`,
`AutoTransaction.cpp`), so the edit opens and commits its own step, "Reverse: clear". The hub's
`changes.finish` finds nothing pending and the undo stack grown, and counts it; it holds real records,
so nothing drops it. Run 2's answer agrees (`steps: ["Reverse: clear"]`). No conflict.

**What an undo does.** FreeCAD puts `PartJson` back and re-attaches the removed body objects with the
shapes they had (`src/App/Transactions.cpp`, `applyNew`; nothing marks them). `history_undo` then
recomputes the document, the container builds again, and the reads are right. Why run 2 could not see
it: the hub's `bodies` lists FreeCAD's parts, and a ReverseBody is counted as built into its
container.

**The gap.** The builder lives in memory, outside the undo. After an undo with no recompute — Edit ›
Undo in the window — it still held the cleared part's build: `reverse_body_names` would answer no
bodies beside four body objects, and a body reached by a recompute before its container (the Group
puts the container after its bodies) would empty itself. `reverse/doc.py` `current_build` builds the
part the document holds now, in memory and without writing the document, wherever `restored_build` was
already asked (the body's execute, the store's builder and last results); nothing extra inside an edit.

**Tests** (`tests/test_reverse_doc.py`): `AfterAnUndo` (4, stand-ins) and one FreeCAD test of the clear
undone, written unrun.

**Live.** Reverse model calls 57–64 (new): after the undo, `reverse_body_names` (four bodies: 23845.49,
1000, 512, 1963.50), `object_list` (four ReverseBody objects, none empty), `reverse_feature_list`,
`reverse_parameter_list`; then `history_redo` → bodies `[]`; `history_undo` → four again.

## 5. The five tools only ever refused, and the 29 to run again

| tool | calls that should succeed | where |
|---|---|---|
| `reverse_parameter_remove` | add a parameter nothing reads, remove it, list, remove again (refused not_found) | reverse model 65–68 |
| `mesh_apply_wrap` | `mesh_wrap { gap: 4 }` as a preview, then apply: 25,548 triangles and volume 24000 here | Mesh Tools model 64–69 |
| `scan_noise` | a meshed sphere is still a "CAD tessellation" (a wrap of it too: 65–94 % coplanar here). Densified and smoothed it reads: sigmaMm 0.0238–0.0252 on three numpy spheres. The figure is the sphere's curvature, not noise; the point is that the tool answers | measure model 126–134 |
| `scan_snapshot_latest` | the camera key pressed through the hub's `cmd_run { name: "ScanRuler_Snapshot" }`, then list, latest, latest original, a wrong index | measure model 138–143 |
| `reverse_build_stop` | none possible: always refused in this port by design, as its description says. Its refusal is its proof; recorded in the model's notCovered | — |

**A fault found on the way: the camera key took no shot.** `ScanRuler_Snapshot` called the panel's
`handle("snapshot")`, which only noted the key as a group to open; `snapshot/card.take_shot` was never
called from anywhere, and the Alt+Shift+S shortcut (`card.install`) was never installed. So no shot
could exist and `scan_snapshot_latest` could only refuse. Fixed: the panel takes the shot
(`dock.snapshot_key`), the command takes it itself when no panel has opened, and the shortcut is
installed once a window and presses the same key. Tests: `tests/test_snapshot.py` `TheCameraKey` (5,
plain Python) and one Qt test, unrun. **Unproven live**, and it is Qt code written without Qt: if call
140 lists no shot, the panel's header or the Report view says why. One risk to check by hand:
Alt+Shift+S is now a window-wide shortcut; if FreeCAD or another add-on uses the same keys, Qt fires
neither.

**The 29.** Their calls were already in the models with expectations corrected by pass 3. Added
where a fix had no proof across documents: measure model 123–137 is the A1 sequence the marks file
asks for (`doc_new`, `scan_info` → no scan, `flat_edges` refused, `scan_open` with no discard accepted,
`doc_save` under 2 MB, `doc_switch` back, `scan_info` → the WornScan and its elements). Expectations
updated for this pass: measure 53 (scatter), Documents 2, 4, 5, 10, 15 (settled, health), reverse 56.
Every ScanRuler call in the models passes its tool's input schema (checked by script).

## 6. `library_pack` is not in the inventory

**Cause.** `docs/hardening/inventory.json` in the hub is a snapshot of what `tool_groups { group }`
listed on the Mac on 16 Nov, and `tool_groups` leaves out a tool with `alias_of`
(`agentlink/tools.py`, the group listing). With ScanRuler-FreeCAD installed, Workshop Documents marks
its `library_pack` as an alias of `pack_write` (`workshop_documents/fam_share.py`
`unlist_when_offered`): callable by name, never listed. Its group, `share`, has no other tool, so the
whole group is missing; `hardening_status.py mark` then stops with "not in the inventory".

**Smallest fix (hub, not made).** One entry in `docs/hardening/inventory.json`, then
`python3 scripts/hardening_status.py render`:

    "share": { "workbench": "Workshop", "repo": "Workshop-FreeCAD", "tools": ["library_pack"] }

No hub test counts the inventory's tools (`tests/test_tool_index.py` reads only the hub's own repo
groups). The lasting fix is to build the inventory from the server's tool table, unlisted aliases
included, and say so in its `about`.

---

## Undecided, with a recommendation

1. **The auto-save spikes** (item 1). Read `around.inside.afterChange` on the next run before changing
   anything.
2. **1.1.3 against 1.1.0** for the dimension marks (item 3). The live `settled` reading settles it.
3. **The Alt+Shift+S shortcut** (item 5). Keep it, since the tools' descriptions promise it; if it
   clashes, limit it to while the ScanRuler workbench is in front.
4. **A part view marked changed when an export starts** (`td_wait.views_ready`): it is recomputed once
   and still reads "touched", for the same reason as item 3, so the export is refused with that
   reason. Safe, not seen live. Recommend treating a view as recomputed once it has been, and waiting
   for its lines with the watcher of item 3.
5. **For the hub's echo.** A TechDraw dimension that is selected and then deselected after its label
   was placed by a program writes its X and Y in an undo step of its own, "Drag Dimension"
   (`QGIDatumLabel::itemChange`, `QGIViewDimension::datumLabelDragFinished`). drawing_make's answer
   names nothing the echo selects, so this is not what run 2 saw; a td_ tool whose answer names a
   dimension under `view` or `object` would trigger it. Worth a look when the td_ tools are next run.
6. **scan_noise on a sphere** proves the tool answers, not that its figure is a scanner's noise. A real
   noisy scan file is still the only proof of the reading.

## What the patches change

scanruler4.patch
- `scanrulerfc/docstate.py`, `handlers/scan.py`, `scanstate.py`, `agentlink_families.py`: item 1.
- `scanrulerfc/geom2d.py`, `handlers/sections.py`: item 2.
- `scanrulerfc/reverse/doc.py`, `reverse/handlers.py`: item 4.
- `scanrulerfc/dock.py`, `commands.py`, `snapshot/card.py`: the camera key (item 5).
- `scanrulerfc/data/tools.json`: scan_info, section_fit, section_to_sketch (added to, not shortened).
- `docs/hardening/`: measure model 119 → 144 calls, Mesh Tools 64 → 70, reverse 57 → 69.
- Tests: `test_freecad_owned.py`, `test_sections.py`, `test_reverse_doc.py`, `test_snapshot.py`.
- Credits to Stefan Hermann / CNC Kitchen untouched.

workshop4.patch
- `workshop_documents/td_wait.py`, `handlers/drawing.py`: item 3 (`settle_page` replaced by `PageExport`).
- `workshop_documents/data/tools.json`: drawing_make, patent_figures.
- `docs/hardening/workshop-documents-model.json`: five expectations.
- Tests: `tests/documents/test_drawing_views_ready.py`.
