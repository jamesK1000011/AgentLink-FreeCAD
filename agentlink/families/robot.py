# SPDX-License-Identifier: LGPL-2.1-or-later
# FreeCAD's Robot workbench headless: a six-axis robot (KUKA models where
# this FreeCAD ships them, a kinematics file of your own, or the built-in
# Puma 560), moved by its axes or its tool point, trajectories of waypoints
# or along a shape's edges, a run of a trajectory checked for reach and the
# axes' ranges, and KUKA KRL out.

import os

import FreeCAD
import Robot  # noqa: F401 — the family stands on the Robot module; left out without it

from .. import paths
from .. import runners
from ..protocol import bad
from . import picks

GROUP = "robot"
INFO = "Robot: six-axis robots (KUKA models, your own kinematics), moves by axes or tool point, trajectories from waypoints or edges, reach checked along them, KUKA KRL out."

V = FreeCAD.Vector
MODELS = ("kr16", "kr125", "kr210", "kr500")


def lib_file(model, ext):
    """A KUKA model's file (csv: kinematics, wrl: its picture) in this FreeCAD's Robot library, or None when it ships none."""
    roots = []
    for base in (FreeCAD.getResourceDir(), FreeCAD.getHomePath(), os.path.join(FreeCAD.getHomePath(), "share")):
        roots += [os.path.join(base, "Mod", "Robot", "Lib", "Kuka"), os.path.join(base, "data", "Mod", "Robot", "Lib", "Kuka")]
    names = {"kr16": "kr16", "kr125": "kr125_3", "kr210": "kr210", "kr500": "kr500_1"}
    for r in roots:
        for stem in (names.get(model, model), model):
            f = os.path.join(r, f"{stem}.{ext}")
            if os.path.isfile(f):
                return f
    return None


def placement(a, what):
    """A placement from { at, ypr | axis + angle }: a robot's base, a tool, a tcp, a waypoint."""
    if not isinstance(a, dict):
        raise bad(f"{what}: {{ at: [x, y, z] mm, ypr: [yaw, pitch, roll] degrees }} (or axis and angle in place of ypr).")
    at = picks.vec3(a.get("at", [0, 0, 0]), f"{what}.at")
    if a.get("ypr") is not None:
        ypr = a["ypr"]
        if not (isinstance(ypr, list) and len(ypr) == 3 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in ypr)):
            raise bad(f"{what}.ypr: [yaw, pitch, roll] in degrees (about Z, then Y, then X).")
        y, p, r = (float(x) for x in ypr)
        rot = FreeCAD.Rotation(y, p, r)
    elif a.get("axis") is not None:
        rot = FreeCAD.Rotation(picks.direction(a["axis"], f"{what}.axis"), picks.num(a.get("angle", 0), f"{what}.angle"))
    else:
        rot = FreeCAD.Rotation()
    return FreeCAD.Placement(at, rot)


def pl_out(pl):
    """A placement as the tools answer it: at [x, y, z] and ypr [yaw, pitch, roll]."""
    y, p, r = pl.Rotation.toEuler()
    return {"at": [round(c, 3) for c in pl.Base], "ypr": [round(y, 3), round(p, 3), round(r, 3)]}


def axes_of(o):
    """A robot's six axis angles, degrees."""
    return [round(float(getattr(o, f"Axis{i}")), 3) for i in range(1, 7)]


def tools(session):
    """The robot tools are data (agentlink/data/tools.json, group "robot";
    run by agentlink/runners.py's steps runner): each entry has the tool's
    words, its checks with their refusals, the order of its steps and its
    answer. What is here is what those entries call by name
    (docs/data-tools.md)."""
    s = session
    doc = lambda: s.doc  # noqa: E731

    def robots():
        """The document's robots."""
        return [o for o in doc().Objects if o.isDerivedFrom("Robot::RobotObject")]

    def robot(ref):
        """The robot ref names, or the only one when ref is left out."""
        if not ref:
            rs = robots()
            if len(rs) == 1:
                return rs[0]
            raise bad("robot: which — " + (", ".join(o.Label for o in rs) or "there are none (robot_new)") + ".")
        o = picks.find(doc(), ref, "robot")
        if not o.isDerivedFrom("Robot::RobotObject"):
            raise bad(f"robot: {o.Label} is not a robot ({o.TypeId}) — " + (", ".join(x.Label for x in robots()) or "there are none (robot_new)") + ".")
        return o

    def trajectory(ref):
        """The trajectory object ref names."""
        o = picks.find(doc(), ref, "trajectory")
        if not hasattr(o, "Trajectory"):
            have = ", ".join(x.Label for x in doc().Objects if hasattr(x, "Trajectory")) or "there are none (robot_path makes one)"
            raise bad(f"trajectory: {o.Label} is not a trajectory ({o.TypeId}) — {have}.")
        return o

    def tool_of(o):
        """The robot's Tool frame (tool point from the flange); identity when unset."""
        t = getattr(o, "Tool", None)
        return t if isinstance(t, FreeCAD.Placement) and not t.isIdentity() else None

    def settle(o):
        """After Tcp was set: FreeCAD's solver moved the axes if it found a
        pose, and left them where they were if not — but the Tcp property
        keeps the value asked for either way. Setting an axis to itself makes
        FreeCAD work Tcp out again from the axes it really holds, so a miss
        shows."""
        o.Axis1 = float(o.Axis1)

    def state(o):
        """A robot as the tools answer it: robot, axes, tcp (the tool point; flange beside it when a tool is set), and FreeCAD's error when it has one."""
        t = tool_of(o)
        return {"robot": o.Label, "axes": axes_of(o), "tcp": pl_out(o.Tcp.multiply(t) if t else o.Tcp), **({"flange": pl_out(o.Tcp)} if t else {}),
                **({"error": o.Error} if getattr(o, "Error", "") else {})}

    def sweep(o, t, n):
        """A trajectory followed by a robot at n points by time, each solved
        by inverse kinematics from the one before, the tool point on the
        path: the lowest and highest angle each axis took, the points it
        missed (out of reach, past an axis limit, or not followed to) and
        the worst miss in mm. The robot's axes are left where the last
        point put them."""
        tr = t.Trajectory
        lows, highs, misses, worst = [1e9] * 6, [-1e9] * 6, [], 0.0
        base = t.Base if hasattr(t, "Base") else FreeCAD.Placement()
        tool = tool_of(o)
        for k in range(n):
            time = tr.Duration * k / (n - 1)
            point = base.multiply(tr.position(time))
            # The flange for this tool point, as FreeCAD's simulation takes it.
            want = point.multiply(tool.inverse()) if tool else point
            o.Error = ""
            o.Tcp = want
            settle(o)
            miss = (o.Tcp.Base - want.Base).Length
            worst = max(worst, miss)
            if miss > 0.1 or getattr(o, "Error", ""):
                misses.append({"t": round(time, 3), "at": [round(c, 2) for c in point.Base], "off_mm": round(miss, 3), **({"error": o.Error} if o.Error else {})})
            for i, v in enumerate(axes_of(o)):
                v = ((v + 180.0) % 360.0) - 180.0  # whole extra turns are the same pose
                lows[i], highs[i] = min(lows[i], v), max(highs[i], v)
        return lows, highs, misses, worst

    def posed(at, turn):
        """The placement a dress-up adds to every waypoint: moved by at, turned by [yaw, pitch, roll]."""
        y, p_, r = turn
        return FreeCAD.Placement(V(*at), FreeCAD.Rotation(y, p_, r))

    def krl(o, t, path, full):
        """A trajectory written as KUKA KRL by FreeCAD's exporter: its compact form, or the full one."""
        import KukaExporter

        (KukaExporter.ExportFullSub if full else KukaExporter.ExportCompactSub)(o, t, path)

    def read_text(path):
        """A written file's text."""
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def prop(o, name):
        """A property by a name worked out in the call (an axis by its number)."""
        return getattr(o, name)

    # What the tools' entries (agentlink/data/tools.json, group "robot") call by name.
    # FreeCAD's and Robot's own are reached when called, not here.
    helpers = {"doc": doc, "unique": lambda label, own=None: s.unique(label, own), "snapshot": lambda tool: s.snapshot(tool), "step": lambda: len(s.steps),
               "finish": lambda tool, read: picks.finish(s, tool, read), "settled": lambda tool, read: picks.finish(s, tool, read, recompute=False),
               "find": lambda ref: picks.find(doc(), ref), "resolve": lambda ref: picks.resolve(s, ref), "ref_list": picks.ref_list, "num": picks.num,
               "local": lambda p: paths.local(s, p), "made": lambda p: paths.made(s, p), "out_dir": lambda: s.out_dir, "isfile": lambda p: os.path.isfile(p),
               "isabs": lambda p: os.path.isabs(p), "join": lambda *parts: os.path.join(*parts), "basename": lambda p: os.path.basename(p),
               "dirname": lambda p: os.path.dirname(p), "make_folder": lambda p: os.makedirs(p, exist_ok=True), "read_text": read_text,
               # Robot's own
               "waypoint": lambda pl, kind, name: Robot.Waypoint(pl, kind, name), "trajectory_of": lambda points: Robot.Trajectory(points), "krl": krl,
               # the family's
               "robot": robot, "trajectory": trajectory, "tool_of": tool_of, "settle": settle, "state": state, "sweep": sweep, "posed": posed, "prop": prop,
               "placement": placement, "axes_of": axes_of, "lib_file": lib_file, "MODELS": MODELS}
    return runners.tools(GROUP, s, helpers)
