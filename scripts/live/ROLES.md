# Two roles on one link: a teacher agent and a student agent

For scripts whose steps carry `role` (`tutor-watch.json`): an add-on that follows the person (the Tutor's watch mode, its lessons' `used` checks and milestones) is tested live by two agents on the same Agent Link. One agent teaches; the other stands in for the person.

## How it works

- The student adds `as: "person"` to every `gui_input`. The window events of that call (selection, commands, workbench switches, task panels, objects made, Ask Claude) and its `call_done` count as the person's.
- The teacher's calls stay the agent's: before, after and during the student's calls. Attribution follows each call; nothing is switched on for the whole link.
- `tutor_watch` is a long poll on the link's own thread. The teacher can wait in it while the student's `gui_input` runs. Never put a waiting `tutor_watch` in a `batch` (`direct: true` steps).

## Running it as two subagents

The main session starts both, in parallel, and gives each only its role's steps.

1. Main session: run `reset.json`.
2. Teacher subagent: gets the `role: "tutor"` steps, the `$next` rule, and (for a lesson) the lesson id. It may use every Agent Link and Tutor tool. It starts each `parallel` step's `tutor_watch` and tells the main session when it is waiting.
3. Student subagent: gets the `role: "student"` steps (or, for a lesson, only "follow the callout"). The main session relays "now" to the student when the teacher waits.
4. Main session: checks each `expect`, joins the two logs by time, and reports pass/fail per step.

### The student may

- Call `gui_input` with `as: "person"` only: `click`, `double`, `press`/`move`/`release`, `drag`, `scroll`, `key`, `type`, `menu_item`, `wait`, `shot`.
- Look at its own shots (the callout's words and rings, the status bar, the task panel) and read its own `gui_input` answers (what a step hit, what it selected, what is still open).
- Use the person's own controls in the window: the Tutor tab's Next, Back, Hint, Skip, Do it for me, Stop, Ask Claude and Let Claude watch.
- Make some mistakes on purpose: select the wrong face, push the wrong command, leave a panel open, Cancel instead of OK. These test hints, branches and "Do it for me".

### The student may not

- See a lesson file, the lesson's id, its steps or checks, or the teacher's answers.
- Call any tool but `gui_input` (no `tutor`, `tutor_watch`, `tutor_point`, `session_state`, document reads, `cmd_run`, `workbench` or `batch`).
- Use `gui_input` without `as: "person"`, or `gui_unstick` (a stuck menu: Escape, as a person would; if that fails, it tells the main session).

### The teacher may not

- Use `as: "person"`: its calls are the agent's.
- Tell the student what to do except through the window (the callout, `tutor_point`, the lesson's hints), as with a real person.

## One driver only

Without a second agent, the main session runs the steps in order and plays both roles. A `parallel` wait then comes after the student's step, with a short `wait`; it answers at once because the milestone is already there.
