# Add-on test models: the call-by-call review (16 Nov 2026)

What was read: every answer in `out2/` against its call's `expect` — Workshop Make 75 answers (74 calls, call 31
twice), Workshop Parts 19, Workshop Fasteners 24, Texturizer 52, ScanRuler measure 71 (calls 0..70; 71..118 have
not run). 241 answers.

Nothing here ran on FreeCAD (it is not installed where this review ran). Causes are from the add-ons' code and
FreeCAD's source (tag 1.1.0; the Mac runs 1.1.3). Every fix has a test; the plain-Python ones ran, the FreeCAD
ones are written and unrun. Where a cause is inferred and not proven, it says so.

Judgments: **(a)** tool bug, cause and fix; **(b)** the model's expectation was wrong; **(c)** cannot tell.

Counts: 10 tool bugs fixed (Workshop 8, Texturizer 2), 10 wrong expectations (13 calls), 3 undecided.
Patches: `workshop2.patch`, `texturizer2.patch`, `scanruler2.patch`. The models in each repo's `docs/hardening/`
are corrected in the same patches (the copies in this folder are not touched).

## The two known items

**mill_export leaves "3 objects not recomputed yet" (Sketch001, Revolution, Endmill001) — (a), fixed.**
Cause, from FreeCAD 1.1 source: `camjob.make_job` sets the tool bit's `Diameter`, then calls `doc.recompute()`.
CAM's tool bit does not rebuild its model when the diameter changes; it queues the rebuild for the END of the
next document recompute (src/Mod/CAM/Path/Tool/toolbit/models/base.py: `onChanged` → `_queue_visual_update`,
`ToolBitRecomputeObserver.slotRecomputedDocument` → `_update_visual_representation`). There it removes the
bit's body and copies a new one into the document (Path/Tool/shape/models/base.py `make_body`:
`doc.copyObject`). The copies — a Body labelled Endmill001, its Sketch001 and Revolution — arrive after the
recompute and nothing recomputes them. Call 69's health did not list them because they were new in that call
(the hub's check excuses objects a call made); calls 70 and 71 did. Fix: `camjob.settle_new` recomputes once
more when objects made in the call are still touched. Test: tests/make/test_camjob.py (stand-in, ran).

**fastener_set leaves "1 object not recomputed yet" — (a), fixed; and the same after hw_hole beside kept screws
(Fasteners call 19).** Cause, from source: the keeper stores its record in the fastener's `WorkshopKeep`
property, made with status NoRecompute, and keep.py said that "never leaves the fastener touched". It does:
`DocumentObject::onChanged` (src/App/DocumentObject.cpp) sets the Touch flag on a change of any property that is
not an Output one; NoRecompute only spares the forced execute. Label is an Output property (same file), so the
label itself is innocent. At call 16 nothing else changed, so the record write was the only touch; at call 19
the record's edge name changed (Edge14 → Edge16, Edge19 → Edge21). Fix: the property gets status Output, and
`keep.quiet` clears the flag after a bookkeeping write when the fastener was clean before (covers records made
before this and a FreeCAD without the status). A reattach's `o.recompute()` also left the flag (one object's
recompute executes and does not purge: src/App/Document.cpp `recomputeFeature`); cleared there too. Tests:
tests/fasteners/test_keep.py `Quiet` (ran). Second fix for call 19, **cause not proven**: `pdhole.settle`
recomputes the Body by `doc.recompute([objs])`, which runs the list and what it stands on, never what stands on
it (Document.cpp `recompute` → `getDependencyList`). Whether FreeCAD touched the screws when the Body's edges
were renumbered I could not establish from source; `settle` now also recomputes whatever the change left
touched that was not before. Test: tests/make/test_pdhole.py `Settle` (stand-in, ran). To check live: Fasteners
calls 16 and 19 answer no `needRecompute`.

**pd_pad at ScanRuler call 59 — (b), the model was wrong.** section_to_sketch's answer names the body it made
(`"body": "Body002"`, a label, as its description says) and its test already pads with `sk["body"]`. A new Body
takes FreeCAD's next free label, and this document had objects named Body and Body001. The model hard-coded
"Body" against its own note ("use that if it differs"). The tool takes `body`, so a model can also make the
Body first. Made better anyway: `next` now gives the call with the real labels (`pd_pad { body: "Body002",
sketch: "MidProfile", length }`), and the wrong-body refusal lists the bodies. The model's call 59 uses
`<BODY>` with a convention entry.

## Workshop Make (75 answers)

| call | expected | got | judgment |
|---|---|---|---|
| 30 → Parts 18 `part_review` | mass as printed | Parts call 18: `mass 3.4`, `material "Default"`, encasedMass 3.4 (mass_properties said 27.51 g for the same bin) | **(a) fixed.** A body with no material was weighed at 1 kg/m³. `fcmaterials._default_uuid` asked `MaterialManager().defaultMaterial()`, which FreeCAD 1.1's Python manager does not have (src/Mod/Material/App/MaterialManagerPyImp.cpp: getMaterial, getMaterialByPath, inheritMaterial …), so the default was never recognised and every part's own ShapeMaterial, the "Default" card (Standard/Default.FCMat: "1 kg/m^3"), was read as a material the person had set. `massMax` in a spec would have passed anything. `clear()` (part_spec { material: "" }) called the same missing method outside its try and would have raised. Fix: the default by the preference and UUID FreeCAD's own C++ uses; `clear` by `getMaterial(uuid)`. The tests' stand-in manager had the method FreeCAD lacks; a 1.1-shaped one is added (ran). |
| 34, 45 `mass_ballast` | closed pockets, 1.2 mm of wall | 10 pockets, "Closed pockets", sound true; two of them run through screw holes: [69.6, 32.8] is 2.83 mm from the M3 hole at [70, 30], [51.2, 23.6] is 3.79 mm from the countersunk M3 at [50, 20] (pocket radius 4). mass_properties after the cut: 87 mm³ less removed than the pockets' own volume | **(a) fixed.** `_pocket_runs` tests the centre and eight points on the wall's circle per level; a hole between them is not seen. Each place is now kept only when the whole cylinder (pocket + wall) is material (`shape.common`); the answer gains `leftOut { places, why }`. FreeCAD test added (unrun): tests/make/test_mass.py test_6. |
| 69–71 `mill_export` | health ok | needRecompute Sketch001, Revolution, Endmill001 | **(a) fixed**, above. |
| 62 `hw_hole` on Plate | refusal, or removed 101.79 | cut, removed 30.54, `sizes.depth 116.658` | Two things. **(b)** the alternative figure was wrong: a 3 mm plate gives π·1.8²·3 = 30.54; part_boolean leaves a plain Part::Feature, so the cut is right. **(a) fixed:** `sizes.depth` was the cutter's length (the body's diagonal) beside `depth: "through"`; it says "through" now. FreeCAD test extended (unrun). |
| 31 `mass_properties` twice | one mass | 17.10 g and inertia 3025.0, then 17.15 g and 3034.6, same body | **(a) fixed, cause inferred.** The printed estimate tessellated the body's own shape; `tessellate` reuses the triangles a shape already carries (src/Mod/Part/App/TopoShapePyImp.cpp → `getFaces`, no clean), so the answer follows whatever meshed the body before (dfm_check had, in the first session). It reads `shape.copy()` now (triangles left behind). That this explains exactly these two figures is not proven. FreeCAD test added (unrun). |
| 21–23 `hw_hole` | note | the 330-character `allowanceOn` text twice in one answer (in `sizes` and again in `note`, starting lower-case) | **(a) fixed** (too much): the note names the field. |
| 28, 45, Fasteners 18 | — | `health` carries its own `ms` | the hub's (a slow check says its time); not an add-on fault. |

Right, but the answer could say more or less:
- `mass_ballast` (34): `massOff −9.49` with 10 of 12 pockets used and no word on why it stopped (no further pocket lowered its score). Call 45 took 26 s; the description now says so.
- `hw_embed` (40): "z 8.50 to 10.80" for a 2.2 mm pocket: the top is rounded up to a layer (10.8), the floor is not; the part's own top (10.0) is not said.
- `slice`, `slice_with` (48, 50): `time "2h 7m 7s"` and `statistics.time "2h 7m 8s"` in one answer; `statistics.objects[].volume` 14011.859 is the filament's volume, not the part's (the slicer's name).
- `thread_identify` (27): right (M5x0.5 and #12-24 tap drills are 4.5, #12-28 minor 4.504, M4.5 major 4.5). A hole read "as major" of M4.5 is listed for a hole; harmless, last in the list.
- `part_spec` (10): health's `next` names the Part workbench after a Make call (the hub's).
- `mill_export` (69): the stock is "Stock001" (CAM's own stock is replaced by the box).
- Everything else read right: ISO 273 and ISO 4762 / 10642 sizes, removed volumes (342.12, 731.38, 101.43 worked out, 101.79, 159.04, 150.28, 37.31, 19.44), the stack (0.6, [0.25, 0.95], rss [0.371, 0.829]), the embed (6.4, floor 3, top 5.2, layer 26), mass_target's ballast centre, cut_check / cut_export (16 lines, 4 circles), mill_check (four sharp corners, least wall 10), fea_frame (0.159 mm against 0.156 Euler and 0.160 with shear; ±15.16 MPa against 15.0; 5000 N each).
- `dfm_check` (29): least wall 3.088 at [20.2, 28.0, 0] is beside the nut trap; a sphere reading there comes to about 2.9 to 3.1 by hand. Taken as right, not recomputed exactly.

## Workshop Parts (19 answers)

| call | expected | got | judgment |
|---|---|---|---|
| 18 `part_review` | a verdict | mass 3.4, material "Default" | **(a) fixed**, the default-material bug above. |
| 18 `part_review` | — | verdict "fix": thin-wall 0.05 mm over 98 readings at the top of the bin's stacking lip | **(c).** gen_make's own bin fails Make's own review. The lip's profile (gridfinity.py: 0.7 mm at 45° at the top) does end in an edge, so the reading is true to the shape; whether the generator should flatten the tip or the check should know a lip is the owner's call. Not changed. |
| 5 `gen_make { generator: "project_box" }` | a refusal naming gen_part | "input.generator: one of gridfinity_bin — not 'project_box'." | **(b)**: the input check answers before the generator. Too little: it does not send the agent to gen_part. |
| 14 `gen_part` without generator | the three generators listed | "input.generator: required." | **(b)**, same; too little. Both are the hub's schema refusals: a wish for it (an enum's refusal could carry the property's description). |

Sizes all right: bin [83.5, 41.5, 32.4], baseplate [84, 84, 4.65], magnet plate 7.65 high with 8 holes of 6.2, box inside [76, 56, 28], pilot 2.8, lid hole 3.7, magnets 3.39 g. Note: gen_make's `encased` differs between measure (`what "6x2 magnets", count 8, centres, hole 6.5`) and made (`what "8 6x2 magnets", pauseAt`).

## Workshop Fasteners (24 answers)

| call | expected | got | judgment |
|---|---|---|---|
| 16 `fastener_set { label }` | health ok | needRecompute ["Spare screw"] | **(a) fixed**, above. |
| 19 `hw_hole` | health ok | needRecompute the two attached screws | **(a) fixed**, above (one cause proven, one not). |
| 13 `fastener_add` | REFUSED invalid_input | not_found; the message holds a Python list: "the nearest are [{'edge': 'Edge14', 'centre': [10.0, …" | code: **(b)**, not_found is right for "no such edge there". Wording: **(a) fixed**, said in words (`api.nearest_words`, test ran). |
| 9 `fastener_types` | pass and tap hole diameters | `hole { tapHole 5, nominal 6 }` | **(b)**: the tool gives the tap drill and the thread's diameter by design (hw_hole sizes pass holes). Too little: no unit, and "nominal" under "hole" reads as a hole; `units` and a `note` added. |

Right: M6 matched to the 6.6 edge, labels per size, the keeper following Edge14 → Edge16 with hole "kept", the BOM, the counterbore screw (M6x8 on a 3.6 mm seat, `lengthNeeded 3.6`: the shortest M6 there is; it stands 4.4 mm proud and the answer gives both numbers but does not say so).

## Texturizer (52 answers)

| call | expected | got | judgment |
|---|---|---|---|
| 43 `texture_check` on the out-of-date Grip_hex | a warning | verdict "ok", "2 mm deep at most", out −1.6, into −2.0, and a warning beside it | **(a) fixed.** The verdict contradicted its own warning: the mesh of the 10 mm body was measured against the 12 mm one. An out-of-date object now answers "check", `outOfDate true`, and the note leads with it. Test ran. |
| 10, 32, 44 `texture_apply` | layers [{ layer 1 … }] | as expected | **(a) fixed** (the expectation copied the fault). The reply numbered layers from 1; texture_mask, texture_set, texture_layer and the draft number them from 0, and the one-call refusals say `layers.0`. Reading "layer 1: Fine Leather" and calling texture_mask { layer: 1 } reached the hexagons. Now from 0, with the layer's name beside it. Three tests updated, one added (ran). `maskReport` sentences still say "Layer 2" (they use the sidebar's names). |
| 29 `texture_preview` | previewEdge ≥ 0.8 | 0.5, 104,194 triangles; export edge 0.8, 34,816 | **(b).** The preview's edge is at most the part's largest size / 80 (engine `_preview_edge`, ported from BumpMesh's choosePreviewEdge), 0.5 mm here, whatever refineLength says. But then the picture is finer than the result, against the description's "what shows is what prints". Not changed (BumpMesh's rule; its JS was not here to compare); the answer now warns and names the refineLength that matches. Test ran. |
| 45 `texture_apply { update, include_new }` | no new faces | included ["Face6"] | **(b).** A Part::Box has no mapped face names (src/Mod/Part/App/FeaturePartBox.cpp sets a plain shape), so masks follow faces by their surface, and the top face moved 2 mm is no longer where it was: "new", left smooth until included. Worth knowing: changing a primitive's height silently drops an include mask on the moved face until include_new. |
| 27 `texture_mask { paint, erase }` | part of Face6 erased, or the answer says what the brush did | faces [], "Nothing textured yet: add faces." | **(b)** for the result (the top is two triangles, the circle lies on both, mode standard takes whole triangles). Too little: nothing said the brush removed the face. `facesBrushedOff` and a sentence added. Test ran. |
| 33, 46 `texture_check` | — | depth 0.904 / 0.893; out 0.64–0.70 on the sides (their layer is 0.3 high), 0.988 on Face6 (0.3 + 0.4 = 0.7) | **(c).** The figures fit the rim's points being moved by the top's 0.7 along both faces' normals (0.7 from the side's plane, 0.7·√2 = 0.99 from the box), which is what the engine's crease rule ("to where the displaced faces meet") would do with one height for both faces. Whether BumpMesh does the same, or the port should use each face's own height, I could not check. The check itself reports truthfully; an agent comparing depth with textureHeight will be puzzled. |

Right, but naming:
- `texture_check`: `into` is the lowest signed distance, so 0.003 means "nothing goes in" and −2.0 means 2 mm in. The description gives no sign rule. `moved` is a share (0 to 1), which the description does say.
- `texture_set` echoes `textureHeight 0.3` while the draft shows the same value as `amplitude 0.3` (BumpMesh's two names).
- `texture_prepare`'s note: "Only Face6 get the texture".
- `view_snapshot` (call 12, the hub's): 3,418 bytes for 800 × 600, most likely an empty view; call 31 gave 119,722.

Everything else read right: the estimates (24,576; 10,321,920 bytes; 69,206,016; refusal over 4 GB), 29,666 triangles for the engine's 29,442, closed meshes, the draft, layers, exports, prepare's 12 and 2 triangles.

Not mine, there at HEAD: tests/test_release.py `test_every_file_has_a_licence` fails on docs/hardening/ (no SPDX header or REUSE.toml entry for the findings and the model).

## ScanRuler measure (71 answers)

| call | expected | got | judgment |
|---|---|---|---|
| 28 `element_construct plane-symmetry` | the plane y = 20, matched 4000 of 4000 | the plane z = 10, rms 0.0, matched 3968 of 4000, no note | **(c).** y = 20 is the part's only exact mirror plane; z = 10 mirrors it but for the pocket. The same search on the numpy-built mesh here answers y = 20 with 4000 of 4000 (z scores 3948). I could not reproduce the Mac's pick without its mesh. Likely, not proven: the port measures a mirrored sample against the tangent plane at the nearest vertex and, on a noise-free mesh, counts anything over 1e-6 mm as unmatched (three times a median of 0); FreeCAD's triangulation of the top is not mirror-symmetric in y, so samples near the creases miss, and y scored worse. What is certain: the answer gave rms 0 and no word that 32 samples had no mirror image. Added: `symmetry.note` when matched is short of sampled ("not a mirror of the whole part … give seed"). The search itself is not changed (a port of Stefan Hermann's; changing how it scores needs his algorithm beside it). To settle live: the same call with `seed: "XZ"`. |
| 59 `pd_pad { body: "Body" }` | a pad | not_found, "they are: Body002" | **(b)**, above. |
| 60 `element_to_document` | 4 objects | numpy's truth-value error | known, fixed in e4cda35; not re-run. |
| 14, 15, 18, 69 | about 137,000 triangles, 15,900 top vertices, 68,000 points | 219,600; 23,465; 109,800 | **(b)**: FreeCAD's mesher and the six halving passes give a denser mesh than the numpy stand-in. The dimensions do not move. |

Right: every plane, the bore (radius 5.999272, 11.9985 mm, cylindricity 0.0014), the constructed points and line, all six dimensions and the 1.047 mm angularity (60·tan 1°), limits, report (text and JSON, 15 CSV rows), sections (200.0 and 37.696 long; 4 lines and one arc; the half section's 4 + 8 lines with the pocket's step), the shadow (2531.69), the sketch (2 closed wires), scan_segment's six faces and pocket floor, the heightmaps cell for cell, the outline (2400 and a circle of 5.998).

Right, but:
- `scan_qa` (16): `thickensToward [-1, 0.06, 0]` with `tiltDeg 0.0` — a direction for no tilt.
- `scan_pattern` (64): `towardDeg` 180, 0, 360, 360 … for rings that are `off 0.0` (noise; 360 for 0); `length` has no unit in the answer.
- `scan_draft` (63): `area 2.0` for a ring of 1,872 vertices at one height: the uneven-sampling limit its description states.
- `section_to_sketch`: a new Body keeps FreeCAD's default label ("Body002").
- Left/Front both `usedPoints 2977`: not a fault (each face's two triangles went through the same six halving passes).

## What the fixes cost in proof

A tool whose code changed after its run needs a re-run before it is marked (addons-marks.sh lists them):
hw_hole, thread_cut, part_review, mass_properties, mass_target, mass_ballast, mill_export, fastener_types,
fastener_add, fastener_set; texture_apply, texture_check, texture_mask, texture_preview; element_construct,
section_to_sketch, element_to_document.

Tests: Workshop per folder (make 117 passed, fasteners 15, parts 17, documents 96, electronics 18, safetynet 115,
top level 62; FreeCAD ones skipped). Texturizer file by file, all passing but the licence test above. ScanRuler
file by file, 102 files, 956 passed, none failing. Every touched file compiles with python3.11.

Wishes for the hub (not done, read-only): a schema refusal for an enum or a missing property could carry that
property's description; `view_snapshot` could say when the picture is nearly empty.
