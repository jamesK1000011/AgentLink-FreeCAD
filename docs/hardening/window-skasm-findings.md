# Sketcher and Assembly in the window: what a person sees (42 pictures)

Source: `win/skasm/sk/` (21 pictures) and `win/skasm/asm/` (21 pictures), each with `pictures.json`.
All 42 pictures were looked at, at full size (1151 x 1400). Enlarged crops were made of sk 029, 051, 053, 060 and asm 031 (toolbar), 038.
Method and P1..P8: `pd-window-findings.md` and `pd2-window-findings.md`.
Nothing was changed. No Mac tools, no network. No code was read.

Limits of this evidence
- A picture is one frame after the call. It cannot show motion or pace.
- `pictures.json` lists only the pictured calls. I do not know what the calls between them did.
- The toolbar is cut at this width ("»" marks). A button behind "»" cannot show a ring.
- The navigation cube is in no picture (as before; probably the capture).

How I graded
- Faults that are in almost every picture are recorded once and not counted per picture: the Tasks tab in front (P3), the old red text in the Report View (G2), no ring on any sketch tool (P7), and the wrong Sketch Edit panel in all Assembly pictures (A1).
- GOOD: result easy to see, words correct, no wrong leftover on the new thing.
- BAD: a person cannot tell from the picture what was done, or the words say a wrong thing.
- A read (state, list, check) with old words is MINOR, as in the Part Design passes.

## Short answer

- Workbench box: correct in 42 of 42 (Sketcher for sketch tools, Part Design for the two pd tools, Part for part tools, Assembly for asm tools and shape_query).
- Callout label and status bar words: present in 42 of 42. The words are often tool names, old, or wrong (S3, A2, A3, A4).
- Sketcher: the sketch is open in edit mode in all 19 sketch pictures. After the first pad, the camera stays isometric and the solid covers the sketch (S1). This is the main Sketcher problem.
- Assembly: the left panel shows a Sketcher "Sketch Edit" panel of another document in all 21 pictures (A1). This is the main Assembly problem.
- No dialog is open in any picture. The correct document tab is in front in all 42 (SketcherTutorial, CrankSlider).

## Sketcher table (21)

| call | tool | verdict | why |
|---|---|---|---|
| 1 | pd_body_new | MINOR | Empty view (correct). Words "Made a new body Star". New Body button lit. Tasks tab in front; the body shows nowhere. |
| 2 | sketch_new | GOOD | Sketcher bench, empty sketch on its axes, top view, Sketch Edit panel, words correct. |
| 3 | sketch_add | GOOD | Five dashed construction lines, well framed, listed in Elements. Words "Drew in StarSketch". Not highlighted, no ring. |
| 4 | sketch_constrain | GOOD | Five constraints in the list, origin point turns red, 20 to 10 degrees of freedom. Words "Constrained StarSketch" (not which kind). |
| 13 | sketch_state | MINOR | A read. Full star profile, "Fully constrained". Words are old ("Constrained StarSketch"). Dimension labels lie on top of each other and cannot be read. Sketch uses only the middle of the view. |
| 14 | pd_pad | GOOD | Part Design bench, 3D solid, green, Pad button lit, words "Padded StarSketch by 10 mm". Tasks tab in front (P3). |
| 20 | sketch_edit | MINOR | Sketch open, but isometric view; the star solid stands in the sketch. "70 mm" can be read at an angle. Words "Edited PlateSketch" do not say what or the value. |
| 24 | sketch_external | MINOR | Magenta external line clear on the plate edge. The external circle is almost hidden in the hole. Words good ("Brought edges into TopSketch"). Isometric, solid in the way. |
| 29 | sketch_offset | MINOR | The offset curve is a blue dashed arc of about 20 pixels; clear only in a crop. Words "Offset lines" but the source (geometry 0) is a circle. |
| 31 | sketch_carbon | MINOR | Copied rectangle visible (green). Orange dimension text at an angle, cannot be read. Words are the tool name ("Sketch carbon on PlateCopy"). |
| 33 | sketch_project | BAD | Looks the same as 031 (only the zoom differs). Nothing shows what was projected. Words are the tool name. |
| 37 | sketch_validate | MINOR | A read. Words "Sketch validate on TourSketch", no result. Sketch plane seen at an angle, cuts through the solid. |
| 39 | sketch_array | MINOR | Six small circles appear at the lower right (about 12 pixels each), partly on the plate edge. Words are the tool name. Not highlighted. |
| 40 | sketch_copy | MINOR | One more small circle. Easy to miss. Words are the tool name. |
| 42 | sketch_extend | MINOR | The arc is longer; visible. Words are the tool name, no length. |
| 48 | sketch_to_bspline | MINOR | Curve now has a thick green band and number labels that lie on top of each other. Elements list shows "4-B-spline". Words are the tool name. |
| 49 | sketch_bspline | BAD | Same picture as 048 except some label numbers. The degree change (op degree, by 1) cannot be seen. Words "Sketch bspline on TourSketch" do not say it. |
| 51 | sketch_mirror | MINOR | Mirrored shapes appear as thin green outlines below the axis; small. The panel still shows the old sketch. Words are the tool name; "TourMirror" is not named. |
| 52 | sketch_merge | BAD | Same picture as 051 (same frame, same 55 degrees of freedom). The new sketch TourBoth is not shown or opened. Words "Merged Sketch on TourBoth". |
| 53 | sketch_attach | MINOR | TourBoth is now open (116 degrees of freedom). The 3 mm offset cannot be seen. Two solid green wedges appear; unclear what they are. View is crowded. Words are the tool name. |
| 60 | sketch_join | MINOR | Joint point visible at the upper right with labels on top of each other. About 20 white circles of other sketches crowd the view. Words are the tool name. |

Totals Sketcher: GOOD 4, MINOR 14, BAD 3.

## Assembly table (21)

| call | tool | verdict | why |
|---|---|---|---|
| 1 | part_primitive | GOOD | Part bench. Box green, 3D, well framed. One button lit. Words "Made a box" (name Base not given). Left panel is a Sketch Edit panel (A1). |
| 5 | part_boolean | GOOD | Fused shape green and clear. Boolean button lit. Words "Combined shapes by fuse". The ring of call 1 is still on. |
| 13 | part_transform | MINOR | Moved rod green and clear. Words "Moved a shape" (not which, not where). Two rings stay on (primitive, boolean); none matches a move. |
| 31 | asm_new | GOOD | Assembly bench. Four parts framed, red lock on Base. Words "Started an assembly CrankSlider". Two rings: the first button and a second one I cannot name. Nothing green. |
| 32 | asm_ground | BAD | Argument grounded: false. The lock goes away, but the words say "Fixed a part in place". The words say the opposite of what was done. |
| 35 | asm_joint | GOOD | Crank sits on the pin, joint marker visible, revolute button lit, words "Joined parts with a revolute joint". Lock button ring still on. Joint not green. |
| 36 | asm_limits | MINOR | Nothing to see (correct). Words "Assembly limits" give no joint and no values (CrankPivot, -90 to 90). No ring. |
| 38 | asm_pose | MINOR | Crank moved. From this camera the crank points at the viewer and looks like an upright post; a person cannot read 45°. Words "Assembly pose". |
| 41 | asm_sweep | BAD | Picture is the start pose again. No sign of a sweep. Words still "Assembly pose". |
| 44 | asm_motion | MINOR | Words "Assembly motion on swing". Nothing shows a saved motion. The rod is now in the block (calls 42, 43, not pictured). Revolute ring on. |
| 49 | asm_list | MINOR | A read. Words are old ("Joined parts with a revolute joint"). Mechanism complete and visible, small. |
| 50 | shape_query | MINOR | A read. Same picture and same old words as 049. The faces that were found are not highlighted. |
| 53 | asm_check | MINOR | A read. Words are old ("Joined parts with a cylindrical joint"). Cylindrical ring on. No result shown. |
| 54 | asm_fits | MINOR | Same old words as 053. No result shown. No ring. |
| 55 | asm_bom | MINOR | Words "Made a parts list", BOM button lit. The parts list itself is not shown. |
| 56 | asm_explode | GOOD | Rod and link lifted, red dotted lines, Explode button lit, words "Made an exploded view". |
| 59 | asm_export | BAD | Words still "Made an exploded view", Explode ring still on. Nothing says a file was written. Parts are back together but the red dotted lines stay. |
| 61 | asm_add | MINOR | Washer appears at the lower right, about 30 pixels, grey. Insert button lit. Words "Added a part to the assembly" (no name). Red dotted lines still there. |
| 64 | asm_joint_remove | MINOR | Words "Removed a joint" (not which). Nothing changes in the view. No ring. |
| 66 | asm_new_part | MINOR | Same picture as 064. An empty part has nothing to show; the tree is hidden. Words "Made a new Assembly part on Guard" read badly. |
| 71 | asm_sub | MINOR | A green object (about 50 pixels) floats above the assembly. Words are the tool name ("Assembly sub on CrankSlider"); "Stand" not named. No ring. |

Totals Assembly: GOOD 5, MINOR 13, BAD 3.

## Totals

| family | GOOD | MINOR | BAD |
|---|---|---|---|
| Sketcher (21) | 4 | 14 | 3 |
| Assembly (21) | 5 | 13 | 3 |

## P1..P8 that also show here

- P1 (top view): not here. All solids are isometric. Side effect in Sketcher: see S1.
- P2 (no words): not here. Label and status words are in 42 of 42.
- P3 (Tasks tab in front): sk 001, 014. All 21 Assembly pictures, where the panel is also the wrong one (A1). The Model tree is in no picture.
- P4 (body missing): not seen.
- P5 (fit frames the whole document): asm 044 to 071; the frame grows from 220 mm to 380 mm and the assembly uses the middle third. Washer in 061 and Stand in 071 are small. sk 013 also sits small in the view.
- P6 (whole body green): sk 014. In Assembly the opposite: almost nothing is green (A7).
- P7 (lit button): no ring on any of the 19 sketch-tool pictures. Rings match in sk 001, 014 and asm 001, 005, 031, 032, 035, 055, 056, 061. Rings left over or not matching: asm 005, 013, 035 (lock), 044, 049, 050 (revolute), 053 (cylindrical), 059 (explode). No ring: asm 036, 038, 041, 054, 064, 066, 071.
- P8 (datum planes stay on): not seen; no datum planes here. The like problem for sketches is S6.
- G2 (old red text in the Report View): all 42. The same BIM `ArchWall.py` traceback (00:40:49) and "Aborting" line. No new red lines appear during either run.

## Problems particular to Sketcher

S1. The sketch is edited in an isometric view with the solid in the way.
- Pictures: 020, 024, 029, 031, 033, 037, 039, 040, 042, 048, 049, 051, 052, 053, 060 (all 15 after the pad of call 14).
- 002 to 013 (before any solid) are in top view and are clear.
- The camera does not turn to face the sketch plane. The solid is not hidden or cut. Dimension text lies at an angle and cannot be read (020, 029, 031, 033).
- TourSketch (037 to 052) is on an upright plane and is seen from the side, through the solid.

S2. New geometry is very small or looks the same as the picture before.
- 029 sketch_offset (distance 1, geometry [0]): arc of about 20 pixels.
- 039 sketch_array (rows 2, cols 3), 040 sketch_copy (by [0, -10]): circles of about 12 pixels.
- 033 sketch_project: same as 031. 049 sketch_bspline (op degree, by 1): same as 048. 052 sketch_merge: same as 051.

S3. The words are tool names, not what was done.
- "Sketch carbon on…", "Sketch project on…", "Sketch validate on…", "Sketch array on…", "Sketch copy on…", "Sketch extend on…", "Sketch to bspline on…", "Sketch bspline on…", "Sketch mirror on…", "Sketch attach on…", "Sketch join on…": 031, 033, 037, 039, 040, 042, 048, 049, 051, 053, 060 (11 of 21).
- 029 says "Offset lines" for a circle. 052 says "Merged Sketch on TourBoth". 020 "Edited PlateSketch" does not name plate_width or 70.
- Good words for comparison: 002, 003, 004, 024.

S4. The new geometry or constraint is not highlighted.
- No sketch picture shows the new lines, circles or constraints selected (003, 004, 024, 029, 039, 040, 042, 060).
- Green shows only in 048 to 053, and I cannot tell if that is a selection or FreeCAD's own B-spline display. In 051 the mirrored outlines are thin green, which may be the new sketch selected.

S5. Tools that make a new sketch do not show the new sketch.
- 051 sketch_mirror (name TourMirror) and 052 sketch_merge (name TourBoth): the panel keeps the old sketch (55 degrees of freedom in both). TourBoth is first open in 053 (116).

S6. Other sketches stay visible and crowd the open sketch.
- White rectangle and circles of other sketches: 037 to 060. Worst in 053 and 060 (about 20 loose circles).
- 053: two solid green wedges; unclear what they are.

S7. Labels lie on top of each other.
- 013 (dimension and "=" labels in the star), 048, 049, 051 (B-spline number labels), 060 (labels at the joint point).

S8. Reads show old words or no result.
- 013 sketch_state: words of an earlier constrain call.
- 037 sketch_validate: no result (pass or fail) in words.

S9. A sketch is left open in edit mode at the end of the run.
- Evidence is in the Assembly pictures: the Sketch Edit panel with "21 Degrees of Freedom" (the same as sk 060, sketch Cuts) is in the left panel of all 21 Assembly pictures. See A1.

## Problems particular to Assembly

A1. The left panel shows a Sketcher panel of another document.
- Pictures: all 21 (001 to 071), in the Part bench and in the Assembly bench.
- "Sketch Edit / Under-constrained 21 Degrees of Freedom / Constraints / Elements" with a Close button. It does not belong to CrankSlider.
- A person sees sketch constraints beside an assembly for the whole run. Nothing about the assembly (parts, joints) is in the left panel in any picture.

A2. asm_ground says the opposite of what it did.
- 032, arguments part Base, grounded false. The lock disappears. Words: "Fixed a part in place".

A3. Old words stay on later calls.
- 041 asm_sweep shows "Assembly pose" (from an earlier pose call).
- 049 asm_list and 050 shape_query show "Joined parts with a revolute joint".
- 053 asm_check and 054 asm_fits show "Joined parts with a cylindrical joint".
- 059 asm_export shows "Made an exploded view".
- It looks as if reads, checks and export write no words of their own. For asm_export this is BAD: words are the only possible signal.

A4. Words are tool names or leave out the name.
- "Assembly limits" (036), "Assembly pose" (038), "Assembly motion on swing" (044), "Assembly sub on CrankSlider" (071), "Made a new Assembly part on Guard" (066).
- No name or value: "Moved a shape" (013), "Added a part to the assembly" (061, Washer), "Removed a joint" (064, WasherGap), "Made a box" (001, Base).

A5. Motion tools show no motion.
- 041 asm_sweep (CrankPivot, 12 steps): the picture is the start pose. A single frame after the call cannot show a sweep, but nothing (trace, words) is left to say it ran.
- 044 asm_motion (save "swing", 3 keys): nothing to see.

A6. The pose cannot be read from the fixed camera.
- 038 asm_pose (CrankPivot to 45): the crank points along the view direction and looks like an upright post. Unclear from the picture that it turned 45°.

A7. Nothing is selected in the Assembly bench.
- No green in 031 to 066. The new joint (035), the added Washer (061) and the faces found by shape_query (050) are not highlighted. Only 071 has a green object.
- Joint markers are about 15 pixels.

A8. Results that are not 3D are never shown.
- 055 asm_bom: the parts list. 053 asm_check (clearance 0.2) and 054 asm_fits (H7/g6): the result. 059 asm_export (crank_slider.asmt): the file. 036 asm_limits: the values.
- With the tree hidden (P3) and a wrong panel (A1), words are the only place, and the words do not carry them.

A9. Exploded-view lines stay after the parts go back.
- Red dotted lines in 059, 061, 064, 066, 071. The parts are together again from 059.

A10. Rings stay on from earlier calls.
- 013: two rings from calls 1 to 5. 035: lock ring. 044, 049, 050: revolute ring. 053: cylindrical ring. 059: explode ring.
- Some may come from calls with no picture; the pictures cannot tell. A ring on a read (049, 050, 053) or an export (059) is misleading.

A11. New parts land far from the assembly and small.
- 061 Washer: lower right, away from the mechanism. 071 Stand: floats above. Both about 30 to 50 pixels (with P5).

## Proven live in the window, on this evidence

Proven: sketch_new, sketch_add, sketch_constrain, pd_pad, part_primitive, part_boolean, asm_new, asm_joint, asm_explode.

Partly proven (result on screen but small, at an angle, not highlighted, or weak words): sketch_edit, sketch_external, sketch_offset, sketch_carbon, sketch_array, sketch_copy, sketch_extend, sketch_to_bspline, sketch_mirror, sketch_attach, sketch_join, part_transform, asm_pose, asm_add, asm_sub, asm_bom, asm_limits, asm_motion, asm_joint_remove, asm_new_part, pd_body_new. Reads with old or empty words: sketch_state, sketch_validate, asm_list, shape_query, asm_check, asm_fits.

Not proven: sketch_project, sketch_bspline, sketch_merge, asm_ground (wrong words), asm_sweep, asm_export.
