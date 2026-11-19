# How Agent Link works
<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->

These pages tell how Agent Link for FreeCAD works inside, step by step, with diagrams.
Each step names its module and its function, so you can find it in the code.

1. [How a call flows](call-flow.md): the client, the Claude extension's launcher, the supervisor, the hidden FreeCAD and the window link. What happens when the window is closed, busy, or has a dialog up.
2. [How a tool reads FreeCAD](reading-freecad.md): data tools and code tools, the families, the shared health check, the echo in the window, and the path guards.
3. [How a batch runs](batch.md): rollback, stopOnError, the held build, the budget, jobs, chaining, and a menu or dialog inside a batch.
4. [How add-ons plug in](addons.md): `agentlink_families`, tool data, groups, no cost when not installed, the launcher's pins, third-party add-ons.
5. [How approvals work](approvals.md): `approve_code` and `approve_file`, what asks, what is shown, what binds, and what cannot approve.

The add-ons have a page of their own each:

- [ScanRuler for FreeCAD](https://github.com/jamesK1000011/ScanRuler-FreeCAD/blob/main/docs/workflow/README.md)
- [Texturizer for FreeCAD](https://github.com/jamesK1000011/Texturizer-FreeCAD/blob/main/docs/workflow/README.md)
- [Workshop for FreeCAD](https://github.com/jamesK1000011/Workshop-FreeCAD/blob/main/docs/workflow/README.md)
- [Tutor for FreeCAD](https://github.com/jamesK1000011/Tutor-FreeCAD/blob/main/docs/workflow/README.md)
- [Agent Link for OrcaSlicer](https://github.com/jamesK1000011/AgentLink-OrcaSlicer/blob/main/docs/workflow/README.md)
