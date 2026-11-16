# BIM, CAM and Points hardening: findings (77 tools)

All three workbenches were finished, in order: BIM (53 tools: groups "bim" 37, "bim_gaps" 16), CAM (15: "cam" 12, "cam_more" 3), Points (9). Nothing was run on FreeCAD here: every fix below is from reading FreeCAD's source, and each has a FreeCAD test that has not been run yet (`tests/test_bim_gaps.py` class `BimHardening`, 12 tests; `tests/test_cam.py` class `CamHardening`, 4 tests; `tests/test_more_families.py` `test_points_hardening`). The source checked out is tag 1.1.0; the Mac runs 1.1.3. Where that could matter it is said.

Files changed: `agentlink/families/bim.py`, `bim_more.py`, `bim_gaps.py`, `ifc.py`, `cam.py`, `cam_more.py`, `points.py`, `std_more.py` (points_structure only), `agentlink/data/tools.json` (the seven data-defined BIM tools), `agentlink/guides/bim.md`, `cam.md`, `points.md`, and the three test files. No new files (FILES unchanged). `health.py`, `protocol.py`, `tools.py`, `keep.py`, `runners.py`, `picks.py`, `fitting.py`, `millsim.py`, `pointfiles.py` untouched. Plain-Python suite: 681 passed, 279 skipped.

Descriptions: all 77 rewritten. Total length 13.7 KB before, 20.4 KB after (1.49x: BIM 1.6x, CAM 1.21x, Points 1.68x). Over the 1.3x aim because most originals were one line with no reply fields, units or traps; the long workflows went to the three guides. Say if they should be cut back further.

## BIM

Checked against FreeCAD 1.1 source: `src/Mod/BIM/Arch.py` (every make* signature), `ArchWall.py`, `ArchComponent.py`, `ArchStructure.py`, `ArchRoof.py`, `ArchStairs.py`, `ArchSpace.py`, `ArchBuildingPart.py`, `ArchWindow.py`, `ArchWindowPresets.py`, `ArchAxis.py`, `ArchFence.py`, `ArchFrame.py`, `ArchTruss.py`, `ArchCurtainWall.py`, `ArchPipe.py`, `ArchEquipment.py`, `ArchMaterial.py`, `ArchPanel.py`, `ArchRebar.py`, `ArchReference.py`, `ArchNesting.py`, `ArchCommands.py`, `ArchIFC.py`, `importers/exportIFC.py`, `importers/importIFC.py`, `Resources/ui/preferences-arch.ui` (via git show), `src/Mod/Draft/draftgeoutils/offsets.py` and `geometry.py`, `draftutils/params.py`; wiki `Arch_tutorial.md`, `Arch_Wall.md`, `Arch_Roof.md`.

### Bugs fixed (proved from source)

1. **bim_opening on a left- or right-aligned wall cut almost nothing.** `ArchWall.getExtrusionData` offsets a Left wall by `direction x normal`: going +X that is -Y, the right-hand side of the line (the line is the wall's left face; wiki Arch_Wall says the same of arcs). The tool put the opening on the other side, so the cutting box met the wall by 10 mm. The side is now right, and the wall's Offset is counted. The description of `align` said the opposite of FreeCAD and is corrected.
2. **bim_roof with a clockwise outline.** `ArchRoof.getPerpendicular` slopes each pane to the left of its edge, so the outline must run counter-clockwise (wiki Arch_Roof step 1). A clockwise one now sets FreeCAD's own `Flip` and turns the per-edge lists round with it. The reply gains `ridge` (from `Heights`) and `flipped`.
3. **bim_structure, a squat column or a stub beam was laid along X.** With no base, `ArchStructure.getExtrusionData` extrudes a Beam or Column along X whenever Length > Height. A column wider than it is tall, or a beam shorter than its width, is now built on a section face (new helper `prism`).
4. **bim_structure slab / footing from a clockwise outline went down instead of up.** The extrusion follows the face's normal, which follows the order of the corners. `Normal` is now set upward for outlines given as points. With `base` the sketch's own direction is kept (said in the guide).
5. **bim_grid: `length` was never applied, and the Y lines ran the wrong way.** `Arch.makeAxis(num, size)` takes the gap as its second input, not the lines' length; `Length` is now set. An axis set's lines run along +Y from x = 0, gap …; turned a quarter they ran along -X and never crossed the X set. The Y set is now moved so both cover 0 … length. This is what makes bim_structural_system find crossings.
6. **bim_fence: posts and panels misplaced.** `ArchFence.execute` reads post and section sizes off their bounding box's XMax / YMax and replaces the post's own placement. The post was centred on the origin, so FreeCAD saw half its size: panels overlapped the posts and the posts sat a quarter off the path. The post now stands on its corner and the panel is set in to the post's middle.
7. **bim_equipment `url` was dropped.** The property is `ProductURL`, not `Url`. `ifc` is now set through a helper that refuses a wrong type with near names instead of ignoring it.
8. **bim_material `color` did nothing.** It was stored under `Color`; `ArchMaterial.onChanged` reads `DiffuseColor` as "(r, g, b)". "#rrggbb" or "r, g, b" is now parsed and stored there. Objects that cannot carry a material are refused instead of skipped silently.
9. **bim_space `use` was ignored when wrong.** `SpaceType` is an enumeration; a value not in it was swallowed. Now matched in any case, and refused with near names.
10. **bim_nest `rotations` and `margin` were never used.** The nester reads the module's `ROTATIONS`; it has no margin in 1.1. Rotations are now set for the run and put back; `margin` is answered as not applied. Pieces that are not single flat faces, and a container that is not one face, are refused up front (FreeCAD only prints and stops).
11. **bim_remove_shape failed on every object it changed.** `Arch.removeShape` deletes the object and makes a new one; the reply then read the deleted object's label. Labels are now taken first.
12. **bim_structural_system with two structures.** `makeStructuralSystem` answers a list then, and naming it failed. Now one structure per call, refused otherwise.
13. **bim_edit join.** `Arch.joinWalls` keeps the *last* wall (it pops it), and its own delete removes a wall once per edge of its line, which fails on a wall of two or more stretches. The others are now removed here; the reply says which was kept.
14. **bim_edit subtract hid roofs and windows.** FreeCAD keeps those shown (`ArchComponent.hideSubobjects`); now the same.
15. **bim_curtain_wall panel counts.** FreeCAD divides each face of the base into `VerticalSections`; the tool counted them over the whole length, so a wall of several stretches got that many mullions on each.
16. **bim_truss pratt pattern string** did not match FreeCAD's `rodmodes` entry (it worked only through a fallback).
17. **bim_schedule { sheet } and bim_library / bim_trash reads.** The sheet is a change made by a tool declared read-only: now `changes=True` with `reads` for the plain call. bim_library search and bim_trash list are declared reads.
18. **bim_views note named a tool that does not exist** (`techdraw_page`); bim_section's note named `td_view` where `td_bim` is the one that takes a section plane.
19. **bim_covering** tried a boolean for every tile of a square as wide as the face's diagonal (four times the count its limit checked). Tiles clear of the face are now skipped before the boolean.

### Per tool

| Tool | Checked against | Fixed | Still doubtful / live check | Description |
|---|---|---|---|---|
| bim_wall | makeWall(baseobj, height, length, width, align, offset, face, name): 1.1 has `offset` before `face`; called by keyword. get_shape_normal: always up for our line | align wording (#1), refusals | a wall along a `base` sketch with construction lines | rewritten |
| bim_opening | ArchComponent.processSubShapes (Subtractions, and anything with Hosts naming the wall), ArchWindowPresets | #1; sill + height above the wall, negative at, non-wall refused | **It does not make an Arch window**: a box in the wall's Subtractions and a plain component typed Window / Door with a Hosts list. `preset` is checked but every preset builds the same frame. `makeWindowPreset(windowtype, width, height, h1, h2, h3, w1, w2, o1, o2, placement)` needs no window in 1.1 by my reading; switching to it is a behaviour change left for a decision. A wall moved after it was made is not followed | rewritten |
| bim_structure | makeStructure(baseobj, length, width, height, name), getExtrusionData, rebase, applyShape | #3, #4 | a `base` sketch drawn upside down still extrudes down | rewritten |
| bim_profiles | ArchProfile.readPresets | nothing | none | rewritten |
| bim_member | makeProfile, makeStructure with a profile base | refusal | a member shorter than its section's height may extrude by the section height (Length > Height rule with a base): not fixed | rewritten |
| bim_roof | makeRoof(baseobj, facenr, angles, run, idrel, thickness, overhang, name), ArchRoof.execute, getPerpendicular, makeRoofProfilsDic (90 = gable, run forced 0), flipEdges | #2; angles outside 0 … 90, all-gable, curved edges refused | the roof's box and volume; a `base` whose edges FreeCAD sorts in another order than drawn | rewritten |
| bim_stairs | makeStairs(baseobj, length, width, height, steps, name), makeRailing, ArchStairs.align | nothing | 1.1's makeStairs calls makeRailing: extra "Railing" pipe objects may appear and be counted by bim_quantities | rewritten |
| bim_space | makeSpace, ArchSpace.getArea (footprint through the centre of mass) | #9 | none | rewritten |
| bim_level (data) | makeFloor → makeBuildingPart; BuildingPart.onChanged moves children with MoveWithHost; preference default false | description only | **A level does not lift BIM components**: with the default preference walls keep their Z while plain shapes move by the elevation. Check on the Mac's preferences | rewritten |
| bim_building | makeBuilding, makeSite(objectslist) | refusal | none | rewritten |
| bim_list (data) | nothing to check | nothing | none | rewritten |
| bim_curtain_wall | makeCurtainWall(baseobj, name), property names | #15 | mullion sizes on a multi-stretch wall | rewritten |
| bim_rebar | makeRebar(baseobj, sketch, diameter, amount, offset, name) | refusals, a 2000-bar limit | whether FreeCAD's own rebar runs with the window up, or the plain-bars fallback | rewritten |
| bim_panel | makePanel(baseobj, length, width, thickness, placement, name) | refusal | none | rewritten |
| bim_pipe (data) | makePipe(baseobj, diameter, length, placement, name) | description | none | rewritten |
| bim_equipment (data) | makeEquipment(baseobj, placement, name), ArchEquipment properties | #7 | none | rewritten |
| bim_grid | makeAxis(num, size, name), ArchAxis.execute | #5 | crossings at a line's very end (grid lines start on the other set's first line) | rewritten |
| bim_section | makeSectionPlane(objectslist, name) | notes, refusals | none | rewritten |
| bim_material | makeMaterial(name, color, transparency), ArchMaterial.onChanged | #8 | none | rewritten |
| bim_schedule | **not** Arch.makeSchedule: Agent Link's own take-off (so the 1.1 Operation / Objects / Value columns do not apply) | #17, mass column in the sheet | none | rewritten |
| bim_export | exportIFC.export(exportList, filename, colors, preferences), getPreferences (metres) | refusals; missing IfcOpenShell says the install step | whether our plain windows export as IfcWindow / IfcDoor with their openings | rewritten |
| bim_import | importIFC.insert(srcfile, docname, …) | refusal | big files: a changing tool cannot be a job. **Wish**: declare it heavy in the family (HEAVY) so it is estimated and given a deadline; not done because I could not see how estimates are made | rewritten |
| bim_frame | makeFrame(baseobj, profile, name), Align / Rotation | refusals | none | rewritten |
| bim_truss | makeTruss(baseobj, name), rodmodes | #16, refusals | none | rewritten |
| bim_fence | makeFence(section, post, path), ArchFence.execute | #6 | post orientation along a bent path | rewritten |
| bim_covering | Arch has no makeCovering in 1.1.0 (built here) | #19, refusals | whether 1.1.3 has makeCovering (then FreeCAD's own object is used) | rewritten |
| bim_layers | makeMultiMaterial | skipped objects answered | a wall's layers as separate solids | rewritten |
| bim_ifc | ArchIFC.IfcTypes (spaced names), IfcProperties "pset;;type;;value" | IfcWall-style names understood, near names | none | rewritten |
| bim_quantities | component area properties | nothing | none | rewritten |
| bim_preflight | own checks | nothing | none | rewritten |
| bim_edit | ArchComponent.processSubShapes, joinWalls(walls, delete, deletebase) | #13, #14, loop refused | join of walls on sketches | rewritten |
| ifc_open … ifc_diff (6) | **not FreeCAD's NativeIFC (ifc_tools)**: IfcOpenShell's own API on a file held in the session. The family is absent without IfcOpenShell, so "how the tools say it is missing" is: they are not listed | ifc_edit with no filter or nothing to change refused; ifc_diff on missing files; refusals | IfcOpenShell is not installed here: none of the six could be imported, let alone run | rewritten |
| bim_component | makeComponent(baseobj, name, delete), cloneComponent | ifcType checked | none | rewritten |
| bim_reference | makeReference(filepath, partname, name); .FCStd, .ifc, .dxf | refusal | none | rewritten |
| bim_panel_out | makePanelCut(panel, name), makePanelSheet(panels, name) | non-panels refused | none | rewritten |
| bim_nest | ArchNesting.Nester | #10 | time on many pieces | rewritten |
| bim_ifc_brep | toggleIfcBrepFlag | nothing | none | rewritten |
| bim_views | Draft.make_shape2dview of a section plane | #18 | none | rewritten |
| bim_image_plane | Image::ImagePlane | refusal | none | rewritten |
| bim_library | own search | read declared (#17) | none | rewritten |
| bim_reextrude | makeWall / makePanel / makeStructure | refusal | none | rewritten |
| bim_rewire, bim_glue, bim_trash, bim_reorder | own code | refusals, list declared a read | none | rewritten |
| bim_remove_shape (data) | ArchCommands.removeShape | #11 | it colours non-box objects red through ViewObject | rewritten |
| bim_structural_system (data) | makeStructuralSystem(objects, axes, name), getAxisPoints | #12 | the count of copies (see bim_grid) | rewritten |
| bim_pipe_connector (data) | makePipeConnector(pipes, radius, name) | refusal | none | rewritten |

## CAM

Checked against FreeCAD 1.1 source: `src/Mod/CAM/Path/Main/Job.py`, `Main/Stock.py`, `Tool/Controller.py`, `Tool/toolbit/models/base.py`, `Tool/shape/models/*.py`, `Tools/Shape/*` (git ls-tree), `Op/Profile.py`, `PocketBase.py`, `Adaptive.py`, `Drilling.py`, `CircularHoleBase.py`, `Custom.py`, `Op/Gui/Array.py`, `Stop.py`, `PathShapeTC.py`, `Main/Gui/Fixture.py`, `Dressup/Tags.py`, `Boundary.py`, `DogboneII.py`, `Array.py`, `Post/Processor.py`, `Post/UtilsExport.py`, `Post/scripts/grbl_post.py`, `linuxcnc_post.py`, `Base/PropertyBag.py`, `Base/SetupSheet.py`, `PathScripts/PathUtils.py`; wiki `CAM_Walkthrough_for_the_Impatient.md`.

### Bugs fixed (proved from source)

1. **cam_post never wrote the work offsets.** In 1.1 the job's post-processor object (`PostProcessorFactory.get_post_processor(job, name).export()`) builds the list to post: each fixture, each tool change, the active operations in the job's order. The tool called the script's `export` directly, so `cam_setup { fixtures }` never reached the G-code (not even G54). It now posts through the job as FreeCAD's Post command does, with the script kept as the fallback. The job's `PostProcessorArgs` get `--no-show-editor` for the run (a post-processor opens an editor dialog when a window is up) and are put back afterwards; the old fallback overwrote them for good. **This is the riskiest change in the patch**: it changes what every posted file contains (a G54 line, tool changes as FreeCAD writes them). The reply gains `via`, `units`, `tools`, `fixtures`.
2. **cam_op adaptive `finish: true` always failed.** The enumeration is `Clearing | Profiling`; the tool set "Profile".
3. **cam_dressup tags ignored `count` and reset width / height.** `setup(obj, True)` generates FreeCAD's default count and puts the default sizes back; `generateTags(obj, count)` is the call that takes the count and the sizes just set.
4. **cam_tool_add dropped sizes in 1.1.** A bullnose's corner radius is `CornerRadius` (the tool wrote `TorusRadius` only), a drill's angle is `TipAngle`, a radius mill's is `CuttingRadius`. Each input now tries the names FreeCAD has used; one a shape has no place for is answered in `skipped`. The bit takes the tool's name as its label and is hidden as FreeCAD's own is.
5. **cam_library export wrote every tool as an endmill in 1.1.** The shape is in `ShapeID` there, which was not read. Import of an unknown shape or a record without a diameter is answered in `notAdded` instead of raising.
6. **cam_remove left a dressed operation behind.** Removing a dressup deleted only the outermost object, leaving the operation outside the job. Naming any member of a stack now removes the whole stack (and a boundary dressup's own stock).
7. **cam_job with a default stock template.** When the CAM preferences name a default stock, the job's stock has no margins and the tool's stock inputs were dropped without a word. FreeCAD's stock-from-base is now made instead, with a note if that fails.
8. **cam_setup heights.** No change in behaviour; the reply now says that operations following the setup sheet were recomputed (their heights are expressions on it), and an empty call is refused.
9. **cam_template_export's note** told the agent to use `cam_job { template }`, an input that does not exist.

### Per tool

| Tool | Checked against | Fixed | Still doubtful / live check | Description |
|---|---|---|---|---|
| cam_job | Job.Create(name, base, templateFile), setupStock, CreateFromBase, Controller.Create(name, tool, toolNumber, …) | #7, negative stock refused, reply has `model` | a job made without FreeCAD's Gui view provider shows as a plain object in the tree | rewritten |
| cam_op | each op's Create(name, obj, parentJob), Profile Side / Direction, PocketBase ClearingPattern (renamed from OffsetPattern in 1.1), findToolController | #2; side, stepOver, stepDown checked; enumeration values named in props refusals; the tool in refusals is the op's own | face names on the job's clone are the body's (by my reading); kinds mill_facing and flute are not in 1.1.0 | rewritten |
| cam_list | nothing to check | nothing | none | rewritten |
| cam_tool | tool controller properties | feeds must be over 0 | none | rewritten |
| cam_tool_add | ToolBit.from_shape_id(shape_id, label), attach_to_doc, shape parameter names per shape, shape file names (v-bit, thread-mill) | #4 | whether the shape assets load headless before the CAM workbench was opened | rewritten |
| cam_library | own JSON (not FreeCAD's .fctl) | #5; export declared a read | none | rewritten |
| cam_dressup | Tags.Create / setup / generateTags, Boundary, DogboneII, Array Create | #3; unknown props refused; a None from FreeCAD refused | the tag count can be one off (FreeCAD spreads them edge by edge) | rewritten |
| cam_setup | Job Fixtures / OrderOutputBy, SetupSheet offsets and expressions | #8 | none | rewritten |
| cam_edit | Custom.Create(name, obj, parentJob) | nothing | none | rewritten |
| cam_remove | job group handling | #6 | none | rewritten |
| cam_sim | own height map (millsim.py untouched) | description says what it is not | none | rewritten |
| cam_post | Processor.py: PostProcessorFactory, _buildPostList, WrapperPost.export, the editor dialog in UtilsExport and each script | #1 | the file's exact lines on 1.1.3; `SplitOutput` jobs (sections are joined into one file) | rewritten |
| cam_path | Path::FeatureArea / FeatureShape, ObjectArray, Stop, Fixture enumeration | props and fixture checked, non-paths refused; kind edges says why it is unavailable on 1.1 (the command is PathShapeTC there) | none | rewritten |
| cam_property_bag | PropertyBag.Create, addCustomProperty | types and names checked; the reply gives the name expressions use | none | rewritten |
| cam_template_export | templateAttrs, SetupSheet.templateAttributes / encodeTemplateAttributes | #9 | none | rewritten |

Units: FreeCAD's scripts post millimetres (`G21`) and feeds per minute unless the job's arguments say `--inches`; the reply reads the unit from the file.

## Points

Checked against FreeCAD 1.1 source: `src/Mod/Points/App/Points.pyi`, `PointsPyImp.cpp`, and via git show `Points.h`, `Points.cpp`, `PointsFeature.cpp`, `src/Mod/Points/Gui/Command.cpp`, `src/Mod/ReverseEngineering/App/AppReverseEngineering.cpp`; wiki `Points_Workbench.md`, `Points_Import.md`, `Points_Export.md`, `Points_Convert.md`, `Points_Merge.md`, `Points_Structure.md`.

### Bugs fixed (proved from source)

1. **A moved point cloud was read moved twice.** `Points::Feature::onChanged` sets the Placement as the kernel's transform, and the kernel's iterator applies it (`PointKernel::const_point_iterator::dereference`), so `obj.Points.Points` are already where the cloud stands. `array_of` applied the Placement again. Every tool that reads a cloud (info, crop, fit, export, merge, mesh) was wrong for any cloud whose Placement is not identity. Clouds made by these tools have identity placement, which is why it did not show.
2. **points_export read back only text formats, and .pcd through the text reader.** Every format is now read back with its own reader; the reply gains `maxError`.
3. **points_import `scale: 0`** put every point on the origin; refused now. NaN points are dropped.
4. **points_crop with nothing to do** rewrote the cloud unchanged, and `outside: true` alone emptied it; both refused now, as is `near` without `radius` (it raised a type error).
5. **points_merge with a cloud named twice and `remove: true`** failed after the new cloud was made.

### Per tool

| Tool | Checked against | Fixed | Still doubtful / live check | Description |
|---|---|---|---|---|
| points_import | Points.addPoints (vectors or tuples), Points.insert for E57 | #3, refusals | E57 (needs the library) | rewritten |
| points_sample | Mesh Topology, Shape.tessellate | refusals | none | rewritten |
| points_info | #1 | #1 | none | rewritten |
| points_crop | #1 | #1, #4 | none | rewritten |
| points_fit | approxSurface keywords (Points, UDegree, VDegree, NbUPoles, NbVPoles, Smooth, Weight, Grad, Bend, Curv, Iterations, Correction, PatchFactor, UVDirs) and its "too less data points" rule | points < poles x poles refused first; a 200000-point limit on surface (my choice, not measured); zero axis hint refused | the surface fit's time on large clouds | rewritten |
| points_merge | #1 | #1, #5 | none | rewritten |
| points_mesh | poissonReconstruction exists only with PCL (HAVE_PCL_SURFACE) | refusals, a 2000000-triangle limit | whether the Mac's build has PCL | rewritten |
| points_export | #1 | #1, #2 | none | rewritten |
| points_structure | Points::Structured; FreeCAD's own command (CmdPointsStructure) | refusal names widths that divide the count | **It is not FreeCAD's Points Structure**: that command sorts the points onto an XY grid seen along Z (NaN where a cell is empty); the tool lays the existing order out as rows. Left as it is (a rewrite would be a new feature); the description says what it does | rewritten |

## Could not do / wishes

- **Nothing was run on FreeCAD or IfcOpenShell.** The 17 new FreeCAD tests are written from source; some expected numbers are my arithmetic (wall volumes, roof ridge, grid crossings, fence post count).
- **bim_opening does not use FreeCAD's windows.** A decision for the owner: keep the plain frame, or move to `Arch.makeWindowPreset` with `Hosts` (real presets, parametric, IFC openings as FreeCAD writes them).
- **health.py**: no wish.
- **keep.py / HEAVY**: bim_import, bim_covering (tiles), bim_nest and cam_op (adaptive, 3D) can be long and are changing tools; none is declared heavy. I did not declare them because I could not check what an estimate would be made from.
- The model files' expected values that depend on FreeCAD's own algorithms (roof box, stair box, tile counts, tag counts) are marked "about".

## Test models

- `bimcam-bim-model.json`: 69 calls, 47 tools. A small house with the Arch tutorial's stated sizes (the tutorial itself builds from a DWG and gives no typed plan). It exercises fixes 1 to 9 and 11 to 15 directly (right-aligned walls with openings, a clockwise slab and roof, a squat column, the grid with a structural system, the fence).
- `bimcam-cam-model.json`: 34 calls, 18 tools. The walkthrough's block with a pocket, tool number 4 at 2 mm/s and 2000 rpm, a Profile and a Pocket (step over 50 %, pattern Offset), posted for linuxcnc and grbl.
- `bimcam-points-model.json`: 35 calls, 11 tools. A cylinder, a sphere and a plate sampled, written and read back, and fitted; the wiki's sample cloud (FreeCAD/Examples: Point_cloud_ExampleFiles/PointCloud-Data_Stanford-Bunny.asc, 397 points in metres).
