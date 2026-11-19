<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Listing text for Agent Link for FreeCAD

The text for the MCP Registry (`server.json`), the Claude extension
(`packaging/mcpb/manifest.json`), the FreeCAD Addon Index (`package.xml`)
and other MCP directories. Written in ASD-STE100. Version 1.0.0.

## Name

- Name: Agent Link for FreeCAD
- MCP Registry name: `io.github.jamesK1000011/agentlink-freecad`
- Claude extension name: `freecad-agentlink`
- PyPI package: `agentlink-freecad`
- Addon Index name: `AgentLink` (the Mod folder)
- Repository: https://github.com/jamesK1000011/AgentLink-FreeCAD
- Licence: LGPL-2.1-or-later; data files CC-BY-4.0
- Privacy policy: https://github.com/jamesK1000011/AgentLink-FreeCAD/blob/main/docs/PRIVACY.md
- Drafts for each submission: `packaging/listing/` (the owner submits)

## Short text (100 characters or fewer)

Drive FreeCAD from an agent: model, measure, check, draw and export parts, headless or live.

## Long text

Agent Link for FreeCAD connects an AI agent to FreeCAD through the Model
Context Protocol (MCP). The agent makes, measures, checks, draws and exports
parts, buildings and assemblies.

It works in two ways. Headless, it needs no FreeCAD window. Live, you watch
the work in your own FreeCAD window: the workbench changes, the buttons
light and the result is selected. The agent does not take your cursor.

The Agent Link panel beside the model tree shows notes, steps, review and
activity. File actions and code runs need your approval through two tools,
`approve_file` and `approve_code`. Your client's tool permissions control
them.

Add-ons that you install add their tools: ScanRuler for FreeCAD (scan
measuring, from ScanRuler by Stefan Hermann, CNC Kitchen), Workshop
(standard parts, making, electronics, drawings, SafetyNet), Texturizer
(surface textures, from BumpMesh by Stefan Hermann, CNC Kitchen), Tutor
(lessons in your window) and Agent Link for OrcaSlicer (slicing). An add-on
that is not installed costs no tokens.

It works with Claude Desktop, Claude Code, Cursor, VS Code, LM Studio and
other MCP clients. It needs FreeCAD 1.0 or later (1.1 recommended).

Not affiliated with or endorsed by the FreeCAD project, the FreeCAD Project
Association (FPA) or CNC Kitchen.

## Keywords

FreeCAD, MCP, Model Context Protocol, CAD, AI agent, Claude, headless,
automation, 3D printing, parametric, TechDraw, FEM, BIM, CAM

## Privacy note

- Agent Link has no telemetry. It sends nothing on its own.
- What leaves your computer is your MCP client's own traffic: the answers
  and pictures that the agent reads go to your client's AI provider, under
  that provider's terms. Agent Link adds no other recipient.
- The window link listens on 127.0.0.1 only. Nothing outside your computer
  can reach it.
- Agent Link's records stay on your computer, in `~/AgentLink`: the usage
  log (`usage`, with no document or file names), `approvals.log` and crash
  copies (`crash`). Exports go there too, or to the output folder that you
  choose. The extension's launcher log is in
  `~/Library/Logs/FreeCAD Agent Link`. No log is sent anywhere.
- The network is used only when you or the agent ask for it: FreeCAD
  install or update (`app_install`, from FreeCAD's GitHub releases), add-on
  updates from GitHub (`agentlink_update`, `app_extensions`), the Addon
  Manager catalog (`addon`), and the printers that you set up in Workshop
  Make. These requests send nothing about you or your files.

## Where the text is used

| Place | Field | Source |
|---|---|---|
| MCP Registry | `description`, `title`, `version`, `repository` | `server.json` |
| Claude extension | `description`, `long_description`, `tools`, `version` | `packaging/mcpb/manifest.json` |
| Addon Index | `description`, `tag`, `version`, `date` | `package.xml` |
| PyPI | `description`, `keywords`, `version` | `pyproject.toml` |
| Anthropic directory (plugin) | `name`, `displayName`, `description`, README | `packaging/listing/claude-plugin/` |
