---
name: fix-bugs
description: Autonomously fix bugs from any source — Slack threads, failing CI tests, docker logs, or a plain description. Use when you have a bug report or failing test and want Claude to investigate and fix without step-by-step guidance.
category: engineering
tier: core
slash_command: /fix
allowed-tools: Bash Read Grep Glob Edit Write
---

# Fix — Autonomous Bug Fixer

Fix the bug described or linked. Investigate and fix without step-by-step guidance.

## Do NOT ask for permission — investigate and fix autonomously.

## How to use
- `/fix` — fix the most recent failing CI run
- `/fix <description>` — fix from plain description
- `/fix <docker logs paste>` — trace error to root cause and fix
- `/fix <Slack URL or paste>` — read thread, extract bug report, fix

---

## Phase 1 — Gather context

Read the error in full — message, stack trace, or thread. Do not skip this step.

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"
# If fixing CI: read most recent failure
gh run list --limit 3
gh run view --log-failed $(gh run list --limit 1 --json databaseId -q '.[0].databaseId') 2>/dev/null | tail -80
```

For docker logs: parse for ERROR/CRITICAL lines, identify service + file.
For Slack thread: extract the bug report and reproduction steps.

---

## Phase 2 — Locate the code

Find the exact file(s) and line(s) responsible. Use Grep/Glob aggressively — do not guess.

```bash
cd "$PROJECT_ROOT"
git log --oneline -10
git status
```

Read the surrounding code. Understand the intent before touching anything.

---

## Phase 3 — Fix

Make the **minimal correct change**. Do not refactor unrelated code. Do not add workarounds or feature flags — fix the root cause.

If the root cause cannot be determined: say so clearly. Do not guess.

---

## Phase 4 — Verify

Run the specific failing test or reproduce the failure condition:

```bash
# Run the test(s) that were failing
npm test 2>&1 | tail -30
# or
./venv/bin/pytest tests/ -v --tb=short -q 2>&1 | tail -30
```

**GATE: The specific failure condition no longer occurs.**

---

## Note on unknown root causes

If the root cause is not clear from the error, stack trace, or logs alone — **invoke `systematic-debugging` skill first** to diagnose before attempting a fix. `/fix` assumes you know (or can quickly find) what's broken. For mysterious failures, diagnosis comes first.

## Phase 5 — Summarize

One sentence: what was wrong and what you changed. Then run `/commit`.
