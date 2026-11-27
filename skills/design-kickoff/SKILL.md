---
name: design-kickoff
description: Run a new design in FreeCAD with Agent Link from first idea to hand-off package. Use at the start of any new part, product, mechanism, frame, room or home project, or a part rebuilt from a photo or scan, before the first sketch.
---
<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->

# Design kickoff

This skill is the design-engineering method for FreeCAD with Agent Link. It tells you how to work with the person and how to use the tools. Follow it from the first message to the hand-off and the feedback loop.

The method in one line: clarify the task, freeze the interfaces, then add detail level by level on a parametric skeleton, check each level, and hand off what each process needs. Rework is cheapest at the start, so spend effort there.

What only the person knows (how a part is made, what it is made of, what it must carry): ask, when someone answers. When nobody answers (a run with no person), take the plain choice, and say it in your last answer.

Write to the person in plain, short sentences. Assume no CAD or engineering skill. Go deeper only when the person shows more skill.

The details are in this skill's own file `design.md`, beside this file (in the AgentLink-FreeCAD repository: `skills/design-kickoff/design.md`). Read each section at its step, by its `##` heading (start with `Start here`). Agent Link's own guides (`guide_read`) hold only facts about FreeCAD and the tools: the design method is here, not there.
- `The brief` — the design records, the requirements list, stories, the kickoff questions, the interface table.
- `Concepts and embodiment` — functions, concepts, how to present options, embodiment rules.
- `Modelling principles` — how to model each part: structure, stable references, parameters, features and patterns, cosmetic detail.
- `Levels, build rules and gates` — the level ladder, the build rules, the gate checklists, the design FMEA, change control.
- `Hand-off and feedback` — the hand-off menu, the package per process, the feedback loop.
- `Workflow branches` — what changes per workflow (printed, sheet/laser, machined, weldment, mechanism, spaces/BIM, PCB + enclosure, scan- or photo-based).
- `Agent Link steps and traps` — the tools for each step, the FreeCAD GUI route, known traps.
- `Sources` — the source of each rule.

If an add-on is installed that brings its own skill (for example slicing, scans, drawings), use that skill at its step.

## 0. Start

1. Read everything the person gave: words, photos, scans, files, links, earlier notes. Do not ask for what is already there.
2. Name the case:
   - **New design** from an idea.
   - **Replacement** of a broken or lost part (the photo or scan is the reference).
   - **Interface part**: something new that fits to an existing item.
   - **Space**: a room, a building or a site.
3. Check your tools: `session_state` (Agent Link) shows FreeCAD, the open document and the add-ons. If Agent Link is not there, use the FreeCAD GUI route in the section `Agent Link steps and traps`.
4. Make the design records (section `The brief`) as plain markdown files where you can write them. Keep them up to date all the way.

## 1. Engineering Q&A (the brief, level L0)

Goal: a requirements list the person approves. No real geometry before it, except a rough envelope to show progress.

Rules:
- Ask one question per turn, unless the person asks for more at once. Give a default with each question. Ask the questions that unlock the most first: what it must do and what must not fail, what you start from, what it fits to.
- When the person does not know a value: first look it up (the maker's spec sheet, a datasheet, a standard, a known size). If you find nothing, assume a sensible value. Mark each value with its source: stated, measured, looked up (with the link), or assumed.
- Never guess a value that sets safety or fit when you can look it up or measure it. Loads, the jurisdiction (for buildings) and the user's use come from the person.
- For a photo, get one known size to set the scale, or identify the item and look up its sizes.
- Write needs as what the product must do, not how. Read the list back in plain words.

Also ask in the brief (each with a default):
- **Run mode and checkpoints.** Default: full auto. Ask where the person wants to stop and check (after the brief, after concepts, after the first draft, before the hand-off).
- **Concepts.** Explore 2–3 concepts, or go straight to one? For a known product type, offer to go straight.
- **Hand-off menu.** Which files and documents at the end (section `Hand-off and feedback`).
- **Process and material per part.** Decide together; give 2–3 options with trade-offs and a recommended default.

Gate G0: the requirements list, the deal-breaker, the interface table and the hand-off menu, read back. Approve, change or stop.

## 2. Concepts (if chosen) and the first draft

- Functions as verb + noun; a morphological chart; 2–3 concepts (section `Concepts and embodiment`).
- Present them as rough block models, each in its own document, rendered at the same view and scale, side by side; a short comparison (demands pass or fail, wishes scored, main risk, how hard to make); a recommendation. The person picks or mixes.
- Make the first model answer the deal-breaker question.
- First-draft check: a rough model and "Are we on the right track?" In auto mode, report it and go on.

Gate G1: the concept and the process per part.

## 3. Build level by level

Levels (details and build rules in the section `Levels, build rules and gates`):

| Level | You can rely on | Gate |
|---|---|---|
| L0 Brief | requirements, functions, interfaces, standards, bought parts | G0 |
| L1 Skeleton | parameters, master sketch, datums/LCS at each interface and motion axis, envelopes and space claims; interfaces frozen | (G1) |
| L2 Layout | every part as one body at its final envelope and interfaces; joints on LCS; motion | G2 (like a preliminary design review) |
| L3 Detail | measurable as-designed geometry; fits, fasteners, clearances | G3 (like a critical design review) |
| L4 Release | process features, drawings, files, BOM and cost | G4 |
| L5 As-built | checked against the real part (test, photo, scan) | feedback loop |

Core build rules:
1. All driving values live in one parameter set (VarSet or a spreadsheet; sizes as rows of a configuration table).
2. A master sketch on the origin, fully constrained and driven by the parameters, is the skeleton. Datums/LCS sit at every interface and motion axis, attached to the skeleton, never to faces made by features or booleans.
3. One body per part. It reads the skeleton through a binder and carries its own LCS. Features in order: base, interfaces, structure, detail, fillets last.
4. Clearances before joints. Joints on LCS only.
5. Every level only adds features to the same bodies. Interfaces frozen at L1 change only through a change note the person approves.
6. Save before each batch of changes and at each level.

Model like a designer, not like a script: one file per part, references only to stable geometry, sizes from parameters, real features and patterns (not placed primitives and boolean chains), threads and heavy detail cosmetic. Read the guide section `Modelling principles` before L1.

At L2, check each part against its process limits (printer bed, sheet size, tube stock, tool reach) and split the parts that do not fit. At L3, build each interface's joining feature (thread or its seat, clamp slot and bolts, bearing seat, retention), model every bought part as a stand-in at its catalogue fit size, check the parts list of the product type (the branch in `Workflow branches`), and check that each part can go on in the order of the assembly steps. Every part in the load path of a high-severity FMEA row gets a feasibility check; check aluminium and welds against fatigue, not only yield.

After L2, design each made part on its own: function, load path, process, then form, then fit it through the frozen interfaces (guide section `Part by part`). A fix that changes a part's concept (material, made to bought, a block in place of a shaped part, an interface outside the brief) is a trade-off for the person: log it as open, also in auto mode. A part that is still a box or a cylinder at L3 is a stand-in, not a design.

At every level, run the gate checklist and fix before going on. Check with real readings (recompute, DoF, measurements, interference, mass, maps, FEA), not with a picture alone. After every fix, measure again. If a check fails three times, stop and give the person the trade-off.

A requirement is met only with a reading next to it (a tool reading, or a hand check with its sum). With no reading it is open.

At each gate, show one screen: what was done, renders and maps, each requirement's status (pass, fail, open), the open risks, and one question: approve, change or stop. In auto mode, record the gate and go on unless a demand fails. Write the decision in the decision log.

## 4. Hand-off (L4)

Before G4, get a cold review: a separate reviewer (an agent with only the brief, the records and a read-out of the model) lists missing items, common-sense gaps and documents that do not agree. Fix its findings first. G4 cannot pass while a demand is open or failed.

Make the hand-off list from the BOM: one row per made part with its process file, drawing and DFM result. An item is complete only when its file is read back.

Make every item on the hand-off menu (section `Hand-off and feedback`). Each process gets its complete package. Always add: the BOM with real masses and cost, the assembly steps, and the requirements list with each line marked met or not.

Never call anything signed off. FEA is a feasibility check. A licensed professional or the authority approves building work. Validation happens when the person uses the real part.

## 5. Feedback loop (L5)

After the part is made or the space is built, the person reports back in any mix: words ("too tight"), photos, measurements, a new scan. Ask for what you need. Check the report against the requirements, make a change note against the frozen items, change the model through the parameters, run the gates again, and make the next version of the package.

## When to stop and ask (also in auto mode)

When you stop at a trade-off, offer an A/B/C check: run the same quick analysis on 2–3 options and show the readings side by side, then ask.

When nobody can answer (a run without the person), do not stop the run at a trade-off. Take the reversible choice inside the brief's ranges that keeps the demands, log it for the person, and go on with all independent work. Stop only for money, for a step that cannot be undone, or for lower safety.

- A change to a demand, a frozen interface, safety, the process, or the cost beyond what the person allowed.
- A value you cannot measure, find or safely assume (loads, use, jurisdiction).
- A failed check whose fix needs a trade-off.
- Anything that costs money or cannot be undone (an order, a long print, a submission).

Decide alone, and log it, when the choice is reversible, inside the stated defaults and covered by a check (fillet sizes inside the process limits, standard clearances from fit tables, rib positions).
