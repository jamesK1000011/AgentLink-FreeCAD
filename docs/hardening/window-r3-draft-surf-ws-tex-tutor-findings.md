# Window review, round 3: Draft, Surface, Workshop, Texturizer, Tutor

FreeCAD 1.1.3 with Agent Link, after echo round 3. 106 pictures (Draft 20, Surface 15, Workshop 53, Texturizer 14, Tutor 4). I looked at each picture, and I enlarged the toolbar rows of all the pictures to find the rings.

How I rated:
- GOOD: the window shows the result correctly. The only problems are known general problems (stale Property panel, whole body selected, no ring, caption that is only the tool name, fit to the whole document).
- MINOR: the result shows, but with a small problem that is particular to this family.
- BAD: you cannot see the result, the window shows a stale or wrong result, or new error text shows.

General notes for all families:
- G1 Caption: every picture has the "+ Agent: ..." caption at the bottom right of the 3D view, and the same words in the status bar. This is fixed. (The ✦ glyph shows as "+".)
- G2 Left panel: in Draft and Surface the Model tab is in front. This is fixed. In the add-on pictures, the Agent Link, Make or Texturizer tab is in front instead (see Workshop).
- G3 Property panel: it often still shows the object of an earlier call (Draft 063/065/067/068, Surface 005/011/013/017/030/045/047).
- G4 Report view: old red text stays on screen. Draft fillet error from 02:44:42 shows from Draft 060 to the end of Texturizer. New red text: Texturizer QThread errors (from tex 0014) and the recovery errors in Tutor (see Tutor).
- G5 Rule "selection, ring and caption stay until the next changing call": this works. The ring and selection stay on read calls (for example ws 0005, 1004, 1007, 2001, 2002, 7005-7011, tex 0003, 0006). But in some pictures the kept caption is the caption of a much earlier call, so the window seems to show a wrong result (see the "stale caption" rows).

---

## 1. Draft (20 pictures). Old echo: GOOD 3, MINOR 13, BAD 4

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 001-draft_plane | draft_plane | GOOD | Draft workbench, Top plane is shown green, Top row selected in tree, caption "Draft plane on Top". |
| 002-draft_shape | draft_shape | GOOD | Arc30 is green and fills the view. Tree row and Property panel still show Top. |
| 006-draft_modify | draft_modify | MINOR | Upgrade made two wires (Wire, Wire001), not one face. Both are selected. No ring on Upgrade. |
| 010-draft_link_array | draft_link_array | MINOR | Ring is now selected (green), fixed. But 3 of 4 copies are half hidden under the Hex face. Property panel shows Wire. |
| 011-draft_dimension | draft_dimension | GOOD | ToHexTop selected, Dimension button has a ring, caption "Added a dimension". |
| 015-draft_style | draft_style | MINOR | The dimensions now show the new style. Nothing is selected and no ring. The right dock shows the Draft "Create objects" list. |
| 023-draft_fix | draft_fix | GOOD | Fixed: ToHexTop is selected and its properties show. Caption "Fixed Draft" does not say "flipped". |
| 024-draft_label | draft_label | MINOR | HexArea selected, ring on Label, properties show. The label text is still too small to read. |
| 027-draft_clone | draft_clone | GOOD | HexHalf fills the view, selected, ring on Clone, properties show. |
| 060-draft_layer | draft_layer | BAD | Layer not selected or shown; Property panel shows "Mark". Red fillet error in Report view. |
| 063-draft_hatch | draft_hatch | GOOD | Fixed: fit to Hex, hatch lines green. Property panel shows layer "Inner". No ring on Hatch. |
| 065-draft_to_sketch | draft_to_sketch | MINOR | FrameSketch selected (green outline), but it lies on Frame, so it looks like Frame. |
| 066-sketch_state | sketch_state | GOOD | FrameSketch selected; caption "Read FrameSketch: 4 degrees of freedom left". |
| 067-draft_from_sketch | draft_from_sketch | MINOR | New face selected and covers Frame. Caption "Draft from sketch" only. No z-fighting now. |
| 068-part_primitive | part_primitive | GOOD | Part workbench, Tag box selected, ring on Primitives. Property panel shows Wire006. |
| 069-draft_2d_view | draft_2d_view | BAD | Top view is now used, but TagTop is under the Tag box, not selected, and cannot be seen. |
| 072-draft_facebinder | draft_facebinder | GOOD | TagSkin (2 mm) shows clearly on the box top and is selected. No ring on Facebinder. |
| 074-draft_fonts | draft_fonts | MINOR | Read tool. Caption is only "Draft fonts"; no font names. The OnTag working plane is selected (kept from the call before). A grey sliver shows at the left edge of the view. |
| 076-draft_text | draft_text | GOOD | Fixed: fit to Plate, "AL-7" can be read, ring on Text, caption "Wrote text in the model". |
| 078-draft_array | draft_array | GOOD | 2x2 plates with text, the copies selected, ring on Array, caption "Made an array". |

Counts: GOOD 11, MINOR 7, BAD 2. (Old echo: GOOD 3, MINOR 13, BAD 4.)

Round 3 numbers: ring visible 6/20 (011, 024, 027, 068, 076, 078). Caption 20/20. Result selected 16/20 (not 015, 060, 069, 074). Sketch edit: no Draft picture has a sketch in edit, so the Sketcher edit toolbars are not tested here.

What is fixed since the old echo:
- Captions in all pictures (old: none).
- Model tab in front (old: Tasks tab).
- Fit to the new object: hatch (063), clone (027), text (076) and array (078) now fill the view; text can be read.
- Correct selection: draft_fix selects ToHexTop (023), link array selects Ring (010), clone and text select the result.
- Z-fighting of the from_sketch face is gone (067).
- draft_2d_view now uses the top view (069), but the result is still hidden.

### Draft-particular problems still open
- 060 draft_layer: select the new layer in the tree, expand it, and show its name and members in the caption ("Layer Outline: Frame, Hex").
- 069 draft_2d_view: TagTop is under Tag. Make Tag see-through (as the round 3 rule says for covering objects) or hide it, and select TagTop.
- 065 and 067: the new sketch or face lies exactly on Frame. Make Frame see-through or hide it for the echo.
- 010: array copies lie under the Hex face. Make the covering Hex see-through.
- Rings are missing for Upgrade (006), Style (015), Layer (060), Hatch (063), To-sketch (065), Facebinder (072). These buttons exist in the Draft toolbar.
- 024: zoom closer on labels so the text can be read.
- 074 draft_fonts and 015 draft_style: put the result in the caption (font names, style name and values).
- The right dock shows the Draft "Modify Objects" / "Create objects" panel in every Draft picture. It takes 40% of the width and makes the 3D view narrow. Hide it or use the left panel.

---

## 2. Surface (15 pictures). Old echo: GOOD 2, MINOR 5, BAD 8

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 001-part_wire | part_wire | GOOD | Part workbench, La selected, properties show, caption. |
| 005-surface_boundary | surface_boundary | GOOD | Patch is green and fills the view. Tree row and Property panel still show Ld. |
| 007-surface_fill | surface_fill | BAD | Looks the same as 005. Filled lies on Patch; Patch is not see-through; Property panel shows Patch. |
| 011-surface_sections | surface_sections | GOOD | Fixed: Plate is see-through, the Ruled surface shows green inside it. |
| 013-surface_extend | surface_extend | GOOD | Wider is green around Plate. Property panel shows Ruled. |
| 016-part_primitive | part_primitive | GOOD | Block selected, ring on Primitives, Block properties show (fixed). |
| 017-surface_cut | surface_cut | MINOR | Half now shows (green, with blotches) under see-through Plate, but Block is not see-through, fills half the view and is cut off. |
| 021-surface_sew | surface_sew | MINOR | "Open box" selected and its properties show. The top of the source Cube shows grey; a grey object is cut at the top-left corner. |
| 024-surface_thicken | surface_thicken | GOOD | Fixed: Block and Plate are see-through, Slab shows green. |
| 028-surface_blend | surface_blend | GOOD | Fixed: fit to Blend, the curve is clear, properties show. |
| 030-draft_shape | draft_shape | GOOD | Draft workbench, spline G1 green. Status bar length (15.37 mm) is from Blend. |
| 045-surface_loft | surface_loft | GOOD | Fixed: fit to Panel, Panel green. Property panel shows WikiBlend. |
| 047-surface_points | surface_points | GOOD | Fixed: fit to Fitted, green. |
| 049-meshobj_from_shape | meshobj_from_shape | MINOR | Mesh workbench, mesh fills the view, Mesh Info panel now has numbers (fixed). The mesh is not green (not selected); Property panel shows Fitted. |
| 050-surface_polynomial | surface_polynomial | BAD | Camera is too close: one large grey surface fills the view and runs off the edges. Quadric is not selected or framed. |

Counts: GOOD 10, MINOR 3, BAD 2. (Old echo: GOOD 2, MINOR 5, BAD 8.)

Round 3 numbers: ring visible 1/15 (016 only). Caption 15/15. Result selected 13/15 (not 049, 050). No sketch edit in this family.

What is fixed since the old echo:
- See-through covering bodies: 011 sections, 024 thicken, and partly 017 cut now show the thin result.
- Fit to the new object: 028, 045, 047 now frame the new object, not the large saddle.
- Mesh Info panel is filled (049).
- Captions in all pictures; Model tab in front.

### Surface-particular problems still open
- No ring on any Surface tool (005, 007, 011, 013, 017, 021, 024, 028, 045, 047, 050). The Surface toolbar has Filling, Sections, Extend and Blend curve buttons. Light Filling for boundary/fill, Sections, Extend, Blend curve. Tools with no button (cut, sew, thicken, loft, points, polynomial) could light the Part button that is closest, or none.
- 007 surface_fill: Filled lies exactly on Patch. Make Patch see-through or hide it. Check that Filled is a real Surface Filling (old note).
- 017 surface_cut: make the "by" body (Block) see-through too, and fit to Half.
- 050 surface_polynomial: the fit does not work for this result. Fit to Quadric's bounding box (or clip it) and select it.
- 049: select the new mesh.

---

## 3. Workshop add-on (53 pictures, first review: make / parts / fasteners / documents tools)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 0001-pd_body_new | pd_body_new | GOOD | Part Design, Bracket selected, ring on Body, caption. |
| 0002-sketch_new | sketch_new | GOOD | Sketcher edit toolbars show, sketch panel in Tasks, caption "Started a sketch on XY of Bracket". |
| 0003-sketch_add | sketch_add | GOOD | Rectangle framed by its own lines, lines selected, ring on Rectangle. |
| 0004-pd_pad | pd_pad | GOOD | Pad shown, ring on Pad, caption "Padded Base by 10 mm". Whole body selected; Property panel shows Base. |
| 0005-setup | setup | MINOR | Caption is only "Setup". Nothing shows the setups. Pad ring stays. |
| 0010-part_spec | part_spec | MINOR | Workbench goes to Part, body is deselected, Agent Link tab comes to front. Caption only "Part spec"; spec values not shown. |
| 0012-fit | fit | MINOR | Good caption ("every hole and fit sized from now on takes it ..."). Part workbench, Agent Link tab in front. |
| 0016-hw_hole | hw_hole | MINOR | Hole shows, ring on Hole. Agent Link tab in front of Model. Caption "Hw hole on Bracket". |
| 1004-thread_lookup | thread_lookup | GOOD | Read tool; caption gives the source of the thread data. |
| 1007-thread_identify | thread_identify | MINOR | Caption does not say which thread was found; the face near the point is not marked. |
| 1008-thread_cut | thread_cut | MINOR | Body selected, caption "Thread cut on Bracket". Nothing shows the thread; no ring. |
| 1009-dfm_check | dfm_check | BAD | Stale caption "Thread cut on Bracket". No DFM result (no colour map, no list). |
| 1010-part_review | part_review | BAD | Same window as 1009: stale caption, no review shown. |
| 1011-mass_properties | mass_properties | MINOR | Caption has no numbers (mass, centre of mass); no centre-of-mass mark. |
| 1012-mass_target | mass_target | MINOR | Caption has no result; no target mark. |
| 1014-mass_ballast | mass_ballast | MINOR | No ballast pocket or mark is visible; caption only names the tool. |
| 1017-part_transform | part_transform | MINOR | Copy "Bracket plain" selected; the original is cut at the left edge. Caption "Moved Bracket" (it was a copy). Part workbench. |
| 1019-hw_embed | hw_embed | MINOR | Make workbench, ring on Embed, Make tab in front. The magnet pocket is inside the body and cannot be seen. |
| 2001-hw_embed_list | hw_embed_list | MINOR | Caption "Listed Hw embed on Bracket plain" with no count. |
| 2002-hw_pauses | hw_pauses | GOOD | Caption "1 found". |
| 2004-hw_unembed | hw_unembed | MINOR | No visible change (pocket was inside). |
| 2008-slice | slice | BAD | Stale caption from an earlier mass_calibrate ("refused (The print weighed 1 g ...)"). Slice result not shown; selected body is cut off at the left edge. |
| 2009-slicer_presets | slicer_presets | MINOR | Caption "Slicer presets on machine"; no list or count. |
| 2010-slice_with | slice_with | BAD | Stale caption "Slicer presets on machine". OrcaSlicer project result not shown. |
| 2011-slice_read | slice_read | MINOR | Caption "Read Slice on bracket-orca.3mf: wrote bracket-orca.3mf" (a read that says "wrote"); no print time or filament. |
| 2012-printer_list | printer_list | MINOR | Caption "Listed Printer"; no count or names. |
| 2015-part_primitive | part_primitive | MINOR | Plate selected, ring. The two brackets cover most of Plate (not see-through). |
| 2017-part_boolean | part_boolean | BAD | Ring on Cut and caption, but the cut hole cannot be seen; the brackets cover Plate. |
| 2019-cut_check | cut_check | MINOR | Plate selected; caption "Checked Cut on Plate" has no verdict. Plate still covered. |
| 3001-cut_export | cut_export | MINOR | Good caption about kerf; nesting lines in Report view. The 4-copy sheet layout is not shown. |
| 3008-mill_check | mill_check | MINOR | Block selected (pocket visible). Caption has no verdict. Block sits on the brackets. |
| 3009-mill_export | mill_export | BAD | All parts are gone from the view; only a wireframe stock box shows (CAM job left over). Block is not visible. |
| 3012-fea_frame | fea_frame | BAD | Same window as 3009: stale caption "Exported Mill on Block", stale ring. No beam, supports or result. |
| 4001-gen_make | gen_make | BAD | New PartsModel document, but the 3D view is empty; the bin does not show. Caption "Made Parts". |
| 4006-body_check | body_check | GOOD | Bin shows, selected, caption "Checked Bin: sound". |
| 4007-gen_part | gen_part | BAD | Baseplate not visible; the old Bin shows, not selected. Caption "Parts part". |
| 5007-fastener_types | fastener_types | MINOR | Caption "6 found". Stays in Part Design; ring on Hole is kept from earlier, not a fastener button. |
| 5011-fastener_add | fastener_add | MINOR | Screw selected in the hole, Fasteners workbench, ring on ISO4762. Body hides the shank (not see-through). Four Fasteners toolbar rows push the view down. |
| 5014-fastener_list | fastener_list | MINOR | Read tool, but the view zooms to the screw alone and the body is hidden. Caption has no count. |
| 5015-fastener_set | fastener_set | BAD | After length 20, the screw is outside the body (below it), not in the hole. Not selected. Possible tool bug. |
| 6002-fastener_print | fastener_print | MINOR | A second screw head and a small hole show; result not selected; caption only the tool name. The loose screw from 5015 is still there. |
| 7002-macro_save | macro_save | GOOD | Caption says where the macro is saved. |
| 7005-macro_list | macro_list | MINOR | Caption "Listed Macros"; no count. |
| 7006-macro_show | macro_show | MINOR | Caption only the tool name; macro text not shown. |
| 7011-macro_unapprove | macro_unapprove | GOOD | Caption names the macro. |
| 7015-mass_calibrate | mass_calibrate | MINOR | Caption has no result (compare 2008 where the result shows). |
| 7022-history_checkpoint | history_checkpoint | GOOD | Caption explains the checkpoint. |
| 7023-app_recover | app_recover | MINOR | Caption shows raw help text with braces ("action auto { documents } ..."). |
| 7026-pref_history | pref_history | MINOR | Caption shows raw help text with braces ("pref_rollback { to: change } ..."). |
| 7027-pref_set | pref_set | MINOR | Caption "Changed a setting" does not name the setting or the value. |
| 7029-pref_reset | pref_reset | GOOD | Caption names the reset path. |
| 7033-printer_add | printer_add | GOOD | Caption names the printer. |
| 7041-export | export | GOOD | Caption names the file written. |

Counts: GOOD 13, MINOR 30, BAD 10.

Round 3 numbers: ring visible 29/53 (0001, 0003, 0004, 0005, 0016, 1004, 1007, 1019, 2001, 2002, 2015, 2017, 2019, 3001, 3008, 3009, 3012, 4001, 4006, 4007, 5007, 5011, 5014, 5015, 6002, 7002, 7005, 7006, 7011). Caption 53/53, but 5 are stale (1009, 1010, 2008, 2010, 3012). Something selected 38/53; often the whole body or an object from an earlier call. Sketch edit pictures 0002 and 0003: yes, the Sketcher edit toolbars show, and 0003 is framed by the sketch lines.

### Workshop-particular problems
- Stale captions make read and check tools look like they did nothing (1009, 1010, 2008, 2010, 3012). The rule that keeps the last changing caption is right for plain reads, but check and export tools have a result. dfm_check, part_review, slice, slice_with and fea_frame must write their own caption with the result (for example "DFM: 2 warnings - thin wall 0.8 mm").
- Checks without a verdict in the caption: thread_identify (1007), mass_properties (1011), mass_target (1012), cut_check (2019), mill_check (3008), mass_calibrate (7015). Put the main number or verdict in the caption. dfm_check and part_review should also show their colour map or marks in the 3D view.
- Lists without a count: hw_embed_list, slicer_presets, printer_list, macro_list, fastener_list (2001, 2009, 2012, 7005, 5014). Add "N found" as fastener_types and hw_pauses do.
- Raw help text in captions (7023 app_recover, 7026 pref_history): the caption shows usage text with braces. Use one plain sentence.
- 3009 mill_export: after export, all parts disappear and only a wireframe stock box is left. This is a leftover CAM job, or the job hid the parts. Remove the job or show the parts again; 3012 then keeps this broken view.
- 4001 gen_make: the new bin does not show; the view is empty (4.94 mm wide). Recompute and fit before the picture. 4007 gen_part: the baseplate does not show and is not selected; the old Bin is in the view. Hide or move the old Bin and fit to the new part.
- 5015 fastener_set: after setting length 20, the screw is outside the body, not in the hole. This looks like a tool bug (the fastener loses its placement or attachment when it is rebuilt). Check the placement after fastener_set.
- Covering objects are not see-through in this family: brackets cover Plate (2015, 2017, 2019), the body hides the screw shank (5011) and the embedded magnet (1019). Use see-through for the bodies around the result, as Surface now does.
- Wrong workbench or no workbench switch: part_spec and fit go to Part (0010, 0012); fastener_types stays in Part Design (5007); the Make tools 0005 setup and 1008-1014 stay in Part Design. These are Workshop tools; switch to Make (or Fasteners) and light its button.
- Left panel: from 0010 on, the Agent Link tab (or Make tab) is in front, not Model. The Make panel is useful for setup tools (Setups list shows the parts), but for model tools (hw_hole, part_transform, part_primitive, part_boolean, gen_make) bring Model to front.
- Ring maps: 2019 cut_check and 3008 mill_check light the first Make button (Setups); 3012 fea_frame keeps the mill-export ring. Check the button map for cut, mill and fea tools.
- 5014 fastener_list (a read tool) hides the body and zooms to the screw. A read tool should not change the view.
- 5011 Fasteners workbench adds four toolbar rows, which makes the 3D view small. Consider showing only the first row.

---

## 4. Texturizer add-on (14 pictures, first review)

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 0001-part_primitive | part_primitive | GOOD | Grip box selected, ring on Primitives, caption. |
| 0003-texture_list | texture_list | GOOD | Caption "Listed Texture: 25 found". Stays in Part (read tool). |
| 0006-texture_settings | texture_settings | MINOR | Caption only "Texture settings"; settings not shown; no switch to Texturizer. |
| 0010-texture_apply | texture_apply | BAD | Texturizer workbench and panel open, textured preview shows. But the panel shows Layer 1 "Knurling" selected, not "Hexagon" from the call, and the top looks like knurl. Caption only the tool name. No ring. |
| 0011-texture_check | texture_check | GOOD | Caption "Checked Texture on Grip_hex: textured". |
| 0012-view_snapshot | view_snapshot | MINOR | Read tool; caption is kept from 0011; nothing says a snapshot was taken. |
| 0013-texture_draft | texture_draft | MINOR | Draft started (grey preview), caption explains the next steps, but the caption is cut off ("then text..."). After reset the knurl preview still shows. |
| 0014-texture_preview | texture_preview | BAD | No change in the view; caption kept from 0013. New red text: four "QObject::startTimer: Timers can only be used with threads started with QThread". |
| 0015-texture_set | texture_set | MINOR | Panel now shows "Fine Leather" in Layer 1, but the 3D preview did not update (still knurl). Caption "Set Texture". |
| 0016-texture_mask | texture_mask | MINOR | Caption "these faces stay plain", but the preview does not show Face5 as plain or marked. |
| 0019-texture_layer | texture_layer | GOOD | Layer 2 added in the panel. Caption "Texture layer" only. |
| 1015-texture_export | texture_export | BAD | Caption "Texture apply" (stale, not export). The view switched to a front view of a preview. Six more QThread errors. |
| 2000-texture_prepare | texture_prepare | BAD | Caption kept from an earlier check ("Checked Texture on grip_textured.stl: textured001"); nothing about the prepared STL. |
| 2002-object_set | object_set | MINOR | Caption "Set Grip Height to 12 mm", panel shows 12.0 mm. Report view tells that the Layer 2 mask face is gone and Face6 is now smooth (useful). Grip box itself not shown or selected; only the preview. |

Counts: GOOD 4, MINOR 6, BAD 4.

Round 3 numbers: ring visible 3/14 (0001, 0003, 0006, all the Part Primitives ring). No Texturizer button is ever ringed. Caption 14/14, but 3 are stale (0014, 1015, 2000). Result selected 3/14 (only the Grip box in 0001-0006). No sketch edit in this family.

### Texturizer-particular problems
- QThread errors (0014 on): texture_preview and texture_export call a Qt timer from a non-GUI thread. Run that part on the GUI thread (QTimer.singleShot on the main thread or the Agent Link GUI queue). After the Texturizer run, FreeCAD restarted and recovered all documents (see Tutor); this error may be the cause. Check the crash log.
- 0010 texture_apply: the panel and preview show Knurling, but the call asked for Hexagon. Either the panel is not synced with the headless apply (Grip_hex), or the wrong texture was used. The echo should load the applied texture into the panel and show Grip_hex.
- The 3D preview does not follow texture_set (0015), texture_mask (0016) and texture_layer (0019). Refresh the preview after each change, and mark masked faces.
- No ring on Texturizer buttons. The Texturizer toolbar has buttons for reset, save, open, layers and export; light the matching one.
- Stale or tool-name captions: 1015 export should say "Wrote grip_textured.stl (N triangles)"; 2000 prepare should say what file it wrote; 0014 preview should say what it suggests.
- Left panel: Texturizer tab in front from 0010. That is sensible for this add-on, but the Grip object is never selected in the tree.
- 0013 caption is cut off; keep captions to one short sentence.

---

## 5. Tutor (4 pictures, first review)

Note: before the Tutor run, FreeCAD restarted and recovered every document ("(recovered 02:38 ... 02:52)" in the tree). The Report view is full of red "Reading failed from embedded file ... (0 bytes, 2 bytes compressed)" lines and a SafetyNet line "FreeCAD's autosave left some cached shapes empty". The tree also shows "AgentLink" and "CoreDoc" twice. This is not an echo problem, but find out why FreeCAD restarted (see the Texturizer QThread note).

| Picture | Tool | Rating | Reason |
|---|---|---|---|
| 0001-part_primitive | part_primitive | GOOD | PointBox selected, ring on Primitives, Model tab in front, caption. |
| 0002-tutor_point | tutor_point | MINOR | Pointers 1 (dot on the top face, face lit cyan), 3 (ring on Fit All) and 4 (ring around the 3D view) show. Pointer 2 (tree: PointBox) is missing: the tree is not scrolled to the TutorRest document. The words bubble is cut off (only half of the first line shows) and its arrow points left at the panel, not at the face. |
| 0009-tutor | tutor (start, demo) | MINOR | BikeStem document, Part Design. Step bubble shows steps 1-3; step 4 is cut off. Ring "1" on the New Sketch menu arrow, but the Body button also has a ring (from the echo), so there are two rings. Caption "Made a new body". |
| 0013-tutor_watch | tutor_watch | GOOD | Demo went on: sketch on XZ open, Sketcher edit toolbars show, sketch panel in Tasks, caption "Started a sketch on XZ of Body". |

Counts: GOOD 2, MINOR 2, BAD 0.

Round 3 numbers: ring visible 3/4 (0001, 0002, 0009; plus numbered tutor rings in 0002 and 0009). Caption 4/4. Result selected 2/4 (0001, 0002). Sketch edit picture 0013: yes, the Sketcher edit toolbars show.

### tutor_point check (what was asked: pointers or highlights on each named target, with the words)
- Face target: yes. Dot "1" and the top face is lit.
- Tree target: no. Nothing points at PointBox. Expand and scroll the tree to the target row before you draw the pointer, then put pointer "2" on the row.
- Command target (Std_ViewFitAll): yes. Ring "3" on the Fit All button.
- View target (3d): yes. Ring "4" around the 3D view.
- Words: shown, but the bubble is too short: the text is cut in half. Make the bubble grow to fit the text. Put the bubble near target 1 and point its arrow at the face, not at the left panel.
- The caption stays "Made a box PointBox". This is the round 3 rule (tutor_point does not change the model), so it is not a fault.

### Tutor-particular problems
- Bubbles clip their text (0002 first line, 0009 step 4). Size the bubble to the text.
- 0009: the echo ring on the Body button and the tutor ring "1" show together. During a tutor step, hide the echo ring so the user sees only the tutor pointer.
- 0009 bubble is anchored at the top-left of the 3D view, not at ring 1.

---

## Counts per family

| Family | GOOD | MINOR | BAD | Total | Ring | Caption | Selected |
|---|---|---|---|---|---|---|---|
| Draft | 11 | 7 | 2 | 20 | 6 | 20 | 16 |
| Surface | 10 | 3 | 2 | 15 | 1 | 15 | 13 |
| Workshop | 13 | 30 | 10 | 53 | 29 | 53 (5 stale) | 38 |
| Texturizer | 4 | 6 | 4 | 14 | 3 | 14 (3 stale) | 3 |
| Tutor | 2 | 2 | 0 | 4 | 3 | 4 | 2 |
| All | 40 | 48 | 18 | 106 | 42 | 106 | 72 |

Old echo for comparison: Draft 3/13/4, Surface 2/5/8.

## Tools proven live in the window (GOOD or MINOR, and the picture shows the result correctly)

Draft: draft_plane, draft_shape, draft_modify, draft_link_array, draft_dimension, draft_style, draft_fix, draft_label, draft_clone, draft_hatch, draft_to_sketch, sketch_state, draft_from_sketch, part_primitive, draft_facebinder, draft_text, draft_array.

Surface: part_wire, surface_boundary, surface_sections, surface_extend, part_primitive, surface_cut, surface_sew, surface_thicken, surface_blend, draft_shape, surface_loft, surface_points, meshobj_from_shape.

Workshop: pd_body_new, sketch_new, sketch_add, pd_pad, fit, hw_hole, thread_lookup, part_transform, hw_pauses, slice_read, part_primitive, cut_export, mill_check, body_check, fastener_types, fastener_add, macro_save, macro_unapprove, history_checkpoint, pref_reset, printer_add, export.

Texturizer: part_primitive, texture_list, texture_check, texture_layer, object_set (panel), texture_draft (draft started).

Tutor: part_primitive, tutor_point (3 of 4 targets), tutor (start, demo), tutor_watch.

Rated MINOR but not proven, because the window shows nothing that confirms the result: draft_fonts, setup, part_spec, thread_identify, thread_cut, mass_properties, mass_target, mass_ballast, hw_embed, hw_embed_list, hw_unembed, slicer_presets, printer_list, cut_check, fastener_list, fastener_print, macro_list, macro_show, mass_calibrate, app_recover, pref_history, pref_set, texture_settings, view_snapshot, texture_set, texture_mask.
