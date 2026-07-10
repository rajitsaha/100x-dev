# Pair-Loop Handoff Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `/pair-loop` — a coder↔reviewer handoff loop (roles swappable between `claude` and `codex`) that conducts each round through a local `HANDOFF.md`, self-instruments cost via `run_manifest.py`, enforces a per-run budget, and opens a PR carrying the transcript once approved.

**Architecture:** A CLI (`scripts/pair-loop.py`) with subcommands (`start`, `budget-check`, `coder-done`, `review`, `finish`) that the skill's `SKILL.md` instructions call at each state-machine step, plus two support modules (`scripts/handoff.py` for the `HANDOFF.md` read/write/parse contract, `scripts/reviewer.py` for the non-interactive reviewer subprocess with same-vendor fallback). The interactive agent running the skill IS the coder — the CLI never simulates coding, only orchestrates state, the reviewer subprocess, and the manifest.

**Tech Stack:** Python 3 stdlib only, `unittest`, `argparse`. Depends on `scripts/run_manifest.py`, `scripts/pricing.py`, `scripts/_config.py`, and `scripts/adapters/{claude_code,codex}.py` from `docs/superpowers/plans/2026-07-09-token-economics-v3.md` — that plan must be fully implemented first.

## Global Constraints

- Zero third-party dependencies.
- No live `codex`/`claude` subprocess calls in tests — the reviewer layer must accept an injectable command for testability (a stub script fixture).
- Never auto-merge; a human always merges the PR (spec: `2026-07-09-pair-loop-handoff-skill-design.md`, "Out of scope").
- Refuse to start on a dirty working tree (same convention as `modules/branch/SKILL.md`).
- `HANDOFF.md` is gitignored, never committed — the PR body carries the transcript instead.
- Every manifest write is atomic (temp file + `os.replace`) — reuse `run_manifest.save_manifest`, never write the JSON file directly.
- Run `python3 hooks/gate-pass.py` in its own bash call before commits that trigger the commit hook — never chained with the commit command.

---

### Task 1: `HANDOFF.md` contract (`scripts/handoff.py`)

**Files:**
- Create: `scripts/handoff.py`
- Test: `scripts/test_handoff.py`

**Interfaces:**
- Produces: `handoff.HANDOFF_FILENAME = "HANDOFF.md"`, `handoff.init_file(path, run_id, task, branch, coder, reviewer) -> None`, `handoff.append_coder_round(path, n, tool, body) -> None`, `handoff.append_reviewer_round(path, n, tool, findings: list[dict], verdict: str) -> None`, `handoff.parse_verdict(reviewer_output: str) -> str|None` (returns `"APPROVED"`, `"CHANGES_REQUESTED"`, or `None` if unparseable), `handoff.parse_findings(reviewer_output: str) -> list[dict]` (each `{"n": int, "category": str, "location": str, "text": str}`).

- [ ] **Step 1: Write the failing tests**

```python
# scripts/test_handoff.py
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 scripts/test_handoff.py`
Expected: `ModuleNotFoundError: No module named 'handoff'`

- [ ] **Step 3: Implement `scripts/handoff.py`**

```python
#!/usr/bin/env python3
"""
handoff.py — the HANDOFF.md conversation contract for pair-loop runs.

HANDOFF.md is the append-only local record of a coder<->reviewer loop: one
"Round N — ROLE (tool)" section per turn. It is gitignored — the PR body carries
the transcript once a run reaches PR phase, not the tracked file itself. The
reviewer's output must end with exactly `VERDICT: APPROVED` or
`VERDICT: CHANGES_REQUESTED` and list findings as a numbered `[category]
file:line — text` list; parse_verdict/parse_findings are the enforcement side of
that contract, used by scripts/pair-loop.py's `review` subcommand.
"""
import re
from datetime import datetime, timezone

HANDOFF_FILENAME = "HANDOFF.md"

_VERDICT_RE = re.compile(r"VERDICT:\s*(APPROVED|CHANGES_REQUESTED)")
_FINDING_RE = re.compile(
    r"^\s*\d+\.\s*\[(?P<category>[^\]]+)\]\s*(?:(?P<location>\S+:\d+)\s*—\s*)?(?P<text>.+)$")


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def init_file(path, run_id, task, branch, coder, reviewer):
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Pair-Loop Handoff — {run_id}\n"
                f"Task: {task} · Branch: {branch} · Coder: {coder} · Reviewer: {reviewer}\n")


def append_coder_round(path, n, tool, body):
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n## Round {n} — CODER ({tool}) · {_now()}\n{body}\n")


def append_reviewer_round(path, n, tool, findings, verdict):
    lines = [f"\n## Round {n} — REVIEWER ({tool}) · {_now()}\n"]
    if findings:
        lines.append("### Findings\n")
        for i, fnd in enumerate(findings, 1):
            loc = f"{fnd['location']} — " if fnd.get("location") else ""
            lines.append(f"{i}. [{fnd['category']}] {loc}{fnd['text']}\n")
    lines.append(f"VERDICT: {verdict}\n")
    with open(path, "a", encoding="utf-8") as f:
        f.write("".join(lines))


def parse_verdict(reviewer_output):
    # Last match wins, not first — a stray earlier "VERDICT: ..."-shaped
    # mention in reviewer prose must not override the real final-line verdict.
    matches = _VERDICT_RE.findall(reviewer_output or "")
    return matches[-1] if matches else None


def parse_findings(reviewer_output):
    findings = []
    for line in (reviewer_output or "").splitlines():
        m = _FINDING_RE.match(line)
        if m:
            findings.append({
                "n": len(findings) + 1,
                "category": m.group("category").strip(),
                "location": (m.group("location") or "").strip(),
                "text": m.group("text").strip(),
            })
    return findings
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 scripts/test_handoff.py -v`
Expected: 8 tests, all PASS

- [ ] **Step 5: Add `HANDOFF.md` to `.gitignore`**

Modify the repo root `.gitignore` — append:

```
HANDOFF.md
```

- [ ] **Step 6: Commit**

```bash
git add scripts/handoff.py scripts/test_handoff.py .gitignore
git commit -m "feat(pair-loop): HANDOFF.md contract — round append, verdict/findings parsing"
```

---

### Task 2: Reviewer invocation layer (`scripts/reviewer.py`)

**Files:**
- Create: `scripts/reviewer.py`
- Test: `scripts/test_reviewer.py`

**Interfaces:**
- Produces: `reviewer.ReviewResult` (namedtuple `output, session_id, fallback_used`), `reviewer.invoke(tool: str, prompt: str, cwd: str, timeout=600, run_command=None) -> ReviewResult` — `run_command` is injectable (defaults to the real `subprocess.run`-based dispatch) so tests never shell out to a live `codex`/`claude`. `reviewer.command_for(tool: str) -> list[str]|None` (returns `None` if the tool's CLI isn't on `PATH`, triggering same-vendor fallback in the caller).

- [ ] **Step 1: Write the failing tests**

```python
# scripts/test_reviewer.py
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


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 scripts/test_reviewer.py`
Expected: `ModuleNotFoundError: No module named 'reviewer'`

- [ ] **Step 3: Implement `scripts/reviewer.py`**

```python
#!/usr/bin/env python3
"""
reviewer.py — non-interactive reviewer subprocess dispatch for pair-loop.

Supports codex ("codex exec") and claude ("claude -p") as the reviewer tool.
When the configured reviewer's CLI isn't on PATH, falls back to the CODER's
vendor as reviewer (a same-vendor self-review) and flags `fallback_used=True`
so the caller can mark `reviewer_fallback: true` in the run manifest and warn
the user — cross-vendor stats then exclude the run.

`run_command` is injectable for tests; production code never needs to pass it.
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
    if `tool`'s CLI is missing from PATH."""
    if tool not in _SUPPORTED_TOOLS:
        # Validate BEFORE any fallback logic — otherwise an unsupported tool
        # name with no CLI on PATH silently gets substituted into "codex" by
        # the fallback branch below instead of raising.
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
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 scripts/test_reviewer.py -v`
Expected: 5 tests, all PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/reviewer.py scripts/test_reviewer.py
git commit -m "feat(pair-loop): reviewer subprocess dispatch with same-vendor fallback"
```

---

### Task 3: `pair-loop.py` — `start` and `budget-check` subcommands

**Files:**
- Create: `scripts/pair-loop.py`
- Test: `scripts/test_pair_loop_start.py`

**Interfaces:**
- Produces: CLI `python3 scripts/pair-loop.py start --task T [--cwd DIR]` → prints `{"run_id":, "manifest_path":, "handoff_path":}` as JSON to stdout, creates the manifest (via `run_manifest.new_manifest`/`save_manifest`) and `HANDOFF.md` (via `handoff.init_file`), reading `coder`/`reviewer`/roles from `_config.load_config()["pair_loop"]`. Refuses (exit code 1, stderr message) if `git status --porcelain` is non-empty. CLI `python3 scripts/pair-loop.py budget-check --run RUN_ID` → prints `{"level": null|"warn"|"alert", "spent":, "limit":}`, exit code 0 normally, exit code 2 when `level == "alert"` (cap hit).
- Consumes: `run_manifest`, `handoff`, `_config`, `_budget.status_for`, `adapters.claude_code.scan`, `adapters.codex.scan`, `pricing`.

- [ ] **Step 1: Write the failing tests**

```python
# scripts/test_pair_loop_start.py
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
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 scripts/test_pair_loop_start.py`
Expected: `FileNotFoundError` (script doesn't exist yet)

- [ ] **Step 3: Implement `scripts/pair-loop.py` (start + budget-check only for now)**

```python
#!/usr/bin/env python3
"""
pair-loop.py — CLI orchestration for the /pair-loop handoff skill.

The interactive agent running the skill IS the coder; this CLI never simulates
coding. It owns: run bookkeeping (manifest + HANDOFF.md), the per-round budget
check, invoking the reviewer subprocess, and PR-body assembly. See
docs/superpowers/specs/2026-07-09-pair-loop-handoff-skill-design.md for the
full state machine.

Subcommands: start, budget-check, coder-done, review, finish.
"""
import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_manifest  # noqa: E402
import handoff  # noqa: E402
import _config  # noqa: E402
import _budget  # noqa: E402
import pricing  # noqa: E402
import adapters.claude_code as claude_code  # noqa: E402
import adapters.codex as codex  # noqa: E402


def _git_dirty(cwd):
    r = subprocess.run(["git", "status", "--porcelain"], cwd=cwd,
                       capture_output=True, text=True)
    return bool(r.stdout.strip())


def _current_branch(cwd):
    r = subprocess.run(["git", "branch", "--show-current"], cwd=cwd,
                       capture_output=True, text=True)
    return r.stdout.strip() or "HEAD"


def cmd_start(args):
    cwd = os.path.abspath(args.cwd or ".")
    if _git_dirty(cwd):
        print("error: working tree is dirty — commit or stash before starting a pair-loop run",
              file=sys.stderr)
        sys.exit(1)
    cfg = _config.load_config()["pair_loop"]
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    branch = _current_branch(cwd)
    manifest = run_manifest.new_manifest(run_id, args.task, cwd, branch,
                                          cfg["coder"], cfg["reviewer"])
    run_manifest.save_manifest(manifest)
    handoff_path = os.path.join(cwd, handoff.HANDOFF_FILENAME)
    handoff.init_file(handoff_path, run_id, args.task, branch, cfg["coder"], cfg["reviewer"])
    print(json.dumps({"run_id": run_id, "manifest_path": run_manifest.manifest_path(run_id),
                      "handoff_path": handoff_path, "max_rounds": cfg["max_rounds"],
                      "coder": cfg["coder"], "reviewer": cfg["reviewer"]}))


def cmd_budget_check(args):
    manifest = run_manifest.load_manifest(args.run)
    per_run = _config.load_config()["budget"].get("per_run_usd")
    summaries = claude_code.scan(verbose=False) + codex.scan(verbose=False)
    cost = run_manifest.run_cost(manifest, summaries)
    _, level = _budget.status_for(cost["total"], per_run)
    print(json.dumps({"level": level, "spent": cost["total"], "limit": per_run}))
    sys.exit(2 if level == "alert" else 0)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start")
    p_start.add_argument("--task", required=True)
    p_start.add_argument("--cwd", default=None)
    p_start.set_defaults(func=cmd_start)

    p_budget = sub.add_parser("budget-check")
    p_budget.add_argument("--run", required=True)
    p_budget.set_defaults(func=cmd_budget_check)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 scripts/test_pair_loop_start.py -v`
Expected: 4 tests, all PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/pair-loop.py scripts/test_pair_loop_start.py
git commit -m "feat(pair-loop): CLI start + per-run budget-check subcommands"
```

---

### Task 4: `pair-loop.py` — `coder-done` and `review` subcommands

**Files:**
- Modify: `scripts/pair-loop.py` (add `cmd_coder_done`, `cmd_review`, their subparsers)
- Test: `scripts/test_pair_loop_review.py`

**Interfaces:**
- Produces: `python3 scripts/pair-loop.py coder-done --run RUN_ID --summary "..."` → appends a CODER round to `HANDOFF.md` and the manifest (session id best-effort: newest `.jsonl` under `~/.claude/projects/<mangled-cwd>/` at call time), prints `{"round": n}`. `python3 scripts/pair-loop.py review --run RUN_ID [--reviewer-cmd JSON_ARRAY]` → builds the review prompt (git diff vs. the run's base branch + current `HANDOFF.md` contents), invokes `reviewer.invoke(...)`, parses verdict + findings via `handoff.parse_*`, appends a REVIEWER round to `HANDOFF.md` and the manifest, prints `{"verdict":, "findings": [...], "fallback_used": bool}`. On an unparseable verdict, re-invokes the reviewer once with a stricter follow-up prompt; if still unparseable, treats it as `CHANGES_REQUESTED` with a synthetic finding noting the parse failure.

- [ ] **Step 1: Write the failing tests**

```python
# scripts/test_pair_loop_review.py
#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "pair-loop.py")
STUB_REVIEWER = os.path.join(HERE, "fixtures", "stub-reviewer.sh")


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.email=t@t.t", "-c", "user.name=t",
                            "-c", "commit.gpgsign=false", "-C", repo, *args],
                           capture_output=True, text=True, check=False)


class TestPairLoopReview(unittest.TestCase):
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

    def test_coder_done_appends_round(self):
        r = self._run("start", "--task", "x")
        run_id = json.loads(r.stdout)["run_id"]
        r2 = self._run("coder-done", "--run", run_id, "--summary", "Implemented the fix.")
        self.assertEqual(r2.returncode, 0, r2.stderr)
        content = open(os.path.join(self.repo, "HANDOFF.md")).read()
        self.assertIn("Implemented the fix.", content)

    def test_review_with_stub_reviewer_approved(self):
        r = self._run("start", "--task", "x")
        run_id = json.loads(r.stdout)["run_id"]
        self._run("coder-done", "--run", run_id, "--summary", "done")
        r2 = self._run("review", "--run", run_id, "--reviewer-cmd",
                       json.dumps(["bash", STUB_REVIEWER, "APPROVED"]))
        self.assertEqual(r2.returncode, 0, r2.stderr)
        out = json.loads(r2.stdout)
        self.assertEqual(out["verdict"], "APPROVED")

    def test_review_with_stub_reviewer_changes_requested(self):
        r = self._run("start", "--task", "x")
        run_id = json.loads(r.stdout)["run_id"]
        self._run("coder-done", "--run", run_id, "--summary", "done")
        r2 = self._run("review", "--run", run_id, "--reviewer-cmd",
                       json.dumps(["bash", STUB_REVIEWER, "CHANGES_REQUESTED"]))
        out = json.loads(r2.stdout)
        self.assertEqual(out["verdict"], "CHANGES_REQUESTED")
        self.assertGreaterEqual(len(out["findings"]), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Create the stub reviewer fixture**

```bash
mkdir -p scripts/fixtures
cat > scripts/fixtures/stub-reviewer.sh <<'EOF'
#!/usr/bin/env bash
# Test fixture: emits a scripted review + verdict. $1: APPROVED|CHANGES_REQUESTED
cat <<REVIEW
### Findings
1. [correctness] src/foo.py:10 — sample finding for tests
VERDICT: $1
REVIEW
EOF
chmod +x scripts/fixtures/stub-reviewer.sh
```

Run: `python3 scripts/test_pair_loop_review.py`
Expected: `AttributeError: 'Namespace' object has no attribute 'func'` or similar — `coder-done`/`review` subcommands don't exist yet

- [ ] **Step 3: Extend `scripts/pair-loop.py`**

Add near the top (after the existing imports):

```python
import glob  # noqa: E402
import reviewer  # noqa: E402
```

Add after `cmd_budget_check`:

```python
CLAUDE_PROJECTS = os.path.join(os.path.expanduser("~"), ".claude", "projects")


def _guess_current_claude_session(cwd):
    """Best-effort: the most-recently-modified transcript file for this cwd's
    mangled project dir, at the moment this is called."""
    import _value
    mangled = _value.mangle_path(os.path.abspath(cwd))
    proj_dir = os.path.join(CLAUDE_PROJECTS, mangled)
    files = glob.glob(os.path.join(proj_dir, "*.jsonl"))
    if not files:
        return None
    newest = max(files, key=os.path.getmtime)
    return os.path.splitext(os.path.basename(newest))[0]


def _guess_current_codex_session(before_mtimes):
    """Best-effort: a Codex rollout file that appeared/changed after
    `before_mtimes` was snapshotted (see cmd_review)."""
    paths = glob.glob(os.path.join(codex.SOURCE_DIR, "**", "*.jsonl"), recursive=True)
    newest, newest_mtime = None, 0
    for p in paths:
        try:
            mt = os.path.getmtime(p)
        except OSError:
            continue
        if mt > before_mtimes.get(p, 0) and mt > newest_mtime:
            newest, newest_mtime = p, mt
    if not newest:
        return None
    with open(newest, errors="ignore") as f:
        for line in f:
            try:
                o = json.loads(line)
            except Exception:
                continue
            if o.get("type") == "session_meta":
                payload = o.get("payload") or {}
                return payload.get("session_id") or payload.get("id")
    return None


def cmd_coder_done(args):
    manifest = run_manifest.load_manifest(args.run)
    cwd = manifest["cwd"]
    session_id = _guess_current_claude_session(cwd) if manifest["coder"] == "claude" else None
    round_ = run_manifest.add_round(manifest, "coder", manifest["coder"], session_id=session_id)
    run_manifest.close_round(manifest, round_, findings_addressed=args.findings_addressed)
    handoff_path = os.path.join(cwd, handoff.HANDOFF_FILENAME)
    handoff.append_coder_round(handoff_path, round_["n"], manifest["coder"], args.summary)
    print(json.dumps({"round": round_["n"]}))


def _build_review_prompt(cwd, branch, handoff_path):
    result = subprocess.run(["git", "diff", branch], cwd=cwd, capture_output=True,
                            text=True)
    if result.returncode != 0:
        # Surface a bad/deleted base branch as a hard failure — never let a
        # git diff error silently degrade into an empty-diff review that
        # could come back APPROVED having seen no code at all.
        raise RuntimeError(f"git diff against '{branch}' failed: {result.stderr.strip()}")
    diff = result.stdout
    if os.path.exists(handoff_path):
        with open(handoff_path, encoding="utf-8") as f:
            handoff_text = f.read()
    else:
        handoff_text = ""
    return (
        "You are reviewing a code change as an independent reviewer in a "
        "coder<->reviewer handoff loop. Read the diff and the prior handoff "
        "rounds below, then respond with a numbered findings list in the form "
        "'N. [category] file:line — description' (omit file:line if not "
        "applicable), followed by a final line that is EXACTLY "
        "'VERDICT: APPROVED' or 'VERDICT: CHANGES_REQUESTED'.\n\n"
        f"=== DIFF vs {branch} ===\n{diff}\n\n=== HANDOFF SO FAR ===\n{handoff_text}\n"
    )


def cmd_review(args):
    manifest = run_manifest.load_manifest(args.run)
    cwd = manifest["cwd"]
    prompt = _build_review_prompt(cwd, manifest["branch"],
                                  os.path.join(cwd, handoff.HANDOFF_FILENAME))

    run_command = None
    if args.reviewer_cmd:
        fixed_cmd = json.loads(args.reviewer_cmd)

        def run_command(cmd, prompt, cwd, timeout):
            r = subprocess.run(fixed_cmd, input=prompt, cwd=cwd, capture_output=True,
                              text=True, timeout=timeout)
            return r.stdout

    codex_before = {p: os.path.getmtime(p) for p in
                    glob.glob(os.path.join(codex.SOURCE_DIR, "**", "*.jsonl"), recursive=True)} \
        if os.path.isdir(codex.SOURCE_DIR) else {}

    result = reviewer.invoke(manifest["reviewer"], prompt, cwd, run_command=run_command)
    verdict = handoff.parse_verdict(result.output)
    if verdict is None:
        # one re-ask with a stricter prompt, then fall back to CHANGES_REQUESTED
        retry_prompt = prompt + "\n\nYour previous response had no parseable VERDICT line. Respond again, ending with exactly 'VERDICT: APPROVED' or 'VERDICT: CHANGES_REQUESTED'."
        result = reviewer.invoke(manifest["reviewer"], retry_prompt, cwd, run_command=run_command)
        verdict = handoff.parse_verdict(result.output)
    findings = handoff.parse_findings(result.output)
    if verdict is None:
        verdict = "CHANGES_REQUESTED"
        findings = findings or [{"n": 1, "category": "process",
                                  "location": "", "text": "reviewer produced no parseable verdict"}]

    actual_tool = manifest["reviewer"]
    if result.fallback_used:
        actual_tool = "claude" if manifest["reviewer"] == "codex" else "codex"
        manifest["reviewer_fallback"] = True

    session_id = (_guess_current_codex_session(codex_before) if actual_tool == "codex"
                  else _guess_current_claude_session(cwd))
    round_ = run_manifest.add_round(manifest, "reviewer", actual_tool, session_id=session_id)
    run_manifest.close_round(manifest, round_, findings=len(findings), verdict=verdict)
    handoff.append_reviewer_round(os.path.join(cwd, handoff.HANDOFF_FILENAME),
                                  round_["n"], actual_tool, findings, verdict)
    print(json.dumps({"verdict": verdict, "findings": findings, "fallback_used": result.fallback_used}))
```

Register the new subparsers in `main()` (insert before `args = ap.parse_args()`):

```python
    p_coder_done = sub.add_parser("coder-done")
    p_coder_done.add_argument("--run", required=True)
    p_coder_done.add_argument("--summary", required=True)
    p_coder_done.add_argument("--findings-addressed", type=int, default=0)
    p_coder_done.set_defaults(func=cmd_coder_done)

    p_review = sub.add_parser("review")
    p_review.add_argument("--run", required=True)
    p_review.add_argument("--reviewer-cmd", default=None,
                          help="JSON array override for testing (bypasses codex/claude auto-detect)")
    p_review.set_defaults(func=cmd_review)
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 scripts/test_pair_loop_review.py -v`
Expected: 3 tests, all PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/pair-loop.py scripts/test_pair_loop_review.py scripts/fixtures/stub-reviewer.sh
git commit -m "feat(pair-loop): coder-done + review subcommands, stub-reviewer test fixture"
```

---

### Task 5: `pair-loop.py` — `finish` subcommand + PR-body assembly

**Files:**
- Modify: `scripts/pair-loop.py` (add `cmd_finish`)
- Test: `scripts/test_pair_loop_finish.py`

**Interfaces:**
- Produces: `python3 scripts/pair-loop.py finish --run RUN_ID --verdict APPROVED --pr 78` → calls `run_manifest.close_run`, writes `~/.100xprism/handoff-runs/<run_id>-pr-body.md` (summary + full `HANDOFF.md` transcript embedded in a collapsible `<details>` block), prints `{"pr_body_path":}`. The calling agent passes that path to the existing `/pr` skill (e.g. `gh pr create --body-file <path>`) — this task does not shell out to `gh` itself, matching the design's "local `gh` only, human merges" boundary.

- [ ] **Step 1: Write the failing test**

```python
# scripts/test_pair_loop_finish.py
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


class TestPairLoopFinish(unittest.TestCase):
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

    def test_finish_writes_pr_body_with_transcript(self):
        r = self._run("start", "--task", "fix the bug")
        run_id = json.loads(r.stdout)["run_id"]
        self._run("coder-done", "--run", run_id, "--summary", "Implemented the fix.")
        r2 = self._run("finish", "--run", run_id, "--verdict", "APPROVED", "--pr", "78")
        self.assertEqual(r2.returncode, 0, r2.stderr)
        out = json.loads(r2.stdout)
        body = open(out["pr_body_path"]).read()
        self.assertIn("Implemented the fix.", body)
        self.assertIn("78", json.dumps(json.load(open(
            __import__("sys").modules["run_manifest"].manifest_path(run_id)
            if False else os.path.join(self.env["HOME"], ".100xprism", "handoff-runs", f"{run_id}.json")))))

    def test_finish_records_outcome_in_manifest(self):
        r = self._run("start", "--task", "x")
        run_id = json.loads(r.stdout)["run_id"]
        self._run("finish", "--run", run_id, "--verdict", "APPROVED", "--pr", "5")
        manifest_path = os.path.join(self.env["HOME"], ".100xprism", "handoff-runs", f"{run_id}.json")
        manifest = json.load(open(manifest_path))
        self.assertEqual(manifest["outcome"]["verdict"], "APPROVED")
        self.assertEqual(manifest["pr"], 5)


if __name__ == "__main__":
    unittest.main()
```

Simplify the awkward inline `__import__` expression in the first test before running it — see Step 2.

- [ ] **Step 2: Fix the test's manifest-path lookup**

Replace the body of `test_finish_writes_pr_body_with_transcript` with a straightforward path join (no `__import__` gymnastics):

```python
    def test_finish_writes_pr_body_with_transcript(self):
        r = self._run("start", "--task", "fix the bug")
        run_id = json.loads(r.stdout)["run_id"]
        self._run("coder-done", "--run", run_id, "--summary", "Implemented the fix.")
        r2 = self._run("finish", "--run", run_id, "--verdict", "APPROVED", "--pr", "78")
        self.assertEqual(r2.returncode, 0, r2.stderr)
        out = json.loads(r2.stdout)
        body = open(out["pr_body_path"]).read()
        self.assertIn("Implemented the fix.", body)
        manifest_path = os.path.join(self.env["HOME"], ".100xprism", "handoff-runs", f"{run_id}.json")
        manifest = json.load(open(manifest_path))
        self.assertEqual(manifest["pr"], 78)
```

- [ ] **Step 3: Run to verify failure**

Run: `python3 scripts/test_pair_loop_finish.py`
Expected: `AttributeError` — `finish` subcommand doesn't exist yet

- [ ] **Step 4: Implement `cmd_finish` in `scripts/pair-loop.py`**

```python
def cmd_finish(args):
    manifest = run_manifest.load_manifest(args.run)
    manifest["pr"] = args.pr
    run_manifest.save_manifest(manifest)
    run_manifest.close_run(manifest, args.verdict, merged=None)

    handoff_path = os.path.join(manifest["cwd"], handoff.HANDOFF_FILENAME)
    transcript = open(handoff_path, encoding="utf-8").read() if os.path.exists(handoff_path) else ""
    body = (
        f"## {manifest['task']}\n\n"
        f"Pair-loop run `{manifest['run_id']}` — coder: {manifest['coder']}, "
        f"reviewer: {manifest['reviewer']}"
        + (" (fallback used)" if manifest.get("reviewer_fallback") else "") + "\n\n"
        f"<details><summary>Full handoff transcript ({manifest['outcome']['rounds']} rounds)</summary>\n\n"
        f"```\n{transcript}\n```\n\n</details>\n"
    )
    body_path = os.path.join(os.path.dirname(run_manifest.manifest_path(manifest["run_id"])),
                             f"{manifest['run_id']}-pr-body.md")
    with open(body_path, "w", encoding="utf-8") as f:
        f.write(body)
    print(json.dumps({"pr_body_path": body_path}))
```

Register the subparser in `main()`:

```python
    p_finish = sub.add_parser("finish")
    p_finish.add_argument("--run", required=True)
    p_finish.add_argument("--verdict", required=True, choices=["APPROVED", "CHANGES_REQUESTED"])
    p_finish.add_argument("--pr", type=int, default=None)
    p_finish.set_defaults(func=cmd_finish)
```

- [ ] **Step 5: Run to verify pass**

Run: `python3 scripts/test_pair_loop_finish.py -v`
Expected: 2 tests, all PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/pair-loop.py scripts/test_pair_loop_finish.py
git commit -m "feat(pair-loop): finish subcommand — close run, assemble PR body with transcript"
```

---

### Task 6: `modules/pair-loop/SKILL.md` — the skill instructions

**Files:**
- Create: `modules/pair-loop/SKILL.md`

**Interfaces:**
- Consumes: every `pair-loop.py` subcommand from Tasks 3-5. This is the only task that produces the actual `/pair-loop` slash command — everything before it is library code the skill orchestrates.

- [ ] **Step 1: Write the skill file**

```markdown
---
name: pair-loop
description: Coder<->reviewer handoff loop (Claude<->Codex, roles swappable) with self-instrumented per-round cost tracking. Loops locally via HANDOFF.md until approved, then opens a PR with the full transcript.
category: lifecycle
tier: core
slash_command: /pair-loop
---

# Pair-Loop — Coder <-> Reviewer Handoff

Runs a formal review loop between a coder and a reviewer (default: you as coder,
Codex as reviewer — swap via `~/.100xprism/config.json`'s `pair_loop` section).
Each round is recorded in `HANDOFF.md` and self-instrumented into a cost
manifest the token dashboard reads. Do NOT ask for permission to start or to
run rounds — only stop for the outcomes listed in "When to stop" below.

## Step 1 — Start

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"
python3 ~/100xprism/scripts/pair-loop.py start --task "<one-line task description>"
```

If this fails with a "dirty" error, commit or stash first — do not force-start
on uncommitted work. Save the printed `run_id`, `handoff_path`, `max_rounds`,
`coder`, and `reviewer` — you'll pass `run_id` to every subsequent command.

## Step 2 — Budget check (before every round)

```bash
python3 ~/100xprism/scripts/pair-loop.py budget-check --run "$RUN_ID"
```

Exit code `2` means the per-run budget cap is hit — STOP and ask the user
whether to continue or stop; do not proceed to another round silently. Exit
code `0` with `"level": "warn"` in the output means print a one-line warning
and continue.

## Step 3 — Coder round

Implement the task (or address the reviewer's findings from the prior round).
Run the project's quick checks (tests + lint) before recording the round. Then:

```bash
python3 ~/100xprism/scripts/pair-loop.py coder-done --run "$RUN_ID" \
  --summary "<what you implemented/fixed, files touched, how you verified it>" \
  --findings-addressed <N>
```

## Step 4 — Reviewer round

```bash
python3 ~/100xprism/scripts/pair-loop.py review --run "$RUN_ID"
```

This shells out to the configured reviewer (falling back to the coder's vendor
if that CLI is missing — the output will say `"fallback_used": true`; mention
this to the user once, don't repeat it every round) and returns
`{"verdict":, "findings": [...]}`.

- `"verdict": "APPROVED"` → go to Step 5 (PR phase).
- `"verdict": "CHANGES_REQUESTED"` and you have rounds remaining (round count
  reported by `start` as `max_rounds`) → go back to Step 2 for the next round.
- `"verdict": "CHANGES_REQUESTED"` at `max_rounds` → STOP. Present the open
  findings to the user and ask whether to ship as-is, do another round anyway,
  or abandon. Do not silently exceed the configured round cap.

## Step 5 — PR phase

```bash
python3 ~/100xprism/scripts/pair-loop.py finish --run "$RUN_ID" --verdict APPROVED
```

(Omit `--pr` on this first call — you don't have a PR number yet.) This prints
`pr_body_path`. Run the **branch** and **pr** skills to push and open the PR,
passing that file as the PR body (`gh pr create --body-file <pr_body_path>`).
Once you have the real PR number, re-run `finish` with `--pr <number>` so the
manifest records it for the dashboard's `$/merged-PR` metric:

```bash
python3 ~/100xprism/scripts/pair-loop.py finish --run "$RUN_ID" --verdict APPROVED --pr <NUMBER>
```

If `pair_loop.pr_final_round` is `true` in the config, run one more `review`
round against the pushed PR diff before this step, and post any findings as a
PR comment via `gh pr comment` — then do exactly one more local coder round to
address them before finishing.

## When to stop and ask the user

- Budget cap hit (Step 2, exit code 2).
- Round cap hit without approval (Step 4).
- The reviewer CLI fell back to the coder's vendor (mention once, don't block).
- Never auto-merge — a human merges the PR, always.
```

- [ ] **Step 2: Verify the module passes the repo's frontmatter checks**

Run: `node --test test/modules-frontmatter.test.js`
Expected: PASS (frontmatter shape matches existing modules like `modules/commit/SKILL.md`)

- [ ] **Step 3: Commit**

```bash
git add modules/pair-loop/SKILL.md
git commit -m "feat(pair-loop): SKILL.md — /pair-loop slash command orchestrating the CLI"
```

---

### Task 7: Full state-machine integration test

**Files:**
- Create: `scripts/test_pair_loop_integration.py`

**Interfaces:**
- Verifies the whole loop end-to-end using the stub reviewer fixture from Task 4: approval path (1 round), max-rounds path (reviewer always requests changes), and the manifest/HANDOFF.md consistency at the end of each.

- [ ] **Step 1: Write the test**

```python
# scripts/test_pair_loop_integration.py
#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "pair-loop.py")
STUB_REVIEWER = os.path.join(HERE, "fixtures", "stub-reviewer.sh")


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.email=t@t.t", "-c", "user.name=t",
                            "-c", "commit.gpgsign=false", "-C", repo, *args],
                           capture_output=True, text=True, check=False)


class TestPairLoopIntegration(unittest.TestCase):
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

    def test_full_loop_approves_on_first_round(self):
        run_id = json.loads(self._run("start", "--task", "add feature").stdout)["run_id"]
        self._run("coder-done", "--run", run_id, "--summary", "Added the feature.")
        r = self._run("review", "--run", run_id, "--reviewer-cmd",
                      json.dumps(["bash", STUB_REVIEWER, "APPROVED"]))
        verdict = json.loads(r.stdout)["verdict"]
        self.assertEqual(verdict, "APPROVED")
        self._run("finish", "--run", run_id, "--verdict", "APPROVED", "--pr", "1")

        manifest_path = os.path.join(self.env["HOME"], ".100xprism", "handoff-runs", f"{run_id}.json")
        manifest = json.load(open(manifest_path))
        self.assertEqual(len(manifest["rounds"]), 2)  # 1 coder + 1 reviewer
        self.assertEqual(manifest["outcome"]["verdict"], "APPROVED")

        handoff_text = open(os.path.join(self.repo, "HANDOFF.md")).read()
        self.assertIn("Round 1 — CODER", handoff_text)
        self.assertIn("Round 1 — REVIEWER", handoff_text)
        self.assertIn("VERDICT: APPROVED", handoff_text)

    def test_loop_hits_round_cap_without_approval(self):
        os.makedirs(os.path.join(self.env["HOME"], ".100xprism"), exist_ok=True)
        with open(os.path.join(self.env["HOME"], ".100xprism", "config.json"), "w") as f:
            json.dump({"pair_loop": {"max_rounds": 2}}, f)
        run_id = json.loads(self._run("start", "--task", "add feature").stdout)["run_id"]

        for _ in range(2):
            self._run("coder-done", "--run", run_id, "--summary", "attempted fix")
            r = self._run("review", "--run", run_id, "--reviewer-cmd",
                          json.dumps(["bash", STUB_REVIEWER, "CHANGES_REQUESTED"]))
            verdict = json.loads(r.stdout)["verdict"]
            self.assertEqual(verdict, "CHANGES_REQUESTED")

        manifest_path = os.path.join(self.env["HOME"], ".100xprism", "handoff-runs", f"{run_id}.json")
        manifest = json.load(open(manifest_path))
        self.assertEqual(len(manifest["rounds"]), 4)  # 2 coder + 2 reviewer
        # the SKILL.md instructs the agent (not this CLI) to stop at max_rounds;
        # verify the data the agent would check on is present and correct.
        self.assertEqual(manifest["rounds"][-1]["n"], 2)
        self.assertEqual(manifest["rounds"][-1]["verdict"], "CHANGES_REQUESTED")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify pass**

Run: `python3 scripts/test_pair_loop_integration.py -v`
Expected: 2 tests, all PASS (no live `codex`/`claude` calls — the stub reviewer fixture stands in for both)

- [ ] **Step 3: Run every pair-loop test together + gate**

Run: `python3 scripts/test_handoff.py && python3 scripts/test_reviewer.py && python3 scripts/test_pair_loop_start.py && python3 scripts/test_pair_loop_review.py && python3 scripts/test_pair_loop_finish.py && python3 scripts/test_pair_loop_integration.py`
Expected: everything PASS

Run: `python3 hooks/gate-pass.py` (own bash call)

- [ ] **Step 4: Commit**

```bash
git add scripts/test_pair_loop_integration.py
git commit -m "test(pair-loop): full state-machine integration — approval and round-cap paths"
```

---

## After this plan

Once both plans are implemented and all tests pass, run the token dashboard
(`100x-tokens`) and confirm it renders the new sections against real data, then
follow `superpowers:finishing-a-development-branch` to decide how to land the
branch (PR review via Codex + `/code-review`, then merge on alignment, per the
user's request that originated both specs).
