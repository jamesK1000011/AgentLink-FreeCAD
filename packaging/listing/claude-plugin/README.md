<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
<!-- DRAFT for Anthropic's plugin directory: the owner submits it (docs/RELEASING.md, section 5). Remove this line before you submit. -->
# Agent Link for FreeCAD

Agent Link lets Claude use FreeCAD for you. You tell Claude what you want:
an idea, some measurements, a photo or a 3D scan. Claude makes the part,
checks it, draws it and exports the files. It works headless, with no
FreeCAD window, or live in your own FreeCAD window, where you see each
step. It does not take your mouse or keyboard.

Not affiliated with or endorsed by the FreeCAD project or the FreeCAD
Project Association (FPA). FreeCAD is the FPA's trademark.

## What you need

- FreeCAD 1.0 or later (1.1 recommended), from https://www.freecad.org
- uv (https://docs.astral.sh/uv/), which starts the server with
  `uvx agentlink-freecad`

## Use it

Ask Claude for a part: "Make a wall bracket for a 20 mm pipe, two M4
screws, printable without supports." Claude makes it, checks that the
body is sound, renders it and exports STEP or STL. To watch the work,
open FreeCAD, pick the Agent Link workbench and press Start Link.

File steps and code runs need your approval (`approve_file`,
`approve_code`). Strength checks (FEA) show if a design is feasible. They
are never a sign-off.

## Data

The plugin has no telemetry. What Claude reads from FreeCAD (answers,
pictures) goes to Anthropic as part of your conversation. Agent Link
sends nothing else. It uses the network only when you or Claude ask:
FreeCAD install and updates from GitHub, add-on updates from GitHub, and
FreeCAD's add-on catalog. Records stay on your computer in `~/AgentLink`.
Privacy policy:
https://github.com/jamesK1000011/AgentLink-FreeCAD/blob/main/docs/PRIVACY.md

## Support

https://github.com/jamesK1000011/AgentLink-FreeCAD/issues

Licence: LGPL-2.1-or-later (data CC-BY-4.0).
