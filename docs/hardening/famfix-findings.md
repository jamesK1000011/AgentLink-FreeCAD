# Family faults from the window reviews (famfix)

FreeCAD 1.1.3 source read for each item (Mod/Fem, Mod/TechDraw, Mod/CAM, Mod/BIM, Mod/PartDesign,
Mod/Mesh, App, Gui). Inputs: window-td-cam-findings.md, window-bim-findings.md,
window-draft-surf-fem-mesh-findings.md, echo2-findings.md (P4). No FreeCAD here: nothing below is
proven live. "Echo" items are listed for the echo agent at the end.

## 1. FEM: "RuntimeError: Cannot add static property" in makeMeshGmsh

- Cause (FreeCAD's, set off by Agent Link's window observer). `ViewProviderFemMesh`'s constructor
  (src/Mod/Fem/Gui/ViewProviderFemMesh.cpp 191-221) sets `ShapeAppearance` and `Transparency`
  between its `ADD_PROPERTY` calls. A view provider's change is signalled to every Python window
  observer (src/Gui/ViewProvider.cpp 588-594), and FreeCAD asks the view for the property's name
  first (src/Gui/DocumentObserverPython.cpp 225). That lookup merges the class's static property
  table (src/App/PropertyContainer.cpp 437-479, `parentMerged = true`). The next `ADD_PROPERTY`
  (`BackfaceCulling`) is then a name the merged table lacks: "Cannot add static property"
  (PropertyContainer.cpp 420-423). The table stays short for the rest of the session, so every
  later FEM mesh view (Gmsh, Netgen, result mesh) fails too. Agent Link's change watch
  (agentlink/changes.py `_Gui.slotChangedObject`, armed during each changing call) is such an
  observer. I scanned every view provider constructor in src/Gui and src/Mod/*/Gui: this one is the
  only one with a set between two `ADD_PROPERTY` calls.
- Why "first study works, later ones fail": it is the first FEM mesh view made in the session while
  the watch is armed that breaks the table. A session where a FEM mesh was made before (by hand, or
  before the watch) has a whole table and never fails. In the FEM run, call 9 (`fea_solve`) most
  likely already fell back silently: `_solve_fem` (strength.py 810-826) removes what the route made
  and the own deck solves (solvedBy says so). That also explains item 2. Call 24 (`fea_native`) had
  no fallback, and its RuntimeError reached the Report view (the picture at 030 is the first one
  after call 24).
- Change: `strength.fem_views_ready(doc)` (strength.py 139): once a session, with Agent Link's
  window observer taken off, it makes and removes a `Fem::FemMeshObject` in the document, so the
  table is whole; the observer is put back in a `finally`. If the table is already short, it is a
  refusal (unavailable) that says to restart FreeCAD (`FEM_VIEWS_BROKEN`, strength.py 128).
  Called by the FEM route before it makes anything (strength.py 858; a refusal there becomes a
  route failure, so `fea_solve` still solves by the own deck), first in `fea_native`, and first in
  `fem_mesh { netgen }` (fem_more.py `_fem_views_ready`). `native_mesh` (strength.py 1463) answers
  the same refusal if makeMeshGmsh still raises it. Descriptions of fea_solve and fea_native say so.
- How sure: high on the mechanism (read line by line in the 1.1.3 source); not seen live.
- The real fix is in changes.py (not mine): a Python Gui observer with `slotChangedObject` will
  always do this to a class first built while it listens. Worth telling FreeCAD upstream too.
- Live check: restart FreeCAD (the running one may have the short table), then the FEM model
  `docs/hardening/models/sheetfem-fem-model.json` calls 0-9 and 24. Call 9: `solvedBy` begins
  "FreeCAD's FEM (Box strength (fea_solve)"; call 24 answers `analysis "Box native"` with Mesh in
  `objects`; `report_read` shows no "Cannot add static property".
- Test: tests/test_famfix.py `FemViews` (observer off then on, once a session; the refusal; no
  window; the route and the entries' order).

## 2. FEM: no Analysis, constraint or result object in the tree

- Cause: by design, not hidden. `fea_setup`, `fea_hold`, `fea_load` keep the study as Agent Link's
  data with the document (`store.write`, strength.py `_save`): no FEM objects. `fea_modes`,
  `fea_buckle`, `fea_heat`, `fea_shell` run Agent Link's own deck: files in the out folder and the
  answer, nothing in the tree. `fea_solve`'s FEM route makes "Box strength (fea_solve)" in the
  user's document, but here it failed (item 1) and was taken out again. The solver buttons had
  colour because `fea_native` (call 24) had made an Analysis before its mesh failed.
- Change: the descriptions say it (fea_setup: no FEM objects, fea_native builds them; fea_modes,
  fea_buckle, fea_heat: results are the answer and files); the replies of fea_modes, fea_buckle and
  fea_heat carry `kept`: "Its results are the answer and files in the out folder (files): it makes
  no FEM objects in the document's tree."
- How sure: high.
- Live check: after item 1's check, call 9: the tree has "Box strength (fea_solve)" with
  CalculiX, Material, Mesh, Fixed, Force and CCX_Results. Call 30 (`fea_modes`) answers `kept`.

## 3. TechDraw

### 3a. Datum, leader, weld, cosmetic line placed upside down

- Cause: techdraw.py `to_paper` (old 308-311) and the entries took the view's indexed geometry
  (`getVertexByIndex`, `getEdgeByIndex`) as y down. In FreeCAD 1.1.3 it is y up and unscaled:
  `DrawUtil::invertY(vert->point()) / scale` and `mirrorShapeVec(edge, 0, 1/scale)`
  (src/Mod/TechDraw/App/DrawViewPartPyImp.cpp 860-900; the stored geometry is y down, as
  `getVisibleEdges` returns it). `frame_of` already fitted the right y direction (`sy`) to resolve
  references, and `anchor_at` (detail, right in the picture) used it; `to_paper` and the steps that
  negate `p[1]` (td_datum, td_leader, td_weld, td_balloon, `_canon` for cosmetic edges) did not.
  Dimensions attach by reference, so they were right.
- Change: `to_paper` (techdraw.py 322) turns the point to paper y down by the frame's `sy`; new
  `flip_y` (1281) does the same for td_cosmetic's centerline and thread points (worked out on the
  indexed edges); `cut_line` (1097, td_export's section line) likewise. The frame's search order is
  unchanged (comment at 280 explains the 1.1.3 reading).
- How sure: high for 1.1.3 from the source; the fit makes it hold for either release.
- Live check: the TechDraw model (asmtd-techdraw-model.json) calls 42, 46, 48, 52, then
  `view_snapshot`: Datum A on the bottom edge, the leader from the top-left corner, the weld leader
  from the bottom-right, the cosmetic line from bottom-left to top-right.

### 3b. td_balloon on the detail view

- Cause: `DrawViewBalloon` keeps `OriginX/Y` and `X/Y` in the parent view's unscaled frame
  (src/Mod/TechDraw/Gui/QGIViewBalloon.cpp 569-575: over `getScale()`). The entry put paper mm
  there, so at scale 2 the balloon sat twice as far out — on Detail B. `SourceView` was PlateTop.
- Change: the entry divides by the view's scale (tools.json td_balloon); `at` is said to be paper
  mm. Test: test_famfix `test_the_balloon_in_the_views_unscaled_frame`.
- Live check: call 45, then `object_get { object: "Balloon" }`: SourceView PlateTop, OriginX 30,
  OriginY 20 (the corner (60,40) of a 60 x 40 plate about its centre).

### 3c. td_centermarks draws nothing

- Cause: by design until now: drawn by td_export only (MARKS_PROP).
- Change: `native_marks` (techdraw.py 1290) also switches FreeCAD's own centre marks of each view
  on or off (`ViewObject.ArcCenterMarks`, src/Mod/TechDraw/Gui/QGIViewPart.cpp 476-500): a small
  cross at each centre, not the chain lines. Rows answer `window`.
- Live check: call 38 then a zoomed `view_snapshot`: crosses at the hole centres.

### 3d. td_weld: a bare leader

- Cause: by design until now (WELD_PROP, drawn by td_export).
- Change: `native_weld` (techdraw.py 1324) makes FreeCAD's own `TechDraw::DrawWeldSymbol` on the
  leader as TaskWeldingSymbol.cpp does (createWeldingSymbol, updateTiles): AllAround, FieldWeld,
  TailText, and on the arrow-side tile (row 0) / other-side tile (row -1) the AWS symbol
  (`Mod/TechDraw/Symbols/Welding/AWS`: fillet, Square, V, plug, bead) and size / length texts. Kinds
  FreeCAD has no symbol for show their words only; the reply's `window` says which.
- How sure: medium. Not sure which of Up/Down FreeCAD's own users pick for row 0; I chose "Up" for
  row 0 because QGITile draws row 0 above the line (QGITile.cpp 137-163).
- Live check: call 48, then `view_snapshot` zoomed on the leader's end; `object_get { object:
  "WeldSymbol" }` and its two `TileWeld` objects (SymbolFile, LeftText "5"). If the symbol hangs
  upside down, swap the `row == 0` test in `native_weld`.

### 3e. "FloatingPointError: Cannot determine diagonal length of invalid bounding box"

- Cause: techdraw.py `resolve_ref` (now 443) asked the source compound's `DiagonalLength`; an empty
  or not yet computed source has an invalid box. `frame_of` did not look at the box.
- Change: new `box_ok` (techdraw.py 311); `frame_of` (269) gives no frame for an invalid box, so
  every reference answers the existing refusal: "{view} has no geometry yet: its bodies are empty or
  hidden, or its lines are still being worked out — td_list shows its edge count; recompute, then
  again." `draw_arch` skips such shapes.
- Live check: the TechDraw model call 19 (`td_export`) with the report view read after it.

## 4. CAM

- Paths computed: yes. `cam_op` recomputes and refuses with nothing kept when the op makes no cutting
  moves; the dressup the same. Not a tool fault.
- No toolpath drawn: not settled from code. The job and ops are made with CAM's App-only `Create`
  (Path/Main/Job.py 816, Path/Op/*.py Create), not the GUI's `Path.Main.Gui.Job.Create` (1702-1717)
  that attaches CAM's view providers; the ops keep the default `PathGui::ViewProviderPathPython`,
  which draws the path. Most likely the green lines are inside the opaque stock or the clone, or the
  ops are hidden. Echo item; probe below before any tool change.
- "EdgeWalker has no edges to load": from call 10, `cam_op { kind: pocket, faces: ["Face1"] }`,
  which the tool rightly refused ("no cutting moves; nothing kept"). FreeCAD's PocketShape prints
  the traceback itself while computing. The refusal is right; the Report view line is echo's.
- cam_sim: by design Agent Link's own height map; it answers a PNG and draws nothing in FreeCAD.
  Echo item: show the PNG or say it in the caption.
- Dressed op at the document root, hidden: FreeCAD's dressup GUI makes the dressup claim its base;
  without CAM's GUI view providers the base shows at the root. Hidden is FreeCAD's own choice. Echo.

Probe (main session), the CAM model calls 0-9 then:
1. `object_get { object: "Profile", props: ["Visibility", "Path"] }` and
   `object_get { object: "Walkthrough" }` (Visibility, ViewObject proxy type if listed).
2. `view_set { hide: ["Stock", "Block"] }` (or `object_set` Visibility false on them), then
   `view_snapshot { fit: true }`: are the green lines there?
3. If not: `object_set { object: "Profile", props: { Visibility: true } }` and snapshot again.

## 5. BIM

- bim_rebar, "Cannot calculate rebar length from its base object": cause in the tool. FreeCAD's
  rebar reads its length from its base's `Length` (a Draft wire), a sketch's geometry or a helix
  (src/Mod/BIM/ArchRebar.py 726-741 `getLengthOfRebar`); the entry gave a plain `Part::Feature`
  line. Change: `rebar_line` (bim.py 456) makes a hidden Draft wire for the base (the Part::Feature
  is removed when FreeCAD's rebar is made; the plain-bars fallback keeps it). How sure: high on the
  cause, medium that the wire's placement matches (make_wire puts its placement at p0 and keeps the
  points global). Live check: bimcam-bim-model.json call 30 then `report_read`: no rebar line;
  `object_get { object: "Slab bars" }` Base is a Wire, TotalLength about 246 m.
- bim_import on top of the old model: by its description it reads "into the document", in the
  file's own coordinates; the file was this document's own export. Change: the reply has `note`
  when what was read lies over the document's model (`lies_over`, bim.py 479), and the description
  says to `doc_new` first. No offset parameter added. Live check: call 68: `note` present.
- "Hip roof cw": not a leftover. It is the model's own call 16 (a second, clockwise roof at x 12000
  to 18000, on the ground). Nothing to change.

## 6. Part Design: pd_multitransform

- Cause: in the entry. `Body.newObject` of each step hides every other visible PartDesign feature,
  the MultiTransform (the tip) too (src/Mod/PartDesign/App/Body.cpp 249-256); the step is not a solid
  (empty Originals: FeatureTransformed.cpp 189), so it goes after the tip and the tip stays.
  FreeCAD's own command then hides each step and shows the MultiTransform
  (Gui/TaskMultiTransformParameters.cpp 278, 448-452 `FCMD_OBJ_HIDE`). The steps after the tip is
  the same as FreeCAD's order.
- Change: tools.json pd_multitransform hides each step as it is made and shows the MultiTransform
  at the end; the description says so. echo2's `tip_shown` was putting this right after the call;
  it can stay as a guard.
- How sure: high. Live check: partdesign-model.json calls 37-38 then `view_snapshot`: Plate shows
  the bore grid; `object_get` on "BoreGrid linear 1": Visibility false.
- Test: tests/test_datask2_data.py (meant difference: the Visibility lines), test_famfix.

## 7. Mesh

- "Mesh Info" panel: not opened by any tool. It is the Mesh workbench's own task watcher
  (src/Mod/Mesh/Gui/Workbench.cpp 60-130, `MeshInfoWatcher`): shown whenever the Mesh workbench is
  active, filled from the selection. It is empty because no mesh is selected. Echo item (select the
  mesh, or leave the Mesh workbench when done).
- Curvature: `meshobj_curvature` reads only and says `view_render { map: "curvature" }` colours it.
  Not a fault; echo may call that map. Segments: `keep: true` meshes now get a colour each in the
  window (`tinted`, meshobj.py 638), as FreeCAD's Mesh_Segmentation colours its segments; without
  keep nothing is made, so nothing to colour.

## For the echo agent (window only, not tool faults)

- Report view: tracebacks from earlier calls stay on screen (FEM, BIM DiffuseColor, CAM EdgeWalker).
- CAM: show the op's path (hide or make the stock see-through, open Operations, select the op);
  cam_sim: show its PNG or a caption; name files for cam_post, cam_library, cam_template_export.
- Mesh: select the new mesh (fills FreeCAD's Mesh Info box); for curvature, `view_render` map.
- FEM: select and expand "Box strength (fea_solve)" / the fea_native analysis when made; results of
  fea_modes / fea_buckle / fea_heat are files (reply `kept`).
- TechDraw: bring the named page to the front (td_list, td_export), select the new annotation, zoom
  to it; switch to the 3D view for Part tools.
- BIM: results inside the house (make others see-through or a section), the IFC tools' marks,
  bim_import into its own view.
- Part Design: `tip_shown` can stay; the tool now leaves the tip shown itself.

## Tests

`timeout 295 python3 -m pytest -q tests`: see the commit message for the totals. New:
tests/test_famfix.py. Changed: tests/_meant.py (the meant description changes, applied to the data
tests' snapshots), the data tests of bim, cam, fem, mesh, pd, sk2, td, td2 (description through
_meant; fem: `kept`; td2: a y sign in td_cosmetic; sk2: multitransform Visibility lines),
tests/test_needs.py (readers pin c411e726…, changers 136 → 140: rebar_line, tinted, native_marks,
native_weld; dataToolsTokens 78323 → 78901).

## Risks

- `fem_views_ready` adds and removes one `Fem::FemMeshObject` in the user's document once a session
  (the change watch counts it as made and removed); it touches `changes._state["gui"]`.
- td_balloon `at` is now paper mm over the view's scale (before it went in unscaled).
- The weld tile's Up/Down choice is from QGITile's code, not from a picture.
- Draft wire for the rebar base: a FreeCAD without Draft falls back to the old line.
