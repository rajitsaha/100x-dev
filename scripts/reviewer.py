#!/usr/bin/env python3
"""
reviewer.py — non-interactive reviewer subprocess dispatch for pair-loop.

Supports codex ("codex exec --full-auto") and claude ("claude -p") as the
reviewer tool. When the configured reviewer's CLI isn't on PATH, falls back to
the CODER's vendor as reviewer (a same-vendor self-review) and flags
`fallback_used=True` so the caller can mark `reviewer_fallback: true` in the
run manifest and warn the user — cross-vendor stats then exclude the run.

`run_command` is injectable for tests; production code never needs to pass it.
No test in this module (or its companion scripts/test_reviewer.py) may shell
out to a real `codex`/`claude` binary — `run_command` and `_which` exist
specifically so tests can stub both.
"""
import shutil
import subprocess
from collections import namedtuple

ReviewResult = namedtuple("ReviewResult", "output session_id fallback_used")

_SUPPORTED_TOOLS = ("codex", "claude")


def _which(name):
    return shutil.which(name)


def command_for(tool):
    if tool == "codex":
        return ["codex", "exec", "--full-auto"]
    if tool == "claude":
        return ["claude", "-p"]
    raise ValueError(f"unsupported reviewer tool: {tool!r}")


def _default_run_command(cmd, prompt, cwd, timeout):
    result = subprocess.run(cmd, input=prompt, cwd=cwd, capture_output=True,
                             text=True, timeout=timeout)
    return result.stdout


def invoke(tool, prompt, cwd, timeout=600, run_command=None):
    """Invoke `tool` as the reviewer. Falls back to the other supported vendor
    if `tool`'s CLI is missing from PATH.

    Raises ValueError immediately for an unsupported tool name, regardless of
    PATH state — without this upfront check, an unsupported name that also
    happens to be missing from PATH would silently fall into the same-vendor
    fallback branch (which only ever swaps between "codex" and "claude") and
    run as "codex" instead of surfacing the caller's mistake.
    """
    if tool not in _SUPPORTED_TOOLS:
        raise ValueError(f"unsupported reviewer tool: {tool!r}")

    run_command = run_command or _default_run_command
    actual_tool = tool
    fallback_used = False
    if _which(tool) is None:
        actual_tool = "claude" if tool == "codex" else "codex"
        fallback_used = True
    cmd = command_for(actual_tool)
    output = run_command(cmd, prompt, cwd, timeout)
    return ReviewResult(output=output, session_id=None, fallback_used=fallback_used)
