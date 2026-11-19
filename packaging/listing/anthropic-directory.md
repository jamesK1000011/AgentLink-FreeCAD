<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# DRAFT: Anthropic directory submission (claude.ai)

Status: DRAFT. The owner submits. Checked against Anthropic's directory
documentation on 19 Nov 2026.

## Which door

- **The `.mcpb` file is not a directory listing any more.** Anthropic's
  connector submission page says that desktop extension listings are
  deprecated and the directory "no longer accepts local servers packaged
  as MCP Bundles (MCPB)". A local server goes into the directory inside a
  **plugin** (https://claude.com/docs/connectors/building/submission).
- The `.mcpb` file still installs by hand: double-click it, drag it into
  the Claude Desktop window, or Settings > Extensions > Advanced settings
  > Install Extension (https://claude.com/docs/connectors/building/mcpb).
  That is our GitHub release download.
- The plugin draft is [claude-plugin/](claude-plugin/). It starts the
  server with `uvx agentlink-freecad@1.0.0`, so PyPI must have 1.0.0
  first. `claude plugin validate ./packaging/listing/claude-plugin`
  passes with no warning (19 Nov 2026).
- Submit at https://claude.ai/directory/manage > **Submit new** >
  **Plugin bundle** (https://claude.com/docs/plugins/submit). Any paid
  Claude plan can submit. The GitHub account connected on claude.ai must
  have push access to the repository.

## Portal: Source step

| Field | Value |
|---|---|
| Repository | `jamesK1000011/AgentLink-FreeCAD` |
| Plugin path | `packaging/listing/claude-plugin` |
| Branch or tag | `main` (or a tag, to release by moving the tag) |

The **Listing details** step reads `plugin.json` and the plugin's
`README.md`. Remove the DRAFT comment line from that README first.

## Listing text (also for a later connector or other directory)

- Name (100 characters or fewer): `Agent Link for FreeCAD`
- Short description (200 characters or fewer):
  `Drive FreeCAD from Claude: model, measure, check, draw and export parts, headless or live in your own FreeCAD window. Not affiliated with or endorsed by the FreeCAD project or the FPA.`
- Categories (one to five): Design, Engineering, Productivity (pick the
  nearest ones that the portal offers).
- Documentation: https://github.com/jamesK1000011/AgentLink-FreeCAD#readme
- Privacy policy: https://github.com/jamesK1000011/AgentLink-FreeCAD/blob/main/docs/PRIVACY.md
- Support: https://github.com/jamesK1000011/AgentLink-FreeCAD/issues

Long description (2,000 characters or fewer):

```
Agent Link for FreeCAD lets Claude use FreeCAD for you. You need no CAD skills. Tell Claude what you want: an idea, some measurements, a photo or a 3D scan. Claude makes the part, checks it, draws it and exports the files.

It works in two ways. Headless, it needs no FreeCAD window. Live, you watch each step in your own FreeCAD window: the workbench changes, the sketch opens and the result is selected. Claude does not take your mouse or keyboard. Each change is one FreeCAD undo step.

What Claude can do: Part and Part Design modelling, sketches with constraints, parameters and spreadsheets, materials, strength checks with Gmsh and CalculiX (a feasibility check, never a sign-off), TechDraw drawings with dimensions and GD&T, meshes and point clouds, assemblies, CAM toolpaths, Draft, Surface, BIM with IFC, OpenSCAD and Robot. It exports STEP, STL, 3MF, DXF, PDF and more, and renders pictures to check its own work.

The tool list starts short and grows by group, so a session costs few tokens. File steps and code runs need your approval.

Needs FreeCAD 1.0 or later (1.1 recommended) and uv. Licence LGPL-2.1-or-later. Not affiliated with or endorsed by the FreeCAD project or the FreeCAD Project Association (FPA).
```

## Tools summary

Agent Link declares 415 tools in 32 groups (README, "What the agent can
do"). The list starts lean (`core`, `view`) and the agent turns on more
groups with `tool_groups`:

| Group | What it does |
|---|---|
| core | session, groups, guides, batches, jobs, undo, soundness, export |
| doc, std_more | open, save, objects, links, parts, document info |
| model, feature, sketch, param, sheet | Part and Part Design modelling, sketches, parameters, spreadsheets |
| measure, inspection | references, distances, mass, a scan against the part |
| material, strength, fem_more | materials; strength by finite elements (feasibility only) |
| techdraw | drawings with dimensions, tolerances, GD&T; SVG, PDF, DXF |
| mesh, points, surface, draft | meshes, point clouds, surfaces, 2D and lettering |
| assembly, cam, cam_more, bim, bim_gaps, openscad, robot | FreeCAD's other workbenches |
| view, notes | pictures headless or of the window; notes and step playback |
| app, unattended, dev, porting | FreeCAD install and updates, dialogs, add-on tests, add-on ports |

Approval tools: `approve_file` (file-level steps), `approve_code` (code
that a tool asks to run or install).

## Data handling step (draft answers)

| Question | Answer |
|---|---|
| Reads or stores personal data? | No. It reads the user's CAD documents on the user's computer. Records (usage counts, approvals) stay in `~/AgentLink`. |
| Sends data to services other than its declared connectors? | No user data. It downloads from GitHub (FreeCAD and add-on updates) and reads FreeCAD's add-on catalog, only on request. `plugin.json` declares these hosts under `network.hosts`. |
| How long does it keep data? | On the user's computer until the user deletes it; `outputs_clean` removes old pictures and runs. |
| Intended for people under 18? | No. |

## Privacy statement (short form)

Agent Link runs on your computer and has no telemetry. What Claude reads
from FreeCAD goes to Anthropic as part of your conversation. Agent Link
sends nothing else and adds no other recipient. It uses the network only
when you or Claude ask (FreeCAD and add-on updates from GitHub, FreeCAD's
add-on catalog). Its records stay in `~/AgentLink`. Full policy:
https://github.com/jamesK1000011/AgentLink-FreeCAD/blob/main/docs/PRIVACY.md

## What may hold the review

- **Tool annotations.** For connectors, Anthropic requires a `title` and a
  `readOnlyHint` or `destructiveHint` on every tool. Agent Link's tools
  have neither now (`agentlink/protocol.py` sends name, description and
  input schema only). The plugin page does not say that this blocks a
  plugin, but the security scan and reviewers may ask. Adding them to 415
  tools is a larger change for a later version.
- **Code execution.** `approve_code`, the `dev` and `porting` groups and
  the updaters fetch and run code. The scan may hold the version for a
  reviewer. The README and docs/PRIVACY.md disclose each source.
- **uvx.** The plugin depends on uv on the user's computer and on PyPI.
- The plugin pre-submission checklist page
  (https://claude.com/docs/plugins/pre-submission-checklist) could not be
  read for this draft. Read it before you submit.
