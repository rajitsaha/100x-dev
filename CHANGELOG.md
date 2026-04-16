# Changelog

All notable changes to 100x-dev are recorded here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)

---

## [Unreleased]

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
