# Version Notification System — Design Spec

**Date:** 2026-04-11  
**Status:** Approved  
**Scope:** Automatic update notification for all 100x-dev users across all supported AI coding tools

---

## Problem

Users who install 100x-dev have no way to know when a new version is available unless they manually run `100x-check`. Most never do. Updated workflows, bug fixes, and new adapters go unseen.

---

## Goals

- All users (Claude Code, Cursor, Copilot, Codex, Windsurf, Gemini, Antigravity) see update notifications
- Zero blocking on shell startup or Claude Code session start
- Check at most once per day (no hammering GitHub)
- Show banner + offer to update immediately
- After updating, auto-regenerate instruction files in all tracked projects

---

## Non-Goals

- Desktop push notifications (macOS `osascript`)
- Email or webhook notifications
- Forced auto-updates without user confirmation

---

## Architecture

Four components, each with a single responsibility:

```
shell/check-update.sh          ← owns all version-check + cache logic
shell/aliases.sh               ← shell startup: reads cache, shows banner
~/.claude/settings.json hook   ← Claude Code session: reads cache, injects notice
update.sh                      ← on update: auto-regenerates tracked projects
```

Shared state lives in `~/.100x-dev/`:
```
~/.100x-dev/
  update-cache          ← last check result (timestamp, SHAs, changelog)
  tracked-projects      ← list of project paths with generated instruction files
```

---

## Component 1: `shell/check-update.sh`

Central script. All other components call this.

### Flags

| Flag | Behaviour |
|------|-----------|
| `--silent` | Refresh cache only. No output. Used by background shell spawn. |
| `--notify` | Read cache. If update available, print banner + prompt "Update now? (Y/n)". |
| `--claude-hook` | Read cache. If update available, print session-context message. If not, print nothing. |

### Cache file format — `~/.100x-dev/update-cache`

```
last_check=1712345678
has_update=true
local_sha=abc1234
remote_sha=def5678
changelog=fix: detect Bun before enabling claude-mem|feat: shared adapter lib
```

Pipe-delimited changelog (max 5 entries) from `git log --oneline LOCAL..REMOTE`.

### Check logic

```
if (now - last_check) < 86400:
    read from cache, return
else:
    git fetch origin main --quiet (5s timeout)
    local_sha  = git rev-parse HEAD
    remote_sha = git rev-parse origin/main
    has_update = (local_sha != remote_sha)
    changelog  = git log --oneline local..remote (max 5 lines)
    write cache
```

If `git fetch` times out or fails (offline): preserve existing cache, update `last_check` to now (avoid retrying on every shell open when offline).

---

## Component 2: Shell Startup — `shell/aliases.sh`

On every new shell session, two things happen **in this order**:

**Step 1 — Read cache (instant, no network):**
```bash
_100x_check_notify() {
  local cache="$HOME/.100x-dev/update-cache"
  [[ -f "$cache" ]] || return
  local has_update
  has_update=$(grep '^has_update=' "$cache" | cut -d= -f2)
  [[ "$has_update" == "true" ]] || return

  # read SHAs and changelog from cache, show banner + prompt
  ...
  read -rp "Update now? (Y/n): " confirm
  [[ "${confirm:-Y}" =~ ^[Yy]$ ]] && "$HOME/100x-dev/update.sh"
}
_100x_check_notify
```

**Step 2 — Background cache refresh (non-blocking):**
```bash
("$HOME/100x-dev/shell/check-update.sh" --silent &) 2>/dev/null
```

This updates the cache for the **next** terminal session. Current session sees the last cached result.

### Banner format

```
╔══════════════════════════════════════════════════════╗
║  100x Dev update available: abc1234 → def5678        ║
║  • fix: detect Bun before enabling claude-mem        ║
║  • feat: shared adapter lib                          ║
╚══════════════════════════════════════════════════════╝
Update now? (Y/n):
```

### Snooze behaviour

If user answers N: write `snoozed_until` = now + 86400 to cache. Banner suppressed for 24h even if cache still shows `has_update=true`.

---

## Component 3: Claude Code SessionStart Hook

### Hook registration

Added to `~/.claude/settings.json` by both `install.sh` (Claude Code path) and `update.sh` (idempotent merge):

```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "~/100x-dev/shell/check-update.sh --claude-hook"
      }]
    }]
  }
}
```

### `--claude-hook` output

If update available:
```
> 100x Dev update available (abc1234 → def5678)
> Changes: fix: detect Bun • feat: shared adapter lib
> Run `100x-update` in your terminal to upgrade.
```

If no update: **no output** — hook produces nothing, session context is clean.

### Merge logic (in install.sh + update.sh)

Same Python snippet pattern as existing plugin merge — reads current `settings.json`, checks if the hook command is already present, adds it if not, writes back. Idempotent.

---

## Component 4: Auto-regeneration on Update — `update.sh`

After pulling latest and updating `~/.claude/commands/`, `update.sh` regenerates instruction files in all tracked projects.

### Tracked projects file — `~/.100x-dev/tracked-projects`

Each adapter writes its resolved `project_path` here on first run (one path per line, deduped). Example:
```
/Users/rajit/projects/my-app
/Users/rajit/work/api-service
```

### Regeneration logic

```bash
regenerate_tracked_projects() {
  local tracked="$HOME/.100x-dev/tracked-projects"
  [[ -f "$tracked" ]] || return

  while IFS= read -r project_path; do
    [[ -d "$project_path" ]] || continue  # skip deleted projects

    [[ -f "$project_path/.cursorrules" ]]                        && bash "$REPO_DIR/adapters/cursor.sh"      "$project_path"
    [[ -f "$project_path/AGENTS.md" ]]                           && bash "$REPO_DIR/adapters/codex.sh"       "$project_path"
    [[ -f "$project_path/.windsurfrules" ]]                      && bash "$REPO_DIR/adapters/windsurf.sh"    "$project_path"
    [[ -f "$project_path/.github/copilot-instructions.md" ]]     && bash "$REPO_DIR/adapters/copilot.sh"    "$project_path"
    [[ -f "$project_path/GEMINI.md" ]]                           && bash "$REPO_DIR/adapters/gemini.sh"      "$project_path"
    [[ -f "$project_path/ANTIGRAVITY.md" ]]                      && bash "$REPO_DIR/adapters/antigravity.sh" "$project_path"
  done < "$tracked"
}
```

Claude Code (`~/.claude/commands/`) is already handled by the existing workflow copy loop — no change needed there.

### Adapter write-back (shared.sh)

`_run_generate` in `adapters/lib/shared.sh` appends the resolved project path to `~/.100x-dev/tracked-projects` after successful generation (deduped with `sort -u`).

---

## Data Flow Summary

```
Shell open
  └─ aliases.sh
       ├─ read cache → banner + prompt (if update available)
       └─ spawn check-update.sh --silent (background, updates cache)

Claude Code session start
  └─ SessionStart hook → check-update.sh --claude-hook
       └─ read cache → inject notice into session (if update available)

User runs 100x-update
  └─ update.sh
       ├─ git pull
       ├─ copy workflows → ~/.claude/commands/
       ├─ merge plugins + hook into settings.json
       ├─ regenerate tracked projects (cursor, codex, windsurf, copilot, gemini, antigravity)
       └─ clear has_update from cache

Adapter runs (cursor.sh, codex.sh, etc.)
  └─ shared.sh _run_generate
       └─ append project_path → ~/.100x-dev/tracked-projects
```

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| No internet / git fetch timeout (5s) | Preserve existing cache, update timestamp to avoid retry storm |
| `~/.100x-dev/` doesn't exist | `check-update.sh` creates it on first run |
| Tracked project path no longer exists | Skip silently during regeneration |
| `settings.json` missing hooks key | Merge logic creates it |
| User declines update (N) | Snooze banner for 24h via `snoozed_until` in cache |

---

## Files Changed

| File | Change |
|------|--------|
| `shell/check-update.sh` | **New** — central cache + check + notify script |
| `shell/aliases.sh` | Add `_100x_check_notify` function + background spawn |
| `adapters/lib/shared.sh` | Add tracked-projects write-back in `_run_generate` |
| `update.sh` | Add `regenerate_tracked_projects` + SessionStart hook merge |
| `install.sh` | Add SessionStart hook merge in Claude Code install path |

---

## Testing Plan

- [ ] Fresh install: cache file created on first shell open
- [ ] With stale cache showing update: banner appears, Y updates, N snoozes 24h
- [ ] Offline: no crash, existing cache preserved
- [ ] Claude Code session: hook injects notice when update available, silent when not
- [ ] `100x-update`: tracked projects regenerated, cache cleared
- [ ] Adapter run: project path written to tracked-projects
- [ ] Duplicate project paths: deduped in tracked-projects
