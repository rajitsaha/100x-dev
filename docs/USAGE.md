# How to Use 100x Dev

This guide covers how to install, configure, and propagate 100x Dev workflows across all your projects — whether you're a solo developer or part of a team.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Installation by Tool](#installation-by-tool)
  - [Claude Code (Global)](#claude-code-global-install)
  - [Cursor](#cursor)
  - [Codex (OpenAI)](#codex-openai)
  - [Windsurf](#windsurf)
  - [Copilot CLI](#copilot-cli)
  - [Gemini CLI](#gemini-cli)
- [Propagating to All Your Projects](#propagating-to-all-your-projects)
  - [Strategy 1: One Command Per Project](#strategy-1-one-command-per-project)
  - [Strategy 2: Batch Apply to All Repos](#strategy-2-batch-apply-to-all-repos)
  - [Strategy 3: Git Init Hook (Auto-Apply to New Projects)](#strategy-3-git-init-hook-auto-apply-to-new-projects)
  - [Strategy 4: Team-Wide via Shared Script](#strategy-4-team-wide-via-shared-script)
- [Using the Workflows](#using-the-workflows)
  - [In Claude Code](#in-claude-code)
  - [In Other Tools](#in-other-tools)
- [Project-Specific Customization](#project-specific-customization)
- [Keeping Workflows Updated](#keeping-workflows-updated)
- [Multi-Tool Setup](#multi-tool-setup)
- [Team Onboarding](#team-onboarding)
- [FAQ](#faq)

---

## How It Works

100x Dev provides 15 AI development workflows (quality gates, testing, security scans, etc.) written as markdown instructions. Your AI coding tool reads these instructions and follows them.

**The key difference between tools:**

| Approach | Tools | How it works |
|:---------|:------|:-------------|
| **Global install** | Claude Code | Workflows are copied to `~/.claude/commands/`. Available in every project automatically. Nothing to add per-project. |
| **Per-project install** | Cursor, Codex, Windsurf, Copilot, Gemini | Workflows are generated into a single instruction file (`.cursorrules`, `AGENTS.md`, etc.) inside each project. You commit this file to your repo. |

---

## Installation by Tool

### Claude Code (Global Install)

Claude Code is the simplest — one install and every project gets the workflows.

```bash
# Install
cd ~/100x-dev && ./install.sh
# Select: Claude Code → Workflows → Plugins
```

**What happens:**
- 15 workflow files are copied to `~/.claude/commands/`
- 7 db-engine files are copied to `~/.claude/commands/db-engines/`
- Each file gets `$ARGUMENTS` appended (Claude Code's argument passing mechanism)
- 14 plugins are merged into `~/.claude/settings.json`

**After install:**
1. Restart Claude Code (or start a new session)
2. Run `/reload-plugins` to activate plugins
3. You now have `/gate`, `/test`, `/commit`, `/push`, `/launch`, `/lint`, `/security`, `/docs`, `/issue`, `/architect`, `/cloud-security`, `/enterprise-design`, `/db` available in every project

**No per-project setup needed.** Open any project directory, start Claude Code, and the slash commands are there.

---

### Cursor

```bash
# Option A: During install
cd ~/100x-dev && ./install.sh
# Select: Cursor → Workflows → enter your project path

# Option B: Direct adapter
bash ~/100x-dev/adapters/cursor.sh /path/to/your/project
```

**What happens:** A `.cursorrules` file is generated in your project root containing all 15 workflows.

**After install:**
1. Open the project in Cursor
2. Cursor reads `.cursorrules` automatically
3. Ask Cursor to "run the gate workflow" or "run the test workflow" — it follows the instructions

**Commit `.cursorrules` to your repo** so teammates get the same workflows.

---

### Codex (OpenAI)

```bash
# Option A: During install
cd ~/100x-dev && ./install.sh
# Select: Codex → Workflows → enter your project path

# Option B: Direct adapter
bash ~/100x-dev/adapters/codex.sh /path/to/your/project
```

**What happens:** An `AGENTS.md` file is generated in your project root.

**After install:**
1. Codex reads `AGENTS.md` automatically when working in the project
2. Reference workflows by name: "run the gate workflow", "run tests to 95% coverage"

**Commit `AGENTS.md` to your repo.**

---

### Windsurf

```bash
bash ~/100x-dev/adapters/windsurf.sh /path/to/your/project
```

Generates `.windsurfrules` in your project root. **Commit it to your repo.**

---

### Copilot CLI

```bash
bash ~/100x-dev/adapters/copilot.sh /path/to/your/project
```

Generates `.github/copilot-instructions.md`. **Commit the `.github/` directory to your repo.**

---

### Gemini CLI

```bash
bash ~/100x-dev/adapters/gemini.sh /path/to/your/project
```

Generates `GEMINI.md` in your project root. **Commit it to your repo.**

---

## Propagating to All Your Projects

For per-project tools (Cursor, Codex, Windsurf, Copilot, Gemini), you need to generate the instruction file in each project. Here are strategies from simplest to most automated.

### Strategy 1: One Command Per Project

Run the adapter in each project directory:

```bash
# Cursor example
bash ~/100x-dev/adapters/cursor.sh ~/projects/my-app
bash ~/100x-dev/adapters/cursor.sh ~/projects/my-api
bash ~/100x-dev/adapters/cursor.sh ~/projects/my-dashboard
```

Best for: A handful of projects.

---

### Strategy 2: Batch Apply to All Repos

Create a script that applies workflows to every repo in a directory:

```bash
#!/usr/bin/env bash
# save as: ~/100x-dev/apply-all.sh

TOOL="${1:-cursor}"  # default to cursor, or pass: codex, windsurf, copilot, gemini
PROJECTS_DIR="${2:-$HOME/projects}"

echo "Applying 100x Dev workflows ($TOOL) to all repos in $PROJECTS_DIR..."

for dir in "$PROJECTS_DIR"/*/; do
  if [ -d "$dir/.git" ]; then
    echo "  → $(basename "$dir")"
    bash ~/100x-dev/adapters/$TOOL.sh "$dir"
  fi
done

echo "Done. Commit the generated files in each repo."
```

Usage:

```bash
# Apply to all git repos in ~/projects/
bash ~/100x-dev/apply-all.sh cursor ~/projects

# Apply Codex workflows to all repos in ~/work/
bash ~/100x-dev/apply-all.sh codex ~/work
```

Best for: Many existing projects you want to onboard at once.

---

### Strategy 3: Git Init Hook (Auto-Apply to New Projects)

Automatically generate the instruction file whenever you create a new git repo:

```bash
# Create a global git template
mkdir -p ~/.git-templates/hooks

cat > ~/.git-templates/hooks/post-checkout << 'HOOK'
#!/usr/bin/env bash
# Auto-apply 100x Dev workflows on first checkout

# Only run on branch checkout (not file checkout)
[ "$3" = "1" ] || exit 0

# Only run if instruction file doesn't exist yet
# Change the adapter and filename for your tool:
TOOL="cursor"
case "$TOOL" in
  cursor)   FILE=".cursorrules" ;;
  codex)    FILE="AGENTS.md" ;;
  windsurf) FILE=".windsurfrules" ;;
  copilot)  FILE=".github/copilot-instructions.md" ;;
  gemini)   FILE="GEMINI.md" ;;
esac

PROJECT_ROOT="$(git rev-parse --show-toplevel)"
if [ ! -f "$PROJECT_ROOT/$FILE" ] && [ -f "$HOME/100x-dev/adapters/$TOOL.sh" ]; then
  bash "$HOME/100x-dev/adapters/$TOOL.sh" "$PROJECT_ROOT"
  echo "100x Dev: Generated $FILE"
fi
HOOK

chmod +x ~/.git-templates/hooks/post-checkout

# Tell git to use this template for all new repos
git config --global init.templateDir ~/.git-templates
```

Now every `git init` or `git clone` automatically gets the workflows.

Best for: Developers who want zero-friction adoption on every new project.

---

### Strategy 4: Team-Wide via Shared Script

For teams, add a setup script to your org's onboarding:

```bash
#!/usr/bin/env bash
# save as: setup-dev-environment.sh (add to your org's onboarding docs)

echo "Setting up 100x Dev workflows..."

# Install 100x Dev if not present
if [ ! -d "$HOME/100x-dev" ]; then
  git clone https://github.com/rajitsaha/100x-dev.git ~/100x-dev
fi

# Pull latest
cd ~/100x-dev && git pull origin main

# Run installer
./install.sh

echo ""
echo "For existing projects, run:"
echo "  bash ~/100x-dev/adapters/cursor.sh /path/to/project"
echo ""
echo "Or apply to all repos:"
echo "  for dir in ~/projects/*/; do"
echo "    [ -d \"\$dir/.git\" ] && bash ~/100x-dev/adapters/cursor.sh \"\$dir\""
echo "  done"
```

Best for: Engineering teams that want consistent quality standards across all developers and repositories.

---

## Using the Workflows

### In Claude Code

Workflows are available as slash commands. Use them directly:

```
/gate              Run the 5-point quality gate
/test              Run all tests, loop until 95% coverage
/test --all        Full test pass across entire codebase
/test --e2e        E2E tests only
/commit            Run gate → stage → conventional commit
/push              Run gate → push → monitor CI/CD
/branch            Create a feature branch from main with auto-naming
/pr                Create a PR with AI review (human merges)
/launch            Full release pipeline (Docker → test → lint → security → build → ship)
/lint              Fix all lint errors
/security          Scan for vulnerabilities and secrets
/docs              Update docs to match code changes
/issue             Investigate and create a GitHub issue
/architect         Get architecture advice
/cloud-security    Run cloud security & data privacy scan
/enterprise-design Generate enterprise design blueprint
/db                Query your database
/db "SELECT ..."   Run a specific SQL query
```

**Typical daily workflow:**

```
# Start your work
cc                          # alias for 'claude'

# Make changes, then...
/test                       # run tests, auto-write missing ones
/commit                     # runs gate first, then commits

# Ready to ship?
/push                       # runs gate, pushes, monitors CI

# Full release?
/launch                     # the whole pipeline, one command
```

```
# PR-based workflow (recommended for teams)
/branch                     # create feature branch
# ... make changes ...
/test                       # run tests
/pr                         # runs gate, pushes, creates PR, AI review
# → human reviews and merges on GitHub
```

### In Other Tools (Cursor, Codex, Windsurf, Copilot, Gemini)

These tools don't have slash commands. Instead, reference workflows by name in your prompts:

```
"Run the gate workflow before committing"
"Run the test workflow — I need 95% coverage"
"Follow the commit workflow"
"Run the security workflow on this project"
"Use the launch workflow to ship this release"
"Run the branch workflow — I need a feature branch for user auth"
"Run the pr workflow — create a PR with AI review"
```

The AI reads the instruction file, finds the workflow, and follows it step by step — running the same bash commands, enforcing the same thresholds.

**Tip:** You can ask for specific workflows or combine them:

```
"Run gate, then commit if it passes"
"Run test with --e2e flag against staging"
"Check the architect workflow — I need help with my database scaling strategy"
```

---

## Project-Specific Customization

The generated instruction file contains the universal workflows. For project-specific configuration, **add a project instruction file alongside it** (or extend the generated one):

### Database Configuration

Add a `## Database` section to your project instruction file:

```markdown
## Database
engine: postgres
host: db.example.supabase.co
port: 5432
database: postgres
user: postgres
auth: env:DATABASE_URL
```

### Security Exceptions

Document known exceptions so the security gate doesn't block on accepted risks:

```markdown
## Security Exceptions
- `lodash` prototype pollution (CVE-2020-XXXX) — install-time only, not exploitable at runtime
- `nth-check` ReDoS — dev dependency only, not in production bundle
```

### Custom Coverage Thresholds

If 95% is too aggressive for a legacy project you're onboarding, you can note an override:

```markdown
## Test Configuration
- Coverage threshold: 80% (legacy codebase, incrementally increasing)
- E2E environment: https://staging.example.com
```

### Health Endpoints

For the push and launch workflows to verify production:

```markdown
## Health Endpoints
- Production: https://api.example.com/health
- Staging: https://staging.example.com/health
```

---

## Keeping Workflows Updated

### Automatic (Shell Aliases)

```bash
100x-check        # Check if updates are available
100x-update       # Pull latest and re-run install
```

### Manual

```bash
cd ~/100x-dev
git pull origin main
./install.sh      # Re-run to copy updated workflows
```

### For Per-Project Files

After updating 100x Dev, re-generate the instruction files in your projects:

```bash
# Re-generate for a single project
bash ~/100x-dev/adapters/cursor.sh ~/projects/my-app

# Re-generate for all projects
for dir in ~/projects/*/; do
  [ -d "$dir/.git" ] && bash ~/100x-dev/adapters/cursor.sh "$dir"
done
```

**Tip:** If you committed the instruction file to your repo, this creates a diff you can review before committing the update.

---

## Multi-Tool Setup

Using multiple AI tools? Install for all of them:

```bash
# During install, select multiple tools
./install.sh
# Toggle: Claude Code, Cursor, Codex → confirm

# Or run adapters individually
bash ~/100x-dev/adapters/cursor.sh ~/projects/my-app
bash ~/100x-dev/adapters/codex.sh ~/projects/my-app
# Now the same project has both .cursorrules and AGENTS.md
```

The workflows are identical across tools. Your quality standards don't change when you switch tools.

---

## Team Onboarding

### For Engineering Managers

1. **Add 100x Dev to your onboarding checklist:**
   ```
   - [ ] Clone 100x-dev: git clone https://github.com/rajitsaha/100x-dev.git ~/100x-dev
   - [ ] Run installer: cd ~/100x-dev && ./install.sh
   - [ ] Verify: open a project and run /gate (Claude Code) or ask AI to "run the gate workflow"
   ```

2. **Commit instruction files to your repos:**
   ```bash
   # Generate and commit for your team's tool
   bash ~/100x-dev/adapters/cursor.sh .
   git add .cursorrules
   git commit -m "chore: add 100x Dev quality workflows"
   ```

3. **New team members clone the repo and get the workflows automatically** — they're in the committed instruction file.

### For Open Source Maintainers

Add the instruction file to your repo so every contributor gets the same quality gates:

```bash
# Generate for your community's most common tool
bash ~/100x-dev/adapters/cursor.sh .
bash ~/100x-dev/adapters/codex.sh .

# Commit both
git add .cursorrules AGENTS.md
git commit -m "chore: add AI coding quality workflows (100x-dev)"
```

Contributors using Cursor or Codex automatically get enforced quality gates on their AI-generated code.

---

## FAQ

### Does this work without an AI coding tool?

No. The workflows are instructions for AI coding tools. They tell the AI what commands to run, what thresholds to enforce, and how to handle failures. Without an AI tool reading them, they're just markdown files.

### Can I use only some workflows?

Yes. The workflows are independent. You can ask your AI tool to run specific ones:
- "Run only the test workflow"
- "Run security but skip the other gates"

For Claude Code, each workflow is a separate slash command, so you naturally pick which ones to run.

### Will this slow down my workflow?

The gate workflow adds checks before every commit. That's the point — catching issues before they ship is faster than debugging production at 2am. Most gate runs complete in under 2 minutes.

### Can I customize the coverage threshold?

Yes. Add a note in your project instruction file (see [Project-Specific Customization](#project-specific-customization)). The AI reads your project config and adjusts accordingly.

### How do I add a new database engine?

Create a new file in `workflows/db-engines/your-engine.md` following the pattern of existing engines. The db workflow auto-detects available engines.

### How do I update workflows across all my projects?

```bash
# Update 100x Dev
100x-update

# Re-generate for Claude Code (automatic — global install)
# Re-generate for other tools:
for dir in ~/projects/*/; do
  [ -d "$dir/.git" ] && bash ~/100x-dev/adapters/cursor.sh "$dir"
done
```

### Can I contribute a new adapter?

Yes. See the [Add Your Own Tool](../README.md#add-your-own-tool) section in the README. Write an adapter script in `adapters/`, add it to `install.sh`, and open a PR.
