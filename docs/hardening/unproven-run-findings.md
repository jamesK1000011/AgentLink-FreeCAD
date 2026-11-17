# Run 5 read: the unproven-hub and bim-rest models, and the hub fixes that follow (hubfix4)

Checkout `<work>/d21`, base `3283fdd`. Nothing committed, pushed or run in FreeCAD.
Patch: `hubfix4.patch` (26 files: 10 of the hub, 2 models, 13 test files changed, `tests/test_hubfix4.py` new; FILES left alone).
Marks: `unproven-marks.sh` (44 tools in 16 lines, and 5 more behind a `#` for the main session to decide; never `--live`).
Suite: `timeout 290 python3 -m pytest -q tests` — 1045 passed, 348 skipped (they need FreeCAD), 237 s.
`scripts/tool_index.py --check` and `scripts/tool_summary.py --check` pass. All changed Python compiles under 3.11.

Every fix below is proven on stand-ins only. Nothing here was run in FreeCAD: each fix names what to run live.

## Part 1 — the answers against their expectations

Read: `unp-a.json` (calls 0–146), `unp-b.json` (147–199), `bimrest-a.json` (39), each answer against its `expect`.

| Model | Calls | PROVEN | NOT PROVEN | MODEL WRONG |
|---|---|---|---|---|
| unproven-hub | 200 | 193 | 6 (59, 61, 103, 178, 193, 199) | 1 (14) |
| bim-rest | 39 | 36 | 2 (9, 37) | 1 (38) |

### NOT PROVEN — what differs

| Call | Expected | Answered | Whose fault |
|---|---|---|---|
| unp 59 `workbench { activate: "Part Design" }` | active PartDesignWorkbench, was, workbenches | REFUSED failed "FreeCAD did not switch to PartDesignWorkbench (still PartDesignWorkbench): the workbench failed to load" — Part Design was the active workbench (call 58 says so) | Hub. Fixed (a) |
| unp 61 `cmd_list { query: "Std_ViewFit" }` | each row with name, menu, tip, shortcut | both rows right, no `shortcut` (Std_ViewFitAll's is V, F) | Hub: it read a key FreeCAD does not give. Fixed (h) |
| unp 103 `view_snapshot { view: iso, fit: true }` | a picture 800 × 600 | `empty`: "The model is a speck in the view (under 6 pixels across …) — view_snapshot with a view and fit left on fits it", `fitted: true`, no path — on a 40 mm bracket, right after its own fit | Hub (the fit); cause not proven. Changed (g) |
| unp 178 `fea_solve` | `solvedBy` begins "FreeCAD's FEM (Beam strength (fea_solve)" | every figure right (59.906 MPa at the root against 60, 0.1908 mm against 0.1905, safety 4.17, loads[0].area 100, 2312 nodes), but `solvedBy` "Agent Link's own CalculiX deck — FreeCAD's FEM route failed here: RuntimeError: Cannot add static property" | FreeCAD (see i). The hub fell back as designed; the route is not proven |
| unp 193 `meshobj_unwrap { of: "Cap" }` (open mesh, 1,651 triangles) | area3d about 314, a pattern "Cap flat", a DXF | REFUSED failed "FreeCAD's unwrapping could not lay this surface flat: it stopped (code -11) — split it into simpler faces" | Not known: the helper Python ended with a crash code and no word. The hub could not tell a crash at import from one in the unwrapping. Changed (j) |
| unp 199 `usage_report { session: true }` | errors higher by each refusal since call 13 | errors 56; the rows 0–198 hold 57 not-ok answers (4 before call 13, 53 after) and the session held 5 more calls than the list: one refusal at least is not counted | Hub, small. Not found, not fixed. A guess, not checked: the refusal of call 35 (`steps_render`, width 50) ran as a job (job-7c1bd94e, "failed") and a job's refusal is not logged as an error |
| bim 9 `bim_library { insert }` | objects ["Shelf block"] | objects ["Shelf block", "Agent Link records001"]: the other file's hidden records object came in and is answered as an object | Hub. Fixed (k) |
| bim 37 `bim_nest` (three rectangles on a 1200 × 600 sheet, rotations [0, 90]) | sheets 1, placed 3 | REFUSED failed "The pieces would not nest: FreeCAD's nester stopped …" | FreeCAD's nester, on a sound sheet and sound pieces. The tool now works round it (e) |

### MODEL WRONG — the cure

| Call | Why | Cure |
|---|---|---|
| unp 14 `usage_report { days: 1 }` | "per day and per session rows": `sessions` is a count (289; `agentlink/usage.py`), not rows. The rest is right (tokens = callTokens + toolListTokens: 1,746,043 + 99,144 = 1,845,187) | expect "sessions: a count" |
| bim 38 `view_render` of the sheet and the pieces | view_render draws solids; four flat faces answer `empty` "Nothing to draw: … have no solid shape", which is right by its description | the expectation now says so (changed in the model). The pieces' places after a nest are read by no call: add `object_get { object: "Piece a", filter: "Placement" }` after 37 |

### The five things known from the compact replies

- **unp 59**: confirmed, a hub fault (a).
- **unp 129** `job_start` inside a batch: confirmed. The answer was the expected (faulty) words, so the call is PROVEN against its expectation; the words are fixed (b) and the model's expectation with them.
- **bim 37** `bim_nest`: confirmed, see (e).
- **snapshot_latest** (97, 98): both refused not_found "No screenshots yet", as expected with `snapshot_list` answering `shots: []`. PROVEN; the tool only ever refused, so it is not marked.
- **td_bim 138**: the refusal is the expected one ("Bracket is not a BIM section plane"). The success is the call before it, 137: view "Plan view", scale 0.02, svgBytes 1136, no warning; `td_page` read (162) lists it as DrawViewArch. td_bim is PROVEN on both.

### Seen in PROVEN answers (the expectation did not ask)

| Where | What | Done |
|---|---|---|
| unp 162 `td_page read` | BracketTop is at [148.5, 105] — the middle of the A4 second sheet — after it was placed at [100, 200] (139) and shared (158) | Hub fault. Fixed (l) |
| unp 31, 32, 34, 41 `steps_list` | the through-all pocket reads `key: "Length 5.00 mm"`: a length it does not use | Fixed (m) |
| unp 127 `job_status` | the refused `steps_render` (35) is kept as a job with status "failed", took 0.0 | Listed, not changed |
| unp 85 against 83 `pref_set` | type "integer" where the first call said "int" | Listed |
| unp 65, 70, 89, 101 | wording: "…in this FreeCAD cmd_list { query } finds them" (no stop between), a list with no stop after it, "…until one is set): " ending in a colon with nothing after, "No stress map to draw: No stress to show: …" said twice | Listed; words left as they are |
| unp 68 `menu_run` | 2,050 ms for one menu item | Listed |
| bim 20 `object_list` | the rebuilt column is name Structure001, label Structure002. That the label is the column's old internal name cannot be read from any answer | Not checked |
| bim 37's own note | "…sheets' worth were laid out; view_render shows where": view_render does not draw flat faces (bim 38) | Listed; words left |

## Part 2 — the fixes

Each has a test. "Old against new" means the family's proof test, which runs the handler at its base commit beside today's entry on a stand-in FreeCAD; a fix that changes behaviour is written there as a meant difference, with its reason, and everything else must still be equal.

### a. workbench { activate } on the active workbench

- **Cause.** `Gui.activateWorkbench` answers False for the workbench that is active already: `src/Gui/Application.cpp`, `Application::activateWorkbench`, "`if (oldWb && oldWb->name() == name) return false;  // already active`". The entry refused on `ok is False`.
- **Fix.** `agentlink/data/tools.json`, entry `workbench`: when the workbench asked for is the active one it answers `active`, `was` (both that name), `note: "Already active."`, `workbenches`, without calling FreeCAD. The refusal is kept for a workbench that is not active after the call (`gui.activeWorkbench().name() != hit`); FreeCAD's False alone no longer refuses. No description or refusal word changed.
- **Test.** `tests/test_dataapp_data.py` (the stand-in now answers False as FreeCAD does; case "by its menu name with a space": old refused, new answers, FreeCAD not asked) and `tests/test_hubfix4.py::WorkbenchAlreadyActive`.
- **Live.** unp 58–60 again: 59 must answer with the note.

### b. job_start inside a batch

- **Cause.** `jobs.wanted()` is False whenever a batch is in hand, and `job_start` then said the tool cannot be a job (`agentlink/tools.py`).
- **Fix.** For a read that would be a job on its own, the refusal is the batch's (`jobs.start_in_batch_refusal`): "job_start: not inside a batch, which is one answer and starts no job — call job_start { tool: "body_check", arguments } on its own, or call body_check itself here: a heavy read inside a batch runs in its place and the batch waits for it." Code invalid_input, as before. A tool that is never a job (a change, a picture, session_state) keeps its own words in and out of a batch. **Refusal words changed** (this one case). The last clause is what the batch does (`agentlink/tools.py`, the heavy-read branch of batch: it starts the job itself and waits while the budget lasts), which the model's finding F1 had not found.
- **Test.** `tests/test_hubfix4.py::JobStartInABatch` (a real batch on a fake FreeCAD: four job_start calls, each refusal read). Model call 129's expectation updated.
- **Live.** unp 129 again inside a batch, and runAlone 4 and 5 (never sent).

### c. draft_outline and td_view_more (symbol, image): a relative path

- **Cause.** Both took `expanduser(path)` as it was (`agentlink/families/draft.py` `outline_faces`; the two `td_view_more` branches in tools.json).
- **Fix.** draft_outline: the helper the entry calls is now `outline_faces(paths.local(s, path))` (one line in draft.py's helper table; the entry is unchanged). td_view_more: `p` is `local(a.path)` (the helper techdraw.py already had) for symbol and image; no path is still "path '': no such …". The refusal words are the same; for a relative path they now carry the place looked in ("path '<session folder>/x.svg': no such SVG.").
- **Test.** `tests/test_datadraft_data.py`: every draft_outline case names a bare "logo.svg"; the new entry hands the reader `<out>/logo.svg`, nothing else differs (meant difference, counted). `tests/test_datatd2_data.py`: four new cases (a bare name in the session's folder placed as symbol and as image, one that is not there refused for each).
- **Not changed, same habit:** `bim_image_plane` and `bim_reference` also take the path as it is; their refusals say "give its full path", so they were left.
- **Live.** `draft_outline { path: "unproven_foot_top.svg", depth: 2 }` and `td_view_more { kind: "symbol", page, path: "unproven_foot_top.svg" }` after meshobj_unwrap wrote it (unp 147).

### d. "'Gui.ViewProviderGeometryObject' object has no attribute 'DiffuseColor'" — NOT FOUND, NOT FIXED

- **The hub does not read or set it on such an object.** `DiffuseColor` appears twice in the whole hub (no other spelling, no `ShapeColor`, no `ShapeAppearance` read): `bim_material` writes it as a key of the Arch material's dictionary (not a view provider), and `object_appearance` sets `vo.DiffuseColor` only `when … has(vo, 'DiffuseColor')`. The echo, the health check, the highlight layer (`annotate.py`, `overlay.py`) and the BIM helpers (`families/bim*.py`, `ifc.py`) touch no colour property; the hub attaches no view-provider proxy to anything.
- **In FreeCAD 1.1.0's source** `DiffuseColor` on a view provider exists only for Part (`src/Mod/Part/Gui/ViewProviderPartExtPyImp.cpp`, `getCustomAttributes`); a plain `ViewProviderGeometryObject` has `ShapeColor` and `ShapeAppearance` (`src/Gui/ViewProviderGeometryObjectPyImp.cpp`). Objects with a plain one in these runs: an image plane (bim-rest 12, 13) and a level or building (`Arch.makeBuildingPart`: `App::GeometryPython`). The "pyException" lines are FreeCAD reporting an error in one of its own Python callbacks. Every read of `.DiffuseColor` I found in BIM and Draft is either behind `hasattr` or on a Part object (`ArchWall.py` 1684, `ArchComponent.py` 1614–1634 and 1977, `ArchWindow.py` 881–895, `ArchBuildingPart.py` 915 and 1332, `draftutils/gui_utils.py` 420–446). I could not name the line that raises. The Mac runs 1.1.3 and other add-ons (Home, Workshop, ScanRuler) that are not in this checkout; either may hold it.
- **What settles it live:** the lines just above one "<class 'AttributeError'>" line in the Report view name the file and line (`report_read { last: 30 }` right after one bim call in a document holding a level and an image plane). With that it is a one-line fix, wherever it is.

### e. bim_nest: FreeCAD's nester stopped — the tool, working round FreeCAD

- **The model is sound**: the sheet is one flat face, the three pieces single flat faces the same way up, the largest far smaller than the sheet.
- **Cause, in FreeCAD.** `src/Mod/BIM/ArchNesting.py`, `Nester.run`: for each rotation of each piece it takes the corners of the "fit polygon" as places to try and rejects a place when a corner of the piece is `placed[1].isInside(vert.Point, TOLERANCE, False)`. For a face, Part's `isInside` goes by distance (`src/Mod/Part/App/TopoShapePyImp.cpp`, 2017–2029: "`extss.Value() <= tolerance`"), so a piece that only touches one already placed counts as inside it. When every corner of the fit polygon touches a placed piece, the `for … else` prints "Could not determine location on sheet. Aborting." and **returns from the whole run** — although another rotation, or the same piece elsewhere, would do. Worked by hand for this model with [0, 90]: the 500 × 300 lands upright at the left, the 400 × 300 at the right end, and the 300 × 200 turned by 90 has room only between them, touching both: the run ends there. (Two pieces pass, which is why the two-piece test on FreeCAD passed.) By hand, not run.
- **Fix.** `agentlink/families/bim_gaps.py` `nest_run`: when the rotations together stop the nester, each is tried alone in the order given and the first that lays the pieces out is taken; the answer then carries `rotationsUsed` and `rotationsNote` beside `rotations`. What the nester prints is caught (and written on to where it would have gone), and its reason is in the refusal when nothing works: "The pieces would not nest: FreeCAD's nester stopped — it said: Could not determine location on sheet. (rotations: together, then each alone). Check each piece …". With no printed reason the refusal is word for word the old one. **Refusal words changed** in that one case; two answer fields added. By hand, [0] alone lays this model out on one sheet.
- **Test.** `tests/test_bim_data.py`: two new cases on a stand-in nester that stops as FreeCAD's does (laid out with 90 alone after [0, 90] and [0] stopped; stops at every rotation and the refusal quotes it). `tests/test_hubfix4.py::NesterStops` (the reason read from the nester's real lines).
- **Honest limit.** The nester can still stop with one rotation (a full sheet). Then the tool refuses, now with the nester's own sentence.
- **Live.** bim-rest 31–37 again. Expect `sheets 1, placed 3`, with `rotationsUsed` if [0, 90] together still stop. If it refuses, the sentence after "it said:" is the proof of the cause above or its correction.

### f. Other places that take "already so" for a failure

Window tools read (entries and code): `show` (sets, no check), `selection`, `doc_switch` ("Already on it."), `pref_set` to the same value (was = now, answered), `pref_reset` of a name not stored (`notSet`), `cmd_run` (Sketcher_LeaveSketch with none open answers `already`; another greyed command is refused because FreeCAD would do nothing), `menu_run`, `dialog_answer`, `gui_unstick`, `queue_go`. **None but `workbench`.** The echo calls `activateWorkbench` too and ignores its answer.

Elsewhere in the hub, refusals for a state already there, listed and left (each says what to do, and most guard against a doubled effect): `asm_add` (every part named is in it already), `asm_explode` (already exploded), `fea_hold` / `fea_load` (already in the study: a second load would count twice), `pd_move_feature` (already in that body), `sketch_extend` (already reaches), `draft_modify upgrade` (as far as they go), `meshobj_edit` (being edited), `addon install` (installed already). `sheet_import` and `sheet_export` read FreeCAD's False, which there does mean failure.

### g. view_snapshot: a fit that left the part a speck (unp 103) — changed, cause not proven

- **What is known.** `snap_fit` ran `cam.viewAll(view.getSceneGraph(), region)` after FreeCAD's `fitAll`. FreeCAD's own fit leaves out what is marked to be skipped (`View3DInventorViewer::viewAll` switches every `SoSkipBoundingGroup` to EXCLUDE_BBOX first: a sketch's grid, a sketch's edit layer); a plain `viewAll` of the scene graph takes those in, with anything an add-on hangs in the scene. The check after it (`_snap_empty`) reads the shown objects' own box. So the fit and the check did not go by the same thing. Which node was large in that scene I cannot tell from here.
- **Fix.** `agentlink/families/view.py`: the fit frames a cube of the shown parts' box in its place (as FreeCAD's `viewAll(float factor)` does), for the picture's viewport; the same box the check reads (`shown_box`). With no box it is the scene graph as before.
- **Test.** `tests/test_hubfix4.py::SnapshotFit` (a fake Coin: the camera is given a translation and a cube of the box's size, never the scene graph; a flat box; no box).
- **Not changed:** the `empty` advice still ends "view_snapshot with a view … and fit left on fits it", which is circular when that was the call.
- **Live.** unp 103 again. If it still answers a speck with `fitted: true`, the cause is elsewhere (an animation in flight is my next guess: `fitAll` runs a 200 ms event loop while the turn to iso is still animating).

### h. cmd_list: no shortcut ever

- **Cause.** `Command.getInfo()` names it `shortcut` (`src/Gui/CommandPyImp.cpp`, `PyDict_SetItemString(pyDict, "shortcut", …)`); `cmd_row` read `shortcutText`.
- **Fix.** `agentlink/families/app.py` `cmd_row` reads `shortcut` (then `shortcutText`).
- **Test.** `tests/test_dataapp_data.py` (the stand-in now gives FreeCAD's key; the old handler shows none, the new "V, F").
- **Live.** unp 61 again.

### i. fea_solve: FreeCAD's FEM route failed (unp 178) — FreeCAD's error; the hub now says where

- **Cause.** "Cannot add static property" is thrown by FreeCAD itself (`src/App/PropertyContainer.cpp`, `PropertyData::addProperty`, when a class registers a property after its property table was merged) while one of the route's objects is made. It names no object, and the route worked in earlier runs, so it depends on what that FreeCAD session had made before. Not a fault of the route's code that I can see.
- **Fix (diagnosis only).** `solvedBy` now ends with the line of the route where it came up: for example "… RuntimeError: Cannot add static property (strength.py:820)" (`strength.failed_at`; the number is the line of `_fem_build_and_run` that was running). **Answer words changed** (a suffix).
- **Test.** `tests/test_hubfix4.py::FemRouteFailure`; `tests/test_datafem_data.py` (meant difference: the suffix, nothing else).
- **Live.** unp 169–178 again in a fresh FreeCAD: `solvedBy` should begin "FreeCAD's FEM". If it fails again the line says which object.

### j. meshobj_unwrap: "it stopped (code -11)" (unp 193) — the next run will say which

- **Cause not known.** The unwrapping runs in a Python of its own; it ended with a crash code and no word, 0.5 s in. That is either FreeCAD's modules failing to load in the Python beside FreeCAD, or flatmesh on this surface.
- **Fix.** The helper marks where it is ("loading", "loaded") on its error stream (`agentlink/families/meshobj.py`, `unwrap_stop`). Ending between the two is a new refusal, code unavailable: "The unwrapping runs in a Python apart from FreeCAD, and FreeCAD's own modules would not load there (it stopped (code -11)): nothing was unwrapped, and this surface is not the cause — unwrap a cylinder, cone or flat face ("Body.Face3") instead: those are laid flat exactly, without it." After "loaded" it is the old refusal, word for word. **One refusal added.**
- **Test.** `tests/test_hubfix4.py::UnwrapEnds`; `tests/test_datamesh_data.py` (a new case, a meant difference).
- **Live.** unp 192–193 again. Either answer names the stage; only then can the real fault be fixed.

### k. bim_library { insert }: the other file's records object

- **Cause.** `mergeProject` brings in the file's hidden `AgentLinkRecords` object (as `AgentLinkRecords001`); `doc_merge` already removes it, `bim_library` did not.
- **Fix.** The same step in the `bim_library` entry (helper `is_records` in bim_gaps.py).
- **Test.** `tests/test_bim_data.py` (new case: old answers ["Merged", "Agent Link records001"], new ["Merged"], and the object is gone).
- **Live.** bim-rest 8–9 again: objects ["Shelf block"].

### l. td_view_more { kind: share } moved the view

- **Cause.** `DrawPage::addView` puts a view it is given in the middle of the page (`src/Mod/TechDraw/App/DrawPage.cpp`, "position all new views without owners in center of Page"; the Python `addView` always asks for it).
- **Fix.** The share branch keeps the view's X and Y and sets them back after `addView`.
- **Test.** `tests/test_datatd2_data.py` (the two share cases: two more lines in the trace, X and Y set back, nothing else).
- **Not changed:** `move` lands the view in the middle of its new page (FreeCAD's own doing; `at` is not read for move, though the description ends "at [x, y]").
- **Live.** unp 139, 157, 158, then `td_page read`: BracketTop still at [100, 200].

### m. steps_list: a through-all pocket keyed by a length it does not use

- **Fix.** `agentlink/families/notes.py` `steps_of`: a pad or pocket whose Type is not Length or TwoLengths is keyed "Type ThroughAll" (or UpToFace …).
- **Test.** `tests/test_hubfix4.py::StepKey`.
- **Live.** unp 31 again.

## Not done

- **(d)** is not fixed: the reader is not in this checkout.
- **usage_report** one refusal short (unp 199): not found.
- **runAlone** (10 calls: batch's own refusals, job_start's successes, job_status of a job) was not sent in run 5: batch, job_start and job_status stay unproven on those.
- Roots not proven, only narrowed: (g), (i), (j). (e) is argued from the source and by hand.
- No call of either model passes a bare file name to draft_outline or td_view_more: (c) has no live call yet.
