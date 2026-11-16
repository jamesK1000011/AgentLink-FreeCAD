# SPDX-License-Identifier: LGPL-2.1-or-later
# Live window scripts (scripts/live/README.md) replayed by live_run: a
# script's steps sent as batches (rollback: false, stopOnError: false) or
# call by call (direct), each step's expect checked against the answers,
# and a pass or fail per step with the failing check's path, what it
# wanted and what it got. The checks and the path walk need no FreeCAD.

import json
import os
import re

from .protocol import ToolError

MISSING = object()
CHECKS = ("equals", "contains", "atLeast", "atMost", "exists", "noneContain")


def _tokens(path):
    """'result.steps[*].selected.0' → ['result', 'steps', '*', 'selected', '0']."""
    out = []
    for part in str(path).split("."):
        if part == "":
            continue
        head, *rest = re.split(r"\[", part)
        if head:
            out.append(head)
        for r in rest:
            out.append(r.rstrip("]"))
    return out


def walk(value, path):
    """Every value the path reaches (a list: [*] fans out); [] when none.
    Dots for keys and list indices, -1 the last item."""
    cur = [value]
    for t in _tokens(path):
        nxt = []
        for v in cur:
            if t == "*":
                if isinstance(v, list):
                    nxt.extend(v)
                elif isinstance(v, dict):
                    nxt.extend(v.values())
            elif isinstance(v, list):
                try:
                    i = int(t)
                except ValueError:
                    continue
                if -len(v) <= i < len(v):
                    nxt.append(v[i])
            elif isinstance(v, dict) and t in v:
                nxt.append(v[t])
        cur = nxt
    return cur


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _eq(a, b):
    if _num(a) and _num(b):
        return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))
    return a == b


def _lines(v):
    if isinstance(v, str):
        return v.splitlines()
    if isinstance(v, list):
        return [x if isinstance(x, str) else json.dumps(x) for x in v]
    return [json.dumps(v)]


def check_one(found, e):
    """(ok, wanted, got) for one expect against the values its path reached."""
    got = found[0] if len(found) == 1 else (found if found else None)
    if "exists" in e:
        want = bool(e["exists"])
        return (bool(found) == want), {"exists": want}, (got if found else "(missing)")
    if not found:
        kind = next((k for k in CHECKS if k in e), "equals")
        return False, {kind: e.get(kind)}, "(missing)"
    if "equals" in e:
        w = e["equals"]
        return any(_eq(v, w) for v in found), {"equals": w}, got
    if "contains" in e:
        w = e["contains"]

        def has(v):
            if isinstance(v, str):
                return isinstance(w, str) and w in v
            if isinstance(v, list):
                return any(_eq(x, w) or (isinstance(x, str) and isinstance(w, str) and w in x) for x in v)
            if isinstance(v, dict):
                return w in v
            return False

        return any(has(v) for v in found), {"contains": w}, got
    if "atLeast" in e or "atMost" in e:
        lo, hi = e.get("atLeast"), e.get("atMost")
        ok = any(_num(v) and (lo is None or v >= lo - 1e-9) and (hi is None or v <= hi + 1e-9) for v in found)
        return ok, {k: e[k] for k in ("atLeast", "atMost") if k in e}, got
    if "noneContain" in e:
        words = e["noneContain"] if isinstance(e["noneContain"], list) else [e["noneContain"]]
        skip = e.get("ignoreLinesWith") or []
        skip = skip if isinstance(skip, list) else [skip]
        bad = []
        for v in found:
            for ln in _lines(v):
                if any(s in ln for s in skip):
                    continue
                if any(w in ln for w in words):
                    bad.append(ln)
        return not bad, {"noneContain": words}, (bad[:5] if bad else "(none)")
    return False, {"check": f"none of {', '.join(CHECKS)}"}, got


def evaluate(answers, expects):
    """Each expect against answers[call] (as batch gives a call: {tool, ok,
    result | error}): [{call, path, ok, wanted, got}]."""
    out = []
    for e in expects or []:
        i = e.get("call", 0)
        ans = answers[i] if isinstance(i, int) and -len(answers) <= i < len(answers) else MISSING
        if ans is MISSING:
            out.append({"call": i, "path": e.get("path"), "ok": False, "wanted": {"call": i}, "got": f"(only {len(answers)} calls answered)"})
            continue
        found = walk(ans, e.get("path", ""))
        ok, wanted, got = check_one(found, e)
        out.append({"call": i, "path": e.get("path"), "ok": ok, "wanted": wanted, "got": got})
    return out


VAR = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")


def substitute(value, vars_):
    """$name filled in from vars_ (a whole string "$next" takes the value
    itself, a number stays a number); answers (value, names not known)."""
    missing = []

    def sub(v):
        if isinstance(v, str):
            m = VAR.fullmatch(v)
            if m:
                if m.group(1) in vars_:
                    return vars_[m.group(1)]
                missing.append(m.group(1))
                return v

            def one(mm):
                if mm.group(1) in vars_:
                    return str(vars_[mm.group(1)])
                missing.append(mm.group(1))
                return mm.group(0)

            return VAR.sub(one, v)
        if isinstance(v, list):
            return [sub(x) for x in v]
        if isinstance(v, dict):
            return {k: sub(x) for k, x in v.items()}
        return v

    return sub(value), sorted(set(missing))


def declared_vars(script):
    """The $names a script's conventions declare ("$X,$Y" declares both)."""
    names = []
    for k in (script.get("conventions") or {}):
        names.extend(VAR.findall(k))
    return names


def capture(vars_, names, answer):
    """A declared $name that is a key of a call's answer (result.next for
    $next) is kept from the latest answer that has it."""
    res = answer.get("result") if isinstance(answer, dict) else None
    if isinstance(res, dict):
        for n in names:
            if n in res:
                vars_[n] = res[n]


def pick_steps(steps, wanted):
    """[(index, step)] for steps given by name or index (all when None)."""
    if wanted is None:
        return list(enumerate(steps))
    if not isinstance(wanted, list):
        wanted = [wanted]
    out = []
    for w in wanted:
        if isinstance(w, int) and not isinstance(w, bool):
            if not -len(steps) <= w < len(steps):
                raise ToolError("invalid_input", f"steps: {w} — the script has {len(steps)} steps (0 … {len(steps) - 1}).")
            i = w % len(steps)
        else:
            hits = [i for i, st in enumerate(steps) if st.get("name") == w]
            if not hits:
                raise ToolError("invalid_input", f"steps: no step named {w!r} — they are: " + "; ".join(f"{i} {st.get('name')}" for i, st in enumerate(steps)) + ".")
            i = hits[0]
        out.append((i, steps[i]))
    return out


def two_role(step):
    """Why a step needs two agents (a teacher and a student), or None."""
    if step.get("role") == "student":
        return "a student step (role: student): input as the person, sent by a second agent — needs two agents (ROLES.md)"
    if step.get("parallel"):
        return "parallel: its call waits while the next step runs — needs two agents (ROLES.md)"
    return None


def find_script(name, roots):
    """A script by name ("reset", "scanruler.json") in the scripts/live
    folders under roots, or None."""
    fn = name if name.lower().endswith(".json") else name + ".json"
    for r in roots:
        p = os.path.join(r, "scripts", "live", fn)
        if os.path.isfile(p):
            return p
    return None


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise ToolError("invalid_input", f"script: {os.path.basename(path)} could not be read as JSON ({e}).")
    if not isinstance(data, dict) or not isinstance(data.get("steps"), list):
        raise ToolError("invalid_input", f"script: {os.path.basename(path)} has no steps — the format is scripts/live/README.md's.")
    return data


def run(script, chosen, call, vars_=None, stop_on_fail=False, shot=None):
    """Replay the chosen steps. call(tool, arguments) answers one call's
    entry ({tool, ok, result | error}); batch(calls) is call("batch", …).
    shot(name) takes a window picture and answers its path or None."""
    vars_ = dict(vars_ or {})
    names = declared_vars(script)
    out, passed, failed, skipped = [], 0, 0, 0
    for i, st in chosen:
        rec = {"step": i, "name": st.get("name")}
        why = two_role(st)
        calls, missing = substitute(st.get("calls") or [], vars_)
        if why is None and missing:
            conv = script.get("conventions") or {}
            told = [f"{k}: {v}" for k, v in conv.items() if any(m in VAR.findall(k) for m in missing)]
            why = "needs " + ", ".join("$" + m for m in missing) + " — give vars { " + ", ".join(f"{m}: …" for m in missing) + " }" + (" (" + "; ".join(told) + ")" if told else "")
        if why:
            rec.update(result="skipped", why=why)
            skipped += 1
            out.append(rec)
            continue
        answers = []
        if st.get("direct"):
            for c in calls:
                ans = call(c.get("tool"), c.get("arguments") or {})
                answers.append(ans)
                capture(vars_, names, ans)
        else:
            b = call("batch", {"calls": calls, "rollback": False, "stopOnError": False})
            answers = (b.get("result") or {}).get("results") or [] if b.get("ok") else []
            if not b.get("ok"):
                rec["batchError"] = b.get("error")
            for ans in answers:
                capture(vars_, names, ans)
        checks = evaluate(answers, st.get("expect"))
        bad = [c for c in checks if not c["ok"]]
        refused = [{"call": k, "tool": a.get("tool"), "error": a.get("error")} for k, a in enumerate(answers) if not a.get("ok")]
        # A refused call fails its step, unless the step checks the refusal.
        meant = any(str(e.get("path", "")).split(".")[0] in ("error", "ok") for e in st.get("expect") or [])
        ok = not bad and "batchError" not in rec and (not refused or meant)
        rec["result"] = "pass" if ok else "fail"
        rec["checks"] = len(checks)
        if bad:
            rec["failed"] = bad
        if refused:
            rec["refused"] = refused
        if st.get("then"):
            rec["then"] = st["then"]
        if st.get("look"):
            rec["look"] = st["look"]
        if st.get("shot") and shot:
            p = shot(st["shot"])
            if p:
                rec["shot"] = p
        passed += ok
        failed += not ok
        out.append(rec)
        if not ok and stop_on_fail:
            break
    return {"script": script.get("name"), "steps": out, "total": {"passed": passed, "failed": failed, "skipped": skipped, "run": passed + failed}, "vars": vars_}
