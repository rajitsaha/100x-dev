#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "pair-loop.py")
STUB_REVIEWER = os.path.join(HERE, "fixtures", "stub-reviewer.sh")


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.email=t@t.t", "-c", "user.name=t",
                            "-c", "commit.gpgsign=false", "-C", repo, *args],
                           capture_output=True, text=True, check=False)


class TestPairLoopIntegration(unittest.TestCase):
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

    def test_full_loop_approves_on_first_round(self):
        run_id = json.loads(self._run("start", "--task", "add feature").stdout)["run_id"]
        self._run("coder-done", "--run", run_id, "--summary", "Added the feature.")
        r = self._run("review", "--run", run_id, "--reviewer-cmd",
                      json.dumps(["bash", STUB_REVIEWER, "APPROVED"]))
        verdict = json.loads(r.stdout)["verdict"]
        self.assertEqual(verdict, "APPROVED")
        self._run("finish", "--run", run_id, "--verdict", "APPROVED", "--pr", "1")

        manifest_path = os.path.join(self.env["HOME"], ".100xprism", "handoff-runs", f"{run_id}.json")
        manifest = json.load(open(manifest_path))
        self.assertEqual(len(manifest["rounds"]), 2)  # 1 coder + 1 reviewer
        self.assertEqual(manifest["outcome"]["verdict"], "APPROVED")

        handoff_text = open(os.path.join(self.repo, "HANDOFF.md")).read()
        self.assertIn("Round 1 — CODER", handoff_text)
        self.assertIn("Round 1 — REVIEWER", handoff_text)
        self.assertIn("VERDICT: APPROVED", handoff_text)

    def test_loop_hits_round_cap_without_approval(self):
        os.makedirs(os.path.join(self.env["HOME"], ".100xprism"), exist_ok=True)
        with open(os.path.join(self.env["HOME"], ".100xprism", "config.json"), "w") as f:
            json.dump({"pair_loop": {"max_rounds": 2}}, f)
        run_id = json.loads(self._run("start", "--task", "add feature").stdout)["run_id"]

        for _ in range(2):
            self._run("coder-done", "--run", run_id, "--summary", "attempted fix")
            r = self._run("review", "--run", run_id, "--reviewer-cmd",
                          json.dumps(["bash", STUB_REVIEWER, "CHANGES_REQUESTED"]))
            verdict = json.loads(r.stdout)["verdict"]
            self.assertEqual(verdict, "CHANGES_REQUESTED")

        manifest_path = os.path.join(self.env["HOME"], ".100xprism", "handoff-runs", f"{run_id}.json")
        manifest = json.load(open(manifest_path))
        self.assertEqual(len(manifest["rounds"]), 4)  # 2 coder + 2 reviewer
        # the SKILL.md instructs the agent (not this CLI) to stop at max_rounds;
        # verify the data the agent would check on is present and correct.
        self.assertEqual(manifest["rounds"][-1]["n"], 2)
        self.assertEqual(manifest["rounds"][-1]["verdict"], "CHANGES_REQUESTED")
        self.assertIsNone(manifest["outcome"]["verdict"])


if __name__ == "__main__":
    unittest.main()
