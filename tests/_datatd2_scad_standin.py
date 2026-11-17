# SPDX-License-Identifier: LGPL-2.1-or-later
# The stand-in of tests/test_datatd2_data.py for families/openscad.py:
# tests/_datapart2_standin.py as it is, and on top of it FreeCAD's OpenSCAD
# workbench as far as the scad_ tools reach: the preference that names the
# OpenSCAD program and the program's answer to -v, OpenSCADUtils (code to a
# CSG file, hull and Minkowski through the program), the CSG reader and
# writer, and ply. Nothing of the first stand-in is changed for its own
# test: this one is only ever installed in this test's child process.
import os
import subprocess
import sys
import types


def install():
    import _datapart2_standin

    fc = _datapart2_standin.install()
    flag, trace, state, show, F = fc.flag, fc.trace, fc.state, fc.show, fc.fc

    def doc():
        return state["doc"]

    def log(text):
        trace.append(text)

    # ---- the OpenSCAD program: where the preference says it is, and what it says to -v --------

    def params(path):
        def get(key, default=""):
            return flag("openscad", "") if key == "openscadexecutable" else default

        return types.SimpleNamespace(GetBool=lambda *a: False, GetInt=lambda *a: 0, GetFloat=lambda *a: 0.0, GetString=get,
                                     SetString=lambda k, v: log(f"preference {k} = {os.path.basename(v)!r}"))

    F.ParamGet = params
    F.setActiveDocument = lambda name: log(f"setActiveDocument({name!r})")
    real_run = subprocess.run

    def run(cmd, *a, **kw):
        if not (isinstance(cmd, list) and cmd[1:] == ["-v"]):
            return real_run(cmd, *a, **kw)
        log(f"{os.path.basename(cmd[0])} -v")
        how = flag("version", "stderr")
        if how == "timeout":
            raise subprocess.TimeoutExpired(cmd, 20)
        if how == "raises":
            raise OSError("Exec format error")
        return types.SimpleNamespace(stdout="OpenSCAD 2021.01\n" if how == "stdout" else "", stderr="OpenSCAD version 2021.01\n" if how == "stderr" else "")

    subprocess.run = run

    # ---- FreeCAD's OpenSCAD modules ---------------------------------------------------------------

    def code_to_csg(code, kind):
        log(f"callopenscadstring({code!r}, {kind!r}) GuiUp={F.GuiUp}")
        how = flag("code")
        if how == "raises":
            raise RuntimeError("ERROR: Parser error in line 1: syntax error")
        if how == "nothing":
            return None
        p = os.path.join(state["tmp"], "from_code.csg")
        if how != "gone":
            with open(p, "w", encoding="utf-8") as f:
                f.write("cube();\n")
        return p

    def via_program(d, objs, op):
        log(f"process_ObjectsViaOpenSCAD({show(objs)}, {op!r}) GuiUp={F.GuiUp}")
        how = flag("program")
        if how == "raises":
            raise RuntimeError("CGAL error in nef polyhedron")
        if how == "nothing":
            return None
        return d.new("Part::Feature", op, Shape=fc.Shape(f"{op} by OpenSCAD", "Compound", (0, 0, 0), (9, 9, 9), solids=0, faces=5) if how == "flat" else fc.solid(f"{op} by OpenSCAD", (0, 0, 0), (12, 12, 12), 1500.0))

    utils = types.ModuleType("OpenSCADUtils")
    utils.callopenscadstring, utils.process_ObjectsViaOpenSCAD, utils.searchforopenscadexe = code_to_csg, via_program, lambda: 1 / 0

    reader = types.ModuleType("importCSG")
    reader.original_root_objects, reader.gui, reader.printverbose = [], True, True

    def insert(path, docname):
        log(f"importCSG.insert({os.path.basename(path)!r}, {docname!r}) GuiUp={F.GuiUp} gui={reader.gui}")
        reader.original_root_objects.append("something")
        how = flag("csg")
        if how == "raises":
            raise ValueError("Syntax error in CSG file")
        if how == "silent":
            raise KeyError()
        if how == "nothing":
            return
        d = doc()
        cube = d.new("Part::Box", "cube", Shape=fc.solid("cube", (0, 0, 0), (10, 10, 10), 1000.0))
        ball = d.new("Part::Sphere", "sphere", Shape=fc.solid("sphere", (0, 0, 0), (6, 6, 6), 113.097))
        top = d.new("Part::Cut", "difference", Shape=fc.solid("difference", (0, 0, 0), (10, 10, 10), 886.903))
        cube.InList.append(top)
        ball.InList.append(top)
        if how == "two":
            d.new("Mesh::Feature", "hull")
        if flag("views"):
            for o in (cube, ball, top):
                o.__dict__["ViewObject"] = fc.View(o.Name)

    reader.insert = insert

    writer = types.ModuleType("exportCSG")
    writer.gui = True

    def export(objs, path):
        log(f"exportCSG.export({show(objs)}, {os.path.basename(path)!r}) GuiUp={F.GuiUp} gui={writer.gui}")
        if flag("export") == "raises":
            raise RuntimeError("no such feature in CSG")
        with open(path, "w", encoding="utf-8") as f:
            f.write("".join(f"// {o.Label}\ncube([10, 10, 10]);\n" for o in objs) + "polyhedron(points=[]);\n" * flag("polyhedra", 0))

    writer.export = export
    mine = {"OpenSCADUtils": utils, "importCSG": reader, "exportCSG": writer, "ply": types.ModuleType("ply")}
    sys.modules.update(mine)

    def fresh():
        """As at the start: the window down, the reader's list empty, a folder of its own for what OpenSCAD writes."""
        import tempfile

        F.GuiUp = False
        del reader.original_root_objects[:]
        state["tmp"] = tempfile.mkdtemp()

    fresh()

    # A shape's triangles for the hull made here: its box's eight corners.
    def tessellate(self, tol):
        b = self.box
        return [fc.Vec(x, y, z) for x in (b.XMin, b.XMax) for y in (b.YMin, b.YMax) for z in (b.ZMin, b.ZMax)], []

    fc.Shape.tessellate = tessellate
    fc.fresh = fresh
    return fc
