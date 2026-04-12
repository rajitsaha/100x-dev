# Changelog

All notable changes to 100x-dev are recorded here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)

---

## [Unreleased]

### Added
- Version notification system: daily update check, shell banner, Claude Code session hook, auto-regeneration of tracked projects
- Shared adapter library (`adapters/lib/shared.sh`) — all 6 non-Claude adapters now use shared `_run_generate()` function

### Changed
- Consolidated 47 skills → 38 (merged copy, CRO, SEO skill groups; removed 3 niche skills)

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
