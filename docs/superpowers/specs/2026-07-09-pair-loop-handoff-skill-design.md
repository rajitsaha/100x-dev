# Pair-Loop Handoff Skill (`/pair-loop`) — Design

**Date:** 2026-07-09
**Status:** Approved (brainstorming), pending spec review
**Depends on:** `2026-07-09-token-economics-v3-design.md` — manifest schema v1,
`scripts/run-cost.py`, and the `budget.per_run_usd` config key are defined there and
must land first.

## Problem

Cross-agent review loops work — PR #73 shipped via a manual 3-round multi-agent loop —
but they are ad-hoc: no fixed conversation format, no round cap, no cost visibility,
no record joining the tokens spent to the PR shipped. Each run is re-improvised.

## Goal

A skill that formalizes the loop: one **coder** agent and one **reviewer** agent
(Claude and Codex, roles swappable), conversing through a local `HANDOFF.md` until
approval, then opening a PR carrying the full handoff transcript — while
self-reporting exact per-round cost data via the run manifest, so the token dashboard
shows $/round, coder-vs-reviewer split, and $/merged-PR with **no heuristics**.

## Channel: hybrid (decided in brainstorming)

Local `HANDOFF.md` inner loop (fast, offline, pre-commit) → PR outer record
(durable, human-joinable). Optional single final review round on the PR itself.

## Architecture

### Roles & configuration

`~/.100xprism/config.json` (shared with the economics spec):

```json
{
  "budget": {"per_run_usd": 15},
  "pair_loop": {"coder": "claude", "reviewer": "codex", "max_rounds": 3, "pr_final_round": false}
}
```

- `coder` is the current interactive session's agent; `reviewer` is invoked
  non-interactively each round.
- **Reviewer = codex:** `codex exec` with a review prompt (diff vs. base branch +
  `HANDOFF.md` history), non-interactive, sandboxed read-only.
- **Reviewer = claude:** a `claude -p` subprocess (or Task subagent) with the same
  prompt contract.
- **Fallback:** if the configured reviewer CLI is missing, fall back to a
  same-vendor reviewer subagent, warn the user, and set `reviewer_fallback: true`
  in the manifest so cross-vendor stats exclude the run.

### HANDOFF.md — the conversation contract

Lives at the repo root during a run (gitignored; the transcript travels in the PR
body, not as a tracked file). Append-only rounds:

```markdown
# Pair-Loop Handoff — <run-id>
Task: <description> · Branch: <branch> · Coder: claude · Reviewer: codex

## Round 1 — CODER (claude) · 2026-07-09T14:32Z
<what was implemented, files touched, how it was verified>

## Round 1 — REVIEWER (codex) · 2026-07-09T14:44Z
### Findings
1. [correctness] src/foo.py:42 — <finding> 
2. [tests] <finding>
VERDICT: CHANGES_REQUESTED

## Round 2 — CODER (claude) · …
Addressed: 1 (fixed), 2 (fixed). <notes>
…
VERDICT: APPROVED
```

Hard contract, enforced by the skill's reviewer prompt:

- Reviewer output MUST end with exactly `VERDICT: APPROVED` or
  `VERDICT: CHANGES_REQUESTED` (parsed by the loop; anything else = one re-ask, then
  treated as CHANGES_REQUESTED).
- Findings are a numbered list with `[category] file:line —` prefixes so
  `findings` / `findings_addressed` counts in the manifest are countable, and so
  reviewer value (defects caught) is measurable downstream.

### State machine

```
START → [budget check] → CODER round → [budget check] → REVIEWER round
   ├─ VERDICT: CHANGES_REQUESTED & round < max_rounds → next CODER round
   ├─ VERDICT: CHANGES_REQUESTED & round = max_rounds → STOP (user decides: ship / continue / abandon)
   └─ VERDICT: APPROVED → PR phase
PR phase: gates → /pr flow → PR body = summary + full HANDOFF transcript
   └─ pr_final_round: reviewer reviews the PR diff once; comment posted via gh; any
      findings go back to one local coder round, then done.
```

- **Coder round:** implement / address findings, run the project's quick checks
  (tests + lint), summarize into `HANDOFF.md`.
- **Budget check:** before every round, `python3 scripts/run-cost.py <manifest>`;
  at ≥100% of `per_run_usd` the loop pauses and asks the user (continue / stop);
  at ≥80% it warns inline and continues.
- **Gates:** the existing commit/push gates are unchanged — the skill routes through
  them (gate-pass in its own step, per repo convention).

### Run manifest — self-instrumentation

Schema v1 is owned by the economics spec. The skill's obligations:

- Create `~/.100xprism/handoff-runs/<run-id>.json` at START; **rewrite it after
  every round boundary** (atomic write via temp file + rename), so a crashed run
  leaves an ingestable partial manifest.
- Record per round: `role`, `tool`, `started`/`ended` (UTC), `session_id`
  **best-effort** — coder: the current Claude session id (from the transcript
  filename / env when exposed); reviewer: the newest `~/.codex/sessions` file
  created during the round window. When a session id can't be captured, omit it —
  the dashboard's time-window fallback join covers it.
- Record `findings` (reviewer rounds) and `findings_addressed` (coder rounds) parsed
  from `HANDOFF.md`.
- Write `outcome.verdict` and `outcome.rounds` at loop end; leave
  `outcome.merged: null` (back-filled by the value layer from git history).

### What the economics dashboard shows (for reference — implemented in the companion spec)

Per run: rounds · coder $ · reviewer $ · total · outcome PR · $/merged-PR.
Aggregates: convergence curve (findings & $ per round), coder-vs-reviewer split,
cross-vendor comparison (claude-codes/codex-reviews vs. inverse, fallback runs
excluded), and the `loop-cap` suggestion rule.

## Packaging

A 100xprism module (workflow skill) like the existing `commit`/`pr`/`grill-me`
modules, so it ships to all adapter targets. The reviewer-invocation layer is the
only tool-specific part and is isolated in one place.

## Failure modes

| Failure | Behavior |
|---|---|
| Reviewer CLI missing | same-vendor fallback + `reviewer_fallback: true` + user warning |
| Reviewer emits no parseable VERDICT | one re-ask; then treat as CHANGES_REQUESTED |
| Budget cap hit | pause, ask user (continue / stop); never silently overspend |
| Max rounds hit without approval | stop, present open findings, user decides |
| Crash mid-run | partial manifest already on disk; `HANDOFF.md` preserves state; re-running `/pair-loop` offers resume |
| Dirty working tree at START | refuse to start (same convention as branch/commit skills) |

## Testing

- State-machine unit tests with a **stub reviewer command** (fixture script emitting
  scripted findings/verdicts) — approval path, max-rounds path, unparseable-verdict
  path, budget-pause path.
- Manifest writing: atomicity, per-round rewrite, partial-manifest shape.
- HANDOFF.md parsing: findings/verdict extraction golden tests.
- No live `codex`/network calls in tests.

## Out of scope

- More than two agents / parallel reviewer panels (the workflow tool covers that).
- CI-side (GitHub Actions) reviewer — the optional final round uses local `gh` only.
- Auto-merge. A human merges, always.
