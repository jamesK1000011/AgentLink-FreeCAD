<!-- SPDX-License-Identifier: LGPL-2.1-or-later -->
# Parameters

## workflow
1. `param_set { name: "width", value: 40 }` (mm by default; `unit: "deg"` for angles; or an expression such as `"width / 2"`).
2. `param_bind { target: "Pad.Length", expression: "height" }`, or bind a named sketch constraint: `target: "Sketch.plate_width"`. A bare name is the parameter of that name (`Params.height`).
3. Change the part with `param_set` from then on. `param_list` shows each value and what uses it.

## variable sets
FreeCAD 1.0 and later also keeps named values in a variable set (App::VarSet), an object whose properties are the variables.
- `varset_new { name: "Dims", properties: { size: "55 mm", angle: "30 deg", count: 3 } }` makes one. `"55 mm"` becomes a length and `"30 deg"` an angle; plain numbers, true/false and text keep their kind.
- `varset_set { varset: "Dims", properties: { size: "60 mm" } }` changes a value or adds a variable. Everything bound to it recomputes.
- Bind to one with `param_bind { target: "Pad.Length", expression: "Dims.size" }`. The label works as well as the object's name (`VarSet.size`). `param_list` lists the variable sets under `varsets`.

## traps
- A sketch constraint must have a name to be bound. Name it with `sketch_constrain { name }`, `sketch_add { dims, name }` or `sketch_edit rename`. A reference (driven) dimension cannot be bound.
- A parameter's name follows FreeCAD's alias rules: a letter first, and not a cell address (`A1`), a unit (`m`, `mm`, `s`, `N`, `W` and the rest) or `e` / `pi`. A variable set's variables take the same names.
- A value that breaks a feature is refused with FreeCAD's error, and nothing is kept.
- A formula in another sheet takes a parameter by its bare name too (`=height * 2`), unless that sheet has an alias of the same name.
- `param_remove` refuses a parameter that is still in use. Unbind its users first (`expression: null`).
- A variable keeps the kind it was made with. A length takes `"60 mm"`, a count takes a whole number.
