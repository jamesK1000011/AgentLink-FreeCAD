# Part Design in the window, second pass (34 pictures)

Source: `win/pd2/pd/pictures.json` and the 34 pictures in the same folder.
All 34 were looked at, at full size (1151 x 1400). Enlarged crops were made for small details (034, 035, 051, 063, 068, 074, 088, 090, 102, 108, 111) and toolbar strips of 021, 025, 059, 090, 111.
First pass for comparison: `win/pd-window-findings.md` and `win/pd-small/`.
Nothing was changed. No Mac tools, no network.

Limits of this evidence
- A picture is one frame after the call. It cannot show motion or pace.
- These pictures are narrower than the first pass. The Report View is not in any of them. I cannot say if red lines were written.
- The toolbar is cut at this width (three "»" overflow marks). A button that is behind "»" cannot show a ring.
- `pictures.json` lists only the 34 pictured calls. I do not know what the calls between them did.
- I did not read the code or the replies. All statements below are from the pictures.

## Short answer

- Workbench box: correct in 34 of 34.
- Camera: all 32 non-sketch pictures are now a 3D (isometric) view. This is the largest gain.
- Words: the callout label is in 32 of 34 and the status bar words are in 33 of 34. Not in 068 (none) and 090 (status words only).
- Lit button: a ring is on a button in 17 pictures. It matches the step in 12. It looks wrong or left over in 5.
- Left panel: the Tasks tab is still in front in all 34. The Model tree is never shown.
- The Plate body is still missing in 037 and 038.
- Each new part is still small after call 49, because the view fits the whole document.
- Datum planes still stay on and cover other parts.
- No dialog is open in any picture. The correct document tab (PDTutorial) is in front in all 34.

Counts: GOOD 7, MINOR 23, BAD 4. First pass: GOOD 2, MINOR 20, BAD 12.

How I graded
- Two faults are in almost every picture and are recorded once, not per picture: the Tasks tab in front (P3) and the whole body green, not the feature (P6). If I counted them, only 003 and 004 would be GOOD.
- GOOD needs: 3D result easy to see, green, a matching lit button where one is on screen, correct words, no leftover on the new part.
- BAD: a person cannot tell from the picture what was done, or a body is missing.

## Table

| call | tool | first pass | now | why |
|---|---|---|---|---|
| 2 | pd_body_new | MINOR | MINOR | Empty view (correct). Label and status say "Made a new body Tut". New Body button lit. The body itself shows only in the tree, which is hidden. |
| 3 | sketch_new | GOOD | GOOD | Sketcher bench, empty sketch on its axes, Sketch Edit panel, words correct. |
| 4 | sketch_add | GOOD | GOOD | Rectangle drawn and framed. Constraints and 4 lines listed. Words "Drew in Master". "Under-constraine" is cut off (FreeCAD layout). |
| 7 | pd_pad | BAD | GOOD | 3D view, solid clear and green, Pad button lit, words "Padded Profile by 53 mm". |
| 10 | pd_pocket | MINOR | GOOD | Corner cut visible in 3D. Pocket button lit. Words correct. |
| 11 | pd_mirrored | MINOR | GOOD | Second corner cut visible. A button at the right end is lit. Words "Mirrored a feature". |
| 19 | feature_edit | BAD | MINOR | Words now say "Edited Pocket 2", Pocket button lit. The words do not say what was edited (Refine). The change cannot be seen. |
| 20 | feature_list | MINOR | MINOR | A read. Label and status still say "Edited Pocket 2" from call 19. Old words on a new call. |
| 21 | body_check | MINOR | MINOR | Words "Checked Tut". No result (pass or fail) in words. Body still green. |
| 24 | pd_hole | MINOR | MINOR | Hole button lit, words correct. The hole is one small ellipse, about 10 pixels. Easy to miss. |
| 25 | pd_linear_pattern | MINOR | MINOR | Three small circles visible. Words correct. No lit button. |
| 26 | pd_chamfer | MINOR | MINOR | Words correct. The chamfer is a very small change at the top edge. No lit button. |
| 27 | pd_fillet | MINOR | GOOD | Round edge visible with shading at the front corner. Fillet button lit. Words correct. |
| 28 | pd_datum_plane | MINOR | MINOR | Plane now clearly above the part; the offset can be seen. Words correct. Body and plane both green. No lit button. |
| 29 | feature_suppress | MINOR | MINOR | Words "Suppressed Fillet". The corner goes square; very small change. No lit button. |
| 32 | pd_tip | MINOR | MINOR | The call only reads (argument: body only). The words say "Set the body's tip". That is not what was done. |
| 34 | pd_primitive | MINOR | GOOD | New box in 3D, green, well framed. New Body and primitive buttons lit. Words correct. Yellow datum plane left on Tut. |
| 35 | pd_draft | BAD | MINOR | Words "Tapered faces by 5°". The taper shows only in a 4x crop (right side leans a little). No lit button. |
| 37 | pd_multitransform | BAD | BAD | The Plate is not in the picture; the view is on Tut only. Nothing green. Words are generic ("Part Design multitransform on Plate"). The lit button is the same one as for the box in 034; it looks like the wrong button. |
| 38 | pd_datum | BAD | BAD | A green line is now visible, but it stands in empty space: the Plate is still not shown. Words generic ("Part Design datum on Plate"). No lit button. |
| 49 | pd_thickness | MINOR | MINOR | Plate is back. Tray green and hollow, but small. New Body and primitive buttons are lit; they do not match "thickness". |
| 51 | pd_binder | BAD | MINOR | Words "Copied a shape into Cap". Only a thin green outline at the Tray base (seen in a crop). New Body lit. Hard to see. |
| 56 | pd_polar_pattern | MINOR | MINOR | Disc green with six holes, 3D. Small, and the yellow plane of Tut is partly over it. No lit button. |
| 59 | pd_clone | BAD | MINOR | Clone is now clear: green disc above the first one. Words "Cloned Disc". The lit button looks like the Fillet button (same place and icon as in 027). |
| 63 | pd_revolution | MINOR | MINOR | Ring green, Revolution button lit, words correct. Small (about 50 pixels). |
| 68 | pd_groove | BAD | BAD | No label. No status words. Nothing green. No lit button. Panel shows "Start Part / New Body". The groove can be seen as a dark band only in a crop. |
| 74 | pd_helix | BAD | MINOR | Coil reads as a spring, green, Helix button lit, words correct. Small (about 35 pixels). The Ring is now a half ring; I do not know why. |
| 82 | pd_loft | MINOR | MINOR | Frustum green, Loft button lit, words correct. Its datum plane is also green and lies over the Disc and Tut. Small. |
| 88 | pd_pipe | BAD | MINOR | Now a thin green post (about 5 x 40 pixels), Pipe button lit, words correct. Still very small. |
| 90 | pd_gear | MINOR | MINOR | Small green gear (about 30 pixels), teeth visible in a crop. Status words "Made a gear". No callout label. No lit button. |
| 95 | pd_boolean | MINOR | MINOR | Sheet green with the round cut, clear. "Boolean Operation" row lit in the panel. Words correct. Small; the primitive button is also lit. |
| 102 | pd_reorder | BAD | MINOR | Words "Reordered the features" (not which). A green block of about 20 pixels. The order shows only in the tree, which is hidden. |
| 108 | pd_move_feature | BAD | BAD | Nothing green. The Tasks panel is empty. New Body button lit. The green block of 102 is gone and a small grey box is left; I cannot tell what moved where. A white outline is on the top of the loft part; unclear. |
| 111 | pd_shaft | MINOR | MINOR | Shaft visible with steps and taper. Words "Made a shaft". Grey, not selected. Tasks panel empty. No lit button. Drawn across Tut, the gear and two yellow planes. |

## P1 to P8 status

### P1. Camera stays in top view: FIXED
All 32 non-sketch pictures are isometric. Evidence: 007 (pad is a solid), 059 (clone above the disc), 074 (coil), 088 (tube is a post, not a dot).

### P2. No callout label, no status words: FIXED in 32 of 34 (partly fixed)
- Label and status words present: all except 068 and 090.
- 068 pd_groove: no label, no status words.
- 090 pd_gear: status words present, no label.
- Word quality is a separate, new problem (see N2).

### P3. Tasks tab in front, not the Model tree: STILL PRESENT
All 34 pictures. Evidence: 007, 034, 102 (reorder shows only in the tree).
New in this pass: the Tasks panel is empty in 108 and 111, and shows "Start Part / New Body" in 068.

### P4. A body goes missing: STILL PRESENT (Plate), UNCLEAR (Hist)
- Plate: shown in 034 and 035, missing in 037 and 038, back in 049. Same as the first pass.
- Hist: a small body is in 102. In 108 its green block is gone and a small grey box and a post are left. I cannot say from the picture if a body is hidden or if the feature moved.

### P5. View fits the whole document, new part is small: STILL PRESENT
The frame grows from 107 mm (007) to 340 mm (049) to 629 mm (102). New parts in 049 to 111 are about 20 to 75 pixels in a view about 660 pixels wide. Worst: 088 (5 x 40 pixels), 102 (20 pixels), 090 (30 pixels).
The 3D view also uses only the middle third of its area in every picture.

### P6. Whole body green, not what changed; some results not green: PARTLY FIXED
- Better: 038 (datum line green), 051 (thin green outline), 059 (clone green).
- Whole body green, not the feature: 007 to 032, 034, 035, 049, 056, 063, 074, 082, 095.
- Nothing green: 037, 068, 108, 111.

### P7. No lit button: PARTLY FIXED
- Lit and matching (12): 002, 007, 010, 011, 019, 024, 027, 034, 063, 074, 082, 088. Also the "Boolean Operation" panel row in 095.
- Lit but looks wrong or left over (5): 037 and 049 (primitive button), 051 and 108 (New Body), 059 (Fillet icon for a clone). 095 has the primitive button lit next to the correct panel row.
- No ring where a Part Design button exists: 025 (linear pattern), 026 (chamfer), 028 (datum plane), 035 (draft), 056 (polar pattern), 068 (groove). Some of these buttons can be behind "»"; the pictures cannot tell.
- No ring: 020, 021, 029, 032, 038, 090, 102, 111, and the two sketch pictures.

### P8. Datum planes stay on and cover other parts: STILL PRESENT
- Yellow plane over Tut: 034 to 111.
- Loft plane over the Disc and Tut: green in 082, yellow in 088 to 111.
- Yellow axis lines also stay through the Plate, Disc and Ring (049 to 111).

### G2. Old red errors in the Report View: CANNOT JUDGE
The Report View is not in these pictures. No red text is visible anywhere.

## Totals

| | GOOD | MINOR | BAD |
|---|---|---|---|
| First pass | 2 | 20 | 12 |
| Second pass | 7 | 23 | 4 |

- BAD to GOOD: 007.
- MINOR to GOOD: 010, 011, 027, 034.
- BAD to MINOR: 019, 035, 051, 059, 074, 088, 102.
- Still BAD: 037, 038, 068, 108.
- No picture got worse.

## New problems

### N1. Rings on buttons that do not match the step
Pictures: 037, 049, 051, 059, 108 (and the extra ring in 095).
The ring is on New Body, the primitive button or Fillet when the step was a multitransform, thickness, binder, clone or move.
I cannot tell if the ring is left from an earlier call that has no picture, or if the tool points to the wrong command. A wrong ring is worse than no ring.

### N2. Words that are old, wrong or too general
- 020 feature_list: still shows "Edited Pocket 2" from call 19.
- 032 pd_tip: says "Set the body's tip" for a call that only reads the tip.
- 037, 038: "Part Design multitransform on Plate", "Part Design datum on Plate". These are tool names, not what was done.
- 019: "Edited Pocket 2" does not say what changed.
- 021: "Checked Tut" gives no result.
- 102, 108: "Reordered the features", "Moved a feature to another body" do not name the feature or the body.

### N3. pd_groove shows nothing at all
068 has no label, no status words, no selection and no ring. It is the only picture like this. It looks as if the echo did not run for this call.

### N4. Tasks panel empty or off-topic
108 and 111: the Tasks panel is blank. 068: "Start Part / New Body". A blank panel in front is worse than the Model tree.

### N5. The Ring changes to a half ring with no step to explain it
063 and 068 show a full ring. 074 to 111 show a "C" shape. A call between 68 and 74 did this; it has no picture. Check if this was planned.

### N6. Small things
- The 3D view has no navigation cube or axis cross in any picture (as in the first pass; probably the capture).
- The label wraps to 4 or 5 short lines in the bottom right corner (088, 108). It is readable.

## Proven live in the window, on this evidence

Proven (bench, 3D result visible, green, words correct, matching ring where on screen):
- sketch_new, sketch_add, pd_pad, pd_pocket, pd_mirrored, pd_fillet, pd_primitive.

Partly proven (result on screen and words correct, but small, no ring, wrong ring, or only words):
- pd_body_new, feature_edit, body_check, pd_hole, pd_linear_pattern, pd_chamfer, pd_datum_plane, feature_suppress, pd_draft, pd_thickness, pd_binder, pd_polar_pattern, pd_clone, pd_revolution, pd_helix, pd_loft, pd_pipe, pd_gear, pd_boolean, pd_reorder, pd_shaft.
- feature_list and pd_tip as reads: the words are old (020) or wrong (032).

Not proven:
- pd_multitransform, pd_datum (Plate missing), pd_groove (no echo), pd_move_feature (nothing to see).
