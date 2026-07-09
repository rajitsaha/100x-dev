#!/usr/bin/env python3
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import handoff


class TestHandoff(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "HANDOFF.md")

    def test_init_file_writes_header(self):
        handoff.init_file(self.path, "run1", "fix the bug", "feat/x", "claude", "codex")
        content = open(self.path).read()
        self.assertIn("run1", content)
        self.assertIn("fix the bug", content)
        self.assertIn("Coder: claude", content)
        self.assertIn("Reviewer: codex", content)

    def test_append_coder_round(self):
        handoff.init_file(self.path, "run1", "t", "b", "claude", "codex")
        handoff.append_coder_round(self.path, 1, "claude", "Implemented the fix in foo.py.")
        content = open(self.path).read()
        self.assertIn("Round 1 — CODER (claude)", content)
        self.assertIn("Implemented the fix in foo.py.", content)

    def test_append_reviewer_round_and_verdict(self):
        handoff.init_file(self.path, "run1", "t", "b", "claude", "codex")
        findings = [{"category": "correctness", "location": "foo.py:42", "text": "off-by-one"}]
        handoff.append_reviewer_round(self.path, 1, "codex", findings, "CHANGES_REQUESTED")
        content = open(self.path).read()
        self.assertIn("Round 1 — REVIEWER (codex)", content)
        self.assertIn("[correctness] foo.py:42", content)
        self.assertIn("VERDICT: CHANGES_REQUESTED", content)

    def test_parse_verdict_approved(self):
        self.assertEqual(handoff.parse_verdict("some review text\nVERDICT: APPROVED"), "APPROVED")

    def test_parse_verdict_changes_requested(self):
        self.assertEqual(handoff.parse_verdict("...\nVERDICT: CHANGES_REQUESTED\n"), "CHANGES_REQUESTED")

    def test_parse_verdict_missing_returns_none(self):
        self.assertIsNone(handoff.parse_verdict("no verdict line here"))

    def test_parse_findings_numbered_list(self):
        text = (
            "### Findings\n"
            "1. [correctness] src/foo.py:42 — off-by-one in loop bound\n"
            "2. [tests] no test covers the empty-input case\n"
            "VERDICT: CHANGES_REQUESTED\n"
        )
        findings = handoff.parse_findings(text)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0]["category"], "correctness")
        self.assertEqual(findings[0]["location"], "src/foo.py:42")
        self.assertIn("off-by-one", findings[0]["text"])
        self.assertEqual(findings[1]["category"], "tests")
        self.assertEqual(findings[1]["location"], "")

    def test_parse_findings_empty_when_none_present(self):
        self.assertEqual(handoff.parse_findings("VERDICT: APPROVED"), [])


if __name__ == "__main__":
    unittest.main()
