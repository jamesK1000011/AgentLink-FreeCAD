# SPDX-License-Identifier: LGPL-2.1-or-later
"""One call shape for batch calls and fast steps (owner decisions 1 and 3,
23 Nov): { tool, arguments }, every input inside arguments.

A batch call may also have writeTo (its answer to a file); a fast step may
also have as and when. Nothing else stands beside tool:

  * an exact field of the tool's card is moved into arguments, and the
    answer says so (readAs). This is no guess: the name is the card's own
    and the value is the agent's; only the nesting was wrong.
  * the same field also inside arguments with the same value: the copy is
    dropped and said; with another value: refused.
  * a wrapper ("options", "params" …) or an unknown key: refused, with the
    keys named and the right form.
  * "tool" only inside arguments: refused, with where it goes.
  * the old fast form { call, … }: refused, no alias (rule R5).

Plain Python: reads the tools' schemas only."""

EXAMPLE = '{ "tool": "sketch_new", "arguments": { "plane": "XY" } }'


def card_fields(server, name):
    t = getattr(server, "tools", {}).get(name) if isinstance(name, str) else None
    if t is None:
        return None
    return list(((getattr(t, "schema", None) or {}).get("properties") or {}))


class Refused(Exception):
    def __init__(self, words):
        super().__init__(words)
        self.words = words


def _show(v):
    import json

    try:
        t = json.dumps(v, ensure_ascii=False)
    except (TypeError, ValueError):
        t = repr(v)
    return t if len(t) <= 40 else t[:37] + "…"


def split(server, c, where, extra=(), runner="batch"):
    """(tool, arguments, readAs words or None) of one call, or Refused.
    c: the call as sent. extra: the step keys this runner takes beside tool
    and arguments. where: "calls.2" or "do.2". The arguments are not
    copied when nothing moves."""
    if not isinstance(c, dict):
        raise Refused(f"{where}: a call is an object, {EXAMPLE}.")
    if "call" in c and "tool" not in c:
        if runner == "fast":
            raise Refused(f"{where}: {{ call, … }} is the old form of a fast step. A tool step is "
                          f"{{ \"tool\": \"{c['call'] if isinstance(c['call'], str) else 'sketch_new'}\", \"arguments\": {{ … }}, \"as\": \"name\" }}, "
                          "the same as a batch call, with every input inside arguments.")
        raise Refused(f"{where}: call is not part of a batch call. A call has tool and arguments: {EXAMPLE}.")
    args = c.get("arguments")
    if "tool" not in c:
        if isinstance(args, dict) and isinstance(args.get("tool"), str):
            raise Refused(f"{where}: tool is inside arguments. tool goes beside arguments: "
                          f"{{ \"tool\": \"{args['tool']}\", \"arguments\": {{ … }} }}.")
        return None, args, None
    name = c["tool"]
    keys = [k for k in c if k not in ("tool", "arguments") and k not in extra]
    if not keys:
        return name, args, None
    fields = card_fields(server, name)
    label = f"{where} ({name})" if isinstance(name, str) else where
    if "as" in keys and runner == "batch":
        raise Refused(f"{label}: as is a key of fast steps, not of batch calls. To use this call's answer in a later call, "
                      f"give {{ \"$from\": {where.rsplit('.', 1)[-1]}, \"$at\": \"feature\" }} there.")
    if fields is None:
        return name, args, None  # no such tool: refused as not found, later
    if not isinstance(args, dict):
        args = {} if args is None else args
    if not isinstance(args, dict):
        return name, args, None
    bad = [k for k in keys if k not in fields]
    if bad:
        words = (f"{label}: {', '.join(bad)} {'is' if len(bad) == 1 else 'are'} not part of a call. A call has tool and arguments only. "
                 f"Put the inputs inside arguments: {{ \"tool\": \"{name}\", \"arguments\": {{ … }} }}. "
                 f"The fields of {name}: {', '.join(fields) or 'none'}.")
        for k in bad:
            v = c[k]
            if isinstance(v, dict):
                known = [x for x in v if x in fields]
                if known:
                    words += f" {k} holds {', '.join(known)}: put {'it' if len(known) == 1 else 'them'} inside arguments."
        raise Refused(words)
    moved, dropped = [], []
    out = dict(args)
    for k in keys:
        if k in out:
            if out[k] != c[k]:
                raise Refused(f"{label}: {k} is given twice (beside tool: {_show(c[k])}, in arguments: {_show(out[k])}). "
                              "Give it once, inside arguments.")
            dropped.append(k)
        else:
            out[k] = c[k]
            moved.append(k)
    said = []
    if moved:
        said.append(f"{where}: {', '.join(moved)} {'was' if len(moved) == 1 else 'were'} beside tool: read inside arguments")
    if dropped:
        said.append(f"{where}: {', '.join(dropped)} beside tool {'was' if len(dropped) == 1 else 'were'} the same as in arguments: dropped")
    return name, out, "; ".join(said) + ". Put every input inside arguments."
