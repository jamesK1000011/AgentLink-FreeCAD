# Sketcher hardening: findings (group "sketch", 20 tools)

Checked against FreeCAD 1.1 source: `src/Mod/Sketcher/App/ConstraintPyImp.cpp`, `Constraint.pyi`, `SketchObjectPyImp.cpp`, `SketchObject.pyi`, and (via `git show HEAD:`) `SketchObject.cpp`, `SketchObject.h`, `GeoEnum.h`, `SketchAnalysis.cpp`; wiki `Basic_Sketcher_Tutorial.md`, `Sketcher_tutorial.md` (a redirect to it). Nothing was run on FreeCAD here: every fix below is from reading the source, and each has a FreeCAD test in `tests/test_sketch_gaps.py` (class `SketchHardening`, 8 tests) that has not been run yet.

Files changed: `agentlink/families/sketch.py`, `agentlink/families/sketch_more.py`, `agentlink/guides/sketch.md`, `tests/test_sketch_gaps.py`. No new files (FILES unchanged). `pd_common.py`, `picks.py`, `refs.py`, `health.py` untouched. Plain-Python suite: 676 passed, 243 skipped.

## Bugs fixed (proved from source)

1. **sketch_array, rows/cols swapped and rows running down.** `addRectangularArray(geos, vec, clone, rows, cols, …)` hands its 4th argument to `addCopy`'s `csize`, the count *along* the vector, and the step across is `perpscale × (vec.y, -vec.x)`. The tool passed `rows` there with `perpscale = dy/dx`, so `rows` ran along x and `cols` along **-y**. Now cols along +x, rows along +y; a 0 step with more than one copy is refused.
2. **sketch_external / sketch_project, wrong ids for more than one edge.** Ids were counted with `len(sk.ExternalGeometry)`, which groups sub-elements by object: two edges of one Pad gave one id or none. Now counted from `ExternalGeo` (1.1: axes at 0 and 1, external geometry after, id = -(index) - 1), with a per-sub-element fallback for older releases (`ext_count` in sketch.py).
3. **sketch_edit fillet { geos, near }, failed every time.** `FreeCAD.Vector(*pc.vec2(q), 0)` gave Vector four numbers (vec2 already returns a Vector); the TypeError was reported as "No fillet fits". Bad-id refusals were swallowed the same way.
4. **sketch_more's state reading, wrong property names.** It read `Conflicting` / `Redundant`; the properties are `ConflictingConstraints` / `RedundantConstraints`. Replies of the eleven sketch_more tools never showed conflicts or redundancy, sketch_validate never found or removed redundant constraints, and its after-repair conflict check never fired. `malformed` was 1-based. All now 0-based, with the solver in the same words as sketch_state.
5. **sketch_extend on an arc, mm passed as radians.** `SketchObject::extend` adds the increment to the arc's angle range. `by` is now mm along the arc (÷ radius). `to` is refused for arcs (it was computed on a straight ray); other curve kinds are refused before the call (FreeCAD extends LineSegment and ArcOfCircle only).
6. **sketch_bspline degree by -1, silent failure.** `decreaseBSplineDegree` answers False instead of raising; now a refusal with the sketch restored. `by: 0` is refused (it did nothing).
7. **sketch_edit exposeInternal reported "None added".** The call answers None; now counts the geometry added. A geometry with no internal geometry gets a refusal naming which kinds have it.
8. **sketch_constrain point refs.** `[g, 0]` counted as a point (a malformed Coincident could be built); vertices outside 1..3 and booleans went through to the PointPos cast. Now 0 means the whole curve and anything else is refused. External ids beyond those in the sketch are refused with the valid range. `fix` on an axis, the origin or an outside edge is refused.
9. **sketch_edit mirror described as "kept symmetric by constraints".** From Python `addSymmetric` runs with `addSymmetryConstraints = false`: constraints among the mirrored geometry are copied, none tie copy to original. Description, guide and reply now say so. Behaviour unchanged.
10. **sketch_carbon refusal named the wrong causes** ("must be parallel, in the same body"). In 1.1 `allowUnaligned` and `allowOtherBody` are true: FreeCAD refuses a non-sketch, a loop, another App::Part, and another body whose sketch has external geometry.
11. **state_of read `OpenVertices` as Vectors.** It returns 3-tuples, so the read always raised and fell through to the wire-based fallback (which is the better reading: `OpenVertices` flags any vertex not on exactly two edges). The dead path is removed; behaviour unchanged.

## Changed without proof (needs the live check most)

- **sketch_mirror arcs.** An in-plane mirror flips an arc's axis; whether Sketcher then keeps the right half is not something I could establish from source (sketch_offset's own comment says a downward axis "reads as the rest of the circle"). Arcs of circles are now rebuilt counter-clockwise from the mirrored end to the mirrored start. Arcs of ellipse, parabola and hyperbola still go through `transform`: **not verified**.

## Per tool

| Tool | Checked against | Fixed | Still doubtful / live check | Description |
|---|---|---|---|---|
| pd_body_new | wiki PartDesign body use in Basic_Sketcher_Tutorial | nothing | none | rewritten |
| sketch_new | `pc.support_prop` (AttachmentSupport in 1.x, Support before), MapMode FlatFace | refusals | XZ frame normal sign on 1.1.3 | rewritten |
| sketch_add | ConstraintPyImp ctor forms for every tuple `build` emits; SketchObjectPyImp addGeometry | refusals | B-spline DoF without exposed poles; parabola `rotate` | rewritten |
| sketch_constrain | every ctor overload (si, siO, siiO, siiiO, siiiiO, siiiiiO), PointPos 0..3, Angle radians, DistanceX/Y sign, Symmetric order, Block; addConstraint index base | #8, FreeCAD's own errors now name the constraint | Block on already-constrained geometry | rewritten (1.7x: each type now carries its ref forms) |
| sketch_state | solve() codes, 1-based solver lists, DoF, getOpenVertices | #11 | none | rewritten |
| sketch_edit | moveGeometry, setDatum (error codes -1..-6), fillet (both forms), trim, split, addSymmetric, exposeInternalGeometry, removeAxesAlignment, delGeometries | #3, #7, #9; setDatum / move failures say what holds; a Point's default vertex is 1 | fillet between two lines that do not share an end; text and group (1.2) | rewritten |
| sketch_offset | none in Sketcher (Part makeOffset2D) | refusals only | makeOffset2D on 1.1.3 not checked from source | rewritten |
| sketch_external | addExternal(obj, sub, defining, intersection), isExternalAllowed, initExternalGeo | #2; a tip built from the sketch is refused up front | an edge that projects to more than one geometry | rewritten |
| sketch_copy | addCopy, addMove | refusals | clone constraints | rewritten |
| sketch_array | addRectangularArray → addCopy(csize, rsize, perpscale) | #1 | constrain: true with a negative perpscale (geometry is right; the Distance/Perpendicular helpers not exercised) | rewritten |
| sketch_extend | extend (line: length; arc: radians) | #5 | none | rewritten |
| sketch_join | join (different curves, start/end only, non-periodic, same construction state) | inputs checked first; reply gives the new B-spline's id | which id the B-spline gets when its poles are exposed after it | rewritten |
| sketch_carbon | carbonCopy, isCarbonCopyAllowed | #10 | whether constraint names carry over | rewritten |
| sketch_project | addExternal, isExternalAllowed | #2; `defining` on a release without it now says so | defining: true live | rewritten |
| sketch_to_bspline | convertToNURBS (id kept; constraints other than end-point coincidences removed) | refusal | none | rewritten |
| sketch_bspline | increase/decreaseBSplineDegree, insertBSplineKnot, modifyBSplineKnotMultiplicity (knot index from 1) | #6 | none | rewritten |
| sketch_merge | Constraint First/Second/Third are writable | reply counts constraints left out (those to external geometry) | sketches on different planes are not refused | rewritten |
| sketch_mirror | none conclusive | arcs (see above) | arcs of ellipse / parabola / hyperbola | rewritten |
| sketch_attach | support_prop, MapMode | refusals | none | rewritten |
| sketch_validate | detect*/makeMissing*/evaluateConstraints/autoRemoveRedundants signatures | #4 | autoconstrain | rewritten |

## Could not do / wishes for files I may not edit

- **pd_common.py**: no change needed. `sketch_of` and `plane_ref` refusals already say what to do.
- **health.py**: no wish; its sketch reading uses the right property names and 0-based ids.
- **Not offered by sketch_constrain** (FreeCAD has them; adding them is a feature, so left): `TangentViaPoint` / `PerpendicularViaPoint` / `AngleViaPoint`, end-point-to-curve tangent and perpendicular (`siiO`), angle at chosen ends (`siiiiO`), Distance between two curves, Weight, SnellsLaw. The guide lists them as not offered.
- **Descriptions over the 1.3x aim**: sketch_constrain (1.7x) and the eleven sketch_more tools (1.3x–2x of one-line originals; +1.0 KB in all). They were too short to call right; say if they should be cut back.
- sketch_constrain's rollback removes the constraints but geometry the solver moved before the refusal stays where the solver left it (within the transaction that is aborted, so the document is restored; noted only because the code path looks otherwise).

## Test model

`sketcher-model.json`: 61 calls, all 20 tools plus pd_pad. Part A is the Basic Sketcher Tutorial star (no answer-key file exists for it; DoF after each step, area and volume are worked out from its dimensions). Part B is `Sketcher_Tutorial_Example_Files/example 1.FCStd` (60 × 80 plate, r 5 hole at [0, 10], pad 2). Part C tours the remaining tools. Geometry in part A is drawn within 0.05 mm of its solved place so the solver cannot settle on a flipped arc.
