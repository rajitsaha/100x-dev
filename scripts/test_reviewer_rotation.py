#!/usr/bin/env python3
"""Covers select_fallback — which reviewer runs when the configured one is absent.

This replaced a hardcoded two-vendor swap. With three vendors that swap could
return a vendor that was itself missing, or the coder's own vendor while a
better option sat installed. `available` is injected so nothing depends on the
host's PATH.
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reviewer


class TestSelectFallback(unittest.TestCase):
    def test_never_returns_a_vendor_that_is_not_installed(self):
        for avail in ([], ["claude"], ["codex", "cursor"], list(reviewer._SUPPORTED_TOOLS)):
            with self.subTest(available=avail):
                got = reviewer.select_fallback("codex", coder="claude", available=avail)
                if got is not None:
                    self.assertIn(got, avail)

    def test_never_returns_the_preferred_vendor(self):
        # It is missing — that is why we are here.
        got = reviewer.select_fallback("codex", coder="claude",
                                       available=["codex", "claude"])
        self.assertNotEqual(got, "codex")

    def test_prefers_a_non_coder_vendor_over_the_coder_s_own(self):
        # The old swap could land on the coder's vendor while another was installed.
        got = reviewer.select_fallback("codex", coder="claude",
                                       available=["claude", "cursor"])
        self.assertEqual(got, "cursor")

    def test_prefers_a_multi_vendor_cli_for_genuine_independence(self):
        # cursor-agent can serve Grok/Kimi/GPT/Claude, so it offers a truly
        # third-party model rather than another of the coder's own vendor.
        got = reviewer.select_fallback("codex", coder="claude",
                                       available=["claude", "cursor", "codex"])
        self.assertEqual(got, "cursor")

    def test_falls_back_to_the_coder_s_vendor_only_as_a_last_resort(self):
        got = reviewer.select_fallback("codex", coder="claude", available=["claude"])
        self.assertEqual(got, "claude", "same-vendor is worse than nothing else, but better than no review")

    def test_returns_none_when_nothing_is_installed(self):
        self.assertIsNone(reviewer.select_fallback("codex", coder="claude", available=[]))

    def test_is_deterministic_regardless_of_input_order(self):
        a = reviewer.select_fallback("cursor", coder="claude", available=["codex", "claude"])
        b = reviewer.select_fallback("cursor", coder="claude", available=["claude", "codex"])
        self.assertEqual(a, b)

    def test_without_a_known_coder_still_avoids_the_preferred_vendor(self):
        got = reviewer.select_fallback("codex", coder=None,
                                       available=["codex", "claude", "cursor"])
        self.assertNotEqual(got, "codex")
        self.assertIn(got, ("claude", "cursor"))


class TestCursorVendor(unittest.TestCase):
    def test_cursor_runs_read_only_and_trusts_the_directory(self):
        cmd = reviewer.command_for("cursor", "composer-2.5")
        self.assertEqual(cmd[0], "cursor-agent")
        self.assertIn("-p", cmd)
        # cursor-agent refuses to run in an untrusted dir; --trust is required.
        self.assertIn("--trust", cmd)
        # --mode ask is what makes -p read-only: -p alone has write+shell.
        self.assertEqual(cmd[cmd.index("--mode") + 1], "ask")
        self.assertEqual(cmd[cmd.index("--model") + 1], "composer-2.5")
        # -f/--yolo would force-allow commands and defeat --mode ask.
        for unsafe in ("-f", "--yolo", "--force"):
            self.assertNotIn(unsafe, cmd)

    def test_cursor_is_a_supported_tool(self):
        self.assertIn("cursor", reviewer._SUPPORTED_TOOLS)


class TestInvokeUsesRotation(unittest.TestCase):
    def test_installed_checks_cursor_agent_not_a_binary_named_cursor(self):
        # Regression: _installed used to check _which(vendor_key), i.e.
        # _which("cursor") — a program that does not exist; the real binary is
        # cursor-agent. On a real machine with cursor-agent installed and no
        # binary literally named `cursor`, this made select_fallback silently
        # skip Cursor. Mock the exact executable names, not "anything but X",
        # so the vendor-key/executable-name distinction is actually exercised.
        real_binaries = {"codex", "claude", "cursor-agent"}
        with mock.patch("reviewer._which", side_effect=lambda n: f"/usr/bin/{n}" if n in real_binaries else None):
            self.assertTrue(reviewer._installed("cursor"),
                            "cursor-agent is on PATH; Cursor must be considered installed")
            got = reviewer.select_fallback("codex", coder="claude")
        self.assertEqual(got, "cursor")

    def test_installed_is_not_fooled_by_an_unrelated_binary_named_cursor(self):
        # The converse of the bug: some other program literally named `cursor`
        # existing on PATH must not make us think the Cursor CLI is available.
        with mock.patch("reviewer._which", side_effect=lambda n: "/usr/bin/cursor" if n == "cursor" else None):
            self.assertFalse(reviewer._installed("cursor"))

    def test_invoke_routes_to_the_rotation_winner_and_pins_its_model(self):
        calls = []
        real_binaries = {"claude", "cursor-agent"}  # codex missing — the trigger

        def avail(n):
            return f"/usr/bin/{n}" if n in real_binaries else None

        with mock.patch("reviewer._which", side_effect=avail):
            r = reviewer.invoke(
                "codex", "p", "/repo",
                run_command=lambda cmd, *a: (calls.append(cmd), "VERDICT: APPROVED")[1],
                fallback_models={"cursor": "composer-2.5", "claude": "sonnet"},
                coder="claude")

        self.assertTrue(r.fallback_used)
        self.assertEqual(calls[0][0], "cursor-agent", "should prefer the multi-vendor CLI over the coder's own")
        self.assertEqual(r.model, "composer-2.5")

    def test_error_names_every_supported_vendor_when_none_installed(self):
        with mock.patch("reviewer._which", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                reviewer.invoke("codex", "p", "/repo",
                                run_command=lambda *a: "unused", coder="claude")
        for vendor in reviewer._SUPPORTED_TOOLS:
            self.assertIn(vendor, str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
