# How to Use 100x Dev

---

## How It Works

100x Dev provides 25 AI development workflows as markdown instructions. Your AI tool reads them and follows them — running bash commands, enforcing thresholds, looping until checks pass.

| Approach | Tools | How workflows are delivered |
|:---------|:------|:---------------------------|
| **Global install** | Claude Code | Copied to `~/.claude/commands/` — available in every project as slash commands |
| **Per-project** | Cursor, Codex, Windsurf, Copilot, Gemini, Antigravity | Concatenated into one instruction file (`.cursorrules`, `AGENTS.md`, etc.) — commit it to your repo |

---

## Installation

**Mac / Linux** — run once per machine:
```bash
curl -fsSL https://raw.githubusercontent.com/rajitsaha/100x-dev/main/get.sh | bash
source ~/.zshrc   # or ~/.bashrc — reload shell to activate the 100x-dev command
```

**Windows** (or anywhere Node.js is installed):
```bash
npm install -g 100x-dev && 100x-dev install
```

The installer sets up Claude Code globally (`~/.claude/commands/`) and scaffolds a `CLAUDE.md` in your project with placeholders for DB config, GCP, production URLs, and security exceptions.

> **Terminal vs Claude Code:** The `100x-dev` command and its subcommands (`init`, `update`, `check`) run in your **terminal** (zsh/bash). Slash commands like `/commit`, `/gate`, and `/reload-plugins` run **inside Claude Code**. Don't mix them up — if you see "command not found", you're likely in the wrong environment.

### Add to a project

Run once from each project root:

```bash
cd my-project && 100x-dev init
```

This writes the right instruction file for each enabled tool (`.cursorrules`, `AGENTS.md`, `.windsurfrules`, etc.). **Commit the generated file** so teammates get the same workflows.

### Keep up to date

```bash
100x-dev update   # pull latest + regenerate all tracked projects
100x-dev check    # check for a newer version without applying it
```

---

## Using the Workflows

### In Claude Code — slash commands

```
/context               7-day git + GitHub activity dump — orient before touching anything
/issue                 Investigate a bug and create a detailed GitHub issue
/spec                  Turn a vague request into an implementation-ready spec
/fix                   Autonomous bug fixer — CI failures, docker logs, Slack pastes
/gate                  5-point quality gate — run before every commit
/test                  All test layers against real Docker services, loops until 95% coverage
/test --all            Full pass across entire codebase
/test --unit           Unit tests only
/test --integration    Integration tests only (spins up Docker DB)
/test --e2e            Full-stack E2E via docker compose, zero mocks
/test --e2e staging    E2E against staging environment
/test --e2e prod       E2E against production
/commit                Gate → stage → conventional commit
/grill                 Adversarial self-review before opening a PR
/pr                    Gate → push branch → create PR
/push                  Gate → push → monitor CI → verify production health
/release patch         Bump patch version, tag, publish to PyPI/npm/Docker Hub, verify
/release minor         Bump minor version and publish
/release major         Bump major version and publish
/launch                Full deploy pipeline in one command
/branch                Create conventional feature branch (feat/, fix/, chore/)
/lint                  Auto-detect and fix all lint errors (ESLint, TypeScript, ruff)
/security              Scan for vulnerabilities and secrets, auto-fix where possible
/techdebt              Scan for dead code, duplication, stale TODOs
/db                    Query any of 7 database engines from one interface
/query                 Plain-English analytics — describe what you want, Claude writes the SQL
/architect             Architectural Q&A and decision matrices
/enterprise-design     Full technical blueprint — IA, API, data model, stack
/cloud-security        Deep GCP IAM, networking, PII, and compliance scan
/docs                  Detect code changes and update documentation
/orchestrate           Plan-first methodology for complex multi-step tasks
/update-claude         Write a CLAUDE.md rule after any correction
/connect               Install + auth any SaaS CLI (GitHub, AWS, Stripe, Supabase…) from .env
```

**Typical daily flow:**
```
/context   →  /spec or /fix   →  /test   →  /commit   →  /grill   →  /pr
```

### In other tools (Cursor, Codex, Windsurf, Copilot, Gemini)

Reference workflows by name in your prompts:

```
"Run the gate workflow before committing"
"Run the test workflow — I need 95% coverage"
"Follow the commit workflow"
"Run the security workflow on this project"
"Use the launch workflow to ship this release"
```

---

## Propagating to Multiple Projects

### One project at a time

```bash
cd ~/projects/my-app && 100x-dev init
```

### Batch apply to all repos

```bash
for dir in ~/projects/*/; do
  [ -d "$dir/.git" ] && bash ~/100x-dev/adapters/cursor.sh "$dir"
done
```

### Auto-apply to every new repo (git init hook)

```bash
mkdir -p ~/.git-templates/hooks
cat > ~/.git-templates/hooks/post-checkout << 'HOOK'
#!/usr/bin/env bash
[ "$3" = "1" ] || exit 0   # branch checkout only
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
[ -f "$PROJECT_ROOT/.cursorrules" ] && exit 0   # already set up
[ -f "$HOME/100x-dev/adapters/cursor.sh" ] && \
  bash "$HOME/100x-dev/adapters/cursor.sh" "$PROJECT_ROOT"
HOOK
chmod +x ~/.git-templates/hooks/post-checkout
git config --global init.templateDir ~/.git-templates
```

Change `cursor` to your tool. Every `git clone` or `git init` now gets workflows automatically.

### Team onboarding

Add to your team's onboarding checklist:

```
- [ ] Mac/Linux: curl -fsSL https://raw.githubusercontent.com/rajitsaha/100x-dev/main/get.sh | bash
      Windows:   npm install -g 100x-dev && 100x-dev install
- [ ] Reload shell: source ~/.zshrc (or ~/.bashrc)
- [ ] cd <your-project> && 100x-dev init
- [ ] Open Claude Code in your project and run /gate
```

For teams using Cursor/Codex/etc., commit the generated instruction file to each repo — new team members get the workflows automatically on clone.

---

## Project-Specific Configuration

`install.sh` scaffolds a `CLAUDE.md` in your project. Fill in the sections that apply:

```markdown
## Database
# engine: postgres
# connections:
#   default:
#     host: localhost
#     port: 5432
#     name: mydb
#     user: myuser
#     auth: env:DB_PASSWORD

## Cloud (GCP)
# gcp_project: my-gcp-project
# cloud_run_service: my-service
# region: us-central1

## Production
# production_url: https://example.com
# health_url: https://example.com/health

## Security Exceptions
# security_exceptions:
#   - lodash CVE-2020-XXXX: dev dependency only, not in production bundle

## Rules
# Add project-specific Claude rules here. /update-claude appends to this section.
```

For per-project tools (Cursor, Codex, etc.) add the same config to the generated instruction file.

---

## Keeping Workflows Updated

```bash
100x-dev check    # check if an update is available
100x-dev update   # pull latest and regenerate all tracked projects
```

Claude Code shows an update banner at session start when a new version is available. After updating, instruction files in all tracked projects are regenerated automatically.

---

## GitHub Actions Templates

Copy into any project:

```bash
mkdir -p .github/workflows
cp ~/100x-dev/github-actions/ci.yml      .github/workflows/ci.yml
cp ~/100x-dev/github-actions/release.yml .github/workflows/release.yml
```

### ci.yml — runs on every push and PR

| Job | What it does |
|:----|:-------------|
| **lint** | ESLint, TypeScript `tsc --noEmit`, ruff. Skips steps that don't apply to your stack. |
| **unit-tests** | Unit + integration tests against real Docker Postgres 16 + Redis 7. 95% coverage enforced. |
| **e2e-tests** | Builds full `docker compose` stack, smoke tests first, then full Playwright suite. Skips if no `playwright.e2e.config.ts` or `e2e/` directory. |

### release.yml — runs on version tags (`v*.*.*`)

Pre-release checks → build → GitHub Release → publish to PyPI/npm/Docker Hub → verify from live registry → Homebrew tap update.

**Required secrets:** `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`, `NPM_TOKEN`. PyPI uses OIDC trusted publishing (no secret needed). Jobs that don't apply to your stack are skipped automatically.

---

## FAQ

**Does this work without an AI coding tool?**
No. The workflows are instructions for AI tools. Without an AI reading them, they're just markdown.

**Can I use only some workflows?**
Yes — workflows are independent. In Claude Code, just run the slash commands you need. In other tools, ask the AI to run a specific workflow by name.

**Will this slow down my workflow?**
The gate adds checks before commits. Most runs complete in under 2 minutes. Catching issues locally is faster than debugging production.

**How do I add a new database engine?**
Add a file to `workflows/db-engines/your-engine.md` following the pattern of existing engines.

**How do I contribute a new adapter?**
Source `adapters/lib/shared.sh`, call `_run_generate` with your output filename and tool name, add it to `install.sh`, and open a PR. Most adapters are under 15 lines.
