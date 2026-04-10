# 100x Dev

Production-grade AI development workflows for every coding tool.

Works with **Claude Code**, **Cursor**, **Codex**, **Windsurf**, **Copilot CLI**, **Gemini CLI**, and **Antigravity**.

## Quick Start

```bash
git clone https://github.com/rajitsaha/100x-dev.git ~/100x-dev
cd ~/100x-dev
./install.sh
```

The installer asks which tools you use and which components to install.

## What You Get

| Workflow | What it does |
|----------|-------------|
| **gate** | Pre-commit quality gate — tests, security, build, Docker, cloud security |
| **test** | Run all test layers (unit → integration → E2E), loop until ≥95% coverage |
| **commit** | Gate → stage → conventional commit |
| **push** | Gate → push → monitor CI/CD → verify production |
| **launch** | Full release pipeline: Docker → test → lint → security → build → commit → push |
| **lint** | Auto-detect linting stack, fix all errors, zero tolerance |
| **security** | Vulnerability scanner + secret audit |
| **docs** | Detect code changes, update corresponding docs |
| **issue** | Investigate and create detailed GitHub issues |
| **architect** | Cloud, data & SaaS architecture advisor |
| **cloud-security** | Cloud security & data privacy scan |
| **enterprise-design** | Enterprise design & systems architecture |
| **db** | Universal database access — 7 engines |

### Database Engines

| Engine | Connection method |
|--------|-----------------|
| `cloud-sql` | GCP Cloud SQL via temporary public IP |
| `postgres` | Direct TCP — PostgreSQL, Supabase |
| `snowflake` | Snowflake via snowsql or Python connector |
| `databricks` | Databricks SQL warehouse |
| `athena` | AWS Athena via boto3 |
| `presto` | Presto / Trino via Python client |
| `oracle` | Oracle via cx_Oracle or sqlplus |

## Supported Tools

| Tool | Install type | Project file |
|------|-------------|-------------|
| Claude Code | Global (`~/.claude/commands/`) | CLAUDE.md |
| Cursor | Project | .cursorrules |
| Codex (OpenAI) | Project | AGENTS.md |
| Windsurf | Project | .windsurfrules |
| Copilot CLI | Project | .github/copilot-instructions.md |
| Gemini CLI | Project | GEMINI.md |
| Antigravity | Project | ANTIGRAVITY.md |

**Global install** copies each workflow as a separate file — available in all your projects.

**Project install** generates a single instruction file containing all workflows — add it to your project repo.

## Templates

Project instruction file starters for common stacks:

```bash
# Copy a template and rename for your tool
cp ~/100x-templates/node-fullstack.md ./CLAUDE.md      # Claude Code
cp ~/100x-templates/node-fullstack.md ./.cursorrules    # Cursor
cp ~/100x-templates/node-fullstack.md ./AGENTS.md       # Codex
```

Available: `node-fullstack`, `node-frontend`, `python-api`, `docker-compose`

## Plugins (Claude Code)

14 curated plugins installed into Claude Code's settings:

superpowers, frontend-design, stripe, hookify, pr-review-toolkit, code-review, playwright, firecrawl, github, remember, skill-creator, code-simplifier, security-guidance, brightdata

Only installed when you select Claude Code + Plugins during setup.

## Shell Aliases

| Alias | What it does |
|-------|-------------|
| `cc` | Launch Claude Code in current directory |
| `ccc` | Continue last Claude Code session |
| `100x-update` | Pull and apply latest setup |
| `100x-check` | Check for updates without applying |

## Update

```bash
100x-check        # Check for updates
100x-update       # Pull and apply
```

## Add Your Own Tool

Write an adapter script in `adapters/`:

```bash
#!/usr/bin/env bash
# adapters/my-tool.sh
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

Then add it to `install.sh`'s tool selection. PRs welcome!

## Philosophy

- **No skips** — quality gates are mandatory
- **95% coverage** — not aspirational, enforced
- **Auto-fix first** — lint and security fixes applied automatically
- **Loop until clean** — tests re-run until all thresholds met
- **Tool-agnostic** — same workflows, any AI coding tool
