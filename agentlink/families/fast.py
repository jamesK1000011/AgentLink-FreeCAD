# SPDX-License-Identifier: LGPL-2.1-or-later
# The fast path (efficiency design C6, A6) and targeted reads (22 Nov): an
# extra way in for an agent that already knows what it does. The full
# answers and the guided workflow stay as they are. The work is in
# agentlink/fastpath.py; here are the two tools and their cards. Not in the
# lean or static base list: tool_find finds them.

from .. import fastpath
from ..protocol import Tool

GROUP = "fast"
INFO = "The fast path: fast runs a block of steps in one call and gives one short answer; get reads one value with its unit."


def tools(session):
    def fast(a):
        return fastpath.fast_tool(session.server, session, a)

    def get(a):
        return fastpath.get_tool(session.server, session, a)

    return [
        Tool("fast", ("Run a block of steps in one call, and get one short answer. Use it when you know the work. "
                      "do: [steps]. A step is { call: tool, its fields, as: name }, { let: { name: value } }, { each: name, in: list, steps }, "
                      "{ when: test, then, else }, { choose: value, of, else }, { try, on: refusal | error, except }, { get: \"Pad.Length\", as }, "
                      "{ push } or { refuse: words }. "
                      "A value \"=x * 2\" is an expression of names, numbers, lists and their own methods. It is not Python code. "
                      "A call's answer is its as name, and last. "
                      "Each call goes through the normal input checks, refusals, approvals and undo step of its tool. "
                      "The answer is one line: calls, time, objects made, the volume change and the health. "
                      "values has the value of each get. warnings has only what is not clean. "
                      "A required field that you leave out comes from the current body, sketch or last result. "
                      "A body or sketch field that you leave out comes from what the block made. filled names each of them. "
                      "Before step 1, each step is checked: its fields, and its leading checks up to the first change. "
                      "A step that would refuse is refused by its number, and nothing runs. check: true does only this check. "
                      "If a call refuses, the block is undone as a whole, as batch does. The undo stops at a step of the person. "
                      "record is the file of each call's whole answer; batch { read, at } reads it. "
                      "A block does not run batch, jobs, gui_input, dialog_answer, the history tools, approvals or a restart. "
                      "The person's preference FastPath can turn it off."),
             {"type": "object", "properties": {"do": {"type": "array", "items": {"type": "object"}}, "check": {"type": "boolean"}},
                                 "required": ["do"], "additionalProperties": False}, fast),
        Tool("get", ("Read one value, and get only that value with its unit. "
                     "what: \"Pad.Length\" (a property), \"Body.volume\" (also area, mass, centerOfMass, size), "
                     "\"Body.Edge7.length\" (an edge or a face: length, radius, area), \"sketch.dof\" (also closedWires, readyForFeature), "
                     "\"active.body\", \"active.sketch\", \"selection\" or \"bodies\". "
                     "body and sketch in lower case are the current ones. what can be a list of up to 20. "
                     "Answer: { what: value }, for example { \"Body.volume\": \"1520 mm³\" }. "
                     "It uses the readers of object_get, measure, measure_mass and sketch_state. "
                     "Changes nothing. The person's preference FastPath can turn it off."),
             {"type": "object", "properties": {"what": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}},
                               "required": ["what"], "additionalProperties": False}, get),
    ]
