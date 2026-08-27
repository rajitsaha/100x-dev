# 100xprism as a Pi package — design

> Status: approved · Shape **B** · 2026-08-18  
> Related: `docs/token-optimization.md`, pair-loop + skill-packs specs

## Problem / goal

Pi already speaks Agent Skills. Porting 100xprism’s Claude Code tax (68 indexed
descriptions, `plugins.json`, MCP) would waste that. Ship an **opt-in Pi
package** that keeps `modules/*/SKILL.md` as source of truth, indexes
**must + profile + one resolver**, enforces gate/secrets in extensions, leaves
other adapters alone, and adds Pi to pair-loop.

Standing description budget: **≈0.6–1.2k** tokens (not ≈4.7k).

## Non-goals (v1)

Shape C · port plugins/MCP · Cursor `alwaysApply` · Databricks on Pi ·
in-session “subagent” reviewers · claiming slim index alone is a 10× $ win.

## Locked decisions

| | |
|---|---|
| Shape | B — `emit-pi` + `package.json` `pi` manifest |
| Index | Retention **on** for Pi; widen via `profiles: ["all"]` |
| Slash | `/skill:<slug>`; prompt aliases only when command ≠ slug |
| Enforce | `tool_call` extensions; shell out to existing Python hooks in v1 |
| Pair-loop | Different **provider** required; same-provider different-model = fallback + `fallback_used`; same-model APPROVED refused (#93) |
| Budget | `$5` default when coder is `pi` |
| Install | `pi install git:github.com/rajitsaha/100xprism` (npm later) |

## Architecture

```
modules/*/SKILL.md → emit-pi → package.json "pi" { skills, prompts, extensions }
                              → project .pi/skills/ (filtered; Pi indexes these)
```

| New | Role |
|---|---|
| `emit-pi` | Retention-filtered skills + prompts; AGENTS.md only if missing |
| `pi/extensions/gate-secret.ts` | Block commit/push without gate-cache; block credential writes |
| `pi/extensions/retention.ts` | Resolver skills never enter system prompt |
| `scripts/adapters/pi.py` | Dashboard pricing for `~/.pi/agent/sessions/` |
| `reviewer.py` + `pi` vendor | Print-mode reviewer |

**Boundary:** no Pi forks inside SKILL bodies · `plugins.json` stays Claude-only ·
Pi project trust unchanged · Codex may keep full `.agents/skills/` (Pi does not —
Pi puts every discovered skill description in the system prompt).

## Pair-loop reviewer

```bash
pi -p --provider <≠coder> --model <mid-or-cheap> \
  --tools read,grep,find,ls --no-skills --no-extensions --no-session
```

`HANDOFF.md` / budget / #93 unchanged. Config adds `coder_provider`,
`reviewer_provider`, `coder_model`, `reviewer_model`.

## Cost messaging (order)

Empty tools → cheap mechanical models → isolated reviewer → cheap compaction →
slim index (clarity; modest $ alone). Measure before marketing $.

## Phases

1. **Ship:** `emit-pi`, `pi` manifest, gate+secret extensions, USAGE.
2. **Loop:** Pi session adapter, `reviewer` vendor `pi`, pair-loop docs, $5 default.
3. **Later:** model-tier ext, npm, compaction, Databricks pack.

## Test / success

Retention count ≠ 68 · gate blocks bare commit · secret fixture blocked ·
`npm run check` green · pair-loop pi↔pi different provider with dashboard cost ·
manual temp-HOME install shows ~must+profile(+1) skills in prompt.
