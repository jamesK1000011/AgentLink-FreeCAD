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
from ..protocol import Tool, ToolError, bad
from ..tools import obj
from . import picks

GROUP = "robot"
INFO = "Robot: six-axis robots (KUKA models, your own kinematics), moves by axes or tool point, trajectories from waypoints or edges, reach checked along them, KUKA KRL out."

V = FreeCAD.Vector
MODELS = ("kr16", "kr125", "kr210", "kr500")


def lib_file(model, ext):
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
    y, p, r = pl.Rotation.toEuler()
    return {"at": [round(c, 3) for c in pl.Base], "ypr": [round(y, 3), round(p, 3), round(r, 3)]}


def axes_of(o):
    return [round(float(getattr(o, f"Axis{i}")), 3) for i in range(1, 7)]


def tools(session):
    s = session
    doc = lambda: s.doc  # noqa: E731

    def robots():
        return [o for o in doc().Objects if o.isDerivedFrom("Robot::RobotObject")]

    def robot(ref):
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
        t = tool_of(o)
        return {"robot": o.Label, "axes": axes_of(o), "tcp": pl_out(o.Tcp.multiply(t) if t else o.Tcp), **({"flange": pl_out(o.Tcp)} if t else {}),
                **({"error": o.Error} if getattr(o, "Error", "") else {})}

    def robot_new(a):
        model = a.get("model", "kr16")
        kin = a.get("kinematics")
        if not kin and model not in MODELS and model != "puma":
            raise bad(f"model: {', '.join(MODELS)} (KUKA files, where this FreeCAD ships them) or puma (FreeCAD's built-in default robot); or kinematics, a CSV of your own.")
        if kin:
            kin = paths.local(s, kin) if isinstance(kin, str) else kin
            if not isinstance(kin, str) or not os.path.isfile(kin):
                raise ToolError("not_found", f"kinematics: {kin} — no such file. A CSV: one header line, then six lines (axis 1 … 6) of a, alpha, d, theta, rotDir, maxAngle, minAngle, velocity (Denavit-Hartenberg, mm and degrees).")
        o = doc().addObject("Robot::RobotObject", "Robot")
        o.Label = s.unique(a.get("name") or f"Robot {model}", o)
        how = None
        if kin:
            o.RobotKinematicFile = kin
            how = f"kinematics from {os.path.basename(kin)}"
        elif model in MODELS:
            f = lib_file(model, "csv")
            if f:
                o.RobotKinematicFile = f
                w = lib_file(model, "wrl")
                if w:
                    o.RobotVrmlFile = w
                how = f"KUKA {model.upper()} (FreeCAD's library)"
        if how is None:
            # With no kinematics file FreeCAD's robot is its built-in default,
            # a KUKA IR 500 (Robot6Axis.cpp), whatever the model asked for.
            if not a.get("name"):
                o.Label = s.unique("Robot (FreeCAD default)", o)
            how = "FreeCAD's built-in default robot (a KUKA IR 500: about 2.8 m reach)" + ("" if model == "puma" else f" — this FreeCAD ships no {model.upper()} file; give kinematics for the real one")
        if a.get("at") is not None or a.get("ypr") is not None:
            o.Base = placement(a, "robot")
        if a.get("tool") is not None:
            # the tool's point from the flange (a gripper's fingertips, a torch's tip)
            o.Tool = placement(a["tool"], "tool")
        # A new robot's Tcp is worked out only when an axis is set (RobotObject::onChanged):
        # until then it reads [0, 0, 0], not where the tool point is at the home pose.
        settle(o)
        return picks.finish(s, "robot_new", lambda: {**state(o), "model": how})

    def robot_move(a):
        o = robot(a.get("robot"))
        if sum(1 for k in ("axes", "tcp") if a.get(k) is not None) + (1 if a.get("home") else 0) > 1:
            raise bad("axes, tcp or home: one of them a call.")
        if a.get("axes") is not None:
            ax = a["axes"]
            if not (isinstance(ax, list) and len(ax) == 6 and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in ax)):
                raise bad("axes: six angles in degrees, axis 1 … 6.")
            for i, v in enumerate(ax, start=1):
                setattr(o, f"Axis{i}", float(v))
        elif a.get("tcp") is not None:
            o.Error = ""
            want = placement(a["tcp"], "tcp")
            t = tool_of(o)
            # tcp is the tool's point: the flange goes where that puts it
            # (as FreeCAD's own simulation does: position × Tool⁻¹).
            o.Tcp = want.multiply(t.inverse()) if t else want
            # the solver can answer whole extra turns (16439°): the same pose, each axis within ±180°
            for i in range(1, 7):
                v = float(getattr(o, f"Axis{i}"))
                setattr(o, f"Axis{i}", ((v + 180.0) % 360.0) - 180.0)
        elif a.get("home"):
            # The home pose the person set (Robot's Set home position), else all axes at 0.
            home = [float(v) for v in (getattr(o, "Home", None) or [])]
            for i in range(1, 7):
                setattr(o, f"Axis{i}", home[i - 1] if len(home) == 6 else 0.0)
        else:
            raise bad("axes [six degrees], tcp { at, ypr | axis + angle }, or home: true.")
        doc().recompute()
        out = state(o)
        if a.get("tcp") is not None:
            got = o.Tcp.multiply(t) if t else o.Tcp
            miss = (got.Base - want.Base).Length
            out["reached"] = miss < 0.1 and not getattr(o, "Error", "")
            if not out["reached"]:
                out["off_mm"] = round(miss, 3)
                out["note"] = "Not reached: the axes are as they were. Out of the arm's reach or past an axis limit, or the solver did not get there from this pose (100 steps): move in smaller steps, or set axes near the pose first."
        return picks.finish(s, "robot_move", lambda: {**out}, recompute=False)

    def robot_path(a):
        name = a.get("name") or "Trajectory"
        if a.get("edges"):
            refs = {}
            for r in picks.ref_list(a["edges"]):
                label, sub, _ = picks.resolve(s, r)
                x = picks.find(doc(), label)
                if sub and not sub.startswith("Edge"):
                    raise bad(f"edges: {label}.{sub} is not an edge — \"{label}.Edge3\", or \"{label}\" for all its edges (shape_query {{ kind: \"edge\" }} lists them).")
                subs = [sub] if sub else [f"Edge{i + 1}" for i in range(len(x.Shape.Edges))]
                refs.setdefault(x, []).extend(subs)
            if len(refs) != 1:
                raise bad("edges: of one object (FreeCAD's edge trajectory follows one shape): part_compound joins several first.")
            # FreeCAD's type is Robot::Edge2TracObject (Edge2TracObject.cpp);
            # the longer name is tried after it, for a build that has that.
            o = None
            for tid in ("Robot::Edge2TracObject", "Robot::Edge2TrajectoryObject"):
                try:
                    o = doc().addObject(tid, "Edge2Trajectory")
                    break
                except Exception:  # noqa: BLE001 - not this build's name for it
                    continue
            if o is None:
                raise ToolError("unavailable", "This FreeCAD's Robot module has no edge trajectory (Robot::Edge2TracObject): give waypoints instead.")
            o.Source = next(iter(refs.items()))
            o.SegValue = float(a.get("deviation", 0.5))
            o.UseRotation = bool(a.get("useRotation", False))
        else:
            wps = a.get("waypoints") or []
            if not isinstance(wps, list) or not all(isinstance(w, dict) for w in wps):
                raise bad("waypoints: a list of { at: [x,y,z], ypr: [yaw, pitch, roll], type, speed, cont }.")
            if len(wps) < 2:
                raise bad("waypoints: two or more { at, ypr, type LIN | PTP | CIRC, speed mm/s, cont } — or edges, a shape's edges to follow.")
            pts = []
            for i, w in enumerate(wps):
                kind = str(w.get("type", "LIN")).upper()
                if kind not in ("LIN", "PTP", "CIRC", "WAIT"):
                    raise bad(f"waypoints.{i}.type: LIN, PTP, CIRC or WAIT.")
                wp = Robot.Waypoint(placement(w, f"waypoints.{i}"), kind, w.get("name") or "Pt")
                wp.Velocity = picks.number(w, "speed", 1000, gt=0, msg=f"waypoints.{i}.speed: mm/s, above 0 (1000 by default).")
                wp.Cont = bool(w.get("cont", False))
                pts.append(wp)
            o = doc().addObject("Robot::TrajectoryObject", "Trajectory")
            o.Trajectory = Robot.Trajectory(pts)
        o.Label = s.unique(name, o)
        doc().recompute()
        tr = o.Trajectory
        return picks.finish(s, "robot_path", lambda: {"trajectory": o.Label, "waypoints": len(tr.Waypoints), "length": round(tr.Length, 2), "seconds": round(tr.Duration, 3)}, recompute=False)

    def robot_run(a):
        o = robot(a.get("robot"))
        t = trajectory(a.get("trajectory"))
        tr = t.Trajectory
        if tr.Duration <= 0:
            raise ToolError("invalid_state", f"{t.Label} has no duration (fewer than two waypoints, or all at one place): robot_path makes one with waypoints and speeds.")
        n = int(a.get("samples", 100))
        if not 2 <= n <= 5000:
            raise bad("samples: 2 … 5000.")
        before = axes_of(o)
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
        for i, v in enumerate(before, start=1):
            setattr(o, f"Axis{i}", v)
        doc().recompute()
        out = {"robot": o.Label, "trajectory": t.Label, "seconds": round(tr.Duration, 3), "samples": n,
               "axes": [{"axis": i + 1, "from": round(lows[i], 2), "to": round(highs[i], 2)} for i in range(6)],
               "verdict": "reaches all" if not misses else f"misses {len(misses)} of {n} points"}
        if misses:
            out["misses"] = misses[:20]
            out["worst_mm"] = round(worst, 3)
            out["note"] = ("Out of reach or past an axis limit there (or the solver could not follow a jump between samples: more samples): "
                           "move the path closer to the robot (robot_trajectory dress, move) or turn the tool. Positions are in the robot's own frame, its origin at its foot.")
        return out

    def robot_trajectory(a):
        op = a.get("op")
        if op == "join":
            srcs = [trajectory(r) for r in (a.get("trajectories") or [])]
            if len(srcs) < 2:
                raise bad("trajectories: two or more trajectories by name, run one after another in that order.")
            o = doc().addObject("Robot::TrajectoryCompound", "Trajectory")
            o.Source = srcs
        elif op == "dress":
            src = trajectory(a.get("trajectory"))
            try:
                o = doc().addObject("Robot::TrajectoryDressUpObject", "Trajectory")
            except Exception:
                o = doc().addObject("Robot::TrajectoryDressUp", "Trajectory")
            o.Source = src
            if a.get("speed") is not None:
                o.UseSpeed = True
                o.Speed = float(a["speed"])
            if a.get("acceleration") is not None:
                o.UseAcceleration = True
                o.Acceleration = float(a["acceleration"])
            if a.get("cont") is not None:
                try:
                    o.ContType = "Continues" if a["cont"] else "Discontinues"
                except Exception:
                    pass
            if a.get("move") is not None or a.get("ypr") is not None:
                at = [float(c) for c in (a.get("move") or [0, 0, 0])]
                y, p_, r = (float(c) for c in (a.get("ypr") or [0, 0, 0]))
                o.PosAdd = FreeCAD.Placement(V(*at), FreeCAD.Rotation(y, p_, r))
                # FreeCAD's own names (TrajectoryDressUpObject.cpp), its
                # misspelling included; the right spelling is taken too.
                add = a.get("add") or ("AddPosition" if a.get("ypr") is None else "AddOrintation" if a.get("move") is None else "AddPositionAndOrientation")
                add = {"AddOrientation": "AddOrintation"}.get(add, add)
                if add not in ("DontChange", "UseOrientation", "AddPosition", "AddOrintation", "AddPositionAndOrientation"):
                    doc().removeObject(o.Name)
                    raise bad("add: UseOrientation (ypr replaces each waypoint's orientation) | AddPosition (move added) | AddOrientation (ypr turned on top) | AddPositionAndOrientation (both) | DontChange.")
                o.AddType = add
        else:
            raise bad("op: join (trajectories, one after another) | dress (trajectory: a copy with speed mm/s, acceleration, cont, move [x,y,z] / ypr added to every point).")
        o.Label = s.unique(a.get("name") or ("Joined trajectory" if op == "join" else "Dressed trajectory"), o)
        doc().recompute()
        tr = o.Trajectory
        s.snapshot("robot_trajectory")
        return {"trajectory": o.Label, "waypoints": int(tr.size()) if hasattr(tr, "size") else len(tr.Waypoints), "seconds": round(tr.Duration, 3),
                "length_mm": round(tr.Length, 1) if hasattr(tr, "Length") else None, "step": len(s.steps)}

    def robot_export(a):
        o = robot(a.get("robot"))
        t = trajectory(a.get("trajectory"))
        p = a.get("path") or f"{t.Label.replace(' ', '_')}.src"
        p = p if os.path.isabs(p) else os.path.join(s.out_dir, p)
        if not p.lower().endswith(".src"):
            p += ".src"
        paths.made(s, p)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        try:
            import KukaExporter

            (KukaExporter.ExportFullSub if a.get("full") else KukaExporter.ExportCompactSub)(o, t, p)
        except Exception as e:
            raise ToolError("failed", f"KRL export failed: {e}") from None
        if not os.path.isfile(p):
            # FreeCAD 1.1's ExportFullSub is a stub: it writes nothing.
            raise ToolError("unavailable", "This FreeCAD's full KRL export writes no file (KukaExporter.ExportFullSub is empty in 1.1): leave full out for the compact form." if a.get("full") else "FreeCAD's KRL exporter wrote no file.")
        with open(p, encoding="utf-8", errors="replace") as f:
            text = f.read()
        return {"path": p, "lines": text.count("\n"), "moves": text.count("LIN ") + text.count("PTP "),
                "note": "KUKA KRL. Check it in the controller's simulator before running; running it is the person's."}

    tcp = {"type": "object", "description": "{ at [x,y,z], ypr [yaw, pitch, roll] | axis + angle }"}
    return [
        Tool("robot_trajectory", "Combine or adjust trajectories as new objects that follow their sources (FreeCAD's compound and dress-up): op join (trajectories [names], in order) | dress (trajectory, with any of: speed mm/s and acceleration for every waypoint, cont true | false, move [x,y,z] added to every waypoint and/or ypr [yaw, pitch, roll] turned on top of each one's orientation — the same path at another place or angle; add: UseOrientation makes ypr replace the orientations instead). Reply: trajectory, waypoints, seconds, length_mm.",
             obj({"op": {"type": "string", "enum": ["join", "dress"]}, "trajectories": {"type": "array", "items": {"type": "string"}}, "trajectory": {"type": "string"}, "speed": {"type": "number"},
                  "acceleration": {"type": "number"}, "cont": {"type": "boolean"}, "move": {"type": "array", "items": {}}, "ypr": {"type": "array", "items": {}}, "add": {"type": "string"}, "name": {"type": "string"}}, ["op"]), robot_trajectory, changes=True),
        Tool("robot_new", "A six-axis robot (Robot::RobotObject): model kr16 | kr125 | kr210 | kr500 (KUKA kinematics and picture, where this FreeCAD ships the files) | puma (only a name for the built-in default below: no Puma's kinematics), or kinematics: a CSV of your own (a header line, then six lines of a, alpha, d, theta, rotDir, maxAngle, minAngle, velocity; mm and degrees). Without a file the robot is FreeCAD's built-in default, a KUKA IR 500 — the reply's model says which was used. tool { at, ypr }: the tool's point from the flange (a gripper's tip), which tcp in robot_move and robot_run then means. at, ypr are stored as its Base, but FreeCAD's kinematics do not use it: positions are always in the robot's own frame, origin at its foot. Reply: robot, axes [6 degrees], tcp { at, ypr }, model.",
             obj({"model": {"type": "string"}, "kinematics": {"type": "string"}, "at": {"type": "array", "items": {}}, "ypr": {"type": "array", "items": {}}, "tool": tcp, "name": {"type": "string"}}), robot_new, changes=True),
        Tool("robot_move", "Move a robot (the one there is when robot is left out): axes [six degrees] (forward: tcp in the reply is where the tool point lands), tcp { at [x,y,z] mm, ypr [yaw, pitch, roll] degrees or axis + angle } (inverse kinematics from the pose it is in, within the axes' limits: reached false and off_mm when it could not get there, the axes then as they were), or home: true (the home pose set in FreeCAD, else all axes 0). An orientation left out means none (tool axes along the robot's) — usually unreachable: read tcp.ypr from the reply of an axes move and keep it. Reply: axes, tcp, reached.",
             obj({"robot": {"type": "string"}, "axes": {"type": "array", "items": {}}, "tcp": tcp, "home": {"type": "boolean"}}), robot_move, changes=True),
        Tool("robot_path", "A trajectory object: waypoints [{ at, ypr, type LIN | PTP | CIRC | WAIT (LIN by default), speed mm/s (1000), cont, name }], two or more, in the robot's frame — or edges [\"Body.Edge3\", …] (or an object for all its edges; one object only) to follow, deviation mm (0.5) from curved ones, useRotation for the edges' own orientation. Reply: trajectory, waypoints, length mm, seconds. robot_run checks a robot can follow it.",
             obj({"waypoints": {"type": "array", "items": {}}, "edges": {"type": "array", "items": {"type": "string"}}, "deviation": {"type": "number"}, "useRotation": {"type": "boolean"}, "name": {"type": "string"}}), robot_path, changes=True),
        Tool("robot_run", "Check a trajectory on a robot without moving it for good: samples (100; 2 … 5000) points along it by time, each solved by inverse kinematics from the one before, the tool point (robot_new tool) on the path. Reply: verdict (reaches all | misses n of N), misses [{ t, at, off_mm }] (the first 20), worst_mm, each axis's range of angles used, seconds. A miss is a point out of reach or past an axis limit, or one the solver could not follow to. The robot's axes are put back as they were.",
             obj({"robot": {"type": "string"}, "trajectory": {"type": "string"}, "samples": {"type": "integer"}}, ["trajectory"]), robot_run),
        Tool("robot_export", "Write a trajectory as KUKA KRL (.src) with FreeCAD's exporter: path (relative: the session's folder; .src added); every waypoint is written as a LIN move with its speed, whatever its type (FreeCAD's compact form; full: true is refused where FreeCAD's full form writes nothing, as in 1.1). Positions are the waypoints as they are (no tool or base applied). Reply: path, lines, moves. Simulate it on the controller before running; running it is the person's.",
             obj({"robot": {"type": "string"}, "trajectory": {"type": "string"}, "path": {"type": "string"}, "full": {"type": "boolean"}}, ["trajectory"]), robot_export),
    ]
