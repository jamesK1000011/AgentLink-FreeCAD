# Window review, round 3 (first window review): ScanRuler add-on

Pictures: `pics3/sr-a` (63) and `pics3/sr-b` (62). Only pictures in `pictures.json` count; all 125 are listed in it.
I looked at every picture at full size (1400 x 852), in batches, and made enlarged crops of the
ScanRuler toolbar row for sr-a 0007, 0014, 0015, 1005, 2018, 3000, 3011 and sr-b 7015 to check for rings.
No code was read. No other file was changed. No Mac tools were used.

Limits: one frame per call, no motion. The Report view is open in every picture, so error text can be judged.
Documents used: ScanMeasureModel (worn block scan, sr-a and sr-b 5xxx-6079), ScanNoiseModel (sphere),
ScanMeshModel (block with pin and island), ScanReverseModel and scan-reverse-model (reverse build).

## Counts

| folder | pictures | GOOD | MINOR | BAD |
|---|---|---|---|---|
| sr-a | 63 | 6 | 32 | 25 |
| sr-b | 62 | 14 | 32 | 16 |
| total | 125 | 20 | 64 | 41 |

## Round-3 questions

| family | pictures | ring visible | caption visible | result selected (changing calls) | Sketcher edit toolbars |
|---|---|---|---|---|---|
| ScanRuler | 125 | 11 | 121 | about 10 of about 85 | no sketch in edit in any picture |

- Ring (11): sr-a 0001, 0003, 1000, 1009, 4011, 4017, 4019; sr-b 8038, 8046, 8050, 8052.
  - 8038 export rings the Part Primitives button. That is the wrong button.
  - 8050 doc_open keeps the Recompute ring of the previous call in a newly opened document. 8052 is a read, so it may keep the ring.
  - The ScanRuler toolbar has buttons for Plane, Point, Cylinder, Section and Dimension. Only fit-plane (1000) and dimension_add (1009) light them. element_construct, section_cut, scan_* and deviation_* light no button.
  - The always-blue button in the ScanRuler toolbar is the active workspace toggle, not a ring.
- Caption: present in 121. Missing in sr-a 3014, 3018, 4001 and sr-b 6079 (6079 shows "Wait until the auto-recovery file has been saved").
  - Stale or wrong captions on changing calls (12): sr-a 3001, 3005, 3011, 3016; sr-b 5015, 6131, 7014, 7015, 7039, 7050, 7052, 7056.
  - Many captions are only the tool name ("Scan nearest", "Wear diff", "Fit scan measure") and give no measured value.
- Selection: the result is selected only when it is a FreeCAD document object: 0001, 0003, 0004, 0007, 2018, 3000, 8004, 8010, 8038, 8040.
  - ScanRuler elements, dimensions, sections, maps and mesh edits are never drawn, so nothing can be selected.
  - The 3000 selection then stays on through 3001-3010, and a green pocket face stays on through 3013-4010 and 6079.
- No sketch is in edit in any picture, so the Sketcher-toolbar check does not apply. 2018 section_to_sketch makes a sketch but does not open it.

## Family-particular problems (most important first)

1. **ScanRuler results are never drawn in the 3D view.** This is the main problem in this family.
   - Fitted elements: 0019, 1000, 1005.
   - Dimensions: 1009, 1016, 1017.
   - Sections: 2010, 2013.
   - Nearest point and marked facets: 0017, 0018.
   - Segments, fit surface, outline, symmetry plane, fit-scan features: 3001, 3002, 3008, 4018, 4008.
   - The ScanRuler panel lists them (Top, Bottom, Bore 11.999 mm, Corner and so on), and the status bar says ELEMENTS 10 · DIM 7, but the view shows only the grey scan.
   - The echo should draw ScanRuler's own overlay (planes, points, cylinders, dimension lines with values, section curves) and select or highlight the new one.
2. **No colour map and no legend for any map tool.**
   - Draft: 3003. Height map: 3005. Thickness: 3011, 3012. Deviation: 3016, 3017, 3018, 4001. Wear: 4004.
   - The panel shows the Colour Scale settings, but the scan stays plain grey and there is no legend bar.
   - The echo should colour the scan, show the legend with its range (for example ±1.000 mm), and remove both when a later tool does not use them.
   - No picture shows a map, so the "removed when not needed" check could not be tested.
3. **Mesh-tool edits are not shown.** ScanRuler edits an "Edited Copy" (the panel shows triangle counts: 219,600; 8,192; 76,664; 25,548), but the view keeps showing the original mesh.
   - 7015 cut: still full height. 7018 boolean: pin still there. 7023 remove islands: island cube still there. 7024 offset. 7027 mirror. 7031 delete marked: no hole. 7050 trim. 7052 shell. 7056 wrap.
   - 7065 apply_wrap: the panel says the wrap is in use, but the view still shows the 12-triangle block.
   - The echo should show the edited copy (or a ghost of it beside the original) after each mesh tool, and the applied mesh after apply/use-edited.
4. **Wrong workbench for ScanRuler mesh calls.** sr-b 6131, 7008-7042 stay in the Mesh workbench with the Agent Link tab in front, and a stale Mesh Info task stays open (8 points / 12 facets). sr-a 0008-0010 (scan_open, scan_info, scan_qa) also stay in Mesh.
   - In contrast, sr-a 0014 and sr-b 7050-7065 switch to ScanRuler with the Mesh Tools panel.
   - scan_open (0008) should switch to ScanRuler and show the Model card. It also leaves a copy WornScan001, and the hidden original stays selected.
5. **Stale or wrong captions on changing calls (12 pictures, listed above).** The mesh tools are the worst: 7014 and 7015 say "Mesh Tools densify", 6131 (smooth) says "densify", 7039 (reduce) says "undo", 7052 (shell) says "Exported ... on piece".
   - This looks like the caption updating one call late, or only when the tool label changes.
6. **Missing captions:** 3014 deviation_align, 3018 deviation_volume, 4001 deviation_set_target, 6079 deviation_export. These are all deviation-workspace calls.
7. **Python RuntimeWarnings in the Report view.**
   - segment.py:98 ("invalid value encountered in sqrt" / "in cast") after scan_segment (3001).
   - heightmap_core.py:452/453 ("invalid value encountered in add/multiply") after scan_heightmap and scan_outline (3005/3008).
   - These are NaNs in ScanRuler code on this clean block scan. Fix them in ScanRuler-FreeCAD, not in the echo.
8. **align_auto result looks wrong (4017).** After auto-align, the scan and the Block reference are visibly offset by about half a block. 4018 (symmetry) and 4019 show the same offset. The caption gives no RMS. Check whether auto-align really converged; the caption should give the RMS or the fit error.
9. **Panel and view out of step.**
   - 8056 history_undo (undo of feature_clear) shows Features 0, and 8061 history_redo shows Features 9. That is the reverse of what is expected, so the panel refreshes one step behind.
   - 6138/6139: the ScanRuler panel shows ScanMeasureModel · WornScan while the 3D view shows the ScanNoiseModel sphere.
   - 6136 doc_switch says it switched to ScanMeasureModel, but the window stays on ScanNoiseModel.
   - 6079 opens a second ScanMeasureModel tab. It is still there in all later pictures.
10. **Panel section does not follow the tool.** 4003 wear_setup and 4007-4010 fit_scan_* leave the Deviation section in front. 0014 densify shows the Reduce Mesh section. The echo should scroll or open the matching ScanRuler section.
11. Smaller items:
    - 8001 has a layout jump (toolbar strip offset, caption over the document tabs).
    - 0014 shows a blank workspace label in the toolbar.
    - 8055 feature_clear frames a leftover grey solid while Bodies is 0.
    - 0004 shows the label Block in the property view while Worn is selected.

General (already known) problems, counted only:
- ScanRuler or Agent Link tab in front of Model: almost every picture. For ScanRuler this is acceptable, but the tree is hidden for document results such as 2018 and 3000.
- Captions that are only the tool name: about 45.
- Lit button missing: most changing calls.

## Tools proven live in the window (GOOD or MINOR)

Strictly proven, because the picture shows the result: part_primitive, part_boolean, part_transform, meshobj_from_shape,
section_to_sketch, element_to_document, align_datum, align_clear, reverse_feature_add, reverse_parameter_add,
reverse_feature_update, reverse_parameter_set, reverse_feature_remove, export, reverse_import_step, recompute, doc_open,
mesh_use_edited (panel state).

Proven only as "runs, caption or panel correct, nothing to draw": part_primitive, part_boolean, part_transform, meshobj_from_shape, scan_info, scan_qa, mesh_densify, mesh_use_edited, dimension_set_basic, dimension_set_limit, dimension_remove, element_rename, element_unlink, element_set_visible, element_remove, element_list, report_get, export_csv, section_list, section_get, section_fit, section_remove, section_to_sketch, element_to_document, scan_pattern, scan_cloud, scan_thread, deviation_open_reference, deviation_settings, wear_setup, wear_rebuild, wear_prewarp, fit_scan_setup, fit_scan_export, align_datum, align_clear, scan_scale, scanner, catalog_part, catalog_links, catalog_provenance, pack_setup, pack_plan, pack_write, manual_plan, manual_check, manual_render, scan_snapshot_list, scan_snapshot_wait, scan_snapshot_latest, flat_edges, doc_save, doc_switch, workbench, cmd_run, mesh_parts, mesh_inspect, mesh_undo, mesh_flip_normals, mesh_discard_edited, mesh_export, mesh_apply_reduced, mesh_discard, reverse_feature_list, reverse_feature_schema, reverse_feature_add, reverse_body_names, reverse_body_check, reverse_body_describe, reverse_parameter_add, reverse_feature_update, reverse_parameter_set, reverse_parameter_rename, reverse_parameter_list, reverse_feature_rollback, export, reverse_import_step, reverse_feature_remove, reverse_build, recompute, doc_open, object_list, reverse_feature_clear, reverse_parameter_remove

## Rating table

| picture | tool | rating | reason |
|---|---|---|---|
| sr-a/0001 | part_primitive | GOOD | Part workbench, Primitives ring, Block selected, caption names it. |
| sr-a/0003 | part_boolean | GOOD | Cut ring lit, Block selected, bore visible. |
| sr-a/0004 | part_transform | MINOR | Worn selected but property view still shows label Block; no ring. |
| sr-a/0007 | meshobj_from_shape | MINOR | Mesh made and selected; caption has no name or facet count; Mesh Info task opens. |
| sr-a/0008 | scan_open | BAD | Stays in Mesh workbench, no ScanRuler panel; a copy WornScan001 appears; the hidden original stays selected. |
| sr-a/0009 | scan_info | MINOR | Mesh workbench; caption "Read Scan" gives no counts; stale Mesh Info task. |
| sr-a/0010 | scan_qa | MINOR | Mesh workbench; caption "Read Scan" gives no QA result. |
| sr-a/0014 | mesh_densify | MINOR | ScanRuler panel now; caption is tool name; workspace label blank; panel shows Reduce section. |
| sr-a/0015 | mesh_use_edited | GOOD | Caption explains; panel shows In Use densify. |
| sr-a/0017 | scan_nearest | BAD | No point marker; caption is tool name, no distance. |
| sr-a/0018 | scan_query | BAD | mark=true but no marked facets shown; caption gives no count. |
| sr-a/0019 | element_fit_marked | BAD | Fitted plane Top not drawn; only the panel lists it. |
| sr-a/1000 | element_fit | BAD | Ring on Plane button, but plane Bottom not drawn or selected. |
| sr-a/1005 | element_construct | BAD | Corner point not drawn; panel only. |
| sr-a/1009 | dimension_add | BAD | Ring on dimension button; Height not drawn; no value in caption. |
| sr-a/1016 | dimension_set_basic | MINOR | Caption has no value; dimension not drawn. |
| sr-a/1017 | dimension_set_limit | MINOR | Caption has no limit value; dimension not drawn. |
| sr-a/1019 | dimension_remove | MINOR | Caption does not name Ang. |
| sr-a/2001 | element_rename | MINOR | Caption ok; element not drawn so nothing to see. |
| sr-a/2002 | element_unlink | MINOR | Caption is tool name. |
| sr-a/2004 | element_set_visible | MINOR | Caption is tool name; elements never drawn, so hide cannot be seen. |
| sr-a/2005 | element_remove | MINOR | Caption does not name Edge1; count 10 to 9 in panel. |
| sr-a/2006 | element_list | MINOR | Caption gives no count. |
| sr-a/2007 | report_get | MINOR | Report not shown; caption "Read Report". |
| sr-a/2009 | export_csv | GOOD | Caption names the file written. |
| sr-a/2010 | section_cut | BAD | Section Mid at z=10 not drawn. |
| sr-a/2011 | section_list | MINOR | Caption gives no count. |
| sr-a/2012 | section_get | MINOR | Caption "Read 3D Measure" only. |
| sr-a/2013 | section_fit | MINOR | Fitted shapes not drawn; caption "Read 3D Measure". |
| sr-a/2016 | section_remove | MINOR | Caption does not name Half. |
| sr-a/2018 | section_to_sketch | MINOR | Sketch line drawn and selected (green); ScanRuler tab hides the tree. |
| sr-a/3000 | element_to_document | GOOD | Top, Bore etc. made as objects, drawn and selected. |
| sr-a/3001 | scan_segment | BAD | Stale caption from 3000; RuntimeWarning segment.py:98 in Report; no segment colours. |
| sr-a/3002 | scan_fit_surface | BAD | Nothing drawn; caption tool name; old selection from 3000 left. |
| sr-a/3003 | scan_draft | BAD | No draft-angle colour map or legend. |
| sr-a/3004 | scan_pattern | MINOR | Caption tool name; nothing drawn. |
| sr-a/3005 | scan_heightmap | BAD | No height map or legend; stale caption "Scan pattern". |
| sr-a/3008 | scan_outline | BAD | No outline drawn; heightmap_core.py:452/453 RuntimeWarnings appear. |
| sr-a/3009 | scan_cloud | MINOR | Caption names the file; old selection from 3000 left. |
| sr-a/3010 | scan_thread | MINOR | Caption gives the result (no thread), cut off. |
| sr-a/3011 | thickness_measure | BAD | No thickness colour map or legend; stale caption from scan_thread. |
| sr-a/3012 | thickness_settings | BAD | Limit 12 set but still no map or legend. |
| sr-a/3013 | deviation_open_reference | MINOR | Reference loaded; not shown in its own colour; pocket face lit green. |
| sr-a/3014 | deviation_align | BAD | No caption and empty status bar; no visible change. |
| sr-a/3015 | deviation_settings | MINOR | Caption tool name; no map yet. |
| sr-a/3016 | deviation_measure | BAD | No deviation colour map, no legend; stale caption "Surface Deviation settings". |
| sr-a/3017 | deviation_hotspots | BAD | No hotspot markers; stale caption. |
| sr-a/3018 | deviation_volume | BAD | No caption; volume errors not drawn. |
| sr-a/4001 | deviation_set_target | BAD | No caption; no map against element Top. |
| sr-a/4003 | wear_setup | MINOR | Tagged pocket region not drawn; caption tool name; panel still Deviation. |
| sr-a/4004 | wear_diff | BAD | No wear colour map or legend. |
| sr-a/4005 | wear_rebuild | MINOR | Caption names file; repaired mesh not shown. |
| sr-a/4006 | wear_prewarp | MINOR | Caption names file. |
| sr-a/4007 | fit_scan_setup | MINOR | Caption tool name; panel still Deviation. |
| sr-a/4008 | fit_scan_features | BAD | Features not drawn. |
| sr-a/4009 | fit_scan_measure | BAD | No measured value anywhere; caption tool name. |
| sr-a/4010 | fit_scan_export | MINOR | Caption names file (cut off). |
| sr-a/4011 | align_datum | MINOR | Ring on Align button; scan moved, overlap shown; caption gives no numbers. |
| sr-a/4015 | align_clear | GOOD | Scan back in place; caption clear. |
| sr-a/4017 | align_auto | BAD | Ring ok, but scan and reference stay visibly offset after auto-align; no RMS in caption. |
| sr-a/4018 | align_symmetry | BAD | No symmetry plane drawn; caption tool name. |
| sr-a/4019 | scan_scale | MINOR | Ring on Scale button; dry run; caption gives no factor. |
| sr-a/5003 | scanner | MINOR | Caption "Scanner" only. |
| sr-b/5006 | catalog_part | MINOR | Caption tool name; no part shown. |
| sr-b/5008 | catalog_links | GOOD | Caption explains; nothing to draw. |
| sr-b/5009 | catalog_provenance | GOOD | Caption gives result. |
| sr-b/5010 | pack_setup | GOOD | Caption gives result (cut off). |
| sr-b/5011 | pack_plan | GOOD | Caption gives result. |
| sr-b/5012 | pack_write | GOOD | Caption names the zip. |
| sr-b/5013 | manual_plan | GOOD | Caption "done, 2 steps". |
| sr-b/5014 | manual_check | MINOR | Keeps manual_plan caption; no check result. |
| sr-b/5015 | manual_render | MINOR | Wrote HTML but caption still manual_plan (stale). |
| sr-b/5016 | scan_snapshot_list | MINOR | Caption gives no count. |
| sr-b/5018 | scan_snapshot_wait | GOOD | Caption explains. |
| sr-b/6079 | deviation_export | BAD | No Agent caption (status shows auto-recovery); second ScanMeasureModel tab appears; old green face. |
| sr-b/6117 | scan_snapshot_latest | MINOR | Refusal shown honestly; duplicate ScanMeasureModel tab left. |
| sr-b/6125 | flat_edges | MINOR | Refusal shown; empty 3D view in new ScanNoiseModel. |
| sr-b/6131 | mesh_smooth | BAD | Mesh workbench, not ScanRuler; caption says "Mesh Tools densify"; stale Mesh Info. |
| sr-b/6135 | doc_save | MINOR | Refusal shown; Mesh workbench. |
| sr-b/6136 | doc_switch | MINOR | Switched target but window stays on ScanNoiseModel. |
| sr-b/6138 | workbench | MINOR | ScanRuler on, but panel shows ScanMeasureModel while view shows ScanNoiseModel. |
| sr-b/6139 | cmd_run | MINOR | Snapshot ran; nothing of it shown; panel and view still on different documents. |
| sr-b/7008 | mesh_parts | MINOR | Mesh workbench, Agent Link tab; parts not coloured; stale Mesh Info. |
| sr-b/7009 | mesh_inspect | MINOR | No defect markers; keeps old caption. |
| sr-b/7014 | mesh_cut_preview | BAD | No cut plane preview; caption says "densify". |
| sr-b/7015 | mesh_cut | BAD | Mesh not cut at z=15; caption says "densify". |
| sr-b/7017 | mesh_undo | MINOR | Nothing to see; caption tool name. |
| sr-b/7018 | mesh_boolean | BAD | Pin still shown; subtract result not shown. |
| sr-b/7023 | mesh_remove_islands | BAD | Small island cube still shown. |
| sr-b/7024 | mesh_offset | BAD | No expanded mesh; stale caption "Removed islands". |
| sr-b/7027 | mesh_mirror | BAD | No mirrored mesh shown. |
| sr-b/7029 | mesh_flip_normals | MINOR | Change cannot be seen; caption tool name. |
| sr-b/7031 | mesh_delete_marked | BAD | No hole in the top where facets were deleted. |
| sr-b/7037 | mesh_discard_edited | MINOR | Caption tool name. |
| sr-b/7039 | mesh_reduce | BAD | Stale caption "Mesh Tools undo"; status bar empty. |
| sr-b/7041 | mesh_export | MINOR | Caption ok; Mesh workbench. |
| sr-b/7042 | mesh_apply_reduced | MINOR | Caption tool name; nothing visible. |
| sr-b/7050 | mesh_trim | BAD | Stale caption "densify"; no trim shown. |
| sr-b/7052 | mesh_shell | BAD | Stale caption "Exported ... on piece"; shell not shown (no cut-away). |
| sr-b/7056 | mesh_wrap | BAD | Stale caption "discard edited"; wrap not shown. |
| sr-b/7059 | mesh_discard | MINOR | Caption tool name. |
| sr-b/7065 | mesh_apply_wrap | BAD | Panel says 25,548 triangles in use, view still the 12-triangle block. |
| sr-b/8001 | reverse_feature_list | MINOR | Layout jump: toolbar strip offset, caption over the tab bar; empty view. |
| sr-b/8002 | reverse_feature_schema | MINOR | Empty view; caption ok. |
| sr-b/8004 | reverse_feature_add | GOOD | Block body drawn and selected; panel lists features. |
| sr-b/8005 | reverse_body_names | MINOR | Caption gives no names. |
| sr-b/8006 | reverse_body_check | MINOR | Caption gives no result. |
| sr-b/8007 | reverse_body_describe | MINOR | Caption gives no result. |
| sr-b/8008 | reverse_parameter_add | GOOD | Parameter h 20 in panel; caption names h. |
| sr-b/8010 | reverse_feature_update | GOOD | Block selected; caption names it. |
| sr-b/8011 | reverse_parameter_set | GOOD | Body visibly halves to h 10. |
| sr-b/8013 | reverse_parameter_rename | MINOR | Caption does not give new name. |
| sr-b/8016 | reverse_parameter_list | MINOR | Caption gives no count. |
| sr-b/8026 | reverse_feature_rollback | MINOR | No rollback marker; caption tool name. |
| sr-b/8038 | export | MINOR | Gauge selected, file named; Part workbench with ring on Primitives (wrong button for export). |
| sr-b/8040 | reverse_import_step | MINOR | Imported gauge selected; overlaps the exported Gauge; Block cut by the frame. |
| sr-b/8043 | reverse_feature_remove | GOOD | Hole gone; caption names Hole sketch. |
| sr-b/8044 | reverse_build | MINOR | Caption tool name. |
| sr-b/8046 | recompute | GOOD | Recompute ring lit; caption clear. |
| sr-b/8050 | doc_open | MINOR | File opened; Recompute ring from previous document still lit. |
| sr-b/8052 | object_list | GOOD | Caption gives count 5. |
| sr-b/8055 | reverse_feature_clear | MINOR | Features 0, but a leftover grey solid is framed. |
| sr-b/8056 | history_undo | BAD | Undo of clear, but panel shows 0 features (panel one step behind). |
| sr-b/8061 | history_redo | BAD | Redo of clear, but panel shows 9 features (panel one step behind). |
| sr-b/8066 | reverse_parameter_remove | MINOR | Caption does not name spare. |
