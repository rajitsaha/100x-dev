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

    def test_command_for_pins_model_per_vendor(self):
        self.assertEqual(reviewer.command_for("claude", "sonnet")[-2:], ["--model", "sonnet"])
        self.assertEqual(reviewer.command_for("codex", "gpt-5.6-luna")[-2:], ["-m", "gpt-5.6-luna"])

    def test_command_for_without_model_adds_no_flag(self):
        # The cross-vendor path must keep each CLI's own configured default.
        self.assertNotIn("--model", reviewer.command_for("claude"))
        self.assertNotIn("-m", reviewer.command_for("codex"))

    def test_fallback_forces_a_different_model_than_the_coder(self):
        # The whole point of the coder<->reviewer split is an independent
        # opinion. When the cross-vendor CLI is missing we have to run on the
        # coder's vendor, so the model MUST differ or it is a self-review.
        calls = []

        def fake_run(cmd, prompt, cwd, timeout):
            calls.append(cmd)
            return "fallback review\nVERDICT: APPROVED"

        with mock.patch("reviewer._which", side_effect=lambda n: None if n == "codex" else "/usr/bin/claude"):
            result = reviewer.invoke("codex", "review this", "/repo", run_command=fake_run,
                                     fallback_models={"claude": "sonnet"})

        self.assertTrue(result.fallback_used)
        self.assertEqual(result.model, "sonnet")
        self.assertEqual(calls[0][0], "claude")
        self.assertEqual(calls[0][-2:], ["--model", "sonnet"], "reviewer must be pinned off the coder's model")

    def test_fallback_without_configured_model_does_not_invent_one(self):
        # No configured fallback model -> no --model flag. Better to run the
        # vendor default than to guess a model id that may not exist.
        calls = []

        def fake_run(cmd, prompt, cwd, timeout):
            calls.append(cmd)
            return "VERDICT: APPROVED"

        with mock.patch("reviewer._which", side_effect=lambda n: None if n == "codex" else "/usr/bin/claude"):
            result = reviewer.invoke("codex", "x", "/repo", run_command=fake_run, fallback_models={})

        self.assertTrue(result.fallback_used)
        self.assertIsNone(result.model)
        self.assertNotIn("--model", calls[0])

    def test_malformed_fallback_models_does_not_raise(self):
        # config.json is user-editable and _config.py's contract is that
        # malformed input never raises. A scalar where a dict belongs must not
        # blow up at the exact moment the fallback is needed.
        with mock.patch("reviewer._which", side_effect=lambda n: None if n == "codex" else "/usr/bin/claude"):
            result = reviewer.invoke("codex", "x", "/repo",
                                     run_command=lambda *a: "VERDICT: APPROVED",
                                     fallback_models="sonnet")
        self.assertTrue(result.fallback_used)
        self.assertIsNone(result.model)

    def test_invoke_raises_when_neither_cli_is_available(self):
        # There is no reviewer to fall back to. Fail with both binaries named
        # rather than letting subprocess raise FileNotFoundError on a command
        # that was never going to run.
        with mock.patch("reviewer._which", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                reviewer.invoke("codex", "review this", "/repo",
                                run_command=lambda *a: "unused")
        self.assertIn("codex", str(ctx.exception))
        self.assertIn("claude", str(ctx.exception))

    def test_non_string_model_value_never_reaches_argv(self):
        # {"claude": {"name": "sonnet"}} is accepted by _config's merge; a dict
        # in argv makes subprocess raise TypeError. Only a usable string counts.
        for bad in ({"name": "sonnet"}, 123, "", "   ", None, []):
            with self.subTest(bad=bad):
                calls = []
                with mock.patch("reviewer._which",
                                side_effect=lambda n: None if n == "codex" else "/usr/bin/claude"):
                    r = reviewer.invoke("codex", "x", "/repo",
                                        run_command=lambda cmd, *a: (calls.append(cmd), "VERDICT: APPROVED")[1],
                                        fallback_models={"claude": bad})
                self.assertIsNone(r.model)
                self.assertTrue(all(isinstance(a, str) for a in calls[0]))

    def test_require_cli_false_skips_path_discovery(self):
        # pair-loop's --reviewer-cmd supplies its own argv and never invokes a
        # vendor binary, so it must work on a machine with neither CLI.
        with mock.patch("reviewer._which", return_value=None):
            result = reviewer.invoke("codex", "x", "/repo",
                                     run_command=lambda *a: "VERDICT: APPROVED",
                                     require_cli=False)
        self.assertFalse(result.fallback_used)
        self.assertIsNone(result.model)

    def test_require_cli_true_still_raises_with_no_cli(self):
        with mock.patch("reviewer._which", return_value=None):
            with self.assertRaises(RuntimeError):
                reviewer.invoke("codex", "x", "/repo",
                                run_command=lambda *a: "unused", require_cli=True)

    def test_invoke_unsupported_tool_raises_even_when_path_lookup_fails(self):
        # A genuinely unsupported tool name must raise ValueError, not silently
        # fall back to "codex" just because it isn't on PATH.
        with self.assertRaises(ValueError):
            reviewer.invoke("gemini", "review this", "/repo", run_command=lambda *a: "unused")


if __name__ == "__main__":
    unittest.main()
