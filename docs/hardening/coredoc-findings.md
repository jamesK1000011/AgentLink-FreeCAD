# Core document, measure, material, inspection, OpenSCAD, Robot and window tools: findings (85 tools)

Groups: "doc" (12), the document tools of "std_more" (13, plus scad_tidy and robot_tool which live in that file), "measure" (6), "material" (4), "inspection" (6), "openscad" (5 + scad_tidy), "robot" (6 + robot_tool), and the window tools "app" (17), "dev" (4), "unattended" (3), "notes" (7).

Checked against FreeCAD 1.1 source (tag 1.1.0; the Mac runs 1.1.3): `src/App/Document.cpp`, `DocumentPyImp.cpp`, `Document.pyi`, `DocumentObject.cpp`, `DocumentObject.pyi`, `PropertyContainerPyImp.cpp`, `PropertyStandard.cpp`, `Link.h`, `LinkBaseExtensionPyImp.cpp`, `src/Base/Color.h`, `src/Gui/ApplicationPy.cpp`, `Command.cpp`, `Command.pyi`, `CommandView.cpp`, `CommandFeat.cpp`, `Selection/Selection.cpp`, `ViewProviderGeometryObjectPyImp.cpp`, `src/Mod/Part/Gui/ViewProviderExt.cpp`, `ViewProviderPartExtPyImp.cpp`, `src/Mod/Measure/App/Measure*.cpp`, `src/Mod/Material/App/*.pyi`, `src/Mod/Inspection/App/InspectionFeature.cpp`, `src/Mod/OpenSCAD/importCSG.py`, `exportCSG.py`, `OpenSCADUtils.py`, `OpenSCADFeatures.py`, `src/Mod/Robot/App/Robot6Axis.cpp`, `RobotObject.cpp`, `TrajectoryDressUpObject.cpp`, `Edge2TracObject.cpp`, `Simulation.cpp`, `WaypointPyImp.cpp`, `Gui/CommandTrajectory.cpp`, `KukaExporter.py`; wiki `App_Link.md`, `Std_LinkMake.md`, `Std_ToggleFreeze.md`, `Robot_API_example.md`, `Robot_Edge2Trac.md`.

Nothing was run on FreeCAD here. Every fix is from reading the source; the FreeCAD tests added for them (in `tests/test_doc.py`, `test_measure.py`, `test_inspection.py`, `test_more_families.py`) have not been run. Plain-Python suite after all changes: 681 passed, 270 skipped (the 8 new FreeCAD tests among the skipped).

Files changed: `agentlink/families/` `doc.py`, `std_more.py` (my tools only), `measure.py`, `material.py`, `inspection.py`, `openscad.py`, `robot.py`, `app.py`, `dev.py`, `unattended.py`, `notes.py`; `agentlink/guides/` `doc.md`, `measure.md`, `material.md`, `inspection.md`; four test files. No new files (FILES unchanged). `picks.py`, `refs.py`, `materials.py` untouched (no signature changed). Not touched: `tools.py`, `protocol.py`, `health.py`, `keep.py`, `gui_link.py`, `gui_input.py`, `supervise.py`, `panel.py`.

## The coordinator's two live findings (doc_close)

1. **doc_close by internal name.** The old code did compare `x.Name == r`, so from source I cannot say why "PDTutorial_recovered" missed: either the document's Name was not what session_state had answered (the two answers came from different FreeCAD processes, hidden and window, or the session held a stale document), or the name differed in a way the refusal hid, since it listed labels only. Now: matched by the key FreeCAD lists it under, its Name, its Label, then any case, then its file, then the session's own document under the name session_state gives. A label two documents share is refused with both as "Label (Name)". The not-found refusal lists every open document as "Label (Name)" wherever the name differs or a label repeats, so the next miss shows the real names. doc_switch finds and lists the same way. Tests: `test_close_by_name_and_shared_label`. **Needs the live check**: close a recovered document by the name session_state answers.
2. **Closing without saving.** The description now says there is no save input, that a changed document is refused with nothing closed, and that `discard: true` closes without saving and loses the changes. The refusal names both ways out. The reply lists `discarded` with a note. Test: `test_close_says_what_was_lost`.

## Bugs fixed (proved from source)

1. **robot_run always answered "reaches all".** `RobotObject::onChanged(Tcp)` calls `Robot6Axis::setTo`, which returns false and changes nothing when the pose cannot be solved; the return is ignored and the `Tcp` property keeps the value asked for. The tool compared `o.Tcp` with what it had just set, so the miss was always 0 (and FreeCAD never writes `Error`). Now an axis is set to itself after each sample, which makes FreeCAD work `Tcp` out from the axes it really holds. robot_move already did this by accident (its ±180° wrap).
2. **robot_trajectory dress with ypr did nothing.** FreeCAD's enumeration is `AddOrintation` (its own misspelling); the tool set `AddOrientation` inside a try/except, so `AddType` stayed `DontChange`. With both move and ypr it set `UseOrientation`, which drops the move. Now: move → `AddPosition`, ypr → `AddOrintation`, both → `AddPositionAndOrientation`; `add` is checked and the right spelling accepted.
3. **robot_path edges failed on every call.** The type is `Robot::Edge2TracObject`; the tool asked for `Robot::Edge2TrajectoryObject`. Now the real name first. A face given as an edge is refused.
4. **robot_export full: true crashed.** `KukaExporter.ExportFullSub` only prints in 1.1, so no file was written and the tool failed opening it. Now refused as unavailable. The compact form writes every waypoint as LIN: said in the description.
5. **robot_new called the default robot a "Puma 560".** With no kinematics file FreeCAD's robot is its built-in KUKA IR 500 table (`Robot6Axis.cpp`). Reply and label now say so; `puma` is still accepted.
6. **robot tool point.** `RobotObject` never uses its `Tool` or `Base` properties in the kinematics; only FreeCAD's Simulation applies `Tool` (position × Tool⁻¹). The description promised that tcp meant the tool point. robot_move tcp and robot_run now apply `Tool` the way Simulation does, and the reply's tcp is the tool point (`flange` beside it when a tool is set). `Base` is stored only: said in the description. robot_move home uses the `Home` list when it has six values (as Robot's Restore home does), else zeros.
7. **measure_mass refused a recorded library or custom material.** It took only the stock keys, though material_set's note says measure_mass reads the material. It now reads the card's density (`material.card`), by id or name, recorded or given. material_set answers `mass_g` (volume × density).
8. **measure_keep.** FreeCAD 1.1 has no `Measure::MeasureDiameter` (kept, refused with what to use). Each kind's accepted elements are now checked first from each type's `isValidSelection`: radius takes a circular edge, not a cylinder's face; a whole object or a point is refused (FreeCAD answers "No geometry element picked"). A measurement that comes out invalid is removed and refused with FreeCAD's reason instead of answering a stale value.
9. **object_set on a percent property.** `App::PropertyPercent` is an integer; the tool sent a float, which FreeCAD refuses. `PropertyLinkHidden` and `PropertyXLink` (a link's LinkedObject) now take an object name as plain links do. Links to faces or edges are refused with the tool that sets them. `Immutable` counts as read-only.
10. **doc_save under a new name relabels the document** (`Document::saveAs` sets Label to the file's base name). Not a tool bug, but the reply hid it: now `label`, `labelWas` and a note. This is likely part of live finding 1 (a label that changed under the agent).
11. **recompute { force } did not get past the document's skip-recompute switch** (`Document::recompute` returns 0 unless its own force argument is set). Now passes it. A 0 with the switch on is said; objects still touched are listed.
12. **doc_revert left the reopened document marked changed** (FreeCAD 1.1 marks a document touched on opening; doc_open already cleared it, doc_revert did not), so the next doc_close asked for discard. Now cleared the same way.
13. **doc_merge** took a path relative to the process, not the session's folder as every other reader; a non-.FCStd or unreadable file raised raw. Now `paths.local`, an extension check, FreeCAD's error wrapped, and a count with errors.
14. **object_appearance: transparency lost with face colours.** In 1.1 setting `DiffuseColor` resets every face's transparency from the colours' fourth value, so a transparency set in the same call was wiped. Transparency is now set after the faces.
15. **insp_update on an inspection made in FreeCAD's own workbench** raised (no tolerance properties). They are added when missing. Everything is now checked before anything is set; a tolerance past the search radius is refused as in insp_run; nominals are type-checked.
16. **object_group.** remove or dissolve of a group that does not exist made an empty group first; now refused. remove of an object not in the group is refused. count, at and step of link are checked. dissolve leaves an App::Part's Origin to go with it.
17. **selection read the wrong document.** `getSelectionEx()` with no name answers for the document in front; it now names the session's document. A wrong name is refused before the selection is cleared.
18. **cmd_run on an inactive command did nothing and said nothing** (`Command::_invoke` runs only `if (isActive())`). `Command.get(name).isActive()` is read first and an inactive command refused with the selection, the workbench and what to do. The reply carries `wasActive`, `objectsAdded` and a note when the document in front is not the session's.
19. **workbench { activate }** did not check that FreeCAD switched (`activateWorkbench` answers a bool); a workbench that fails to load is now refused.

## Changed without proof (needs the live check most)

- **robot_run after fix 1.** `tests/test_more_families.py::test_robot` expects "reaches all" on a 300 mm line near the pose robot_move reached. It should still hold; if the solver cannot follow from sample to sample it will now say so, where before it could not. The default robot's tool point at axes [0, -90, 90, 0, 0, 0] is worked out here as [1825, 0, 2400] from the DH table (KDL's `Frame::DH` taken as the standard form): **not verified**.
- **App::Link placement.** Descriptions say a link's placement stands in for the original's own (LinkTransform false), from the wiki; the model's unlink step checks it.
- **object_freeze.** The wiki says the frozen state is not saved with the file; whether object_set on a frozen object is refused by the health check or passes is not known (the window script checks it).
- **selection { clear: false } with no objects** used to clear anyway; it now reads the selection (with picked faces and edges). A small addition, used by the window script as its read-back.
- **Std_ToggleVisibility / menu titles** in the window script are 1.1.0's.

## Per tool

D = description rewritten. All 84 changed descriptions name the reply's key fields; app_restart's was left as it was.

| Tool | Checked against | Fixed | Doubtful / live check | D |
|---|---|---|---|---|
| doc_new | `Application.newDocument`, name sanitising | note names doc_switch | name given when one of that name is open | yes |
| doc_close | `closeDocument`, `listDocuments` | live findings 1, 2 | the recovered-document case | yes |
| doc_open | `openDocument`, touched-on-open | refusals; note when already open | none | yes |
| doc_save | `Document::saveAs`, `save` | #10 | none | yes |
| object_list | Name / Label (`DocumentObject.cpp`) | none | none | yes |
| object_get | `getPropertyStatus`, `getEditorMode` names | hidden, choices, empty filter refused | editor ReadOnly is a GUI hint: some such properties can be set from Python | yes |
| object_set | `PropertyStandard.cpp` setters, quantities from strings | #9 | enumerations by index are not taken | yes |
| object_delete | `Document::removeObject` (no dependency check) | refusal | none | yes |
| object_rename | Label uniqueness, `DuplicateLabels` preference | refusal names the holder; FreeCAD's own relabel said | with duplicate labels allowed the tool still refuses | yes |
| object_group | GroupExtension, App::Part, App::Link | #16 | none | yes |
| recompute | `DocumentPy::recompute(objs, force, checkCycle)`, returns | #11 | none | yes |
| import_file | `Part.Shape.read`, Mesh, importers by extension | refusals | STEP colours and names are not read (said) | yes |
| doc_graph | OutList / InList | none | none | yes |
| doc_info | Document properties | id / uid and non-text refused | it is not flagged as a changing tool | yes |
| doc_merge | `DocumentPy::mergeProject` | #13 | label clashes | yes |
| doc_revert | `restore` vs close and open | #12; refusal | none | yes |
| doc_save_all | `save` | none | none | yes |
| link_make | `PropertyXLink`, `ElementCount`, wiki | count and element checked; reply gives placement and elements | element names of an array (`ElementList`) | yes |
| link_edit | `importLinks`, `setLink` | a link to itself refused; shapeless unlink refused | import / import_all not exercised | yes |
| object_align | none in FreeCAD (own least-squares fit) | refusals | none | yes |
| object_appearance | `ViewProviderPartExtPyImp.cpp`, `Color.h` (fourth value is alpha in 1.1) | #14; empty call refused | on FreeCAD 1.0 the fourth value was transparency: faces would come out clear | yes |
| object_duplicate | `copyObject(object, recursive, return_all)` | none | none | yes |
| object_freeze | no Python freeze in 1.1 (`DocumentObject.pyi`), `Std_ToggleFreeze`, `RecomputesFrozen` | refusal, notes | see above | yes |
| text_document | App::TextDocument | none | none | yes |
| units_convert | `Units.Quantity` | refusals | offset units (°C) are not FreeCAD's | yes |
| shape_query | own code | limit checked | none | yes |
| measure | own code (`distToShape`) | the same thing twice refused | none | yes |
| measure_keep | `Measure*.cpp` `isValidSelection`, `execute` | #8 | MeasureArea's accepted face types | yes |
| measure_mass | Shape.Mass is volume; `material.card` | #7 | none | yes |
| section | own code | tolerance, maxPoints checked | none | yes |
| clearance | own code | refusal | none | yes |
| material_list / get / set / clear | `MaterialManager.pyi`, `Material.pyi` | refusals, limit, mass_g, hadNone | `getPhysicalValue` return types on 1.1.3; ShapeMaterial in the window's panel | yes |
| insp_run | `InspectionFeature.cpp` (sign, FLT_MAX, radius, placement) | refusals; Thickness is unused by FreeCAD 1.1: said | point-cloud actuals and placement | yes |
| insp_update | same | #15 | none | yes |
| insp_read / insp_list / insp_export | own reading | none | none | yes |
| insp_faces | own code | body without faces refused; nothing in reach refused | none | yes |
| scad_status / import / code / export / op | `importCSG.py`, `exportCSG.py`, `OpenSCADUtils.py` | refusals; shapeless objects refused | `importCSG` fixes its `gui` flag at import time, so the tool's GuiUp switch does not reach it once imported; `exportCSG` prints to stdout | yes |
| scad_tidy | `replaceobj.py`, `expandplacements.py`, `OpenSCADFeatures.py`, `removesubtree` | refusals (no objects, tolerance values, replace of a non-child, loops) | expand_placements | yes |
| robot_new | `Robot6Axis.cpp`, `RobotObject.cpp` | #5, #6; kinematics path relative to the session's folder | whether 1.1.3 ships the KUKA files | yes |
| robot_move | `onChanged`, `setTo` | #6; one of axes / tcp / home | see above | yes |
| robot_path | `WaypointPyImp.cpp`, `Edge2TracObject.cpp` | #3; refusals | none | yes |
| robot_run | `Simulation.cpp` | #1, #6 | see above; a trajectory's own Base is still applied, which FreeCAD's Simulation does not do | yes |
| robot_trajectory | `TrajectoryDressUpObject.cpp` | #2 | none | yes |
| robot_export | `KukaExporter.py` | #4 | none | yes |
| robot_tool | `ViewProviderRobotObject.cpp` (ToolShape, ToolBase: drawing only) | refusal, note | none | yes |
| pref_get / set / reset / pack / import | parameter groups | pref_reset answers notSet; refusals | none | yes |
| cmd_list | `Command.pyi` | none | none | yes |
| cmd_run | `ApplicationPy::sRunCommand`, `Command::_invoke` | #18 | Python commands whose IsActive raises are run as before | yes |
| menu_list / menu_run | Qt actions | refusals | none | yes |
| selection | `sGetSelectionEx(documentName, resolve, single)` | #17 | see above | yes |
| show | ViewObject.Visibility | none | none | yes |
| window_snapshot / snapshot_latest / snapshot_list | own code | refusal | none | yes |
| workbench | `activateWorkbench` returns bool | #19 | none | yes |
| app_install | own code | none | none | yes |
| app_restart | own code | none | none | no |
| addon_test / gui_input / gui_unstick | own code | refusals | none | yes |
| live_run | own code | the reset gotcha is in the description; the not-found refusal names reset | none | yes |
| addon / doc_switch / queue_go | own code | refusals; doc_switch finds any case and lists label (name) | none | yes |
| note_add / list / answer / done / delete | own code | refusals | none | yes |
| steps_list / steps_render | own code | width and height checked | none | yes |

## Descriptions are over the 1.3x aim

Measured over the 85 tools: 23.3 KB before, 43.5 KB after (1.87x): doc and std_more 5.6 → 11.2 KB, measure 2.3 → 3.9, material / inspection / OpenSCAD / Robot 4.7 → 11.0, window tools 10.8 → 17.4. Many originals were one line with no reply fields or gotchas (doc_merge 69 characters, doc_save_all 43). Say if they should be cut back; the long workflows are already in the guides.

## Wishes for files I may not edit

- **tools.py (session_state)**: when it answers `document`, answer `label` beside it always, and say `where`; live finding 1 needed both to be told apart.
- **tools.py / protocol.py**: a `reads` entry for `selection` (`clear: false` with no objects is a read), and `doc_info` with nothing to set is a read too.
- **health.py**: a frozen object stays touched after a recompute; if the health check flags touched objects, frozen ones should be named as frozen, not as a problem.
- **gui_link.py**: none.

## Test models

- `coredoc-model.json`: 114 calls, 56 tools (all 54 headless tools of sections 1–3 plus part_primitive and export as helpers), 23 expected refusals. One small part: a 40 × 30 × 20 box and an r5 × 20 cylinder. Known numbers: volumes, unit conversions, link placements, mass 204.0 g from a custom density, an inspection of the box against a copy moved 0.5 mm (max +0.5, min −0.5), the box written as CSG and read back at 24000 mm³, the default robot's tool point and an unreachable path.
- `coredoc-gui-model.json`: a live script in `scripts/live` format: 15 steps, 78 calls, 101 machine checks, from the reset document. It touches every window tool except four that cannot be a step (live_run is the runner; app_restart ends the replay; pref_import and queue_go need the person's word), which are in `byHand` with what a pass looks like.
