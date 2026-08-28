#!/usr/bin/env python3
"""
reviewer.py — non-interactive reviewer subprocess dispatch for pair-loop.

Supports codex ("codex exec") and claude ("claude -p") as the reviewer tool.
The whole point of the coder<->reviewer split is a second, *independent*
opinion, so the fallback path matters as much as the happy path.

Reviewers always run READ-ONLY. The review diff is `git diff <branch>` against
a working tree the coder deliberately left uncommitted (see the pair-loop
module, Step 3), so a reviewer with write access can mutate the very thing it
is judging — the next round then reviews a mix of the coder's work and the
previous reviewer's edits, with no record of which is which. Each vendor
declares its own read-only mechanism in `_VENDORS`; there is no way to add a
vendor without one.

When the configured reviewer's CLI isn't on PATH we fall back to another vendor
that is present — often, but not always, the coder's own. Reviewing with the
coder's exact configuration would be a self-review, the blind spot this design
exists to avoid, so the fallback also pins a model from `fallback_models` (see
scripts/_config.py) when one is configured. That pin *reduces* the chance of a
same-model review; it does not guarantee it, because nothing compares the pin
to the coder's model. `fallback_used=True` is flagged so the caller can mark
`reviewer_fallback: true` in the run manifest and warn the user — cross-vendor
stats exclude the run either way.

If no supported CLI is on PATH there is no reviewer to be had; that raises
naming every supported vendor, rather than letting subprocess fail with a bare
FileNotFoundError from a command that was never going to run.

Known limitation, here: nothing in this module compares the fallback model to
the coder's — invoke()/select_fallback() only pick and pin a vendor/model, they
don't verify what actually ran. The comparison lives one layer up, in
pair-loop.py's cmd_review(), which has what this module deliberately doesn't:
each round's session_id and the claude_code/codex adapters that resolve a
session_id to the model it actually ran (#93). cmd_review refuses an APPROVED
verdict when the coder's and reviewer's resolved models match. That check is
still best-effort — it needs both session_ids to resolve, which isn't
guaranteed (no session lookup exists for Cursor yet, and a guessed session_id
can miss) — so a same-model review can still slip through when the models
can't be resolved. Set the coder session to the model named in
`fallback_models` and, if both resolve, the fallback review is caught as a
self-review rather than passing silently.

`run_command` is injectable for tests; production code never needs to pass it.
No test in this module (or its companion scripts/test_reviewer.py) may shell
out to a real `codex`/`claude` binary — `run_command` and `_which` exist
specifically so tests can stub both.
"""
import shutil
import subprocess
from collections import namedtuple

# `tool` is the vendor that actually ran — may differ from the tool the caller
# asked for whenever a fallback happened. Callers must read this rather than
# re-derive it: a hardcoded two-vendor guess in the caller previously went
# stale the moment a third vendor (Cursor) existed, silently mislabeling every
# non-adjacent fallback in the manifest, HANDOFF.md, and the PR summary.
# `model` is the model the reviewer actually ran with — None when we didn't
# pin one (the normal cross-vendor path uses each CLI's own default).
ReviewResult = namedtuple("ReviewResult", "output session_id fallback_used model tool")

# One table per vendor so base command, read-only policy, and model flag can't
# drift apart — and so a new vendor cannot be added without declaring how it is
# made read-only. `read_only` is not optional: a reviewer's job is to read and
# judge, and write access lets it mutate the very tree it is reviewing.
#
#   codex  --sandbox read-only     documented sandbox policy
#   claude --permission-mode plan  read-only/planning, no edits
_VENDORS = {
    "codex": {
        "base": ["codex", "exec"],
        "read_only": ["--sandbox", "read-only"],
        "model_flag": "-m",
    },
    "claude": {
        "base": ["claude", "-p"],
        "read_only": ["--permission-mode", "plan"],
        "model_flag": "--model",
    },
    # `--trust` is required, not optional: cursor-agent refuses to run in an
    # untrusted directory. It trusts the directory only — unlike `-f`/`--yolo`,
    # which force-allows commands and would defeat `--mode ask`.
    "cursor": {
        "base": ["cursor-agent", "-p", "--trust"],
        "read_only": ["--mode", "ask"],
        "model_flag": "--model",
    },
    "pi": {
        # Read-only via tool allowlist (no write/edit/bash).
        "base": ["pi", "-p"],
        "read_only": [
            "--no-skills", "--no-extensions", "--no-session",
            "--tools", "read,grep,find,ls",
        ],
        "model_flag": "--model",
        "provider_flag": "--provider",
    },
}

_SUPPORTED_TOOLS = tuple(_VENDORS)

# Vendors whose CLI can serve models from *other* vendors. When the configured
# reviewer is unavailable, one of these is a better fallback than the coder's
# own vendor: cursor-agent can run Grok, Kimi, GPT and Claude models, so it
# offers genuine third-party independence rather than same-vendor-different-model.
_MULTI_VENDOR = ("cursor",)


def _which(name):
    return shutil.which(name)


def _installed(tool):
    """Is `tool`'s CLI actually on PATH?

    Checks the real executable (`_VENDORS[tool]["base"][0]`), never the vendor
    key. For codex/claude the key happens to equal the binary name, which
    masked this: `_which("cursor")` checks for a program literally named
    `cursor` — it does not exist; the real binary is `cursor-agent`. Every
    availability check must go through this, not raw `_which(tool)`.
    """
    spec = _VENDORS.get(tool)
    return spec is not None and _which(spec["base"][0]) is not None


def command_for(tool, model=None, provider=None):
    """Argv for `tool`, read-only, optionally pinned to provider/model.

    Read-only is unconditional. Provider/model flags are appended only when
    given. Pi uses both; other vendors ignore provider.
    """
    spec = _VENDORS.get(tool)
    if spec is None:
        raise ValueError(f"unsupported reviewer tool: {tool!r}")
    cmd = list(spec["base"]) + list(spec["read_only"])
    if provider and spec.get("provider_flag"):
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError(f"invalid provider for {tool!r}: {provider!r}")
        cmd += [spec["provider_flag"], provider.strip()]
    if model:
        cmd += [spec["model_flag"], model]
    return cmd


def _default_run_command(cmd, prompt, cwd, timeout):
    result = subprocess.run(cmd, input=prompt, cwd=cwd, capture_output=True,
                             text=True, timeout=timeout)
    return result.stdout


def select_fallback(preferred, coder=None, available=None):
    """Pick a replacement reviewer when `preferred`'s CLI is missing.

    Ordered by how independent the result is, best first:

      1. A multi-vendor CLI that isn't the coder's vendor. cursor-agent can
         serve Grok/Kimi/GPT/Claude, so it can supply a genuinely third-party
         model rather than another of the coder's own.
      2. Any other installed vendor that isn't the coder's.
      3. The coder's own vendor — last resort, and worth something only if the
         pinned model differs from the coder's, which nothing here checks (#93).

    Returns None when nothing is installed. Replaces a hardcoded two-vendor
    swap (`"claude" if tool == "codex" else "codex"`) which, with three
    vendors, could return a vendor that was itself missing or was the coder's
    while a better option sat installed.

    `available` is injectable so tests don't depend on host PATH.
    """
    if available is None:
        available = [t for t in _SUPPORTED_TOOLS if _installed(t)]
    candidates = [t for t in available if t != preferred]

    cross = [t for t in candidates if t != coder]
    for tier in ([t for t in cross if t in _MULTI_VENDOR], cross, candidates):
        if tier:
            # Deterministic: _SUPPORTED_TOOLS order, not set/dict iteration order.
            return sorted(tier, key=_SUPPORTED_TOOLS.index)[0]
    return None


def invoke(tool, prompt, cwd, timeout=600, run_command=None, fallback_models=None,
           require_cli=True, coder=None, provider=None, model=None):
    """Invoke `tool` as the reviewer.

    If `tool`'s CLI is missing from PATH, `select_fallback` picks the most
    independent installed replacement (see its docstring for the ordering).
    Pass `coder` so it can avoid the coder's own vendor; without it, all
    non-preferred vendors look equally good.

    `provider` / `model` pin Pi (and model-flag vendors). On CLI fallback, the
    configured model pin is replaced by `fallback_models[actual_tool]` when set.

    Raises ValueError immediately for an unsupported tool name, regardless of
    PATH state — without this upfront check, an unsupported name that also
    happens to be missing from PATH would fall into the fallback branch and
    silently run as some other vendor instead of surfacing the caller's
    mistake.

    Raises RuntimeError when no supported CLI is on PATH: there is no reviewer
    to fall back to, and running the command anyway would surface as an opaque
    FileNotFoundError from subprocess.

    `require_cli=False` skips PATH discovery entirely. Callers that fully
    override dispatch (pair-loop's `--reviewer-cmd`) supply their own argv, so
    gating them on a vendor binary they never invoke would fail on a machine
    with no supported CLI at all — exactly the machine the override exists for.
    """
    if tool not in _SUPPORTED_TOOLS:
        raise ValueError(f"unsupported reviewer tool: {tool!r}")

    run_command = run_command or _default_run_command
    if not isinstance(fallback_models, dict):
        fallback_models = {}
    actual_tool = tool
    pinned_model = model
    pinned_provider = provider
    fallback_used = False

    if require_cli and not _installed(tool):
        actual_tool = select_fallback(tool, coder=coder)
        if actual_tool is None:
            raise RuntimeError(
                f"no reviewer CLI available: {tool!r} is not on PATH, and neither "
                f"is any supported alternative ({', '.join(_SUPPORTED_TOOLS)}). "
                f"Install one, or set pair_loop.reviewer in "
                f"~/.100xprism/config.json to a vendor you have."
            )
        fallback_used = True
        pinned_provider = None  # other vendors don't use provider_flag the same way
        pinned_model = fallback_models.get(actual_tool)
        if not isinstance(pinned_model, str) or not pinned_model.strip():
            pinned_model = None

    cmd = command_for(actual_tool, model=pinned_model, provider=pinned_provider)
    output = run_command(cmd, prompt, cwd, timeout)
    return ReviewResult(output=output, session_id=None, fallback_used=fallback_used,
                        model=pinned_model, tool=actual_tool)
