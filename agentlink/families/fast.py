# SPDX-License-Identifier: LGPL-2.1-or-later
# The fast path (efficiency design C6, A6) and targeted reads (22 Nov): an
# extra way in for an agent that already knows what it does. The full
# answers and the guided workflow stay as they are. The work is in
# agentlink/fastpath.py; here are the two tools and their cards. Not in the
# lean or static base list: tool_find finds them. run is the exception:
# it is listed with the base (agentlink/staticbase.py).

import copy
import json

from .. import callshape, fastpath, staticbase
from ..protocol import Tool, ToolError

GROUP = "fast"
INFO = "The fast path: run runs one step; fast runs many steps and gives one short answer; get reads one value with its unit."

STEP = '{ "tool": "pd_pad", "sketch": "Sketch", "length": 6 }'
STEP_SCHEMA = copy.deepcopy(staticbase._STEP_ITEM)


# run takes the same calls list as batch and fast, with one step in use (27 Nov).
RUN_SCHEMA = copy.deepcopy(staticbase.LISTED_SCHEMAS["run"])


def tools(session):
    def fast(a):
        return fastpath.fast_tool(session.server, session, a)

    def get(a):
        return fastpath.get_tool(session.server, session, a)

    def run(a):
        # run goes through Server.call, which puts the step through the named
        # tool (callshape.run_call). This handler is for a caller that does not.
        r = callshape.run_call(session.server, {"name": "run", "arguments": a})
        body = json.loads(r["content"][0]["text"])
        if r.get("isError"):
            err = body.get("error") or {}
            raise ToolError(err.get("code", "failed"), err.get("message", "run was refused"))
        return body

    return [
        Tool("run", ("Run one call, and get its full answer. run, batch and fast take the same calls list: calls: [step]. "
                     "A step is the tool's name in tool, and its inputs beside it. "
                     "Example: run { \"calls\": [ { \"tool\": \"pd_pad\", \"sketch\": \"Sketch\", \"length\": 6 } ] }. "
                     "The answer is the answer of a direct call of that tool, with the same checks, approvals and undo step. "
                     "run runs the first step only. A step after it is not run and not checked. The answer has a notice that says so. "
                     "each: { x: [15, 45] } on the step runs it once for each value, as a batch does. The answer is then the batch's. \"$x\" in the inputs is the value. "
                     "run does not run approve_file, approve_code, batch or fast: call them by their own names. "
                     "The answer ends with now: the names in each body as they are, by label. Example: \"now\": { \"Body\": [\"Sketch→Pad\"] }. "
                     "A refusal has a kind: fixable, retry or stop. fixable: the message names what to change. retry: the cause is not in the call. "
                     "For many calls in one request, use batch (a full answer for each call) or fast (one short answer)."),
             copy.deepcopy(RUN_SCHEMA), run),
        Tool("fast", ("Run many calls in one request, and get one short answer. The answer ends with now: the names in each body as they are, by label. Example: \"now\": { \"Body\": [\"Sketch→Pad\"] }. For one call, use run. For a full answer for each call, use batch. "
                      "calls: [steps]. A step is the same as a batch step: the tool's name in tool, and its inputs beside it. Example: { \"tool\": \"pd_pad\", \"sketch\": \"Sketch\", \"length\": 6 }. "
                      "each: { x: [15, 45] } runs the step once for each value, in order; \"$x\" in the inputs is the value, also inside a list. "
                      "{ \"$from\": 2, \"$at\": \"height\" } takes a value from the answer of call 2 of this block. Calls count from 0. Each pass of each is one call. "
                      "A read is the tool get: { tool: \"get\", what: \"Body.volume\" }. "
                      "Each call goes through the normal input checks, refusals, approvals and undo step of its tool. "
                      "The answer is one line: calls, time, objects made, the volume change and whether FreeCAD reports a recompute error. "
                      "made lists each object made: its name (later calls take it), label and type. "
                      "checks has the main results of body_check, doc_save, doc_close, measure and other *_check steps. "
                      "The volume change is of the document the block started in, while it is open. "
                      "values has the value of each get. warnings has each warning of a call, and the health's facts of a call with a recompute error. "
                      "A required field that you leave out comes from the current body, sketch or last result. "
                      "A body or sketch field that you leave out comes from what the block made. filled names each of them. "
                      "Before step 1, each step is checked: its fields, and its leading checks up to the first change. "
                      "A step that would refuse is refused by its number, and nothing runs. check: true does only this check. "
                      "If a call refuses, the block stops there. The calls before it stay, as in batch: each is its own undo step. "
                      "The refusal names the steps that ran before it, and from which step to go on in a new block. "
                      "keep: true is the same as the default. rollback: true undoes the whole block instead. The undo stops at a step of the person. "
                      "record is the file of each call's whole answer; record_read { path, at } reads it. "
                      "A block does not run batch, run, jobs, gui_input, dialog_answer, the history tools, approvals or a restart. "
                      "The person's preference FastPath can turn it off."),
             {"type": "object", "properties": {"calls": {"type": "array", "items": dict(STEP_SCHEMA)}, "check": {"type": "boolean"}, "keep": {"type": "boolean"},
                                               "rollback": {"type": "boolean"}},
              "required": ["calls"], "additionalProperties": False}, fast),
        Tool("get", ("Read one value, and get only that value with its unit. "
                     "what: \"Pad.Length\" (a property), \"Body.volume\" (also area, mass, centerOfMass, size), "
                     "\"Body.Edge7.length\" (an edge or a face: length, radius, area), \"sketch.dof\" (also closedWires, wiresMeet), "
                     "\"active.body\", \"active.sketch\", \"selection\" or \"bodies\". "
                     "body and sketch in lower case are the current ones. what can be a list of up to 20. "
                     "Answer: { what: value }, for example { \"Body.volume\": \"1520 mm³\" }. In a list, a value that cannot be read goes in missed, with why. "
                     "It uses the readers of object_get, measure, measure_mass and sketch_state. "
                     "Changes nothing. The person's preference FastPath can turn it off."),
             {"type": "object", "properties": {"what": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]}},
                               "required": ["what"], "additionalProperties": False}, get),
    ]
