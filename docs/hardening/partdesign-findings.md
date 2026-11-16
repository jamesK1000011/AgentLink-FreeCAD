# Part Design hardening pass — findings (agent: partdesign)

Checkout: the agent checkout. Nothing committed or pushed. FreeCAD could not be run here: every fix below is from
reading FreeCAD 1.1.0's source (tag 1.1.0 in (the agent workspace); the Mac runs 1.1.3) and is unproven until run live.
Tests: `python3 -m pytest -q -x` → 676 passed, 242 skipped (the FreeCAD ones, mine included).

Sources read: src/Mod/PartDesign/App — Body.cpp, Feature.cpp, FeatureSketchBased.cpp, FeatureExtrude.cpp, FeaturePad.cpp,
FeaturePocket.cpp, FeatureRevolution.cpp, FeatureGroove.cpp, FeatureHole.cpp/.h, FeatureDressUp.cpp, FeatureFillet.cpp,
FeatureChamfer.cpp, FeatureDraft.cpp, FeatureThickness.cpp, FeatureTransformed.cpp, FeatureLinearPattern.cpp,
FeaturePolarPattern.cpp, FeatureMirrored.cpp, FeatureMultiTransform.cpp, FeatureScaled.cpp, FeatureLoft.cpp/.h,
FeaturePipe.cpp, FeatureHelix.cpp, FeatureBoolean.cpp, FeaturePrimitive.cpp, FeatureBase.cpp, ShapeBinder.cpp, DatumLine.cpp;
Gui/TaskMultiTransformParameters.cpp; Part/App/Attacher.cpp; App/PropertyContainerPyImp.cpp; Sketcher/App/SketchObject.cpp/.pyi;
PartDesign/InvoluteGearFeature.py, fcsprocket/; PartDesignTests/TestMultiTransform.py, TestBoolean.py, TestShapeBinder.py,
TestLoft.py, TestPipe.py, TestHole.py. Wiki: Basic_Part_Design_Tutorial_019.md, Basic_Part_Design_Tutorial.md,
PartDesign_Pad.md, PartDesign_Pocket.md.

## Bugs fixed (each provable from source; each needs the live run)

1. **Axis by sketch geometry id was the wrong edge** (pd_revolution, pd_groove, pd_helix; pd_common.axis_ref). Id n was sent as
   `(sketch, "Edge{n+1}")`. FreeCAD reads "EdgeN" on the sketch's *shape*, which holds only the profile's edges, and names
   construction lines "Axis0", "Axis1" … in their own count (ProfileBased::getAxis, SketchObject::getAxis). A construction
   line with id 0 therefore revolved about the profile's first edge, silently. Now: construction line → "Axis{k}"; a profile
   line → its edge found on the shape by its end points; anything but a line refused. Test: test_feature.py test_9e.
2. **Datum lines and points placed from the origin could not attach** (pd_datum without `on`). They were given MapMode
   "FlatFace"; AttachEngineLine and AttachEnginePoint have no such mode (default branch: throwWrongMode). Now ObjectZ (line)
   and ObjectOrigin (point); coordinate systems keep FlatFace. Test: test_feature_more.py test_5.
3. **A face given as a plane was looked for after the new feature became the tip** (pd_draft `neutral`, pd_mirrored
   `plane` as `{ at, normal }`): the tip then has no shape and the call was refused with "has no solid yet". The plane and
   axis are now read before the feature is made. Test: test_9a (draft).
4. **Fine threads were never found on 1.1** (pd_hole). FreeCAD 1.1 names them "M8x1.0"; the tool's own example "M8x1" matched
   nothing and was refused. Designations are now matched by diameter and pitch. Test: test_9c.
5. **Hole count and the "no circles" refusal ignored 1.1's holes at sketch points** (Hole.BaseProfileType; a new Hole takes
   points, circles and arcs by default) and counted construction circles, where FreeCAD drills none. Now read from the
   feature. Test: test_9c.
6. **pd_revolution / pd_groove `sides: "two"` crashed** with a raw enumeration error (it set Type "TwoLengths"; a revolution's
   enumeration is Angle, UpToLast|ThroughAll, UpToFirst, UpToFace, TwoAngles). The schema has no second angle, so it is now
   refused, pointing at feature_edit { Type: "TwoAngles", Angle2 }. Any other bad `sides` value raised KeyError; now refused
   by name. Test: test_9d.
7. **MultiTransform's steps were taken out of the body.** FreeCAD's task panel and its own test leave them in the body
   (Body::isSolidFeature skips a MultiTransform's children); outside it their plane and axis links cross the body's
   boundary, and feature_remove left them orphaned in the document. They now stay in the body, are labelled
   "<name> linear 1" …, are listed with `stepOf`, and are removed with their MultiTransform. Test: test_6.
8. **pd_tip accepted a sketch or a datum as the tip**, which breaks the body ("Linked object is not a PartDesign feature",
   Body::execute) and reported nothing. Now the solid feature before it (as the window's Set tip), refused when there is
   none; a tip that breaks something is refused and undone; replies carry `tipWas` and `afterTip`.
9. **feature_remove did not see a fillet/chamfer/draft built on the feature as a user** (the check skipped anything whose
   BaseFeature was the feature, and a dress-up's BaseFeature and Base are the same object). The call then failed later with a
   bare recompute error. Users are now found by their own link properties (pd_common.uses). Test: test_9a.
10. **pd_gear made its profile in FreeCAD.ActiveDocument** (makeInvoluteGear), not the session's document; now made on the
    session's document the same way. `outsideDiameter` now counts profile shift and the addendum coefficient.
11. **pd_pocket through_all with sides two** went through one way and 5 mm the other (Type2 stays "Length"); Type2 is now
    ThroughAll too. A pad/pocket with sides two and no length2 silently took FreeCAD's default 10 / 5 mm; now refused, naming
    length2.
12. Refusals that named things that do not exist: the stale-reference hint said `feature_edit { feature, edges }` (no such
    input); pd_shaft's note named `strength_check` (no such tool) and pd_fillet (does not work on a Part solid).

## Per tool

| tool | checked against | wrong and fixed | still doubtful (live check) | description |
|---|---|---|---|---|
| pd_pad | FeaturePad.cpp, FeatureExtrude.cpp, PartDesign_Pad.md | type list per kind and its refusal; `upToFace` alone now means up_to_face; length2 required for two sides; taper checked; first pad must be a length | two sides on 1.0 (TwoLengths path, untested); up_to_* with a taper | yes |
| pd_pocket | FeaturePocket.cpp, FeatureExtrude.cpp | bug 11; refusals | through_all + two sides + taper | yes |
| pd_revolution | FeatureRevolution.cpp, FeatureSketchBased.cpp | bugs 1, 6; angle range | a profile line (not construction) as the axis: found by end points on the sketch's shape | yes |
| pd_groove | FeatureGroove.cpp | bugs 1, 6 | — | yes |
| pd_hole | FeatureHole.cpp/.h | bugs 4, 5; depth / drillPoint / fit validated; `cut` matched without regard to case, so a screw standard's name is taken; reply adds `cut` | that sketch points really come through as holes on 1.1.3 (test_9c asserts volume = holes × area × depth); standard counterbore sizes; modelThread speed | yes |
| pd_fillet | FeatureFillet.cpp, FeatureDressUp.cpp | radius validated; hint names tangent edges (FreeCAD drops non-C0 edges) | — | yes |
| pd_chamfer | FeatureChamfer.cpp | size2 and angle together refused | — | yes |
| pd_draft | FeatureDraft.cpp | bug 3; angle range | sign of the volume change for a given angle/reversed (not derived) | yes |
| pd_thickness | FeatureThickness.cpp | join validated (Arc / Intersection; Reversed true = inward confirmed) | — | yes |
| pd_mirrored | FeatureMirrored.cpp, FeatureTransformed.cpp | bug 3; wording: the 1.1 mode is "Whole shape", not "Transform body" (the code already fell through to it) | a copy that misses the body: 2 solids vs. FreeCAD error | yes |
| pd_linear_pattern | FeatureLinearPattern.cpp | spacing/length must be over 0; occurrences a whole number; kept in Extent mode (1.1's Spacing mode / Offset / Direction2 not exposed) | — | yes |
| pd_polar_pattern | FeaturePolarPattern.cpp | angle range (360 → angle/occurrences, else angle/(n−1): confirmed) | negative angles are now refused (use reversed) | yes |
| pd_multitransform | FeatureMultiTransform.cpp, FeatureTransformed.cpp, Gui/TaskMultiTransformParameters.cpp, TestMultiTransform.py | bug 7; a linear step with no spacing/length silently took 10 mm, now refused | that the health check stays quiet about the steps (null shapes) in the body; scale steps | yes |
| pd_loft | FeatureLoft.cpp/.h, TestLoft.py | profile listed again in sections refused | closed, subtractive | yes |
| pd_pipe | FeaturePipe.cpp, TestPipe.py | path = profile and an empty path refused before the feature is made | Mode / Transition by feature_edit | yes |
| pd_helix | FeatureHelix.cpp | bug 1; pitch/height/turns validated; growth with taper refused (FreeCAD computes the angle in that mode) | growth, leftHanded | yes |
| pd_primitive | FeaturePrimitive.cpp | refusals; schema text (ellipsoid radius1 is along z; wedge x2/z2 are the face at ymax) | — | yes |
| pd_gear | InvoluteGearFeature.py, fcsprocket/ | bug 10; kind/module/bore/rim validated; bore on a ring gear refused (it cut nothing) | sprocket path; internal gear's addendum (FreeCAD suggests 0.6, the feature keeps 1.0 when ExternalGear is switched after creation); no view-provider proxy on the gear profile (as before) | yes |
| pd_datum | Attacher.cpp, DatumLine.cpp | bug 2; `on` now reads the body's shape like its neighbours | lcs `on` an edge (ObjectXY) | yes |
| pd_datum_plane | Attacher.cpp | rotate validated; refusal says what `on` takes | — | yes |
| pd_binder | ShapeBinder.cpp, TestShapeBinder.py | refusals (SubShapeBinder, Support, BindMode Frozen confirmed) | faces of a body that has a Placement | yes |
| pd_boolean | FeatureBoolean.cpp, TestBoolean.py | `with` as one name taken; refusals | FreeCAD's test uses setObjects, the tool addObjects (left as it was) | yes |
| pd_shaft | (own code; lives in std_more.py) | note named a tool that does not exist; says now it is a plain Part solid | — | yes |
| feature_list | — | marks MultiTransform steps; adds `tip`; shows more key values (Offset, TaperAngle, ChamferType, Size2, Join, TransformMode, Factor, ModelThread, Pitch/Height/Turns; Angle2 only for TwoAngles) | — | yes |
| feature_edit | PropertyContainerPyImp.cpp (ReadOnly status does not block Python; Immutable does) | "?TwoLengths" refused; clearer refusals | refsFound path | yes |
| feature_remove | Body.cpp (removeObject re-links the next feature and moves the tip back) | bug 9; a MultiTransform's steps go with it; reply adds `tip` | — | yes |
| feature_suppress | Feature.cpp (SuppressibleExtension) | refusal text; hint | — | yes |
| pd_tip (std_more) | Body.cpp | bug 8 | — | yes |
| pd_reorder (std_more) | Body.cpp | after and before together refused; itself as target refused; reply adds `afterTip` | a feature that was the tip and is moved earlier stays the tip, so later ones drop out — now reported, not changed | yes |
| pd_move_feature (std_more) | Body.cpp | non-PartDesign objects refused early; refusals | a primitive or datum moved keeps its link to the old body's origin plane (only sketches are re-attached) — not changed | yes |
| pd_clone (data/tools.json) | Body.cpp (BaseFeature → FeatureBase, tip set) | description and note only | the window's Clone also copies the source's Placement into the FeatureBase; the tool sets Body.BaseFeature instead (works by source, differs in structure) | yes |

Counts: 31 tools checked, 31 descriptions rewritten, 12 fixes (11 in behaviour, 1 in refusal and guidance text).

## Description lengths
feature.py 5897 → about 7560 characters (1.28×); feature_more.py 1760 → 2354 (1.34×). The four one-line descriptions in
std_more.py (pd_tip, pd_reorder, pd_move_feature, pd_shaft) and pd_clone grew 2–4.5× because they said almost nothing before
(about 60 characters each). Long workflows went to agentlink/guides/feature.md (new sections: reading the answer, pad and
pocket, holes, patterns and mirrors, the history and the tip).

## Outside my brief, done anyway — say if it should be backed out
- pd_shaft is one of my 27 tools but its code is in std_more.py, where I was told to touch four tools only. I changed its
  description, two refusals and its note (which named a tool that does not exist). No logic changed.
- pd_clone is not in std_more.py but in agentlink/data/tools.json; I changed its description and note text there only.

## Not verified / could not do
- Nothing was run on FreeCAD. The new tests (test_feature.py 9a–9e, test_feature_more.py 5–6) were written blind.
- Changing tools cannot run as jobs (job_start takes reads only), so "use a job when heavy" does not apply to this family;
  the guide says which calls are slow instead. No size limits were added: that would be a new behaviour.
- Body AllowCompound: read only (default true in 1.1; with it off FreeCAD errors "Result has multiple solids", for which
  settle now gives a next step). No tool sets it; object_set can.
- 1.1's pattern Spacing mode, second linear direction, pad UpToShape / Offset / UseCustomVector, hole Tapered / ThreadClass /
  ThreadDepthType are not inputs of the pd_ tools (no new features); feature_edit reaches the non-link ones.
- Health wish (health.py not edited): a MultiTransform's steps and datum objects have null or helper shapes — the check
  should not report them as broken shapes; and a body with AllowCompound and 2+ solids could say which feature first made
  the second solid.
- The answer key is the old (0.16) tutorial's file and contains a 1 mm pad the tutorials do not describe; see
  referenceNotes in partdesign-model.json. Its volume is estimated, not measured.
