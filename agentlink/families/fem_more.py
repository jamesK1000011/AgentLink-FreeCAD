# SPDX-License-Identifier: LGPL-2.1-or-later
# The rest of FreeCAD's FEM workbench, headless: any boundary condition,
# material, element, equation, solver or mesh refinement FEM has, added to an
# analysis by kind on faces, edges or solids picked by name or by query; a
# Netgen mesh; a FEM mesh back to a plain mesh; clearing mesh groups; and the
# stress linearization through a wall (membrane and bending) from a result.

import FreeCAD

from .. import facepick
from ..protocol import Tool, ToolError, bad
from ..tools import obj
from . import picks

GROUP = "fem_more"
INFO = "FEM: every boundary condition, material, element, equation, solver and mesh refinement by kind; Netgen meshes, FEM mesh to mesh, mesh groups cleared; stress linearization."

# kind → (ObjectsFem factory, what it needs: None | "mesh" | "solver")
KINDS = {
    # boundary conditions
    "bearing": ("makeConstraintBearing", None),
    "body_heat_source": ("makeConstraintBodyHeatSource", None),
    "current_density": ("makeConstraintCurrentDensity", None),
    "electric_charge_density": ("makeConstraintElectricChargeDensity", None),
    "electromagnetic": ("makeConstraintElectromagnetic", None),
    "electrostatic_potential": ("makeConstraintElectrostaticPotential", None),
    "flow_velocity": ("makeConstraintFlowVelocity", None),
    "fluid_boundary": ("makeConstraintFluidBoundary", None),
    "gear": ("makeConstraintGear", None),
    "initial_flow_velocity": ("makeConstraintInitialFlowVelocity", None),
    "initial_pressure": ("makeConstraintInitialPressure", None),
    "initial_temperature": ("makeConstraintInitialTemperature", None),
    "magnetization": ("makeConstraintMagnetization", None),
    "plane_rotation": ("makeConstraintPlaneRotation", None),
    "pulley": ("makeConstraintPulley", None),
    "rigid_body": ("makeConstraintRigidBody", None),
    "section_print": ("makeConstraintSectionPrint", None),
    "spring": ("makeConstraintSpring", None),
    "transform": ("makeConstraintTransform", None),
    "centrifugal": ("makeConstraintCentrif", None),
    "contact": ("makeConstraintContact", None),
    "tie": ("makeConstraintTie", None),
    "displacement": ("makeConstraintDisplacement", None),
    "heatflux": ("makeConstraintHeatflux", None),
    "temperature": ("makeConstraintTemperature", None),
    "vacuum_permittivity": ("makeConstantVacuumPermittivity", None),
    # elements and materials
    "fluid_1d": ("makeElementFluid1D", None),
    "rotation_1d": ("makeElementRotation1D", None),
    "geometry_1d": ("makeElementGeometry1D", None),
    "geometry_2d": ("makeElementGeometry2D", None),
    "material_fluid": ("makeMaterialFluid", None),
    "material_reinforced": ("makeMaterialReinforced", None),
    "material_nonlinear": ("makeMaterialMechanicalNonlinear", "material"),
    # solvers and equations
    "solver_mystran": ("makeSolverMystran", None),
    "solver_z88": ("makeSolverZ88", None),
    "solver_elmer": ("makeSolverElmer", None),
    "solver_calculix": ("makeSolverCalculiX", None),
    "eq_magnetodynamic2d": ("makeEquationMagnetodynamic2D", "solver"),
    "eq_magnetodynamic": ("makeEquationMagnetodynamic", "solver"),
    "eq_electrostatic": ("makeEquationElectrostatic", "solver"),
    "eq_heat": ("makeEquationHeat", "solver"),
    "eq_flow": ("makeEquationFlow", "solver"),
    "eq_elasticity": ("makeEquationElasticity", "solver"),
    # mesh refinements (on a Gmsh mesh)
    "mesh_region": ("makeMeshRegion", "mesh"),
    "mesh_boundary_layer": ("makeMeshBoundaryLayer", "mesh"),
    "mesh_group": ("makeMeshGroup", "mesh"),
    "mesh_distance": ("makeMeshDistance", "mesh"),
    "mesh_manipulate": ("makeMeshManipulate", "mesh"),
    "mesh_advanced": ("makeMeshAdvanced", "mesh"),
    "mesh_shape": ("makeMeshShape", "mesh"),
    "mesh_transfinite_curve": ("makeMeshTransfiniteCurve", "mesh"),
    "mesh_transfinite_surface": ("makeMeshTransfiniteSurface", "mesh"),
    "mesh_transfinite_volume": ("makeMeshTransfiniteVolume", "mesh"),
}


def _fem():
    try:
        import ObjectsFem

        return ObjectsFem
    except ImportError:
        raise ToolError("unavailable", "FreeCAD's FEM workbench is not in this build.")


def tools(s):
    def d():
        if s.doc is None:
            raise ToolError("invalid_state", "No document open: doc_new first.")
        return s.doc

    def analysis(ref):
        ans = [o for o in d().Objects if o.TypeId == "Fem::FemAnalysis" or o.isDerivedFrom("Fem::FemAnalysis")]
        return picks.one_of(ans, ref, "analysis: which — {labels}.", "analysis {ref}: they are {labels}.",
                            none="No FEM analysis: fea_native makes one (or kind solver_* with a new analysis: true).")

    def refs_of(a):
        """refs: ["Body.Face3", …], or { body, faces: [queries as facepick takes] }."""
        out = {}
        r = a.get("refs")
        if not r:
            return []
        if isinstance(r, dict):
            o = picks.shaped(d(), r.get("body"), "refs.body")
            qs = r.get("faces") or {}
            qs = qs if isinstance(qs, list) else [qs]
            names = list(dict.fromkeys(n for q in qs for n, _ in facepick.pick(o.Shape, q, "refs.faces")))
            return [(o, tuple(names))]
        import re

        for x in r:
            m = re.match(r"^(.*)\.(Solid\d+)$", str(x))
            if m:
                head, sub = m.group(1), m.group(2)
                o = picks.shaped(d(), head)
                if not 1 <= int(sub[5:]) <= len(o.Shape.Solids):
                    raise bad(f"{x}: {o.Label} has {len(o.Shape.Solids)} solids.")
                out.setdefault(o.Name, (o, []))[1].append(sub)
                continue
            head, sub = picks.split_ref(x)
            if head is None or sub is None:
                raise bad(f"refs: \"Body.Face3\" (or .Edge, .Vertex, .Solid), not {x!r}.")
            o = picks.shaped(d(), head)
            picks.element(o.Shape, sub, o.Label)
            out.setdefault(o.Name, (o, []))[1].append(sub)
        return [(o, tuple(v)) for o, v in out.values()]

    def set_props(o, props):
        for k, v in (props or {}).items():
            if k not in o.PropertiesList:
                raise bad(f"props.{k}: {o.Label} has no such property — it has {', '.join(p for p in o.PropertiesList if p[0].isupper())[:600]}.")
            try:
                cur = getattr(o, k)
                if isinstance(cur, FreeCAD.Units.Quantity):
                    # A bare number went in FreeCAD's internal units (force in
                    # mN, pressure in kPa): 1000 x off with nothing said. A
                    # quantity takes its unit with it.
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        if not cur.Unit.Signature or float(v) == 0:
                            v = FreeCAD.Units.Quantity(float(v), cur.Unit)
                        else:
                            raise bad(f"props.{k}: a value with its unit, as text — e.g. \"{v} {cur.getUserPreferred()[2] if hasattr(cur, 'getUserPreferred') else ''}\" (now {cur.UserString}).")
                    elif isinstance(v, str):
                        q = FreeCAD.Units.Quantity(v)
                        if q.Unit != cur.Unit and q.Unit.Signature:
                            raise bad(f"props.{k}: {v!r} is not in a unit of {cur.UserString!r}.")
                        v = q if q.Unit.Signature else FreeCAD.Units.Quantity(q.Value, cur.Unit)
                elif isinstance(cur, FreeCAD.Vector) and isinstance(v, (list, tuple)):
                    v = FreeCAD.Vector(*v)
                setattr(o, k, v)
            except Exception as e:
                raise bad(f"props.{k} = {v!r}: FreeCAD refuses it ({e}) — now {_show(getattr(o, k))!r}; a value of that kind (an enumeration takes one of its own words).")

    def fem_add(a):
        F = _fem()
        kind = picks.choice(a, "kind", KINDS, "kind: " + ", ".join(KINDS) + ".")
        fn, need = KINDS[kind]
        if not hasattr(F, fn):
            raise ToolError("unavailable", f"{kind} is not in FreeCAD {'.'.join(FreeCAD.Version()[:3])}'s FEM.")
        if a.get("new") and kind.startswith("solver_"):
            an = F.makeAnalysis(d(), "Analysis")
            an.Label = s.unique(a.get("name") or "Analysis", an)
        else:
            an = analysis(a.get("analysis"))
        if need == "mesh":
            m = picks.find(d(), a["mesh"], "mesh") if a.get("mesh") else next((x for x in an.Group if hasattr(x, "FemMesh") and "Gmsh" in x.TypeId + getattr(getattr(x, "Proxy", None), "Type", "")), None)
            if m is None:
                m = next((x for x in an.Group if hasattr(x, "FemMesh")), None)
            if m is None:
                raise ToolError("not_found", f"{an.Label} has no mesh to refine: fea_native makes the analysis a Gmsh mesh, or mesh: its label.")
            o = getattr(F, fn)(d(), m)
        elif need == "solver":
            sv = picks.find(d(), a["solver"], "solver") if a.get("solver") else next((x for x in an.Group if "Elmer" in getattr(getattr(x, "Proxy", None), "Type", "") or "Elmer" in x.Label), None)
            if sv is None:
                raise ToolError("not_found", f"{an.Label} has no Elmer solver for equations: fem_add {{ kind: \"solver_elmer\" }} first, or solver: its label.")
            o = getattr(F, fn)(d(), sv)
        elif need == "material":
            mat = picks.find(d(), a["material"], "material") if a.get("material") else next((x for x in an.Group if x.TypeId == "App::MaterialObjectPython" and getattr(x, "Category", "Solid") == "Solid"), None)
            if mat is None:
                raise ToolError("not_found", f"{an.Label} has no solid material for a nonlinear model to extend: fea_native gives the analysis one, or material: its label.")
            o = getattr(F, fn)(d(), mat)
            an.addObject(o)
        else:
            o = getattr(F, fn)(d())
            an.addObject(o)
        rf = refs_of(a)
        if rf:
            if not hasattr(o, "References"):
                raise bad(f"refs: {kind} takes no references (it applies to the whole analysis) — leave refs out.")
            o.References = rf
        set_props(o, a.get("props"))
        if a.get("name"):
            o.Label = s.unique(a["name"], o)
        d().recompute()
        s.snapshot("fem_add")
        out = {"added": o.Label, "kind": kind, "analysis": an.Label, "type": o.TypeId}
        if rf:
            out["refs"] = [f"{x.Label}.{n}" for x, ns in rf for n in ns]
        settable = [p for p in o.PropertiesList if p[0].isupper() and p not in ("Label", "Label2", "Proxy", "ExpressionEngine", "Visibility", "References", "Placement", "Shape")]
        out["props"] = {p: _show(getattr(o, p)) for p in settable[:30]}
        return out

    def fem_mesh(a):
        F = _fem()
        act = a.get("action")
        if act == "netgen":
            b = picks.shaped(d(), a.get("body"), "body")
            an = analysis(a.get("analysis")) if a.get("analysis") or any(o.TypeId == "Fem::FemAnalysis" for o in d().Objects) else None
            m = F.makeMeshNetgen(d(), "MeshNetgen")
            m.Shape = b
            set_props(m, a.get("props"))
            if an is not None:
                an.addObject(m)
            try:
                d().recompute()
                from femmesh import netgentools  # noqa: F401
            except Exception:
                pass
            nodes = m.FemMesh.NodeCount if m.FemMesh is not None else 0
            if not nodes:
                try:
                    import Fem  # noqa: F401
                    from femtools import membertools  # noqa: F401
                    import femmesh.netgentools as NT

                    from . import strength as S

                    # FreeCAD 1.1 runs Netgen as a separate process and reads
                    # the mesh in when it ends: run() alone returns at once,
                    # with nothing meshed yet.
                    said = S.gmsh_run(NT.NetgenTools(m), 300.0, "Netgen", "a coarser mesh (props) or a longer timeout")
                    nodes = m.FemMesh.NodeCount
                    if not nodes:
                        raise RuntimeError(" | ".join([ln.strip() for ln in said.splitlines() if ln.strip()][-2:])[:400] or "no mesh came back")
                except ToolError:
                    raise
                except Exception as e:
                    d().removeObject(m.Name)
                    raise ToolError("unavailable", f"Netgen did not mesh here ({e}): it needs Netgen installed with this FreeCAD's Python. fea_native makes a Gmsh mesh instead.")
            s.snapshot("fem_mesh")
            return {"mesh": m.Label, "nodes": nodes, "volumes": m.FemMesh.VolumeCount}
        m = picks.find(d(), a.get("mesh"), "mesh")
        if not hasattr(m, "FemMesh"):
            raise bad(f"{m.Label} is not a FEM mesh.")
        if act == "to_mesh":
            from femmesh.femmesh2mesh import femmesh_2_mesh

            res = picks.find(d(), a["result"], "result") if a.get("result") else None
            out_mesh = femmesh_2_mesh(m.FemMesh, res) if res is not None else femmesh_2_mesh(m.FemMesh)
            import Mesh

            o = d().addObject("Mesh::Feature", "Mesh")
            o.Mesh = Mesh.Mesh(out_mesh)
            o.Label = s.unique(a.get("name") or f"{m.Label} surface", o)
            d().recompute()
            s.snapshot("fem_mesh")
            return {"mesh": o.Label, "facets": o.Mesh.CountFacets, **({"deformed": res.Label} if res is not None else {})}
        if act == "clear_groups":
            fm = m.FemMesh
            ids = list(fm.Groups)
            for g in ids:
                fm.removeGroup(g)
            m.FemMesh = fm
            s.snapshot("fem_mesh")
            return {"mesh": m.Label, "cleared": len(ids), "groups": fm.GroupCount}
        raise bad("action: netgen { body, props } | to_mesh { mesh, result } | clear_groups { mesh }.")

    def fem_linearize(a):
        """Membrane and bending stress through a wall: von Mises (or a
        component) along a line from one face to the other, linearized as
        it stands. ASME VIII-2 linearizes each stress component and takes
        the equivalent after; linearizing von Mises itself is the quicker,
        rougher reading, and the answer says so."""
        src = picks.find(d(), a.get("result"), "result")
        p0 = FreeCAD.Vector(*picks.vec3(a.get("from"), "from"))
        p1 = FreeCAD.Vector(*picks.vec3(a.get("to"), "to"))
        n = int(a.get("points", 41))
        L = (p1 - p0).Length
        if L <= 0 or n < 5:
            raise bad("from and to: the line through the wall, apart; points 5 or more.")
        field = a.get("field", "von Mises Stress")
        if src.isDerivedFrom("Fem::FemPostPipeline"):
            f = d().addObject("Fem::FemPostDataAlongLineFilter", "Linearized")
            src.addObject(f) if hasattr(src, "addObject") else None
            f.Point1, f.Point2, f.Resolution = p0, p1, n - 1
            f.PlotData = field
            d().recompute()
            xs = list(f.XAxisData)
            ys = list(f.YAxisData)
            if not ys:
                raise ToolError("failed", f"No {field!r} along the line: inside the part, through the wall; field names are the pipeline's.")
        elif hasattr(src, "vonMises") and hasattr(src, "Mesh"):
            # A CalculiX result object: nearest node per sample.
            fm = src.Mesh.FemMesh
            if field.lower().startswith("von"):
                vals = list(src.vonMises)
            elif field in src.PropertiesList and isinstance(getattr(src, field), (list, tuple)):
                vals = list(getattr(src, field))
            else:
                have = [p for p in src.PropertiesList if p.startswith(("NodeStress", "Principal", "MaxShear", "vonMises", "Temperature", "Peeq"))]
                raise bad(f"field {field!r}: not a list of values on {src.Label} — one of {', '.join(have)}.")
            if not vals:
                raise ToolError("invalid_state", f"{src.Label} holds no {field} values: the solve wrote none (fea_solve again).")
            ids = list(src.NodeNumbers)
            pos = {i: fm.getNodeById(i) for i in ids}
            xs, ys, far = [], [], 0.0
            for k in range(n):
                t = k / (n - 1)
                q = p0 + (p1 - p0) * t
                j = min(range(len(ids)), key=lambda m: (pos[ids[m]] - q).Length)
                far = max(far, (pos[ids[j]] - q).Length)
                xs.append(t * L)
                ys.append(vals[j])
            # Nearest node with no limit read stresses for a line that left
            # the part: refuse once a sample is further from any node than a
            # fair share of the wall.
            if far > max(0.5, 0.25 * L):
                raise ToolError("invalid_input", f"The line runs {far:.2f} mm from any node of the mesh: it leaves the part. from and to go across the wall, on its two faces.")
        else:
            raise bad(f"result {src.Label}: not a FEM result — a CalculiX result object (CCX_Results in the analysis fea_solve makes) or a post pipeline.")
        # Membrane: the mean; bending: the linear part, at the surfaces.
        T = xs[-1] - xs[0] or L
        h = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
        mem = sum((ys[i] + ys[i + 1]) / 2 * h[i] for i in range(len(h))) / T
        # the linear part by least squares: its slope × half the thickness
        mx = sum(xs) / len(xs)
        my = sum(ys) / len(ys)
        slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sum((x - mx) ** 2 for x in xs) or 1)
        bend = slope * T / 2
        peak = max(abs(y) for y in ys)
        return {"result": src.Label, "field": field, "thickness": round(T, 4), "membrane": round(mem, 4), "bending": round(abs(bend), 4),
                "membranePlusBending": round(abs(mem) + abs(bend), 4), "peak": round(peak, 4), "points": len(ys),
                "note": "Stress linearization along the line (membrane = mean, bending from the first moment) of the field as given — for von Mises a rough reading: ASME VIII-2 linearizes each component and takes the equivalent after (field: a component, then combine). Compare with the code's allowables; FEA is a feasibility check, not a sign-off."}

    st = {"type": "string"}
    return [
        Tool("fem_add", "Add one of FEM's other objects to an analysis (fixed / force / pressure / self-weight, the material and Gmsh mesh: fea_native): kind (" + ", ".join(KINDS) + "; refused where this FreeCAD lacks it); refs [\"Body.Face3\", …] or { body, faces: [queries] }; props { its FreeCAD properties: a quantity as text with its unit, \"2 MPa\", \"100 N\", \"1000 N/mm\" — a bare number is refused for a quantity, since FreeCAD keeps them in mN and kPa } — the answer lists them; mesh / solver / material where a refinement, equation or nonlinear material needs one; new: true makes a new analysis for a solver.",
             obj({"kind": {"type": "string", "enum": list(KINDS)}, "analysis": st, "refs": {}, "props": {"type": "object"}, "mesh": st, "solver": st, "material": st, "new": {"type": "boolean"}, "name": st}, ["kind"]), fem_add, changes=True),
        Tool("fem_mesh", "FEM meshes: action netgen { body, props } (Netgen's mesh; refused where Netgen is not installed) | to_mesh { mesh, result, name } (the FEM mesh's outside as a plain mesh, deformed by a result) | clear_groups { mesh } (its groups removed).",
             obj({"action": {"type": "string", "enum": ["netgen", "to_mesh", "clear_groups"]}, "body": st, "mesh": st, "result": st, "analysis": st, "props": {"type": "object"}, "name": st}, ["action"]), fem_mesh, changes=True),
        Tool("fem_linearize", "Stress linearization through a wall from a FEM result (a CalculiX result object, CCX_Results after fea_solve, or a post pipeline): from and to [x,y,z] mm on the wall's two faces, points (41), field (von Mises by default; NodeStressXX …) → membrane, bending, membrane + bending, peak (MPa). A line that leaves the part is refused.",
             obj({"result": st, "from": {"type": "array", "items": {"type": "number"}}, "to": {"type": "array", "items": {"type": "number"}}, "points": {"type": "integer"}, "field": st}, ["result", "from", "to"]), fem_linearize, changes=True),
    ]


def _show(v):
    if isinstance(v, FreeCAD.Units.Quantity):
        return str(v)
    if isinstance(v, FreeCAD.Vector):
        return [round(v.x, 6), round(v.y, 6), round(v.z, 6)]
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [_show(x) for x in v][:10]
    return getattr(v, "Label", str(v))[:80]

