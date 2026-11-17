# SPDX-License-Identifier: LGPL-2.1-or-later
# What the code made of the material, FEM and strength tools of
# families/material.py, fem_more.py and strength.py now kept as data, at the
# commit they were converted from (tests/test_datafem_data.py's BASE): name,
# description, inputSchema, changes, reads, group. Written by
#   python3 tests/test_datafem_data.py --before
# and checked against that commit's source wherever git has it.
import json

BEFORE = json.loads(r'''
{
 "material_list": {
  "name": "material_list",
  "description": "Find materials: words (every word must be in the id, name, category, tags or description) and category (part of one: \"Printing filament\", \"Metal/Steel\", \"Thermoplast\" …; the reply's categories lists them). The printing filaments (pla, petg, abs, asa, pa6-cf, tpu-95a) come first, then FreeCAD's material library (its cards with a density or stiffness; appearance-only, fluid and pattern cards left out), then this document's custom ones. Reply: found, materials [{ id, name, category, density g/cm³, E and yield MPa where the card has them }] (limit 20), more. A library card's id is its UUID; its exact name works wherever an id is asked. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "words": {
     "type": "string"
    },
    "category": {
     "type": "string"
    },
    "limit": {
     "type": "integer"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "material"
 },
 "material_get": {
  "name": "material_get",
  "description": "One material's figures by id (a filament key, a library card's UUID or exact name, custom:<name>): density g/cm³, E (Young's modulus) MPa, nu (Poisson's ratio), yield and uts MPa, k W/(m·K) where the card has them, source, and missing (which of density, E, nu, yield the card lacks — fea needs E and yield, mass needs density). Library and filament figures are typical — a part that must not fail needs the supplier's. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "id": {
     "type": "string"
    }
   },
   "required": [
    "id"
   ],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "material"
 },
 "material_set": {
  "name": "material_set",
  "description": "Say what bodies are made of: id from material_list (or a library card's exact name), or custom { name, density g/cm³ (required), youngsMPa, yieldMPa, utsMPa, poisson, conductivity W/(m·K), softensC, source } for the supplier's figures (kept as custom:<name>). Kept with the document by the body's label (measure_mass, fea_* and drawings read it there); a library card also goes on the object's ShapeMaterial, which FreeCAD's own Material panel shows (shapeMaterial says per body). An installed add-on that owns materials keeps those it knows (printing filaments), marked from. bodies: the one body when left out. Reply: material, mass_g (volume × density, solid through), missing (E / yield the card lacks). Trap: object_rename does not carry it to the new label.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "bodies": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "id": {
     "type": "string"
    },
    "custom": {
     "type": "object"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "material"
 },
 "material_clear": {
  "name": "material_clear",
  "description": "Forget what bodies are made of (bodies; every body with a material when left out). measure_mass then asks for a material again (a printed part is taken as PLA and says so); strength studies assume PLA and say so. FreeCAD's own ShapeMaterial on the object is left as it was. Reply: cleared, materials (what is still recorded).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "bodies": {
     "type": "array",
     "items": {
      "type": "string"
     }
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "material"
 },
 "fem_add": {
  "name": "fem_add",
  "description": "Add one of FEM's other objects to an analysis (fixed / force / pressure / self-weight, the material and Gmsh mesh: fea_native): kind (bearing, body_heat_source, current_density, electric_charge_density, electromagnetic, electrostatic_potential, flow_velocity, fluid_boundary, gear, initial_flow_velocity, initial_pressure, initial_temperature, magnetization, plane_rotation, pulley, rigid_body, section_print, spring, transform, centrifugal, contact, tie, displacement, heatflux, temperature, vacuum_permittivity, fluid_1d, rotation_1d, geometry_1d, geometry_2d, material_fluid, material_reinforced, material_nonlinear, solver_mystran, solver_z88, solver_elmer, solver_calculix, eq_magnetodynamic2d, eq_magnetodynamic, eq_electrostatic, eq_heat, eq_flow, eq_elasticity, mesh_region, mesh_boundary_layer, mesh_group, mesh_distance, mesh_manipulate, mesh_advanced, mesh_shape, mesh_transfinite_curve, mesh_transfinite_surface, mesh_transfinite_volume; refused where this FreeCAD lacks it); refs [\"Body.Face3\", …] or { body, faces: [queries] }; props { its FreeCAD properties: a quantity as text with its unit, \"2 MPa\", \"100 N\", \"1000 N/mm\" — a bare number is refused for a quantity, since FreeCAD keeps them in mN and kPa } — the answer lists them; mesh / solver / material where a refinement, equation or nonlinear material needs one; new: true makes a new analysis for a solver.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "kind": {
     "type": "string",
     "enum": [
      "bearing",
      "body_heat_source",
      "current_density",
      "electric_charge_density",
      "electromagnetic",
      "electrostatic_potential",
      "flow_velocity",
      "fluid_boundary",
      "gear",
      "initial_flow_velocity",
      "initial_pressure",
      "initial_temperature",
      "magnetization",
      "plane_rotation",
      "pulley",
      "rigid_body",
      "section_print",
      "spring",
      "transform",
      "centrifugal",
      "contact",
      "tie",
      "displacement",
      "heatflux",
      "temperature",
      "vacuum_permittivity",
      "fluid_1d",
      "rotation_1d",
      "geometry_1d",
      "geometry_2d",
      "material_fluid",
      "material_reinforced",
      "material_nonlinear",
      "solver_mystran",
      "solver_z88",
      "solver_elmer",
      "solver_calculix",
      "eq_magnetodynamic2d",
      "eq_magnetodynamic",
      "eq_electrostatic",
      "eq_heat",
      "eq_flow",
      "eq_elasticity",
      "mesh_region",
      "mesh_boundary_layer",
      "mesh_group",
      "mesh_distance",
      "mesh_manipulate",
      "mesh_advanced",
      "mesh_shape",
      "mesh_transfinite_curve",
      "mesh_transfinite_surface",
      "mesh_transfinite_volume"
     ]
    },
    "analysis": {
     "type": "string"
    },
    "refs": {},
    "props": {
     "type": "object"
    },
    "mesh": {
     "type": "string"
    },
    "solver": {
     "type": "string"
    },
    "material": {
     "type": "string"
    },
    "new": {
     "type": "boolean"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "kind"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "fem_more"
 },
 "fem_mesh": {
  "name": "fem_mesh",
  "description": "FEM meshes: action netgen { body, props } (Netgen's mesh; refused where Netgen is not installed) | to_mesh { mesh, result, name } (the FEM mesh's outside as a plain mesh, deformed by a result) | clear_groups { mesh } (its groups removed).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "action": {
     "type": "string",
     "enum": [
      "netgen",
      "to_mesh",
      "clear_groups"
     ]
    },
    "body": {
     "type": "string"
    },
    "mesh": {
     "type": "string"
    },
    "result": {
     "type": "string"
    },
    "analysis": {
     "type": "string"
    },
    "props": {
     "type": "object"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "action"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "fem_more"
 },
 "fem_linearize": {
  "name": "fem_linearize",
  "description": "Stress linearization through a wall from a FEM result (a CalculiX result object, CCX_Results after fea_solve, or a post pipeline): from and to [x,y,z] mm on the wall's two faces, points (41), field (von Mises by default; NodeStressXX …) → membrane, bending, membrane + bending, peak (MPa). A line that leaves the part is refused.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "result": {
     "type": "string"
    },
    "from": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "to": {
     "type": "array",
     "items": {
      "type": "number"
     }
    },
    "points": {
     "type": "integer"
    },
    "field": {
     "type": "string"
    }
   },
   "required": [
    "result",
    "from",
    "to"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "fem_more"
 },
 "fea_shell": {
  "name": "fea_shell",
  "description": "A thin plate or shell by shell elements (CalculiX on Gmsh's triangles): object (a face, shell or sheet: its faces are the mid-surface; faces narrows), thickness mm, material, holds [{ edges \"boundary\" (every free edge) | [{ near: [x,y,z] }], kind pinned (simply supported) | fixed (clamped) }], pressure MPa and/or gravity: true, mesh mm. Answers the largest deflection (mm) and stress (MPa). Panels, lids, sheet-metal, floors and walls as plates. Runs in the foreground (timeout s, 300); needs ccx and gmsh.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "object": {
     "type": "string"
    },
    "faces": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "thickness": {
     "type": "number"
    },
    "material": {
     "type": "string"
    },
    "holds": {
     "type": "array",
     "items": {
      "type": "object"
     }
    },
    "pressure": {
     "type": "number"
    },
    "gravity": {
     "type": "boolean"
    },
    "mesh": {
     "type": "number"
    },
    "timeout": {
     "type": "number"
    }
   },
   "required": [
    "object",
    "thickness"
   ],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "strength"
 },
 "fea_parts": {
  "name": "fea_parts",
  "description": "A strength study of several parts together (instead of fea_setup): bodies [labels, one solid each], materials { label: id } (else each body's own), join tie (bonded where they touch: glued, welded, press-fit) | contact (they push but do not pull; friction 0.2 lets them slide) | none, tolerance mm for touching (0.05), mesh mm. Makes a hidden compound, the study's body; answers touching (pairs and area) and warns of overlaps. Then fea_hold / fea_load on the parts' faces and fea_solve: each part's peak stress and safety.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "bodies": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "materials": {
     "type": "object"
    },
    "join": {
     "type": "string",
     "enum": [
      "tie",
      "contact",
      "none"
     ]
    },
    "friction": {
     "type": "number"
    },
    "tolerance": {
     "type": "number"
    },
    "mesh": {
     "type": "number"
    },
    "name": {
     "type": "string"
    }
   },
   "required": [
    "bodies"
   ],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "strength"
 },
 "fea_setup": {
  "name": "fea_setup",
  "description": "Start (or change) a strength study of one body: body; solid: n studies one solid of a multi-solid body alone (a hidden helper, read again from the body at each solve; its faces are numbered on their own); material (the body's by default; it needs a Young's modulus), mesh (largest element edge, mm; by default a third of the least size; one that makes over about 400,000 elements is refused). The same body's holds and loads are kept (said as kept; unmatched lists those that fit no face now); reset: true drops them (said as dropped). Answers study, material and next. A rigid hold makes stress no real mount does; a coarse mesh under-reads peaks; library figures are typical.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "body": {
     "type": "string"
    },
    "solid": {
     "type": "integer",
     "description": "One solid of a multi-solid body (an AllowCompound Body), from 1, studied alone."
    },
    "material": {
     "type": "string"
    },
    "mesh": {
     "type": "number"
    },
    "reset": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "strength"
 },
 "fea_hold": {
  "name": "fea_hold",
  "description": "Hold faces: faces by query — { near: [x,y,z] }, { normal: [0,0,-1], z: 0 }, { faces: [\"Face1\"] }, shape_query's references (\"Face8\", a list) or its filters ({ type: cylinder, radius: 3 }); kind fixed (no movement at all, the default) | slide (held only along the face's normal, x/y/z: a roller, a smooth floor, a symmetry plane) | pin (dofs [\"x\",\"y\",\"z\"] held, the rest free) | move (move [dx,dy,dz] mm, null for free: a set displacement, a press fit). Adds to the holds (replace: true starts again; clear: true drops them). The query is kept, not the face numbers (they change when the part is edited): fea_solve matches it again and refuses if it finds nothing. Answers held (the faces picked, with area and centre): check them.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "faces": {
     "description": "Faces by query: { near: [x,y,z], radius }, { normal: [nx,ny,nz], x|y|z: plane, largest }, { faces: [\"Face3\"] }; or what shape_query answers — \"Face8\", \"Body.Face8\", a list of them, its items — or its filters ({ type: cylinder, radius: 3 }, { type: plane, normal, z }, …)"
    },
    "kind": {
     "type": "string",
     "enum": [
      "fixed",
      "slide",
      "pin",
      "move"
     ]
    },
    "dofs": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "move": {
     "type": "array",
     "items": {}
    },
    "replace": {
     "type": "boolean"
    },
    "clear": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "strength"
 },
 "fea_load": {
  "name": "fea_load",
  "description": "Load the part: force on faces (N; [fx, fy, fz] in total spread by area, or a number pushing into the faces), pressure on faces (MPa = N/mm², positive pushes in), gravity (true is 1 g down -z; a number of g; [gx, gy, gz] in g), or temperature (K the whole part warms by, against its holds; alpha 1/K, else the material's), or spin { rpm, axis [x,y,z], at [x,y,z] } (a rotor's own mass flung outward). One kind a call; faces as fea_hold takes them. Adds to the loads (replace: true starts again; clear: true drops them); an identical or zero load is refused. Answers on (the faces picked) and load.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "faces": {
     "description": "Faces by query: { near: [x,y,z], radius }, { normal: [nx,ny,nz], x|y|z: plane, largest }, { faces: [\"Face3\"] }; or what shape_query answers — \"Face8\", \"Body.Face8\", a list of them, its items — or its filters ({ type: cylinder, radius: 3 }, { type: plane, normal, z }, …)"
    },
    "force": {},
    "pressure": {
     "type": "number"
    },
    "gravity": {},
    "temperature": {
     "type": "number"
    },
    "alpha": {
     "type": "number"
    },
    "spin": {
     "type": "object"
    },
    "replace": {
     "type": "boolean"
    },
    "clear": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "strength"
 },
 "fea_solve": {
  "name": "fea_solve",
  "description": "Solve the study: as FreeCAD's own FEM analysis (CalculiX solver object, Gmsh mesh object, its constraints, results loaded into it; made anew each solve as \"<body> strength (fea_solve)\") where the study is one body, fixed holds, force/pressure/gravity, linear; else Agent Link's own CalculiX deck (solvedBy says which and why). Second-order tetrahedra, linear static; mm, N, MPa. Answers vonMisesMax { MPa, at, face } and displacementMax { mm, at, face }, safety (yield over the peak), mesh { nodes, elements }, warnings, files; health carries CalculiX's own warning lines. nonlinear: true follows large deflections and each material into yield (elasticOnly: true keeps it elastic) and answers the plastic strain. Runs in the foreground, FreeCAD waiting: seconds for a few thousand elements, minutes past 100,000 (timeout s, 300, bounds Gmsh and the own deck). A rigid hold makes stress no real mount does; a coarse mesh under-reads peaks; library figures are typical. Needs ccx and gmsh installed.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "timeout": {
     "type": "number"
    },
    "nonlinear": {
     "type": "boolean"
    },
    "elasticOnly": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "strength"
 },
 "fea_modes": {
  "name": "fea_modes",
  "description": "Natural frequencies of the study's body: the lowest count (6, up to 30) modes, held by the study's holds (none: free, its rigid motions left out). Answers each mode's Hz and where it swings most and which way. Keep what shakes the part well away from the lowest. Runs in the foreground; needs ccx and gmsh (timeout s, 300).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "count": {
     "type": "integer"
    },
    "timeout": {
     "type": "number"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "strength"
 },
 "fea_heat": {
  "name": "fea_heat",
  "description": "Steady heat through the study's body: temperatures [{ faces, celsius }] held, heat [{ faces, watts }] going in (one of the two at least), air { h W/(m²·K) (10, still air), celsius (25), faces (the rest) } taking it away — air: false for none. Answers the hottest and coolest place and warns when the part passes where its material softens (k from the card, or conductivity W/(m·K) here). Conduction and convection only. view_render map heat shows it. Runs in the foreground (timeout s, 300); needs ccx and gmsh.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "temperatures": {
     "type": "array",
     "items": {}
    },
    "heat": {
     "type": "array",
     "items": {}
    },
    "air": {},
    "conductivity": {
     "type": "number"
    },
    "timeout": {
     "type": "number"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "strength"
 },
 "fea_results": {
  "name": "fea_results",
  "description": "The last solve's answer again (kept with the session, not the file), with stale: true and staleWhy when the body or the study changed since. Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {},
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "strength"
 },
 "fea_clear": {
  "name": "fea_clear",
  "description": "Drop the strength study (body, material, holds, loads, refined regions) and its results. FEM analyses already made in the document stay.",
  "inputSchema": {
   "type": "object",
   "properties": {},
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "strength"
 },
 "fea_buckle": {
  "name": "fea_buckle",
  "description": "Linear buckling of the study (its holds and loads): the lowest count (3) buckling factors — the loads times the factor is where each mode buckles; under 1 it buckles as loaded — and where each bulges. Thin walls, columns, ribs under compression. Runs in the foreground; needs ccx and gmsh (timeout s, 300).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "count": {
     "type": "integer"
    },
    "timeout": {
     "type": "number"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "strength"
 },
 "fea_refine": {
  "name": "fea_refine",
  "description": "A finer mesh near faces (a fillet, a hole's edge, where the peak sits): faces (a query as fea_hold takes), size mm (under the study's mesh); clear: true drops every region. Kept in the study; the next solve uses it (by Agent Link's own deck).",
  "inputSchema": {
   "type": "object",
   "properties": {
    "faces": {},
    "size": {
     "type": "number"
    },
    "clear": {
     "type": "boolean"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "strength"
 },
 "fea_probe": {
  "name": "fea_probe",
  "description": "Read the last solve where asked: points [[x,y,z] …] (von Mises MPa and displacement mm there, from the nearest nodes; nearestNodeMm says how near), line { from, to, samples } (a profile along it; warns where it leaves the part), faces (a query as fea_hold takes: max, mean and where on them). Changes nothing.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "points": {
     "type": "array",
     "items": {}
    },
    "line": {
     "type": "object"
    },
    "faces": {}
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "strength"
 },
 "fea_chart": {
  "name": "fea_chart",
  "description": "The last solve as FreeCAD's FEM post-processing charts, headless: kind histogram (field over every node, bins 20: an SVG bar chart, the CSV of the bins, min, median, p95, p99, max) | line (along line { from, to, samples } mm: an SVG line plot and CSV) | table (points [[x,y,z] …] or a line: a CSV, and the rows in the answer when 25 or fewer). field vonMises (MPa, default) or displacement (mm). name, title. Files go to the out folder. Changes nothing in the document.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "kind": {
     "type": "string",
     "enum": [
      "histogram",
      "line",
      "table"
     ]
    },
    "field": {
     "type": "string",
     "enum": [
      "vonMises",
      "displacement"
     ]
    },
    "bins": {
     "type": "integer"
    },
    "line": {
     "type": "object"
    },
    "points": {
     "type": "array",
     "items": {}
    },
    "name": {
     "type": "string"
    },
    "title": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "strength"
 },
 "fea_export": {
  "name": "fea_export",
  "description": "Write the last solve to the out folder: formats [vtu (ParaView, FreeCAD FEM post-processing), csv (every node: position mm, von Mises MPa, displacement mm)] (both by default), name. Changes nothing in the document.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "formats": {
     "type": "array",
     "items": {
      "type": "string"
     }
    },
    "name": {
     "type": "string"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": false,
  "reads": {},
  "group": "strength"
 },
 "fea_native": {
  "name": "fea_native",
  "description": "Build the study as FreeCAD's own FEM analysis (Analysis, solver, material, Gmsh mesh, fixed / force / pressure / self-weight constraints), to open and run in the FEM workbench; it is not solved here (fea_solve does that), and skipped lists what the FEM objects could not take. solver elmer (multiphysics) takes equations [elasticity, heat, flow, electrostatic, electricforce, flux, staticcurrent, magnetodynamic, deformation (nonlinear elasticity)] together, temperatures [{ faces, celsius }] and heat [{ faces, watts }] for heat, potentials [{ faces, volts }] for electrostatics; with flow the body is the fluid's space (fluid air | water; inlets and walls are set in the FEM workbench); write: true meshes it and writes Elmer's case (case.sif), run: true solves it where ElmerSolver is installed.",
  "inputSchema": {
   "type": "object",
   "properties": {
    "name": {
     "type": "string"
    },
    "solver": {
     "type": "string",
     "enum": [
      "calculix",
      "elmer"
     ]
    },
    "equations": {
     "type": "array",
     "items": {
      "type": "string",
      "enum": [
       "elasticity",
       "deformation",
       "heat",
       "flow",
       "electrostatic",
       "electricforce",
       "flux",
       "staticcurrent",
       "magnetodynamic",
       "magnetodynamic2d"
      ]
     }
    },
    "temperatures": {
     "type": "array",
     "items": {
      "type": "object"
     }
    },
    "heat": {
     "type": "array",
     "items": {
      "type": "object"
     }
    },
    "potentials": {
     "type": "array",
     "items": {
      "type": "object"
     }
    },
    "fluid": {
     "type": "string",
     "enum": [
      "air",
      "water"
     ]
    },
    "write": {
     "type": "boolean"
    },
    "run": {
     "type": "boolean"
    },
    "timeout": {
     "type": "number"
    }
   },
   "required": [],
   "additionalProperties": false
  },
  "changes": true,
  "reads": {},
  "group": "strength"
 }
}
''')
