# Live answers against the models' expectations: findings (agent "status", 16 Nov 2026)

Read by eye, call by call: 515 answers (sheet 20..54: 35; fem 43; draft 81; mesh 63; surface 52; core 0..59, 60..71,
83..99, 100..113: 103; points 35; cam 34, the re-run; bim 69, with bim-1b, bim-2b and the IFC re-run), plus the 43
superseded answers of cam-0/1 and bim-3. Not seen by me: sheet 0..19, core 80..82 and the hand-run ifc_remove (taken from
the coordinator's words), core 72..80 (not run).

Nothing was run on FreeCAD here. "Proven" means read in FreeCAD 1.1.0's source (the Mac runs 1.1.3) or, for the two
plain-Python helpers, run in the test suite. Every fix has a test; the FreeCAD ones have not been run.
`python3 -m pytest -q`: 687 passed, 311 skipped. Fixes and tests: `status.patch` (25 files, FILES untouched, no new file).

Judgments: **(a)** tool bug, **(b)** the model's expectation was wrong, **(c)** cannot tell.

Totals: 22 tool faults (16 behaviour fixes and 4 wording corrections in status.patch, 2 for health.py described), 20 wrong expectations, 4 undecided.

## (a) Tool bugs, fixed in status.patch

| # | call | expected | came back | cause and fix |
|---|---|---|---|---|
| 1 | bim 16 `bim_roof` (hip, 30° all round, 6000 × 4000) | ridge about 1154.7 | ridge 1732.1 on a roof whose box is 1501.1 high | `bim.py` answered `max(o.Heights)`. ArchRoof's Heights are each pane's own run × tan(angle) (`calcHeight`); `calcApex` shortens a run only against a parallel opposite edge whose runs overlap, so the end panes of a hip keep 3000 × tan 30 though the long panes cut them off at 2000 × tan 30. Now read from the roof as built: the highest point of its downward-facing faces above the eaves (`Face.normalAt` follows the face's orientation, Part/App/Tools.cpp), used only when lower than Heights. The gable roof (bim 15) was right and stays 1732.1. Test: `test_04_roof_either_way_round`. |
| 2 | bim 34 `bim_quantities` | groups by material | "(no material)": 16 objects, 143.5 m³ in a 37 m³ house | Levels and the building carry their members' solids as their own shape in 1.1, and the container test only skipped groups without solids: Ground floor, Roof level and House were counted beside their members. Now skipped by proxy and IFC type (the test bim_preflight already uses). Test: `test_13_quantities_count_each_member_once`. |
| 3 | bim 26 `bim_layers` (seen at bim 62) | the wall's material layers in the IFC | reply note "IFC export writes the layer set"; ifc_find shows material null | The note was false: exportIFC.py associates `App::MaterialObject` materials only ("TODO : support multimaterials too"). Note and description now say so. Text only. |
| 4 | mesh 10, 11 `meshobj_trim` | wouldRemove over 0 | wouldRemove -2, removed -2 | The count was triangles before minus after, and a cut adds triangles. Now `removed` = triangles wholly on the side taken away, `cut` = triangles the plane crossed (`wouldCut` in a preview). Test: `test_8_live_run_findings`. |
| 5 | mesh 27 `meshobj_sections` (sphere, slice at 0) | length 62.83 | loops 1, length 125.644 | `MeshAlgorithm::CutWithPlane` takes a segment from every triangle the plane meets: where the plane runs along the mesh's own edges, the triangle on each side gives the same segment and the loop comes back twice round. New `meshdist.once_each` keeps each segment once and chains them again (polylines with no repeat are returned untouched). Tests: `test_meshdist.Polylines` (run here), `test_8_live_run_findings`. |
| 6 | mesh 35 `meshobj_project` (6 mm line over the cube) | length 6 | length 16 | FreeCAD's own: `MeshCore::MeshProjection::projectLineOnMesh`, for a sample that lands exactly on a mesh edge (the cube's top diagonal at x = 5), takes the start triangle's whole chord when its far end is behind the sample, and `connectLines` then runs out to x = 0 and back: +10 mm. New `meshdist.no_spurs` drops repeated points and any stretch that runs straight back along itself. Tests as #5. |
| 7 | mesh 62 `meshobj_unwrap` (a mesh) | unwrapped, or unavailable for no flatmesh | "No Python to run the unwrapping in apart from FreeCAD here." | In the window `sys.executable` is FreeCAD's program, and the tool only accepted an executable named python. Now it also looks beside it (`testrun.real_python`) and in the Mac bundle (`app._bundle_python`). Whether that Python imports flatmesh with the window's paths needs the live run. A face (mesh 59) unwrapped right. |
| 8 | draft 76, 77 `draft_text` | box on z 10 … 11 | box z 10 … 10 | The description says "box (the real extent)"; the reply gave the flat outline before it was raised or cut. Now the box of the raised / cut lettering. Test: `test_2_emboss_and_engrave`. `draft_outline` answers the same flat box (not in this run, left as it is: say if it should follow). |
| 9 | fem 9, 26, 27, 34 `fea_solve` / `fea_results` | (not in the expectation) | loads[].area 1045519, 1008524, 1074772 for a 1000000 mm² face; 1000000 on Agent Link's own deck | On the FreeCAD FEM route `elems` came from `femmesh.getElementNodes` in FreeCAD's node order, while `getccxVolumesByFace`'s face numbers and `ccx_io.TET10_FACES` count in CalculiX's (FemMesh.cpp: 1, 0, 2, 3, 4, 6, 5, 8, 7, 9). The wrong three nodes were taken as each loaded face. The solve itself was right (FreeCAD's own constraint applied the load). Now reordered. The same list feeds `fea_export`'s VTU, so a VTU written after a FEM-route solve (fem 15) had scrambled tetrahedra. Test: `test_2_cantilever` (area 100). |
| 10 | cam 21 `cam_setup` (first run: ops 0; re-run: ops 2) | 2 or 3 | 0, then 2 | The loop went over `job.Operations.Group`, which lists the dressup of a dressed operation, and a dressup has no CoolantMode (the post reads the base operation's: `Path.Base.Util.coolantModeForOp`). Now set on the operation under the dressup. Test: `test_4_tags…`. |
| 11 | cam 22 → 24 `cam_edit` stop, then `cam_post` | tools has only number 4 (Drill is off) | tools [T4, Drill 5 T2] | The stop is a Custom operation; FreeCAD's `findToolController` gave it the controller selected in the window (the drill's, just added), and with several controllers and none selected it would open a dialog. The post then changes to T2 for the M1. Now the stop or comment takes the tool of the operation it follows. Test: `test_4_tags…`. |
| 12 | core 59, 60 `material_set` / `material_clear` | health ok | "1 object not recomputed yet: Pin" on both | One cause: `material_set` wrote ShapeMaterial and left the object touched; `material_clear` changes no object, its verdict was the leftover. `material_set` now recomputes when it set a ShapeMaterial. |
| 13 | core 104 `doc_close` | document CoreDoc | document SheetTutorial; doc_merge, object_delete, doc_revert then ran there | After closing the current document the tool switched to `list(FreeCAD.listDocuments().values())[-1]`: the last by name, not the one doc_new answered as "previous". The session now keeps a trail of the documents it left (`doc.went_from`, also fed by doc_switch) and goes back to the latest still open. Test: `test_close_goes_back_to_the_document_before`. |
| 14 | core 105 `doc_merge` | count 1, objects [Ball] | count 2, [Ball, "Agent Link records001"] | `mergeProject` brings the source file's hidden records object (steps, materials) in as an object; into a document with no records of its own it would stand in as that document's. Now removed after the merge. Test: `test_std_more` (doc_merge). |
| 15 | core 81 `robot_new` (by hand) | tcp.at [3125, 0, 1100] | tcp [0, 0, 0] until the first move | `RobotObject::onChanged` works Tcp out only when an axis is set. `robot_new` now sets Axis1 to itself (the tool's own `settle`) before reading. Test: `test_more_families` (robot). |
| 16 | pts 23 `points_mesh` poisson | closed | closed false under the note "a closed surface through the cloud" | The note was fixed text. It now follows `isSolid()` and names meshobj_repair when open. Why PCL's surface came back open (41151 triangles on 20578 points: one short of closed) is FreeCAD's, not looked into. |
| 17 | mesh 21 `meshobj_smooth` | (see b-7) | −20% volume | Not a bug in the call (see b-7), but the description, refusal and guide said taubin "keeps its size". Reworded, and the reply now carries a warning past 2% change. |
| 18 | draft 6 `draft_modify` upgrade | (see b-5) | two wires, no word why | Suspect settled: yes, the tool should say. When an upgrade leaves two or more open wires whose ends are within 0.01 mm but over 1e-7, the reply's note names them and the gap. Test: `test_6_upgrade_says_which_ends_do_not_meet`. |
| 19 | surf 43 `surface_blend` | (see b-9) | length 242.7 | Mapping is right; the description now says what size means. Text only. |
| 20 | core 81 `robot_new` model "puma" | — | default KUKA IR 500 | By design and as the model expected (Robot6Axis.cpp's only built-in is KukaIR500); the description now says puma is only a name for that default. Text only. |

## (a) For agentlink/health.py (not edited): the fix, precisely

**H1. A sketch's yellow line repeats on calls that did not touch it** ("NutSketch: 1 DoF left…" on sheet_format, sheet_rows,
sheet_cells, sheet_table; sheet 20–26, 49).
Cause: `check()` step 2 reads every sketch in `changed`, and `changed` is every object the observer saw recomputed. NutSketch
depends on the sheet through its bound constraints, so any change to the sheet recomputes it. Parts have a filter for this
(`shapes0[o.Name] == _key(o)`: "recomputed, and the same shape as before the call"); sketches have none.
Fix: in `mark()`, beside `m["shapes"]`, keep `m["sketches"] = {sk.Name: _sketch_key(sk)}` for the document's
`Sketcher::SketchObject`s (up to MAX_SKETCHES), where `_sketch_key(sk)` is
`(int(sk.DoF), int(sk.GeometryCount), int(sk.ConstraintCount), tuple(sk.ConflictingConstraints), tuple(sk.RedundantConstraints), tuple(sk.MalformedConstraints), number of open wires, round(sk.Shape.Length, 6) if the shape is not null)`
(all attributes, no solve). In `check()` step 2, after `r = sketch_reading(sk)`: if `not r["red"]` and `same_doc` and
`sk.Name in m["sketches"]` and `m["sketches"][sk.Name] == _sketch_key(sk)`, skip it (no amber line, no fine line). Red
sketches are always named, new sketches always read, and a sketch whose freedom, geometry or constraints changed is read as
now. The value-driven case (sheet_set changing a bound dimension) changes Shape.Length, so it still reports.

**H2. "Sketch: fully constrained" on cam_job, cam_op, cam_tool_add** (cam 6, 8, 17, 18, 19).
Cause: a CAM tool bit builds a body with a sketch of the tool's profile (`Path/Tool/toolbit/models/base.py`: the bit object's
`BitBody` link); those sketches are new in the call, so step 2 names them. They are FreeCAD's, not the person's.
Fix: in step 2's list, leave out a sketch whose body is a tool bit's: with
`body = next((p for p in sk.InList if p.isDerivedFrom("PartDesign::Body")), None)`, skip when
`body is not None and any(getattr(q, "BitBody", None) is body for q in body.InList)`. (Step 3 should skip that body too if
it ever shows as a part; it did not in these runs.)

## (b) The model's expectation was wrong

1. **bim 3, 7 `bim_opening` "no wallCut_m3".** It is there in all four replies (0.6125, 0.36, 0.45, 0.2205), after `step`; the comparison script cut the answer at 260 characters. No mismatch.
2. **sheet 18 `sheet_read` "B1:D9 answered only two cells".** The call is `cells: ["B1", "D9"]`: a list of two cells, not a range. Two cells is the right answer (B1 8.4, D9 empty). No mismatch.
3. **surf 43 `surface_blend` WikiBlend 242.7.** `at` → StartParameter / EndParameter (0…1 of the edge's own parameter range, `RelativeToRealParameters`) and `size` → StartSize / EndSize are mapped right. FreeCAD's `BlendCurve::setSize(i, f, relative=true)` makes the tangent `f × the distance between the two points` long: the wiki's −5 gives 265 mm tangents on a 53 mm gap, and a degree-5 Bézier that swings wide. 242.7 is FreeCAD's answer for the wiki's own numbers (and "over the 53 mm chord", as the model literally asked).
4. **mesh 33 `meshobj_curvature` cube flatPercent 0.** The cube mesh has 8 points and every one is a corner; the reading is per point. "Cube even" (1244 points) would read mostly flat. The tool is right.
5. **draft 6, 10 upgrade → two wires; Ring length 125.66.** The model typed the tie lines' ends to six decimals: 1.13e-7 mm off the outer arc's ends, 9.5e-8 mm off the inner arc's. FreeCAD joins within 1e-7, which is exactly what came back (Arc25 + both ties = 36.18; Arc30 alone). Give the points with all decimals (as tests/test_draft.py does). Draft 10 follows from it.
6. **draft 24 `draft_label` "6495.19 mm²".** Draft writes `Quantity(area).UserString` (draftobjects/label.py), and the standard unit scheme shows that area as 64.95 cm².
7. **mesh 21 `meshobj_smooth` taubin "under 1%".** FreeCAD's TaubinSmoothing moves each point towards its neighbours' mean and back (`-(lambda + micro)`), in place, point after point, with equal weights, in (iterations + 1) / 2 pairs. I ran that algorithm on coarse UV spheres here: −21.6% on 138 points, −12.7% on 266. The live −20.2% on 153 points is FreeCAD's own behaviour; the tool passes lambda and mu as FreeCAD wants them.
8. **fem 39 `fea_shell` 2.688 MPa for "about 3.0 within 5%".** 3.0 is the larger bending stress; with the cross stress ν × 3.0 the von Mises value is 2.67. The reply is within 1% of that.
9. **fem 13, 14, 11 nearest-node readings** (380 for "roughly 432" at the root; 34.9 for "about 23" on the neutral axis). The sample's nearest node was 72 mm off the axis (the reply says nearestNodeMm), where bending adds about 31 MPa. Rough expectations, right answers.
10. **surf 34 WikiPatch area 98416 for a guessed 70000–85000.** A guess, not derived.
11. **pts 3 `points_info` spacing 0.338 for "0.5 to 0.8".** The tool reports the median gap to the nearest neighbour; for 6000 random points on 3142 mm² that is about 0.5 / √density = 0.36. The model expected the grid pitch.
12. **mesh 61 Cap area 117.1 for 125.7.** A 2 mm cap cut from a mesh made with 0.5 mm deflection: the facets are well inside the sphere there.
13. **bim 17 `bim_stairs` box height 2426.7 for "about 2600".** FreeCAD counts risers: 15 risers, 14 treads, the top tread one riser below the floor (the tool's own refusal text says so). Riser, going and Blondel matched.
14. **bim 61 `ifc_open` Ground floor elevation null for 0.** FreeCAD's `exportIfcAttributes` leaves out any attribute whose value is false, and 0 is. The tool reads what is in the file.
15. **bim 62 `ifc_find` Outer walls material null.** FreeCAD 1.1 does not export multi-materials (see a-3).
16. **core 56, 61 `measure_mass` answering in another form / not refusing.** With neither density nor material given, the installed add-on's mass service answers (the description says so), and it takes a body with no material as PLA.
17. **core 85, 87, 90 `robot_path` seconds 3.0 for "≈ 2".** FreeCAD's trajectory has an acceleration limit: 200 mm at 100 mm/s is 3.0 s, 500 mm 6.0 s, a 20 mm edge 0.894 s; all three fit an acceleration of 100 mm/s².
18. **core 83, 86 `robot_move` / `robot_run` not reaching a 100–200 mm move.** The start pose [0, −90, 90, 0, 0, 0] has axis 5 at 0: a wrist singularity, where FreeCAD's solver (100 steps) does not converge. The tool says so in its note. A model pose with axis 5 off zero would test the reach.
19. **cam 12, 13, 14, 33 (first run) and pts 30–34.** Followed from the pocket's failure (known, fixed, right in the re-run) and from the bunny file not being in the output folder.
20. **bim 27 classification "Ss_25_10_30".** Run before the known fix with the bare code; the re-run's file shows system Uniclass, code Ss_25_10_30.

## (c) Cannot tell

1. **mesh 32 `meshobj_curvature` on the fine sphere: tightestRadius 1.30, meanCurvature max 0.439** where every point should read near radius 10 (median 9.994 is right). Most likely the two pole points, where the standard mesher's triangles fan out and FreeCAD's per-vertex estimate goes wrong; I could not confirm it from source. A live check: `view_render { map: "curvature" }` on "Globe fine".
2. **cam 19 `cam_op` drill named "Drill" came out "Drill001".** FreeCAD renames a label another object holds; which object holds "Drill" in that document (the bit's body?) I could not see. `cam_edit { op: "Drill" }` still found it (by its internal name). `object_list` after `cam_tool_add` would show it.
3. **fem 27 `fea_solve` vonMisesMax "at": [534, 500, 500], "face": "Face4".** A point in the middle of the section is given the nearest face's name; not asked by the model. Whether a peak of 551 MPa inside a bar in plain tension (500 MPa) is a mid-side-node artefact I cannot say.
4. **core 113 `doc_open { recent }` without CoreDoc.FCStd.** The file was saved by doc_save a few calls earlier; whether FreeCAD adds a script's saveAs to the window's recent list is not something I found in source. The model allowed an empty list.

## Suspects, one line each

| suspect | settled as |
|---|---|
| bim_roof ridge 1732.1 (bim 16) | a-1, fixed |
| bim_opening no wallCut_m3 (bim 3, 7) | b-1: it is there |
| meshobj_project 16 for 6 (mesh 35) | a-6: FreeCAD's spur, cleaned in the tool |
| surface_blend 242.7 (surf 43) | b-3: mapping right, FreeCAD's sizing |
| meshobj_curvature flatPercent 0 on a cube (mesh 33) | b-4: right |
| draft upgrade two wires (draft 6) | b-5, and a-18: the tool now reports the gap |
| sheet_read "B1:D9" two cells | b-2: two cells were asked |
| health verdicts repeating / tool-bit sketches | H1, H2 above |
| doc_close landing on SheetTutorial | a-13, fixed |
| material_set / material_clear "not recomputed yet" | a-12, fixed in material_set |
| robot_new puma → KUKA | by design (a-20, text); the real fault there was tcp [0,0,0] (a-15) |

## Not covered by any answer I read

scad_import, scad_op, scad_code, scad_tidy (not run); points_crop specks / thin and the bunny import (no file); object_delete's
in-use refusal and doc_revert's check (wrong document after doc_close); sheet 0..19 and core 80..82 (by hand).
