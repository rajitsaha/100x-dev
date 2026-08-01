#!/usr/bin/env python3
"""Covers the PR review summary — the artifact a human reviewer actually sees.

The summary is the only evidence on the PR that an adversarial pass happened,
so the fallback warning matters as much as the counts: an approval produced by
same-vendor review must not read like a cross-vendor one.
"""
import importlib.util
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_spec = importlib.util.spec_from_file_location(
    "pair_loop", os.path.join(os.path.dirname(os.path.abspath(__file__)), "pair-loop.py"))
pair_loop = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pair_loop)


def _manifest(**over):
    m = {
        "run_id": "run-1", "task": "do the thing", "cwd": "/repo",
        "coder": "claude", "reviewer": "codex", "pr": 42,
        "rounds": [
            {"n": 1, "role": "coder", "tool": "claude", "findings_addressed": 0},
            {"n": 1, "role": "reviewer", "tool": "codex", "findings": 3,
             "verdict": "CHANGES_REQUESTED"},
            {"n": 2, "role": "coder", "tool": "claude", "findings_addressed": 3},
            {"n": 2, "role": "reviewer", "tool": "codex", "findings": 0,
             "verdict": "APPROVED"},
        ],
        "outcome": {"verdict": "APPROVED", "rounds": 2, "merged": None},
    }
    m.update(over)
    return m


class TestRenderReviewSummary(unittest.TestCase):
    def test_counts_rounds_and_findings(self):
        out = pair_loop.render_review_summary(_manifest())
        self.assertIn("| Rounds | 2 |", out)
        self.assertIn("| Findings raised | 3 |", out)
        self.assertIn("| Findings addressed | 3 |", out)
        self.assertIn("**APPROVED**", out)

    def test_cross_vendor_run_carries_no_warning(self):
        out = pair_loop.render_review_summary(_manifest())
        self.assertNotIn("Cross-vendor review unavailable", out)

    def test_fallback_run_names_the_model_and_warns(self):
        out = pair_loop.render_review_summary(_manifest(
            reviewer_fallback=True, reviewer_fallback_model="sonnet"))
        self.assertIn("Cross-vendor review unavailable", out)
        self.assertIn("sonnet", out, "the model is the only thing separating this from a self-review")
        self.assertIn("claude", out)

    def test_fallback_without_recorded_model_is_still_flagged(self):
        out = pair_loop.render_review_summary(_manifest(reviewer_fallback=True))
        self.assertIn("Cross-vendor review unavailable", out)
        self.assertIn("unspecified", out)

    def test_handles_a_run_with_no_rounds(self):
        out = pair_loop.render_review_summary(_manifest(
            rounds=[], outcome={"verdict": "APPROVED", "rounds": 0, "merged": None}))
        self.assertIn("| Findings raised | 0 |", out)


class TestPostPrComment(unittest.TestCase):
    def test_posts_body_to_the_right_pr(self):
        calls = []

        class R:
            returncode = 0
            stderr = ""

        def fake_run(cmd, **kw):
            calls.append((cmd, kw))
            return R()

        ok = pair_loop.post_pr_comment(42, "hello", "/repo", run=fake_run)
        self.assertTrue(ok)
        self.assertEqual(calls[0][0][:4], ["gh", "pr", "comment", "42"])
        self.assertIn("hello", calls[0][0])
        self.assertEqual(calls[0][1]["cwd"], "/repo")

    def test_nonzero_exit_warns_without_raising(self):
        # The review already happened and is recorded; a failed post must not
        # discard it.
        class R:
            returncode = 1
            stderr = "no such PR"

        ok = pair_loop.post_pr_comment(42, "hello", "/repo", run=lambda cmd, **kw: R())
        self.assertFalse(ok)

    def test_missing_gh_binary_warns_without_raising(self):
        def boom(cmd, **kw):
            raise OSError("gh not found")

        ok = pair_loop.post_pr_comment(42, "hello", "/repo", run=boom)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
