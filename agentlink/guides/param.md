<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Parameters

## workflow
1. `param_set { name: "width", value: 40 }` (mm by default; `unit: "deg"` for angles; or an expression such as `"width / 2"`).
2. `param_bind { target: "Pad.Length", expression: "height" }`, or bind a named sketch constraint: `target: "Sketch.plate_width"`. A bare name is the parameter of that name (`Params.height`).
3. Change the part with `param_set` from then on. `param_list` shows each value and what uses it.

## traps
- A sketch constraint must have a name to be bound. Name it with `sketch_constrain { name }`, `sketch_add { dims, name }` or `sketch_edit rename`.
- A value that breaks a feature is refused with FreeCAD's error, and nothing is kept.
- A formula in another sheet takes a parameter by its bare name too (`=height * 2`), unless that sheet has an alias of the same name.
- `param_remove` refuses a parameter that is still in use. Unbind its users first (`expression: null`).
