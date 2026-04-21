<div align="center">

<img src="assets/100x-dev-blogo.png" alt="100x Dev Logo" width="120" />

# 100x Dev

### Stop vibe coding. Start shipping production-grade software.

[![Version](https://img.shields.io/github/v/release/rajitsaha/100x-dev?style=flat-square&label=version&color=brightgreen)](https://github.com/rajitsaha/100x-dev/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude_Code-✓-blue?style=flat-square)](https://claude.ai)
[![Cursor](https://img.shields.io/badge/Cursor-✓-purple?style=flat-square)](https://cursor.com)
[![Codex](https://img.shields.io/badge/Codex-✓-green?style=flat-square)](https://openai.com)
[![Windsurf](https://img.shields.io/badge/Windsurf-✓-teal?style=flat-square)](https://windsurf.ai)
[![Copilot](https://img.shields.io/badge/Copilot-✓-orange?style=flat-square)](https://github.com/features/copilot)
[![Gemini](https://img.shields.io/badge/Gemini-✓-red?style=flat-square)](https://cloud.google.com/gemini)

</div>

---

24 slash commands. Quality gates on every commit. Works with any AI coding tool.

```bash
# Mac / Linux
curl -fsSL https://raw.githubusercontent.com/rajitsaha/100x-dev/main/get.sh | bash

# Windows (or anywhere Node.js is installed)
npm install -g 100x-dev && 100x-dev install
```

Run once per machine. Then to add 100x-dev to a project:

```bash
cd my-project && 100x-dev init
```

> **New here?** See the [full usage guide](docs/USAGE.md).

---

## The Pipeline

```
/context → /issue → /spec → /fix → /commit
                                      ↓
         /techdebt ← /gate → /grill → /pr → /push → /release
```

Every `/commit` and `/push` runs a 5-point quality gate — tests, security, build, Docker, cloud security. Nothing ships without passing.

---

## Commands

| Command | What it does |
|:--------|:-------------|
| `/context` | 7-day git + GitHub activity dump — orient before touching anything |
| `/issue` | Investigate a bug and create a detailed GitHub issue |
| `/spec` | Turn a vague request into an implementation-ready spec |
| `/fix` | Autonomous bug fixer — CI failures, docker logs, Slack pastes |
| `/gate` | 5-point quality gate — run before every commit |
| `/test` | Run all test layers against real Docker services, loop until 95% coverage |
| `/commit` | Gate → stage → conventional commit |
| `/grill` | Adversarial pre-PR review — challenge your own diff |
| `/pr` | Gate → push → create PR |
| `/push` | Gate → push → monitor CI → verify production health |
| `/release` | Version bump → tag → publish to PyPI/npm/Docker Hub → verify |
| `/launch` | Full deploy pipeline in one command |
| `/branch` | Create conventional feature branches (`feat/`, `fix/`, `chore/`) |
| `/lint` | Auto-detect and fix all lint errors (ESLint, TypeScript, ruff) |
| `/security` | Scan for vulnerabilities and secrets, auto-fix where possible |
| `/techdebt` | Scan for dead code, duplication, stale TODOs |
| `/db` | Query any of 7 database engines from one interface |
| `/query` | Plain-English analytics — describe what you want, Claude writes the SQL |
| `/architect` | Architectural Q&A and decision matrices |
| `/enterprise-design` | Full technical blueprint — IA, API, data model, stack |
| `/cloud-security` | Deep GCP IAM, networking, PII, and compliance scan |
| `/docs` | Detect code changes and update documentation |
| `/orchestrate` | Plan-first methodology for complex multi-step tasks |
| `/update-claude` | Write a CLAUDE.md rule after any correction |

---

## Supported Tools

| Tool | How it works |
|:-----|:-------------|
| **Claude Code** | Each workflow is a slash command in `~/.claude/commands/` |
| **Cursor** | All workflows concatenated into `.cursorrules` |
| **Codex** | All workflows embedded in `AGENTS.md` |
| **Windsurf** | All workflows in `.windsurfrules` |
| **Copilot CLI** | All workflows in `.github/copilot-instructions.md` |
| **Gemini CLI** | All workflows in `GEMINI.md` |
| **Antigravity** | All workflows in `ANTIGRAVITY.md` |

The installer asks which tools you use and sets up each one. For Claude Code it also scaffolds a `CLAUDE.md` in your project with placeholders for DB config, GCP project, production URLs, and security exceptions.

---

## What's Included

- **24 workflows** — full dev lifecycle from orientation to release
- **7 database adapters** — PostgreSQL, Cloud SQL, Snowflake, Databricks, Athena, Presto, Oracle
- **10 Claude Code plugins** — superpowers, frontend-design, playwright, github, pr-review-toolkit, hookify, skill-creator, code-simplifier, security-guidance, claude-mem
- **4 project templates** — node-fullstack, node-frontend, python-api, docker-compose
- **2 GitHub Actions templates** — CI pipeline (lint + real-DB tests + E2E) and release pipeline
- **Shell aliases** — `cc`, `ccc`, `100x-update`, `100x-check`

---

## Get Notified of Updates

**Watch releases**: Click **Watch → Custom → Releases** on this repo for email notifications.

**Auto-banner**: Claude Code shows an update notice at session start when a new version is available.

**Manual**: `100x-dev update` to update, `100x-dev check` to check.

---

## More

- [Full usage guide](docs/USAGE.md) — installation by tool, team onboarding, daily patterns
- [Changelog](CHANGELOG.md) — what's changed in each release
- [Contributing](https://github.com/rajitsaha/100x-dev/issues) — add an adapter in one shell script

---

<div align="center">

Built by [Rajit Saha](https://www.linkedin.com/in/rajsaha/) — 20+ years in enterprise data at Udemy, Experian, LendingClub, VMware, Yahoo.

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?style=for-the-badge&logo=linkedin)](https://www.linkedin.com/in/rajsaha/)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-black?style=for-the-badge&logo=github)](https://github.com/rajitsaha)

If this saves you time, **[star the repo](https://github.com/rajitsaha/100x-dev)** and share it with your team.

</div>
