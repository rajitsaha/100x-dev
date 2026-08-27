# Token usage: audit, optimization & monitoring

A review of the installed Claude Code footprint (plugins, skills, hooks, MCP
servers, subagents) for duplication and token cost, plus a local dashboard to
monitor usage. Numbers below were measured from local transcripts
(`~/.claude/projects/**/*.jsonl`).

## TL;DR

- **93% of input tokens are cache reads** — the fixed context (system prompt +
  tool/skill/agent descriptions + SessionStart injections) re-sent on every turn.
  The lever is shrinking that fixed block and cutting redundant tool surface.
- **Startup context** measured at **median ~13K / avg ~26K tokens** before you
  type anything — much of it duplicated capability.
- Four overlapping **memory systems** were running at once; the claude-mem
  observer alone accounted for ~1.5B input tokens of history.

## The four token "purposes"

| Bucket | What it is | Relative $/token |
|---|---|---|
| **cache read** | Fixed context + history re-sent each turn, served from cache | 0.1× (cheap/token, huge volume) |
| **cache write** | Context written to cache on a miss / when it changes | 1.25× |
| **input** | New uncached text per turn (your messages, fresh tool results) | 1× |
| **output** | Model generations | 5× (costliest/token) |

Cost is dominated by **fixed-context size × number of turns**, not by what you type.

## Duplication & conflicting capabilities found

Overlaps span the whole installed ecosystem, not just this repo's modules:

| Capability | Competing implementations |
|---|---|
| Memory | claude-mem (MCP + observer + SessionStart dump) · remember plugin · `.remember/` · `MEMORY.md` |
| Code review | code-review plugin · pr-review-toolkit (7 agents) · code-simplifier · this repo's `grill-me`/`pr`/`commit` · superpowers review skills |
| Planning / orchestration | `orchestrate`,`spec` · superpowers planning skills · claude-mem `make-plan`/`do` · ralph-wiggum · built-in Workflow/Plan mode |
| Browser automation | playwright MCP **+** chrome-devtools-mcp (~55 tool schemas combined) |
| UI / design | frontend-design · ui-ux-pro-max · this repo's `visual-system-architect`/`interaction-engineer`/`motion-designer` |
| Debugging / TDD | `fix-bugs` vs superpowers `systematic-debugging`; `test` vs `test-driven-development` |

Within this repo's `modules/`, the only genuine duplicates were two pairs, now
**merged**:

- `systems-architect` → **`enterprise-design`** (the latter is a strict superset).
- `conversion-copy` → **`copywriting`** (folded in as a "Full-Page Mode" section;
  `figma-translator` repointed accordingly).

## Changes applied

### Live environment (`~/.claude/settings.json`, backed up first)

Disabled globally (re-enable per-project via a project `.claude/settings.json`):

| Plugin disabled | Why |
|---|---|
| `claude-mem` | Kept `remember` + `.remember/` instead; removes the ~15K SessionStart injection and the observer |
| `chrome-devtools-mcp` | Kept `playwright`; one browser stack is enough |
| `pr-review-toolkit` | 7 verbose agents loaded every session; overlaps the repo's own review path |
| `ui-ux-pro-max` | Overlaps `frontend-design` + this repo's design modules |

> Restore anytime: `cp ~/.claude/settings.json.bak.<timestamp> ~/.claude/settings.json`.
> A claude-mem observer process may still be running from before — it won't be
> relaunched in new sessions.

### This repo

- Merged the two duplicate module pairs (above); module count 68 → 66,
  auto-trigger skills 42 → 40. Counts synced across README/AGENTS/USAGE/install/package.
- Removed dead entries from `scripts/trigger-overlap-allow.txt`.
- Added `scripts/token-dashboard.py` (below).

### Update propagation (so removals actually reach users)

A merge/removal is only useful if `100xprism update` cleans up the old artifacts.
Two gaps were fixed so it does:

- **Claude Code skills + slash aliases now prune.** `emit-claude-code` writes a
  per-skill marker + a manifest, then removes any skill/alias it previously
  emitted that no longer exists (e.g. `systems-architect`, `conversion-copy`) —
  while never deleting the user's own hand-authored skills/commands. (Cursor and
  Codex emitters already pruned via markers.)
- **Plugins now add *and* remove.** `adapters/lib/sync_plugins.py` (used by both
  install and update) adds newly-declared plugins and removes ones 100xprism
  previously installed but has since dropped from `plugins.json`, without
  touching plugins the user enabled themselves or flipping a value they set. The
  managed set is tracked in a sidecar beside `settings.json`.

Single-file tool configs (Codex `AGENTS.md`, `.windsurfrules`,
`copilot-instructions.md`, `GEMINI.md`, `ANTIGRAVITY.md`) are regenerated
wholesale on update, so removed modules simply stop appearing. 100xprism does not
generate `CLAUDE.md` — it scaffolds an editable project file once and leaves it
to you.

## The routed index

The audit above shrank *what was installed*. This pass changes *what installation
costs*, by separating the two things a module charges you for:

- its **description** — re-sent on every turn, forever, once installed
- its **body** — free until the module is actually invoked

The committed footprint check measures every adapter in `all`, `profile`, and `must`
mode. It uses description characters ÷ 4 as a deterministic estimate and labels it
as such; these numbers are not provider-billed usage.

### Retention classes

Every module derives one (see `retention_of` in `adapters/lib/modules.py`; a module
can override it with `retention:` in frontmatter):

| Class | Kept because | Count |
|---|---|---|
| `must` | Deterministic machinery or house policy a model won't reproduce unprompted — the commands `gate` runs, the order `release` runs them in, the protocol `pair-loop` speaks. | 12 |
| `profile` | Earns its slot in repos of a matching kind. Also **anything owning a slash command**: the generic resolver route keeps it reachable. | 18 |
| `resolver` | General expertise a capable model already has. One catalog row, read by path on demand. | 38 |

Routed modules are copied to a catalog directory *outside* whatever the tool indexes
and listed in a generated `100x-resolver` artifact whose rows carry an exact path.
One description now stands in for 38.

### What it costs, measured

| Surface | Before | After | Notes |
|---|---|---|---|
| Claude Code user scope | 4,816 | **1,667** (`profile`) · **574** (`must`) | 68 → 31 → 13 indexed entries |
| Cursor project rules | 1,942 | **705** (`profile`) · **261** (`must`) | 68 → 31 → 13 indexed entries |
| Codex repo skills | 4,816 | **1,648** (`profile`) · **555** (`must`) | non-selected bodies move to the catalog |
| Pi package skills | 4,816 | **1,667** (`profile`) · **574** (`must`) | extensions remain available but opt-in |
| Consumer `CLAUDE.md` scaffold | ~350 | ~180 | commented TODOs → router table; config to `.claude/100xprism.yml` |

`commit`, `push` and `branch` moved from `tier: core` to `on-demand`, which is where
most of the unconditional Cursor win comes from: Cursor loads the full **body** of an
`alwaysApply: true` rule. All three are explicitly invoked, and the `gate-on-commit`
PreToolUse hook already blocks `git commit`/`git push` deterministically — the
always-resident copies were redundant with machine enforcement. `gate` stays resident.

### Lean by default

A fresh emit with no config keeps only must-have modules plus one resolver. Explicit
configuration widens the index and remains reversible.

| Scope | File | Values |
|---|---|---|
| user | `~/.100xprism/config.json` → `skills` | `must` (default) · `profile` · `all` |
| project | `<project>/.100xprism.json` → `profiles` | `[]`/unset = must; detected list = profile widening; `["all"]` = every module |

`100xprism optimize` writes both (`--dry-run`, `--all-projects`, `--skills=`), and
`100xprism slim` remains a compatibility alias. Install/update reconciliation removes
only marker- or sidecar-owned 100xprism artifacts; user-authored skills, rules, hooks,
and plugins are preserved.

### Does a smarter model make this unnecessary?

Partly, and the split above is drawn on exactly that line. What a capable model
already knows — "act as a Senior X, here is a framework" — is what became `resolver`
class. What it cannot know is the other two classes: which commands *this* repo's gate
runs, and that `user_id` is TEXT-not-UUID here, or that the Stripe webhook must
register `express.raw()` before `express.json()`. Model capability retires
**procedure**. It does not retire **project facts** or **determinism**, which is why
`CLAUDE.md` got restructured rather than deleted.

## Further recommendations (not yet applied)

1. Move rarely-used **user-scoped plugins to project scope** (`understand-anything`,
   `vercel`) so they don't load for every project.
2. Disable the `google-drive-write` MCP server if unused.
3. Pick **one reviewer** and **one planner** path to reduce ambiguity + description weight.
4. Compress the remaining descriptions: ~1,024 tokens are quoted trigger-phrase lists
   and ~599 are `"For X, see Y."` cross-references that would serve better in bodies.
5. Operational habits: `/context` to see the live window, `/clear` between unrelated
   tasks, and push big exploration into subagents to keep the main context lean.

## Local monitoring

### Built-in
- `/context` — live breakdown of what's filling the window right now.
- `/cost` — session tokens + cost.

### This repo's dashboard

```bash
100xprism tokens                            # web UI at http://127.0.0.1:8787
100xprism dashboard                         # alias for tokens
100xprism tokens --print                    # text summary, no server
100xprism tokens --json                     # fast versioned cross-tool counter report
100xprism tokens --json --tool codex        # exact source filter
100xprism audit --json                      # standing-context estimate and inventory
100xprism tokens --ensure-daemon            # start it detached if not already running
100xprism value                             # value report for the current directory
```

An explicit `token-dashboard.py` launch stops and replaces the previous owned
dashboard process. `--ensure-daemon` remains idempotent, so opening a new shell
does not restart a healthy daemon. Incremental refreshes inspect recent or newly
created transcripts; a full transcript reconciliation runs every 30 minutes.

**Start.** The dashboard does not launch during shell startup or ordinary
`100xprism install` / `init` / `update`. Start it explicitly with
`100xprism tokens`, `100xprism dashboard`, or `100xprism install --dashboard`.

Offline, no dependencies. Reads `~/.claude/projects/**/*.jsonl` and shows the four
token purposes, a **startup-bloat meter** (fixed context re-sent per turn), and
breakdowns by project / model / day. First run scans all transcripts (slow); later
runs use an incremental on-disk cache (`~/.claude/.token-dashboard-cache.json`).
Cost estimates use per-model $/1M-token rates (`scripts/pricing.py`, `RATES`),
with an explicit `PRICING_AS_OF` date and official source links; a
model id is matched by substring against a lowercased pattern list (most specific
first), so new model ids are usually priced correctly with no code change.
Unmatched ids fall back to Opus-tier rates and are counted separately — the
dashboard's `fallback_pct` shows what portion of total spend is a real per-model
price versus that fallback estimate.

**Machine-global + singleton.** It reads the *global* `~/.claude/projects`, so one
instance covers **every session and every repo/directory on the machine** at one
URL (with a by-project breakdown). Launching it again — from any repo, any session
— just opens the already-running URL instead of failing on a port clash. The
`100x-tokens` remains available as a compatibility alias if you manually source
`shell/aliases.sh`, but install no longer edits shell startup files or auto-starts
the dashboard. Prefer the CLI command: `100xprism tokens`.

**Content composition (estimate).** The dashboard and `--print` show where your
conversation *text volume* goes — **code written / code & files read / command
output & logs / model prose / your prompts / tool calls**. This is the
"what portion is code vs logs vs output" view. It is an **estimate** (chars ÷ 4),
*not* billed tokens: the API bills per-turn aggregates, not per content block, so
treat it as directional. It's the closest you can get without re-tokenizing.

### Value, not just cost

Tokens measure *cost*; the `100xprism tokens` dashboard measures *value* in the same view — no registration step needed.

The dashboard shows **every directory that consumed tokens** (repo or not) plus every agentic project discovered machine-wide by marker files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.cursorrules`, `.windsurfrules`, `.github/copilot-instructions.md`) — even directories with zero Claude token spend. Value is derived tool-agnostically from git history (commits / merged PRs / releases / files / churn — merged PRs are deduped by PR number across squash-merge subjects and real merge commits) with a filesystem-mtime fallback for non-repos, plus cached AI one-line summaries generated via the local `claude` CLI (non-blocking, degrades silently when absent).

Collection lives in a registry of pluggable per-tool adapters (`scripts/adapters/`).
`claude_code` and `codex` parse provider-recorded local token counters and support
list-price cost attribution. Pi is best-effort because its JSONL shape varies: only
records containing native usage fields are metered. `cursor` parses flat and nested JSONL beneath
`~/.cursor/projects/*/agent-transcripts` for project/session/message/date activity;
legacy `.txt`, `~/.cursor/chats`, and Cursor `state.vscdb` data are outside its scope.
`antigravity` joins local protobuf
conversation IDs and task-artifact timestamps to Antigravity workspace storage.
Cursor and Antigravity expose no provider token counters in these local formats,
so their rows are explicitly activity-only with `—` cost—never a fabricated $0
or character-based billing estimate.

The dashboard's charts and tables — all inline SVG / vanilla JS, zero dependency, dark by default, with a persisted light/dark toggle:
- **Delivery scoreboard** — per-directory spend, shipped PRs/commits/files, insertions/deletions, and unit cost; it does not invent a monetary value score
- **Work-mix cards** — estimated code authored, files/docs read, model/chat prose, and terminal logs
- **Daily cost by model** — exact per-model list-price dollars, stacked over the last 30 active days
- **Dollar-spend donut** and **token-volume split** — separate views of economic cost and raw volume by input / output / cache-read / cache-write
- **Cost by directory**, plus an **all-directories table**
- **Data provenance** — usage-source counts, named-rate coverage, git-outcome join coverage, and measurement window
- **Activity-only coverage** — Cursor and Antigravity sessions/projects with message or artifact counts where exposed
- **Budget** — spend vs your configured daily/weekly limit (see Budgets, below)
- **Sessions** — top 50 sessions by cost, last 30 days
- **By skill** — cost and $/invocation per skill (see Skill attribution, below)
- **Main vs subagent** — cost split between the main conversation and Task-tool subagent branches
- **Pair-loop handoff runs** — coder/reviewer round costs for `pair-loop.py` runs, once any exist
- **GitHub PR insights** — opt-in PR metadata for local remotes and configured users/repos
- **Suggestions** — rule-based, offline cost-reduction suggestions ranked by estimated $ impact

`~/.100xprism/value.json` is an automatic per-directory cache (keyed by dir + git HEAD + date window), not a manual registry.

**Skill attribution.** Claude Code sets `attributionSkill` natively on transcript lines while a Skill tool is active — this is **exact** attribution, not a heuristic, and the dashboard's "by skill" table marks it `exact`. Built-in slash commands that aren't Skills (e.g. `/model`) don't set `attributionSkill`, so those are segmented via the `<command-name>/xyz</command-name>` marker in the preceding user turn instead — usage between one marker and the next, marked `attr.` in the table. That fallback is a boundary heuristic, same honesty convention as the char-based composition estimate above.

**Budgets.** Add a `budget` section to `~/.100xprism/config.json` (`daily_usd` / `weekly_usd` / `per_run_usd`, all `null` — inert — by default) to get a budget bar in the dashboard, a `⚠`/`‼` glyph in the `--oneline` shell summary, and a native OS notification (macOS `osascript`) the first time a period crosses 80% (WARN) or 100% (ALERT) in a day.

**GitHub PR insights.** Remote GitHub fetching is opt-in. The dashboard always detects local GitHub remotes, but it only calls the GitHub API when `gh` is authenticated and `github.enabled` is true in `~/.100xprism/config.json`. It fetches bounded PR metadata for locally checked-out GitHub repos plus explicitly configured GitHub users, then caches results for 30 minutes:

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

Run `gh auth login` first. The dashboard then shows PR counts, merged/open/closed split, comment-heavy PRs, docs-touching PRs, deleted-file PRs, and additions/deletions across the fetched repo set.

### Other options
- `npx ccusage@latest` and `npx ccusage@latest blocks --live` — terminal dashboards.
- OpenTelemetry (`CLAUDE_CODE_ENABLE_TELEMETRY=1` + an OTLP exporter) → Prometheus +
  Grafana for a persistent web dashboard graphing input/output/cache over time.
