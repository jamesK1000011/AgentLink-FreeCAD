# Window review, round 6: ScanRuler add-on, part b

Pictures: `pics6/srb` (59, all listed in `pictures.json`). I looked at every picture at full size and made enlarged crops of the 5003 overlay and toolbar.
Compared with round 3 (`window-r3-scanruler-findings.md`), for the same 59 calls. The claimed fixes are in `scanruler-freecad/docs/hardening/sr4-findings.md`.
ScanRuler tools by Stefan Hermann (CNC Kitchen), ported to FreeCAD.

## Counts

| set | pictures | GOOD | MINOR | BAD |
|---|---|---|---|---|
| round 6 (srb) | 59 | 25 | 33 | 1 |
| round 3, same 59 calls | 59 | 14 | 30 | 15 |

Note: an empty "Tasks" dock fills the right third of the window in all 59 pictures. I counted it as a general problem and did not lower ratings for it. If it counts, no picture is GOOD.

Ring on a real button: 8046 (Recompute). 8052 keeps that ring (a read, so this is acceptable). 8038 lights the wrong button (Part Primitives) and 8050 keeps the Recompute ring from the previous document. No mesh or reverse tool lights its ScanRuler button.
Caption: 59 of 59, and none is stale. 7039 has no Agent words in the status bar.
Result selected: 7008, 8004, 8010, 8038 and 8040. ScanRuler overlay results are drawn but cannot be selected (by design).

## Per picture

| picture | tool | rating | reason |
|---|---|---|---|
| 5003 | scanner | GOOD | Caption names file; overlay of elements and sections drawn. |
| 5006 | catalog_part | MINOR | Caption is tool name only. |
| 5008 | catalog_links | GOOD | Caption explains; nothing to draw. |
| 5009 | catalog_provenance | GOOD | Caption names file. |
| 5010 | pack_setup | GOOD | Caption gives result (cut off). |
| 5011 | pack_plan | GOOD | Caption gives result. |
| 5012 | pack_write | GOOD | Caption names zip. |
| 5013 | manual_plan | GOOD | Caption "done, 2 steps". |
| 5014 | manual_check | GOOD | Own caption now, gives check result. |
| 5015 | manual_render | GOOD | Own caption now, names HTML file. |
| 5016 | scan_snapshot_list | MINOR | "Listed Snapshot": no count. |
| 5018 | scan_snapshot_wait | GOOD | Refusal explained honestly. |
| 6131 | mesh_smooth | MINOR | ScanRuler bench, right caption; panel shows Reduce section. |
| 6136 | doc_switch | MINOR | Window stays on ScanNoiseModel; panel shows ScanMeasureModel. |
| 6138 | workbench | MINOR | Panel and view still on different documents. |
| 6139 | cmd_run | MINOR | Snapshot not shown; panel and view on different documents. |
| 7008 | mesh_parts | GOOD | Block shown and selected; caption gives counts. |
| 7009 | mesh_inspect | GOOD | Caption gives triangles and open edges. |
| 7014 | mesh_cut_preview | MINOR | Cut plane drawn, but it runs off the view's left edge. |
| 7015 | mesh_cut | GOOD | Part above z=15 ghosted; caption gives triangles. |
| 7017 | mesh_undo | GOOD | Full block back; caption names the undo. |
| 7018 | mesh_boolean | MINOR | Caption right; see-through pin hides whether hole made. |
| 7023 | mesh_remove_islands | MINOR | Panel one call behind (10,048 vs caption 10,036). |
| 7024 | mesh_offset | GOOD | Block visibly grows by 1 mm; caption right. |
| 7027 | mesh_mirror | GOOD | Symmetric block, caption gives plane and triangles. |
| 7029 | mesh_flip_normals | MINOR | Panel lacks the flip step (one call behind). |
| 7031 | mesh_delete_marked | MINOR | Hole in top shown; panel one call behind. |
| 7037 | mesh_discard_edited | MINOR | View back to original; panel still lists edits. |
| 7039 | mesh_reduce | MINOR | Preview drawn over scan in stripes; no status words. |
| 7041 | mesh_export | GOOD | Caption names STL; preview still shown. |
| 7042 | mesh_apply_reduced | MINOR | Panel still 10,022 while caption says 2,184. |
| 7050 | mesh_trim | MINOR | Caption has no result; trim not visible; stripes on scan. |
| 7052 | mesh_shell | MINOR | Caption right; hollow not visible (no cut-away). |
| 7056 | mesh_wrap | MINOR | "Beside the mesh" but drawn on it; stripes. |
| 7059 | mesh_discard | MINOR | Preview gone; caption is tool name. |
| 7065 | mesh_apply_wrap | MINOR | Caption right; wrap shape hard to read, faint stripes. |
| 8001 | reverse_feature_list | MINOR | Layout jump fixed; panel shows Mesh Tools; no count. |
| 8002 | reverse_feature_schema | GOOD | Reverse panel; caption names extrude. |
| 8004 | reverse_feature_add | GOOD | Block drawn and selected; "2 added". |
| 8005 | reverse_body_names | MINOR | Caption gives no names. |
| 8006 | reverse_body_check | GOOD | Caption gives 24000 mm³. |
| 8007 | reverse_body_describe | MINOR | Caption gives no result. |
| 8008 | reverse_parameter_add | GOOD | h 20 in panel; caption names h. |
| 8010 | reverse_feature_update | GOOD | Block selected; caption names it. |
| 8011 | reverse_parameter_set | MINOR | Body halves; caption is tool name; buttons squashed. |
| 8013 | reverse_parameter_rename | MINOR | Caption tool name; panel still shows "h". |
| 8016 | reverse_parameter_list | MINOR | Caption gives no count. |
| 8026 | reverse_feature_rollback | MINOR | Rolled back in panel only; caption tool name. |
| 8038 | export | MINOR | Gauge selected; ring on Primitives (wrong); Block cut off. |
| 8040 | reverse_import_step | MINOR | Gauge selected; zoom too tight; Block cut off. |
| 8043 | reverse_feature_remove | GOOD | Bore gone; caption "2 removed". |
| 8044 | reverse_build | MINOR | Caption is tool name. |
| 8046 | recompute | GOOD | Recompute ring; clear caption. |
| 8050 | doc_open | MINOR | Opened; Recompute ring from previous document still lit. |
| 8052 | object_list | GOOD | Caption gives 5 found. |
| 8055 | reverse_feature_clear | BAD | Panel still 9 features after clear; grey leftover framed. |
| 8056 | history_undo | MINOR | Panel 9 features (fixed); camera frames one small cube. |
| 8061 | history_redo | MINOR | Panel 0 features (fixed); grey leftover framed. |
| 8066 | reverse_parameter_remove | MINOR | Caption does not name spare. |

## Round-3 problems: status

1. Results never drawn: **FIXED**. The planes, cylinder, points, sections (green) and dimension labels are drawn over the scan (5003-5018). Remaining issues:
   - The labels are too small to read, even when enlarged.
   - Every element is orange in pictures of calls that made nothing (5003-5018). This may be the last changing call's "new" colour staying up. If it is not, only the new item should be orange.
2. No colour map or legend: **NOT TESTED**. No map tool is in this set.
3. Mesh edits not shown: **MOSTLY FIXED**.
   - Shown: 7015 cut, 7017 undo, 7024 offset, 7031 hole, 7014 plane, 7039 preview, 7037 original back.
   - **PARTLY**: in 7018 boolean, 7050 trim, 7052 shell, 7056 wrap and 7065 apply_wrap the change cannot be seen.
4. Wrong workbench (Mesh) for mesh calls and the stale Mesh Info task: **FIXED** (6131, 7008-7042).
5. Stale captions (6131, 7014, 7015, 7039, 7050, 7052, 7056, 5014, 5015): **FIXED**.
6. Captions that are only the tool name: **PARTLY**. Still in 5006, 5016, 7059, 8005, 8007, 8011, 8013, 8016, 8026, 8044, 8066.
7. Panel one step behind after undo/redo (8056/8061): **FIXED**.
8. doc_switch, workbench and cmd_run show a different document in the panel than in the view (6136, 6138, 6139): **NOT FIXED**. The duplicate ScanMeasureModel tab is still open in 6131-7065: **NOT FIXED**.
9. Panel section does not follow the tool: **NOT FIXED**. 6131 and every mesh tool show the Reduce Mesh section, and 8001 shows Mesh Tools in the reverse document.
10. 8001 layout jump: **FIXED**. Leftover grey solid after clear (8055, also 8061): **NOT FIXED**.
11. 8038 rings the wrong button (Primitives) for export: **NOT FIXED**. 8050 stale ring after doc_open: **NOT FIXED**.

## New problems (family-particular)

1. **Panel one call behind after some mesh and reverse calls**: 7023, 7029, 7031, 7037, 7042, 8013 and 8055. **8055 is WORSE**: after reverse_feature_clear the panel shows 9 features (round 3 showed 0). The dock's `tick` should redraw on every ScanRuler call's version change before the picture is taken, not only on the undo/redo mark.
2. **Z-fighting stripes** where an overlay mesh lies on the scan: the 5003-5018 front face, 7039 reduce preview, 7050-7065. The wrap and reduce previews should be drawn beside the scan, as their captions say, or the scan's own drawing should be switched off under them.
3. **Squashed panel buttons with clipped text** (half-height rows):
   - Create Element: 5003-5015.
   - Tools / Reduce Mesh: 6131, 6136, 6138, 7009-7065.
   - Create Feature: 8011, 8026, 8043, 8044, 8050-8066.
4. **Fit**: 7014 plane off-screen; 8038 and 8040 Block cut off; 8056 frames only one small cube while 4 bodies are restored.
5. General: an empty "Tasks" dock takes the right third of the window in all 59 pictures, and the caption sits at its edge.

PROVEN_LIVE ScanRuler: scanner, catalog_part, catalog_links, catalog_provenance, pack_setup, pack_plan, pack_write, manual_plan, manual_check, manual_render, scan_snapshot_list, scan_snapshot_wait, mesh_smooth, workbench, mesh_parts, mesh_inspect, mesh_cut_preview, mesh_cut, mesh_undo, mesh_offset, mesh_mirror, mesh_flip_normals, mesh_delete_marked, mesh_discard_edited, mesh_reduce, mesh_export, mesh_discard, reverse_feature_list, reverse_feature_schema, reverse_feature_add, reverse_body_names, reverse_body_check, reverse_body_describe, reverse_parameter_add, reverse_feature_update, reverse_parameter_set, reverse_parameter_rename, reverse_parameter_list, reverse_feature_rollback, export, reverse_import_step, reverse_feature_remove, reverse_build, recompute, doc_open, object_list, history_undo, history_redo, reverse_parameter_remove
NOT_PROVEN ScanRuler: reverse_feature_clear (panel still 9 features, leftover solid), doc_switch (window stays on other document), cmd_run (snapshot not shown, panel/view on different documents), mesh_boolean (hole not visible), mesh_remove_islands (panel behind, change not visible), mesh_apply_reduced (panel 10,022 vs caption 2,184), mesh_trim (trim not visible), mesh_shell (hollow not visible), mesh_wrap (preview on scan, not beside; stripes), mesh_apply_wrap (wrap shape not readable)
