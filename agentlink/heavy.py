# SPDX-License-Identifier: LGPL-2.1-or-later
# Heavy jobs on this Mac (unattended use, N): each heavy tool's time and peak
# memory are logged against a size measure (the faces of the parts, mesh
# facets, cloud points), so the next one can be estimated. Over 2 minutes,
# the first call is answered with the estimate and a rough pass offered —
# the same call again runs it. Over the memory ceiling (half this Mac's
# memory unless the person set Mod/AgentLink MemoryCeilingGB), it is refused
# before it starts. Holding back for heat, memory pressure or the person
# working in the window is the supervisor's (supervise.py), which sees every
# call whichever FreeCAD runs it.

import resource
import sys
import time

from . import keep
from .protocol import ToolError

OFFER_OVER = 120.0
OFFER_KEEP = 600.0
# Heavy tools never refused on an estimate: a picture is the job itself (no
# rougher pass to offer), and its time follows its views and pixels, not the
# document's faces the estimate is read against — a 17 s render was put at
# 6 min from an earlier slow run, and every render took two calls. They are
# still queued, timed and given a heavy call's deadline.
NO_OFFER = {"view_render", "steps_render"}
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


def insp_size(session, args):
    """insp_run's size: the actual body's B-spline poles (a free-form face
    is what tessellates and inspects slowly), a hundredth for each other
    face, and mesh points / 20000 on both sides. None for a file (read
    in the call)."""
    doc = session.doc
    n = 0.0
    act = _obj(doc, args.get("actual"))
    if act is None:
        return None
    for o in [act] + [_obj(doc, x) for x in (args.get("nominals") or []) if isinstance(x, str)]:
        if o is None:
            continue
        sh = getattr(o, "Shape", None)
        if o is act and sh is not None and not getattr(o, "Mesh", None):
            try:
                for f in sh.Faces:
                    srf = f.Surface
                    up, vp = getattr(srf, "NbUPoles", None), getattr(srf, "NbVPoles", None)
                    n += float(up * vp) if up and vp else 0.01
            except Exception:
                pass
        m = getattr(o, "Mesh", None)
        if m is not None and hasattr(m, "CountPoints"):
            n += int(m.CountPoints) / 20000.0
    return max(1e-3, n)


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
    (base faces x tool faces), else the document's faces. None when it
    cannot be read (the tool's own refusal then says why)."""
    try:
        doc = session.doc
        if tool == "part_boolean":
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
            return keep.boolean_size(_faces(base), tf)
        if tool == "insp_run":
            return insp_size(session, args)
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
        est = keep.estimate(q, tool.name, size)
        key = keep.call_key(tool.name, args)
        now = time.time()
        self.offers = {k: t for k, t in self.offers.items() if now - t < OFFER_KEEP}
        # Inside a batch the batch is the plan: a heavy call in it runs as
        # asked (a refused estimate stopped the batch and rolled back the
        # good steps before it).
        in_batch = bool(getattr(self.s, "batch_now", None))
        # A read sent to a job (agentlink/jobs.py) runs: its answer waits
        # for it, the call does not.
        as_job = bool(getattr(self, "as_job", False))
        if est and est > OFFER_OVER and key not in self.offers and tool.name not in NO_OFFER and not in_batch and not as_job:
            self.offers[key] = now
            rough = keep.estimate(q, tool.name, max(1, size / 4.0)) or est / 4.0
            rng = keep.estimate_range(q, tool.name, size)
            span = f" ({_fmt(rng[0])} to {_fmt(rng[2])} over its runs)" if rng and _fmt(rng[0]) != _fmt(rng[2]) else ""
            raise ToolError("invalid_state", f"{tool.name} takes about {_fmt(est)}{span} here at this size (from its past runs on this Mac); a rough pass (a coarser mesh, fewer points) takes about {_fmt(rough)} — run that first? The same call again runs it as asked. Nothing was run.")
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
        size = sized_size(self.s, tool.name, args)
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
        after = keep.stopped_before(tool.name, q=q)
        if after is not None:
            # It stopped FreeCAD before: never estimated under what it ran then.
            est = max(est, 1.5 * after)
        now = time.time()
        if keep.SIZED[tool.name]["ask"] and est > keep.SIZED_ASK_OVER and self.live():
            key = keep.call_key(tool.name, args)
            self.offers = {k: t for k, t in self.offers.items() if now - t < OFFER_KEEP}
            if key not in self.offers:
                self.offers[key] = now
                src = "its past runs on this Mac" if len((q.get("timings") or {}).get(tkey) or []) >= 2 else "a rough rule"
                raise ToolError("invalid_state", self._sized_words(tool.name, args, size, est, src))
        self.sized = (now, size, est, tkey)
        if est > keep.SIZED_MARK_OVER:
            try:
                keep.mark_heavy_call(tool.name, est, size, t=now)
                # The tool's own time budget (part_loft stops its tries and
                # checks past it): twice the estimate, inside the watchdog's
                # three times.
                self.s.call_budget = 2.0 * est
            except Exception:
                pass

    def _stopped_before(self, tool, args):
        """A change the watchdog stopped FreeCAD in before (it ran past its
        deadline without answering): asked about once in the window with
        what happened, then run with a deadline of three times as long as it
        ran then (a read like it goes to a job instead: jobs.wanted)."""
        try:
            changes = tool.changes_for(args or {})
        except Exception:
            changes = getattr(tool, "changes", True)
        if not changes or keep.is_heavy(tool.name) or getattr(self, "as_job", False):
            return
        after = keep.stopped_before(tool.name)
        if after is None:
            return
        est = max(keep.SIZED_MARK_OVER + 1.0, 1.5 * after)
        now = time.time()
        if self.live() and not getattr(self.s, "batch_now", None):
            key = keep.call_key(tool.name, args)
            self.offers = {k: t for k, t in self.offers.items() if now - t < OFFER_KEEP}
            if key not in self.offers:
                self.offers[key] = now
                raise ToolError("invalid_state", f"{tool.name} stopped FreeCAD before: a call of it ran {_fmt(after)} without answering and the watchdog took the window for hung. "
                                f"A lighter call first (fewer points, a coarser mesh or deflection, a smaller part), or the same call again runs it with up to {_fmt(keep.deadline('heavy', est))} before the watchdog steps in. Nothing was run.")
        self.sized = (now, None, est, None)
        try:
            keep.mark_heavy_call(tool.name, est, 0, t=now)
            self.s.call_budget = 2.0 * est
        except Exception:
            pass

    def _sized_words(self, tool, args, size, est, src):
        """The refusal of a sized call estimated past SIZED_ASK_OVER: its
        estimate, what it is from, and the lighter way."""
        if tool == "part_loft":
            loop = bool(args.get("closed"))
            c = loft_counts(self.s, args) or (2, 48)
            per_run, runs, pts = loft_split(c[0], c[1], loop, est)
            how = "ruled" if args.get("ruled") else "smooth"
            return (f"part_loft here is heavy: about {_fmt(est)} for {c[0]} profiles of {c[1]} points {how} ({loft_faces(c[0], c[1], loop):,} faces along the way; from {src}), "
                    "and FreeCAD's window is frozen until OCC finishes — past its deadline the window is taken for hung and stopped. Lighter: "
                    f"split it into {runs} lofts of about {per_run} profiles each (each run starting on the profile the last ended on), then part_boolean fuse them; "
                    f"or fewer points a profile (samples: {pts}, the profiles rebuilt alike); or fewer profiles where the shape changes slowly. "
                    "The same call again runs it as asked; the watchdog then waits its estimate times three. Nothing was run.")
        return (f"{tool} here is heavy: about {_fmt(est)} at this size ({int(size):,} face pairs; from {src}), "
                "and FreeCAD's window is frozen until OCC finishes. Lighter first: fewer faces (part_refine merges coplanar facets; a coarser mesh before part_from_mesh), "
                "or meshobj_boolean on the meshes. The same call again runs it as asked; the watchdog waits for it. Nothing was run.")

    def _sized_after(self, tool, ok):
        got, self.sized = getattr(self, "sized", None), None
        if got is None:
            return
        t0, size, est, tkey = got
        if tkey is None:  # a call stopped before (_stopped_before): not timed by size
            keep.clear_heavy_call()
            ok = False
        if est > keep.SIZED_MARK_OVER:
            keep.clear_heavy_call()
            try:
                self.s.call_budget = 0
            except Exception:
                pass
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
