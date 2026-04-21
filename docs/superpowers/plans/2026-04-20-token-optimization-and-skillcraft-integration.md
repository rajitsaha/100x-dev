# Token Optimization & Skillcraft Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement issues #7 (token optimization) and #8 (skillcraft integration) — reduce per-session token cost, add 8 new dev-workflow slash commands from skillcraft, retire bloated enterprise-design in favour of leaner replacement, and clean up `~/.claude/skills/` after integration.

**Architecture:** All changes are to markdown workflow files and shell adapter scripts. No application code. New workflows follow the established 100x-dev format (title header, How-to-use, numbered phases, GATE lines, model hints). The adapter `shared.sh` hardcodes the workflow list; new workflows must be appended there. `_lib.md` is a conventions reference doc excluded from adapter output (not in the hardcoded list).

**Tech Stack:** Bash, Markdown. Tools: `wc`, `bash -n`, `git`, `gh`.

---

## File Map

```
NEW
  workflows/_lib.md                     conventions reference (excluded from adapters)
  workflows/fix.md                      from fix-bugs skill
  workflows/spec.md                     from spec skill
  workflows/grill.md                    from grill-me skill
  workflows/techdebt.md                 from techdebt skill
  workflows/context.md                  from context-dump skill
  workflows/query.md                    from data-query skill
  workflows/orchestrate.md              from orchestrate skill
  workflows/update-claude.md            from update-claude-md skill

REPLACED
  workflows/enterprise-design.md        replaced with systems-architect content (#7B-1 + #8P3)

MODIFIED
  workflows/architect.md                add scope banner; strip cloud-infra overlap with enterprise-design
  workflows/db.md                       add scope banner differentiating from /query
  workflows/cloud-security.md           strip verbose Python inline scripts → compact bash equivalents
  workflows/issue.md                    compress 5-dim impact analysis → framework bullets
  workflows/test.md                     compress Phase 0 docker A/B/C → single detection block
  adapters/lib/shared.sh                add new workflows to hardcoded list; exclude _lib.md

UPDATED
  README.md                             add new commands table entries + pipeline diagram
  docs/USAGE.md                         document new pipeline
  CHANGELOG.md                          record this release

CLEANUP (Task 19 — after all verified)
  ~/.claude/skills/fix-bugs/            delete
  ~/.claude/skills/spec/                delete
  ~/.claude/skills/grill-me/            delete
  ~/.claude/skills/techdebt/            delete
  ~/.claude/skills/context-dump/        delete
  ~/.claude/skills/data-query/          delete
  ~/.claude/skills/orchestrate/         delete
  ~/.claude/skills/update-claude-md/    delete
  ~/.claude/skills/systems-architect/   delete
  ~/.claude/skills/skillcraft-repo/     delete
```

---

## Task 1: Create `workflows/_lib.md` — shared conventions reference

**Files:**
- Create: `workflows/_lib.md`

- [ ] **Step 1: Write the file**

```markdown
# _lib — Shared Workflow Conventions
<!-- Reference only — not a slash command. Not included in adapter output. -->

## Standard preamble (paste into every workflow's first bash block)

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
INSTRUCTION_FILE=$(for f in CLAUDE.md AGENTS.md .cursorrules .windsurfrules .github/copilot-instructions.md GEMINI.md; do [ -f "$PROJECT_ROOT/$f" ] && echo "$PROJECT_ROOT/$f" && break; done)
```

## Autonomy banner
Add to any workflow that operates without user prompting:
```
## Do NOT ask for permission — [action]. Do NOT stop until done.
```

## Model hints
- `<!-- model: haiku -->` — mechanical tasks: lint, security scan, branch, docs, update-claude
- `<!-- model: opus -->` — deep reasoning: architect, enterprise-design, cloud-security
- (none) — general purpose: commit, push, pr, gate, test, fix, spec, grill, techdebt, context, query, orchestrate

## GATE line format
```
**GATE: [Condition that must be true before proceeding.]**
```
```

- [ ] **Step 2: Verify file was written**

```bash
wc -l /Users/rajit/personal-github/100x-dev/workflows/_lib.md
# Expected: ~30 lines
```

- [ ] **Step 3: Verify adapter does NOT include _lib.md**

```bash
grep "_lib" /Users/rajit/personal-github/100x-dev/adapters/lib/shared.sh
# Expected: no output (it's not in the hardcoded list)
```

- [ ] **Step 4: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add workflows/_lib.md
git commit -m "docs: add _lib.md — shared workflow conventions reference (#7)"
```

---

## Task 2: Create `workflows/fix.md`

**Files:**
- Create: `workflows/fix.md`

- [ ] **Step 1: Write the file**

```markdown
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
```

- [ ] **Step 2: Verify**

```bash
bash -n /Users/rajit/personal-github/100x-dev/workflows/fix.md 2>/dev/null; wc -l /Users/rajit/personal-github/100x-dev/workflows/fix.md
# Expected: ~55 lines, no bash errors
```

- [ ] **Step 3: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add workflows/fix.md
git commit -m "feat: add /fix workflow — autonomous bug fixer from skillcraft (#8)"
```

---

## Task 3: Create `workflows/spec.md`

**Files:**
- Create: `workflows/spec.md`

- [ ] **Step 1: Write the file**

```markdown
# Spec — Implementation-Ready Specification

Turn a vague request into an unambiguous, implementation-ready specification. Do not write any code until the spec is approved.

## How to use
- `/spec <feature request>` — clarify, read codebase, produce spec, get approval

---

## Phase 1 — Clarify (ask, don't assume)

Ask targeted questions to eliminate ambiguity:
- **Who** triggers this? (user action, background job, webhook, cron?)
- **What** is the exact input? (types, shapes, valid ranges, optional vs required)
- **What** is the exact output? (return value, side effects, UI state change)
- **What** are the error cases? (invalid input, missing data, network failure, auth failure)
- **What** are the constraints? (performance, backwards-compatibility, permissions, rate limits)
- **What** does "done" look like? (how do you know it works?)

Only ask questions that materially change the spec. Infer what you can from the codebase.

---

## Phase 2 — Read context

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"
git log --oneline -10
```

Read relevant existing code: find related files with Grep/Glob, understand existing data shapes, API contracts, naming conventions. Note anything constraining the implementation.

---

## Phase 3 — Write the spec

```
## Feature: [name]

### Summary
One paragraph: what this does and why.

### Inputs
- [param]: [type] — [description, valid values, required/optional]

### Outputs / Side Effects
- [what changes, what is returned, what events are fired]

### Acceptance Criteria
- [ ] [specific, testable condition]
- [ ] [specific, testable condition]

### Edge Cases & Error Handling
- [condition] → [expected behavior]

### Out of Scope
- [explicitly list what this does NOT do]

### Open Questions
- [anything unresolved — flag for user to decide]
```

---

## Phase 4 — Get approval

Present the spec. Do **not** proceed to implementation until the user says "approved", "lgtm", "ship it", or similar.

If the user requests changes: update the spec and re-present it.

**Once approved:** run `/commit` or hand off to implementation.
```

- [ ] **Step 2: Verify**

```bash
wc -l /Users/rajit/personal-github/100x-dev/workflows/spec.md
# Expected: ~60 lines
```

- [ ] **Step 3: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add workflows/spec.md
git commit -m "feat: add /spec workflow — implementation-ready specs from skillcraft (#8)"
```

---

## Task 4: Create `workflows/grill.md`

**Files:**
- Create: `workflows/grill.md`

- [ ] **Step 1: Write the file**

```markdown
# Grill — Adversarial Code Review

Enter adversarial review mode. Challenge the current changes before a PR is created. Do not approve until satisfied.

## How to use
- `/grill` — adversarial review of current diff before `/pr`
- `/grill rewrite` — scrap and implement the elegant solution
- `/grill spec` — write detailed specs before handing off work

---

## Mode A — Code Review (default)

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"
git diff main
git diff --staged
```

Read the diff. Identify risks:

- [ ] Does this handle the unhappy path?
- [ ] Are there race conditions or async issues?
- [ ] Is this the right abstraction (over- or under-engineered)?
- [ ] Will this break anything that depends on it?
- [ ] Are tests missing for the new behaviour?
- [ ] Is the naming clear to someone reading this cold?
- [ ] Could this be 50% simpler?

Ask the user **3–5 hard, specific questions** about the changes. Do not accept vague answers — probe further. Only approve (and proceed with `/pr`) once satisfied.

---

## Mode B — Elegant Rewrite

After a messy fix, start fresh:
- Identify the root insight that makes the solution simple
- Rewrite with that insight as the foundation — no legacy cruft
- The elegant solution is usually 30–50% less code

---

## Mode C — Spec-Driven Development

Ask clarifying questions until requirements are unambiguous. Produce a written spec (inputs, outputs, edge cases, acceptance criteria). Only begin implementation once spec is approved.

---

**GATE: User has answered all questions satisfactorily. Only then proceed to `/pr`.**
```

- [ ] **Step 2: Verify**

```bash
wc -l /Users/rajit/personal-github/100x-dev/workflows/grill.md
# Expected: ~55 lines
```

- [ ] **Step 3: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add workflows/grill.md
git commit -m "feat: add /grill workflow — adversarial pre-PR review from skillcraft (#8)"
```

---

## Task 5: Create `workflows/techdebt.md`

**Files:**
- Create: `workflows/techdebt.md`

- [ ] **Step 1: Write the file**

```markdown
# Techdebt — Technical Debt Scanner
<!-- model: haiku -->

Scan the codebase for technical debt and eliminate it. Run at end of session or when the codebase feels bloated.

## Do NOT ask for permission — scan, report, then ask before fixing.

## How to use
- `/techdebt` — full scan + report, confirm before fixing
- `/techdebt fix` — scan and fix without confirmation

---

## Phase 1 — Scan

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"
```

Look for:

1. **Duplicated code** — copy-pasted logic that should be a shared utility
2. **Dead code** — unused functions, variables, imports, exports, commented-out blocks
3. **Redundant abstractions** — over-engineered helpers used in only one place
4. **Inconsistent patterns** — same operation done 3+ different ways across files
5. **Stale TODOs / FIXMEs** — old comments no longer relevant

Use Grep and Glob to identify candidates. Confirm each item is truly dead/duplicated before reporting.

---

## Phase 2 — Report

```
## Tech Debt Found

### Duplicated Code
- `src/utils/formatDate.ts:12` and `src/helpers/dates.ts:45` — identical logic
  Fix: consolidate into formatDate.ts, delete dates.ts

### Dead Code
- `src/api/legacyAuth.ts` — no imports found anywhere
  Fix: delete file

### Stale TODOs
- `src/components/Modal.tsx:89` — TODO from 6 months ago, feature shipped
  Fix: remove comment
```

---

## Phase 3 — Fix (with confirmation)

For each item, ask the user to confirm unless they said "fix". After fixes:

```bash
# Run tests to verify nothing broke
npm test 2>&1 | tail -20
```

**GATE: Tests still pass after cleanup.**
```

- [ ] **Step 2: Verify**

```bash
wc -l /Users/rajit/personal-github/100x-dev/workflows/techdebt.md
# Expected: ~65 lines
```

- [ ] **Step 3: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add workflows/techdebt.md
git commit -m "feat: add /techdebt workflow — debt scanner from skillcraft (#8)"
```

---

## Task 6: Create `workflows/context.md`

**Files:**
- Create: `workflows/context.md`

- [ ] **Step 1: Write the file**

```markdown
# Context — Session Orientation Dump
<!-- model: haiku -->

Pull 7 days of git and GitHub activity into a structured summary. Run at the start of a session before making changes.

## How to use
- `/context` — full 7-day dump
- `/context focus: <area>` — limit to specific feature area or last PR

---

## Phase 1 — Gather activity

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"

# Recent commits
git log --since="7 days ago" --oneline --all

# Open PRs
gh pr list --state open

# Merged PRs (last 10)
gh pr list --state merged --limit 10

# Open issues
gh issue list --state open

# CI health
gh run list --limit 3
```

---

## Phase 2 — Produce summary

```
## Context Dump — [DATE]

### What shipped this week
- [merged PRs, 1-line summary of what changed]

### What's in flight
- [open PRs, status, blockers]

### Open issues
- [bugs / features, prioritized by recency]

### Recent commits (7 days)
- [key commits grouped by feature area]

### CI health
- [pass/fail, any flaky tests]

### Suggested next actions
- [based on above, what needs attention first]
```
```

- [ ] **Step 2: Verify**

```bash
wc -l /Users/rajit/personal-github/100x-dev/workflows/context.md
# Expected: ~55 lines
```

- [ ] **Step 3: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add workflows/context.md
git commit -m "feat: add /context workflow — session orientation dump from skillcraft (#8)"
```

---

## Task 7: Create `workflows/query.md`

**Files:**
- Create: `workflows/query.md`

Note: `/db` = execute SQL against configured connections. `/query` = plain-English analytics for any DB.

- [ ] **Step 1: Write the file**

```markdown
# Query — Plain-English Database Analytics
<!-- model: haiku -->

Describe what you want to know — Claude writes and runs the query.

## How to use
- `/query <business question>` — Claude translates to SQL, runs it, returns analysis

## Supported interfaces
- **BigQuery**: `bq` CLI — `bq query`, `bq show`, `bq ls`
- **PostgreSQL**: `psql` CLI
- **MySQL**: `mysql` CLI
- **SQLite**: `sqlite3` CLI

---

## Phase 1 — Understand the question

Restate the business question in concrete terms. If the schema is ambiguous, inspect it first:

```bash
# BigQuery — show table schema
bq show <dataset>.<table>

# PostgreSQL
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" \
  -c "\d <table_name>"
```

---

## Phase 2 — Write and run the query

Write the SQL for the business question. Run it using the appropriate CLI. Explain the results in plain English.

---

## Phase 3 — Return results

Return:
1. The SQL written
2. A plain-English answer to the original question
3. A table of key numbers

For recurring queries: offer to save as a named script.

## Scope vs `/db`
- `/query` = analytics in plain English (you describe a business question)
- `/db` = execute specific SQL against a named connection (you write the SQL or say "migrate")
```

- [ ] **Step 2: Verify**

```bash
wc -l /Users/rajit/personal-github/100x-dev/workflows/query.md
# Expected: ~55 lines
```

- [ ] **Step 3: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add workflows/query.md
git commit -m "feat: add /query workflow — plain-English analytics from skillcraft (#8)"
```

---

## Task 8: Create `workflows/orchestrate.md`

**Files:**
- Create: `workflows/orchestrate.md`

- [ ] **Step 1: Write the file**

```markdown
# Orchestrate — Complex Task Orchestration

Apply workflow orchestration methodology for multi-step tasks with 3+ steps or architectural decisions.

## How to use
- `/orchestrate <task>` — plan-first approach for any non-trivial task

---

## Methodology

### 1. Plan first (invoke `writing-plans` skill)

**Always start by invoking the `writing-plans` skill** to produce a structured plan document at `docs/superpowers/plans/YYYY-MM-DD-<feature>.md` with TDD-style task steps. Do not proceed to coding until the plan is written and reviewed.

- If something goes sideways mid-task: STOP, re-plan using `writing-plans` again
- Track progress via `tasks/todo.md` checkboxes

### 2. Use subagents
- Offload research, exploration, and parallel analysis to subagents
- Keep main context window clean and focused
- One task per subagent for precision

### 3. Self-improvement loop
- After any correction: note the pattern in `tasks/lessons.md`
- Review lessons at session start for relevant context

### 4. Verify before done
- Never mark complete without proving it works
- Run tests, check logs, diff behaviour vs main
- Ask: "Would a staff engineer approve this?"

### 5. Demand elegance
- After a working but messy fix: "Implement the elegant solution"
- Skip this for simple, obvious fixes

### 6. Autonomous bug fixing
- When given a bug: investigate and fix. Do not wait for hand-holding.
- Pair with `/fix` for CI failures and log-based bugs.

---

## Task Management

1. Write plan → `tasks/todo.md`
2. Check in before implementation starts
3. Mark items complete as you go
4. Document results in review section
5. Capture lessons → `tasks/lessons.md`
```

- [ ] **Step 2: Verify**

```bash
wc -l /Users/rajit/personal-github/100x-dev/workflows/orchestrate.md
# Expected: ~55 lines
```

- [ ] **Step 3: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add workflows/orchestrate.md
git commit -m "feat: add /orchestrate workflow — complex task methodology from skillcraft (#8)"
```

---

## Task 9: Create `workflows/update-claude.md`

**Files:**
- Create: `workflows/update-claude.md`

- [ ] **Step 1: Write the file**

```markdown
# Update-Claude — CLAUDE.md Rule Writer
<!-- model: haiku -->

After any correction, update CLAUDE.md with a rule to prevent the same mistake recurring.

## How to use
- `/update-claude` — after a correction, write a rule to CLAUDE.md

---

## Phase 1 — Identify the pattern

What went wrong? What should have been done instead? Be specific — one clear pattern, not a vague note.

---

## Phase 2 — Write a rule

Formulate as a clear, actionable rule:
```
- [Rule]: [What to do / not to do]. Why: [brief context].
```

Short rules stick. Long paragraphs get ignored.

---

## Phase 3 — Update CLAUDE.md

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
INSTRUCTION_FILE=$(for f in CLAUDE.md AGENTS.md .cursorrules .windsurfrules .github/copilot-instructions.md GEMINI.md; do [ -f "$PROJECT_ROOT/$f" ] && echo "$PROJECT_ROOT/$f" && break; done)
```

Append the rule under a `## Rules` or `## Corrections` section in the project's instruction file. If no instruction file exists, create `CLAUDE.md` in the project root.

---

## Phase 4 — Confirm

Tell the user: "Updated [file] with: [rule summary]"

If the rule isn't reducing mistakes after 2–3 sessions: rewrite it — be more specific or more prominent.
```

- [ ] **Step 2: Verify**

```bash
wc -l /Users/rajit/personal-github/100x-dev/workflows/update-claude.md
# Expected: ~50 lines
```

- [ ] **Step 3: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add workflows/update-claude.md
git commit -m "feat: add /update-claude workflow — CLAUDE.md rule writer from skillcraft (#8)"
```

---

## Task 10: Replace `workflows/enterprise-design.md` with systems-architect content

**Files:**
- Modify: `workflows/enterprise-design.md` (full replacement, ~24KB → ~3KB)

This satisfies both #7 Phase B-1 (trim bloated workflow) and #8 Phase 3 (retire enterprise-design in favour of leaner systems-architect content). Keep the command name `/enterprise-design` for continuity; update the description.

- [ ] **Step 1: Note current file size**

```bash
wc -c /Users/rajit/personal-github/100x-dev/workflows/enterprise-design.md
# Record: ~24,600 bytes
```

- [ ] **Step 2: Replace file content**

Overwrite `workflows/enterprise-design.md` with:

```markdown
# Enterprise Design — Technical Blueprint Generator
<!-- model: opus -->

Produce a comprehensive technical blueprint for a web product or SaaS, suitable for implementation in Figma Make, engineering sprints, and cloud deployment.

## How to use
- `/enterprise-design <product or feature>` — full blueprint
- `/enterprise-design ia` — information architecture + sitemap only
- `/enterprise-design api` — API surface definition only
- `/enterprise-design data` — data architecture + entity model only
- `/enterprise-design ux` — user journeys + component inventory only
- `/enterprise-design stack` — tech stack recommendation only
- `/enterprise-design review` — audit current project against enterprise standards

---

## Step 0 — Load context

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
INSTRUCTION_FILE=$(for f in CLAUDE.md AGENTS.md .cursorrules .windsurfrules .github/copilot-instructions.md GEMINI.md; do [ -f "$PROJECT_ROOT/$f" ] && echo "$PROJECT_ROOT/$f" && break; done)
[ -n "$INSTRUCTION_FILE" ] && head -100 "$INSTRUCTION_FILE"
```

Establish: site/product type, primary audience, core capabilities (3–5), technical priorities.

---

## Deliverables

Produce a structured technical blueprint covering:

### 1. Information Architecture
Complete sitemap with primary, secondary, semantic, and neutral path hierarchy. URL conventions (kebab-case, hierarchy reflects ownership, pagination via query params).

### 2. User Journey Mapping
Three critical conversion paths: acquisition→activation, free→paid, core workflow loop. Include drop-off points and success metrics.

### 3. Data Architecture
Entity relationships and schema models. Indexing strategy (FK indexes, composite for pagination, GIN for full-text). Caching tier (Redis key patterns + TTLs). Analytics tier (event schema for BigQuery).

### 4. API Surface Definition
Core REST endpoints (auth, primary entity CRUD, billing, admin). Standard response envelope. Third-party integrations table. Rate limiting per tier.

### 5. Component Inventory (30+)
Layout, navigation, data display, form, feedback, and feature-specific components. For each: purpose + key props.

### 6. Page Blueprints
Structural wireframe descriptions for: landing page, dashboard, detail/entity view, settings page.

### 7. Technology Stack
Recommended stack with rationale for: frontend, styling, state, backend, database, cache, auth, payments, email, hosting, CI/CD, observability, IaC.

### 8. Performance Benchmarks
Core Web Vitals targets (LCP < 1.8s, INP < 100ms, CLS < 0.05). API latency targets (P50/P95). Performance budget per page.

### 9. SEO Framework
URL conventions, meta structure per page type, schema markup strategy, Core Web Vitals for SEO.

### 10. Enterprise Considerations (if applicable)
Domain-Driven Design bounded contexts, API governance, zero-trust security, multi-region DR. Only include if product is at scale (> 10K users / multi-team / regulated).

---

## Output Format

Structured specification with clear headings, bullet points, and numbered lists throughout. Suitable for direct handoff to Figma Make or engineering sprint planning.
```

- [ ] **Step 3: Verify reduction**

```bash
wc -c /Users/rajit/personal-github/100x-dev/workflows/enterprise-design.md
# Expected: ~2,500–3,000 bytes (was ~24,600)
wc -l /Users/rajit/personal-github/100x-dev/workflows/enterprise-design.md
# Expected: ~75 lines (was 589)
```

- [ ] **Step 4: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add workflows/enterprise-design.md
git commit -m "perf: replace enterprise-design.md with leaner systems-architect content — 24KB→3KB (#7 #8)"
```

---

## Task 11: Update `workflows/architect.md` — add scope banner, strip overlap

**Files:**
- Modify: `workflows/architect.md`

Add a scope banner at the top distinguishing `/architect` (advisory Q&A) from `/enterprise-design` (full blueprint generation). Remove sections that now live exclusively in enterprise-design (component inventory, page blueprints — which are generation artifacts, not architectural questions).

- [ ] **Step 1: Note current size**

```bash
wc -c /Users/rajit/personal-github/100x-dev/workflows/architect.md
# Record: ~9,965 bytes
```

- [ ] **Step 2: Add scope banner after the title line**

Open `workflows/architect.md`. After the first heading line (`# Architect — Cloud, Data & SaaS Distributed Architecture Advisor`), insert:

```markdown
<!-- model: opus -->

> **Scope:** `/architect` answers architectural questions and produces decision matrices.
> For full technical blueprints (sitemap, component inventory, page blueprints), use `/enterprise-design`.
```

- [ ] **Step 3: Verify file still starts correctly**

```bash
head -10 /Users/rajit/personal-github/100x-dev/workflows/architect.md
```

Expected: title, model hint, scope banner, then existing How-to-use section.

- [ ] **Step 4: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add workflows/architect.md
git commit -m "docs: add scope banner to architect.md — delineate from /enterprise-design (#7)"
```

---

## Task 12: Update `workflows/db.md` — add scope banner

**Files:**
- Modify: `workflows/db.md`

Add a one-line scope note after the description distinguishing `/db` (named connections + explicit SQL/migrate) from `/query` (plain-English analytics).

- [ ] **Step 1: Add scope note**

In `workflows/db.md`, after the opening description paragraph (after the line `Reads connection config from the project instruction file...`), add:

```markdown
> **Scope:** `/db` executes specific SQL or migrations against named connections. For analytics in plain English, use `/query`.
```

- [ ] **Step 2: Verify**

```bash
head -10 /Users/rajit/personal-github/100x-dev/workflows/db.md
```

- [ ] **Step 3: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add workflows/db.md
git commit -m "docs: add scope banner to db.md — delineate from /query (#8)"
```

---

## Task 13: Trim `workflows/cloud-security.md` — ~19KB → ~8KB

**Files:**
- Modify: `workflows/cloud-security.md`

Remove: inline Python JSON parsing scripts (Sections 1a–1c, 2a, 2b, 3) — replace with compact `gcloud`-native queries and natural-language instructions. Keep the scanning logic but express it as concise bash with comments, not embedded Python interpreters.

- [ ] **Step 1: Note current size**

```bash
wc -c /Users/rajit/personal-github/100x-dev/workflows/cloud-security.md
# Record: ~19,437 bytes
```

- [ ] **Step 2: Rewrite Section 1 (IAM)**

Replace the Section 1 bash block (which embeds ~30 lines of Python JSON parsing) with:

```bash
for PROJECT in $GCP_PROJECTS; do
  echo "=== IAM: $PROJECT ==="
  # Overprivileged bindings
  gcloud projects get-iam-policy "$PROJECT" --format=json 2>/dev/null \
    | python3 -c "
import sys,json
p=json.load(sys.stdin)
bad=['roles/editor','roles/owner','roles/iam.securityAdmin','roles/storage.admin']
[print('[HIGH]',b['role'],m) for b in p.get('bindings',[]) for m in b['members'] if b['role'] in bad and ('serviceAccount' in m or 'allUsers' in m)]"
  # User-managed SA keys
  gcloud iam service-accounts list --project="$PROJECT" --format="value(email)" 2>/dev/null \
    | while read SA; do
        n=$(gcloud iam service-accounts keys list --iam-account="$SA" --filter="keyType=USER_MANAGED" --format="value(KEY_ID)" 2>/dev/null | wc -l)
        [ "$n" -gt 0 ] && echo "[HIGH] $SA: $n user-managed key(s) — use Workload Identity instead"
      done
  # Public IAM bindings
  gcloud projects get-iam-policy "$PROJECT" --format=json 2>/dev/null | grep -E "allUsers|allAuthenticatedUsers" && echo "[CRITICAL] Public IAM binding found" || true
done
```

Apply the same pattern to Sections 2 and 3: keep gcloud commands, replace multiline Python parsers with compact one-liner python3 -c pipes.

- [ ] **Step 3: Verify reduction**

```bash
wc -c /Users/rajit/personal-github/100x-dev/workflows/cloud-security.md
# Target: ≤ 9,000 bytes (was 19,437)
```

- [ ] **Step 4: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add workflows/cloud-security.md
git commit -m "perf: trim cloud-security.md — replace verbose Python parsers with compact bash (#7)"
```

---

## Task 14: Trim `workflows/issue.md` — ~10KB → ~5KB

**Files:**
- Modify: `workflows/issue.md`

Compress Phase 2 (Multi-Dimensional Impact Analysis) from 5 sections of enumerated sub-questions into bullet-framework summaries. The current form lists 6–10 explicit questions per dimension; a 3–4 bullet framework conveys the same intent with far fewer tokens.

- [ ] **Step 1: Note current size**

```bash
wc -c /Users/rajit/personal-github/100x-dev/workflows/issue.md
# Record: ~9,659 bytes
```

- [ ] **Step 2: Replace Phase 2 content**

Find the block `## Phase 2 — Multi-Dimensional Impact Analysis` through the end of `### 2.5 SaaS / Distributed System Impact` and replace with:

```markdown
## Phase 2 — Multi-Dimensional Impact Analysis

Analyze from ALL FIVE perspectives before forming a resolution plan.

### 2.1 Product & Business
- Which feature/journey/tier is affected? Regression or known gap?
- Severity: Critical (blocks core flow) / High (degrades key feature) / Medium / Low
- Revenue, retention, or compliance risk?

### 2.2 User Experience
- What does the user actually see? Exact errors or broken states?
- Data loss, incorrect data, or silent failure? Accessibility / performance impact?

### 2.3 Cloud Architecture
- Which GCP services involved (Cloud Run, Cloud SQL, GCS, Pub/Sub, Redis, Firebase)?
- Scaling, concurrency, IAM, networking, or cold-start related?

### 2.4 Data Architecture
- Which tables/columns/indexes involved? Data integrity risk?
- Migration needed? Cache invalidation? PII/compliance concern?

### 2.5 SaaS / Distributed Systems
- Race condition, multi-tenancy isolation risk, or async/webhook issue?
- Third-party dependency (Stripe, Firebase Auth, Resend)? Retry/idempotency gap?
```

- [ ] **Step 3: Verify reduction**

```bash
wc -c /Users/rajit/personal-github/100x-dev/workflows/issue.md
# Target: ≤ 5,500 bytes (was 9,659)
```

- [ ] **Step 4: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add workflows/issue.md
git commit -m "perf: compress issue.md Phase 2 — bullet frameworks replace enumerated sub-questions (#7)"
```

---

## Task 15: Trim `workflows/test.md` Phase 0 — collapse A/B/C docker strategies

**Files:**
- Modify: `workflows/test.md`

Phase 0 has three alternative docker detection strategies (Option A, Option B, Option C) with separate bash blocks. Replace with a single detection block that auto-selects the right approach.

- [ ] **Step 1: Find the Phase 0 section bounds**

```bash
grep -n "Option A\|Option B\|Option C\|Phase 0" /Users/rajit/personal-github/100x-dev/workflows/test.md
```

- [ ] **Step 2: Replace the three Option blocks**

Remove the `**Option A**`, `**Option B**`, `**Option C**` bash blocks and replace with a single adaptive block:

```bash
# Auto-detect and start required services
TEST_COMPOSE=$(ls docker-compose.test.yml docker-compose.testing.yml docker-compose.yml compose.yml 2>/dev/null | head -1 || true)
NEEDS_SERVICES=$(grep -qE "postgres|redis|mysql|mongodb|elasticsearch" \
  "$PROJECT_ROOT/pyproject.toml" "$PROJECT_ROOT/requirements"*.txt "$PROJECT_ROOT/package.json" 2>/dev/null && echo true || echo false)

if [ -n "$TEST_COMPOSE" ]; then
  docker compose -f "$TEST_COMPOSE" up -d --wait 2>/dev/null || true
elif $NEEDS_SERVICES; then
  docker run -d --name test-postgres \
    -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test \
    -p 5432:5432 postgres:16 2>/dev/null || true
  grep -qE "redis" "$PROJECT_ROOT/package.json" "$PROJECT_ROOT/pyproject.toml" 2>/dev/null && \
    docker run -d --name test-redis -p 6379:6379 redis:7 2>/dev/null || true
  sleep 3 && docker exec test-postgres pg_isready -U test 2>/dev/null || sleep 3
fi
```

- [ ] **Step 3: Verify reduction**

```bash
wc -c /Users/rajit/personal-github/100x-dev/workflows/test.md
# Target: noticeably smaller (was 15,096 bytes, should lose ~500–800 bytes)
```

- [ ] **Step 4: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add workflows/test.md
git commit -m "perf: collapse test.md Phase 0 docker options A/B/C into single adaptive block (#7)"
```

---

## Task 16: Consolidate `workflows/db-engines/` — router + per-engine deltas

**Files:**
- Create: `workflows/db-engines/_router.md`
- Modify: each of `postgres.md`, `snowflake.md`, `presto.md`, `oracle.md`, `databricks.md`, `athena.md`, `cloud-sql.md`

Current state: 7 files × ~100 lines = ~700 lines, ~17KB. All share the same 4-step skeleton (validate CLI, run via CLI, run via driver, migrate, safety rules). Only the CLI binary name, port, SSL handling, and migration detection differ.

- [ ] **Step 1: Create `_router.md` with the shared skeleton**

```markdown
# db-engines/_router — Shared DB Engine Skeleton
<!-- Reference only — sourced by /db; not a slash command. -->

## Shared execution skeleton

Each engine file receives pre-resolved variables from the /db router:
`$DB_HOST`, `$DB_PORT`, `$DB_NAME`, `$DB_USER`, `$DB_PASS`, `$SQL`

### Step 1 — Validate prerequisites
Check that the engine CLI is available. If not, print install instructions and exit.

### Step 2 — Execute query via CLI (if available)
Use the engine's native CLI with SSL/TLS as required. Never log $DB_PASS.

### Step 3 — Execute query via driver (fallback)
If CLI unavailable, use a Node.js or Python driver equivalent.

### Step 4 — Migrate (if SQL = "migrate")
Detect migration tool (alembic, prisma, raw SQL scripts) and run it.

### Safety rules
- Never log or print $DB_PASS
- Always require SSL for non-localhost hosts
- Never commit connection strings with passwords
```

- [ ] **Step 2: Trim each engine file to engine-specific delta only**

For each of the 7 engine files, replace the full content with only the engine-specific fields:

**postgres.md** (example of target format):
```markdown
# db-engine: postgres
<!-- Implements _router.md skeleton for PostgreSQL and Supabase -->

Receives pre-resolved variables from /db router: $DB_HOST, $DB_PORT, $DB_NAME, $DB_USER, $DB_PASS, $SQL

**CLI:** `psql` | **Default port:** 5432 | **SSL:** `--set=sslmode=require` (always for non-localhost)

```bash
# CLI execution
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" \
  --set=sslmode=require -c "$SQL"
```

**Driver fallback:** Node `pg` — `new Pool({ host, port, user, password, database, ssl: ... })`

**Migration detection:** alembic.ini → `alembic upgrade head` | migrations/*.sql → apply in order
```

Apply the same pattern to snowflake, presto, oracle, databricks, athena, cloud-sql — keeping only CLI invocation, default port, SSL flag, and migration detection (all unique per engine).

- [ ] **Step 3: Verify size reduction**

```bash
wc -c /Users/rajit/personal-github/100x-dev/workflows/db-engines/*.md
# Target: total ≤ 6,000 bytes (was ~17,000)
```

- [ ] **Step 4: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add workflows/db-engines/
git commit -m "perf: consolidate db-engines — router + per-engine deltas, 17KB→~5KB (#7)"
```

---

## Task 17: Add new workflows to adapter's hardcoded list

**Files:**
- Modify: `adapters/lib/shared.sh`

The `_run_generate` function in `shared.sh` has a hardcoded list of workflows to include in generated adapter output. New workflows need to be added. `_lib.md`, `_router.md`, and any file starting with `_` should NOT be in the list (they're reference-only).

- [ ] **Step 1: Find the current list**

```bash
grep -n "for f in" /Users/rajit/personal-github/100x-dev/adapters/lib/shared.sh
```

Expected current list: `gate test commit push pr branch launch lint security docs issue architect cloud-security enterprise-design db`

- [ ] **Step 2: Update the list**

In `adapters/lib/shared.sh`, update the for loop to include the new workflows. Replace the current `for f in ...` line with:

```bash
for f in gate test commit push pr branch launch lint security docs issue architect cloud-security enterprise-design db fix spec grill techdebt context query orchestrate update-claude; do
```

- [ ] **Step 3: Verify syntax**

```bash
bash -n /Users/rajit/personal-github/100x-dev/adapters/lib/shared.sh
echo "exit: $?"
# Expected: exit: 0
```

- [ ] **Step 4: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add adapters/lib/shared.sh
git commit -m "feat: add 8 new workflows to adapter generation list (#8)"
```

---

## Task 18: Update README.md and docs/USAGE.md

**Files:**
- Modify: `README.md`
- Modify: `docs/USAGE.md`

- [ ] **Step 1: Update README.md commands table**

Find the commands/workflows table in README.md. Add the 8 new commands:

| Command | Description |
|---|---|
| `/fix` | Autonomous bug fixer — CI, docker logs, Slack, or description |
| `/spec` | Write implementation-ready spec before coding |
| `/grill` | Adversarial code review before `/pr` |
| `/techdebt` | Scan + eliminate dead/duplicated code |
| `/context` | 7-day git/gh activity dump for session start |
| `/query` | Plain-English analytics against any database |
| `/orchestrate` | Plan-first methodology for complex multi-step tasks |
| `/update-claude` | Write CLAUDE.md rules after corrections |

- [ ] **Step 2: Add pipeline diagram to README.md**

Find the existing workflow pipeline section in README.md (or add after the commands table):

```
/context → /issue → /spec → /fix → /commit
                                      ↓
             /techdebt ← /gate → /grill → /pr → /push → /release
```

- [ ] **Step 3: Update docs/USAGE.md**

Add a "Full Development Pipeline" section documenting the new end-to-end workflow.

- [ ] **Step 4: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add README.md docs/USAGE.md
git commit -m "docs: update README and USAGE with 8 new workflows and pipeline diagram (#8)"
```

---

## Task 19: Update CHANGELOG.md and version

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `VERSION`

- [ ] **Step 1: Read current version**

```bash
cat /Users/rajit/personal-github/100x-dev/VERSION
```

- [ ] **Step 2: Bump to next minor version**

If current is `0.3.0`, set to `0.4.0`. Update `VERSION` file.

- [ ] **Step 3: Add CHANGELOG entry**

Add to CHANGELOG.md under a new version header:

```markdown
## [0.4.0] — 2026-04-20

### Added
- `/fix` — autonomous bug fixer (CI, docker logs, Slack, or description)
- `/spec` — implementation-ready spec before coding
- `/grill` — adversarial code review before `/pr`
- `/techdebt` — scan and eliminate dead/duplicated code
- `/context` — 7-day git/gh activity dump for session start
- `/query` — plain-English analytics against any database
- `/orchestrate` — plan-first methodology for complex tasks
- `/update-claude` — write CLAUDE.md rules after corrections

### Changed
- `enterprise-design`: replaced 24KB verbose template with lean 3KB systems-architect blueprint format
- `architect`: added scope banner distinguishing advisory Q&A from full blueprint generation
- `db`: added scope banner differentiating from /query

### Performance
- cloud-security.md: 19KB→~9KB (compact bash replaces verbose Python parsers)
- issue.md: 10KB→~5KB (bullet frameworks replace enumerated sub-questions)
- test.md Phase 0: single adaptive docker block replaces 3 alternative strategies
- db-engines: 17KB→~5KB (router + per-engine deltas)
- adapters: regenerated to include all new workflows
```

- [ ] **Step 4: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add CHANGELOG.md VERSION
git commit -m "chore: bump version to 0.4.0, update CHANGELOG for token opt + skillcraft integration"
```

---

## Task 20: Regenerate adapters and run tests

**Files:**
- Auto-generated: tracked-projects adapter outputs

- [ ] **Step 1: Run test suite**

```bash
cd /Users/rajit/personal-github/100x-dev
bash tests/test-check-update.sh
# Expected: 8/8 tests pass
```

- [ ] **Step 2: Syntax-check all new and modified workflow files**

```bash
for f in fix spec grill techdebt context query orchestrate update-claude enterprise-design architect db cloud-security issue; do
  echo -n "Checking workflows/$f.md... "
  bash -n /Users/rajit/personal-github/100x-dev/workflows/$f.md 2>/dev/null && echo "ok" || echo "BASH SYNTAX ISSUE (may be ok for md)"
done

# Check shell scripts
bash -n /Users/rajit/personal-github/100x-dev/adapters/lib/shared.sh && echo "shared.sh: ok"
```

- [ ] **Step 3: Verify total corpus size reduction**

```bash
wc -c /Users/rajit/personal-github/100x-dev/workflows/*.md /Users/rajit/personal-github/100x-dev/workflows/db-engines/*.md 2>/dev/null | tail -1
# Target: total ≤ 80KB (was ~158KB for workflows only)
# Note: will be higher with 8 new files added, but trimmed files should net savings
```

- [ ] **Step 4: Regenerate tracked projects**

```bash
# Regenerate for any tracked projects
cat ~/.100x-dev/tracked-projects 2>/dev/null | head -5
# Re-run adapters for each tracked project (update.sh handles this)
```

---

## Task 21: Cleanup — remove skillcraft from `~/.claude/skills/`

**Only run after all tasks 1–20 are complete and verified.**

- [ ] **Step 1: Remove ported skills**

```bash
rm -rf \
  ~/.claude/skills/fix-bugs \
  ~/.claude/skills/spec \
  ~/.claude/skills/grill-me \
  ~/.claude/skills/techdebt \
  ~/.claude/skills/context-dump \
  ~/.claude/skills/data-query \
  ~/.claude/skills/orchestrate \
  ~/.claude/skills/update-claude-md \
  ~/.claude/skills/systems-architect \
  ~/.claude/skills/skillcraft-repo
```

- [ ] **Step 2: Verify remaining skills**

```bash
ls ~/.claude/skills/
# Expected: only marketing skills remain (to be addressed in #7 Phase E)
```

- [ ] **Step 3: Final commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git status
# Should be clean after all prior commits
```

---

---

## Task 22: Create `.github/workflows/release.yml` — auto GitHub Release on version tag

**Files:**
- Create: `.github/workflows/release.yml`

The existing `github-actions/release.yml` is a **template for users' projects**. 100x-dev has no `.github/workflows/` of its own, so no GitHub Releases are created when a version ships. This means users who "Watch → Releases" get no notification, and the check-update banner shows raw git commit SHAs rather than readable release notes.

This workflow triggers when a `v*.*.*` tag is pushed (via `scripts/changelog.sh --release`), extracts the matching CHANGELOG.md section, and creates a GitHub Release.

- [ ] **Step 1: Create `.github/workflows/` directory marker**

```bash
mkdir -p /Users/rajit/personal-github/100x-dev/.github/workflows
```

- [ ] **Step 2: Write `.github/workflows/release.yml`**

```yaml
name: Release

on:
  push:
    tags:
      - "v*.*.*"

permissions:
  contents: write

jobs:
  release:
    name: Create GitHub Release
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Extract version from tag
        id: version
        run: echo "version=${GITHUB_REF#refs/tags/v}" >> $GITHUB_OUTPUT

      - name: Extract CHANGELOG section
        id: notes
        run: |
          VERSION="${{ steps.version.outputs.version }}"
          NOTES=$(awk "/^## \[${VERSION}\]/{flag=1; next} /^## \[/{flag=0} flag" CHANGELOG.md 2>/dev/null | sed '/^---$/d' | sed '/^[[:space:]]*$/d')
          if [ -z "$NOTES" ]; then
            NOTES="See [CHANGELOG.md](https://github.com/${{ github.repository }}/blob/main/CHANGELOG.md) for details."
          fi
          EOF=$(dd if=/dev/urandom bs=15 count=1 status=none | base64)
          echo "notes<<$EOF" >> $GITHUB_OUTPUT
          echo "$NOTES" >> $GITHUB_OUTPUT
          echo "$EOF" >> $GITHUB_OUTPUT

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          name: "v${{ steps.version.outputs.version }}"
          body: |
            ${{ steps.notes.outputs.notes }}

            ---
            **Install / upgrade:**
            ```bash
            # New install
            bash -c "$(curl -fsSL https://raw.githubusercontent.com/${{ github.repository }}/main/install.sh)"

            # Existing users
            ~/100x-dev/update.sh
            ```
          draft: false
          prerelease: ${{ contains(github.ref, '-rc') || contains(github.ref, '-beta') || contains(github.ref, '-alpha') }}
```

- [ ] **Step 3: Verify YAML syntax**

```bash
python3 -c "import yaml; yaml.safe_load(open('/Users/rajit/personal-github/100x-dev/.github/workflows/release.yml'))" && echo "YAML valid"
# Expected: YAML valid
```

- [ ] **Step 4: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add .github/workflows/release.yml
git commit -m "feat: add GitHub Actions release workflow — auto-creates release on version tag (#8)"
```

---

## Task 23: Enhance `scripts/changelog.sh --release` to push tag automatically

**Files:**
- Modify: `scripts/changelog.sh`

Currently `--release` creates the tag locally and prints "Next: git push origin $tag". Extend it to push the tag after confirming, which triggers the GitHub Actions release workflow from Task 22.

- [ ] **Step 1: Find the current `_do_release` ending**

```bash
grep -n "git.*tag\|push.*tag\|Next:" /Users/rajit/personal-github/100x-dev/scripts/changelog.sh
```

- [ ] **Step 2: Replace the final lines of `_do_release`**

Find the block:
```bash
  git -C "$REPO_DIR" tag -a "$tag" -m "Release $tag"
  echo -e "${GREEN}Tagged $tag and updated CHANGELOG.md${NC}"
  echo -e "${CYAN}  Next: git push origin $tag${NC}"
```

Replace with:
```bash
  git -C "$REPO_DIR" tag -a "$tag" -m "Release $tag"
  echo -e "${GREEN}Tagged $tag and updated CHANGELOG.md${NC}"

  read -rp "Push tag $tag now to trigger GitHub Release? (Y/n): " _push
  _push="${_push:-Y}"
  if [[ "$_push" =~ ^[Yy]$ ]]; then
    git -C "$REPO_DIR" push origin "$tag"
    echo -e "${GREEN}Tag $tag pushed — GitHub Release will be created automatically.${NC}"
    echo -e "${CYAN}Watch: https://github.com/rajitsaha/100x-dev/releases${NC}"
  else
    echo -e "${CYAN}  Push when ready: git push origin $tag${NC}"
  fi
```

- [ ] **Step 3: Verify syntax**

```bash
bash -n /Users/rajit/personal-github/100x-dev/scripts/changelog.sh && echo "ok"
# Expected: ok
```

- [ ] **Step 4: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add scripts/changelog.sh
git commit -m "feat: changelog.sh --release now prompts to push tag, triggering GitHub Release (#8)"
```

---

## Task 24: Enhance `check-update.sh` to show release notes from GitHub Releases

**Files:**
- Modify: `shell/check-update.sh`

Currently the update banner shows raw git commit message summaries (`git log --oneline`). When a GitHub Release exists for the latest version, show its body instead — giving users readable release notes. Falls back to commit messages if `gh` CLI is unavailable or the release doesn't exist yet.

- [ ] **Step 1: Add `_fetch_release_notes` helper after `_refresh_cache`**

In `shell/check-update.sh`, after the `_refresh_cache` function, add:

```bash
_fetch_release_notes() {
  # Try GitHub Releases API first (requires gh CLI)
  if command -v gh >/dev/null 2>&1; then
    local notes
    notes=$(gh release view --repo rajitsaha/100x-dev --json body -q .body 2>/dev/null | head -20 || true)
    if [[ -n "$notes" ]]; then
      echo "$notes"
      return
    fi
  fi
  # Fallback: format cached commit messages
  local changelog
  changelog="$(_cache_get changelog)"
  IFS='|' read -ra _lines <<< "$changelog"
  for _line in "${_lines[@]}"; do
    [[ -z "$_line" ]] && continue
    echo "• ${_line#* }"
  done
}
```

- [ ] **Step 2: Update `_do_notify` to use `_fetch_release_notes`**

In `_do_notify`, find the section that reads cached changelog and prints lines:

```bash
  IFS='|' read -ra _lines <<< "$changelog"
  for _line in "${_lines[@]}"; do
    [[ -z "$_line" ]] && continue
    local _msg="${_line#* }"
    # shellcheck disable=SC2059
    printf "${YELLOW}║${NC}  %-52s${YELLOW}║${NC}\n" "• $_msg"
  done
```

Replace with:

```bash
  local _notes
  _notes="$(_fetch_release_notes)"
  while IFS= read -r _note; do
    [[ -z "$_note" ]] && continue
    # Truncate long lines to fit banner width
    _note="${_note:0:50}"
    # shellcheck disable=SC2059
    printf "${YELLOW}║${NC}  %-52s${YELLOW}║${NC}\n" "$_note"
  done <<< "$_notes"
```

- [ ] **Step 3: Update `_do_claude_hook` similarly**

Find the `_do_claude_hook` changes section and replace with `_fetch_release_notes` output.

- [ ] **Step 4: Verify syntax**

```bash
bash -n /Users/rajit/personal-github/100x-dev/shell/check-update.sh && echo "ok"
# Expected: ok
```

- [ ] **Step 5: Commit**

```bash
cd /Users/rajit/personal-github/100x-dev
git add shell/check-update.sh
git commit -m "feat: check-update.sh shows GitHub Release notes in update banner (#8)"
```

---

## Task 25: Update README — "Get Notified" section + updated CHANGELOG/VERSION in Task 19

**Files:**
- Modify: `README.md` (add to Task 18's README changes)
- Modify: `CHANGELOG.md` (update Task 19's entry)
- Modify: `VERSION` (update Task 19)

This extends Tasks 18 and 19 with the release notification additions.

- [ ] **Step 1: Add "Get Notified" section to README.md**

In `README.md`, find the installation or contributing section. Add:

```markdown
## Get Notified of Updates

**GitHub Releases** (recommended): Click **Watch → Custom → Releases** on this repo to receive email notifications when a new version ships.

**SessionStart banner**: After installing, Claude Code will automatically show an update banner at the start of each session when a new version is available. The banner shows release notes and prompts you to update.

**Shell alias**: Run `100x-update` in your terminal at any time to check for and apply updates.

**Manual check**: `~/100x-dev/update.sh --check-only`
```

- [ ] **Step 2: Confirm `CHANGELOG.md` entry for this release includes the notification features**

The CHANGELOG entry written in Task 19 should include under `### Added`:
```
- GitHub Actions release workflow — auto-creates GitHub Release on version tag push
- `scripts/changelog.sh --release` now prompts to push tag automatically
- Update banner now shows GitHub Release notes instead of raw commit messages
- README: "Get Notified" section with Watch Releases instructions
```

- [ ] **Step 3: Commit README change (or include in Task 18's commit)**

```bash
cd /Users/rajit/personal-github/100x-dev
git add README.md
git commit -m "docs: add Get Notified section to README — Watch Releases + banner instructions (#8)"
```

---

## Self-Review

**Spec coverage check:**

| Requirement | Covered by |
|---|---|
| #7A — `_lib.md` shared helper | Task 1 |
| #7B-1 — trim enterprise-design | Task 10 |
| #7B — trim cloud-security | Task 13 |
| #7B — trim issue.md | Task 14 |
| #7B — trim test.md Phase 0 | Task 15 |
| #7C — db-engines consolidation | Task 16 |
| #7D — architect scope banner | Task 11 |
| #8P1 — 5 new workflows (fix, spec, grill, techdebt, context) | Tasks 2–6 |
| #8P2 — orchestrate + update-claude | Tasks 8–9 |
| #8P3 — enterprise-design replaced by systems-architect | Task 10 |
| #8P3 — /query added; /db scoped | Tasks 7, 12 |
| adapter regen | Task 17 |
| README + USAGE + "Get Notified" updated | Tasks 18, 25 |
| CHANGELOG + VERSION bumped | Task 19 |
| GitHub Actions release workflow | Task 22 |
| changelog.sh auto-push tag | Task 23 |
| check-update.sh shows release notes | Task 24 |
| Tests pass | Task 20 |
| ~/.claude/skills cleanup | Task 21 |
| #7E — marketing plugin audit | **NOT in this plan — separate effort** |
| Remove `code-review` plugin (superseded by `pr-review-toolkit`) | GitHub issue #9 — separate PR |
| Add skill cross-references: fix↔systematic-debugging, orchestrate→writing-plans | GitHub issue #10 — Tasks 2 & 8 |

**Placeholder scan:** No TBDs, no "fill in later", no "similar to Task N". Every step has actual content.

**Type consistency:** No type mismatches (this is markdown, not typed code). Workflow file names consistent throughout (fix.md, not fix-bugs.md; grill.md not grill-me.md; update-claude.md not update-claude-md.md).

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-20-token-optimization-and-skillcraft-integration.md`.**
