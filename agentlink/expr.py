# SPDX-License-Identifier: LGPL-2.1-or-later
"""The data tools' expressions: one small evaluator, shared by the runners'
rules, arguments, steps and answers (agentlink/runners.py).

A value in a tool's entry that is a string starting with "=" is an
expression: "=height / steps", "=a.name or 'Stairs'",
"=[e.Length for e in base.Shape.Edges]". It is written the way Python
writes it, and read with Python's own parser (ast.parse) so that it need
not be learnt; but nothing is ever given to eval or exec. evaluate() walks
the parsed tree itself and knows only what is listed here:

  values        numbers, strings, True, False, None, [lists], (tuples),
                {dicts}, {sets}
  names         a value of the run (an argument resolved, a step's result);
                "a" is the call's arguments; pi
  x.name        an attribute; of a dict, its item (None when it has none),
                so a.name is the argument "name". Names starting with "_"
                are refused.
  x[i] x[i:j]   an item or a slice
  arithmetic    + - * / // % **, and -x
  comparisons   == != < <= > >= in, not in, is, is not (chained too)
  logic         and, or, not, "x if cond else y"
  lists         [f(x) for x in xs if cond], the same for {sets}, {k: v} and
                (generators, made a list); lambda x: … (for sorted's key)
  calls         FUNCTIONS below by name, the family's helpers by name
                (helpers win), and a value's own methods: s.lower(),
                o.isDerivedFrom("Part::Feature")

Anything else (assignment, import, names with underscores in front,
f-strings, starred calls …) is a FormatError when the entry is loaded.

fmt(template, env, helpers) fills a message: "{name}" fields as
str.format has them, each field an expression, with !r and :spec
("{sill + height:g} mm", "{path!r}", "{', '.join(near)}"); "{{" and "}}"
are braces. A field may not itself hold ":" or "!" outside brackets (work
the value out in a step first).
"""
import ast
import math
import operator
import re
import string

__all__ = ["evaluate", "fmt", "check", "check_fmt", "FUNCTIONS", "ExprError"]


class ExprError(ValueError):
    """An expression the evaluator does not read (found when the entry is checked)."""


def _has(o, name):
    return name in o if isinstance(o, dict) else hasattr(o, name)


def _get(o, name, default=None):
    return o.get(name, default) if isinstance(o, dict) else getattr(o, name, default)


def _tally(xs):
    """How many of each, in the order first met."""
    out = {}
    for x in xs:
        out[x] = out.get(x, 0) + 1
    return out


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _maker(dotted):
    """A module's function by its dotted name ("Arch.makeFence"), or None
    when this FreeCAD has no such module or function."""
    import importlib

    mod, _, fn = dotted.rpartition(".")
    try:
        return getattr(importlib.import_module(mod), fn, None)
    except ImportError:
        return None


# What an expression may call by name (a family's helpers come on top).
FUNCTIONS = {
    "len": len, "sum": sum, "round": round, "min": min, "max": max, "abs": abs,
    "int": int, "float": float, "str": str, "bool": bool, "repr": repr,
    "list": list, "tuple": tuple, "dict": dict, "set": set,
    "sorted": sorted, "reversed": lambda x: list(reversed(x)), "any": any, "all": all,
    "zip": lambda *x: list(zip(*x)), "enumerate": lambda x, start=0: list(enumerate(x, start)), "range": lambda *x: list(range(*x)),
    "ceil": math.ceil, "floor": math.floor, "sqrt": math.sqrt, "tan": math.tan, "radians": math.radians,
    "has": _has, "get": _get, "first": lambda xs, default=None: next(iter(xs), default), "tally": _tally, "chr": chr,
    "is_list": lambda x: isinstance(x, list), "is_str": lambda x: isinstance(x, str), "is_num": _is_num,
    "is_number": lambda x: isinstance(x, (int, float)),  # as Python has it: True and False count (is_num: they do not)
    "is_bool": lambda x: isinstance(x, bool), "is_dict": lambda x: isinstance(x, dict),
    "is_int": lambda x: isinstance(x, int) and not isinstance(x, bool), "is_float": lambda x: isinstance(x, float),
    "maker": _maker,
}

_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod, ast.Pow: operator.pow}
_CMP = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
        ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b, ast.Is: operator.is_, ast.IsNot: operator.is_not}
_UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Not: operator.not_}
_COMPS = (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)
_ALLOWED = (ast.Expression, ast.Constant, ast.Name, ast.Load, ast.Store, ast.Attribute, ast.Subscript, ast.Slice, ast.BinOp, ast.UnaryOp,
            ast.BoolOp, ast.And, ast.Or, ast.Compare, ast.IfExp, ast.List, ast.Tuple, ast.Dict, ast.Set, ast.Call, ast.keyword,
            ast.comprehension, ast.Lambda, ast.arguments, ast.arg, *_COMPS, *_BIN, *_CMP, *_UNARY)

_parsed = {}


def parse(text):
    """text's tree, checked once: only what the evaluator knows."""
    tree = _parsed.get(text)
    if tree is not None:
        return tree
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except SyntaxError as e:
        raise ExprError(f"{text!r}: {e.msg}") from None
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise ExprError(f"{text!r}: {type(node).__name__} is not part of the expressions")
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise ExprError(f"{text!r}: .{node.attr} is private")
        if isinstance(node, ast.Name) and node.id.startswith("_"):
            raise ExprError(f"{text!r}: {node.id} is private")
        if isinstance(node, ast.Call) and not isinstance(node.func, (ast.Name, ast.Attribute)):
            raise ExprError(f"{text!r}: a call is of a name or a value's method")
        if isinstance(node, ast.Call) and any(isinstance(x, ast.Starred) for x in node.args) or isinstance(node, ast.keyword) and node.arg is None:
            raise ExprError(f"{text!r}: no * or ** in a call")
        if isinstance(node, ast.Lambda):
            g = node.args
            if g.vararg or g.kwarg or g.kwonlyargs or g.defaults or g.posonlyargs:
                raise ExprError(f"{text!r}: a lambda takes plain names only")
    _parsed[text] = tree
    return tree


def called(text):
    """The names text calls as functions (to check them against the helpers)."""
    return {n.func.id for n in ast.walk(parse(text)) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}


def check(text):
    """What is wrong with an expression, or None."""
    try:
        parse(text)
    except ExprError as e:
        return str(e)
    return None


def evaluate(text, env, helpers=None):
    """The value of an expression among env's values and the helpers."""
    return _ev(parse(text).body, env, helpers or {})


def _bind(target, v, env):
    if isinstance(target, ast.Name):
        env[target.id] = v
    else:  # a tuple or list of targets
        vals = list(v)
        if len(vals) != len(target.elts):
            raise ValueError(f"{len(target.elts)} names for {len(vals)} values")
        for t, x in zip(target.elts, vals):
            _bind(t, x, env)


def _loop(gens, env, h, emit):
    if not gens:
        emit(env)
        return
    g = gens[0]
    for x in _ev(g.iter, env, h):
        _bind(g.target, x, env)
        if all(_ev(c, env, h) for c in g.ifs):
            _loop(gens[1:], env, h, emit)


def _ev(n, env, h):
    t = type(n)
    if t is ast.Constant:
        return n.value
    if t is ast.Name:
        if n.id in env:
            return env[n.id]
        if n.id in h:
            return h[n.id]  # a helper itself, to hand on (a maker chosen by input)
        if n.id == "pi":
            return math.pi
        raise NameError(f"{n.id}: not a value in this run")
    if t is ast.Attribute:
        x = _ev(n.value, env, h)
        return x.get(n.attr) if isinstance(x, dict) else getattr(x, n.attr)
    if t is ast.Subscript:
        x = _ev(n.value, env, h)
        s = n.slice
        if isinstance(s, ast.Slice):
            return x[slice(*[None if p is None else _ev(p, env, h) for p in (s.lower, s.upper, s.step)])]
        return x[_ev(s, env, h)]
    if t is ast.BinOp:
        return _BIN[type(n.op)](_ev(n.left, env, h), _ev(n.right, env, h))
    if t is ast.UnaryOp:
        return _UNARY[type(n.op)](_ev(n.operand, env, h))
    if t is ast.BoolOp:
        v = None
        for x in n.values:
            v = _ev(x, env, h)
            if bool(v) is isinstance(n.op, ast.Or):
                return v
        return v
    if t is ast.Compare:
        left = _ev(n.left, env, h)
        for op, right in zip(n.ops, n.comparators):
            right = _ev(right, env, h)
            if not _CMP[type(op)](left, right):
                return False
            left = right
        return True
    if t is ast.IfExp:
        return _ev(n.body, env, h) if _ev(n.test, env, h) else _ev(n.orelse, env, h)
    if t is ast.List:
        return [_ev(x, env, h) for x in n.elts]
    if t is ast.Tuple:
        return tuple(_ev(x, env, h) for x in n.elts)
    if t is ast.Set:
        return {_ev(x, env, h) for x in n.elts}
    if t is ast.Dict:
        return {_ev(k, env, h): _ev(v, env, h) for k, v in zip(n.keys, n.values)}
    if t is ast.Call:
        f = n.func
        if isinstance(f, ast.Name):
            fn = h.get(f.id) or FUNCTIONS.get(f.id)
            if fn is None and callable(env.get(f.id)):
                fn = env[f.id]  # a lambda's own argument, or a maker kept by a step
            if fn is None:
                raise NameError(f"{f.id}(): not a function of the expressions nor a helper of this family")
        else:
            fn = getattr(_ev(f.value, env, h), f.attr)  # a value's own method (never a dict's item)
        return fn(*[_ev(x, env, h) for x in n.args], **{k.arg: _ev(k.value, env, h) for k in n.keywords})
    if t is ast.Lambda:
        names = [x.arg for x in n.args.args]
        return lambda *xs: _ev(n.body, {**env, **dict(zip(names, xs))}, h)
    if t in _COMPS:
        local, out = dict(env), []
        if t is ast.DictComp:
            _loop(n.generators, local, h, lambda e: out.append((_ev(n.key, e, h), _ev(n.value, e, h))))
            return dict(out)
        _loop(n.generators, local, h, lambda e: out.append(_ev(n.elt, e, h)))
        return set(out) if t is ast.SetComp else out
    raise ExprError(f"{type(n).__name__} is not part of the expressions")


# ---- messages ------------------------------------------------------------------------------

_PLAIN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*\??)*$")  # no name with "_" in front: those are refused
_fields = {}


def _split(template):
    parts = _fields.get(template)
    if parts is None:
        try:
            parts = _fields[template] = list(string.Formatter().parse(template))
        except ValueError as e:
            raise ExprError(f"{template!r}: {e}") from None
    return parts


def _plain(path, env):
    """"base.Label", as str.format reads it (a word Python keeps, such as
    "from", may be a value's name here)."""
    parts = path.split(".")
    if parts[0] not in env:
        raise NameError(f"{parts[0]}: not a value in this run")
    x = env[parts[0]]
    for k in parts[1:]:
        if k.endswith("?"):
            x = getattr(x, k[:-1], None)
        else:
            x = x.get(k) if isinstance(x, dict) else getattr(x, k)
    return x


def fmt(template, env, helpers=None):
    """template with its {fields} filled from the run's values."""
    out = []
    for text, field, spec, conv in _split(template):
        out.append(text)
        if field is None:
            continue
        v = _plain(field, env) if _PLAIN.match(field) else evaluate(field, env, helpers)
        if conv == "r":
            v = repr(v)
        elif conv == "s":
            v = str(v)
        elif conv == "a":
            v = ascii(v)
        out.append(format(v, spec or ""))
    return "".join(out)


def check_fmt(template):
    """What is wrong with a message template, or None."""
    try:
        for _, field, spec, _conv in _split(template):
            if field is None:
                continue
            if not field.strip():
                return f"{template!r}: an empty {{}} field"
            if spec and "{" in spec:
                return f"{template!r}: a field inside a format spec"
            if not _PLAIN.match(field):
                parse(field)
    except ExprError as e:
        return str(e)
    return None
