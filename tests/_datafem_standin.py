# SPDX-License-Identifier: LGPL-2.1-or-later
# The stand-in FreeCAD of tests/test_datafem_data.py: tests/_datapart_standin.py
# as it is, and on top of it what the material, FEM and strength tools reach
# (families/material.py, fem_more.py, strength.py): the Materials module's
# library, quantities with units, ObjectsFem's makers, FreeCAD's meshers and
# FemToolsCcx, a FEM mesh, face queries, and Gmsh and CalculiX as programs
# that write the files a case says they write. It is not FreeCAD and solves
# nothing: it is one fixed world on which the old handlers and the new data
# entries are run side by side. Nothing of the first stand-in is changed for
# its own test: this one is only ever installed in this test's child process.
import os
import types

LIBRARY = {
    "uuid-steel": {"Name": "Steel-S235", "Directory": "Standard/Metal/Steel", "LibraryName": "System", "Tags": ["structural"], "Description": "A plain structural steel.",
                   "URL": "https://example.org/steel", "Density": 7.85, "YoungsModulus": 210000.0, "PoissonRatio": 0.3, "YieldStrength": 235.0,
                   "UltimateTensileStrength": 360.0, "ThermalConductivity": 50.0},
    "uuid-pla": {"Name": "PLA", "Directory": "Standard/Thermoplast", "LibraryName": "System", "Tags": [], "Description": "", "Density": 1.24, "YoungsModulus": 3500.0},
    "uuid-alu": {"Name": "Aluminum-6061-T6", "Directory": "Standard/Metal/Aluminum", "LibraryName": "System", "Tags": ["light"], "Description": "An aluminium alloy.", "Density": 2.7,
                 "YoungsModulus": 69000.0, "YieldStrength": 276.0},
    "uuid-foam": {"Name": "Foam", "Directory": "Standard/Foam", "LibraryName": "System", "Tags": [], "Description": "No stiffness on the card.", "Density": 0.05},
    "uuid-look": {"Name": "Shiny", "Directory": "Appearance/Metal", "LibraryName": "System", "Tags": [], "Description": "", "Density": 1.0},
    "uuid-none": {"Name": "Nothing", "Directory": "Standard/Odd", "LibraryName": "System", "Tags": [], "Description": ""},
}
UNITS = {"N": "force", "kN": "force", "mN": "force", "MPa": "pressure", "kPa": "pressure", "Pa": "pressure", "mm": "length", "m": "length", "K": "temperature",
         "N/mm": "stiffness", "mm/s^2": "acceleration", "": ""}


def install():
    import sys

    import _datapart_standin

    fc = _datapart_standin.install()
    flag, log, show, trace, Shape, Obj, Vec, part = fc.flag, fc.log, fc.show, fc.trace, fc.Shape, fc.Obj, fc.Vec, fc.part
    Doc = type(fc.Session().doc)
    Doc.Meta = None  # the records are kept in the document's own hidden object (agentlink/store.py)
    Vec.__getitem__ = lambda self, i: (self.x, self.y, self.z)[i]
    Vec.multiply = lambda self, k: Vec(self.x * k, self.y * k, self.z * k)

    def fails(what):
        if what in flag("fail", ()):
            raise RuntimeError(f"{what}: it failed")

    # ---- quantities ------------------------------------------------------------------------

    class Unit:
        def __init__(self, name=""):
            self.name, self.Signature = name, UNITS[name]

        def __eq__(self, o):
            return isinstance(o, Unit) and o.Signature == self.Signature

        def __ne__(self, o):
            return not self == o

        def __repr__(self):
            return f"Unit({self.name})"

    class Quantity:
        def __init__(self, v=0.0, unit=None):
            if isinstance(v, str):
                num, _, name = v.strip().partition(" ")
                if name not in UNITS:
                    raise ValueError(f"syntax error in {v!r}")
                v, unit = float(num), Unit(name)  # a word that is no number: Python's own ValueError
            self.Value, self.Unit = float(v), unit or Unit()

        UserString = property(lambda self: f"{self.Value:g} {self.Unit.name}".strip())

        def getUserPreferred(self):
            return (self.UserString, 1.0, self.Unit.name)

        def getValueAs(self, unit):
            return self.Value

        def __mul__(self, k):
            return Quantity(self.Value * k, self.Unit)

        def __str__(self):
            return self.UserString

        def __repr__(self):
            return f"<{self.UserString}>"

    fc.fc.Units = types.SimpleNamespace(Quantity=Quantity, Unit=Unit)

    # ---- the material library --------------------------------------------------------------

    class Card:
        def __init__(self, uid, d):
            self.UUID, self.props = uid, {k: v for k, v in d.items() if k[0].isupper() and k not in ("Name", "Directory", "LibraryName", "Tags", "Description", "URL")}
            for k in ("Name", "Directory", "LibraryName", "Tags", "Description", "URL"):
                if k in d:
                    setattr(self, k, d[k])

        def hasPhysicalProperty(self, name):
            return name in self.props

        def getPhysicalValue(self, name):
            v = self.props[name]
            return v if name == "PoissonRatio" else Quantity(v)

        def __repr__(self):
            return f"<card {self.Name}>"

    class MaterialManager:
        def __init__(self):
            log("MaterialManager")
            fails("MaterialManager")

        @property
        def Materials(self):
            return {u: Card(u, d) for u, d in flag("library", LIBRARY).items()}

        def getMaterial(self, uid):
            log("getMaterial", uid)
            fails("getMaterial")
            return Card(uid, flag("library", LIBRARY)[uid])

    materials = fc.Module("Materials")
    materials.MaterialManager = MaterialManager

    # ---- a FEM mesh, and the objects of the FEM workbench ----------------------------------

    class FemMesh:
        """Four nodes a face, on a grid: enough for a case to say where the
        nodes are and which a face holds."""

        def __init__(self, nodes=0, volumes=0, groups=(), faces=0):
            self.NodeCount, self.VolumeCount, self.FaceCount, self.Groups = nodes, volumes, faces, tuple(groups)

        GroupCount = property(lambda self: len(self.Groups))

        @property
        def Nodes(self):
            return {i: Vec(*p) for i, p in flag("nodes", NODES).items()} if self.NodeCount else {}

        @property
        def Volumes(self):
            return list(flag("elems", ELEMS)) if self.VolumeCount else []

        def getElementNodes(self, e):
            return tuple(flag("elems", ELEMS)[e])

        def getNodeById(self, i):
            return Vec(*flag("nodes", NODES)[i])

        def removeGroup(self, g):
            log("removeGroup", g)
            self.Groups = tuple(x for x in self.Groups if x != g)

        def getNodesByFace(self, f):
            return list(flag("face_nodes", {}).get(f.tag.rsplit(".", 1)[-1], [1, 2, 3, 4]))

        def getNodesByEdge(self, e):
            name = e.tag.rsplit(".", 1)[-1]
            return list(flag("edge_nodes", {}).get(name, [int(name[4:]), int(name[4:]) + 1] if name[4:].isdigit() else [1, 2]))

        def getccxVolumesByFace(self, f):
            return [tuple(x) for x in flag("face_elems", {}).get(f.tag.rsplit(".", 1)[-1], [(1, 1)])]

        def writeABAQUS(self, path, *a):
            log("writeABAQUS", os.path.basename(path), *a)
            with open(path, "w") as fh:
                fh.write(flag("mesh_text", "*Node, NSET=Nall\n1, 0, 0, 0\n*Element, TYPE=C3D10, ELSET=Evolumes\n1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10\n"))

        def write(self, path):
            log("FemMesh.write", os.path.basename(path))
            with open(path, "w") as fh:
                fh.write("unv\n")

        def __repr__(self):
            return f"<FemMesh {self.NodeCount} nodes, {self.VolumeCount} volumes>"

    NODES = {i: (float(i % 3) * 5.0, float(i % 2) * 5.0, float(i)) for i in range(1, 11)}
    ELEMS = {1: (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)}

    # What each maker's object carries: its TypeId, and its properties as FreeCAD has them.
    def fem_object(doc, type_, name, **props):
        o = doc.addObject(type_, name)
        o.__dict__.update(props)
        return o

    def constraint(type_, **props):
        def make(doc, name=None, *more):
            log(make.fn, *([name] if isinstance(name, str) else []))
            fails(make.fn)
            return fem_object(doc, type_, name if isinstance(name, str) else type_.split("::")[-1], References=[], **{k: (v() if callable(v) else v) for k, v in props.items()})
        return make

    def on_a(what, type_, **props):
        """An object made on another (a refinement on a mesh, an equation on a solver, a nonlinear material on a material)."""
        def make(doc, base, name=None):
            log(make.fn, base)
            fails(make.fn)
            o = fem_object(doc, type_, name or type_.split("::")[-1], **props)
            if what == "mesh":
                base.__dict__["MeshRegionList"] = list(base.__dict__.get("MeshRegionList", [])) + [o]
            return o
        return make

    def make_analysis(doc, name="Analysis"):
        log("makeAnalysis", name)
        return fem_object(doc, "Fem::FemAnalysis", name, Group=[])

    def make_solver(type_name, **props):
        def make(doc, name=None):
            log(make.fn)
            return fem_object(doc, "Fem::FemSolverObjectPython", name or type_name, Proxy=types.SimpleNamespace(Type=f"Fem::{type_name}"), **props)
        return make

    def make_material(category):
        def make(doc, name="Material"):
            log(make.fn, name)
            return fem_object(doc, "App::MaterialObjectPython", name, Category=category, Material={}, References=[])
        return make

    def make_mesh(kind):
        def make(doc, name="Mesh"):
            log(make.fn, name)
            fails(make.fn)
            link = {"Part": None} if flag("old_mesh_link") else {"Shape": None}
            return fem_object(doc, "Fem::FemMeshObjectPython", name, Proxy=types.SimpleNamespace(Type=f"Fem::FemMesh{kind}"), FemMesh=FemMesh(), CharacteristicLengthMax=Quantity(0, Unit("mm")),
                              ElementOrder="1st", **link)
        return make

    def self_weight(doc, name="SelfWeight"):
        log("makeConstraintSelfWeight", name)
        props = {"Gravity_x": 0.0, "Gravity_y": 0.0, "Gravity_z": -1.0} if flag("old_gravity") else {"GravityAcceleration": Quantity(9806.65, Unit("mm/s^2")), "GravityDirection": Vec(0, 0, -1)}
        return fem_object(doc, "Fem::ConstraintSelfWeight", name, **props)

    objects_fem = fc.Module("ObjectsFem")
    makers = {
        "makeAnalysis": make_analysis, "makeConstraintSelfWeight": self_weight,
        "makeConstraintFixed": constraint("Fem::ConstraintFixed"), "makeConstraintForce": constraint("Fem::ConstraintForce", Force=lambda: Quantity(0, Unit("N")), Direction=None, Reversed=False),
        "makeConstraintPressure": constraint("Fem::ConstraintPressure", Pressure=lambda: Quantity(0, Unit("MPa"))),
        "makeConstraintDisplacement": constraint("Fem::ConstraintDisplacement", xFree=True, xDisplacement=lambda: Quantity(0, Unit("mm")), Offset=lambda: Vec(0, 0, 0), Scale=1.0, Mode="Free"),
        "makeConstraintSpring": constraint("Fem::ConstraintSpring", NormalStiffness=lambda: Quantity(0, Unit("N/mm")), ElmerStiffness="Normal-Tangential"),
        "makeConstraintTemperature": constraint("Fem::ConstraintTemperature", Temperature=lambda: Quantity(300, Unit("K")), ConstraintType="Temperature"),
        "makeConstraintInitialTemperature": constraint("Fem::ConstraintInitialTemperature", initialTemperature=lambda: Quantity(300, Unit("K"))),
        "makeConstraintHeatflux": constraint("Fem::ConstraintHeatflux", ConstraintType="Convection", DFlux=0.0),
        "makeConstraintElectrostaticPotential": constraint("Fem::ConstraintElectrostaticPotential", Potential=0.0, PotentialEnabled=False),
        "makeConstraintTie": constraint("Fem::ConstraintTie", Tolerance=lambda: Quantity(0, Unit("mm"))),
        "makeConstraintContact": constraint("Fem::ConstraintContact", Friction=0.0),
        "makeConstraintCentrif": constraint("Fem::ConstraintCentrif", RotationFrequency=0.0),
        "makeConstantVacuumPermittivity": lambda doc, name=None: (log("makeConstantVacuumPermittivity"), fem_object(doc, "Fem::ConstantVacuumPermittivity", "VacuumPermittivity", VacuumPermittivity=8.854e-12))[1],
        "makeMaterialSolid": make_material("Solid"), "makeMaterialFluid": make_material("Fluid"),
        "makeMaterialMechanicalNonlinear": on_a("material", "Fem::MaterialMechanicalNonlinear", YieldPoints=["235, 0"], MaterialModelNonlinearity="isotropic hardening"),
        "makeSolverCalculiXCcxTools": make_solver("SolverCcxTools", AnalysisType="static", GeometricalNonlinearity="linear"),
        "makeSolverCalculiX": make_solver("SolverCalculiX", AnalysisType="static"),
        "makeSolverElmer": make_solver("SolverElmer", WorkingDirectory=""), "makeSolverZ88": make_solver("SolverZ88"),
        "makeEquationHeat": on_a("solver", "Fem::EquationElmerHeat", Priority=0), "makeEquationElasticity": on_a("solver", "Fem::EquationElmerElasticity", Priority=0),
        "makeEquationFlow": on_a("solver", "Fem::EquationElmerFlow", Priority=0), "makeEquationElectrostatic": on_a("solver", "Fem::EquationElmerElectrostatic", Priority=0),
        "makeMeshRegion": on_a("mesh", "Fem::MeshRegion", CharacteristicLength=Quantity(0, Unit("mm")), References=[]),
        "makeMeshGroup": on_a("mesh", "Fem::MeshGroup", UseLabel=False, References=[]),
        "makeMeshGmsh": make_mesh("Gmsh"), "makeMeshNetgen": make_mesh("Netgen"),
    }
    for k, fn in makers.items():
        fn.fn = k
        setattr(objects_fem, k, fn)

    first_enums = Obj.__dict__.get("getEnumerationsOfProperty")
    Obj.getEnumerationsOfProperty = lambda self, prop: list(flag("enums", {}).get(prop, [])) if first_enums is None else first_enums(self, prop)
    first_get = Obj.__getattr__

    def get_(self, k):
        if k == "PropertiesList":  # FreeCAD's FEM has properties that start small (xFree, initialTemperature)
            return first_get(self, k) + [p for p in self.__dict__ if p in ("xFree", "xDisplacement", "initialTemperature")]
        return first_get(self, k)

    Obj.__getattr__ = get_
    first_set = Obj.__setattr__

    def set_(self, k, v):
        if k in flag("refuses", ()):  # a property FreeCAD will not take that value for
            was = self.__dict__.get(k)
            first_set(self, k, v)
            self.__dict__[k] = was
            raise ValueError(f"{v!r} is not part of the enumeration")
        first_set(self, k, v)

    Obj.__setattr__ = set_

    # FreeCAD's meshers: a case says how many nodes and volumes come back, and what they print.
    class Mesher:
        name = "Gmsh"

        def __init__(self, mesh):
            self.mesh = mesh

        def _mesh(self):
            log(f"{self.name} meshes", self.mesh)
            fails(self.name)
            self.mesh.__dict__["FemMesh"] = FemMesh(flag("nodes_made", 10), flag("volumes_made", 1))
            return flag("mesher_said", "")

        def create_mesh(self):
            return self._mesh()

    class NetgenTools(Mesher):
        name = "Netgen"

        def __init__(self, mesh):
            fails("NetgenTools")
            self.mesh = mesh

        def run(self):
            return self._mesh()

        create_mesh = property(lambda self: (_ for _ in ()).throw(AttributeError("create_mesh")))

    class FemToolsCcx:
        def __init__(self, analysis, solver):
            log("FemToolsCcx", analysis, solver)
            self.analysis, self.ccx_stdout, self.ccx_stderr = analysis, "", ""

        def update_objects(self):
            log("update_objects")

        def setup_working_dir(self, wd):
            log("setup_working_dir", os.path.basename(wd))
            self.wd = wd

        def setup_ccx(self, ccx_binary=None, ccx_binary_sig="CalculiX"):
            log("setup_ccx", ccx_binary, ccx_binary_sig)

        def check_prerequisites(self):
            return flag("prerequisites", "")

        def write_inp_file(self):
            log("write_inp_file")
            fails("write_inp_file")
            self.inp_file_name = os.path.join(self.wd, "FEMMeshGmsh.inp")
            with open(self.inp_file_name, "w") as fh:
                fh.write("FreeCAD's deck\n")

        def ccx_run(self):
            self.setup_ccx()
            log("ccx_run")
            self.ccx_stdout = flag("ccx_out", "Job finished\n")
            if not flag("no_frd"):
                with open(os.path.splitext(self.inp_file_name)[0] + ".frd", "w") as fh:
                    fh.write("frd\n")
            return flag("ccx_exit", 0)

        def load_results(self):
            log("load_results")
            fails("load_results")
            mesh = state_doc().addObject("Fem::FemMeshObject", "ResultMesh")
            res = state_doc().addObject("Fem::FemResultObjectPython", "CCX_Results")
            res.__dict__.update(kinds=("Fem::FemResultObject",), Mesh=mesh)
            self.analysis.addObject(res)

    def state_doc():
        return fc.state["doc"]

    def femmesh_2_mesh(femmesh, result=None):
        log("femmesh_2_mesh", femmesh, result)
        return [[(0, 0, 0), (1, 0, 0), (0, 1, 0)]] * flag("facets", 12)

    class PlainMesh:
        def __init__(self, facets):
            self.CountFacets = len(facets)

        def __repr__(self):
            return f"<mesh of {self.CountFacets}>"

    def fem_read(path):
        log("Fem.read", os.path.basename(path))
        return FemMesh(flag("nodes_made", 10), flag("volumes_made", 1), faces=flag("faces_made", 8))

    fem = fc.Module("Fem")
    fem.read = fem_read
    femtools, femmesh, femsolver, elmer = fc.Module("femtools"), fc.Module("femmesh"), fc.Module("femsolver"), fc.Module("femsolver.elmer")
    ccxtools, membertools, gmshtools, netgentools = fc.Module("femtools.ccxtools"), fc.Module("femtools.membertools"), fc.Module("femmesh.gmshtools"), fc.Module("femmesh.netgentools")
    f2m, writer, meshmod = fc.Module("femmesh.femmesh2mesh"), fc.Module("femsolver.elmer.writer"), fc.Module("Mesh")
    ccxtools.FemToolsCcx, gmshtools.GmshTools, netgentools.NetgenTools, f2m.femmesh_2_mesh, meshmod.Mesh = FemToolsCcx, Mesher, NetgenTools, femmesh_2_mesh, PlainMesh
    femtools.ccxtools, femtools.membertools, femmesh.gmshtools, femmesh.netgentools, femmesh.femmesh2mesh, femsolver.elmer, elmer.writer = ccxtools, membertools, gmshtools, netgentools, f2m, elmer, writer

    class Writer:
        def __init__(self, solver, wd, testmode=False):
            log("elmer Writer", solver, os.path.basename(wd), testmode)
            self.wd = wd

        def write_solver_input(self):
            fails("elmer writer")
            with open(os.path.join(self.wd, "case.sif"), "w") as fh:
                fh.write("case\n")

    writer.Writer = Writer
    mods = {"Materials": materials, "ObjectsFem": objects_fem, "Fem": fem, "femtools": femtools, "femtools.ccxtools": ccxtools, "femtools.membertools": membertools, "femmesh": femmesh,
            "femmesh.gmshtools": gmshtools, "femmesh.netgentools": netgentools, "femmesh.femmesh2mesh": f2m, "femsolver": femsolver, "femsolver.elmer": elmer,
            "femsolver.elmer.writer": writer, "Mesh": meshmod}
    sys.modules.update(mods)

    # The post-processing filter along a line, and a result object, as a case gives them.
    first_add = Doc.addObject

    def add_object(self, type_, name):
        o = first_add(self, type_, name)
        if type_ == "Fem::FemPostDataAlongLineFilter":
            o.__dict__.update(XAxisData=[], YAxisData=[], computes_line=True)
        return o

    first_recompute = Doc.recompute

    def recompute(self, objs=None):
        fails("recompute")
        first_recompute(self, objs)
        for o in self.Objects:
            if o.__dict__.get("computes_line"):
                ys = list(flag("line_values", [10.0, 20.0, 30.0, 20.0, 10.0]))
                o.__dict__.update(YAxisData=ys, XAxisData=[float(i) for i in range(len(ys))])

    Doc.addObject, Doc.recompute = add_object, recompute

    # ---- faces by query, and the programs ---------------------------------------------------

    from agentlink import ccx_io, facepick, hooks
    from agentlink.protocol import ToolError

    def pick(shape, q, what="faces", names=()):
        """The faces a query names here: "Face2", ["Face1", "Face2"], { faces: [...] }; every other query picks what the case says (flags["picks"], Face1 else)."""
        if isinstance(q, str):
            got = [q.rsplit(".", 1)[-1]]
        elif isinstance(q, list):
            got = [str(x).rsplit(".", 1)[-1] for x in q]
        elif isinstance(q, dict) and "faces" in q:
            got = list(q["faces"]) if isinstance(q["faces"], list) else [q["faces"]]
        elif isinstance(q, dict):
            got = list(flag("picks", ["Face1"]))
        else:
            raise ToolError("invalid_input", f"{what}: a face query.")
        faces = shape.Faces
        if not got or any(not (n.startswith("Face") and n[4:].isdigit() and 1 <= int(n[4:]) <= len(faces)) for n in got):
            raise ToolError("not_found", f"{what}: no face matches {q!r}.")
        return [(n, faces[int(n[4:]) - 1]) for n in got]

    def normal_of(f):
        n = flag("normals", {}).get(f.tag.rsplit(".", 1)[-1])
        return Vec(*n) if n is not None else Vec(f.normal)

    facepick.pick, facepick.outward_normal = pick, normal_of
    facepick.describe = lambda name, f: {"face": name, "area": round(f.Area, 2)}
    Shape.exportBrep = lambda self, path: (log("exportBrep", os.path.basename(path)), open(path, "w").write("brep\n"))[0]

    def is_inside(self, p, tol, on):
        """Which solid a point is in: below flags["split_z"] the first, above it the second; every point in the first without it."""
        if flag("split_z") is None:
            return not flag("outside")
        return (p.z < flag("split_z")) == self.tag.endswith("Solid1")

    Shape.isInside = is_inside
    first_dist = Shape.distToShape

    def dist_to_shape(self, o):
        if self.ShapeType == "Solid" and self.tag.rsplit(".", 1)[-1] in flag("apart", ()):  # a solid no held face touches
            return (5.0, [], [])
        return first_dist(self, o)

    Shape.distToShape = dist_to_shape
    first_common = Shape.common

    def common(self, other):
        if self.ShapeType == "Face":  # two faces that lie on each other: the area a case says
            return Shape("shared face", "Face", self.box.lo, self.box.hi, area=flag("shared_area", 25.0), faces=1, solids=0, shells=0)
        if flag("overlap") is not None:
            return Shape("overlap", "Solid", self.box.lo, self.box.hi, volume=flag("overlap"))
        return first_common(self, other)

    Shape.common = common

    def make_shell(faces):
        log("makeShell", [f.tag for f in faces])
        return Shape(f"shell of {len(faces)}", "Shell", faces[0].box.lo, faces[0].box.hi, area=sum(f.Area for f in faces), faces=len(faces), edges=3 * len(faces) + 1, closed=False, solids=0)

    part.makeShell = make_shell
    box_type = type(Shape().BoundBox)
    box_type.intersect = lambda self, o: self.gap(o) <= 1e-9
    box_type.isInside = lambda self, p: True
    vertex_type = part.Vertex
    vertex_type.distToShape = lambda self, sh: (flag("node_gap", 0.0), [], [])

    ccx_io.find_binary = lambda name, group, key, env: None if name in flag("no_binary", ()) else f"/opt/bin/{name}"

    def read_mesh(text):
        return ({i: tuple(p) for i, p in flag("nodes", NODES).items()}, {} if flag("no_tets") else dict(flag("elems", ELEMS)))

    def read_frd(text):
        if flag("no_results"):
            return {}, {}
        nodes = flag("nodes", NODES)
        peak = flag("peak", 40.0)
        return ({n: (0.01 * n * flag("moves", 1.0), 0.0, 0.0) for n in nodes}, {n: (peak * n / len(nodes), 0.0, 0.0, 0.0, 0.0, 0.0) for n in nodes})

    def read_frd_blocks(text, name):
        if name == "PE":
            return [{n: (flag("plastic", 0.0),) for n in flag("nodes", NODES)}]
        return [{n: (0.0, 0.1 * n, 0.0) for n in flag("nodes", NODES)} for _ in range(flag("shapes", 12))]

    ccx_io.read_mesh, ccx_io.read_frd, ccx_io.read_frd_blocks = read_mesh, read_frd, read_frd_blocks
    ccx_io.read_frequencies = lambda dat: [(i + 1, hz) for i, hz in enumerate(flag("freqs", [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 120.5, 340.25, 610.0, 900.0, 1200.0, 1500.0]))]
    ccx_io.read_buckling = lambda dat: [(i + 1, f) for i, f in enumerate(flag("factors", [4.2, 7.9, 12.0]))]
    ccx_io.read_temperatures = lambda frd: {} if flag("no_results") else {n: flag("coolest", 25.0) + (flag("hottest", 80.0) - flag("coolest", 25.0)) * (n - 1) / 9 for n in flag("nodes", NODES)}
    for name in ("deck", "deck_modes", "deck_heat", "parts_deck", "nodal_loads", "vtu"):
        real = getattr(ccx_io, name)

        def logged(*a, _name=name, _real=real, **kw):
            log(_name, *[x for x in a if not isinstance(x, str) or len(x) < 40], **kw)
            if _name == "nodal_loads":
                return {1: list(a[3])}, 100.0
            if _name == "vtu":
                return "<VTKFile/>\n"
            return f"*{_name}\n" + ("*STEP\n*STATIC\n*EL FILE\nS\n" if _name == "deck" else "") + ("*MATERIAL, NAME=PART\n*ELASTIC\n1, 0.3\n" if _name == "deck" else "")
        setattr(ccx_io, name, logged)

    import subprocess

    def run(cmd, cwd=None, capture_output=False, text=False, timeout=None, env=None):
        """Gmsh and CalculiX: each writes what it would (or not, as the case says) and prints the case's lines."""
        prog = os.path.basename(cmd[0])
        log("run", prog, *cmd[1:], timeout=timeout)
        if prog in flag("slow", ()):
            raise subprocess.TimeoutExpired(cmd, timeout)
        out, err, code = "", "", 0
        if prog == "gmsh":
            stem = cmd[2].rsplit(".", 1)[0]
            if flag("gmsh_fails"):
                err, code = "Error: could not mesh surface 3\nError: no elements\n", 1
            else:
                with open(os.path.join(cwd, stem + ".unv"), "w") as fh:
                    fh.write("unv\n")
        elif prog == "ccx":
            out = flag("ccx_out", "Job finished\n")
            if not flag("no_frd"):
                with open(os.path.join(cwd, "job.frd"), "w") as fh:
                    fh.write("frd\n")
                with open(os.path.join(cwd, "job.dat"), "w") as fh:
                    fh.write("dat\n")
        elif prog == "ElmerGrid":
            code, err = (1, "ElmerGrid: bad mesh") if flag("grid_fails") else (0, "")
        elif prog == "ElmerSolver":
            out = flag("elmer_out", "ALL DONE\n")
            code = flag("elmer_exit", 0)
            with open(os.path.join(cwd, "case.vtu"), "w") as fh:
                fh.write("vtu\n")
        return types.SimpleNamespace(returncode=code, stdout=out, stderr=err)

    subprocess.run = run

    import time

    time.time = lambda: 1000.0  # seconds: 0.0 in every answer

    def reset(*modules):
        """Before each run: no add-on's services, the library read afresh, the case's flags only."""
        hooks._SERVICES.clear()
        for m in modules:
            getattr(m, "_cache", {}).clear()

    fc.reset, fc.Quantity, fc.Unit, fc.FemMesh, fc.LIBRARY, fc.hooks, fc.objects_fem, fc.fem_object, fc.Card = reset, Quantity, Unit, FemMesh, LIBRARY, hooks, objects_fem, fem_object, Card
    return fc
