# Assemblies: parts put together
<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->

FreeCAD's own Assembly workbench, its solver and its joints. Parts are bodies already made; an assembly says where they go relative to one another.

## Start here
A map of this guide. `guide_read { topic: "assembly", section: [...] }` reads the sections named.
- Before the first joint: `The workflow` (asm_new, a joint at a time, look, `asm_check`), `Joints` (what each kind allows), `Picking the elements` (each end is a part and a query) and `traps` (which part moves, grounding).
- When a solve answers and you need to know what it means: `What the solver tells, and what it does not`.
- At their own moment (the index lists them under later): `Moving it through its range`, `Fits`, `Poses and limits`, `Exploded layout and parts list`, `Sub-assemblies`, `couplings`.

## The workflow
1. `asm_new { parts }`: the bodies into a new assembly (the bodies themselves, moved in — a body is in one assembly). The first is **grounded** (held fixed) unless `ground` names another; the solver moves only the others.
2. `asm_joint` between two parts, one at a time, each solved as it is made. Read `moved` (which part went where) and `overlaps` after every joint.
3. `view_render { views: "all" }` — look. A part upside down or inside another is a face picked the wrong way: `history_undo`, then the joint again with `reverse: true`.
4. `asm_check { clearance }` at the end: solves, overlaps (volume and where), pairs closer than the clearance, parts joined to nothing. **verdict clear** is the goal.
5. Draw it from where the parts now sit (`td_page`, `td_view`); `export` each part.

## Joints
- `fixed` — no motion between them: a lid screwed down, a bracket bolted on.
- `revolute` — turns about an axis: a hinge, a wheel on an axle. Pick round edges or faces (the axis is theirs).
- `cylindrical` — turns and slides: a pin in a hole with no end stop.
- `slider` — slides along one direction only: a drawer, a carriage on a rail.
- `ball` — turns any way about a point.
- `distance` — the two elements `distance` mm apart: a gap, a spacer. Between round faces the distance counts from their surfaces (FreeCAD adds the radii); two flat faces at 0 slide on one another.
- `parallel`, `perpendicular`, `angle` (`angle` degrees, 90 when left out) — orientation only.
- `offset` and `rotate` are FreeCAD's joint offset on b's side (Offset2): its panel offers offset for fixed and revolute, rotation for fixed and slider. Reverse is offered for fixed, revolute, cylindrical, slider, distance and parallel; only those are turned over on their own when parts overlap.

## Picking the elements
- Each end is `{ part, element }`. The element is a query as `shape_query` takes it: `{ kind: "face", normal: [0, 0, 1] }` (the flat face facing up), `{ kind: "edge", type: "circle", radius: 3 }` (a 6 mm hole's rim), `near: [x, y, z]` to take the closest of several. A name ("Face6") works but changes when the part is edited.
- A flat face: the joint sits at its middle, along its normal. A round edge or a cylindrical face: on its axis — the right pick for anything that turns or slides on a shaft.
- Faces that meet face to face (a lid's underside on a box's rim) have opposite normals: up on one part, down on the other. `offset` mm moves b off along the normal (a gap); `rotate` degrees turns it about it.

## traps
- A joint between two flat faces puts their middles together: a post joined to a plate's top moves to the plate's middle. To keep a part where it stands, `asm_ground` it instead of joining it, or join it by an element that is where it should meet (a hole's edge, a pin's face).
- Which part moves: the one not yet joined to a grounded part — `a` when neither is — and the parts already joined to it go along. A grounded part never moves. Make joints from the grounded part outwards, the grounded side as `a`, and the answer's `moved` is what you expect.
- An assembly needs one grounded part: `asm_ground`. With none, every solve answers "no part is grounded".
- Some workbenches relabel their objects on every recompute (Fasteners counts its screws' labels up): name such a part by its object name (session_state's `object`, asm_list), which stays. A label that differs only by that counter still finds the one part it fits.
- The solve moves parts; it does not check they fit. `asm_check` does — a press fit reads as an overlap of its interference volume.

## What the solver tells, and what it does not
- FreeCAD 1.1's solve answers three things only: **solved**, **solver error** (it could not put the parts where the joints ask) and **no part is grounded**. The other words in its notes (redundant, conflicting, over-constrained, malformed) are not returned by 1.1.
- **Solved is not fully constrained.** The solver does not count the freedom left. To see what still moves: `asm_sweep` a joint, or `asm_check`'s `notConnected` (parts joined to nothing grounded — the solver leaves them, and joints between two such parts, out without a word).
- A joint that repeats what another holds (a slider where the chain already keeps the axis parallel) is tolerated: FreeCAD's own crank-and-slider example has two such. A joint that *fights* another (fixed over a revolute at another angle) ends in solver error, and `asm_joint` keeps nothing.
- Every assembly tool's reply may carry `health`: the solver's line an assembly, red with a `todo` when it is not solved.

## Moving it through its range
<!-- later: when checking a motion with asm_sweep -->
- `asm_sweep { joint, from, to, steps }` turns a revolute joint through degrees (a slider or cylindrical one along its axis, mm), solving and checking for overlaps at each step, then puts every part back. `collidesAt` lists where parts run into each other; `clearFromStart` the range that is clear from the start.
- Does a lid open to 110°, does an arm swing past a post, does a drawer slide out: sweep it before printing. Steps are a sample — a thin part can pass between two: more steps to look closer (72 at most), `clearance` to list near misses too.
- `from` and `to` count from where the joint stands now; `asm_pose`'s `to` and `asm_limits` count from the joint's own zero. They are the same only while the joint stands at its zero: `asm_pose { joint, home: true }` before a sweep between limits.
- The moving part carries what is joined beyond it rigidly. A closed loop (a four-bar, a crank and slider once closed) is not followed: sweep the open chain, or pose it and read `asm_check`.

## Fits
<!-- later: when reading a hole and shaft fit with asm_fits -->
- `asm_fits` reads the hole and the shaft each joint puts together: both diameters, the clearance (minus is interference), how far they engage, and how far their axes are apart. Pass `joint` for one, or `pairs: [{ a, b }]` for parts with no joint.
- `fit: "H7/g6"` holds them to ISO 286, giving the fit's type and clearance range and whether each part is in its band. The nominal is read off the parts unless `size` says it.
- A model drawn at nominal sizes fails a shaft band like g6 (it wants the shaft a little under). Say so, then size the part into the band, or keep the fit as a callout for the drawing (`td_dim { fit }`).

## Poses and limits
<!-- later: when using asm_limits or asm_pose -->
- `asm_limits { joint, min, max }` sets FreeCAD's own limits on a joint. `asm_sweep` then sweeps between them by default.
- `asm_pose { joint, to }` moves a joint and leaves it there: the lid open at 90° for a render or a drawing. `to` counts from the joint's own zero (where its two frames line up, usually how it was made); `by` from where it stands. `home: true` returns it to zero. Refused when the solver moves it back: something else holds it.

## Exploded layout and parts list
<!-- later: when using asm_explode or asm_bom -->
- `asm_explode { factor }` spreads the parts out from the middle; `axis: "z"` stacks them along an axis in the order they sit. Then render it, or draw it (`td_view`), and `asm_explode { collapse: true }` puts them back. Don't solve or add joints while exploded: the solver pulls the parts home.
- `asm_bom` is FreeCAD's own bill of materials, with material, mass and volume from the materials recorded (`material_set`). `td_table { sheet }` puts it on a drawing. Each call makes a new BOM object.
- While exploded the joints are suppressed and the parts really are moved: collapse before `asm_joint`, `asm_pose` or `asm_sweep`.

## Sub-assemblies
<!-- later: when using asm_sub -->
- Build the sub-assembly as an assembly of its own, then `asm_sub { assembly: "Machine", sub: "Hinge" }` puts it in as a link (FreeCAD's AssemblyLink). It is rigid by default (one part to the parent); `rigid: false` lets its own joints keep moving.
- `asm_joint` and `asm_ground` take bodies put in with `asm_new` or `asm_add`; they do not take a sub-assembly (or a part linked in by `asm_new_part`) as a part yet. Place a sub-assembly with `object_set` (its Placement). `asm_check` checks its parts where they stand.
- `asm_bom` itemises a sub-assembly's parts under it (2, 2.1, 2.1.1 …), as FreeCAD's BOM does.

## couplings
<!-- later: when a joint is gears, belt, rackpinion or screw -->
`asm_joint` kinds `gears`, `belt`, `rackpinion` and `screw` tie one motion to another, for `asm_sweep`. Give `radius1`/`radius2`, or the wheels' round edges and the radii are read off them; for a screw, `pitch` is mm per turn. They need each part's own joint (revolute, slider) as well; a screw needs one of its two parts on a slider or cylindrical joint, or FreeCAD leaves the screw out. FreeCAD does not count a coupling as tying a part to ground.
