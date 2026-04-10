<div align="center">

# 100x Dev

### Stop vibe coding. Start shipping production-grade software.

**15 battle-tested AI development workflows that enforce quality gates, security scans, and 95% test coverage — before every single commit.**

One install. Any AI coding tool. Zero excuses.

[![Claude Code](https://img.shields.io/badge/Claude_Code-supported-blue?style=flat-square)](https://claude.ai)
[![Cursor](https://img.shields.io/badge/Cursor-supported-purple?style=flat-square)](https://cursor.com)
[![Codex](https://img.shields.io/badge/Codex-supported-green?style=flat-square)](https://openai.com)
[![Windsurf](https://img.shields.io/badge/Windsurf-supported-teal?style=flat-square)](https://windsurf.ai)
[![Copilot](https://img.shields.io/badge/Copilot_CLI-supported-orange?style=flat-square)](https://github.com/features/copilot)
[![Gemini CLI](https://img.shields.io/badge/Gemini_CLI-supported-red?style=flat-square)](https://cloud.google.com/gemini)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

[Quick Start](#quick-start) | [Workflows](#what-you-get) | [Supported Tools](#supported-tools) | [How to Use](docs/USAGE.md) | [Templates](#templates) | [Contributing](#add-your-own-tool)

</div>

---

## The Problem

AI coding tools generate code fast. But fast code without quality gates is just **technical debt at 10x speed**.

Most developers using Claude Code, Cursor, or Codex have no guardrails. No enforced test coverage. No security scanning. No pre-commit gates. The AI writes it, you ship it, and production breaks at 2am.

## The Fix

**100x Dev** gives your AI coding tool a complete quality-enforced workflow system:

- Every commit passes a **5-point quality gate** (tests, security, build, Docker, cloud security)
- Test coverage **loops until 95%** — not aspirational, enforced
- Security vulnerabilities are **scanned and auto-fixed** before code leaves your machine
- Works with **7 AI coding tools** — same workflows, same standards, any tool

```bash
git clone https://github.com/rajitsaha/100x-dev.git ~/100x-dev
cd ~/100x-dev && ./install.sh
```

That's it. Your AI coding tool now has production-grade discipline.

> **New here?** Read the full **[How to Use guide](docs/USAGE.md)** — covers installation by tool, propagating workflows to all your projects, team onboarding, and daily usage patterns.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/rajitsaha/100x-dev.git ~/100x-dev

# 2. Install (interactive — picks your tools and components)
cd ~/100x-dev && ./install.sh

# 3. Use
# In Claude Code:  /gate, /test, /commit, /push, /launch
# In Cursor:       workflows embedded in .cursorrules
# In Codex:        workflows embedded in AGENTS.md
```

The installer asks which AI tools you use (Claude Code, Cursor, Codex, Windsurf, Copilot, Gemini, Antigravity) and installs workflows in the right format for each.

---

## What You Get

### 15 Production Workflows

| Workflow | What it does |
|:---------|:-------------|
| **gate** | 5-point pre-commit quality gate — tests, security, build, Docker, cloud security. Nothing ships without passing. |
| **test** | Runs all test layers (unit, integration, E2E). Writes missing tests. Loops until 95% coverage. |
| **commit** | Runs gate first, then stages and creates a conventional commit. |
| **push** | Re-runs gate, pushes, monitors CI/CD, verifies production health. |
| **pr** | Gate → push branch → create PR → full AI review → human merges. Never auto-merges. |
| **branch** | Create conventional feature branches from main — `feat/`, `fix/`, `chore/`, auto-push upstream. |
| **launch** | Full release pipeline: Docker, test, lint, security, build, commit, push — one command. |
| **lint** | Auto-detects your linting stack (ESLint, TypeScript, ruff). Fixes everything. Zero errors. |
| **security** | Scans all package managers for vulnerabilities. Audits for leaked secrets. Auto-fixes what it can. |
| **docs** | Detects code changes and updates corresponding documentation automatically. |
| **issue** | Investigates bugs and creates detailed, actionable GitHub issues. |
| **architect** | Cloud, data & SaaS distributed architecture advisor with GCP/AWS expertise. |
| **cloud-security** | Deep cloud security & data privacy scan — IAM, networking, PII, GDPR/CCPA compliance. |
| **enterprise-design** | Enterprise-grade design system and technical blueprint generation. |
| **db** | Universal database access — query any of 7 database engines from one interface. |

### The Quality Gate

Every commit and push runs through this. No exceptions.

```
╔══════════════════════════════════════════════════════╗
║               QUALITY GATE RESULTS                   ║
╠══════════════════════════════════════════════════════╣
║ Gate 1 Tests:          ✅ PASSED  (FE 97% | BE 96%) ║
║ Gate 2 Security:       ✅ PASSED  (0 critical)      ║
║ Gate 3 Build:          ✅ PASSED  (FE ✅ | BE ✅)    ║
║ Gate 4 Docker:         ✅ PASSED                     ║
║ Gate 5 Cloud Security: ✅ PASSED                     ║
╠══════════════════════════════════════════════════════╣
║ STATUS: ✅ ALL GATES PASSED — safe to commit         ║
╚══════════════════════════════════════════════════════╝
```

**If any gate fails, you fix it before committing.** That's the entire philosophy.

### 7 Database Engines

| Engine | Connection |
|:-------|:-----------|
| **PostgreSQL** | Direct TCP — PostgreSQL, Supabase, Neon |
| **Cloud SQL** | GCP Cloud SQL via temporary public IP |
| **Snowflake** | snowsql or Python connector |
| **Databricks** | SQL warehouse via Python connector |
| **Athena** | AWS Athena via boto3 |
| **Presto** | Presto / Trino via Python client |
| **Oracle** | cx_Oracle or sqlplus |

---

## Supported Tools

Works with every major AI coding tool:

| Tool | Install Type | Instruction File | How It Works |
|:-----|:------------|:-----------------|:-------------|
| **Claude Code** | Global | `~/.claude/commands/` | Each workflow becomes a slash command (`/gate`, `/test`, etc.) |
| **Cursor** | Per-project | `.cursorrules` | All workflows concatenated into your rules file |
| **Codex (OpenAI)** | Per-project | `AGENTS.md` | All workflows embedded in your agent instructions |
| **Windsurf** | Per-project | `.windsurfrules` | All workflows in your Windsurf rules |
| **Copilot CLI** | Per-project | `.github/copilot-instructions.md` | All workflows in Copilot instructions |
| **Gemini CLI** | Per-project | `GEMINI.md` | All workflows in Gemini instructions |
| **Antigravity** | Per-project | `ANTIGRAVITY.md` | Provisional adapter — ready when format is confirmed |

**Don't see your tool?** [Add your own adapter](#add-your-own-tool) — it's a single shell script.

---

## Templates

Jump-start any project with pre-configured instruction files:

```bash
# Copy a template and rename for your tool
cp ~/100x-templates/node-fullstack.md ./CLAUDE.md      # Claude Code
cp ~/100x-templates/node-fullstack.md ./.cursorrules    # Cursor
cp ~/100x-templates/node-fullstack.md ./AGENTS.md       # Codex
```

| Template | Stack |
|:---------|:------|
| `node-fullstack` | React + Vite + TypeScript + Node.js + Express + PostgreSQL |
| `node-frontend` | React + Vite + TypeScript + Vitest + Playwright |
| `python-api` | FastAPI / Flask + PostgreSQL + pytest |
| `docker-compose` | Multi-service: API + frontend + DB + cache |

---

## Plugins (Claude Code Bonus)

12 curated plugins auto-installed into Claude Code:

**superpowers** | **frontend-design** | **stripe** | **hookify** | **pr-review-toolkit** | **code-review** | **playwright** | **firecrawl** | **github** | **skill-creator** | **code-simplifier** | **security-guidance**

Only installed when you select Claude Code + Plugins during setup.

---

## Shell Aliases

| Alias | What it does |
|:------|:-------------|
| `cc` | Launch Claude Code in current directory |
| `ccc` | Continue last Claude Code session |
| `100x-update` | Pull latest workflows and apply |
| `100x-check` | Check for updates without applying |

---

## Add Your Own Tool

Write one adapter script in `adapters/`:

```bash
#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOWS_DIR="$REPO_DIR/workflows"

install_project() {
  local project_path="${1:-.}"
  local output_file="$project_path/.my-tool-config"

  {
    echo "# 100x Dev Workflows"
    for f in "$WORKFLOWS_DIR/"*.md; do
      echo "---"
      cat "$f"
    done
  } > "$output_file"
}

install_project "${1:-.}"
```

Add it to `install.sh` and open a PR. That's it.

---

## Philosophy

| Principle | What it means |
|:----------|:-------------|
| **No skips** | Quality gates are mandatory. No `--no-verify`. No exceptions. |
| **95% coverage** | Not a target. A requirement. The test workflow loops until it's met. |
| **Auto-fix first** | Lint errors, security vulnerabilities — fixed automatically where possible. |
| **Loop until clean** | Tests re-run, coverage re-checked, until every threshold passes. |
| **Tool-agnostic** | Same workflows, same standards, regardless of which AI tool you use. |

---

## Why I Built This

I've spent 20+ years building and scaling enterprise data platforms at companies like Udemy, LendingClub, VMware, and Yahoo. I've seen what happens when teams ship fast without guardrails — and I've seen what happens when quality is non-negotiable.

AI coding tools are the biggest productivity leap I've seen in two decades. But without discipline, they're just generating technical debt faster. **100x Dev** is the guardrail system I wish existed when AI coding tools first landed.

This project was built in collaboration with [Claude](https://claude.ai) — using the very workflows it contains.

---

<div align="center">

### Built by [Rajit Saha](https://www.linkedin.com/in/rajsaha/)

Tech leader | 20+ years building enterprise data platforms | Udemy, Experian, LendingClub, VMware, Yahoo

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?style=for-the-badge&logo=linkedin)](https://www.linkedin.com/in/rajsaha/)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-black?style=for-the-badge&logo=github)](https://github.com/rajitsaha)

---

If this saves you time, **[star the repo](https://github.com/rajitsaha/100x-dev)** and share it with your team.

Built with [Claude](https://claude.ai) | [Report an issue](https://github.com/rajitsaha/100x-dev/issues)

</div>
