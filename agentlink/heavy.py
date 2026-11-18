# SPDX-License-Identifier: LGPL-2.1-or-later
# Heavy jobs on this Mac (unattended use, N): each heavy tool's time and peak
# memory are logged against a size measure (the faces of the parts, mesh
# facets, cloud points). The times are logged data only: no estimate stops
# or delays a call (no prejudging, 18 Nov: an export estimated at 2 min took
# 0.48 s, a loft estimated at 3 min took 6.4 s). Every call starts at once;
# one past about 60 s moves to the background (agentlink/sup_jobs.py). Over
# the memory ceiling (half this Mac's
# memory unless the person set Mod/AgentLink MemoryCeilingGB), it is refused
# before it starts. Holding back for heat, memory pressure or the person
# working in the window is the supervisor's (supervise.py), which sees every
# call whichever FreeCAD runs it.

import resource
import sys
import time

from . import keep
from .protocol import ToolError

# A heavy tool may say during its call what its work really was
# (session.heavy_work = (timing key, size)): a render its triangles times
# views, not the document's faces. Its time is then logged against that,
# under that key, and the estimate it gives tracks what it drew. A render
# logged against faces was put at 6 min and took 17 s.
WORK = "heavy_work"


def _maxrss_mb():
    k = 1.0 if sys.platform == "darwin" else 1024.0  # bytes on macOS, KB elsewhere
    a = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * k
    b = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * k
    return a / 1048576.0, b / 1048576.0


def size_of(session):
    """How big the work is: the parts' faces, mesh facets and cloud points."""
    n = 0
    try:
        for o in session.doc.Objects:
            sh = getattr(o, "Shape", None)
            if sh is not None:
                try:
                    if not sh.isNull():
                        n += len(sh.Faces)
                except Exception:
                    pass
            m = getattr(o, "Mesh", None)
            if m is not None and hasattr(m, "CountFacets"):
                n += int(m.CountFacets) // 20
            p = getattr(o, "Points", None)
            if p is not None and hasattr(p, "CountPoints"):
                n += int(p.CountPoints) // 50
    except Exception:
        pass
    return max(1, n)


# Memory per heavy tool and size, in MB, as each job raised the peak. A new key:
# the old "memory" entries held whole-process peaks, which made a small job
# look like tens of GB.
MEMORY_KEY = "memoryAdded"
# A refusal needs at least this many runs to go on, and is never extrapolated
# further than this many times the largest size already seen.
MEMORY_MIN_RUNS = 2
MEMORY_REACH = 4.0


def memory_estimate(q, tool, size):
    """MB a heavy job of this size should add, from its past runs here, or
    None when there is too little to go on."""
    pts = [(s, m) for s, m in (q.get(MEMORY_KEY) or {}).get(tool, []) if s > 0]
    if len(pts) < MEMORY_MIN_RUNS:
        return None
    reach = max(s for s, _ in pts) * MEMORY_REACH
    return keep.estimate({"timings": {tool: pts}}, tool, min(float(size), reach))


def _obj(doc, ref):
    if not isinstance(ref, str) or not ref:
        return None
    ref = ref.split(".")[0]
    o = doc.getObject(ref)
    if o is None:
        o = next((x for x in doc.Objects if x.Label == ref), None)
    return o


def _faces(o):
    try:
        sh = o.Shape
        return 0 if sh.isNull() else len(sh.Faces)
    except Exception:
        return 0


def loft_counts(session, args):
    """(profiles, points per profile) a part_loft call will loft: its
    profiles (points given inline or in a points_file) or its
    profiles_file, read as the tool reads them; a sketch or edge counts 48
    points (sample_count's least). None when they cannot be read."""
    from . import paths, pointfiles

    if args.get("profiles_file") is not None:
        outs = pointfiles.outlines(paths.in_file(session, "part_loft", args["profiles_file"], "profiles_file"), args.get("key"), "profiles_file")
        counts = [len(pts) for _, pts in outs]
    else:
        counts = []
        for p in args.get("profiles") or []:
            n = 48
            if isinstance(p, dict):
                if isinstance(p.get("points"), list):
                    n = len(p["points"])
                elif p.get("points_file") is not None:
                    n = len(pointfiles.one_outline(paths.in_file(session, "part_loft", p["points_file"], "points_file"), p.get("key"), "points_file"))
            counts.append(n)
    if len(counts) < 2:
        return None
    n = max(counts)
    samples = args.get("samples")
    if isinstance(samples, int) and not isinstance(samples, bool) and samples > 0 and (not args.get("ruled") or len(set(counts)) > 1):
        n = samples  # rebuilt with that many points each
    return len(counts), max(2, n)


def _poles(face):
    """A face's B-spline or Bezier poles (U x V), or None for another kind."""
    try:
        srf = face.Surface
    except Exception:
        return None
    up, vp = getattr(srf, "NbUPoles", None), getattr(srf, "NbVPoles", None)
    try:
        return float(up * vp) if up and vp else None
    except TypeError:
        return None


def tess_size(shape, tol=0.1):
    """The work of meshing a shape to a chord error of tol mm, in insp_run's
    units: each B-spline or Bezier face its poles, each other face a
    hundredth, times sqrt(0.1 / tol) (a finer tolerance, more triangles)."""
    n = 0.0
    try:
        for f in shape.Faces:
            p = _poles(f)
            n += p if p else 0.01
    except Exception:
        return 0.0
    try:
        k = (0.1 / float(tol)) ** 0.5 if tol and float(tol) > 0 else 1.0
    except (TypeError, ValueError):
        k = 1.0
    return n * k


# insp_run, a solid nominal: each measured point is an OCC distance to it and
# a classifier (FreeCAD's InspectNominalShape), its time about points x the
# nominal's faces (a B-spline face more, by its poles). In tess_size's units.
INSP_POINT_WORK = 1.0 / 700.0


def _measured_points(o, args):
    """The points insp_run measures on its actual: a mesh's or a cloud's
    own, a body's as meshed at spacing (its area / spacing squared, at most
    cap)."""
    m = getattr(o, "Mesh", None)
    if m is not None and hasattr(m, "CountPoints"):
        return int(m.CountPoints)
    p = getattr(o, "Points", None)
    if p is not None and hasattr(p, "CountPoints"):
        return int(p.CountPoints)
    sh = getattr(o, "Shape", None)
    try:
        area = float(sh.Area)
        diag = float(sh.BoundBox.DiagonalLength)
    except Exception:
        return 0
    sp = args.get("spacing")
    sp = float(sp) if isinstance(sp, (int, float)) and not isinstance(sp, bool) and sp > 0 else max(diag / 100.0, 0.2)
    cap = args.get("cap", 60000)
    cap = max(1000, min(int(cap) if isinstance(cap, int) and not isinstance(cap, bool) else 60000, 400000))
    return int(min(cap, area / (sp * sp)))


def _nominal_work(o):
    """A solid nominal's work for each measured point: its faces, a B-spline
    face 1 + poles / 100. A mesh or a cloud nominal: none worth counting (a
    grid lookup)."""
    if getattr(o, "Mesh", None) is not None or getattr(o, "Points", None) is not None:
        return 0.0
    sh = getattr(o, "Shape", None)
    n = 0.0
    try:
        for f in sh.Faces:
            p = _poles(f)
            n += 1.0 + (p / 100.0 if p else 0.0)
    except Exception:
        return 0.0
    return n


def insp_size(session, args):
    """insp_run's size: the actual body's tessellation (tess_size at
    deflection: its B-spline poles, a hundredth for each other face), mesh
    points / 20000 on both sides, and the measured points x each solid
    nominal's faces (INSP_POINT_WORK). None for a file (read in the call)."""
    doc = session.doc
    n = 0.0
    act = _obj(doc, args.get("actual"))
    if act is None:
        return None
    defl = args.get("deflection", 0.1)
    defl = float(defl) if isinstance(defl, (int, float)) and not isinstance(defl, bool) and defl > 0 else 0.1
    noms = [_obj(doc, x) for x in (args.get("nominals") or []) if isinstance(x, str)]
    for o in [act] + noms:
        if o is None:
            continue
        sh = getattr(o, "Shape", None)
        if o is act and sh is not None and not getattr(o, "Mesh", None):
            n += tess_size(sh, defl)
        m = getattr(o, "Mesh", None)
        if m is not None and hasattr(m, "CountPoints"):
            n += int(m.CountPoints) / 20000.0
    work = sum(_nominal_work(o) for o in noms if o is not None and o is not act)
    if work:
        n += _measured_points(act, args) * work * INSP_POINT_WORK
    return max(1e-3, n)


# Tessellating formats of export (a solid written as triangles).
TESS_FORMATS = {"stl", "obj", "3mf", "ply", "off", "wrl", "x3d", "glb", "gltf", "dae"}


def export_size(session, args):
    """export's size: the tessellation of the shapes it writes as triangles
    (tess_size at its tolerance, 0.01 mm by default); 0 for a format that
    does not tessellate (STEP, IGES, BREP, DXF, SVG) or meshes written as
    they are. None when it cannot be read."""
    import os

    doc = session.doc
    fmt = str(args.get("format") or "").lower()
    if not fmt and isinstance(args.get("path"), str):
        fmt = os.path.splitext(args["path"])[1].lstrip(".").lower()
    names = args.get("objects")
    names = names if isinstance(names, list) else ([names] if isinstance(names, str) and names else [])
    objs = [_obj(doc, n) for n in names]
    if not names:
        bodies = [o for o in doc.Objects if getattr(o, "Shape", None) is not None and _faces(o) and not getattr(o, "InList", [])]
        objs = bodies[:1]
    objs = [o for o in objs if o is not None and getattr(o, "Mesh", None) is None]
    if not objs:
        return 0.0
    if not fmt:
        fmt = "step"
    if fmt not in TESS_FORMATS:
        return 0.0
    tol = args.get("tolerance", 0.01)
    tol = float(tol) if isinstance(tol, (int, float)) and not isinstance(tol, bool) and tol > 0 else 0.01
    return sum(tess_size(o.Shape, tol) for o in objs)


def _stl_facets(path):
    """Triangles in a binary STL by its header, else None."""
    import os
    import struct

    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            head = f.read(84)
        n = struct.unpack("<I", head[80:84])[0]
        return n if 84 + 50 * n == size else None
    except Exception:
        return None


def from_mesh_size(session, args):
    """part_from_mesh's size: the mesh's triangles, twice that with refine
    (the default). None when they cannot be read before the call."""
    n = None
    if args.get("mesh"):
        m = getattr(_obj(session.doc, args.get("mesh")), "Mesh", None)
        if m is not None and hasattr(m, "CountFacets"):
            n = int(m.CountFacets)
    elif isinstance(args.get("file"), str):
        import os

        n = _stl_facets(os.path.expanduser(args["file"]))
    if not n:
        return None
    return float(n) * (2.0 if args.get("refine", True) else 1.0)


def _boxes(shape):
    """Each face's bounding box as rows of [xmin, ymin, zmin, xmax, ymax,
    zmax] (numpy), or None when the faces have none (stand-ins)."""
    import numpy as np

    rows = []
    for f in shape.Faces:
        b = getattr(f, "BoundBox", None)
        if b is None:
            return None
        rows.append((b.XMin, b.YMin, b.ZMin, b.XMax, b.YMax, b.ZMax))
    return np.array(rows, dtype=float).reshape(-1, 6)


# At most this many tool faces are tested against every base face; past it,
# an even sample of them, and the count scaled up (an estimate's count).
PAIR_SAMPLE = 400


def overlap_pairs(base_shape, tool_shapes, gap=1e-3):
    """Face pairs (a base face, a tool face) whose bounding boxes meet: the
    pairs OCC's boolean intersects (it filters by boxes first). Of many tool
    faces, an even sample of PAIR_SAMPLE, scaled up. None when they cannot
    be read (no numpy, faces with no box)."""
    try:
        import numpy as np

        B = _boxes(base_shape)
        if B is None:
            return None
        Ts = []
        for sh in tool_shapes:
            T = _boxes(sh)
            if T is None:
                return None
            Ts.append(T)
        T = np.concatenate(Ts) if Ts else np.zeros((0, 6))
        if not len(T) or not len(B):
            return 0
        # Only the base faces inside the tools' whole box can meet any.
        lo, hi = T[:, :3].min(axis=0) - gap, T[:, 3:].max(axis=0) + gap
        B = B[np.all((B[:, :3] <= hi) & (B[:, 3:] >= lo), axis=1)]
        step = max(1, -(-len(T) // PAIR_SAMPLE))
        n = 0
        for t in T[::step]:
            n += int(np.count_nonzero((B[:, 0] <= t[3] + gap) & (B[:, 3] >= t[0] - gap) & (B[:, 1] <= t[4] + gap) & (B[:, 4] >= t[1] - gap)
                                      & (B[:, 2] <= t[5] + gap) & (B[:, 5] >= t[2] - gap)))
        return int(round(n * len(T) / len(T[::step])))
    except Exception:
        return None


def boolean_parts(session, args):
    """A part_boolean call's size and its parts: {size, pairs (face pairs
    whose boxes meet, or None), base, tools (faces)}, or None when its
    bodies cannot be read."""
    doc = session.doc
    names = args.get("tools")
    names = names if isinstance(names, list) else [names]
    tools = [_obj(doc, n) for n in names]
    tf = [_faces(t) for t in tools if t is not None]
    base = _obj(doc, args.get("base"))
    if base is None:
        # base left out: the one other solid body there is.
        rest = [o for o in doc.Objects if o not in tools and getattr(o, "Shape", None) is not None and _faces(o) and not o.InList]
        base = max(rest, key=_faces) if rest else None
    if base is None or not tf:
        return None
    nb, nt = _faces(base), sum(tf)
    pairs = overlap_pairs(base.Shape, [t.Shape for t in tools if t is not None])
    size = keep.boolean_size(nb, tf) if pairs is None else keep.boolean_work(pairs, nb + nt)
    return {"size": size, "pairs": pairs, "base": nb, "tools": nt}


def loft_faces(profiles, points, loop=False):
    """The faces a ruled loft of these makes along its way."""
    return (profiles if loop else profiles - 1) * points


def loft_size(faces):
    """A loft's size for its estimate: (faces / 1000) cubed — its time grows
    about so (36 points a profile 9.7 s, 80 points past 120 s, 91 profiles)."""
    return max(1e-6, (float(faces) / 1000.0) ** 3)


def loft_split(profiles, points, loop, est, target=40.0):
    """How to bring a loft under target seconds: runs of so many profiles
    (each sharing its end profile with the next), or so many points a
    profile."""
    k = max(1.0, (est / target) ** (1.0 / 3.0))  # time ~ faces cubed
    spans = max(1, (profiles if loop else profiles - 1))
    per_run = max(2, int(spans / k) + 1)
    runs = max(2, -(-spans // max(1, per_run - 1)))
    pts = max(8, int(points / k))
    return per_run, runs, pts


def sized_size(session, tool, args):
    """The size a sized tool (keep.SIZED) works at: a boolean's face pairs
    whose boxes meet and its faces (boolean_parts), insp_run's and export's
    tessellation, part_from_mesh's triangles, a loft's faces cubed, else the
    document's faces. None when it cannot be read (the tool's own refusal
    then says why)."""
    try:
        if tool == "part_boolean":
            got = boolean_parts(session, args)
            return got["size"] if got else None
        if tool == "insp_run":
            return insp_size(session, args)
        if tool == "part_from_mesh":
            return from_mesh_size(session, args)
        if tool == "export":
            return export_size(session, args)
        if tool == "part_loft":
            c = loft_counts(session, args)
            if c is None:
                return None
            return loft_size(loft_faces(c[0], c[1], bool(args.get("closed"))))
        return size_of(session)
    except Exception:
        return None


def _fmt(sec):
    return f"{int(round(sec))} s" if sec < 90 else f"{sec / 60:.0f} min"


class Gate:
    def __init__(self, session):
        self.s = session
        self.offers = {}
        self.start = None
        self.sized = None

    @staticmethod
    def live():
        """Offers and the ceiling apply where the person's work runs: the
        window, or the hidden FreeCAD under the supervisor. A server used
        in-process (tests, scripts) only logs."""
        import os

        try:
            import FreeCAD

            gui = bool(getattr(FreeCAD, "GuiUp", False))
        except Exception:
            gui = False
        return gui or bool(os.environ.get("AGENTLINK_SUPERVISED")) or bool(os.environ.get("AGENTLINK_GATE"))

    def before(self, tool, args):
        if tool.name in keep.SIZED:
            self._sized_before(tool, args)
        else:
            self._stopped_before(tool, args)
        if not keep.is_heavy(tool.name):
            return
        try:
            setattr(self.s, WORK, None)
        except Exception:
            pass
        if not self.live():
            self.start = (time.time(), size_of(self.s), _maxrss_mb())
            return
        q = keep.queue_state()
        size = size_of(self.s)
        m = keep.preset(self._overrides())
        ceiling = float(m.get("memoryCeilingGB") or 0)
        mem = memory_estimate(q, tool.name, size)
        if ceiling and mem and mem / 1024.0 > ceiling:
            raise ToolError("invalid_state", f"{tool.name} at this size would need about {mem / 1024.0:.1f} GB (from its past runs here), over this Mac's {ceiling:g} GB ceiling for one job: a coarser pass (fewer elements or points) first. The person can raise the ceiling (Mod/AgentLink MemoryCeilingGB).")
        now = time.time()
        # No estimate refuses or holds the call (no prejudging): it runs,
        # and its time is logged after it (after()).
        # A saved copy before a heavy change (an add-on's "checkpoints"
        # service): a crash or a hang in it loses nothing done before.
        if tool.changes:
            from . import hooks

            cps = hooks.service("checkpoints")
            if cps is not None:
                try:
                    cps.take(self.s, f"before {tool.name}", auto=True)
                except Exception:
                    pass
        self.start = (now, size, _maxrss_mb())

    # ---- tools heavy only at some sizes (keep.SIZED): a Part boolean of faceted solids ----

    def _sized_before(self, tool, args):
        self.sized = None
        if getattr(self, "as_job", False):
            # A read sent to a job (jobs.wanted: its estimate is past
            # jobs.SLOW_READ) runs on a worker thread: the window is not
            # frozen, so nothing to ask and no deadline to stretch.
            return
        size = sized_size(self.s, tool.name, args)
        try:
            # For a batch's start-time guess (jobs.typical): the input size
            # of the call that runs now, kept with its time.
            self.s.sized_now = (tool.name, size)
        except Exception:
            pass
        if not size:
            return
        try:
            q = keep.queue_state()
        except Exception:
            q = {}
        tkey = keep.sized_key(tool.name, args)
        est = keep.sized_estimate(q, tool.name, size, tkey)
        if est is None:
            return
        # Logged data only (no prejudging): the call runs whatever the
        # estimate says; its real time is logged against its size after it.
        self.sized = (time.time(), size, est, tkey)

    def _stopped_before(self, tool, args):
        """A change the watchdog stopped FreeCAD in before (it ran past its
        deadline without answering): asked about once in the window with
        what happened, then run with a deadline of three times as long as it
        ran then (a read like it goes to a job instead: jobs.wanted)."""
        try:
            changes = tool.changes_for(args or {})
        except Exception:
            changes = getattr(tool, "changes", True)
        # A stop before is logged data only now (no prejudging): the call
        # runs as asked, and the watchdog stops FreeCAD only when it is
        # truly hung (supervise.stalled), never for being slow.
        return

    def _sized_after(self, tool, ok):
        got, self.sized = getattr(self, "sized", None), None
        if got is None:
            return
        t0, size, est, tkey = got
        if tkey is None:  # not timed by size
            ok = False
        secs = time.time() - t0
        # Timed where it says something: a run of a second or more.
        if ok and secs >= 1.0:
            try:
                with keep.queue_lock():
                    q = keep.queue_state()
                    keep.log_timing(q, tkey, size, secs)
                    keep.save_queue(q)
            except Exception:
                pass

    def after(self, tool, args, ok):
        if getattr(self, "sized", None) is not None:
            self._sized_after(tool, ok)
        if not keep.is_heavy(tool.name) or self.start is None:
            return
        t0, size, (a0, b0) = self.start
        self.start = None
        if not ok:
            return
        secs = time.time() - t0
        key = tool.name
        work = getattr(getattr(self, "s", None), WORK, None)
        if isinstance(work, tuple) and len(work) == 2 and work[1]:
            key, size = work
            try:
                setattr(self.s, WORK, None)
            except Exception:
                pass
        try:
            a1, b1 = _maxrss_mb()
            # What this job added to the high-water mark, not the process's
            # lifetime peak (ru_maxrss never falls): a job that stayed under
            # an earlier peak adds nothing and is not logged.
            peak = max(a1 - a0, b1 - b0, 0.0)
            with keep.queue_lock():  # the supervisor writes the same file (round 8)
                q = keep.queue_state()
                keep.log_timing(q, key, size, secs)
                if peak > 0 and key == tool.name:
                    mem = {"timings": q.get(MEMORY_KEY) or {}}
                    keep.log_timing(mem, tool.name, size, peak)
                    q[MEMORY_KEY] = mem["timings"]
                keep.save_queue(q)
        except Exception:
            pass

    @staticmethod
    def _overrides():
        try:
            import FreeCAD

            g = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/AgentLink")
            return {"heavySlots": g.GetInt("HeavySlots", 0), "memoryCeilingGB": g.GetFloat("MemoryCeilingGB", 0.0)}
        except Exception:
            return {}
