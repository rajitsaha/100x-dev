# Changelog

All notable changes to 100x-dev are recorded here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)

---

## [1.3.1] — 2026-04-20

### Fixed
- changelog.sh awk multiline variable — use temp file instead of -v flag
- changelog.sh --release now writes VERSION file automatically
- scaffold CLAUDE.md in user project during Claude Code install (closes #11)

### Changed
- docs: rewrite USAGE.md and e2e-patterns.md — concise, correct, 24 workflows
- chore: remove docs/superpowers/ — internal planning docs, not user-facing
- chore: remove ROADMAP.md — stale, GitHub Issues is source of truth
- docs: fix CHANGELOG order — newest first (1.3.0 → 1.2.0 → 1.1.0 → 1.0.0)
- docs: rewrite README — 300 lines → 130, install command visible in 10s
---

## [1.3.0] — 2026-04-20

### Added
- `/fix` — autonomous bug fixer (CI, docker logs, Slack, or description)
- `/spec` — implementation-ready spec before coding
- `/grill` — adversarial code review before `/pr`
- `/techdebt` — scan and eliminate dead/duplicated code
- `/context` — 7-day git/gh activity dump for session start
- `/query` — plain-English analytics against any database
- `/orchestrate` — plan-first methodology for complex tasks
- `/update-claude` — write CLAUDE.md rules after corrections
- `workflows/_lib.md` — shared conventions reference (excluded from adapter output)
- GitHub Actions release workflow — auto-creates GitHub Release on version tag push
- `install_project()` in Claude Code adapter — scaffolds `CLAUDE.md` with db/cloud/production/security placeholders (closes #11)

### Changed
- `enterprise-design`: replaced 24KB verbose template with lean 3KB systems-architect blueprint format (#7 #8)
- `architect`: added scope banner distinguishing advisory Q&A from full blueprint generation
- `db`: added scope banner differentiating from `/query`
- README rewritten — 300 lines → 130, install command visible within 10 seconds
- `install.sh` now prompts for project path when Claude Code is selected, consistent with all other adapters

### Performance
- cloud-security.md: ~19KB → ~12KB (compact bash replaces verbose Python parsers)
- issue.md: ~10KB → ~8KB (bullet frameworks replace enumerated sub-questions)
- test.md Phase 0: single adaptive docker block replaces 3 alternative strategies
- db-engines: ~17KB → ~5KB (router + per-engine deltas)
- enterprise-design.md: 24KB → 3KB (leaner systems-architect content)

---

## [1.2.0] — 2026-04-20

### Changed
- Removed `firecrawl@claude-plugins-official` from plugins (unused — web scraping not needed for dev workflow)
- Removed `stripe@claude-plugins-official` from plugins (unused — no Stripe integration in core workflows)
- Removed `code-review@claude-plugins-official` from plugins (superseded by `pr-review-toolkit` which provides multi-agent review)
- Plugin count: 13 → 10

### Added
- Plugin scope table in README documenting each plugin's purpose and overlap notes
- Code review pipeline diagram: `/grill` → PR → `/review-pr`
- GitHub issues #9 and #10 tracking remaining overlap remediation

### Performance
- ~3,000–5,000 tokens/session saved by removing 3 unused/redundant plugins from system prompt

---

## [1.1.0] — 2026-04-12

### Added
- Version notification system: daily update check, shell banner, Claude Code session hook, auto-regeneration of tracked projects
- Shared adapter library (`adapters/lib/shared.sh`) — all 6 non-Claude adapters now use shared `_run_generate()` function
- Banner and logo images added to assets/ and README.md header
- `docs/e2e-patterns.md` — extracted Playwright fixture, auth, and CRUD test reference patterns from test.md

### Changed
- Consolidated 47 skills → 38 (merged copy, CRO, SEO skill groups; removed 3 niche skills)
- **Token optimization** (closes #5): reduced per-invocation context overhead by ~3,500–4,500 tokens
  - Gate Phase 0 block deduplicated in commit.md, push.md, release.md (3× identical 12-line blocks → 1-line reference each)
  - `INSTRUCTION_FILE` detection loop (6 lines × 8 workflows) collapsed to a one-liner in all 8 files
  - test.md trimmed from 791 → 470 lines by extracting Phase 4c–4g E2E boilerplate to `docs/e2e-patterns.md`
  - Removed unused plugins: firecrawl, stripe, brightdata (save ~225 tokens/session from skill listing)
  - Added `<!-- model: haiku -->` hint to lint.md + security.md; `<!-- model: opus -->` to architect.md + enterprise-design.md

---

## [1.0.0] — 2026-04-11

### Added
- 16 production workflows: gate, test, commit, push, pr, branch, launch, release, lint, security, docs, issue, architect, cloud-security, enterprise-design, db
- 7 database engine adapters: PostgreSQL, Cloud SQL, Snowflake, Databricks, Athena, Presto, Oracle
- Adapters for 7 AI coding tools: Claude Code, Cursor, Codex, Windsurf, Copilot CLI, Gemini CLI, Antigravity
- 13 curated Claude Code plugins: superpowers, frontend-design, stripe, hookify, pr-review-toolkit, code-review, playwright, firecrawl, github, skill-creator, code-simplifier, security-guidance, claude-mem
- Shell aliases: cc, ccc, 100x-update, 100x-check
- GitHub Actions templates: ci.yml (lint + real-DB tests + E2E), release.yml (multi-registry publish)
- Project templates: node-fullstack, node-frontend, python-api, docker-compose
- Bun auto-detection before enabling claude-mem plugin
