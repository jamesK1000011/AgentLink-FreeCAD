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
                      "do: [steps]. A tool step is { tool, arguments, as: name }, the same as a batch call: every input goes inside arguments. "
                      "Other steps: { let: { name: value } }, { each: name, in: list, steps }, "
                      "{ when: test, then, else }, { choose: value, of, else }, { try, on: refusal | error, except }, { get: \"Pad.Length\", as }, "
                      "{ push } or { refuse: words }. "
                      "A value \"=x * 2\" is an expression of names, numbers, lists and their own methods. It is not Python code. "
                      "A call's answer is its as name, and last. "
                      "Each call goes through the normal input checks, refusals, approvals and undo step of its tool. "
                      "The answer is one line: calls, time, objects made, the volume change and the health. "
                      "made lists each object made: its name (later calls take it), label and type. "
                      "checks has the main results of body_check, doc_save, doc_close, measure and other *_check steps. "
                      "The volume change is of the document the block started in, while it is open. "
                      "values has the value of each get. warnings has only what is not clean. "
                      "A required field that you leave out comes from the current body, sketch or last result. "
                      "A body or sketch field that you leave out comes from what the block made. filled names each of them. "
                      "Before step 1, each step is checked: its fields, and its leading checks up to the first change. "
                      "A step that would refuse is refused by its number, and nothing runs. check: true does only this check. "
                      "If a call refuses, the block stops there. The calls before it stay, as in batch: each is its own undo step. "
                      "The refusal names the steps that ran before it, and from which step to go on in a new block. "
                      "keep: true is the same as the default. rollback: true undoes the whole block instead. The undo stops at a step of the person. "
                      "record is the file of each call's whole answer; record_read { path, at } reads it. "
                      "A block does not run batch, jobs, gui_input, dialog_answer, the history tools, approvals or a restart. "
                      "The person's preference FastPath can turn it off."),
             {"type": "object", "properties": {"do": {"type": "array", "items": {"type": "object"}}, "check": {"type": "boolean"}, "keep": {"type": "boolean"}, "rollback": {"type": "boolean"}},
                                 "required": ["do"], "additionalProperties": False}, fast),
        Tool("get", ("Read one value, and get only that value with its unit. "
                     "what: \"Pad.Length\" (a property), \"body.volume\" (also area, mass, centerOfMass, size), "
                     "\"body.Edge7.length\" (an edge or a face: length, radius, area), \"sketch.dof\" (also closedWires, readyForFeature), "
                     "\"active.body\", \"active.sketch\", \"selection\" or \"bodies\". "
                     "body and sketch in lower case are the current ones; any other name is an object's label or internal name. what can be a list of up to 20. "
                     "Answer: { what: value }, for example { \"body.volume\": \"1520 mm³\" }. In a list, a value that cannot be read goes in missed, with why. "
                     "readFrom names the object read when its label is not the name given or it is hidden. "
                     "It uses the readers of object_get, measure, measure_mass and sketch_state. "
                     "Changes nothing. The person's preference FastPath can turn it off."),
             {"type": "object", "properties": {"what": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}},
                               "required": ["what"], "additionalProperties": False}, get),
    ]
