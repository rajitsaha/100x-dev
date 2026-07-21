# AI Economics Measurement System

**Date:** 2026-07-20

## Decision

The dashboard presents three separate measurement layers. It never promotes an
engineering activity metric into a business-value claim.

| Layer | Question | Evidence | Allowed language |
|---|---|---|---|
| Token economics | What did AI usage cost? | Provider token counters × dated list prices | spend, estimated cost, token volume |
| Delivery economics | What observable work accompanied attributed spend? | Git commits, merged PRs, releases, files, churn | observable delivery, delivery unit cost |
| Business value | What outcome did the delivered work create? | Revenue, adoption, incidents avoided, time saved, or another connected outcome source | value, ROI, return |

Business value defaults to **Not measured**. PRs, commits, files, additions, and
deletions are never labeled ROI or a value score.

## Attribution contract

- Total spend is always visible.
- Attributed spend is the subset joined to a Git-backed directory.
- Attribution coverage is `attributed spend / total spend` and appears beside
  delivery unit costs.
- Delivery unit cost uses attributed spend only. Labels must say this directly.
- Selected-window spend must not imply selected-window outcomes while outcome
  snapshots remain directory-source-scoped.
- A missing local token source renders `—`, never `$0`.

## Interface hierarchy

The default Economics view opens with one measurement chain:

1. **Token economics** — selected-window list-price spend.
2. **Observable delivery** — PR/commit evidence, attributed spend, and coverage.
3. **Business value** — explicit measurement status.

Amber means cost. Green means observable delivery. Neutral means unknown or not
measured. Green does not mean business value.

Recommendations remain a separate view because optimization advice answers a
different question from economic measurement.

## PR details

When GitHub integration is enabled, the GitHub view includes PR-level rows with:

- repository and PR number linked to GitHub;
- open, closed, or merged status;
- author and title;
- comment count;
- sampled docs/deleted-file detail and churn;
- last-updated date.

File and churn fields say when they were not sampled. Repository and developer
rollups remain evidence views, not employee performance scoring.

## Future value connectors

A future connector may populate business value only when it supplies an explicit
outcome definition, source, time window, and attribution method. Candidate
outcomes include revenue influenced, adoption, cycle-time change, support volume,
incident reduction, and verified hours saved. Until then, the UI stays at
**Not measured**.
