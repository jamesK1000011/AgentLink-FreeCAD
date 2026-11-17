# SPDX-License-Identifier: LGPL-2.1-or-later
# CAM's remaining commands, headless: path objects (area, from a shape, path
# from edges, compound, array), program flow (stop, fixture offset, custom
# G-code), the property bag, and the job template export; Draft's dimension
# flip and heal; Assembly's rigid groups and a new empty part. The ops CAM
# makes like any other (3D pocket, tapping, mill facing, probe, flute) are
# cam_op kinds.
#
# The six tools are entries in agentlink/data/tools.json (docs/data-tools.md):
# their checks with the refusals' words, the order of their steps and their
# answers are there. What is here is what the entries call by name: the
# finders, and the small functions that know FreeCAD's CAM, Draft and
# Assembly modules (which module a proxy class is in, what a job template
# gathers, which document Draft heals).

import importlib
import json
import os

import FreeCAD

from .. import paths
from .. import runners
from ..protocol import ToolError
from . import picks

GROUP = "cam_more"
INFO = "CAM paths from areas and shapes, compound, array, stop, fixture offsets, property bags, job templates."

BAG_KINDS = ("Float", "Length", "Distance", "Angle", "Integer", "String", "Bool", "Percent", "Speed")  # the property types a bag takes


def has_cam():
    """Whether this build has FreeCAD's CAM workbench (its Path module)."""
    try:
        import Path  # noqa: F401

        return True
    except ImportError:
        return False


def from_module(module, name=None):
    """A module of a FreeCAD workbench by its dotted name ("Path.Main.Job"),
    or one name out of it as `from module import name` takes it — a class
    ("Path.Op.Gui.Stop", "Stop") or a module of the package ("Path.Base",
    "PropertyBag"). ImportError where this FreeCAD has none."""
    mod = importlib.import_module(module)
    if name is None:
        return mod
    if hasattr(mod, name):
        return getattr(mod, name)
    try:
        return importlib.import_module(f"{module}.{name}")
    except ImportError:
        raise ImportError(f"cannot import name {name!r} from {module!r}") from None


def proxied(cls, o, *more):
    """A FreeCAD Python proxy class put on a new object (what gives a
    Path::FeaturePython its properties and its path)."""
    cls(o, *more)


def gcode(o):
    """An object's path as G-code lines ([] for one with no path)."""
    p = getattr(o, "Path", None)
    return [c.toGCode() for c in p.Commands] if p is not None else []


def setprop(o, prop, value):
    """A property set by its name (the caller's own props, a bag's named values)."""
    setattr(o, prop, value)


def write_template(path, enc):
    """A job template written as FreeCAD's own export writes it (JSON, keys sorted), its folder made first."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as fp:
        json.dump(enc, fp, sort_keys=True, indent=2)


def has_rigid_groups():
    """Whether this FreeCAD's Assembly has rigid group joints (from 1.2)."""
    import JointObject

    return hasattr(JointObject, "RigidGroupJoint")


def rigid_group(joint, parts):
    """Assembly's own rigid group joint put on a new object of the joint group, over parts."""
    import JointObject

    JointObject.RigidGroupJoint(joint, parts)


def tools(s):
    def d():
        if s.doc is None:
            raise ToolError("invalid_state", "No document open: doc_new first.")
        return s.doc

    def job_of(ref):
        from .cam import _job

        return _job(d(), ref)

    def draft_ready():
        """Draft loaded and this document the active one: Draft's heal works on the active document."""
        import Draft  # noqa: F401

        if FreeCAD.ActiveDocument is not d():
            FreeCAD.setActiveDocument(d().Name)

    def heal(targets):
        """Draft's heal: old Draft objects rebuilt as new copies (None: every one that needs it)."""
        import Draft

        Draft.heal(targets)

    def assembly(ref):
        from .assembly import _assembly

        return _assembly(d(), ref)

    def joints(asm):
        from .assembly import _joints

        return _joints(asm)

    def part_of(asm, ref):
        from .assembly import _part

        return _part(asm, ref)

    # What the tools' entries (agentlink/data/tools.json) call by name.
    helpers = {"doc": d, "job_of": job_of, "find": lambda ref, what="object": picks.find(d(), ref, what), "shaped": lambda ref, what: picks.shaped(d(), ref, what),
               "resolve": lambda ref: picks.resolve(s, ref), "unique": lambda label, *own: s.unique(label, *own), "snapshot": s.snapshot,
               "placed": picks.placed, "placement": picks.placement, "made": lambda p: paths.made(s, p), "out_dir": lambda: s.out_dir,
               "fc_version": lambda: ".".join(FreeCAD.Version()[:3]), "V": lambda *xyz: FreeCAD.Vector(*xyz),
               "join": os.path.join, "dirname": os.path.dirname, "basename": os.path.basename, "expanduser": os.path.expanduser, "getsize": os.path.getsize,
               # FreeCAD's CAM, Draft and Assembly
               "has_cam": has_cam, "from_module": from_module, "proxied": proxied, "gcode": gcode, "setprop": setprop, "BAG_KINDS": BAG_KINDS,
               "write_template": write_template, "draft_ready": draft_ready, "heal": heal, "assembly": assembly, "joints": joints, "part_of": part_of,
               "has_rigid_groups": has_rigid_groups, "rigid_group": rigid_group}
    return runners.tools(GROUP, s, helpers)
