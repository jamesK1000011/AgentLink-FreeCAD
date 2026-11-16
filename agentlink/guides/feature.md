<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# PartDesign features

## Start here
A map of this guide. `guide_read { topic: "feature", section: [...] }` reads the sections named.
- Before the first feature: `workflow` (a ready sketch, then the feature; the order that keeps a model stable), `reading the answer` (`volumeChange`, `solids`, names) and `traps` (naming faces and edges, pockets and holes cut against the sketch's normal).
- At their own moment (the index lists them under later): `pad and pocket`, `holes`, `patterns and mirrors`, `the history and the tip`, `More features`, `gears and sprockets`.

## workflow
1. Make a sketch ready (`sketch_state` reads `readyForFeature`), then `pd_pad`, `pd_pocket`, `pd_revolution`, `pd_groove`, `pd_hole`, `pd_loft` or `pd_pipe`.
2. Finish with `pd_fillet` / `pd_chamfer` (edges), `pd_draft` / `pd_thickness` (faces), and `pd_mirrored` / `pd_linear_pattern` / `pd_polar_pattern` (features by name, or `features: "all"` for the whole body — FreeCAD 1.1's TransformMode "Whole shape", else every pad and pocket up to the tip).
3. Each answer gives the feature's name, the body's volume, faces, solids and size after the change, the volume change, and `health` (`ok`, `verdict`, `todo`) from FreeCAD's own state.
4. `feature_list` shows the history. `feature_edit` changes values. `feature_suppress` and `feature_remove` take features out.

Order that keeps a model stable (FreeCAD's own advice): sketches on the body's planes or datum planes rather than on faces; pads and pockets first; patterns and mirrors next; shell (`pd_thickness`) before fillets; fillets and chamfers last.

## reading the answer
- `volumeChange` is the check that a feature did what was meant: a pad adds, a pocket removes, a fillet on an outside edge removes a little.
- `solids` above 1 means the body is in pieces. FreeCAD 1.1 allows it while the body's `AllowCompound` property is true (the default), and `health` then reads "2 solids (AllowCompound)". It is usually a mistake: a pad that does not touch the body, a pocket that cut it in two, a pattern copy that landed beside it. With `AllowCompound` off, FreeCAD refuses such a feature ("Result has multiple solids").
- A refusal is FreeCAD's own error with what to do next. Nothing is kept: the document is as it was before the call.
- Names: features are labelled Pad, Pocket, Fillet …; a second one is "Pad 2". Use the `feature` each answer gives.

## traps
- Name faces and edges by where they are: `{ at, normal }` for a face, `{ near }` for an edge, or `shape_query`'s filters (`{ type: "line", axis: [1, 0, 0], z: 10 }`). A reference from `shape_query` ("Edge3") is good until the next change. Query again after one: the numbers change (the topological naming problem).
- A pocket cuts against its sketch's normal. One that cuts nothing is refused: use `reversed: true`, or put the sketch on the face the pocket enters.
- A pad that adds nothing (inside the body already) is refused.
- Holes drill at the centre of each circle in the sketch, against the sketch's normal. Put the sketch on the face the holes enter. In FreeCAD 1.1 a hole is drilled at each sketch point too; construction geometry is skipped. The answer's `holes` is the count.
- A fillet or chamfer larger than a face beside it fails. Try a smaller value or fewer edges. Edges where two faces already meet smoothly are skipped.
- A failed feature is refused with FreeCAD's own error and nothing is kept. The document stays as it was.
- To change a property bound to a parameter, use `param_set`. `feature_edit` refuses it.
- Changing tools cannot run as background jobs. Keep one call under about a minute: a modelled thread (`modelThread`), a helix of many turns and a pattern of hundreds of copies are the slow ones. Split a big pattern into two steps or check the count first.

## pad and pocket
<!-- later: when a pad or pocket needs a type or sides other than a plain length -->
- `type`: `length` (default), `up_to_first`, `up_to_face` (with `upToFace`), and `up_to_last` for a pad or `through_all` for a pocket. These are FreeCAD's Length, UpToFirst, UpToFace, UpToLast and ThroughAll.
- `sides`: `one`; `symmetric` (the length shared both ways about the sketch); `two` (`length` on the normal's side, `length2` on the other). FreeCAD 1.1 keeps these as SideType "One side", "Symmetric", "Two sides" with Type2 and Length2; a through-all pocket with `sides: "two"` goes through both ways.
- `feature_edit` reaches the rest by FreeCAD's names: `Offset` (mm from the up-to face), `TaperAngle`, `Type2`, `Refine`.

## holes
<!-- later: when using pd_hole -->
- `thread: "M5"` is ISO coarse (FreeCAD's "M5x0.8"); `"M8x1"` is ISO fine ("M8x1.0"). With `threaded: true` (default) the hole is the tap drill's size and the thread is only recorded; `modelThread: true` cuts the real thread and is slow. `threaded: false` gives a clearance hole: `fit` close, normal or loose (FreeCAD's Fine, Medium, Coarse for metric).
- `cut`: counterbore, countersink or counterdrill. With a thread size FreeCAD fills in standard sizes (ISO 4762 for a counterbore, ISO 10642 for a countersink) and also takes a screw standard by name; with a plain `diameter`, give `cutDiameter` (and `cutDepth`, `countersinkAngle`).
- Other thread standards (UNC, UNF, BSP …): make the hole by diameter, then `feature_edit { set: { ThreadType: "UNC" } }` and its `ThreadSize`; a wrong value lists the right ones.

## patterns and mirrors
<!-- later: when using pd_linear_pattern, pd_polar_pattern, pd_mirrored or pd_multitransform -->
- `pd_linear_pattern`: `spacing` between copies or `length` first to last; kept as FreeCAD's Extent mode (Length = spacing × (occurrences − 1)).
- `pd_polar_pattern`: `angle: 360` spaces the copies evenly all round; a smaller angle is from the first to the last copy.
- A copy of a pocket or hole must land on material. A copy of a pad that does not touch the body becomes a second solid.
- `pd_multitransform { features, steps }` chains patterns. A grid is two linear steps; `scale` steps grow the copies. Its steps stay in the body under it (`feature_list` marks them `stepOf`) and are removed with it.

## the history and the tip
<!-- later: when using pd_tip, feature_remove, pd_reorder, pd_move_feature or pd_clone -->
- The tip is the feature the body's shape stops at. New features go in right after it. `pd_tip` reads or sets it; features past the tip are kept but left out of the shape (`afterTip`), so set it back to the last feature when done.
- `feature_remove` moves the tip back to the feature before the one removed. One that others use (a sketch on its face, a fillet of its edges, a pattern of it) is refused: remove those first, the last made first.
- `pd_reorder` moves a feature or sketch in the history; a feature may only use what comes before it. `pd_move_feature` takes a feature and its sketch to another body.
- `pd_clone` starts a new body on another object's shape; `pd_shaft` makes a stepped shaft as a plain Part solid (use `part_fillet` on it, or `pd_clone` to bring it into a body).

## More features
<!-- later: when using pd_primitive, pd_helix, pd_datum, pd_binder, pd_boolean, pd_loft or pd_pipe -->
- `pd_primitive { kind: "cylinder", size: { radius, height }, at, rotate }` adds a box, cylinder, sphere, cone, ellipsoid, torus, prism or wedge without a sketch. `at` is a box's corner, a cylinder's or cone's base centre, a sphere's or torus's centre. `subtractive: true` cuts it out instead: a quick bore or slot.
- `pd_helix { profile, axis, pitch, height }` makes a spring or a coil; `subtractive: true` cuts a thread or a groove. Give two of pitch, height and turns. The profile must not cross the axis, and its height should be under the pitch.
- `pd_datum` makes a line, point or coordinate system: placed from the origin, or `on: { near }` a round edge (its axis or centre), which then follows the model. A datum line serves as an axis by name. `pd_datum_plane` makes a plane to sketch on.
- `pd_binder { from: "Other body", faces }` brings another body's faces in to sketch on (`sketch_external`). `pd_boolean { op, with }` fuses, cuts or keeps the common part of other bodies.
- `pd_loft` needs each section on its own plane, one closed wire each, the same number of edges. `pd_pipe` sweeps a profile along a path sketch; `feature_edit` sets its `Mode` (Standard, Fixed, Frenet, Auxiliary, Binormal) and `Transition` (Transformed, Right corner, Round corner).

## gears and sprockets
<!-- later: when using pd_gear -->
`pd_gear` makes an involute gear (`teeth`, `module`, `pressureAngle`; `internal: true` gives a ring gear with a `rim`) or a roller-chain sprocket (`kind: "sprocket"`, chain `pitch`: 9.525 for #35, 12.7 for #40). It is padded to `thickness` on the body's XY plane at `at`, with an optional `bore`. It answers the pitch diameter; two gears mesh at centres (d1 + d2) / 2 apart.
