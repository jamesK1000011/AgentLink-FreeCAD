# SPDX-License-Identifier: LGPL-2.1-or-later
# The owner's decisions of 18 Nov 2026 (docs/security/red-team-2026-11-18.md):
# 1. approvals are approve_file / approve_code, guarded by the client's own
#    tool permissions; the tools that need one answer pending and act once
#    it exists; only a direct call from the client approves.
# 2. an add-on never hides or replaces a hub tool or group.
# 3. an add-on install names source, version (commit or folder fingerprint)
#    and author; a new version needs a new approval.
# 4. no memory refusal before a job: the critical-pressure guard stops the
#    job alone at CRITICAL pressure (fakes for macOS and ps).
import io
import json
import os
import shutil
import sys
import tempfile
import time
import types
import unittest
from contextlib import redirect_stderr
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

from agentlink import approvals, hooks, memguard, person_ok  # noqa: E402
from agentlink.protocol import Server, Tool  # noqa: E402


def _server(extra=()):
    """A stand-in server with the two approval tools (bound as the hub binds
    them) and a batch that calls tools by name, as the hub's batch does."""
    def approve(name):
        def fn(a):
            try:
                return approvals.approve(name, a)
            except approvals.Refused as e:
                from agentlink.protocol import ToolError

                raise ToolError(e.code, e.message)
        return fn

    srv = Server("t", "0", [Tool(n, n, approvals.schema(n), approve(n)) for n in approvals.CLIENT_ONLY] + list(extra))

    def batch(a):
        out = []
        for c in a.get("calls") or []:
            r = srv.call({"name": c["tool"], "arguments": c.get("arguments") or {}})
            out.append(json.loads(r["content"][0]["text"]))
        return {"results": out}

    srv.add(Tool("batch", "batch", {"type": "object", "properties": {"calls": {"type": "array"}}}, batch))
    return srv


def client(srv, name, args):
    """A tools/call as the MCP client sends it (Server.handle)."""
    r = srv.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}})["result"]
    return bool(r.get("isError")), json.loads(r["content"][0]["text"])


class ClientApproval(unittest.TestCase):
    def setUp(self):
        approvals.reset()
        approvals.note_client(None, "claude-ai")  # a client that asks the person first
        person_ok.SHOW = None
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home, True)
        self.env = mock.patch.dict(os.environ, {"AGENTLINK_HOME": self.home})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(approvals.reset)

    def pending(self, kind="addon-install", name="Gears", fp="commit:abc", shown=None):
        r = approvals.ask(kind, name, f"Install the add-on {name}", ["x"], fp,
                          shown=shown or {"source": "https://example.org/Gears.git", "version": "commit abc", "author": "someone"})
        self.assertTrue(r["pending"])
        return r

    def test_pending_names_the_tool_and_its_exact_arguments(self):
        r = self.pending()
        a = r["approve"]["arguments"]
        self.assertEqual(r["approve"]["tool"], "approve_code")
        self.assertEqual((a["kind"], a["id"], a["fingerprint"], a["source"], a["version"], a["author"]),
                         ("addon-install", "Gears", "commit:abc", "host: example.org, path: /Gears.git", "commit abc", "someone"))
        self.assertIn("approve_code", r["next"])
        self.assertEqual(approvals.ask("recover", "Doc", "Save over", [], "fp")["approve"]["tool"], "approve_file")
        self.assertEqual(approvals.ask("save-all", "restart", "Save all", [], "fp")["approve"]["tool"], "approve_file")
        self.assertEqual(approvals.ask("dialog", "Unsaved Document", "Press Save", [], "fp")["approve"]["tool"], "approve_file")

    def test_the_client_approves_and_the_next_call_acts_once(self):
        srv = _server()
        r = self.pending()
        err, out = client(srv, "approve_code", r["approve"]["arguments"])
        self.assertFalse(err, out)
        self.assertTrue(out["approved"])
        self.assertEqual(approvals.ask("addon-install", "Gears", "Install", [], "commit:abc"), {"ok": True})
        # One approval, one action.
        self.assertTrue(approvals.ask("addon-install", "Gears", "Install", [], "commit:abc")["pending"])
        with open(os.path.join(self.home, "approvals.log")) as f:
            row = json.loads(f.readline())
        self.assertEqual((row["by"], row["id"]), ("client", "Gears"))

    def test_a_batch_a_job_or_a_direct_call_cannot_approve(self):
        srv = _server()
        args = self.pending()["approve"]["arguments"]
        err, out = client(srv, "batch", {"calls": [{"tool": "approve_code", "arguments": args}]})
        self.assertEqual(out["results"][0]["error"]["code"], "not_allowed")
        # A nested call (Server.call, as batch, cookbooks, lessons and the panel use).
        r = srv.call({"name": "approve_code", "arguments": args})
        self.assertTrue(r.get("isError"))
        with self.assertRaises(approvals.Refused):
            approvals.approve("approve_code", args)
        self.assertFalse(approvals.granted("addon-install", "Gears", "commit:abc"))

    def test_the_arguments_must_be_the_pending_ones(self):
        srv = _server()
        args = self.pending()["approve"]["arguments"]
        for bad in ({**args, "author": "someone else"}, {**args, "source": "https://evil.example/x.git"}, {**args, "button": "Save"},
                    {k: v for k, v in args.items() if k != "version"}):
            err, out = client(srv, "approve_code", bad)
            self.assertTrue(err, bad)
        err, out = client(srv, "approve_file", args)
        self.assertTrue(err)  # its schema has no source, version, author
        err, out = client(srv, "approve_file", {k: args[k] for k in ("kind", "id", "fingerprint", "what")})
        self.assertTrue(err)
        self.assertIn("approve_code", out["error"]["message"])
        err, out = client(srv, "approve_code", {**args, "id": "Other"})
        self.assertEqual(out["error"]["code"], "not_found")
        self.assertFalse(approvals.granted("addon-install", "Gears", "commit:abc"))

    def test_a_new_version_needs_a_new_approval(self):
        srv = _server()
        old = self.pending(fp="commit:abc")["approve"]["arguments"]
        # The add-on moved on before the approval: the tool asks again with the new commit.
        approvals.reset()
        approvals.note_client(None, "claude-ai")  # a client that asks the person first
        self.pending(fp="commit:def", shown={"source": "https://example.org/Gears.git", "version": "commit def", "author": "someone"})
        err, out = client(srv, "approve_code", old)
        self.assertEqual(out["error"]["code"], "invalid_state")
        self.assertIn("new version", out["error"]["message"])
        # Approved at abc; the install now sees def: no grant for it.
        approvals.reset()
        approvals.note_client(None, "claude-ai")  # a client that asks the person first
        a = self.pending(fp="commit:abc")["approve"]["arguments"]
        client(srv, "approve_code", a)
        self.assertTrue(approvals.ask("addon-install", "Gears", "Install", [], "commit:def")["pending"])

    def test_a_kept_approval_calls_on_ok(self):
        srv = _server()
        kept = []
        r = approvals.ask("cookbook", "mine", "Run", [], "sha", on_ok=lambda by: kept.append(by),
                          shown={"source": "~/AgentLink/cookbooks/mine.json", "version": "sha", "author": "not given"})
        client(srv, "approve_code", r["approve"]["arguments"])
        self.assertEqual(kept, ["client"])

    def test_the_window_press_is_an_optional_extra_path(self):
        shown = []
        person_ok.SHOW = shown.append
        self.addCleanup(setattr, person_ok, "SHOW", None)
        r = self.pending()
        self.assertIn("Approve in the FreeCAD window", r["next"])
        req = shown[-1]
        self.assertFalse(person_ok.pressed(req, spontaneous=False, now=req["opened"] + 5))
        self.assertTrue(person_ok.pressed(req, spontaneous=True, now=req["opened"] + 5))
        self.assertEqual(approvals.ask("addon-install", "Gears", "Install", [], "commit:abc"), {"ok": True})

    def test_the_window_path_is_off_by_default(self):
        with mock.patch.dict(os.environ, {"AGENTLINK_WINDOW_OK": ""}):
            self.assertFalse(person_ok.turned_on())
        with mock.patch.dict(os.environ, {"AGENTLINK_WINDOW_OK": "on"}):
            self.assertTrue(person_ok.turned_on())

    def test_a_panel_click_gets_the_window_dialog(self):
        shown = []
        person_ok.SHOW = shown.append
        self.addCleanup(setattr, person_ok, "SHOW", None)
        with mock.patch.dict(os.environ, {"AGENTLINK_WINDOW_OK": "off"}):
            person_ok.SHOW = None
            r = approvals.ask("recover", "Doc", "Save over", [], "fp", shown={"document": "Doc", "file": "~/a.FCStd"})
            person_ok.SHOW = shown.append
            ran = []
            self.assertTrue(hooks.approval_in_window(r, then=lambda: ran.append(1)))
            req = shown[-1]
            person_ok.pressed(req, True, now=req["opened"] + 3)
        self.assertEqual(ran, [1])
        self.assertTrue(approvals.granted("recover", "Doc", "fp"))

    def test_text_in_the_arguments_is_one_line_and_capped(self):
        r = approvals.ask("macro", "m", "Run\nit‮", [], "fp", shown={"source": "a\nb", "version": "v" * 900, "author": "x y"})
        a = r["approve"]["arguments"]
        for k in ("what", "source", "version", "author"):
            self.assertNotIn("\n", a[k])
            self.assertNotIn("‮", a[k])
            self.assertLessEqual(len(a[k]), approvals.MAX_FIELD + 1)

    def test_invisible_characters_never_reach_the_fields(self):
        # Red team 2, R2-7: format characters, tags and direction marks.
        r = approvals.ask("macro", "m\U000E0041x", "Run\u2060 it", [], "fp", shown={"source": "a\u2060b", "author": "x\U000E0041y\u202e"})
        a = r["approve"]["arguments"]
        for k in ("id", "what", "source", "author"):
            self.assertFalse([c for c in a[k] if approvals.invisible(c)], k)
        self.assertEqual((a["id"], a["source"], a["author"]), ("mx", "ab", "xy"))
        for bad in ({**a, "author": "x\u2060y"}, {**a, "what": a["what"] + "\U000E0041"}):
            with approvals.client_call("approve_code", bad):
                with self.assertRaises(approvals.Refused):
                    approvals.approve("approve_code", bad)
        with approvals.client_call("approve_code", a):
            self.assertTrue(approvals.approve("approve_code", a)["approved"])

    def test_the_id_is_cleaned_and_capped_and_the_kind_is_known(self):
        # Red team 2, R2-9: a dialog's title is the id.
        r = approvals.ask("dialog", "Save?\n" + "x" * 400, "Press Save", [], "fp", shown={"button": "Save"})
        a = r["approve"]["arguments"]
        self.assertNotIn("\n", a["id"])
        self.assertLessEqual(len(a["id"]), approvals.MAX_ID + 1)
        with approvals.client_call("approve_file", a):
            self.assertTrue(approvals.approve("approve_file", a)["approved"])
        with self.assertRaises(approvals.Refused):
            approvals.ask("anything", "x", "Do it", [], "fp")
        bad = {**a, "kind": "anything"}
        with approvals.client_call("approve_file", bad):
            with self.assertRaises(approvals.Refused):
                approvals.approve("approve_file", bad)

    def test_a_source_is_never_cut(self):
        # Red team 2, R2-10: the host comes first; a long source is refused.
        a = approvals.ask("extension", "x", "Add", [], "fp", shown={"source": "https://example.org/a/b.git"})["approve"]["arguments"]
        self.assertEqual(a["source"], "host: example.org, path: /a/b.git")
        a = approvals.ask("extension", "y", "Add", [], "fp", shown={"source": "https://evil.example:8443/x.git"})["approve"]["arguments"]
        self.assertTrue(a["source"].startswith("host: evil.example,"), a["source"])
        self.assertIn("address: evil.example:8443", a["source"])
        a = approvals.ask("extension", "z", "Add", [], "fp", shown={"source": "git@example.org:a/b.git"})["approve"]["arguments"]
        self.assertEqual(a["source"], "host: example.org, path: a/b.git")
        with self.assertRaises(approvals.Refused):
            approvals.ask("extension", "w", "Add", [], "fp", shown={"source": "https://example.org/" + "a" * 190 + "/evil.example"})

    def test_the_source_and_the_log_have_no_home_path(self):
        # Red team 2, R2-17.
        home = os.path.expanduser("~")
        a = approvals.ask("macro", "m", "Run", [], "fp", shown={"source": os.path.join(home, "AgentLink", "x.json")})["approve"]["arguments"]
        self.assertEqual(a["source"], "~/AgentLink/x.json")
        with mock.patch.dict(os.environ, {"AGENTLINK_HOME": self.home}):
            with approvals.client_call("approve_code", a):
                approvals.approve("approve_code", a)
        log = os.path.join(self.home, "approvals.log")
        if os.path.exists(log):
            with open(log) as f:
                self.assertNotIn(home + os.sep, f.read())

    def test_scripts_and_lessons_never_reach_the_approval_tools(self):
        from agentlink import cookbook

        self.assertTrue({"approve_file", "approve_code"} <= cookbook.SCRIPT_BLOCKED)
        self.assertFalse(hooks.extendable("approve_code"))
        self.assertFalse(hooks.extendable("approve_file"))

    def test_the_static_list_carries_both(self):
        from agentlink import staticbase

        self.assertIn("approve_file", staticbase.BASE)
        self.assertIn("approve_code", staticbase.BASE)


class FolderFingerprint(unittest.TestCase):
    def test_a_change_of_a_file_is_a_new_fingerprint(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        os.makedirs(os.path.join(d, "pkg"))
        with open(os.path.join(d, "pkg", "a.py"), "w") as f:
            f.write("x = 1\n")
        one = approvals.folder_fingerprint(d)
        os.makedirs(os.path.join(d, ".git"))
        with open(os.path.join(d, ".git", "HEAD"), "w") as f:
            f.write("ref")
        self.assertEqual(approvals.folder_fingerprint(d), one)  # .git is not the add-on's code
        with open(os.path.join(d, "pkg", "a.py"), "a") as f:
            f.write("import os\n")
        self.assertNotEqual(approvals.folder_fingerprint(d), one)
        self.assertIsNone(approvals.folder_fingerprint(os.path.join(d, "none")))
        self.assertTrue(one.startswith("sha256:"))


class NoHiding(unittest.TestCase):
    def test_an_add_on_that_says_replaces_is_refused_at_load(self):
        from agentlink import families

        fam = types.SimpleNamespace(EXTERNAL=True, EXTENSION="standin.agentlink_families", GROUP="standin", REPLACES={"view", "core"}, HIDES={"export"})
        err = io.StringIO()
        with redirect_stderr(err):
            got = families.refuse_hiding(fam)
            families.declared([types.SimpleNamespace(EXTERNAL=True, EXTENSION="other.agentlink_families", GROUP="other", REPLACES=["dev"])])
        self.assertEqual(got, ["REPLACES", "HIDES"])
        self.assertEqual((fam.REPLACES, fam.HIDES), ((), ()))
        log = err.getvalue()
        self.assertIn("standin.agentlink_families declares REPLACES", log)
        self.assertIn("refused: an add-on never hides or replaces a hub tool or group", log)
        self.assertIn("other.agentlink_families declares REPLACES", log)

    def test_the_server_has_no_replaces_any_more(self):
        with open(os.path.join(os.path.dirname(HERE), "agentlink", "tools.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("REPLACES", src)
        self.assertNotIn("server.replaced", src)


class FileDialogs(unittest.TestCase):
    def test_which_presses_need_approve_file(self):
        from test_gui_link_dialog import gui_link

        close = {"name": "confirmSave", "title": "Unsaved Document", "text": "Do you want to save your changes to document 'Part' before closing?"}
        self.assertIsNotNone(gui_link.file_dialog_press(close, "Save"))
        self.assertIsNotNone(gui_link.file_dialog_press(close, "Don't Save"))
        self.assertIsNone(gui_link.file_dialog_press(close, "Cancel"))
        repl = {"title": "Export", "text": "a.step already exists. Do you want to replace it?"}
        self.assertIsNotNone(gui_link.file_dialog_press(repl, "Yes"))
        self.assertIsNone(gui_link.file_dialog_press(repl, "No"))
        self.assertIsNone(gui_link.file_dialog_press({"title": "Sketch", "text": "Close the sketch?"}, "Yes"))


# ---- 4. the critical-pressure guard --------------------------------------------------------

class PressureGuard(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home, True)
        self.env = mock.patch.dict(os.environ, {"AGENTLINK_HOME": self.home, "AGENTLINK_MEMORY_GUARD": ""})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_the_level_is_read_from_macos(self):
        self.assertEqual(memguard.level(lambda: "kern.memorystatus_vm_pressure_level: 4"), "critical")
        self.assertEqual(memguard.level(lambda: "kern.memorystatus_vm_pressure_level: 2"), "warn")
        self.assertEqual(memguard.level(lambda: "kern.memorystatus_vm_pressure_level: 1"), "normal")
        self.assertIsNone(memguard.level(platform="linux"))

    def test_two_critical_samples_in_a_row_and_never_faster_than_every(self):
        seq = iter(["critical", "normal", "critical", "critical"])
        w = memguard.Watch(read=lambda: next(seq), every=3.0, need=2)
        self.assertIsNone(w.sample(0))
        self.assertIsNone(w.sample(1))       # too soon: not read
        self.assertIsNone(w.sample(3))       # normal: the row starts again
        self.assertIsNone(w.sample(6))
        self.assertEqual(w.sample(9), "critical")

    def test_only_the_jobs_own_processes_are_stopped(self):
        # FreeCAD 100; its link helper 101 (older than the job); the job's solver 102 and its child 103.
        rows = [(100, 1, 5000, 900000), (101, 100, 4000, 1000), (102, 100, 20, 3000000), (103, 102, 10, 50000), (200, 1, 30, 9000000)]
        self.assertEqual(memguard.job_children(100, 25, rows), [102, 103])
        stopped = []
        seq = iter(["critical", "critical"])
        sup = memguard.Supervisor(watch=memguard.Watch(read=lambda: next(seq), every=0, need=2), rows=lambda: rows, stop=stopped.append, guard=lambda: True)
        job = {"tool": "fea_solve", "start": time.time() - 25, "pid": 100}
        self.assertIsNone(sup.turn(job))
        m = sup.turn(job)
        self.assertEqual(stopped, [102, 103])
        self.assertEqual((m["tool"], m["how"]), ("fea_solve", "children"))
        self.assertIsNone(sup.turn(job))  # once per job
        got = memguard.take_mark("fea_solve", job["start"])
        self.assertEqual(got["children"], [102, 103])
        self.assertIsNone(memguard.take_mark("fea_solve", job["start"]))

    def test_the_supervisor_names_the_job_and_stops_only_its_recorded_children(self):
        # FreeCAD 100; an import helper 104 started after the job (not its
        # own); the job's recorded solver 102 and its child 103.
        rows = [(100, 1, 5000, 900000), (102, 100, 20, 3000000), (103, 102, 10, 50000), (104, 100, 5, 10)]
        stopped = []
        jobs = {"pid": 100, "jobs": [{"tool": "fea_solve", "tid": 7, "token": "ab" * 16, "t": time.time() - 25, "children": [102, 999]}]}
        sup = memguard.Supervisor(watch=memguard.Watch(read=lambda: "critical", every=0, need=1), rows=lambda: rows, stop=stopped.append,
                                  guard=lambda: True, jobs=lambda: jobs)
        m = sup.turn({"tool": "fea_solve", "start": time.time() - 25, "pid": 100})
        self.assertEqual(stopped, [102])
        self.assertEqual((m["tid"], m["token"], m["how"]), (7, "ab" * 16, "children"))
        self.assertIsNone(memguard.take_mark("fea_solve", time.time() - 25, token="cd" * 16))
        self.assertIsNotNone(memguard.take_mark("fea_solve", time.time() - 25, token="ab" * 16))

    def test_run_records_the_child_for_the_job(self):
        tid = memguard.started("fea_solve")
        seen = []
        try:
            real_add = memguard.add_child

            def add(pid, tid=None):
                seen.append(pid)
                return real_add(pid, tid)

            with mock.patch.object(memguard, "add_child", add):
                r = memguard.run([sys.executable, "-c", "print('hi')"], capture_output=True, text=True, timeout=30)
            self.assertEqual((r.returncode, r.stdout.strip()), (0, "hi"))
            self.assertEqual(len(seen), 1)
            self.assertEqual([j["children"] for j in memguard.read_jobs()["jobs"] if j["tid"] == tid], [[]])
        finally:
            with mock.patch.object(memguard, "_raise_in", lambda t, e: 0):
                memguard.finished(tid)

    def test_no_job_or_guard_off_reads_nothing(self):
        reads = []
        sup = memguard.Supervisor(watch=memguard.Watch(read=lambda: reads.append(1) or "critical", every=0), rows=lambda: [], guard=lambda: False)
        self.assertIsNone(sup.turn({"tool": "x", "start": 0, "pid": 1}))
        sup.guard = lambda: True
        self.assertIsNone(sup.turn(None))
        self.assertEqual(reads, [])
        with mock.patch.dict(os.environ, {"AGENTLINK_MEMORY_GUARD": "off"}):
            self.assertFalse(memguard.on())

    def test_a_job_in_this_python_is_stopped_alone(self):
        stopped = []
        tid = memguard.started("mesh_map", tid=11, now=time.time() - 5)
        memguard.started("other_job", tid=12, now=time.time() - 5)
        try:
            rec = {r["tid"]: r for r in memguard.read_jobs()["jobs"]}[11]
            # A mark without the job's thread id and token stops nothing (R2-14).
            for forged in (memguard.write_mark("mesh_map", os.getpid(), []),
                           memguard.write_mark("mesh_map", os.getpid(), [], tid=11, token="0" * 32),
                           memguard.write_mark("mesh_map", os.getpid(), [], tid=12, token=rec["token"])):
                self.assertEqual(memguard.check_once(read=lambda: dict(forged), raise_in=lambda t, e: stopped.append((t, e))), [])
            self.assertEqual(stopped, [])
            m = memguard.write_mark("mesh_map", os.getpid(), [], tid=11, token=rec["token"])
            self.assertEqual(memguard.check_once(read=lambda: dict(m), raise_in=lambda t, e: stopped.append((t, e))), ["mesh_map"])
            self.assertEqual(stopped, [(11, memguard.MemoryStop)])
        finally:
            with mock.patch.object(memguard, "_raise_in", lambda t, e: 0):
                memguard.finished(tid)
                memguard.finished(12)

    def test_the_answer_says_why_and_names_the_checkpoint(self):
        from agentlink import heavy
        from agentlink.protocol import ToolError

        class T:
            name = "fea_solve"
            changes = True

        g = heavy.Gate.__new__(heavy.Gate)
        g.s, g.sized, g.start, g.checkpoint = None, None, None, "cp7"
        t0 = time.time() - 3
        with mock.patch.object(memguard, "_raise_in", lambda t, e: 0):
            g.watched = (memguard.started("fea_solve", now=t0), t0)
            rec = {r["tid"]: r for r in memguard.read_jobs()["jobs"]}[g.watched[0]]
            memguard.write_mark("fea_solve", 1, [55], tid=rec["tid"], token=rec["token"])
            with self.assertRaises(ToolError) as e:
                g.after(T(), {}, False)
        self.assertEqual(e.exception.code, "stopped")
        self.assertIn("critical memory pressure", e.exception.message)
        self.assertIn("The checkpoint cp7 from before the job is kept", e.exception.message)
        self.assertIn("CriticalPressureGuard", e.exception.message)

    def test_no_refusal_before_a_job_starts(self):
        with open(os.path.join(os.path.dirname(HERE), "agentlink", "heavy.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("would need about", src)
        self.assertNotIn("MemoryCeilingGB", src)


if __name__ == "__main__":
    unittest.main()
