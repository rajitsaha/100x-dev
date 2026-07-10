# Token Economics v3 — Accuracy, Attribution, Budgets, Suggestions — Design

**Date:** 2026-07-09
**Status:** Approved (brainstorming), pending spec review
**Builds on:** `2026-06-21-token-value-all-directories-design.md` (adapter architecture, value layer, discovery)
**Companion spec:** `2026-07-09-pair-loop-handoff-skill-design.md` (produces the run manifests this spec ingests)

## Problem

The token dashboard answers "where did tokens go, by directory and day" — but:

- **Cost is inaccurate.** A single flat `RATES` table (Opus list prices) prices every
  model, so Sonnet/Haiku/Fable sessions are all billed as Opus. `by_model` token counts
  exist but never reach the pricing step.
- **Attribution is shallow.** Composition is a char-count heuristic. Nothing answers
  "which session / skill / subagent spent this?" — the top acknowledged gap
  (`docs/token-optimization.md:164`).
- **Cost covers Claude Code only.** `scripts/adapters/codex.py` is a stub; the adapter
  interface exists but `token-dashboard.py` still parses transcripts inline (refactor
  half-landed).
- **Monitoring is passive.** No budgets, no alerts, no guidance. The dashboard shows
  spend but never says "here is how to reduce it."
- **Value is coarse.** Commits + 3×PRs per directory/day; no $/commit, no $/merged-PR,
  no per-unit-of-work economics.

## Goal

Trustworthy per-model cost across Claude Code **and** Codex; attribution down to
session, skill, and subagent; per-run economics for pair-loop handoff runs; budgets
with three alert surfaces; a compact, data-rich dashboard refreshing every 30 s; and a
rule-based suggestions panel that names concrete ways to cut token cost, sorted by
estimated $ impact.

## Architecture

Six layers, built bottom-up. Everything stays stdlib-only, offline, zero new
dependencies.

### 1. Data pipeline — adapters finished, per-model pricing

**Finish the adapter refactor.** `token-dashboard.py`'s inline `parse_file()` moves
into `scripts/adapters/claude_code.py`; the dashboard consumes only the merged
`ADAPTERS` stream. Net behavior for Claude-only users is unchanged.

**Per-model rates.** `RATES` becomes an ordered pattern → rates mapping (editable at
the top of the file, $/1M tokens):

```python
# values below are ILLUSTRATIVE — verified against published pricing at implementation
RATES = [
    ("fable-5",   {"input": 25.0, "output": 100.0, "cache_read": 2.5,  "cache_write": 31.25}),
    ("opus-4",    {"input": 15.0, "output": 75.0,  "cache_read": 1.5,  "cache_write": 18.75}),
    ("sonnet",    {"input": 3.0,  "output": 15.0,  "cache_read": 0.3,  "cache_write": 3.75}),
    ("haiku",     {"input": 1.0,  "output": 5.0,   "cache_read": 0.1,  "cache_write": 1.25}),
    # Codex / OpenAI tiers appended here by the codex adapter section
]
FALLBACK = "opus-4"  # unknown model ids priced as Opus and flagged
```

First substring match on the model id wins. Unknown ids use `FALLBACK` and are counted
in a `priced_as_fallback` token total surfaced in the UI ("~N% of spend priced at
fallback rates"). Rates are checked against current published pricing at
implementation time; the table is data, not logic.

**Codex adapter — implemented.** Parse `~/.codex/sessions/**/*.jsonl` token-count
events (newer Codex CLI rollout format: `event_msg` / `token_count` entries carrying
input/cached/output totals per turn; exact field names verified against the installed
CLI at implementation time). Yields the same `Usage` tuples with `tool="codex"` plus
per-model ids for pricing. Missing directory → yields nothing, exactly as today.

**Cache.** `CACHE_VERSION` bumps 3 → 4 (per-file summaries gain model-keyed usage,
session metadata, and attribution segments). Old caches are discarded and rebuilt on
first run, as with prior bumps.

### 2. Attribution layer — session, subagent, skill

All derived from data already in the transcripts; no hooks, no new writers.

- **Session (exact).** One JSONL file = one session. Aggregate cost, message count,
  duration (first→last timestamp), model mix per session. New `by_session` table
  (top 50 by cost, last 30 days) in the dataset.
- **Subagent vs. main loop (exact).** Messages carrying sidechain markers
  (`isSidechain: true` and/or separate agent transcript files — the exact marker set
  is verified against the current transcript format at implementation time and
  documented in the adapter) are summed separately. Yields an exact
  main/subagent cost split per session and overall.
- **Skill / slash command (attributed, honest estimate).** Detect `Skill` tool-use
  blocks and `<command-name>` markers in the message stream. All usage from a marker
  until the next marker (or session end) is attributed to that skill. Labelled
  **"attributed"** in the UI with the same disclaimer convention as the existing
  composition bars — segmentation truth, not billed truth. Produces `by_skill`
  (skill → cost, invocations, cost/invocation, last 30 days).

### 3. Run-manifest ingestion — per-run economics

The pair-loop skill (companion spec) writes one JSON manifest per run to
`~/.100xprism/handoff-runs/<run-id>.json`. This spec owns the **schema (v1)** and the
reader:

```json
{
  "v": 1,
  "run_id": "2026-07-09-1432-a1b2",
  "task": "short human description",
  "cwd": "/Users/rajit/personal-github/100xprism",
  "branch": "feat/foo", "pr": 78,
  "coder": "claude", "reviewer": "codex", "reviewer_fallback": false,
  "rounds": [
    {"n": 1, "role": "coder",    "tool": "claude", "session_id": "…",
     "started": "2026-07-09T14:32:01Z", "ended": "2026-07-09T14:41:55Z",
     "findings_addressed": 0},
    {"n": 1, "role": "reviewer", "tool": "codex",  "session_id": "…",
     "started": "…", "ended": "…", "findings": 4, "verdict": "CHANGES_REQUESTED"}
  ],
  "outcome": {"verdict": "APPROVED", "rounds": 3, "merged": null}
}
```

- **Join rule:** prefer `session_id` match against the adapter's session index; fall
  back to `[started, ended]` time-window overlap within the run's `cwd`. Both
  adapters expose the needed session index.
- Partial manifests (crashed runs, missing `outcome`) are ingested and shown as
  "incomplete" — the skill writes incrementally precisely so this works.
- `outcome.merged` is back-filled by the value layer (branch/PR joined to git
  history), not by the skill.
- Result: `by_run` — per run: rounds, coder $, reviewer $, total $, outcome,
  $/merged-PR.

### 4. Value layer — $/unit-of-work

`scripts/_value.py` additions (still git-native, offline, no `gh`):

- **Merged-PR detection:** merge commits + `(#N)`-suffixed squash subjects on the
  default branch, deduped by PR number.
- **Releases:** tags created within the window.
- **Derived ratios** computed at build time and shipped in the dataset:
  `$/commit`, `$/merged-PR` per directory (window = spend range, as today) and per
  handoff run.
- Store version bumps 2 → 3; snapshots re-mined lazily as windows change (existing
  HEAD+window cache keying already handles this).

### 5. Budgets & alerts

**Config:** `~/.100xprism/config.json` (created on demand, absent = feature off):

```json
{"budget": {"daily_usd": 50, "weekly_usd": 250, "per_run_usd": 15}}
```

Thresholds: **warn at 80%**, **alert at 100%** of each configured limit.

Three surfaces:

1. **Dashboard** — budget bar in the KPI strip (today vs. daily, 7d vs. weekly),
   amber ≥80%, red ≥100%.
2. **Shell** — the existing cache-only `--oneline` output gains the budget fraction:
   `100x · today $41.23/$50 ⚠ · 7d $210.10/$250`. Glyph: nothing <80%, `⚠` ≥80%,
   `‼` ≥100%. Stays cache-only (no rescan on shell startup), so the number can lag
   one refresh cycle — acceptable.
3. **macOS notification** — the daemon, after each rebuild, fires
   `osascript -e 'display notification …'` when a threshold is newly crossed.
   Dedupe state in `~/.100xprism/alert-state.json`
   (`{"daily_warn": "2026-07-09", …}`): max one notification per threshold per day.
   Non-macOS or osascript failure → silently skipped.

`per_run_usd` is enforced by the pair-loop skill (companion spec) via the
`run-cost` helper below, not by the daemon.

**Helper CLI:** `scripts/run-cost.py <manifest-path>` — performs the §3 join on
demand and prints the run's cost so far (used by the skill's pre-round budget check;
also handy standalone).

### 6. Dashboard redesign — compact, data-rich, 30 s

Same single-file stdlib `ThreadingHTTPServer`, same inline-SVG/no-framework rule.

- **Refresh:** server incremental rescan every 30 s (`REFRESH_SECONDS` 300 → 30 —
  cheap because the mtime/size cache makes a no-change pass near-free); client polls
  `/api/data` every 30 s. Discovery walk TTL stays 1800 s. `/api/refresh` unchanged.
  `/api/data` remains the single data endpoint (docs updated to drop stale
  `/api/value` references).
- **Layout (dense grid, top to bottom):**
  1. **KPI strip** — today / 7d / 30d spend, budget bars, $/commit, $/merged-PR,
     fallback-pricing % badge.
  2. **Donut** — spend by purpose (the four token purposes) — replaces the four cards.
  3. **Stacked area** — daily cost, stacked **by model**, with a by-model ⇄
     by-project toggle.
  4. **Handoff runs table** — run · rounds · coder $ · reviewer $ · total ·
     outcome/PR · $/PR (hidden when no manifests exist).
  5. **Attribution tables** — by-skill, by-session (top 50), main-vs-subagent split.
  6. **Suggestions card** — see §7.
  7. Existing leverage scatter, all-directories table, and composition bars are kept
     but compacted (smaller type, tighter rows); startup-bloat meter folds into the
     suggestions card.

### 7. Suggestions engine

`scripts/_suggest.py` — pure functions over the built dataset. Each rule:
`rule(data) -> Suggestion(impact_usd_estimate, message) | None`. Output sorted by
impact, top 5 shown, each message containing the user's actual numbers. Initial rule
set:

| Rule | Fires when | Message shape |
|---|---|---|
| startup-bloat | median first-fixed tokens > 15K | "Each session starts with ~NK tokens (~$X/mo) — trim CLAUDE.md / skill descriptions" |
| model-tiering | expensive-tier model ≥60% of cost on sessions with <M messages | "N light sessions ran on <model> — re-tier to Haiku/Sonnet, est. $X/mo" |
| cache-hygiene | cache-read share of input < 70% | "Cache reads are only N% — long-lived sessions / stable prompts raise this" |
| read-delegation | files_read composition share > 30% | "N% of tokens are raw file reads — delegate searches to Explore subagents" |
| skill-outlier | one skill > 3× median cost/invocation | "<skill> costs $X/invocation vs $Y median — inspect its prompt size" |
| loop-cap | handoff runs where final round found 0 findings | "Runs converge by round N — lower pair-loop round cap" |

Rules are independent and individually unit-tested; adding a rule = adding a function
to a list.

## Testing

- **Adapters:** fixture JSONL for Claude (multi-model, sidechain, skill markers) and
  Codex (token-count events); golden-number cost tests per model tier; fallback-flag
  test for unknown ids.
- **Attribution:** segmentation tests — marker → next-marker boundaries, session
  aggregation, subagent split.
- **Manifest join:** session-id join, time-window fallback, partial-manifest
  ingestion.
- **Budgets:** threshold math, oneline formatting, alert-state dedupe (no osascript
  in tests — the notify call is injected/mocked).
- **Suggestions:** one test per rule (fires / doesn't fire / message contains the
  numbers).
- **Value:** merged-PR and tag detection on a fixture repo; ratio math.
- Existing `test_value.py` suite must stay green; `npm run check` gates as always.

## Out of scope

- OTEL ingestion (external alternative, documented in `docs/token-optimization.md`).
- Cursor / Antigravity / Gemini cost adapters — still no local token data.
- GitHub API (`gh`) enrichment of value — value stays offline/git-native.
- The pair-loop skill itself — companion spec.

## Sequencing

This project lands first: the manifest schema (§3), `run-cost.py` helper (§5), and
`per_run_usd` config key are the contract the pair-loop skill consumes.
