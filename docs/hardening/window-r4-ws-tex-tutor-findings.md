# Window review, round 4: Workshop, Texturizer, Tutor

FreeCAD 1.1.3 with Agent Link, after echo round 4. 71 pictures (Workshop 53, Texturizer 14, Tutor 4). I looked at every picture listed in pictures.json.

Rating: GOOD = result shows, only known general problems. MINOR = result shows, small family problem. BAD = result not visible, stale or wrong result, or a leftover / error in the view.

Report view: no new red text in Workshop or Texturizer. No QThread lines. No restart or recovery errors before Tutor. New orange Texturizer lines from 04:30:39 (see Texturizer).

---

## 1. Workshop (53). Round 4: GOOD 15, MINOR 29, BAD 9. Round 3: 13 / 30 / 10.

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 0001-pd_body_new | pd_body_new | GOOD | Part Design, ring on Body, caption "Made a new body Bracket: 3 axes". |
| 0002-sketch_new | sketch_new | GOOD | Sketcher edit toolbars, sketch panel, caption names plane. |
| 0003-sketch_add | sketch_add | GOOD | Framed by its lines, lines selected, ring on Rectangle. |
| 0004-pd_pad | pd_pad | GOOD | Ring on Pad, caption with volume. Empty Tasks dock on right. |
| 0005-setup | setup | MINOR | Caption only "Setup"; stays Part Design; Pad ring kept. |
| 0010-part_spec | part_spec | MINOR | Part workbench, caption "Part spec" only, body deselected. |
| 0012-fit | fit | MINOR | Good caption; Part workbench; Agent Link tab in front. |
| 0016-hw_hole | hw_hole | MINOR | Hole shows, ring on Hole; caption "Hw hole on Bracket". |
| 1004-thread_lookup | thread_lookup | GOOD | Read; caption gives source of thread data. |
| 1007-thread_identify | thread_identify | MINOR | Caption now "10 mm", but no thread name; face not marked. |
| 1008-thread_cut | thread_cut | MINOR | Body selected; no ring; thread not visible. |
| 1009-dfm_check | dfm_check | BAD | Stale caption "Thread cut on Bracket". No DFM result. |
| 1010-part_review | part_review | BAD | Same stale caption; no review. |
| 1011-mass_properties | mass_properties | MINOR | Caption has no numbers; no CoM mark. |
| 1012-mass_target | mass_target | MINOR | Caption has no result. |
| 1014-mass_ballast | mass_ballast | MINOR | No ballast mark; caption tool name. |
| 1017-part_transform | part_transform | MINOR | Copy shown; original cut at left; caption "Moved" for a copy. |
| 1019-hw_embed | hw_embed | MINOR | Make bench, ring on Embed; pocket hidden inside body. |
| 2001-hw_embed_list | hw_embed_list | MINOR | No count in caption. |
| 2002-hw_pauses | hw_pauses | GOOD | "1 found". |
| 2004-hw_unembed | hw_unembed | MINOR | No visible change; ring gone. |
| 2008-slice | slice | BAD | Stale caption from mass_calibrate; empty status bar; selection jumped to the original Bracket, cut off at left. |
| 2009-slicer_presets | slicer_presets | MINOR | "Listed orcaslicer presets", no count. |
| 2010-slice_with | slice_with | BAD | Stale caption "Listed orcaslicer presets"; empty status bar. |
| 2011-slice_read | slice_read | MINOR | "Read ... wrote bracket-orca.3mf"; no time or filament. |
| 2012-printer_list | printer_list | MINOR | "Listed Printer", no count. |
| 2015-part_primitive | part_primitive | MINOR | Plate selected, ring on Box; brackets cover it. |
| 2017-part_boolean | part_boolean | BAD | Ring on Cut, caption; hole hidden under brackets. |
| 2019-cut_check | cut_check | MINOR | Verdict "pass" now. Plate covered; ring on Setups button. |
| 3001-cut_export | cut_export | MINOR | Caption "Exported Cut on Plate: 3 mm" (shorter than r3, no file); no sheet layout. |
| 3008-mill_check | mill_check | MINOR | Verdict "pass with warnings" now; ring on Setups. |
| 3009-mill_export | mill_export | GOOD | Fixed: all parts visible, no stock box; Block selected; ring on mill export. |
| 3012-fea_frame | fea_frame | BAD | Stale caption "Exported Mill on Block"; stale ring; no frame. |
| 4001-gen_make | gen_make | BAD | View still empty (948 mm wide); bin not shown. Ring on PD additive primitive. |
| 4006-body_check | body_check | GOOD | Bin selected, "Checked Bin: sound". |
| 4007-gen_part | gen_part | BAD | Shows the old Bin, not the baseplate; not selected. |
| 5007-fastener_types | fastener_types | MINOR | "6 found"; stays Part Design; Hole ring kept. |
| 5011-fastener_add | fastener_add | MINOR | Screw selected, ring on ISO4762; body hides shank; 4 toolbar rows. |
| 5014-fastener_list | fastener_list | MINOR | Read tool zooms to screw alone; no count. |
| 5015-fastener_set | fastener_set | BAD | Screw again outside, below the body; not selected. |
| 6002-fastener_print | fastener_print | MINOR | New head + hole show, not selected; loose screw still there. |
| 7002-macro_save | macro_save | GOOD | Caption names saved file. |
| 7005-macro_list | macro_list | MINOR | No count. |
| 7006-macro_show | macro_show | MINOR | Caption "...: no" (meaningless); macro text not shown. |
| 7011-macro_unapprove | macro_unapprove | GOOD | Names macro. |
| 7015-mass_calibrate | mass_calibrate | MINOR | No result in caption. |
| 7022-history_checkpoint | history_checkpoint | GOOD | Names file written. |
| 7023-app_recover | app_recover | MINOR | Raw help text with braces. |
| 7026-pref_history | pref_history | MINOR | Raw help text with braces. |
| 7027-pref_set | pref_set | GOOD | Caption names the setting path (not the value). |
| 7029-pref_reset | pref_reset | GOOD | Names path. |
| 7033-printer_add | printer_add | GOOD | Names printer. |
| 7041-export | export | GOOD | Names file. Probe box not selected. |

Numbers: ring visible 29/53; ring on the real button of that call 11 (0001, 0003, 0004, 0016, 1019, 2015, 2017, 3009, 5011, 5015, 6002); the rest are kept rings or wrong maps. Caption 53/53, stale 5 (1009, 1010, 2008, 2010, 3012). Something selected 41/53 (often whole body or an earlier object). Sketch edit 0002/0003: Sketcher toolbars show.

### Round-3 Workshop problems
| Problem | Status | Pictures |
|---|---|---|
| Stale captions dfm_check, part_review, slice, slice_with, fea_frame | NOT FIXED | 1009, 1010, 2008, 2010, 3012 |
| mill_export hides all parts | FIXED | 3009 |
| Verdict in check captions | PARTLY: cut_check, mill_check fixed; thread_identify gives "10 mm" only; mass_properties, mass_target, mass_calibrate not | 2019, 3008, 1007, 1011, 1012, 7015 |
| Lists without count | NOT FIXED | 2001, 2009, 2012, 5014, 7005 |
| Raw help text in caption | NOT FIXED | 7023, 7026 |
| gen_make empty view | NOT FIXED | 4001 |
| gen_part shows old Bin | NOT FIXED | 4007 |
| fastener_set screw outside body | NOT FIXED | 5015, 6002 |
| Covering bodies not see-through | NOT FIXED | 2015, 2017, 2019, 1019, 5011 |
| Wrong / no workbench switch | NOT FIXED | 0005, 0010, 0012, 1008-1014, 5007 |
| Agent Link / Make tab in front of Model | NOT FIXED | from 0010 on |
| Ring map: cut/mill checks light Setups; fea keeps mill ring | NOT FIXED | 2019, 3001, 3008, 3012 |
| fastener_list (read) changes view | NOT FIXED | 5014 |
| pref_set caption | PARTLY (path, no value) | 7027 |
| part_transform "Moved" for a copy | NOT FIXED | 1017 |

### New Workshop problems
- 2008, 2010: status bar is empty while the 3D caption is stale.
- 2008-2012: selection jumps to the original Bracket, cut off at the left edge.
- 4001-4007: gen_make / gen_part / body_check ring the Part Design additive primitive button.
- 7006 caption ends in ": no". 3001 caption lost the kerf words. 7041 export does not select the exported object.

---

## 2. Texturizer (14). Round 4: GOOD 3, MINOR 9, BAD 2. Round 3: 4 / 6 / 4.

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 0001-part_primitive | part_primitive | GOOD | Grip selected, ring on Box, caption. |
| 0003-texture_list | texture_list | GOOD | "25 found". |
| 0006-texture_settings | texture_settings | MINOR | Now Texturizer bench + ring on preview button; caption tool name only. |
| 0010-texture_apply | texture_apply | BAD | Caption fixed ("Textured Grip as Grip_hex: 29666 triangles"), but panel still Layer 1 Knurling, not Hexagon; no ring. |
| 0011-texture_check | texture_check | GOOD | Caption with triangle count. |
| 0012-view_snapshot | view_snapshot | MINOR | Kept caption; nothing says snapshot. |
| 0013-texture_draft | texture_draft | MINOR | Ring on Reset, grey draft; caption cut off. |
| 0014-texture_preview | texture_preview | MINOR | Caption "Suggested a refine length..."; no QThread errors. Two rings (Reset kept + Preview). |
| 0015-texture_set | texture_set | MINOR | Panel Fine Leather; 3D preview unchanged; caption "Set Texture". Two rings. |
| 0016-texture_mask | texture_mask | MINOR | Caption "Texture mask: 0 triangles"; Face5 not marked. Two rings. |
| 0019-texture_layer | texture_layer | MINOR | Layer 2 in panel; caption tool name. Two rings. |
| 1015-texture_export | texture_export | MINOR | Caption "Updated Grip_textured: 25506 triangles" (not stale, but no file); no ring; front view; no QThread errors. |
| 2000-texture_prepare | texture_prepare | BAD | Stale caption "Checked Texture on grip_textured.stl". |
| 2002-object_set | object_set | MINOR | Caption "Set Grip Height to 12 mm"; panel 12.0 mm; Grip not shown or selected. |

Numbers: ring visible 8/14 (0001, 0003, 0006, 0013, 0014, 0015, 0016, 0019); on a Texturizer button 6; two rings at once 4 (0014-0019). Caption 14/14, stale 1 (2000). Result selected 2/14.

### Round-3 Texturizer problems
| Problem | Status | Pictures |
|---|---|---|
| QThread errors in Report view | FIXED | 0014, 1015 clean; no restart before Tutor |
| apply shows Knurling not Hexagon | NOT FIXED (caption fixed) | 0010 |
| Preview not following set / mask / layer | NOT FIXED | 0015, 0016, 0019 |
| No ring on Texturizer buttons | PARTLY | rings 0006, 0013-0019; none 0010, 1015 |
| Stale captions | PARTLY: 0014 fixed, 1015 not stale but no file, 2000 not fixed | 0014, 1015, 2000 |
| 0013 caption cut off | NOT FIXED | 0013 |
| Grip never selected | NOT FIXED | 0006-2002 |

### New Texturizer problems
- Two rings at once: Reset ring kept while Preview ring lights (0014-0019). Keep one ring.
- 0016 caption "0 triangles" for a mask call; say which faces stay plain.
- Preview leaks into other documents: the TutorRest and BikeStem views show a teal/orange textured PointBox preview (Tutor 0001, 0009, 0013). Report: "PointBox (the sidebar's draft): 2 new faces since texturing". The sidebar draft follows the active document. Close the draft and remove the preview node when the document changes.

---

## 3. Tutor (4). Round 4: GOOD 0, MINOR 1, BAD 3. Round 3: 2 / 2 / 0. WORSE.

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 0001-part_primitive | part_primitive | BAD | PointBox not visible; view 5.8 mm wide, only a textured preview corner top right. Ring on Box. |
| 0002-tutor_point | tutor_point | BAD | Face dot missing (box not in view). Pointer 2 on "Model" tab, not the PointBox row. Rings 3 (Fit All) and 4 (3D view) show. Bubble text cut in half, top left. |
| 0009-tutor | tutor (start, demo) | BAD | A textured box (PointBox preview leak) fills the empty BikeStem body. Two rings (Body echo + tutor 1). Bubble cuts step 4, anchored top left. |
| 0013-tutor_watch | tutor_watch | MINOR | Sketch on XZ, Sketcher toolbars, caption. Teal preview strip still in the view. |

Numbers: ring 3/4 (plus tutor rings in 0002, 0009). Caption 4/4. Result selected 0/4.

### tutor_point targets
- Face: NO (WORSE). Nothing visible to point at; Fit All target did not frame the box.
- Tree: PARTLY. Pointer 2 sits on the Model tab; the PointBox row is not shown or ringed.
- Command (Fit All): yes, ring 3. View (3d): yes, ring 4.
- Bubble: NOT FIXED. Text still clipped; arrow at top left, not at the face.

### Round-3 Tutor problems
| Problem | Status | Pictures |
|---|---|---|
| Tree target not shown | PARTLY | 0002 |
| Bubble clips text | NOT FIXED | 0002, 0009 |
| Echo ring + tutor ring together | NOT FIXED | 0009 |
| Bubble anchored top left | NOT FIXED | 0002, 0009 |
| Restart / recovery errors | FIXED | none now |

---

## Counts

| Family | R4 GOOD | R4 MINOR | R4 BAD | R3 G/M/B | Ring (real button) | Caption (stale) | Selected |
|---|---|---|---|---|---|---|---|
| Workshop | 15 | 29 | 9 | 13/30/10 | 29 (11) | 53 (5) | 41 |
| Texturizer | 3 | 9 | 2 | 4/6/4 | 8 (6) | 14 (1) | 2 |
| Tutor | 0 | 1 | 3 | 2/2/0 | 3 | 4 (0) | 0 |

## Top problems
1. Texturizer preview leaks into other documents (Tutor 0001, 0002, 0009, 0013): it hides PointBox and breaks tutor_point and the tutor demo.
2. Heavy-read captions still stale: dfm_check, part_review, slice, slice_with, fea_frame, texture_prepare (1009, 1010, 2008, 2010, 3012, 2000).
3. gen_make empty view and gen_part shows the old Bin (4001, 4007).
4. fastener_set moves the screw out of the body (5015).
5. texture_apply panel shows Knurling, and the preview does not follow set/mask/layer (0010, 0015-0019); plus two rings at once.

PROVEN_LIVE Workshop: pd_body_new, sketch_new, sketch_add, pd_pad, fit, hw_hole, thread_lookup, thread_identify, part_transform, hw_embed_list, hw_pauses, slicer_presets, slice_read, printer_list, part_primitive, cut_check, cut_export, mill_check, mill_export, body_check, fastener_types, fastener_add, fastener_list, fastener_print, macro_save, macro_list, macro_show, macro_unapprove, history_checkpoint, app_recover, pref_history, pref_set, pref_reset, printer_add, export
NOT_PROVEN Workshop: setup (nothing shown), part_spec (tool-name caption), thread_cut (thread not visible), dfm_check (stale caption), part_review (stale caption), mass_properties (no result), mass_target (no result), mass_ballast (no mark), mass_calibrate (no result), hw_embed (pocket hidden), hw_unembed (no visible change), slice (stale caption), slice_with (stale caption), part_boolean (hole hidden), fea_frame (stale caption), gen_make (empty view), gen_part (old Bin shown), fastener_set (screw outside body)
PROVEN_LIVE Texturizer: part_primitive, texture_list, texture_check, texture_draft, texture_preview, texture_layer, texture_export, object_set
NOT_PROVEN Texturizer: texture_apply (panel shows Knurling), texture_settings (settings not shown), view_snapshot (nothing says snapshot), texture_set (preview not updated), texture_mask (no mark, "0 triangles"), texture_prepare (stale caption)
PROVEN_LIVE Tutor: tutor_watch
NOT_PROVEN Tutor: part_primitive (box not in view, preview leak), tutor_point (no face pointer, tree pointer on Model tab, bubble clipped), tutor (preview leak, two rings, bubble clipped)
