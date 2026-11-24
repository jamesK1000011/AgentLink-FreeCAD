# Design: from first idea to hand-off
<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->

The method behind the design-kickoff skill: clarify the task, freeze the interfaces, build level by level on a parametric skeleton, check each level, hand off what each process needs, and learn from the made part. The skill itself is `skills/design-kickoff/SKILL.md` in this repository.

## Start here
A map of this guide. `guide_read { topic: "design", section: [...] }` reads the sections named.
- Before the first question to the person: `The brief` (the records, the requirements list, the kickoff questions, the interface table).
- Before L1: `Modelling principles`, `Levels, build rules and gates` and `Agent Link steps and traps`.
- At their own moment (the index lists them under later): `Concepts and embodiment`, `Workflow branches`, `Hand-off and feedback`, `Sources`.

## The brief

### Design records

Keep these as plain markdown files in a folder that you can write: next to the FreeCAD file (`<design>-records/`) or in your own workspace. Agent Link has no records tool. A later agent must be able to pick up the work from them alone.

| File | Holds |
|---|---|
| `requirements.md` | the requirements list, the deal-breaker, the stories |
| `interfaces.md` | one row per interface (the ICD) |
| `decisions.md` | each gate and each choice: date, what, why, who (person or agent), source |
| `changes.md` | each change to a frozen item: what, why, effect on requirements and checks, approval |
| `fmea.md` | the short design FMEA (see the section `Levels, build rules and gates`) |
| `handoff-status.md` | the hand-off menu the person chose, and the status of each item |

### Requirements list

One row per requirement:

| ID | Requirement (what it must do) | D/W | Metric | Unit | Marginal | Ideal | Source | Check |
|---|---|---|---|---|---|---|---|---|
| R1 | holds the phone in portrait | D | phone width fits | mm | 76 | 76 ± 0.3 | looked up: maker spec (link) | fit check L3 |
| R2 | stays put on a bumpy road | D | holding force | N | 15 | 25 | assumed | test at L5 |
| R3 | looks like the dash | W | colour match | – | grey | dash grey | stated | render G2 |

- **D (demand)**: must be met or the design fails. **W (wish)**: met where possible; used to rank options.
- Each line has a metric, a unit, a marginal and an ideal value where it can. Some are pass/fail tests.
- **Source** of each value: stated, measured, looked up (with link), or assumed. Assumed values are listed at each gate until confirmed.
- **Check**: how and at which level it is verified (measurement, interference, FEA, render, test print, use).
- Target values come first; set final values after the concept is chosen.
- Keep the list live: update it when the design shows new facts.

Write each requirement as what the product does, in positive words, as specific as the person was. Avoid "must/should" inside the text; D/W carries that.

**Deal-breaker:** name the one function or risk whose failure kills the design. The first model answers it.

### Stories (light format for the person)

"As a <user>, I want <capability>, so that <benefit>." Each story gets an acceptance check in Given/When/Then form, which maps to a requirement line:

> Given a 7 kg load on the hook, when it hangs for 24 h, then the deflection is below 2 mm and nothing cracks.

### Completeness list (use the headings that apply; do not force all)

Performance, environment (indoor/outdoor, heat, water, UV, chemicals), life in service (cycles, years), maintenance, target cost, quantity, manufacturing (what the person can make or order), size, weight, materials, look and finish, ergonomics (hand, reach, body), safety, standards and law, testing, disposal, time scale.

### Kickoff questions (ask the missing ones, one per turn by default, each with a default)

| # | Question | Unlocks |
|---|---|---|
| 1 | What should it do, in one sentence, and what must never fail? | main function, deal-breaker |
| 2 | What do you start from: an idea, a photo, a scan, a part, measurements? One known size? | scale, reference, the case |
| 3 | What does it fit to, touch or go around, and what must stay clear? | interfaces, envelope, keep-outs |
| 4 | Where and how is it used: inside/outside, heat, water, sun, children, how often? | environment, life, material shortlist |
| 5 | What loads or abuse: weight, drops, people on it? | load cases, safety factor, FEA set-up |
| 6 | How many, by when, what budget each? | quantity, target cost, process shortlist |
| 7 | What can you make or order: your printer and presets, laser, CNC, online shops, PCB fab? | process limits, DFM rules, hand-off format |
| 8 | Any electronics: power, buttons, sensors, connectors? | PCB + enclosure branch |
| 9 | How should it look and feel: colour, finish, size limits? | look wishes, render criteria |
| 10 | Is it part of a building or home? Where (jurisdiction)? Will a professional stamp it? | code packs, permit sheets |
| 11 | If we must trade, what matters most: cost, strength, look, speed? | weights for scoring and defaults |
| 12 | Run mode: full auto, or which checkpoints? Concepts or straight to one? Which hand-off items? | gates, concepts, package |

Elicit by use, not features: ask how it is installed, used every day, cleaned, and how it fails. Repeat across those situations until no new needs come up.

### Interface table (ICD), one row per interface

| ID | Part A | Part B | Datum / LCS | Governing sizes | Fit or gap | Fastener / standard part | Source | Frozen at |
|---|---|---|---|---|---|---|---|---|

Freeze the interfaces at L1. A later change goes through `changes.md` and the person's approval.

### From a photo or scan

- Find the item and its maker and model if you can; look up its drawings and sizes.
- Read the interfaces (mating faces, holes, clearances) and the envelope from the image or scan.
- Ask for one known size to set the scale when nothing can be looked up.
- For a scan, decide with the person how accurate each face must be (a tolerance band per face).

## Concepts and embodiment
<!-- later: when the person wants concepts, or at L2 for the embodiment rules -->

### When to do concept work

Ask the person (default in the brief). Go straight to one concept when the product type is well known (a bracket, a shelf, an enclosure, an adapter, a replacement part) or the person brings a reference. Say "no concept phase needed" and why. Keep 2–3 variants alive only for a sub-function that is still uncertain, and drop the weaker ones as the data comes in (set-based design).

### Steps

1. **Function.** The overall function as verb + noun ("hold phone", "clamp tube"). Split it into sub-functions. Note the flows between them: energy, material, signal.
2. **Morphological chart.** Rows: sub-functions. Columns: solution principles for each. Write functions, not parts ("warn the user", not "bell").
3. **Concepts.** Combine one cell per row into 2–3 concepts. Drop combinations that do not work together.
4. **Screen.** Compare each concept with a reference concept, criterion by criterion: better (+), same (0), worse (−). Then score the survivors with the person's weights (brief question 11).
5. **Deal-breaker first.** The first model of the chosen concept answers the critical question.

### Present the options

- **Rough block models**, just enough to show the idea and the main sizes. Each concept in its own document, so they never mix.
- **Pictures side by side**: the same view, the same scale, sent in chat; also live in the FreeCAD window.
- **A short comparison** per concept: each demand pass or fail, each wish scored, the main risk, how hard it is to make, a cost guess.
- **A recommendation with the reason.** The person picks one, or mixes parts of two.
- Never more than 3 options.

### Embodiment rules (apply at L2 and L3)

Basic rules:
- **Clarity**: each function has one clear working principle and load path. No double location of one feature.
- **Simplicity**: fewest parts and features; simple shapes that are easy to make and check.
- **Safety**: make it safe by design first, then guards, then warnings.

Principles:
- **Short, direct force path**: carry loads the shortest way; it saves material and deflection.
- **Even strength**: no sharp changes of section in the force flow; balance forces where you can.
- **Division of tasks**: one element per function when it helps; combine when it saves cost without harm.
- **Self-help**: let the load increase the hold (self-reinforcing) or protect itself under overload.
- **Stability**: disturbances die out; snap action only where wanted.
- **Mistake-proof assembly**: wrong assembly is impossible (keys, asymmetry, poka-yoke).

Design for X:
- **Manufacture**: use the native features of the chosen process (see the section `Workflow branches`).
- **Assembly**: fewer parts (aim: essential parts / all parts above 80 %), self-locating features, one assembly direction, standard fasteners.
- **Cost**: fix a target cost early; track it in the BOM at every gate.
- **Maintenance**: reach the wear parts with standard tools.
- **Disposal**: one material per part where you can; joints that come apart; marked plastics.
- **Standards**: standard parts and preferred sizes first.


### Part by part (each part is a design of its own)

The assembly fixes where parts meet. It does not design the parts. A fit problem in the assembly is not a reason to change a part's material, process or shape until that part was designed on its own.
- After L2, design each made part in its own pass: its function, its load path, its process, then its form (sections that follow the load, fillets at changes of section, the native features of the process). Read the parts of a similar product (catalogue or a photo) before you draw.
- Then fit it to its neighbours through the frozen interfaces. When it does not fit, change the interface by a change note, not the part's concept.
- A quick fix that changes a part's concept (another material, a bought part in place of a made one, a block in place of a shaped part, a moved interface outside the brief) is a trade-off for the person, also in a run without the person: log it as open, do not decide it alone.
- A part that is still a box or a cylinder at L3 is a stand-in, not a design: say so in the BOM.

## Modelling principles

These rules apply to every part in every CAD tool. They make a model cheap to build, exact and easy to change. A model made of placed blocks and long chains of booleans is a script, not a design: it breaks when one value changes.

1. **Plan the structure first.** One file for each part. A thin skeleton holds the shared values and the layout (centrelines, axes, interface points). Name and save it before anything refers to it. The assembly only places the parts.
2. **Refer only to stable geometry.** That is the origin planes and axes, datums attached to them, the skeleton and sketches. Never attach to a face or edge that a later feature, a boolean, a fillet or a pattern made: it can get a new name after a change. If you must use a made face, use the first feature that made it.
3. **Drive sizes from parameters.** Each value that sets a size, a fit or an interface has a name in one place. Features read it by name. Do not type the same number in two features. Keep the parameters outside the objects that they drive.
4. **Build shape with real features. Repeat it with patterns.** Make a shape from a constrained profile (pad, pocket, revolve, sweep, loft, hole), not from placed primitives and booleans. Repeat a feature inside a part with a pattern or a mirror. Repeat a whole part with linked copies in the assembly, not with a pattern.
5. **A stand-in is a block. A part is designed.** A block is correct for a placeholder that nothing else is built from. A made part gets its shape from its function, its load path and its process. Replace a stand-in before you add detail that depends on it.
6. **Keep the feature tree short and in a clear order.** Base shape, then the main features, then holes, then patterns, then fillets and chamfers. Each feature is one more point that can break. Correct a part in its own file and its own tree, not with patches in the assembly.
7. **Keep heavy detail cosmetic or last.** Threads, knurls, text and small fillets on many edges cost time on each rebuild. Give a thread as data (its size and standard) on a tap-drill hole and show it on the drawing. Model it only when the process needs the geometry (a printed thread). Put drawing dimensions on sketch-driven edges, as the last step.

A merge setting that joins faces (refine) is a choice for each feature. Do not use it on members that must stay separate (the tubes of a weldment, the parts of a cut list).

## Levels, build rules and gates

### The level ladder

A level says what the next person can **rely on**, not how much detail is drawn. Each level is a minimum. The mapping to BIMForum LOD is an analogy; for buildings, agree the LOD per element per stage with the person.

| Level | ≈ LOD | Holds | Frozen after it |
|---|---|---|---|
| L0 Brief | – | requirements list, deal-breaker, stories, interface table draft, standards, bought parts, hand-off menu | the brief (changes by change note) |
| L1 Skeleton | 100 | parameter set; master sketch; datums/LCS at every interface and motion axis; envelopes and space claims; bought parts as envelopes with their datums | interfaces and envelopes |
| L2 Layout | 200 | every part as one body at its final envelope and interfaces; process per part; joints on LCS; motion; first mass and cost | concept, process per part |
| L3 Detail | 300–350 | measurable as-designed geometry; fits, fasteners, clearances, connections | geometry and materials |
| L4 Release | 400 | process features, tolerances, drawings, process files, BOM and cost | the release |
| L5 As-built | 500 | checked against the real part or space; the accuracy is stated | – |

Define for this design what each level adds before L1. Stop at the end-state level the person chose.

### Build rules

**Parameters**
- One parameter set: a VarSet for named values; a spreadsheet configuration table for size families (variants as rows).
- Names: letters, digits, _; no leading digit; not a unit name.
- Put standards, fits, process values (wall, K-factor, clearance, layer height), loads and derived values (trail, wheelbase, mass budget) there too. Derived values are expressions, so they show the effect of a change at once.

**Skeleton**
- A master sketch on the origin planes, as simple as possible, fully constrained, driven by the parameters. It holds the layout only (centrelines, axes, key points).
- For members that leave the sketch plane (pairs of stays, legs), use 3D lines whose end points are expressions of the parameters.
- Datums/LCS at each interface and each motion axis, attached to the skeleton (vertex + edge), never to faces made by features or booleans.
- Bought and standard parts (gears, bearings, boards, fasteners): build or insert them at their own origin with their own LCS, and place them by joints.

**Parts**
- One body per manufactured part. It reads the skeleton through a binder and has its own LCS on it.
- Feature order: base → interfaces → structure → detail → fillets and chamfers last (larger first). Drafts early.
- Sketches fully constrained, geometric constraints before sizes. Generated profiles (gears, sprockets, imported outlines) are exempt; say so.
- Placeholders have the final envelope and the final interfaces, and are hollow where the real part is hollow, so mass is right.

**Assembly**
- Clearances (bores, slots, gaps) are cut before the joints.
- Joints on LCS only. Couplings by real ratios (gear and sprocket teeth).
- Motion checked at every level from L2.

**Tolerances**
- Model at nominal size. Record the fit (hole basis: H7/g6 sliding, H7/h6 located, H7/p6 press) in the interface table and the parameters. Printed parts are the exception: model their clearance.
- The datum frame on drawings is the skeleton LCS (and the scan alignment datums).
- Stack-ups: worst case for short or safety-critical chains and one-offs; RSS × 1.5 only for long chains from capable processes.

**Analysis**
- Check the geometry before meshing. Use a clean study copy (no slivers, no cosmetic features) that keeps the material.
- At least 2 elements through the thinnest wall, more for bending; else beams or shells. Refine until the stress where it matters stops changing.
- FEA is a feasibility check, never a sign-off.

**Test the skeleton**
- At the end of L1 and L2, change one driving parameter and one size row: everything must rebuild with no failure. Put them back.

### Gate checklist (every level)

- Recompute clean; every sketch fully constrained (generated profiles named as exempt); geometry valid.
- The parameter test rebuilds with no failure.
- Interference: static overlaps named; motion sweep clear.
- Mass and cost against the budget, with real materials.
- Each requirement: pass, fail, or open with the check that will close it. A line is pass only with a reading next to it (a tool reading, or a hand check with its sum). No reading: open.
- Each interface has its joining feature (a thread or its seat, a clamp slot and bolts, a bearing seat, a retention feature). Each bought part has a stand-in at its catalogue fit size and mass.
- The parts list of the product type is complete (for a bicycle, see `B4`). Each part can go on in the order of the assembly steps.
- Each part fits its process limits: printer bed, sheet size, tube stock, tool reach. Split a part that does not fit before L3.
- Analysis-ready (L3+): the study copy is valid; the mesh fits the thinnest wall.
- Each part in the load path of an FMEA row with S ≥ 9 has a feasibility check. Run each load case on its own. Check aluminium and welds against a fatigue value, not only against yield. A "recheck" in `changes.md` blocks the next gate.
- The branch rules of each part's process pass (the section `Workflow branches`).
- Scan-based: the deviation map is inside each face's tolerance band.
- Open risks from the FMEA with their action priority.

### Gates

| Gate | After | Must show |
|---|---|---|
| G0 Brief | L0 | requirements list (D/W, values, sources), deal-breaker, stories, interface table, hand-off menu, run mode and checkpoints |
| G1 Concept | concepts | 2–3 options compared, the pick, process per part, the deal-breaker answered by a first model |
| G2 Layout (PDR-like) | L2 | interfaces confirmed, load path, first mass and cost, motion clear, first FEA feasibility, DFM pass, FMEA rows |
| G3 Detail (CDR-like) | L3 | every demand verified or with a planned test, high-priority FMEA items closed, frozen interfaces unchanged, change log reviewed |
| G4 Release | L4 | the hand-off package complete per process (each file read back), the validation step named, a cold review done; no demand open or failed |

Each gate is one screen: what was done, renders and maps, requirement status, open risks, and one question: approve, change or stop. Write the answer in `decisions.md`. In auto mode, record it and go on unless a demand fails or a stop rule (the skill) applies. Close the actions of a gate before the next gate.

When nobody can answer (a run without the person), do not stop at a trade-off. Take the reversible choice inside the brief's ranges that keeps the demands, log it as a trade-off for the person, and go on with all work that does not depend on it. Stop only for a choice that costs money, cannot be undone, or lowers safety.

**Cold review before G4.** A separate reviewer (an agent that gets only the brief, the records and a read-out of the model) lists missing items, common-sense gaps and documents that do not agree. Fix the findings, then release.

**Verification** (did we build it right?) is your job: measurements, interference, FEA, DFM, renders. **Validation** (did we build the right thing?) is the person's, with the real part in use.

### Design FMEA (5–10 rows)

| Item / function | Failure mode | Effect | S | Cause | O | Prevention / detection | D | Action priority | Action |
|---|---|---|---|---|---|---|---|---|---|

- S, O, D from 1 to 10. Rank by severity first: lower the severity by design, then the occurrence by prevention, then improve detection.
- Failure modes: loss of function, less function, function now and then, partial function, unwanted function.
- High priority: S ≥ 9, or S ≥ 7 with O ≥ 4. Close those before G3.

### Change control

- After each gate, the approved items are frozen.
- For any change to a frozen item, first state its effect ("a 1.5 mm wall in place of 2 mm changes the thickness map and print time; OK?"), then act, then log it in `changes.md`.

## Hand-off and feedback
<!-- later: at L4, and when the person reports on a made part -->

### The hand-off menu (ask in the brief; offer what fits the process)

Always:
- The process files for each part (below).
- A BOM: parts, quantities, materials, real masses, cost per part and total, sources for bought parts.
- The requirements list with each line marked met, not met, or open.
- The decision and change logs.

Offer:
- Assembly drawings and exploded views.
- Step-by-step assembly instructions (an assembly manual), with the tools needed.
- An instruction or user manual (use, care, safety notes).
- Drawings with tolerances and the datum frame.
- A cut list (tubes, boards) with angles.
- Renders for a listing or a review.
- Patent-style figures (line drawings, numbered parts, views) — for the person's own filing; you do not give legal advice.
- A test plan for the first article (what to check, how, pass values).
- A permit or review set for building work (for a licensed professional or the authority).
- Other documents the process or the person needs.

### Package per process

| Process | Package | Rules |
|---|---|---|
| 3D print | sliced 3MF with the person's printer, filament and process presets; source STEP; print notes (orientation, supports, material, walls/infill, time, mass, post-processing, insert sizes, pause heights) | orientation set by the load direction (layers are weak); thickness map against the nozzle width; a test coupon for press or slide fits |
| Laser / sheet | 1:1 DXF (flat) or STEP (bent), one file per part per material and thickness; part list (material, thickness, quantity, finish, hardware); bend list | closed contours, no duplicate lines or stray points, text as outlines; holes and bridges at least the shop's minimum (often ≥ 50 % of thickness); taps and countersinks as plain holes with a callout; kerf only in the cut file, never in the model; use the shop's live limits |
| CNC machining | one-solid STEP + PDF drawing: critical sizes, tolerances, threads, finish, material, edge breaks | general tolerance class stated (for example ISO 2768-m); tighter tolerances only on the drawing; threads called out |
| Weldment / tube frame | tube cut list (OD, wall, length, both end angles and their phase), jig drawing with the datums and angles, weld notes, drawings | as for CNC for machined parts of the frame |
| PCB + enclosure | Gerbers (all layers and outline) + drill files; for assembly: BOM (designator, value, footprint, part number) and placement file (designator, X, Y, rotation, side); assembly drawing; enclosure STEP with board keep-outs | one revision for all files; designators match across BOM, placement and drawing; the same origin for all |
| Building / home | to-scale sheets: cover (address, code edition, sheet index), site plan, floor/foundation/framing plans, elevations, sections and details, load notes, material list, schedules, the code rule-pack report, IFC | every sheet marked "for review by a licensed professional or the authority"; rules depend on the jurisdiction — ask where |

Make the hand-off list from the BOM: one row per made part with its process file, its drawing and its DFM result. An item is complete only when its file is read back.

Never present output as stamped, approved or signed off.

### Feedback loop (L5)

1. The person reports in any mix: words ("too tight by about half a millimetre"), photos of the part in place, measurements, a new scan. Ask for what you need to decide.
2. Map the report to requirement lines: which line failed, by how much.
3. Find the cause: the model, the process (printer, shop), or the requirement itself.
4. Write a change note (`changes.md`) with the effect on frozen items; get approval if it touches a demand or a frozen interface.
5. Change the model through the parameters, run the gates again from the level the change touches, and make the next version of the package (keep the old one).
6. Record what was learned (for example a printer's real clearance) as a parameter value with its source, so the next design starts from it.

## Workflow branches
<!-- later: when a part's process is chosen -->

Each branch adds rules to the core method. Parameters, skeleton, datums and gates stay the same. Numbers marked "default" come from vendors or forums: confirm them with the supplier, the shop or a test, and record the real value as a parameter with its source.

### B1 Printed (FDM, SLA, SLS)
- Choose the print orientation at L2: it sets overhangs, supports and the weak layer direction. Loads across layers are the weak case.
- Overhangs: about 45° self-supporting (FDM default); metal LPBF 30–45°.
- Parameters per printer and material: min wall (a multiple of the nozzle width), min hole, part-to-part clearance, bridge span, layer height. Model fit clearances; ISO 286 fits do not apply.
- Inserts, nut traps, embedded parts: sizes from the insert maker; pause heights in the slice.
- Textures last, after all checks.
- Hand-off: see the section `Hand-off and feedback` (3D print).

### B2 Sheet metal and laser
- Set the bend model before the first flange: BA = π(R + K·T)·A/180. K, R and T per material and thickness from the shop's bend table or a test bend.
- Bend relief where a bend meets an edge. Min flange and hole-to-bend distance from the shop's tooling table.
- Flat laser parts: tab-and-slot or finger joints sized to the sheet thickness plus a small fit. Kerf only in the cut file.
- Hand-off: see the section `Hand-off and feedback` (laser / sheet).

### B3 Machined (mill, lathe)
- Inside corner radius ≥ cutter radius (default ≥ 1/3 of the pocket depth). Pocket depth ≤ 4 × width. Hole depth ≤ 10 × D (4 preferred). Thread engagement 2–3 × D.
- Standard drill and tap sizes (the Hole feature). Few setups; every feature reachable.
- Hand-off: see the section `Hand-off and feedback` (CNC).

### B4 Weldment and tube frame
- The skeleton is the centrelines between nodes. Tubes are bodies swept along skeleton edges with real OD and wall.
- Mitre or cope each tube end to its neighbour for a tight fit-up. Fillet gap: AWS D1.1 max 3/16 in; above 1/16 in, add the gap to the leg. Thin chromoly fit-up about 0.25–0.5 mm (forum default).
- Tubular T/Y/K joints per AWS D1.1 Clause 10; watch acute crotches (dihedral < 30°) for weld access.
- Where several tubes meet at one point (a bottom bracket, a head tube), make the shell first (as a ring, with its bore), then sweep the tubes into it, then cut the bores again. A bore cut after a fuse does not repair a shell that the fuse made invalid.
- Trap: Refine on every feature of a big pipe weldment can make the body unorientable (Check Geometry) after a small parameter change. Keep Refine off on the pipes (pd_pipe does this by default). If body_check or the health check says unorientable or not valid, set Refine false on each feature (object_set { object, values: { Refine: false } }), then recompute and body_check again.
- Put each tube node away from the shell faces: a tube centre at least its radius + 8 mm from a head-tube face; a top tube below the seat clamp; stays inboard of the BB shell faces.
- Welded 6061 for T6: solution treat, quench, straighten in the W temper, then age. The usual filler for a heat treatment after welding is 4643 (confirm with the shop). After the heat treatment, ream and face the bores and chase the threads.
- Jig and fixture datums in the skeleton; balanced weld order.
- FEA of thin tubes: beams or shells, or a study copy whose mesh is at most half the wall.
- Bicycle parts list (each one a body or a stand-in by L2): frame with dropouts (axle slots) and brake mounts; fork with a crown race seat and the steerer preload (top cap, star nut or expander); headset; BB (BSA: tap drill 33.6 mm, drive side left-hand); cranks on the spindle interface (separate arms); pedals (9/16 × 20, left pedal left-hand); chainring with its bolt holes; chain (length by the formula, even links); cog or freewheel on its thread; wheels (hub flanges, spoke holes, spoke length; rear laced tangent); rims with a smooth brake track; tires with a retention feature; brakes (calipers, levers, cables, housing, stops); bar with 22.2 mm grip ends; grips; stem with clamp slots and bolts; seatpost (insertion ≥ 100 mm) and seat clamp slot; saddle with 7 mm rails; city items (lights, reflectors, bell, mounts). Clearances: tire to frame and fork, chainring to stays, heel, toe overlap, pedal to ground.
- Bicycle: origin at the bottom-bracket centre; stack and reach to the head-tube top; trail = (R·cos A − offset)/sin A with A from horizontal; head angle 71.5–74.5°, trail 55–60 mm (57 common); sizes as rows of a configuration table.
- Hand-off: see the section `Hand-off and feedback` (weldment).

### B5 Mechanism
- The skeleton is a linkage: lines and points on LCS, before any bodies.
- Mobility (planar): M = 3(L − 1) − 2·J1 − J2. M = 1 for one input; M ≤ 0 is a structure.
- Grashof: S + L ≤ P + Q means at least one link turns fully.
- Joints on LCS at the pivots; couplings by tooth counts; limits from the requirements.
- Motion sweep at every level; static overlaps apart from contacts the motion makes.

### B6 Spaces: rooms, buildings, sites (BIM / home)
- Ask the jurisdiction and whether a professional will stamp it. Codes and permit thresholds depend on the place.
- Agree the LOD per element per stage (schematic 100–200, design 300, coordination 350, shop 400, as-built 500 with a stated accuracy).
- Site, levels and grids are the skeleton; walls, slabs and openings host on them.
- An IFC class for every element; quantities from schedules.
- Code checks with the rule packs at each stage; report pass or fail with the code section.
- Hand-off: see the section `Hand-off and feedback` (building / home).

### B7 PCB and enclosure
- The interface is the board outline + mounting holes + keep-outs + height zones: one sketch on an LCS, shared with KiCad (the grid origin is the shared datum).
- Bosses, standoffs and openings take their positions from that sketch only.
- Connectors as full models; small parts as boxes; collision check.
- Hand-off: see the section `Hand-off and feedback` (PCB + enclosure); the enclosure follows its own process branch.

### B8 Scan- or photo-based (replacement and interface parts)
- Align first: a datum (3-2-1) alignment where the part has functional faces; best fit only for free form.
- Fit planes and cylinders to scan regions; build the datums and the skeleton from the fits.
- Decide a tolerance band per face with the person; run a deviation map at every level; state the scan accuracy.
- Take snapshots during the build and compare with the reference.
- For a photo: identify the item and look up its sizes, or get one known size for scale.
- Scan tools from ScanRuler by Stefan Hermann (CNC Kitchen) where they are installed.

## Agent Link steps and traps

Agent Link drives FreeCAD (1.1 or later) through MCP, live in the person's window or headless. Every tool is callable by name; the client may list only a few. Find others with `tool_find` (by words or by name for the whole card) and call them through `batch` when the client sends only listed tools. `guide_read` has the workflow guides.

Pin one FreeCAD version per project: 1.1 converts old Body origins when it opens older files.

### Start of a session
- `session_state`: FreeCAD version, the open document, bodies, add-ons, what FreeCAD is doing now.
- After any FreeCAD restart: `doc_switch` to another document and back, so the agent and the window act on the same document; `session_state` shows `mismatch` when they differ.
- `doc_new`, `doc_save { path }`. Save before each batch and at each level. Before each save, measure the bodies that changed (`body_check`, or `get` of `Body.volume`) and report the volume. Make a checkpoint (a saved copy) before a risky step.

### Step → tools → GUI

| Step | Agent Link tools | FreeCAD GUI |
|---|---|---|
| Parameters | `varset_new`, `varset_set` (group for derived values); `param_bind` for expressions | Std VarSet; f(x) / `=` in a property field |
| Size family | `sheet_table` make / use / add | Spreadsheet > Configuration table… |
| Bind a value | `param_bind { target: "Object.Property" or "Sketch.constraintName", expression }` | Expression editor |
| Master sketch | `pd_body_new` (a "Master" body), `sketch_new`, `sketch_add`, `sketch_constrain` (named constraints), `sketch_state`; one `batch` with `build: "end"` | PartDesign body > Sketch on an origin plane |
| 3D skeleton lines | `part_wire { kind: line }`, then `param_bind` on X1…Z2 | Part > Primitives > Line + expressions |
| Read the skeleton | `shape_query { body: <binder or sketch>, kind: edge | vertex }` | select and read the status bar |
| Bring the skeleton into a part | `pd_binder { body, from }` (a SubShapeBinder) | PartDesign > Sub-object shape binder |
| Datums / LCS | `pd_datum { kind: lcs | line | point, refs: [vertex, edge], mode, offset }`; `part_datum` (planes, csys in a body or part); `pd_datum_plane` | Part > Create coordinate system (1.1 core datum); attachment panel |
| Tubes on the skeleton | `pd_pipe { path: binder, edges: [..], sketch: { circle: { d, wall } } }` (d and wall may be expressions) | PartDesign > Additive pipe |
| Features | `pd_pad`, `pd_pocket`, `pd_revolution`, `pd_polar_pattern`, `pd_hole`, `pd_fillet`, `feature_edit { body, feature, set }` | PartDesign toolbar |
| Gears, sprockets | `pd_gear { kind: gear | sprocket, teeth, pitch }` (on the body's own XY plane) | PartDesign > Involute gear / Sprocket |
| Material | `material_set { bodies, id }` or `custom { name, density }` | Material editor |
| Assembly | `asm_new`, `asm_add`, `asm_ground`, `asm_joint` (ends on LCS by name; `keep: true` for parts already in place; `kind: chain` with teeth); `link_make { file, to }` for a part in another file, then `asm_add` the link | Assembly workbench; Std LinkMake |
| Motion | `asm_sweep` (static overlaps apart; stops at its time limit and says where to go on), `asm_motion` | Assembly > Create Simulation |
| Checks | `body_check`, `asm_check`, `measure_mass`, `view_render`, `view_maps` (thickness, deviation, stress), `fea_setup` / `fea_solve`, and the DFM and fit checks of installed add-ons | Check geometry; FEM; interference |
| Hand-off | `export`, `asm_bom`; add-on tools for slicing, drawings, cut files (their own skills) | Export; TechDraw; Assembly BOM |

### Known traps
- Refine on every feature of a large pipe weldment can leave the body "unorientable" after a small parameter change. Keep Refine off on weldment features (pd_pipe does by default).
- A sketch attached to a binder edge can lose the edge after a rebuild (topological naming): sketch_attach { sketch, repair: true }, or attach it again with edge and mode.

- `param_bind` and expressions resolve an object by its **name**, not its label ("Pad" may be another body's pad). Use the label form `<<Label>>.Property` or the exact name from `feature_list` / `object_list`.
- A feature made right after a datum it uses may read the datum's old position. Run `recompute { force: true }` after you make or move datums, before features that use them, and check the box size in the answer.
- An LCS attached in mode Translate keeps its own rotation and ignores the offset rotation: set the rotation on its Placement.
- `sketch_new` takes the body's planes and PartDesign datum planes; to sketch on an LCS, make a datum plane from it first.
- `pd_gear` works on the body's own XY plane: build the gear at the part's origin and place the part by a joint.
- Booleans and refine can rename faces; joints on LCS do not break. A joint picked by a query is picked again and the health line says so.
- Tube ends that all meet at one point inside a solid can make the fused shape invalid: end tubes at the shell surface or cut the bore after the fuse; check with `body_check`.
- A joint can put a part on the other side (the drive side on the left, a pedal into its arm). After each joint, check the side in `asm_check` or a top view; use `reverse: true`. A changed LCS offset does not move parts that are joined already: remove the joint and make it again.
- Helper lines at document level used in a body through `pd_binder`: set the binder's `Relative` to false, else the shape stays at its world place when the assembly moves the body.
- Expressions on an LCS (its `AttachmentOffset`) need the label form `<<Geo>>.name`; `VarSet.name` is read as a role inside the LCS. A placed LCS has a computed Placement: bind `AttachmentOffset`.
- A PartDesign feature in the middle of a chain cannot be deleted: suppress it (`Suppressed: true`), the base feature first.
- A part that goes around another (a brake caliper around a tire) needs an envelope with the gap, not a solid block.
- A large assembly makes each call slower (5–35 s): hide or leave out stand-ins with many solids (spokes) for sweeps and renders.
- The slicer command line can stop on the person's own filament preset or on a two-nozzle printer: use the system filament of the same type and say so.
- No tool makes a tube cut list in this version: calculate lengths, cope angles and phase from the skeleton.
- Long calls go to a background job: read `job_status`; read the newest batch record before you call again.
- Never approve code or file actions for the person (`approve_code`, `approve_file` are theirs).
- One file for each part, the route: `doc_new` for each part, and `doc_save` each in one project folder. Keep the shared values in a parameter file (a VarSet); a part reads them with `File#<<Params>>.name` (that file must be open). Make the assembly file in the same folder: `link_make { file, to }` for each part, then `asm_add` the links and put joints on the LCS of each part (`asm_joint`, element: the LCS label). Save, close and open the assembly again, and read each link's target (`object_get`, filter `LinkedObject`): a FreeCAD bug can save a link path from the home folder. Move the whole folder, never one file: links keep relative paths.
- A value from another file (`File#<<Params>>.name`) needs that file open. A closed file keeps its last value and gives no warning. After you change a shared value, open the parameter file first, recompute, and read one driven value.
- Threads not in FreeCAD 1.1's hole tables: there is no custom pitch, and 9/16"-20 (the bicycle pedal thread) is not there (UNF 9/16 is 18 TPI). Make the hole by its tap-drill diameter (9/16"-20: 33/64 in, 13.1 mm) and give the thread (size, pitch, hand) in a note and on the drawing. The hole's "cosmetic thread" option comes after 1.1.
- `modelThread: true` makes no thread when the hole is reversed or when its depth is shorter than the part ("through" works). Mirroring a modelled thread changes its hand.
- 1.1 changed the body origin and the datums: a file saved in 1.1 can break in 1.0. Part's datum line replaces PartDesign Line.

## Sources
<!-- later: when the person asks where a rule comes from -->

Each rule in the skill comes from one of these. Standards marked * were read through previews, summaries or course notes only. Vendor numbers are defaults; link to the live vendor page.

### Design process
- Pahl, Beitz, Feldhusen, Grote, Engineering Design: A Systematic Approach, 3rd ed., Springer 2007* — four phases; requirements list with demands and wishes; embodiment rules and principles; design for X.
- VDI 2221 Part 1:2019* — model of product design; the requirements list as a living document.
- Ulrich & Eppinger, Product Design and Development* — needs → target specs (metric, unit, marginal, ideal) → concepts → screening and scoring → final specs; writing needs. https://stuff.mit.edu/people/eppinger/SDE-MIT/PDD_Text.html
- Pugh, Total Design* — the PDS headings; concept screening against a datum (via Illinois ME170 PDS guide https://courses.grainger.illinois.edu/me170/sp2020/PDS.pdf).
- Cambridge IfM, Morphological charts. https://www.ifm.eng.cam.ac.uk/research/dmg/tools-and-techniques/morphological-charts/
- U. Arkansas, Mechanical Design (function analysis, morphological chart, Gruebler, Grashof). https://uark.pressbooks.pub/mechanicaldesign/
- Georgia Tech ME capstone, ideation (verb-noun functions; deal-breaker). https://mecapstone.gatech.edu/ideation-report
- MIT 2.009 milestones (sketch model, mockup, assembly review; "critical question"). https://2022.2009.mit.edu/syllabus
- ISO 9001:2015 clause 8.3* — planned stages, review, verification, validation, records, change control.
- VDI/VDE 2206:2021* — the V-model; continuous property validation (Graessler & Hentze, at – Automatisierungstechnik 2020).
- NASA Systems Engineering Handbook Rev 2; 6.3 Interface Management; NPR 7123.1 App. G (PDR, CDR). https://www.nasa.gov/reference/6-3-interface-management/
- AIAG & VDA FMEA Handbook 2019* — seven steps; Action Priority.
- Ward, Liker, Cristiano & Sobek, The Second Toyota Paradox (1995); Sobek, Ward & Liker (1999) — set-based design.
- ISO 9241-210:2019* — human-centred design.
- Bill Wake, INVEST in Good Stories (2003); Given/When/Then.
- BIMForum LOD Specification 2013–2024 (Level of Development as reliable output; LOD 350). https://bimforum.org
- Anthropic, Building effective agents (checkpoints, ground truth, gates). https://www.anthropic.com/research/building-effective-agents

### AI and CAD agents
- CAD-Assistant (arXiv 2412.13810) — tool-augmented FreeCAD agent.
- CADCodeVerify (ICLR 2025) — self-verification on renders helps.
- CADTests (arXiv 2605.07807)* preprint — renders alone did not help.
- Self-improving CAD agents with FEA feedback (arXiv 2605.17448)* preprint — blueprint first.
- Physics-in-the-Loop (arXiv 2605.19717)* preprint — over-complex geometry fails meshing.
- Text2CAD (NeurIPS 2024) — explicit parameters give precision.
- Autodesk Fusion generative design set-up (preserve, obstacle, loads, methods).

### FreeCAD
- FreeCAD 1.1 release notes (core datums usable in Assembly; Body origin conversion; external geometry defining; Hole threads; Check Geometry). https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Release_notes_1.1.md
- FreeCAD wiki: Topological naming problem; Feature editing; SubShapeBinder; Std VarSet; Configuration Tables; Part CoordinateSystem; KicadStepUp.
- Assembly4 README (no geometry used to place parts). https://github.com/Zolko-123/FreeCAD_Assembly4
- Modelling principles: FreeCAD wiki Feature editing (one solid in each Body; sketches and datums on the origin planes also after the 1.0 naming fix; dress-ups last; binders not from made geometry). https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Feature_editing.md
- FreeCAD wiki Expressions (cross-document values need the master file open). https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/Expressions.md
- FreeCAD wiki PartDesign Hole and FeatureHole.cpp (thread tables; Model Thread limits; cosmetic thread option after 1.1). https://github.com/FreeCAD/FreeCAD-documentation/blob/main/wiki/PartDesign_Hole.md
- FreeCAD issues on the naming problem in 1.x (#26889, #29154) and on links saved by scripts (#33468). https://github.com/FreeCAD/FreeCAD/issues/29154
- Park Tool TAP-6 (9/16"-20 tap drill 33/64 in).
- PTC Creo skeleton models; Autodesk Inventor skeletal modeling; Onshape master modeling; Solid Edge "10 golden rules"; CMU 24-688.

### Fits, stacks, analysis
- ISO 286-1:2010* (preferred fits); ASME Y14.5-2018*, ISO 5459* (datum frames).
- F. Scholz, Tolerance Stack Analysis Methods (Boeing / U. Washington). https://faculty.washington.edu/fscholz/Reports/isstech-95-030.pdf
- GoEngineer, failed mesh; MLC CAD meshing guide.

### Branches and hand-off
- ISO/ASTM 52910*; U. Oulu course slides citing ISO/ASTM 52911-1 and VDI 3405-3.
- SOLIDWORKS Help, K-factor; Javelin, bend tables.
- RpProto, CNC DfM rules (vendor); Xometry CNC design guide; Fictiv quoting help.
- SendCutSend file checklist and material limits. https://sendcutsend.com/faq/do-you-have-a-file-setup-checklist/
- JLCPCB, Gerber and drill files from KiCad. https://jlcpcb.com/help/article/how-to-generate-gerber-and-drill-files-in-kicad-9
- Miller Electric (chromoly TIG); LANL WFP 2-04 (AWS D1.1 gap rule); AWS D1.1:2025 preview*; Lincoln Electric (weld distortion).
- Fitwerx (stack and reach); bicycle geometry (trail); Calfee Design, Geometry of bike handling.
- Geomagic Design X guide; GoEngineer and Digitize Designs (datum vs best-fit alignment).
- Grass Valley CA and Monterey CA deck permit checklists (examples only; rules vary by place).
- ScanRuler and BumpMesh by Stefan Hermann (CNC Kitchen).
