#!/usr/bin/env python3
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_manifest
import pricing


class TestRunManifest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._orig = run_manifest.RUNS_DIR
        run_manifest.RUNS_DIR = self.tmp

    def tearDown(self):
        run_manifest.RUNS_DIR = self._orig

    def test_new_manifest_shape(self):
        m = run_manifest.new_manifest("run1", "fix bug", "/repo", "feat/x", "claude", "codex")
        self.assertEqual(m["v"], 1)
        self.assertEqual(m["rounds"], [])
        self.assertEqual(m["outcome"]["verdict"], None)

    def test_save_and_load_roundtrip(self):
        m = run_manifest.new_manifest("run1", "fix bug", "/repo", "feat/x", "claude", "codex")
        run_manifest.save_manifest(m)
        loaded = run_manifest.load_manifest("run1")
        self.assertEqual(loaded["run_id"], "run1")

    def test_add_round_increments_n_correctly(self):
        m = run_manifest.new_manifest("run1", "t", "/repo", "b", "claude", "codex")
        r1 = run_manifest.add_round(m, "coder", "claude", session_id="s1")
        self.assertEqual(r1["n"], 1)
        run_manifest.close_round(m, r1, findings_addressed=0)
        r2 = run_manifest.add_round(m, "reviewer", "codex", session_id="s2")
        self.assertEqual(r2["n"], 1)  # same round number as its paired coder round
        run_manifest.close_round(m, r2, findings=2, verdict="CHANGES_REQUESTED")
        r3 = run_manifest.add_round(m, "coder", "claude", session_id="s3")
        self.assertEqual(r3["n"], 2)

    def test_partial_manifest_survives_reload(self):
        m = run_manifest.new_manifest("run1", "t", "/repo", "b", "claude", "codex")
        run_manifest.add_round(m, "coder", "claude", session_id="s1")
        reloaded = run_manifest.load_manifest("run1")
        self.assertEqual(len(reloaded["rounds"]), 1)
        self.assertIsNone(reloaded["rounds"][0]["ended"])

    def test_list_manifests_returns_all_saved(self):
        run_manifest.save_manifest(run_manifest.new_manifest("a", "t", "/r", "b", "claude", "codex"))
        run_manifest.save_manifest(run_manifest.new_manifest("b", "t", "/r", "b", "claude", "codex"))
        self.assertEqual(len(run_manifest.list_manifests()), 2)

    def test_run_cost_joins_by_session_id(self):
        m = run_manifest.new_manifest("run1", "t", "/repo", "b", "claude", "codex")
        r1 = run_manifest.add_round(m, "coder", "claude", session_id="s1")
        run_manifest.close_round(m, r1)
        r2 = run_manifest.add_round(m, "reviewer", "codex", session_id="s2")
        run_manifest.close_round(m, r2)
        summaries = [
            {"session_id": "s1", "by_model": {"claude-sonnet-4-5": {"input": 1_000_000, "output": 0,
                                                                     "cache_read": 0, "cache_write": 0}},
             "project": "repo", "mtime": 0},
            {"session_id": "s2", "by_model": {"gpt-5.5": {"input": 0, "output": 1_000_000,
                                                           "cache_read": 0, "cache_write": 0}},
             "project": "repo", "mtime": 0},
        ]
        result = run_manifest.run_cost(m, summaries)
        sonnet_rates = next(r for k, r in pricing.RATES if k == "sonnet")
        gpt5_rates = next(r for k, r in pricing.RATES if k == "gpt-5")
        self.assertAlmostEqual(result["coder"], sonnet_rates["input"], places=4)
        self.assertAlmostEqual(result["reviewer"], gpt5_rates["output"], places=4)
        self.assertAlmostEqual(result["total"], result["coder"] + result["reviewer"], places=4)

    def test_run_cost_falls_back_to_time_window_when_no_session_match(self):
        m = run_manifest.new_manifest("run1", "t", "/repo", "b", "claude", "codex")
        r1 = run_manifest.add_round(m, "coder", "claude", session_id=None)
        run_manifest.close_round(m, r1)
        m["rounds"][0]["started"] = "2026-07-09T10:00:00Z"
        m["rounds"][0]["ended"] = "2026-07-09T10:10:00Z"
        import time as _time
        import calendar
        import _value
        in_window_mtime = calendar.timegm((2026, 7, 9, 10, 5, 0))
        summaries = [{"session_id": None, "project": "repo",
                      "projdir": _value.mangle_path(os.path.abspath("/repo")),
                      "by_model": {"claude-sonnet-4-5": {"input": 100_000, "output": 0,
                                                          "cache_read": 0, "cache_write": 0}},
                      "mtime": in_window_mtime}]
        result = run_manifest.run_cost(m, summaries)
        self.assertGreater(result["coder"], 0)

    def test_run_cost_dedupes_shared_session_id_across_rounds(self):
        """Critical #1 regression: the coder's session_id is the SAME across
        every round of one pair-loop run (same interactive session). Summing
        round_cost() naively over rounds double/triple-counts that session's
        full cumulative cost. run_cost() must count it ONCE across the run."""
        m = run_manifest.new_manifest("run1", "t", "/repo", "b", "claude", "codex")
        r1 = run_manifest.add_round(m, "coder", "claude", session_id="shared-sid")
        run_manifest.close_round(m, r1)
        r2 = run_manifest.add_round(m, "reviewer", "codex", session_id="rev-sid-1")
        run_manifest.close_round(m, r2)
        r3 = run_manifest.add_round(m, "coder", "claude", session_id="shared-sid")
        run_manifest.close_round(m, r3)
        r4 = run_manifest.add_round(m, "reviewer", "codex", session_id="rev-sid-2")
        run_manifest.close_round(m, r4)
        summaries = [
            {"session_id": "shared-sid",
             "by_model": {"claude-sonnet-4-5": {"input": 1_000_000, "output": 0,
                                                  "cache_read": 0, "cache_write": 0}},
             "project": "repo", "mtime": 0},
            {"session_id": "rev-sid-1",
             "by_model": {"gpt-5.5": {"input": 0, "output": 1_000_000,
                                       "cache_read": 0, "cache_write": 0}},
             "project": "repo", "mtime": 0},
            {"session_id": "rev-sid-2",
             "by_model": {"gpt-5.5": {"input": 0, "output": 1_000_000,
                                       "cache_read": 0, "cache_write": 0}},
             "project": "repo", "mtime": 0},
        ]
        result = run_manifest.run_cost(m, summaries)
        sonnet_rates = next(r for k, r in pricing.RATES if k == "sonnet")
        gpt5_rates = next(r for k, r in pricing.RATES if k == "gpt-5")
        # coder cost counted ONCE for the shared session_id, not twice.
        self.assertAlmostEqual(result["coder"], sonnet_rates["input"], places=4)
        # reviewer sessions differ per round -> both counted.
        self.assertAlmostEqual(result["reviewer"], 2 * gpt5_rates["output"], places=4)
        self.assertAlmostEqual(result["total"], result["coder"] + result["reviewer"], places=4)

    def test_run_cost_fallback_matches_real_absolute_path_via_projdir(self):
        """Critical #2 regression: cwd is a real absolute filesystem path and
        summary["project"] is the dashboard's abbreviated label — neither is
        ever a substring of the other for a real path (unlike the existing
        fixture's coincidentally-matching "/repo"/"repo" pair). The fallback
        must join on the mangled `projdir` field instead, and actually find
        a match (not silently return $0)."""
        import _value
        cwd = "/Users/rajit/personal-github/100xprism"
        m = run_manifest.new_manifest("run1", "t", cwd, "b", "claude", "codex")
        r1 = run_manifest.add_round(m, "coder", "claude", session_id=None)
        run_manifest.close_round(m, r1)
        m["rounds"][0]["started"] = "2026-07-09T10:00:00Z"
        m["rounds"][0]["ended"] = "2026-07-09T10:10:00Z"
        import calendar
        in_window_mtime = calendar.timegm((2026, 7, 9, 10, 5, 0))
        summaries = [{
            "session_id": None,
            "project": "~/personal/github/100xprism",  # dashboard label — no substring relation to cwd
            "projdir": _value.mangle_path(cwd),
            "by_model": {"claude-sonnet-4-5": {"input": 100_000, "output": 0,
                                                "cache_read": 0, "cache_write": 0}},
            "mtime": in_window_mtime,
        }]
        # sanity check: the old substring approach would never match these two strings
        self.assertNotIn(cwd, summaries[0]["project"])
        self.assertNotIn(summaries[0]["project"], cwd)
        result = run_manifest.run_cost(m, summaries)
        self.assertGreater(result["coder"], 0)


if __name__ == "__main__":
    unittest.main()
