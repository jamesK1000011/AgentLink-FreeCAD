# Window review, round 6: Workshop, Texturizer, Tutor

FreeCAD 1.1.3 with Agent Link, final pictures after echo round 6. 71 pictures (Workshop 53, Texturizer 14, Tutor 4). I looked at every picture listed in pictures.json. Compared with `docs/hardening/window-r4-ws-tex-tutor-findings.md`.

Rating: GOOD = result shows, only known general problems. MINOR = result shows, small family problem. BAD = result not visible, stale or wrong result, or a leftover / error in the view.

No dialogs, red tree marks or error text in any picture. Stale captions: 0 of 71 (round 4: 6).

## Counts

| Family | R6 GOOD | R6 MINOR | R6 BAD | R4 G/M/B |
|---|---|---|---|---|
| Workshop | 15 | 37 | 1 | 15/29/9 |
| Texturizer | 3 | 8 | 3 | 3/9/2 |
| Tutor | 2 | 2 | 0 | 0/1/3 |

---

## 1. Workshop (53)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 0001-pd_body_new | pd_body_new | GOOD | Ring on Body, body selected, caption. |
| 0002-sketch_new | sketch_new | GOOD | Sketcher toolbars, sketch panel, plane named. |
| 0003-sketch_add | sketch_add | GOOD | Lines selected, ring on Rectangle. |
| 0004-pd_pad | pd_pad | GOOD | Ring on Pad, caption with volume. |
| 0005-setup | setup | MINOR | Caption only "Setup"; Pad ring kept. |
| 0010-part_spec | part_spec | MINOR | Caption "Part spec" only; body not selected. |
| 0012-fit | fit | MINOR | Good words; Agent Link tab in front. |
| 0016-hw_hole | hw_hole | MINOR | Hole and ring show; caption is tool name. |
| 1004-thread_lookup | thread_lookup | GOOD | Caption gives data source. |
| 1007-thread_identify | thread_identify | MINOR | "10 mm", no thread name; face not marked. |
| 1008-thread_cut | thread_cut | MINOR | No ring; thread not visible. |
| 1009-dfm_check | dfm_check | MINOR | Stale caption gone: "...: printable"; says "Checking" (present). |
| 1010-part_review | part_review | MINOR | Stale caption gone: "Reviewing ...: pass". |
| 1011-mass_properties | mass_properties | MINOR | No numbers; no CoM mark. |
| 1012-mass_target | mass_target | MINOR | No result in caption. |
| 1014-mass_ballast | mass_ballast | MINOR | No ballast mark; tool-name caption. |
| 1017-part_transform | part_transform | MINOR | "Moved" for a copy; other body cut off left. |
| 1019-hw_embed | hw_embed | MINOR | Make bench, ring on Embed; pocket hidden. |
| 2001-hw_embed_list | hw_embed_list | MINOR | No count. |
| 2002-hw_pauses | hw_pauses | GOOD | "1 found". |
| 2004-hw_unembed | hw_unembed | MINOR | No visible change; ring gone. |
| 2008-slice | slice | MINOR | Fixed words "2h 7m 7s, 17.82 g"; Bracket cut off left; status bar empty. |
| 2009-slicer_presets | slicer_presets | MINOR | No count. |
| 2010-slice_with | slice_with | MINOR | Fixed words; same cut-off and empty status bar. |
| 2011-slice_read | slice_read | MINOR | Names file; no time or filament. |
| 2012-printer_list | printer_list | MINOR | "Listed Printer", no count. |
| 2015-part_primitive | part_primitive | MINOR | Plate selected, ring on Box; brackets cover it. |
| 2017-part_boolean | part_boolean | BAD | Cut hole hidden under brackets. |
| 2019-cut_check | cut_check | MINOR | "pass"; ring on Setups; plate covered. |
| 3001-cut_export | cut_export | MINOR | "3 mm" only; no file, no sheet layout. |
| 3008-mill_check | mill_check | MINOR | "pass with warnings"; ring on Setups. |
| 3009-mill_export | mill_export | GOOD | Block framed and selected; ring on mill export. |
| 3012-fea_frame | fea_frame | MINOR | Stale caption gone: "at most 15.1 MPa"; mill ring and Block kept; no frame. |
| 4001-gen_make | gen_make | MINOR | Measure only, "nothing made" says why empty; PD primitive ring. |
| 4006-body_check | body_check | GOOD | Bin selected, "sound". |
| 4007-gen_part | gen_part | MINOR | Measure only, "nothing made"; old Bin, wrong ring; "1 parts". |
| 5007-fastener_types | fastener_types | MINOR | "6 found"; stays Part Design; Hole ring kept. |
| 5011-fastener_add | fastener_add | MINOR | Screw selected, ring ISO4762; caption "Added Fasteners". |
| 5014-fastener_list | fastener_list | MINOR | Read zooms to screw alone; no count. |
| 5015-fastener_set | fastener_set | MINOR | Screw now in hole, head up; loose small screw below; not selected. |
| 6002-fastener_print | fastener_print | MINOR | New head + hole; loose screw still; not selected. |
| 7002-macro_save | macro_save | GOOD | Names saved file. |
| 7005-macro_list | macro_list | MINOR | No count. |
| 7006-macro_show | macro_show | MINOR | Caption ends ": no"; macro text not shown. |
| 7011-macro_unapprove | macro_unapprove | GOOD | Names macro. |
| 7015-mass_calibrate | mass_calibrate | MINOR | No result in caption. |
| 7022-history_checkpoint | history_checkpoint | GOOD | Names file written. |
| 7023-app_recover | app_recover | MINOR | Raw help text with braces. |
| 7026-pref_history | pref_history | MINOR | Raw help text with braces. |
| 7027-pref_set | pref_set | GOOD | Names path (no value). |
| 7029-pref_reset | pref_reset | GOOD | Names path. |
| 7033-printer_add | printer_add | GOOD | Names printer. |
| 7041-export | export | GOOD | Names file; Probe box not selected. |

Numbers: ring visible 29/53 (one ring at a time in all). Caption 53/53, stale 0 (round 4: 5).

### Round-4 Workshop problems

| Problem | Status | Pictures |
|---|---|---|
| Stale captions dfm_check, part_review, slice, slice_with, fea_frame | FIXED (results now in words) | 1009, 1010, 2008, 2010, 3012 |
| Heavy-read words say "Checking / Reviewing / Slicing / Solving ... in the background" after the result is known | NEW, small | 1009, 1010, 2008, 2010, 3012 |
| Status bar empty while slicing | NOT FIXED | 2008, 2010 |
| Selection jumps to the other Bracket, cut off at the left edge | NOT FIXED | 2008-2012 |
| gen_make empty view / gen_part shows old Bin | FIXED by words: both calls are `measure: true`; caption says "nothing made" | 4001, 4007 |
| gen_* ring PD additive primitive | NOT FIXED | 4001, 4006, 4007 |
| fastener_set screw outside body | FIXED: screw in its hole, head on the open (top) side | 5015 |
| Loose small screw below the body | NOT FIXED (still in 5015, 6002) | 5015, 6002 |
| Lists without count | NOT FIXED | 2001, 2009, 2012, 5014, 7005 |
| Raw help text in caption | NOT FIXED | 7023, 7026 |
| Covering bodies not see-through | NOT FIXED | 2015, 2017, 2019, 3001 |
| part_boolean hole hidden | NOT FIXED | 2017 |
| Wrong / no workbench switch | NOT FIXED | 0005, 0010, 0012, 1008-1014, 5007 |
| Agent Link / Make tab in front of Model | NOT FIXED | from 0010 on |
| Ring map: cut/mill checks light Setups; fea keeps mill ring | NOT FIXED | 2019, 3001, 3008, 3012 |
| fastener_list (read) zooms | NOT FIXED | 5014 |
| mass_* no result | NOT FIXED | 1011, 1012, 1014, 7015 |
| part_transform "Moved" for a copy | NOT FIXED | 1017 |
| 7006 ": no", 3001 no kerf/file, 7041 not selected, pref_set no value | NOT FIXED | 7006, 3001, 7041, 7027 |

What the echo should do: after a heavy read ends, say it in past tense ("Checked Bracket for printing: printable"); frame the selected object (2008-2012); light no button and keep the view for a measure-only gen call; select the changed screw and say its new length in fastener_set; make covering bodies see-through on part_primitive / part_boolean / cut checks.

---

## 2. Texturizer (14)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 0001-part_primitive | part_primitive | GOOD | Grip selected, ring on Box. |
| 0003-texture_list | texture_list | GOOD | "25 found". |
| 0006-texture_settings | texture_settings | GOOD | "Read the texture settings"; preview shows; ring. |
| 0010-texture_apply | texture_apply | BAD | Panel now Hexagon, but 3D view completely empty. |
| 0011-texture_check | texture_check | MINOR | Triangle count; Grip_hex not visible. |
| 0012-view_snapshot | view_snapshot | MINOR | Kept 0011 caption; empty view. |
| 0013-texture_draft | texture_draft | BAD | Empty view, no grey draft; caption help text cut. |
| 0014-texture_preview | texture_preview | BAD | No preview drawn; one ring only. |
| 0015-texture_set | texture_set | MINOR | Panel Fine Leather, good words; no preview. |
| 0016-texture_mask | texture_mask | MINOR | "Kept Face5 ... plain"; "brush: 0 triangles"; no mark. |
| 0019-texture_layer | texture_layer | MINOR | Layer 2 in panel; caption says "layer 1". |
| 1015-texture_export | texture_export | MINOR | Triangle count, no file name; no ring; empty view. |
| 2000-texture_prepare | texture_prepare | MINOR | Stale caption gone; ring on prepare; empty view. |
| 2002-object_set | object_set | MINOR | Panel 12.0 mm; Grip not shown or selected. |

Numbers: ring visible 10/14; one ring at a time in every picture. Caption 14/14, stale 0. Result selected 1/14 (0001).

### Round-4 Texturizer problems

| Problem | Status | Pictures |
|---|---|---|
| texture_apply panel shows Knurling, not Hexagon | FIXED (panel Layer 1 Hexagon, tile chosen) | 0010 |
| Preview not following set / mask / layer | WORSE: no preview or model drawn at all | 0010-2002 |
| Two rings at once | FIXED | 0013-0019 |
| texture_prepare stale caption | FIXED | 2000 |
| texture_export words without file | NOT FIXED | 1015 |
| texture_draft caption cut off | NOT FIXED | 0013 |
| texture_settings tool-name caption | FIXED | 0006 |
| texture_mask "0 triangles" | PARTLY (Face5 named; "brush: 0 triangles" kept) | 0016 |
| Grip never selected | NOT FIXED | 0006-2002 |
| view_snapshot words | NOT FIXED | 0012 |
| Preview leaks into other documents | FIXED (Tutor 0001, 0009, 0013 clean; preview stays in TextureGrip) | Tutor all |

### New Texturizer problems
- **Empty 3D view from texture_apply on** (0010-2002; checked by pixels: no drawn pixel in 0010). Neither Grip, Grip_hex, the grey draft nor the preview shows. Probably the new "remove the preview node" fix (or apply hiding Grip) also removes or hides what should stay. The echo should show and select Grip_hex after apply, the draft/preview on the draft tools, and Grip after object_set.
- Layer numbers in words are 0-based ("layer 0", "Added layer 1") while the panel shows Layer 1 / Layer 2 (0015, 0016, 0019).

---

## 3. Tutor (4)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 0001-part_primitive | part_primitive | GOOD | PointBox shown and selected; no preview leak. |
| 0002-tutor_point | tutor_point | MINOR | All four targets shown; bubble whole but beside tree row, not face. |
| 0009-tutor | tutor (start, demo) | MINOR | Bubble whole (4 steps + why); top-left anchor; echo + tutor rings. |
| 0013-tutor_watch | tutor_watch | GOOD | Sketch on XZ, Sketcher toolbars, clean view. |

### tutor_point targets (0002)
- Face: YES. Top face lit, dot "1" on it.
- Tree: YES. Model tab in front; ring 2 on the PointBox ROW (its top edge runs through the "TutorRest" label above).
- Command (Fit All): ring 3. View (3d): ring 4.
- Bubble text: whole ("This is the top face of the box."). Arrow points at the tree row, not at face 1.
- Echo ring on Part Box still lit with the tutor rings.

### Round-4 Tutor problems

| Problem | Status | Pictures |
|---|---|---|
| PointBox not in view (preview leak) | FIXED | 0001, 0002 |
| Face pointer missing | FIXED | 0002 |
| Tree pointer on Model tab | FIXED | 0002 |
| Bubble clips text | FIXED | 0002, 0009 |
| Bubble anchored top left | PARTLY (0002 next to tree row; 0009 still top-left corner) | 0002, 0009 |
| Echo ring + tutor ring together | NOT FIXED (by design per round6 §9) | 0002, 0009 |
| Preview leak in 0009 / 0013 | FIXED | 0009, 0013 |

---

## Top problems
1. Texturizer 3D view empty from texture_apply on: Grip_hex, draft and preview never drawn (0010-2002).
2. part_boolean cut hidden under the brackets; covering bodies still opaque (2015, 2017, 2019).
3. Workshop selection/framing: slice pictures select a Bracket cut off at the left edge; status bar empty (2008-2012).
4. A loose screw stays below the body after fastener_set / fastener_print; changed screw not selected (5015, 6002).
5. Results still missing from words: mass_* (1011, 1012, 1014, 7015), list counts, raw help text (7023, 7026), texture_export file.

PROVEN_LIVE Workshop: pd_body_new, sketch_new, sketch_add, pd_pad, fit, hw_hole, thread_lookup, thread_identify, dfm_check, part_review, part_transform, hw_embed_list, hw_pauses, slice, slicer_presets, slice_with, slice_read, printer_list, part_primitive, cut_check, cut_export, mill_check, mill_export, gen_make, body_check, gen_part, fastener_types, fastener_add, fastener_list, fastener_set, fastener_print, macro_save, macro_list, macro_show, macro_unapprove, history_checkpoint, app_recover, pref_history, pref_set, pref_reset, printer_add, export
NOT_PROVEN Workshop: setup (nothing shown), part_spec (tool-name caption), thread_cut (thread not visible), mass_properties (no result), mass_target (no result), mass_ballast (no mark), mass_calibrate (no result), hw_embed (pocket hidden), hw_unembed (no visible change), part_boolean (hole hidden), fea_frame (no frame drawn; mill ring and Block kept)
PROVEN_LIVE Texturizer: part_primitive, texture_list, texture_settings, texture_check, texture_set, texture_layer, texture_export, texture_prepare, object_set
NOT_PROVEN Texturizer: texture_apply (empty 3D view), view_snapshot (empty view, kept caption), texture_draft (no draft drawn), texture_preview (no preview drawn), texture_mask (no face mark)
PROVEN_LIVE Tutor: part_primitive, tutor_point, tutor, tutor_watch
NOT_PROVEN Tutor: none
