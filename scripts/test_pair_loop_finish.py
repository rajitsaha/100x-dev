#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "pair-loop.py")


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.email=t@t.t", "-c", "user.name=t",
                            "-c", "commit.gpgsign=false", "-C", repo, *args],
                           capture_output=True, text=True, check=False)


class TestPairLoopFinish(unittest.TestCase):
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

    def test_finish_writes_pr_body_with_transcript(self):
        r = self._run("start", "--task", "fix the bug")
        run_id = json.loads(r.stdout)["run_id"]
        self._run("coder-done", "--run", run_id, "--summary", "Implemented the fix.")
        r2 = self._run("finish", "--run", run_id, "--verdict", "APPROVED", "--pr", "78")
        self.assertEqual(r2.returncode, 0, r2.stderr)
        out = json.loads(r2.stdout)
        body = open(out["pr_body_path"]).read()
        self.assertIn("Implemented the fix.", body)
        manifest_path = os.path.join(self.env["HOME"], ".100xprism", "handoff-runs", f"{run_id}.json")
        manifest = json.load(open(manifest_path))
        self.assertEqual(manifest["pr"], 78)

    def test_finish_records_outcome_in_manifest(self):
        r = self._run("start", "--task", "x")
        run_id = json.loads(r.stdout)["run_id"]
        self._run("finish", "--run", run_id, "--verdict", "APPROVED", "--pr", "5")
        manifest_path = os.path.join(self.env["HOME"], ".100xprism", "handoff-runs", f"{run_id}.json")
        manifest = json.load(open(manifest_path))
        self.assertEqual(manifest["outcome"]["verdict"], "APPROVED")
        self.assertEqual(manifest["pr"], 5)

    def test_finish_called_twice_preserves_pr_and_rounds(self):
        # Real workflow (see modules/pair-loop/SKILL.md Step 5): `finish` is
        # called once right after approval WITHOUT --pr (no PR number exists
        # yet), then called again WITH --pr once the PR is actually opened.
        # The second call must not lose the round history recorded so far,
        # and a manifest["pr"] set on the second call must stick.
        r = self._run("start", "--task", "fix the bug")
        run_id = json.loads(r.stdout)["run_id"]
        self._run("coder-done", "--run", run_id, "--summary", "Implemented the fix.")
        self._run("review", "--run", run_id, "--reviewer-cmd",
                  json.dumps(["bash", os.path.join(HERE, "fixtures", "stub-reviewer.sh"), "APPROVED"]))

        manifest_path = os.path.join(self.env["HOME"], ".100xprism", "handoff-runs", f"{run_id}.json")
        rounds_before = len(json.load(open(manifest_path))["rounds"])

        r1 = self._run("finish", "--run", run_id, "--verdict", "APPROVED")
        self.assertEqual(r1.returncode, 0, r1.stderr)
        manifest_after_first = json.load(open(manifest_path))
        self.assertIsNone(manifest_after_first["pr"])
        self.assertEqual(len(manifest_after_first["rounds"]), rounds_before)

        r2 = self._run("finish", "--run", run_id, "--verdict", "APPROVED", "--pr", "78")
        self.assertEqual(r2.returncode, 0, r2.stderr)
        manifest_after_second = json.load(open(manifest_path))
        self.assertEqual(manifest_after_second["pr"], 78)
        self.assertEqual(len(manifest_after_second["rounds"]), rounds_before)

        # A hypothetical accidental third call without --pr must NOT wipe out
        # the PR number that was already recorded.
        r3 = self._run("finish", "--run", run_id, "--verdict", "APPROVED")
        self.assertEqual(r3.returncode, 0, r3.stderr)
        manifest_after_third = json.load(open(manifest_path))
        self.assertEqual(manifest_after_third["pr"], 78)
        self.assertEqual(len(manifest_after_third["rounds"]), rounds_before)

        # The PR body file path is stable across calls (same run_id => same
        # path) and is correctly overwritten, not duplicated/collided.
        out2 = json.loads(r2.stdout)
        out3 = json.loads(r3.stdout)
        self.assertEqual(out2["pr_body_path"], out3["pr_body_path"])


if __name__ == "__main__":
    unittest.main()
