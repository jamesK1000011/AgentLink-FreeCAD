# SPDX-License-Identifier: LGPL-2.1-or-later
# The rest of FreeCAD's FEM workbench, headless: any boundary condition,
# material, element, equation, solver or mesh refinement FEM has, added to an
# analysis by kind on faces, edges or solids picked by name or by query; a
# Netgen mesh; a FEM mesh back to a plain mesh; clearing mesh groups; and the
# stress linearization through a wall (membrane and bending) from a result.

import FreeCAD

from .. import facepick
from .. import runners
from ..protocol import ToolError, bad
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


def objects_fem():
    """FreeCAD's ObjectsFem (the makers of every FEM object), or None where
    the FEM workbench is not in this build."""
    try:
        import ObjectsFem

        return ObjectsFem
    except ImportError:
        return None


def analyses(doc):
    """The document's FEM analyses."""
    return [o for o in doc.Objects if o.TypeId == "Fem::FemAnalysis" or o.isDerivedFrom("Fem::FemAnalysis")]


def ref_parts(x):
    """A reference in its parts: ("Body", "Solid2", True) for a solid (the
    shared readers know faces, edges and vertices only), else picks.split_ref's
    (head, sub) and False."""
    import re

    m = re.match(r"^(.*)\.(Solid\d+)$", str(x))
    if m:
        return m.group(1), m.group(2), True
    head, sub = picks.split_ref(x)
    return head, sub, False


def face_names(o, queries):
    """The names of the faces a query or a list of queries picks on an
    object (facepick's), each once, in the order picked."""
    qs = queries or {}
    qs = qs if isinstance(qs, list) else [qs]
    return tuple(dict.fromkeys(n for q in qs for n, _ in facepick.pick(o.Shape, q, "refs.faces")))


def set_props(o, props):
    """FreeCAD properties set on a FEM object from props, each as its kind
    takes it: a quantity with its unit (a bare number is refused for one,
    since FreeCAD keeps force in mN and pressure in kPa), a vector from a
    list. A name the object lacks and a value FreeCAD will not take are
    refused here, in these words."""
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


def settable(o):
    """The properties of a FEM object a call can set through props (its own,
    not FreeCAD's bookkeeping)."""
    return [p for p in o.PropertiesList if p[0].isupper() and p not in ("Label", "Label2", "Proxy", "ExpressionEngine", "Visibility", "References", "Placement", "Shape")]


def recompute_quietly(doc):
    """A recompute after a Netgen mesh object is made (before FreeCAD 1.1 it
    meshed there), and Netgen's tools loaded: neither is this tool's failure."""
    try:
        doc.recompute()
        from femmesh import netgentools  # noqa: F401
    except Exception:
        pass


def netgen_run(m):
    """Netgen run to the end on a mesh object, bounded (300 s): what it said.
    FreeCAD 1.1 runs Netgen as a separate process and reads the mesh in when
    it ends: run() alone returns at once, with nothing meshed yet."""
    import Fem  # noqa: F401
    from femtools import membertools  # noqa: F401
    import femmesh.netgentools as NT

    from . import strength as S

    return S.gmsh_run(NT.NetgenTools(m), 300.0, "Netgen", "a coarser mesh (props) or a longer timeout")


def surface_maker():
    """FreeCAD's femmesh_2_mesh: a FEM mesh's outside as facets (deformed by a result)."""
    from femmesh.femmesh2mesh import femmesh_2_mesh

    return femmesh_2_mesh


def fem_surface(femmesh, result=None):
    """A FEM mesh's outside as facets, deformed by a result when one is given."""
    return surface_maker()(femmesh, result) if result is not None else surface_maker()(femmesh)


def mesh_module():
    """FreeCAD's Mesh module."""
    import Mesh

    return Mesh


def nearest_samples(src, fm, vals, p0, p1, n):
    """A CalculiX result object read along a line: (distances, values, the
    furthest a sample lay from its node), the nearest node per sample."""
    L = (p1 - p0).Length
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
    return xs, ys, far


def membrane_bending(xs, ys, L):
    """(thickness, membrane, bending, peak) of values along a wall. Membrane:
    the mean; bending: the linear part by least squares, its slope × half the
    thickness, at the surfaces. ASME VIII-2 linearizes each stress component
    and takes the equivalent after; linearizing von Mises itself is the
    quicker, rougher reading, and the answer says so."""
    T = xs[-1] - xs[0] or L
    h = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
    mem = sum((ys[i] + ys[i + 1]) / 2 * h[i] for i in range(len(h))) / T
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (sum((x - mx) ** 2 for x in xs) or 1)
    return T, mem, slope * T / 2, max(abs(y) for y in ys)


def tools(s):
    """The fem_more tools are data (agentlink/data/tools.json, group
    "fem_more"): what their entries call by name is here (docs/data-tools.md)."""
    def d():
        """The open document; refused when there is none."""
        if s.doc is None:
            raise ToolError("invalid_state", "No document open: doc_new first.")
        return s.doc

    # FreeCAD's own are reached when called, not here.
    helpers = {"doc": d, "unique": lambda label, own=None: s.unique(label, own), "snapshot": lambda tool: s.snapshot(tool),
               "find": lambda ref, what="object": picks.find(d(), ref, what), "shaped": lambda ref, what="body": picks.shaped(d(), ref, what),
               "element": picks.element, "one_of": picks.one_of, "point": lambda v, name: FreeCAD.Vector(*picks.vec3(v, name)),
               "freecad_version": lambda: FreeCAD.Version(), "is_seq": lambda v: isinstance(v, (list, tuple)),
               # the family's
               "KINDS": KINDS, "objects_fem": objects_fem, "analyses": lambda: analyses(d()), "ref_parts": ref_parts, "face_names": face_names, "set_props": set_props,
               "settable": settable, "shown": _show, "recompute_quietly": lambda: recompute_quietly(d()), "netgen_run": netgen_run, "surface_maker": surface_maker, "fem_surface": fem_surface,
               "mesh_module": mesh_module, "nearest_samples": nearest_samples, "membrane_bending": membrane_bending}
    return runners.tools(GROUP, s, helpers)


def _show(v):
    """A property's value as an answer shows it: a quantity as text with its
    unit, a vector as [x, y, z], a list's first ten, an object by its label."""
    if isinstance(v, FreeCAD.Units.Quantity):
        return str(v)
    if isinstance(v, FreeCAD.Vector):
        return [round(v.x, 6), round(v.y, 6), round(v.z, 6)]
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [_show(x) for x in v][:10]
    return getattr(v, "Label", str(v))[:80]

