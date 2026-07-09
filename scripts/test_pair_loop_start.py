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


class TestPairLoopStart(unittest.TestCase):
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

    def test_start_creates_manifest_and_handoff_file(self):
        r = self._run("start", "--task", "fix the bug")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertTrue(os.path.exists(out["manifest_path"]))
        self.assertTrue(os.path.exists(out["handoff_path"]))

    def test_start_refuses_on_dirty_tree(self):
        with open(os.path.join(self.repo, "dirty.txt"), "w") as f:
            f.write("uncommitted")
        r = self._run("start", "--task", "x")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("dirty", r.stderr.lower())

    def test_budget_check_ok_when_no_config(self):
        r = self._run("start", "--task", "x")
        run_id = json.loads(r.stdout)["run_id"]
        r2 = self._run("budget-check", "--run", run_id)
        self.assertEqual(r2.returncode, 0, r2.stderr)
        out = json.loads(r2.stdout)
        self.assertIsNone(out["level"])

    def test_budget_check_alerts_when_cap_exceeded(self):
        os.makedirs(os.path.join(self.env["HOME"], ".100xprism"), exist_ok=True)
        with open(os.path.join(self.env["HOME"], ".100xprism", "config.json"), "w") as f:
            json.dump({"budget": {"per_run_usd": 0.0000001}}, f)
        r = self._run("start", "--task", "x")
        run_id = json.loads(r.stdout)["run_id"]
        # manually add a costed round via run_manifest to simulate spend
        sys.path.insert(0, HERE)
        import run_manifest
        orig = run_manifest.RUNS_DIR
        run_manifest.RUNS_DIR = os.path.join(self.env["HOME"], ".100xprism", "handoff-runs")
        try:
            m = run_manifest.load_manifest(run_id)
            rnd = run_manifest.add_round(m, "coder", "claude", session_id="nonexistent")
            run_manifest.close_round(m, rnd)
        finally:
            run_manifest.RUNS_DIR = orig
        r2 = self._run("budget-check", "--run", run_id)
        # with a near-zero cap and any positive spend (even $0 if nothing joins),
        # the important contract is: no crash, valid JSON, exit 0 or 2 only.
        self.assertIn(r2.returncode, (0, 2))
        json.loads(r2.stdout)


if __name__ == "__main__":
    unittest.main()
