# hubfix5: findings (17 Nov 2026)

Branch `hubfix5`, on origin/main aab454d. It holds the earlier untested work (view_snapshot) and the
rest below. Nothing here was run in FreeCAD. "Source" is FreeCAD 1.1.3's own source. "Tested" means
plain-Python tests on stand-ins in `tests/test_hubfix5.py` (17 tests). Full suite (four runs): 1066 passed,
374 skipped, 0 failed. `scripts/tool_needs.py --check` passes. Changed files compile under python3.11.

Files touched: `agentlink/emptywhy.py`, `families/view.py`, `families/meshobj.py`, `report_watch.py`,
`usage.py`, `protocol.py` (the meter's error code), `gui_link.py` (the meter only), `store.py`,
`tools.py` (report_read's description: one clause added), `data/tools.json` (view_snapshot: one call),
`tests/_datacore_cases.py`, `tests/test_needs.py` (token counts re-pinned: coded tools 8467 to 8483,
lean listing 7150 to 7166, from report_read's added clause). `readers.json` did not change.

## 1. view_snapshot: "fitted" and "a speck", then "do the same call again"

- **Cause.** Four faults together.
  - FreeCAD turns a view (viewIsometric …) as an animation that runs on after the call returns
    (source: `Gui/Navigation/NavigationStyle.cpp`, `setCameraOrientation`, about line 540). Our fit ran
    on a camera still turning, and the turn then undid it.
  - The check read the corners through `getPointOnViewport`, which gives the window's pixels as short
    integers. A datum plane's box (1e100 mm) put every corner on one pixel: "a speck". The window can
    also be of another size than the picture, or not shown at all.
  - Parts held by a hidden Body or Part were counted; a body in a moved App::Part was boxed where it
    is not drawn.
  - After a fit, the words still said "view_snapshot with a view … fits it": the call just made.
- **Change.**
  - `families/view.py:82` `still`: animation off while the view turns and fits, the person's setting
    put back. Used in `turn` and `snap_fit`.
  - `families/view.py:380` `shown_box`: a box past 1e9 mm is counted as shown but left out of the
    box; `_seen` (line 345) leaves out what a hidden holder holds; `_placed` (line 368) moves a box
    by its holder's placement.
  - `families/view.py:427` `_snap_empty`: the corners are put in the picture from the camera itself
    (`emptywhy.camera_of`, `emptywhy.in_picture`), at the picture's size. The window's pixels are the
    fallback; a window under 16 px makes no claim.
  - `emptywhy.py:148` `off_screen(…, fitted, box)`: after a fit, an empty or speck view says "The fit
    did not take …", gives the parts' span, and sends the agent to view_render. It never sends it back
    to the same call. A number that is not finite makes no claim.
  - `families/view.py:759` `active_view`: with a drawing page or sheet in front, the 3D view behind it.
  - tools.json view_snapshot: `snap_empty(view, w, h, fitted)`.
- **How sure.** Tested (the camera reading, the words, the box, the animation switch). The animation
  cause is from the source; that it was the live cause is not proven.
- **Check live.** `view_snapshot { view: "iso" }` on a document with a datum plane and a 40 mm part:
  a picture, no "empty". Then `view_snapshot { view: "iso", width: 400, height: 800 }`: a picture.
  Then with the part's Body hidden (`object_set { object: "Body", values: { Visibility: false } }`)
  `view_snapshot { view: "top" }`: "everything is hidden", not "a speck".

## 2. meshobj_unwrap: the helper Python ends with code -11

- **Cause.** Not proven. Two candidates from the code:
  - **flatmesh's own outline walk** (source: `Mod/MeshPart/App/MeshFlattening.cpp`, `getBoundaries`,
    lines 85-108). Where two outlines meet at one point (a point on four open edges), the walk reaches
    a point it has already erased and reads `[0]` of an empty list: a crash, code -11. A plane cut of a
    sphere's mesh can leave such a point. This is a sure crash path; that it is this one is a guess.
  - **Loading FreeCAD's modules in the bundle's Python.** If this build links Python into FreeCAD's
    libraries (`BUILD_DYNAMIC_LINK_PYTHON`), `import FreeCAD` from `Contents/Resources/bin/python`
    loads a second copy of Python: also code -11. Not known for the Mac build.
- **Change.** `families/meshobj.py:489` `flatten_apart`: the helper no longer calls
  `getFlatBoundaryNodes`; the outlines are found here (`flat_loops`, line 548, from the open edges).
  The helper marks "unwrapping" before and "unwrapped" after flatmesh's work, so the stderr tells the
  stage. No refusal words changed.
- **How sure.** The removed crash path: code reading plus a test. The live cause: a guess.
- **Check live (in order).**
  1. `part_primitive { kind: "sphere", radius: 10, at: [0, 200, 0], name: "Ball" }`,
     `meshobj_from_shape { body: "Ball", deflection: 0.02, angle: 8, name: "Ball mesh" }`,
     `meshobj_trim { mesh: "Ball mesh", at: [0, 200, 5], normal: [0, 0, -1], copy: true, name: "Cap" }`.
  2. `meshobj_info { mesh: "Cap" }`: note `evaluation.nonManifolds` and `components`.
  3. `meshobj_unwrap { of: "Cap", make: false }`. What the answer means:
     - area3d about 314 and a stretch: fixed (the outline walk was the cause).
     - refused unavailable "… FreeCAD's own modules would not load there (it stopped (code -11)) …":
       the crash is at import in the bundle's Python. The next fix is to run the helper with
       FreeCAD's console program (FreeCADCmd) and not the bundle's `python`.
     - refused failed "… could not lay this surface flat: it stopped (code -11) …": the crash is in
       flatmesh's own solver on this surface (LSCM or relax). Then step 4.
  4. Control: `part_primitive { kind: "box", size: [20, 20, 10], name: "Tray" }`,
     `meshobj_from_shape { body: "Tray", name: "Tray mesh" }`,
     `meshobj_trim { mesh: "Tray mesh", at: [10, 10, 5], normal: [0, 0, 1], copy: true, name: "Tray half" }`,
     `meshobj_unwrap { of: "Tray half", make: false }`. If this one works and the cap does not, the
     cap's triangles are the cause (send `meshobj_info` of both).

## 3. BIM: the Report view floods with "… has no attribute 'DiffuseColor'"

- **Cause.** FreeCAD's own, by the code. `bim_wall` makes walls with `Arch.makeWall` (tools.json
  bim_wall: runner make, maker `Arch.makeWall`), the same function FreeCAD's BIM_Wall command uses.
  `ArchWall.py` `_ViewProviderWall.updateData` (lines 1683-1685) reads `obj.ViewObject.DiffuseColor` on
  every change of a wall. In 1.1 only a Part view provider answers `DiffuseColor`
  (`Mod/Part/Gui/ViewProviderPartExtPyImp.cpp`); a plain `Gui.ViewProviderGeometryObject` does not.
  Why a wall's view answers as the plain kind was not found in the source.
- **Change.** `report_watch.py:37` `KNOWN` and `fold_known` (line 56): the error line and its whole
  traceback are taken out of the problem lines. `take()` (the "report" on answers, and the health
  verdict's count) says it once in a FreeCAD session: "FreeCAD's own, known: … not from this call".
  `read()` (report_read) puts one line "… (× n)" first and adds `known: [{ what, times }]`; `count`
  stays the raw line count. It also no longer opens the Report view. report_read's description has
  one clause added.
- **How sure.** That it is not our wall-making: code reading, fairly sure. The folding: tested.
- **Check live.** `doc_open { path: "<FreeCAD.app>/Contents/Resources/share/examples/BIMExample.FCStd" }`
  (FreeCAD's own example; the folder may differ in the bundle), `recompute`, then
  `report_read { problems: true }`. If `known` shows the DiffuseColor fault there, it is FreeCAD's own
  for sure (no Agent Link tool made those walls). Then `bim_wall { points: [[0, 0], [3000, 0]] }`
  twice: the first answer's `report` says it once, the second says nothing of it.

## 4. usage_report: errors one short

- **Cause.** Two holes.
  - `protocol.py` (the meter, about line 466) read the error code from all text parts joined as one
    JSON. An error answer with a second text part failed that read, and the whole call was not
    counted at all.
  - Refusals the window writes itself never reach the server's meter: "busy" while a dialog holds
    the window, the agent's document closed, another document in front, a call in a blocked dialog
    (`gui_link.py`). A call answered busy while it ran was counted as answered.
- **Change.** `usage.py:110` `err_code(result)`: the first text part only; an error that cannot be
  read is still an error. `usage.py:85` `Meter.refused` and `usage.py:91` `Meter.amend` (kept on
  disk as a line of kind "amend"; `report()` adds them, line 208). `gui_link.py:1005`
  `_meter_refused` at the four places the window refuses, and `_meter_amend` (line 1413) when a busy
  answer went out for a call that then finished well.
- **How sure.** Tested (the error read, the server, the window's refusals, the amend). Which hole
  missed the one error in run unp 199 is not known.
- **Check live.** `usage_report { session: true }` before and after a call that is refused
  (`pd_pad { sketch: "NoSuchSketch" }`): errors goes up by exactly one.

## 5. Other hub leftovers

- **material_set / material_clear leave an object touched.** Cause: the hidden records object
  (`store.py`) is touched by each record written (a plain string property is an input). material_clear
  never recomputes; material_set only when a body's material changed. Change: `store.py:79` a record
  is set as an Output property before it is written (also on older files), and a new records object is
  `purgeTouched` (line 60). Tested on a stand-in; the FreeCAD behaviour is from the source
  (`App/DocumentObject.cpp` about line 924). Check live: `material_set { id: "pla" }`, then
  `session_state`: no object waits for a recompute. **mill_export** and **fastener_set** are add-on
  tools (not in this repo); if they write records through this store, the same change covers them.
  Check live: each, then `session_state`.
- **Health "Sketch: fully constrained" for CAM tool-bit sketches.** Not changed. `health.py`
  `tool_bit_sketch` finds the bit through the sketch's Body and the Body's users with `BitBody`.
  Guess: FreeCAD's tool bit removes and re-makes its body at each change
  (`Mod/CAM/Path/Tool/toolbit/models/base.py`, `_update_visual_representation`), and a re-made sketch
  can take a freed name, so it reads as a known sketch that changed. Probe:
  `cam_tool_add { diameter: 6 }` twice (6, then 8); after the second, if the health line is there,
  `object_get { object: "<that sketch>" }` and send whether its Body has an `InList` with `BitBody`.
- **Health repeats a sketch's freedom on spreadsheet calls.** Not changed. The check compares each
  sketch's reading before and after the call (`sketch_sig`). Guess: `DoF` read before the sheet call is
  stale until the sketch is solved again. Probe: `sketch_state { sketch: "<it>" }`, then
  `sheet_set { cells: { A1: 5 } }` on a cell no sketch uses: send both answers' health.
- **session_state "next" lists five tools in a-to-z order.** Not found: the "next" line names at most
  three tools (`nexthint.MAX_TOOLS`), ranked by rule weight. Probe: send one whole `session_state`
  answer that shows it.
- **FEM route "Cannot add static property".** Not changed here: hubfix4 made the answer name the
  line of the route. Probe: unp 169-178 again in a fresh FreeCAD.

## Risks

- `still` turns FreeCAD's view animation off for the length of a turn and a fit. If an error came in
  between, the `finally` puts it back.
- The camera reading assumes Coin's camera text and ADJUST_CAMERA. Where it cannot be read, the
  window's pixels are used as before.
- A Report view line that matches the known fault is no longer shown on answers after the first time.
  A different DiffuseColor fault would still show: the pattern names the plain view provider.
