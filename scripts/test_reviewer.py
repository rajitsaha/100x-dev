#!/usr/bin/env python3
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reviewer


class TestReviewer(unittest.TestCase):
    def test_command_for_codex(self):
        cmd = reviewer.command_for("codex")
        self.assertEqual(cmd[0], "codex")
        self.assertIn("exec", cmd)

    def test_command_for_claude(self):
        cmd = reviewer.command_for("claude")
        self.assertEqual(cmd[0], "claude")
        self.assertIn("-p", cmd)

    def test_command_for_unknown_tool_raises(self):
        with self.assertRaises(ValueError):
            reviewer.command_for("gemini")

    def test_invoke_uses_injected_run_command(self):
        calls = []

        def fake_run(cmd, prompt, cwd, timeout):
            calls.append((cmd, prompt, cwd))
            return "some review\nVERDICT: APPROVED"

        # Pin _which so this test's expectations don't depend on whether a
        # real `codex` binary happens to be installed on the machine running
        # the suite (it must not shell out either way, but the *assertion*
        # here should be deterministic regardless of host PATH state).
        with mock.patch("reviewer._which", return_value="/usr/bin/codex"):
            result = reviewer.invoke("codex", "review this diff", "/repo", run_command=fake_run)
        self.assertEqual(result.output, "some review\nVERDICT: APPROVED")
        self.assertFalse(result.fallback_used)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][2], "/repo")

    def test_invoke_falls_back_to_same_vendor_when_cli_missing(self):
        with mock.patch("reviewer._which", return_value=None):
            def fake_run(cmd, prompt, cwd, timeout):
                return "fallback review\nVERDICT: APPROVED"
            result = reviewer.invoke("codex", "review this", "/repo", run_command=fake_run)
            self.assertTrue(result.fallback_used)

    def test_invoke_unsupported_tool_raises_even_when_path_lookup_fails(self):
        # A genuinely unsupported tool name must raise ValueError, not silently
        # fall back to "codex" just because it isn't on PATH.
        with self.assertRaises(ValueError):
            reviewer.invoke("gemini", "review this", "/repo", run_command=lambda *a: "unused")


if __name__ == "__main__":
    unittest.main()
