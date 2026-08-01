# How to Use 100xPrism

---

## How it works

100xPrism ships 67 modules as markdown files with YAML frontmatter. Your AI tool reads them and follows the instructions — running commands, enforcing thresholds, looping until checks pass.

Each module is the **single source of truth**. Adapters generate the right format for each tool:

| Delivery | Tools | How modules arrive |
|:---------|:------|:-------------------|
| **Global install** | Claude Code | Each module → `~/.claude/skills/<slug>/SKILL.md`, plus slash command aliases in `~/.claude/commands/` |
| **Per-project (multi-file)** | Cursor | One file per module → `.cursor/rules/<slug>.mdc` (auto-trigger via description) |
| **Per-project (Codex-native)** | Codex | Compact `AGENTS.md` + repo skills in `.agents/skills/` + hooks in `.codex/hooks.json` |

> Windsurf, Copilot, Gemini, and Antigravity were supported through v2.x via a single concatenated instruction file. That surface was removed in v3.0.0 — see the release notes.

---

## Installation

### Step 1 — Global setup (once per machine)

**Mac / Linux:**
```bash
curl -fsSL https://raw.githubusercontent.com/rajitsaha/100xprism/main/get.sh | bash
```

**Windows** (or anywhere Node.js is installed):
```bash
npm install -g 100xprism && 100xprism install
```

The installer:
0. Cleans legacy startup hooks, stale command links, and any old owned dashboard process
1. Emits all 67 modules to `~/.claude/skills/`
2. Creates slash command aliases in `~/.claude/commands/` for the modules whose command name differs from the skill name (`/fix`, `/grill`, `/context`, `/query`, `/update-claude`) — every other module is invoked as `/<skill-name>` directly
3. Merges 14 Claude Code plugins into `~/.claude/settings.json`
4. Leaves shell startup files untouched; optional aliases are available with `source ~/100xprism/shell/aliases.sh`
5. Copies 4 project templates to `~/100x-templates/`
6. Optionally installs enforcing hooks (gate-on-commit, secret-scan)

> **Terminal vs Claude Code:** `100xprism install`, `init`, `update`, and `check` run in your **terminal**. Slash commands like `/commit` and `/gate` run **inside Claude Code**. If you see "command not found", you're in the wrong environment.

### Step 2 — Project setup (once per project)

```bash
cd my-project && 100xprism init
```

This generates the right instruction files for each enabled tool (`.cursor/rules/`, `AGENTS.md`, `.agents/skills/`, `.codex/hooks.json`). **Commit the generated files** so teammates get the same modules on clone.

For Codex, `AGENTS.md` stays compact and the full 100xprism modules are emitted as repo-scoped skills under `.agents/skills/`. Use `$gate`, `$commit`, `$test`, or `/skills` in Codex to invoke them explicitly. Generated Codex hooks live in `.codex/hooks.json`; review and trust them with `/hooks` before relying on enforcement.

It also scaffolds a `CLAUDE.md` with placeholders for database, cloud, production URLs, and security exceptions — see [Project configuration](#project-configuration).

### Step 3 — Start using

Open Claude Code in your project and try:
```
/gate        # run the quality gate
/test        # run all test layers
/commit      # gate + stage + commit
```

---

## Keeping up to date

```bash
100xprism check                  # check if a newer version is available
100xprism update                 # pull latest + sync plugins + regenerate tracked projects
100xprism update --plugins-only  # refresh plugins only (when repo is already current)
```

`update` does the following:
1. Pulls the latest code from `origin/main`
2. Backs up `~/.claude/commands/` to `~/.claude/commands.bak.<timestamp>`
3. Re-emits all modules to `~/.claude/skills/` and `~/.claude/commands/`, and **prunes** any skill or slash-command alias 100xprism previously installed that no longer exists (e.g. a merged/renamed module) — your own hand-authored skills and commands are never touched
4. Reconciles plugins in `~/.claude/settings.json`: **adds** newly-declared plugins and **removes** ones 100xprism previously installed but has since dropped, without changing plugins you enabled or disabled yourself
5. Runs `claude plugin update` for each plugin (updates across all scopes)
6. Syncs any installed hooks to their latest versions
7. Regenerates instruction files in all tracked projects (Cursor `.cursor/rules/` and Codex `AGENTS.md` are rewritten wholesale, so removed modules simply stop appearing)

After updating, **restart your Claude Code session** to load the new modules and plugins.

> **Tip:** Plugins (superpowers, claude-mem, hookify, etc.) receive independent updates. Running `update --plugins-only` refreshes them without re-pulling the repo.

Run `100xprism check` when you want to check for an update.

---

## Custom install location

The `get.sh` installer clones to `~/100xprism` by default. It does not write that path into `~/.zshrc`, `~/.bashrc`, `~/.bash_profile`, or Claude `SessionStart` hooks.

If you have legacy startup entries from an older 100xprism version and then move/delete the checkout, you may see errors:
```
.zshrc:source: no such file or directory: /Users/<you>/100xprism/shell/aliases.sh
SessionStart:startup hook error
```

Run `100xprism uninstall` to remove legacy shell-startup source lines, stale command symlinks, and the old dashboard daemon. If you want aliases for a single terminal session, run:

```bash
source "$HOME/work/100xprism/shell/aliases.sh"   # adjust to your checkout path
```

---

## Using the modules

### In Claude Code — slash commands

The following 27 slash commands are available. Run them directly:

**Lifecycle:**
```
/branch                Create conventional feature branch (feat/, fix/, chore/)
/commit                Gate → stage → conventional commit
/grill                 Adversarial code review before opening a PR
/pr                    Gate → push branch → create PR
/push                  Gate → push → monitor CI → verify production health
/release patch         Bump patch version, tag, publish, verify
/release minor         Bump minor version and publish
/release major         Bump major version and publish
/launch                Full deploy pipeline in one command
```

**Quality:**
```
/gate                  5-point quality gate — MANDATORY before every commit
/test                  All test layers, loops until 95% coverage
/test --unit           Unit tests only
/test --integration    Integration tests only (spins up Docker DB)
/test --e2e            Full-stack E2E via docker compose
/test --e2e staging    E2E against staging environment
/test --e2e prod       E2E against production
/lint                  Auto-detect and fix all lint errors (ESLint, TypeScript, ruff)
/security              Vulnerability + secrets scan, auto-fix where possible
/cloud-security        GCP IAM, networking, PII, compliance scan
/eval                  Run module evals — check triggers and output quality
```

**Engineering:**
```
/spec                  Turn a vague request into an implementation-ready spec
/fix                   Autonomous bug fixer — CI failures, docker logs, Slack pastes
/orchestrate           Plan-first methodology for complex multi-step tasks
/techdebt              Dead code, duplication, stale TODOs
/context               7-day git + GitHub activity dump
/update-claude         Write a CLAUDE.md rule after any correction
```

**Data & Infrastructure:**
```
/db                    Query any of 7 database engines from one interface
/query                 Plain-English analytics — describe what you want, get SQL
/connect               Install + auth 27 SaaS CLIs from .env
```

**Documentation & Architecture:**
```
/docs                  Detect code changes and update documentation
/issue                 Investigate a bug and create a detailed GitHub issue
/architect             Architectural Q&A and decision matrices
/enterprise-design     Full technical blueprint — IA, API, data model, stack
```

### Auto-trigger skills (40 skills)

These modules activate automatically when your prompt matches their description. No slash command needed — just describe the task naturally:

- "Write homepage copy" → triggers `copywriting`
- "Audit SEO on this page" → triggers `seo-audit`
- "Optimize the signup flow" → triggers `signup-flow-cro`
- "Plan a product launch" → triggers `launch-strategy`
- "Audit this page for WCAG accessibility" → triggers `a11y-auditor`
- "Spec the modal entrance animation" → triggers `motion-designer`
- "Pick the right chart for this dashboard" → triggers `data-viz`

### In Codex

Codex gets native repo skills instead of deprecated custom prompt slash commands:

```
$gate        # run the gate skill
$test        # run the test skill
$commit      # gate + stage + commit
```

You can also type `/skills` and pick a 100xprism skill. If you type a Claude-style workflow name like `/gate` in prose, the generated `AGENTS.md` tells Codex to treat that as the matching skill request.

Codex hooks are generated into `.codex/hooks.json`:

- `gate-on-commit` blocks `git commit` / `git push` until the gate cache matches the current tree.
- `secret-scan` blocks obvious hard-coded credentials in writes.

Open `/hooks` in Codex to inspect and trust generated hooks. Claude Code plugins from `plugins/plugins.json` do not install into Codex; use Codex `/plugins` for Codex-native plugins and app/MCP integrations.

### In Cursor

Reference modules by name in your prompts:

```
"Run the gate workflow before committing"
"Run the test workflow — I need 95% coverage"
"Follow the commit workflow"
"Run the security workflow on this project"
```

Modules auto-trigger from their description (same as Claude Code). `tier: core` modules are written with `alwaysApply: true` and stay resident; the rest are agent-requested when their description matches.

---

## Daily workflows

**Typical session:**
```
/context → /spec or /fix → /test → /commit → /grill → /pr
```

**Pre-release:**
```
/context → /techdebt → /grill → /test → /commit → /gate → /pr → /launch → /release
```

**Quick bug fix:**
```
/fix "the login button returns 403" → /test → /commit → /pr
```

---

## Project configuration

`100xprism init` scaffolds a `CLAUDE.md` in your project. Uncomment and fill in the sections that apply:

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
# Project-specific rules. /update-claude appends here automatically.
```

These sections are consumed by `/db`, `/gate`, `/cloud-security`, `/launch`, `/push`, and `/security`.

---

## Multi-project setup

### One project at a time

```bash
cd ~/projects/my-app && 100xprism init
```

### Batch apply to all repos

```bash
for dir in ~/projects/*/; do
  [ -d "$dir/.git" ] && (cd "$dir" && 100xprism init)
done
```

### Auto-apply on every clone (git template hook)

```bash
mkdir -p ~/.git-templates/hooks
cat > ~/.git-templates/hooks/post-checkout << 'HOOK'
#!/usr/bin/env bash
[ "$3" = "1" ] || exit 0   # branch checkout only
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
[ -f "$PROJECT_ROOT/.cursorrules" ] && exit 0   # already set up
command -v 100xprism >/dev/null && (cd "$PROJECT_ROOT" && 100xprism init)
HOOK
chmod +x ~/.git-templates/hooks/post-checkout
git config --global init.templateDir ~/.git-templates
```

Every `git clone` or `git init` now gets modules automatically.

### Team onboarding

Add to your team's onboarding checklist:

```
- [ ] Install: curl -fsSL https://raw.githubusercontent.com/rajitsaha/100xprism/main/get.sh | bash
      (Windows: npm install -g 100xprism && 100xprism install)
- [ ] Set up project: cd <your-project> && 100xprism init
- [ ] Open Claude Code and run /gate to verify
```

For Cursor/Codex teams, commit the generated instruction files — new members get modules on clone.

---

## GitHub Actions templates

Copy into any project:

```bash
mkdir -p .github/workflows
cp ~/100xprism/github-actions/ci.yml      .github/workflows/ci.yml
cp ~/100xprism/github-actions/release.yml  .github/workflows/release.yml
```

### ci.yml — runs on every push and PR

| Job | What it does |
|:----|:-------------|
| **lint** | ESLint, TypeScript `tsc --noEmit`, ruff. Skips steps that don't apply. |
| **unit-tests** | Unit + integration tests against real Docker Postgres 16 + Redis 7. 95% coverage enforced. |
| **e2e-tests** | Full `docker compose` stack, smoke tests, then Playwright suite. Skipped if no `playwright.e2e.config.ts` or `e2e/` directory. |

### release.yml — runs on version tags (`v*.*.*`)

Pre-release checks → build → GitHub Release → publish to PyPI/npm/Docker Hub → verify from live registry → Homebrew tap update.

**Required secrets:** `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`, `NPM_TOKEN`. PyPI uses OIDC trusted publishing (no secret needed). Jobs that don't apply are skipped automatically.

---

## Common CI traps

Three bugs that consistently cause CI failures when AI tools generate pipelines. All three are documented in the project templates and `ci.yml` with `# TRAP:` comments. [Full breakdown →](ci-traps.md)

### 1. npm package not published → Docker build 404

`npm install` passes locally (cached) but fails in Docker with `404 Not Found`.

```json
// Wrong — 404 in Docker
"dependencies": { "@yourorg/internal-client": "^0.1.0" }

// Fix — local file reference
"dependencies": { "@yourorg/internal-client": "file:./internal-client" }
```

### 2. `useState(false)` animation → Playwright timeout

Form renders with `opacity-0` on first paint. `toBeVisible()` fails on invisible elements.

```tsx
// Wrong — opacity-0 until mount effect runs
const [mounted, setMounted] = useState(false);

// Fix — initialize true (no SSR hydration guard needed in SPA)
const [mounted, setMounted] = useState(true);
```

### 3. Integration tests silently excluded

Tests pass in CI but integration failures only appear after merge.

```yaml
# Wrong — integration tests never run
run: pytest tests/unit/

# Fix — run both
run: pytest tests/unit/ tests/integration/
```

---

## Monitoring token usage

Claude Code records every session's token usage in `~/.claude/projects/**/*.jsonl`.
100xprism ships a local, offline dashboard to make sense of it:

```bash
100xprism tokens           # web UI at http://127.0.0.1:8787
100xprism tokens --print   # text summary, no server
```

It does not start during shell startup or ordinary `install` / `init` / `update`.
Install output prints the command to start it; it does not imply the URL is live.
Start it explicitly when you want it:

```bash
100xprism tokens
100xprism dashboard
100xprism install --dashboard   # optional one-time start after install
```

It breaks usage into the four token "purposes" — **input**, **output**,
**cache-read** (re-sent context, usually the largest), and **cache-write** — and
shows a **startup-bloat meter** (the fixed context re-sent every turn) plus
per-project / per-model / per-day breakdowns, **every directory you build in**
(token-spend dirs plus agentic projects discovered machine-wide via marker files),
and an **observable delivery scoreboard**. Cost tracking covers Claude Code and Codex CLI
sessions, priced per-model from a dated, source-linked catalog (`scripts/pricing.py`).
Cursor agent-transcript JSONL files and Antigravity conversations/task artifacts are also
collected for project, session, message/artifact, and date coverage. Cursor coverage is
limited to flat or nested JSONL beneath `~/.cursor/projects/*/agent-transcripts`;
legacy `.txt`, `~/.cursor/chats`, and Cursor `state.vscdb` data are not parsed. Their local
formats do not expose provider token counters, so the dashboard labels them
activity-only and leaves cost unavailable rather than estimating it. The first run scans all
transcripts; later runs use an incremental cache. The page auto-refreshes every
30s.

The default Economics view keeps three layers separate:

1. **Token economics** — metered tokens and estimated list-price spend.
2. **Observable delivery** — Git-backed PRs, commits, releases, files, and churn,
   with the percentage of spend that could be attributed to those sources.
3. **Business value** — explicitly **Not measured** until an outcome source such
   as adoption, revenue, incidents avoided, or verified time saved is connected.

`$/PR` and `$/commit` are labeled **delivery unit costs** and use attributed
spend only. They are not ROI or employee-performance scores. Outcome snapshots
currently use each directory's available source window; the UI does not present
them as selected-window outcomes.

It also shows top sessions and skills by cost, a main-vs-subagent cost split, and
a **recommendations panel** — rule-based, offline cost-reduction opportunities ranked by
estimated $ impact (e.g. trimming fixed startup context, or skills with a high
$/invocation).

The dashboard defaults to a dark, animated interface with a persisted light/dark
toggle. Motion is CSS-only and respects `prefers-reduced-motion`.

**Budgets.** Add a `budget` section to `~/.100xprism/config.json` to get a budget
bar in the dashboard, a `⚠`/`‼` glyph in the `--oneline` shell summary, and a
native OS notification the first time a period crosses 80%/100%:

```json
{
  "budget": {
    "daily_usd": 25,
    "weekly_usd": 150,
    "per_run_usd": null
  }
}
```

All keys default to `null` (no limit — the feature is inert until you set one).

**GitHub PR insights.** Remote GitHub metadata is opt-in. With `gh` authenticated,
the dashboard can fetch bounded PR data for detected local GitHub remotes plus
explicit users/repos:

```json
{
  "github": {
    "enabled": true,
    "users": ["octocat", "hubot"],
    "repos": [
      "acme/example-service",
      "acme/example-docs"
    ],
    "max_repos": 12,
    "max_prs_per_repo": 30,
    "max_pr_file_fetches_per_repo": 3,
    "max_user_repos_per_user": 20
  }
}
```

The GitHub view includes PR-level links, status, author, title, comments,
last-updated date, and bounded file/churn detail. Rows explicitly identify when
file details were not sampled.

It reports PR counts, merged/open/closed split, comment-heavy PRs, docs-touching
PRs, deleted-file PRs, and additions/deletions. Results are cached for 30 minutes.

To shrink token spend, audit your installed plugins/skills/MCP servers for
duplication and trim the fixed context — see
[docs/token-optimization.md](token-optimization.md). Built-in `/context` (live
window) and `/cost` (session total) complement the dashboard.

---

## Troubleshooting

| Problem | Solution |
|:--------|:---------|
| "command not found: 100xprism" | Reinstall or reshim your package manager: `npm install -g 100xprism && mise reshim node` if using mise |
| Slash command not recognized in Claude Code | Restart your Claude Code session — modules load at startup |
| "source: no such file: ~/100xprism/shell/aliases.sh" | Legacy shell startup entry — run `100xprism uninstall` or remove the source line from your rc file |
| "SessionStart:startup hook error" | Legacy Claude startup hook — run `100xprism install` or remove the 100xprism `SessionStart` hook from `~/.claude/settings.json` |
| Modules not updating after `100xprism update` | Restart your Claude Code session to pick up new modules |
| Codex skill not appearing | Restart Codex, then run `/skills`; verify `.agents/skills/<slug>/SKILL.md` exists |
| Codex hook not running | Run `/hooks` in Codex and trust the generated hook definition |
| `/gate` hangs on Docker check | Docker Desktop must be running, or set `SKIP_DOCKER=1` in your environment |
| Claude Code plugin not activating | Check `~/.claude/settings.json` → `enabledPlugins`, then restart Claude Code |
| Codex plugin not activating | Open Codex `/plugins`; Claude Code plugins from `plugins/plugins.json` are not Codex plugins |

---

## FAQ

**Does this work without an AI coding tool?**
No. Modules are instructions for AI tools. Without an AI reading them, they're just markdown.

**Can I use only some modules?**
Yes — modules are independent. In Claude Code, run only the slash commands you need. In Codex, invoke the matching skill with `$skill-name` or `/skills`. Auto-trigger skills activate only when relevant.

**Will this slow down my workflow?**
The gate adds checks before commits. Most runs complete in under 2 minutes. Catching issues locally is faster than debugging production.

**How do I add a custom database engine?**
Add a file to `modules/db/references/your-engine.md` following the pattern of existing engines, then run `100xprism update`.

**How do I contribute a new module?**
Create `modules/<slug>/SKILL.md` with the required frontmatter (`name`, `description`, `category`, `tier`), run `100xprism update` to regenerate, and open a PR.

**How do I contribute a new adapter?**
Create `adapters/<tool>.sh`, call `adapters/lib/modules.py` with your tool name, add it to `install.sh`, and open a PR.
