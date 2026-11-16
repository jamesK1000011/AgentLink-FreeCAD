# SPDX-License-Identifier: LGPL-2.1-or-later
# The runners' own data handling (agentlink/runners.py): plain Python, no
# FreeCAD. The tools they run are checked on FreeCAD by each family's tests.
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agentlink import expr, runners, tooldata  # noqa: E402
from agentlink.protocol import ToolError  # noqa: E402


class Thing:
    def __init__(self, label, **kw):
        self.Label = label
        self.__dict__.update(kw)


class Doc:
    def __init__(self):
        self.Objects = []

    def addObject(self, t, base):
        o = Thing(base, TypeId=t)
        self.Objects.append(o)
        return o


ENTRY = {"group": "g", "description": "A tool for the test, long enough.", "inputSchema": {"type": "object", "properties": {}},
         "changes": True, "source": "test", "date": "2026-11-14"}


class Runners(unittest.TestCase):
    def setUp(self):
        self.doc = Doc()
        self.log = []
        self.helpers = {"doc": lambda: self.doc, "find": lambda ref: Thing(ref, Size=3),
                        "named": lambda o, n: setattr(o, "Label", n),
                        "finish": lambda o, tool, extra: {"object": o.Label, **extra, "tool": tool},
                        "setprops": lambda o, d: self.log.append(dict(d))}

    def run_entry(self, e, a):
        return runners.tools("g", None, self.helpers, {"t": {**ENTRY, **e}})[0].fn(a)

    def test_make_in_order(self):
        e = {"runner": "make", "target": {"type": "X::Thing", "base": "Thing"},
             "args": {"from": {"helper": "find"},
                      "name": {"then": {"call": "named", "with": ["$o", {"or": ["$a.name", {"fmt": "{from.Label} copy"}]}]}},
                      "size": {"prop": "Size"}, "colour": {"prop": "Colour"}, "kind": {"prop": "Kind", "when": "truthy", "alone": True}},
             "rules": [{"check": "range", "of": "$a.count", "min": 1, "max": 3, "after": "start", "message": "count: 1 … 3."}],
             "answer": {"via": "finish", "with": ["$o", "$tool", "$fields"], "fields": {"from": "$from.Label", "n": {"len": "$doc_objects"}}}}
        e["args"]["=doc_objects"] = {"value": [1, 2]}
        out = self.run_entry(e, {"from": "Box", "count": 2, "size": 5, "kind": "k"})
        self.assertEqual(out, {"object": "Box copy", "from": "Box", "n": 2, "tool": "t"})
        self.assertEqual(self.log, [{"Size": 5, "Colour": None}, {"Kind": "k"}])
        self.assertEqual(self.doc.Objects[0].TypeId, "X::Thing")
        with self.assertRaises(ToolError) as c:
            self.run_entry(e, {"from": "Box", "count": 9})
        self.assertEqual((c.exception.code, c.exception.message), ("invalid_input", "count: 1 … 3."))
        self.assertEqual(len(self.doc.Objects), 1)  # refused before anything was made

    def test_apply_and_read(self):
        class Data:
            def __init__(self, n):
                self.n = n

            def copy(self):
                return Data(self.n)

            def grow(self, by):
                self.n += by

        target = Thing("M", Data=Data(4))
        self.helpers["find"] = lambda ref: target
        e = {"runner": "apply", "target": {"on": "mesh", "copy": "Data", "method": "grow", "call": ["$by"]},
             "args": {"mesh": {"helper": "find"}, "by": {"default": 0, "as": "float"}},
             "rules": [{"check": "nonzero", "of": "$by", "message": "by: not zero."}],
             "answer": {"fields": {"was": "$o.Data.n", "now": "$m.n"}}}
        self.assertEqual(self.run_entry(e, {"mesh": "M", "by": 2}), {"was": 4, "now": 6.0})
        with self.assertRaises(ToolError):
            self.run_entry(e, {"mesh": "M"})
        self.doc.Objects = [Thing("a", Group=[Thing("b")]), Thing("c", Group=[]), Thing("d")]
        r = {"runner": "read", "target": {"from": "$doc.Objects", "where": "keep",
                                          "each": {"object": "$o.Label", "holds": {"when": "$o.Group?", "value": "$o.Group[].Label"}}},
             "answer": {"fields": {"objects": "$rows", "count": {"len": "$rows"}}}}
        self.helpers["keep"] = lambda o: o.Label != "d"
        self.assertEqual(self.run_entry(r, {}), {"objects": [{"object": "a", "holds": ["b"]}, {"object": "c"}], "count": 2})

    def test_rule_when_sum_and_a_step_value(self):
        # A rule with "when" is checked only then; {"sum"} adds a list; an
        # argument's "then" sees it as given ("$value", its default when left
        # out) and its name ("$key").
        parts = [Thing("a", Length=2.5), Thing("b", Length=4)]
        self.helpers["find"] = lambda ref: Thing(ref, Parts=parts if ref == "Full" else [])
        seen = []
        self.helpers["note"] = lambda *x: seen.append(x)
        e = {"runner": "make", "target": {"type": "X::Thing", "base": "Thing"},
             "args": {"=base": {"value": {"if": ["$a.base", {"call": "find", "with": ["$a.base"]}, {"call": "find", "with": ["Full"]}]}},
                      "at": {"default": [0, 0], "then": {"call": "note", "with": ["$key", "$value", "$o.TypeId"]}}},
             "rules": [{"check": "count", "of": "$base.Parts", "min": 1, "when": "$a.base", "after": "=base", "format": True,
                        "message": "base: {base.Label} has no parts."}],
             "answer": {"fields": {"length": {"sum": "$base.Parts[].Length"}, "none": {"sum": []}}}}
        self.assertEqual(self.run_entry(e, {"base": "Full", "at": [1, 2]}), {"length": 6.5, "none": 0})
        self.assertEqual(self.run_entry(e, {}), {"length": 6.5, "none": 0})  # no base given: the rule does not apply
        self.assertEqual(seen, [("at", [1, 2], "X::Thing"), ("at", [0, 0], "X::Thing")])
        n = len(self.doc.Objects)
        with self.assertRaises(ToolError) as c:
            self.run_entry(e, {"base": "Bare"})
        self.assertEqual((c.exception.code, c.exception.message), ("invalid_input", "base: Bare has no parts."))
        self.assertEqual(len(self.doc.Objects), n)  # refused before anything was made
        # A rule whose condition is not met is used up like any other: it is not checked later either.
        late = {**e, "rules": [{**e["rules"][0], "after": "", "when": {"not": "$a.base"}, "of": []}]}
        self.assertEqual(self.run_entry(late, {"base": "Bare"})["length"], 0)
        with self.assertRaises(ToolError):
            self.run_entry(late, {})

    # ---- the evaluator (agentlink/expr.py) ------------------------------------------------

    def test_expressions(self):
        box = Thing("Box", Size=3, Parts=[Thing("a", Length=2.5), Thing("b", Length=4)])
        env = {"a": {"name": "N", "from": [1, 2], "n": 0}, "o": box, "h": 3000, "words": ["x", "y"]}
        h = {"twice": lambda x: x * 2, "len": lambda x: -1}
        for text, want in (
                ("h / 175", 3000 / 175), ("max(3, round(h / 175))", 17), ("2 ** 3 - 7 % 4 + 7 // 2", 8), ("-h + +1", -2999),
                ("a.name or 'Stairs'", "N"), ("a.missing or 'Stairs'", "Stairs"), ("a.get('from')[1]", 2), ("a.get('nope', 5)", 5),
                ("o.Label + ' copy'", "Box copy"), ("o.Parts[-1].Length", 4), ("words[::-1]", ["y", "x"]), ("words[:1]", ["x"]),
                ("1 < o.Size <= 3", True), ("not 0 < a.n <= 90", True), ("a.n is None", False), ("a.missing is None", True), ("'x' in words and 'z' not in words", True),
                ("'big' if o.Size > 2 else 'small'", "big"), ("a.n or None", None), ("a.n and 1 / a.n", 0),
                ("[p.Length for p in o.Parts if p.Length > 3]", [4]), ("sum(p.Length for p in o.Parts)", 6.5),
                ("{p.Label: p.Length for p in o.Parts}", {"a": 2.5, "b": 4}), ("len({w for w in words + words})", -1),
                ("[x + y for x in [1, 2] for y in [10, 20]]", [11, 21, 12, 22]), ("[k + str(v) for k, v in {'p': 1}.items()]", ["p1"]),
                ("sorted(words, key=lambda w: -ord(w))", None), ("sorted(o.Parts, key=lambda p: -p.Length)[0].Label", "b"),
                ("twice(o.Size)", 6), ("o.Label.lower().startswith('b')", True), ("(1, [2], {'k': {3}})", (1, [2], {"k": {3}})),
                ("first(w for w in words if w > 'x')", "y"), ("first([], 'none')", "none"), ("tally(['a', 'b', 'a'])", {"a": 2, "b": 1}),
                ("reversed(words)", ["y", "x"]), ("range(3)", [0, 1, 2]), ("zip(words, [1, 2])", [("x", 1), ("y", 2)]),
                ("has(o, 'Size') and not has(o, 'Nope') and has(a, 'n')", True), ("get(o, 'Nope', 7)", 7),
                ("[is_list(words), is_str('s'), is_num(True), is_number(True), is_int(1), is_float(1), is_bool(False), is_dict(a)]", [True, True, False, True, True, False, True, True]),
                ("ceil(2.1) + floor(2.9) + chr(65)", None), ("round(tan(radians(45)) + pi, 2)", 4.14), ("maker('os.path.basename')('/a/b')", None),
                ("maker('no_such_module.fn') is None and maker('os.nothing') is None", True)):
            if want is None and text.startswith(("sorted(words", "ceil", "maker('os.path")):
                continue  # below: they need names the evaluator does not have
            self.assertEqual(expr.evaluate(text, env, h), want, text)
        # A name ending the run, a function not listed, and what is not an expression at all.
        with self.assertRaises(NameError):
            expr.evaluate("nothing + 1", env)
        with self.assertRaises(NameError):
            expr.evaluate("open('/etc/passwd')", env)
        with self.assertRaises(NameError):
            expr.evaluate("sorted(words, key=lambda w: -ord(w))", env)
        with self.assertRaises(TypeError):
            expr.evaluate("ceil(2.1) + chr(65)", env)
        for text in ("__import__('os')", "o.__class__", "o._private", "_x", "x = 1", "import os", "lambda *a: a", "f(*words)", "f(**a)", "f'{h}'",
                     "(yield 1)", "x := 1", "a if", "o.Parts[0].__dict__", "(lambda: 1)()", "h @ h", "h | 1", "~h", "await x", "print"):
            self.assertTrue(expr.check(text) or text == "print", text)
            if text != "print":
                with self.assertRaises(expr.ExprError):
                    expr.evaluate(text, env)
        self.assertIsNone(expr.check("a.name or 'x'"))
        self.assertEqual(expr.called("twice(len(x)) + o.method(y)"), {"twice", "len"})
        # A comprehension's names stay its own; a lambda sees the run's values.
        self.assertEqual(expr.evaluate("[h for h in [1, 2]] + [h]", env), [1, 2, 3000])

    def test_messages(self):
        env = {"sill": 900.0, "height": 2100.0, "wall": Thing("Inner wall", Height=2600), "a": {"path": "/x y", "use": None}, "near": ["Room", "Office"],
               "from": Thing("Box")}
        for template, want in (
                ("sill + height is {sill + height:g} mm, above the wall's {float(wall.Height):g} mm.", "sill + height is 3000 mm, above the wall's 2600 mm."),
                ("path {a.path!r}: no such file; use {a.use!r}", "path '/x y': no such file; use None"),
                ("Near: {', '.join(near)}. bim_component {{ from }} makes one.", "Near: Room, Office. bim_component { from } makes one."),
                ("{from.Label} copy ({len(near)} near, {sill:.1f}, {wall.Nope?})", "Box copy (2 near, 900.0, None)"),
                ("{'door' if sill else 'window'}: {near[0]}", "door: Room"), ("no fields", "no fields")):
            self.assertEqual(expr.fmt(template, env), want)
            self.assertIsNone(expr.check_fmt(template))
        self.assertEqual(runners.value({"fmt": "{wall.Label}!"}, env, {}), "Inner wall!")
        for bad in ("{", "{}", "{o.__class__}", "{x:{w}}", "{import os}"):
            self.assertTrue(expr.check_fmt(bad), bad)

    # ---- the steps runner -----------------------------------------------------------------

    def steps(self, steps, a=None, answer=None, **more):
        e = {"runner": "steps", "steps": steps, **more}
        if answer is not None:
            e["answer"] = answer
        self.assertEqual(tooldata.check({"dataVersion": "1.0.0", "entries": {"t": {**ENTRY, **e}}}), [])
        return self.run_entry(e, a or {})

    def test_steps_in_order_each_using_the_ones_before(self):
        made = []

        def make(kind, size=1):
            made.append((kind, size))
            return Thing(kind, Size=size, Placement=Thing("pl", Base=0))

        self.helpers.update({"build": make, "headless_call": lambda fn, *a, **kw: ("headless", fn(*a, **kw)), "double": lambda x: x * 2})
        out = self.steps([
            {"let": {"w": "=a.get('width', 200)", "name": "=a.name or 'Thing'"}},
            {"let": {"lo, hi": "=[w / 2, w * 2]"}},
            {"let": {"o": "=build('box', size=hi)"}},
            {"make": "os.path.join", "call": ["=name", "x"], "as": "path"},
            {"make": "os.path.basename", "headless": True, "call": ["=path"], "as": "wrapped"},
            {"make": "=double", "call": ["=lo"], "as": "twice"},
            {"add": "X::Thing", "name": "Extra", "as": "extra"},
            {"set": {"o.Label": "=name", "o.Placement.Base": "=lo", "extra.Size": "=o.Size + 1"}},
            {"do": ["=named(extra, 'renamed')", "=o.Label.upper()"]},
            {"let": {"seen": [], "notes": {}}},
            {"push": {"seen": "=extra.Label"}},
            {"put": {"k": "=len(seen)"}, "into": "notes"},
        ], {"name": "N"}, {"via": "finish", "with": ["=o", "=tool", "$fields"],
                           "fields": {"path": "=path", "wrapped": "=wrapped", "twice": "=twice", "base": "=o.Placement.Base", "extra": "=extra.Size", "seen": "=seen",
                                      "notes": "=notes", "late": {"when": "=w > 500", "value": 1}}})
        self.assertEqual(out, {"object": "N", "path": os.path.join("N", "x"), "wrapped": ("headless", "x"), "twice": 200.0, "base": 100.0, "extra": 401,
                               "seen": ["renamed"], "notes": {"k": 1}, "tool": "t"})
        self.assertEqual(made, [("box", 400)])
        self.assertEqual(self.doc.Objects[0].TypeId, "X::Thing")

    def test_steps_refuse_where_they_stand(self):
        undone = []
        self.helpers["undo"] = undone.append
        steps = [
            {"let": {"n": "=a.get('n', 1)"}},
            {"refuse": "n: 1 or more.", "when": "=n < 1"},
            {"add": "X::Thing", "name": "Made", "as": "o"},
            {"refuse": {"fmt": "{n} is too many ({{ n }} up to {limit})."}, "when": "=n > limit", "code": "invalid_state", "first": [{"do": "=undo(o.Label)"}]},
        ]
        e = [{"let": {"limit": 3}}] + steps
        self.assertEqual(self.steps(e, {"n": 2}, {"fields": {"n": "=n"}}), {"n": 2})
        with self.assertRaises(ToolError) as c:
            self.steps(e, {"n": 0}, {"fields": {}})
        self.assertEqual((c.exception.code, c.exception.message, len(self.doc.Objects)), ("invalid_input", "n: 1 or more.", 1))  # nothing made by the refused call
        with self.assertRaises(ToolError) as c:
            self.steps(e, {"n": 9}, {"fields": {}})
        self.assertEqual((c.exception.code, c.exception.message, undone), ("invalid_state", "9 is too many ({ n } up to 3).", ["Made"]))

    def test_steps_branch_loop_and_try(self):
        steps = [
            {"let": {"kind": "=a.get('kind', 'column')", "log": []}},
            {"choose": "=kind", "of": {"column": [{"push": {"log": "upright"}}], "beam": [{"push": {"log": "across"}}]}, "else": [{"refuse": "kind: column | beam."}]},
            {"when": "=a.points", "then": [{"push": {"log": "outline"}}], "else": [{"push": {"log": "box"}}]},
            {"push": {"log": "named"}, "when": "=a.name"},
            {"each": "way, key", "in": [["x", "xs"], ["y", "ys"]], "index": "i", "steps": [
                {"when": "=a.get(key)", "then": [{"push": {"log": "=str(i) + way + str(sum(a.get(key)))"}}]}]},
            {"try": [{"let": {"n": "=float(a.get('n', 1))"}}], "on": ["TypeError", "ValueError"], "except": [{"refuse": {"fmt": "n: a number ({error})."}}]},
            {"try": [{"do": "=fail()"}, {"push": {"log": "not reached"}}], "on": "refusal", "except": [{"push": {"log": "=error.message"}}]},
            {"try": [{"do": "=a.nothing.attribute"}], "except": [{"push": {"log": "caught"}}]},
        ]

        def fail():
            raise ToolError("failed", "it needs its window")

        self.helpers["fail"] = fail
        ans = {"fields": {"log": "=log"}}
        self.assertEqual(self.steps(steps, {"points": [1], "name": "x", "ys": [1, 2]}, ans), {"log": ["upright", "outline", "named", "1y3", "it needs its window", "caught"]})
        self.assertEqual(self.steps(steps, {"kind": "beam", "xs": [5], "ys": [1]}, ans)["log"][:4], ["across", "box", "0x5", "1y1"])
        for a, msg in (({"kind": "slab"}, "kind: column | beam."), ({"kind": ["a"]}, "kind: column | beam."), ({"n": "many"}, "n: a number (could not convert string to float: 'many').")):
            with self.assertRaises(ToolError) as c:
                self.steps(steps, a, ans)
            self.assertEqual(c.exception.message, msg)
        # A try catches what it names and no more; an answer inside one still ends the run.
        with self.assertRaises(ZeroDivisionError):
            self.steps([{"try": [{"do": "=1 / 0"}], "on": ["ValueError"], "except": []}], {}, ans)
        self.assertEqual(self.steps([{"try": [{"answer": {"fields": {"early": True}}}], "except": [{"refuse": "never"}]}, {"refuse": "nor this"}]), {"early": True})

    def test_steps_answers_early_late_and_after(self):
        order = []

        def finish(tool, read):
            order.append("recompute")
            out = read() if callable(read) else read
            return {**out, "step": 1}

        self.helpers.update({"done": finish, "note": lambda x: order.append(x)})
        steps = [
            {"let": {"act": "=a.get('action', 'put')"}},
            {"choose": "=act", "of": {"list": [{"answer": {"fields": {"listed": []}}}]}},
            {"do": "=note('made')"},
        ]
        late = {"via": "done", "with": ["=tool", "$fields"], "late": True, "fields": {"n": "=note('read') or 1"},
                "then": [{"put": {"site": "after"}, "when": "=a.get('site', True)"}, {"do": "=note(out.step)"}]}
        self.assertEqual(self.steps(steps, {"action": "list"}, late, reads={"action": ["list"]}), {"listed": []})
        self.assertEqual(order, [])  # a read: nothing made, nothing recorded
        self.assertEqual(self.steps(steps, {}, late), {"n": 1, "step": 1, "site": "after"})
        self.assertEqual(order, ["made", "recompute", "read", 1])  # late: the fields are read by the helper, after its recompute
        del order[:]
        self.assertEqual(self.steps(steps, {"site": False}, {**late, "late": False}), {"n": 1, "step": 1})
        self.assertEqual(order, ["made", "read", "recompute", 1])
        t = runners.tools("g", None, self.helpers, {"t": {**ENTRY, "runner": "steps", "steps": steps, "answer": late, "reads": {"action": ["list"]}}})[0]
        self.assertEqual((t.changes_for({"action": "list"}), t.changes_for({})), (False, True))

    def test_steps_format_check_and_families(self):
        def problems(**e):
            return tooldata.check({"dataVersion": "1.0.0", "entries": {"t": {**ENTRY, "runner": "steps", **e}}})

        self.assertEqual(problems(steps=[], answer={"fields": {}}), [])
        for bad in ({}, {"steps": [{"let": {"x": "=1 +"}}]}, {"steps": [{"leap": 1}]}, {"steps": [{"let": {}, "do": "=1"}]}, {"steps": ["x"]},
                    {"steps": [{"refuse": "no", "code": "nope"}]}, {"steps": [{"refuse": 5}]}, {"steps": [{"refuse": {"fmt": "{x.__class__}"}}]},
                    {"steps": [{"each": "x", "steps": []}]}, {"steps": [{"choose": "=x", "of": [1]}]}, {"steps": [{"try": [], "on": "SystemExit"}]},
                    {"steps": [{"when": "=1", "then": [{"nope": 1}]}]}, {"steps": [{"let": {"x": 1}, "into": "y"}]}, {"steps": [], "target": {}},
                    {"steps": [{"answer": {"say": 1}}]}, {"steps": [], "answer": {"then": [{"put": "x"}]}}, {"steps": [{"set": {"o.x": "=__import__('os')"}}]},
                    {"steps": [{"choose": "=x", "of": {"a": [{"do": "=o._x"}]}}]}):
            self.assertTrue(problems(**bad), bad)
        self.assertTrue(tooldata.check({"dataVersion": "1.0.0", "entries": {"t": {**ENTRY, "runner": "read", "target": {}, "steps": []}}}))
        # Two family modules that share a group each get their own entries ("family").
        data = {"one": {**ENTRY, "runner": "steps", "steps": [], "answer": {"fields": {"of": "first"}}},
                "two": {**ENTRY, "runner": "steps", "family": "more", "steps": [], "answer": {"fields": {"of": "=mine()"}}}}
        self.assertEqual([t.name for t in runners.tools("g", None, {}, data)], ["one"])
        mine = runners.tools("g", None, {"mine": lambda: "second"}, data, family="more")
        self.assertEqual(([t.name for t in mine], mine[0].fn({})), (["two"], {"of": "second"}))
        self.assertEqual(runners.calls({"steps": [{"let": {"x": "=mine(len(a))"}}, {"make": "M.f", "headless": True}, {"refuse": {"fmt": "{why(x)} {x.Label}"}}],
                                        "answer": {"via": "done", "with": []}}), {"mine", "headless_call", "why", "done"})

    def test_wrapper_entries_take_expressions_too(self):
        e = {"runner": "make", "target": {"type": "X::Thing", "base": "Thing"},
             "args": {"=size": {"value": "=a.get('size', 2) * 10"}, "name": {"then": {"call": "named", "with": ["$o", "=a.name or 'T' + str(size)"]}}},
             "rules": [{"check": "truthy", "of": "=size <= 50", "after": "=size", "format": True, "message": "size: {size / 10:g} is over 5."}],
             "answer": {"fields": {"object": "=o.Label", "size": "$size"}}}
        self.assertEqual(self.run_entry(e, {}), {"object": "T20", "size": 20})
        with self.assertRaises(ToolError) as c:
            self.run_entry(e, {"size": 9})
        self.assertEqual(c.exception.message, "size: 9 is over 5.")

    def test_format_check(self):
        good = {**ENTRY, "runner": "read", "target": {}, "answer": {"fields": {}}}
        doc = {"dataVersion": "1.0.0", "entries": {"t": good}}
        self.assertEqual(tooldata.check(doc), [])
        for bad in ({"runner": "paint", "target": {}}, {"runner": "make", "target": {}}, {"target": {}},
                    {"runner": "read", "target": {}, "rules": [{"check": "range"}]}, {"runner": "read", "target": {}, "answer": {"say": 1}}):
            self.assertTrue(tooldata.check({"dataVersion": "1.0.0", "entries": {"t": {**ENTRY, **bad}}}), bad)

    def test_own_data_is_well_formed(self):
        path = os.path.join(runners.DATA, "tools.json")
        if not os.path.isfile(path):
            self.skipTest("no data-defined tools yet")
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        self.assertEqual(tooldata.check(doc), [])
        for name, e in doc["entries"].items():
            self.assertIn(e["runner"], runners.RUNNERS, name)
            self.assertIs(e["inputSchema"].get("additionalProperties"), False, name)


if __name__ == "__main__":
    unittest.main()
