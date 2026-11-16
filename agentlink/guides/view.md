# Pictures
<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->

Look at the part after every change that matters, as a person would.
`view_render` draws it headless and hands the picture back.

## Views
- `views: "all"`: iso, top, front and right, each fitted. One name for one view; a list of up to 6.
- `section { axis: "x"|"y"|"z", offset }`: cut open at offset mm (the middle when left out); the half away from the eye is kept. Solid cut faces are hatched red.
- `zoom { at, size }`: frame a spot — a finding's `at`, a map's `worst.at` — `size` mm across.

## Maps
- `wall`: thickness at each spot, straight in from the surface. Red is thin; `reach` (12 mm) reads as thick.
- `stress`: von Mises of the last `fea_solve`; stale when the body changed since.
- `heat`: temperature of the last `fea_heat`.
- Add-ons add theirs: `view_maps` lists them.
- `range: [lo, hi]` fixes the colours, to compare two pictures. The answer gives the worst value and where.

## The window
- `view_snapshot` saves the FreeCAD window's own view, as the person left it (or turned to `view`). Headless it is refused.
- `view_snapshot { views: ["top", "front", "right", "iso"] }` (up to 6, or `"all"`) gives one grid picture, and each view's file in `paths`. It puts the person's view back after.

## traps
- `view_render` runs on the first call: it is not held back on a time estimate. Its answer's `time` says what it took and what to expect at the same triangles and views, from past renders here.
- Left without `objects`, every shown body is drawn: a Body of several solids, screws and other parts attached to it, each in its own colour.
- `view_snapshot` `width` and `height` are the whole picture. With several `views` they are split among the grid; `cell: true` makes them each view's size. The answer gives the sizes as saved.
- Grey on a map is unread: an open mesh, a scan past the max distance.
- The picture is the tessellation: a fine curve shows facets; `tolerance` sets the chord.
- Big pictures are big answers: `inline: false` writes the file only.

## Driving the window (`gui_input`, group dev)
- Panel buttons by `{widget:{text}}`; a panel's tabs by `{tab:{text, under?: dock title}}` (a tab is not a widget, so `widget` never finds it); rows of lists, trees and tables by `{item:{text, under?, column?}}`, scrolled into view first, and a row's check box by adding `check: true` (the answer's `hit.check` says whether the click took or the model's state was set); points on the part by `{view_world:[x,y,z]}` (each step answers its `point`: where it landed, and why if FreeCAD's own projection was used). Look with `shot`, then trust a headless read-back over the picture.
- The live camera by `cmd_run { name: "Std_ViewIsometric" }` and `"Std_ViewFitAll"`: `view_snapshot` renders apart and leaves it where it was.
- A `click` is a tap (press and release back to back), so every navigation style selects with it, Gesture included; its answer's `selected` lists what FreeCAD's selection holds after it (first 3 sub-elements). A held `press` … `release` is what turns or opens a hold menu.
- Keys go where the call's last press went; with none, to the window's focus.
- A step that opens a menu or dialog does not stop the call: the next steps act in it (`{menu_item:"New Sketch"}`, `{key:"Escape"}`). The answer's `open` names what is still open; close it. If other calls answer `busy`, use `gui_unstick`.
- Dev only, two agents on one link (a teacher and a student who stands in for the person): the student adds `as: "person"` to each `gui_input`. The window events of that call and its `call_done` are the person's; the calls of the teacher stay the agent's, also when they come between or during the calls of the student. The answer shows `as: "person"`.
- Toggle buttons flip on each click and keep their state over a restart: check before clicking twice.
- Save before `agentlink_update`: the person's unsaved changes come back as a "(recovered …)" copy in front; `doc_switch { front: true }` brings the right tab back. The agent's never-saved documents come back once, from ~/AgentLink/unsaved.
