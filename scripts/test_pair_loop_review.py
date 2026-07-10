#!/usr/bin/env python3
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "pair-loop.py")
STUB_REVIEWER = os.path.join(HERE, "fixtures", "stub-reviewer.sh")


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.email=t@t.t", "-c", "user.name=t",
                            "-c", "commit.gpgsign=false", "-C", repo, *args],
                           capture_output=True, text=True, check=False)


def _load_pair_loop():
    """pair-loop.py has a hyphen in its name, so it can't be `import`-ed
    normally; load it via importlib for the in-process unit tests below."""
    spec = importlib.util.spec_from_file_location("pair_loop_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestPairLoopReview(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp()
        git(self.repo, "init", "-q")
        with open(os.path.join(self.repo, "a.txt"), "w") as f:
            f.write("x")
        git(self.repo, "add", "a.txt")
        git(self.repo, "commit", "-q", "-m", "init")
        self.env = dict(os.environ, HOME=tempfile.mkdtemp())

    def _run(self, *args):
        return subprocess.run([sys.executable, SCRIPT, *args], cwd=self.repo,
                              capture_output=True, text=True, env=self.env)

    def test_coder_done_appends_round(self):
        r = self._run("start", "--task", "x")
        run_id = json.loads(r.stdout)["run_id"]
        r2 = self._run("coder-done", "--run", run_id, "--summary", "Implemented the fix.")
        self.assertEqual(r2.returncode, 0, r2.stderr)
        with open(os.path.join(self.repo, "HANDOFF.md")) as f:
            content = f.read()
        self.assertIn("Implemented the fix.", content)

    def test_review_with_stub_reviewer_approved(self):
        r = self._run("start", "--task", "x")
        run_id = json.loads(r.stdout)["run_id"]
        self._run("coder-done", "--run", run_id, "--summary", "done")
        r2 = self._run("review", "--run", run_id, "--reviewer-cmd",
                       json.dumps(["bash", STUB_REVIEWER, "APPROVED"]))
        self.assertEqual(r2.returncode, 0, r2.stderr)
        out = json.loads(r2.stdout)
        self.assertEqual(out["verdict"], "APPROVED")

    def test_review_with_stub_reviewer_changes_requested(self):
        r = self._run("start", "--task", "x")
        run_id = json.loads(r.stdout)["run_id"]
        self._run("coder-done", "--run", run_id, "--summary", "done")
        r2 = self._run("review", "--run", run_id, "--reviewer-cmd",
                       json.dumps(["bash", STUB_REVIEWER, "CHANGES_REQUESTED"]))
        out = json.loads(r2.stdout)
        self.assertEqual(out["verdict"], "CHANGES_REQUESTED")
        self.assertGreaterEqual(len(out["findings"]), 1)

    def test_coder_done_then_review_share_the_same_round_number(self):
        """coder-done + review is one paired round: run_manifest.add_round
        pairs a reviewer round onto a preceding coder round's `n` (companion
        plan's pairing rule). This must hold end-to-end through the CLI, not
        just inside run_manifest's own unit tests."""
        r = self._run("start", "--task", "x")
        run_id = json.loads(r.stdout)["run_id"]
        r1 = self._run("coder-done", "--run", run_id, "--summary", "done")
        coder_round = json.loads(r1.stdout)["round"]
        r2 = self._run("review", "--run", run_id, "--reviewer-cmd",
                       json.dumps(["bash", STUB_REVIEWER, "APPROVED"]))
        self.assertEqual(r2.returncode, 0, r2.stderr)

        sys.path.insert(0, HERE)
        import run_manifest
        orig = run_manifest.RUNS_DIR
        run_manifest.RUNS_DIR = os.path.join(self.env["HOME"], ".100xprism", "handoff-runs")
        try:
            manifest = run_manifest.load_manifest(run_id)
        finally:
            run_manifest.RUNS_DIR = orig
        self.assertEqual(len(manifest["rounds"]), 2)
        self.assertEqual(manifest["rounds"][0]["role"], "coder")
        self.assertEqual(manifest["rounds"][1]["role"], "reviewer")
        self.assertEqual(manifest["rounds"][0]["n"], coder_round)
        self.assertEqual(manifest["rounds"][1]["n"], coder_round)

    def test_review_reasks_once_then_falls_back_on_unparseable_verdict(self):
        """Both reviewer calls return output with no VERDICT line. The CLI must
        invoke the reviewer exactly twice (one re-ask), then synthesize a
        CHANGES_REQUESTED verdict with a synthetic finding rather than crash
        or silently treat the unparseable output as approved."""
        r = self._run("start", "--task", "x")
        run_id = json.loads(r.stdout)["run_id"]
        self._run("coder-done", "--run", run_id, "--summary", "done")

        call_log = os.path.join(self.repo, "calls.log")
        unparseable_reviewer = os.path.join(self.repo, "unparseable-reviewer.sh")
        with open(unparseable_reviewer, "w") as f:
            f.write(
                "#!/usr/bin/env bash\n"
                f"echo call >> {call_log}\n"
                "echo 'this review has no verdict line at all'\n"
            )
        os.chmod(unparseable_reviewer, 0o755)

        r2 = self._run("review", "--run", run_id, "--reviewer-cmd",
                       json.dumps(["bash", unparseable_reviewer]))
        self.assertEqual(r2.returncode, 0, r2.stderr)
        out = json.loads(r2.stdout)
        self.assertEqual(out["verdict"], "CHANGES_REQUESTED")
        self.assertGreaterEqual(len(out["findings"]), 1)
        self.assertTrue(out.get("fallback_used") is not None)  # key present

        with open(call_log) as f:
            calls = [l for l in f.read().splitlines() if l]
        self.assertEqual(len(calls), 2, "reviewer must be invoked exactly twice: "
                          "the original ask + exactly one re-ask")

    def test_review_does_not_reask_when_first_verdict_parses(self):
        """A parseable first response must NOT trigger a second reviewer call."""
        r = self._run("start", "--task", "x")
        run_id = json.loads(r.stdout)["run_id"]
        self._run("coder-done", "--run", run_id, "--summary", "done")

        call_log = os.path.join(self.repo, "calls.log")
        counting_reviewer = os.path.join(self.repo, "counting-reviewer.sh")
        with open(counting_reviewer, "w") as f:
            f.write(
                "#!/usr/bin/env bash\n"
                f"echo call >> {call_log}\n"
                "echo '1. [correctness] src/foo.py:1 — fine'\n"
                "echo 'VERDICT: APPROVED'\n"
            )
        os.chmod(counting_reviewer, 0o755)

        r2 = self._run("review", "--run", run_id, "--reviewer-cmd",
                       json.dumps(["bash", counting_reviewer]))
        self.assertEqual(r2.returncode, 0, r2.stderr)
        out = json.loads(r2.stdout)
        self.assertEqual(out["verdict"], "APPROVED")

        with open(call_log) as f:
            calls = [l for l in f.read().splitlines() if l]
        self.assertEqual(len(calls), 1, "a parseable first verdict must not trigger a re-ask")


class TestSessionGuessing(unittest.TestCase):
    """Direct unit tests for the fuzzy session-id detection helpers. These
    monkeypatch the module's directory constants rather than relying on the
    real (and possibly non-empty, concurrently-written-to) ~/.claude/projects
    or ~/.codex/sessions on this machine."""

    def setUp(self):
        self.mod = _load_pair_loop()
        self.tmp = tempfile.mkdtemp()

    def test_guess_claude_session_returns_none_when_no_transcripts(self):
        self.mod.CLAUDE_PROJECTS = self.tmp
        result = self.mod._guess_current_claude_session("/some/repo")
        self.assertIsNone(result)

    def test_guess_claude_session_returns_none_when_project_dir_missing(self):
        self.mod.CLAUDE_PROJECTS = os.path.join(self.tmp, "does-not-exist")
        result = self.mod._guess_current_claude_session("/some/repo")
        self.assertIsNone(result)

    def test_guess_claude_session_picks_newest_transcript(self):
        import _value
        cwd = "/some/repo"
        mangled = _value.mangle_path(os.path.abspath(cwd))
        proj_dir = os.path.join(self.tmp, mangled)
        os.makedirs(proj_dir)
        older = os.path.join(proj_dir, "older-session.jsonl")
        newer = os.path.join(proj_dir, "newer-session.jsonl")
        with open(older, "w") as f:
            f.write("{}")
        time.sleep(0.02)
        with open(newer, "w") as f:
            f.write("{}")

        self.mod.CLAUDE_PROJECTS = self.tmp
        result = self.mod._guess_current_claude_session(cwd)
        self.assertEqual(result, "newer-session")

    def test_guess_codex_session_returns_none_when_no_new_files(self):
        # Must monkeypatch codex.SOURCE_DIR to an empty dir here — leaving it
        # pointed at the real ~/.codex/sessions would let this test pick up an
        # unrelated real session from this very development machine and pass
        # for the wrong reason (or flake if a concurrent codex run is active).
        empty_dir = os.path.join(self.tmp, "empty-codex-sessions")
        os.makedirs(empty_dir)
        codex_mod = sys.modules.get("adapters.codex") or self.mod.codex
        orig_source_dir = codex_mod.SOURCE_DIR
        codex_mod.SOURCE_DIR = empty_dir
        try:
            result = self.mod._guess_current_codex_session({})
        finally:
            codex_mod.SOURCE_DIR = orig_source_dir
        self.assertIsNone(result)

    def test_guess_codex_session_ignores_files_unchanged_since_snapshot(self):
        codex_dir = os.path.join(self.tmp, "codex-sessions")
        os.makedirs(codex_dir)
        path = os.path.join(codex_dir, "rollout-old.jsonl")
        with open(path, "w") as f:
            f.write(json.dumps({"type": "session_meta",
                                "payload": {"session_id": "should-not-be-picked"}}) + "\n")
        mtime = os.path.getmtime(path)

        codex_mod = sys.modules.get("adapters.codex") or self.mod.codex
        orig_source_dir = codex_mod.SOURCE_DIR
        codex_mod.SOURCE_DIR = codex_dir
        try:
            # before_mtimes snapshot equal to the file's current mtime -> not "new"
            result = self.mod._guess_current_codex_session({path: mtime})
        finally:
            codex_mod.SOURCE_DIR = orig_source_dir
        self.assertIsNone(result)

    def test_guess_codex_session_reads_session_id_from_new_file(self):
        codex_dir = os.path.join(self.tmp, "codex-sessions")
        os.makedirs(codex_dir)
        path = os.path.join(codex_dir, "rollout-new.jsonl")
        with open(path, "w") as f:
            f.write(json.dumps({"type": "session_meta",
                                "payload": {"session_id": "abc-123"}}) + "\n")

        codex_mod = sys.modules.get("adapters.codex") or self.mod.codex
        orig_source_dir = codex_mod.SOURCE_DIR
        codex_mod.SOURCE_DIR = codex_dir
        try:
            result = self.mod._guess_current_codex_session({})  # empty snapshot -> file is "new"
        finally:
            codex_mod.SOURCE_DIR = orig_source_dir
        self.assertEqual(result, "abc-123")


if __name__ == "__main__":
    unittest.main()
