#!/usr/bin/env python3
"""
reviewer.py — non-interactive reviewer subprocess dispatch for pair-loop.

Supports codex ("codex exec --full-auto") and claude ("claude -p") as the
reviewer tool. The whole point of the coder<->reviewer split is a second,
*independent* opinion, so the fallback path matters as much as the happy path.

When the configured reviewer's CLI isn't on PATH we must fall back to the only
vendor present — which is the coder's own vendor. Reviewing with the coder's
exact configuration would be a self-review, the blind spot this design exists
to avoid, so the fallback additionally forces a DIFFERENT MODEL (see
`fallback_models` in scripts/_config.py). `fallback_used=True` is still flagged
so the caller can mark `reviewer_fallback: true` in the run manifest and warn
the user — cross-vendor stats exclude the run either way.

If neither CLI is on PATH there is no reviewer to be had; that raises with both
missing binaries named, rather than letting subprocess fail with a bare
FileNotFoundError from a command that was never going to run.

Known limitation: the coder is the interactive session, whose model we cannot
observe from here, so `fallback_models` is configured rather than derived. If
you set the coder session to the same model named in `fallback_models`, the
fallback review is a true self-review again — pick a fallback model you don't
code with.

`run_command` is injectable for tests; production code never needs to pass it.
No test in this module (or its companion scripts/test_reviewer.py) may shell
out to a real `codex`/`claude` binary — `run_command` and `_which` exist
specifically so tests can stub both.
"""
import shutil
import subprocess
from collections import namedtuple

# `model` is the model the reviewer actually ran with — None when we didn't
# pin one (the normal cross-vendor path uses each CLI's own default).
ReviewResult = namedtuple("ReviewResult", "output session_id fallback_used model")

_SUPPORTED_TOOLS = ("codex", "claude")

# Model-selection flag per vendor. Kept next to command_for so the two can't
# drift: `codex exec -m <model>`, `claude -p --model <model>`.
_MODEL_FLAG = {"codex": "-m", "claude": "--model"}


def _which(name):
    return shutil.which(name)


def command_for(tool, model=None):
    """Argv for `tool`, optionally pinned to `model`.

    The model flag is appended only when a model is given, so the cross-vendor
    path keeps using each CLI's configured default.
    """
    if tool == "codex":
        cmd = ["codex", "exec", "--full-auto"]
    elif tool == "claude":
        cmd = ["claude", "-p"]
    else:
        raise ValueError(f"unsupported reviewer tool: {tool!r}")
    if model:
        cmd += [_MODEL_FLAG[tool], model]
    return cmd


def _default_run_command(cmd, prompt, cwd, timeout):
    result = subprocess.run(cmd, input=prompt, cwd=cwd, capture_output=True,
                             text=True, timeout=timeout)
    return result.stdout


def invoke(tool, prompt, cwd, timeout=600, run_command=None, fallback_models=None):
    """Invoke `tool` as the reviewer.

    If `tool`'s CLI is missing from PATH, fall back to the other supported
    vendor — and pin that fallback to `fallback_models[vendor]` so the reviewer
    is never the coder's own vendor *and* model. Without the model pin this is
    a same-vendor, same-model self-review, which is worth roughly nothing as a
    second opinion. See the module docstring.

    Raises ValueError immediately for an unsupported tool name, regardless of
    PATH state — without this upfront check, an unsupported name that also
    happens to be missing from PATH would silently fall into the fallback
    branch (which only ever swaps between "codex" and "claude") and run as
    "codex" instead of surfacing the caller's mistake.

    Raises RuntimeError when neither CLI is on PATH: there is no reviewer to
    fall back to, and running the command anyway would surface as an opaque
    FileNotFoundError from subprocess.
    """
    if tool not in _SUPPORTED_TOOLS:
        raise ValueError(f"unsupported reviewer tool: {tool!r}")

    run_command = run_command or _default_run_command
    # Coerce rather than trust: config.json is user-editable and _config.py's
    # contract is that malformed input never raises. A scalar here (e.g.
    # `"fallback_models": "sonnet"`) would otherwise blow up on .get() at the
    # exact moment the fallback is needed.
    if not isinstance(fallback_models, dict):
        fallback_models = {}
    actual_tool = tool
    model = None
    fallback_used = False

    if _which(tool) is None:
        actual_tool = "claude" if tool == "codex" else "codex"
        if _which(actual_tool) is None:
            raise RuntimeError(
                f"no reviewer CLI available: neither {tool!r} nor {actual_tool!r} "
                f"is on PATH. Install one, or set pair_loop.reviewer in "
                f"~/.100xprism/config.json to a vendor you have."
            )
        fallback_used = True
        model = fallback_models.get(actual_tool)

    cmd = command_for(actual_tool, model)
    output = run_command(cmd, prompt, cwd, timeout)
    return ReviewResult(output=output, session_id=None,
                        fallback_used=fallback_used, model=model)
