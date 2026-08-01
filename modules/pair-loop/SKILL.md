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
Run the project's quick checks (tests + lint) before recording the round. **Do not commit — leave all changes in the working tree so review diffs stay accurate across rounds; commit only in Step 5 (PR phase).** Then:

```bash
python3 ~/100xprism/scripts/pair-loop.py coder-done --run "$RUN_ID" \
  --summary "<what you implemented/fixed, files touched, how you verified it>" \
  --findings-addressed <N>
```

## Step 4 — Reviewer round

```bash
python3 ~/100xprism/scripts/pair-loop.py review --run "$RUN_ID"
```

This shells out to the configured reviewer and returns
`{"verdict":, "findings": [...], "fallback_used":, "reviewer_model":}`.

If the reviewer's CLI is missing, it falls back to the coder's vendor pinned to
`pair_loop.fallback_models` (default `sonnet` for Claude, `gpt-5.6-luna` for
Codex) to reduce the chance of a same-model self-review. Nothing compares that
model to the coder's, so independence is configured, not verified — pick a
fallback model you don't code with. The
output says `"fallback_used": true` with the model in `"reviewer_model"` —
mention it to the user once, don't repeat it every round. If neither CLI is on
PATH the command fails with both binaries named; that is a stop condition.

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

This second call also posts a review summary to the PR — rounds, reviewer tool
(plus its model when one was pinned; the normal path uses each CLI's own
default, which isn't recorded), findings raised/resolved, verdict, and an
explicit warning when the fallback was used. Pass `--no-comment` to skip it. A failed post warns and
returns `"summary_posted": false`; it never fails the run.

If `pair_loop.pr_final_round` is `true` in the config, run one more `review`
round against the pushed PR diff before this step, and post any findings as a
PR comment via `gh pr comment` — then do exactly one more local coder round to
address them before finishing.

## When to stop and ask the user

- Budget cap hit (Step 2, exit code 2).
- Round cap hit without approval (Step 4).
- Never auto-merge — a human merges the PR, always.

**Note:** If the reviewer CLI fell back to the coder's vendor, mention it to the user once (the output will say `"fallback_used": true` and name the model in `"reviewer_model"`), but do not block — this is not a stop condition. A same-vendor review on a different model is weaker than a cross-vendor one; the PR summary says so explicitly.
