# Cross-tool token observability and lean-context design

**Status:** Proposed — awaiting approval  
**Date:** 2026-08-26  
**Repository:** `100xprism`

## Summary

Turn 100xprism into a token-aware distributor that does two things consistently across Claude Code, Codex, Cursor, Pi, and future adapters:

1. **Measures usage honestly:** display exact provider token counters when the local tool exposes them; otherwise display clearly separated estimates or activity-only telemetry and never price invented tokens.
2. **Minimizes standing context by default:** fresh installs retain only must-have modules plus one compact resolver, install only a small core Claude plugin set, keep hooks reactive and opt-in, and automatically remove only obsolete artifacts that 100xprism itself previously managed.

The implementation must build on, not overwrite, the current uncommitted dashboard/Pi/pair-loop work in this checkout.

## Current-state audit

Observed in the working tree:

- 68 source modules.
- Claude user-scope default is currently `all`; Cursor/Codex project filtering is currently opt-in.
- `100xprism slim` already supports `all | profile | must` and writes reversible config.
- Claude installer currently selects all 14 declared plugins by default.
- Enforcing hooks are installer opt-in. In the hook manifest, gate and secret scan default on only after hook installation; lint and permission routing default off.
- Dashboard collectors already exist for:
  - Claude Code: exact local counters.
  - Codex: exact local cumulative counters converted to deltas.
  - Cursor: activity-only because observed local transcripts expose no provider counters.
  - Antigravity: activity-only.
  - Pi: best-effort exact counters when its JSONL contains usage.
- Measured standing-description proxies from generated artifacts:

| Surface | Indexed entries | Description chars | Approx. tokens (chars/4, estimate) |
|---|---:|---:|---:|
| Claude `all` | 68 | 19,263 | 4,816 |
| Claude `profile` | 31 | 6,592 | 1,648 |
| Claude `must` | 13 | 2,221 | 555 |
| Cursor unfiltered | 68 | 7,766 | 1,942 |
| Cursor `core` | 14 | 1,105 | 276 |
| Cursor `core,code` | 26 | 2,366 | 592 |

These are deterministic footprint estimates, not provider-billed usage.

## User decisions

- Fresh installs use **must-have only** by default and resolve everything else on demand.
- Claude installs a **small core plugin set** by default.
- Existing setups automatically remove **only 100xprism-managed** unused/stale artifacts.
- Usage reporting uses exact counters where available and explicitly labels estimates/activity-only elsewhere.

## Architecture

### 1. One normalized telemetry contract

Every tool collector returns a common record:

```json
{
  "tool": "claude-code | codex | cursor | pi | antigravity | ...",
  "session_id": "string",
  "project": "string",
  "cwd": "string|null",
  "day": "YYYY-MM-DD|unknown",
  "model": "string|unknown",
  "usage": {
    "input": 0,
    "output": 0,
    "cache_read": 0,
    "cache_write": 0
  },
  "measurement": {
    "kind": "exact | estimate | activity_only",
    "source": "tool-specific source identifier",
    "limitations": ["human-readable limitation"]
  }
}
```

Rules:

- `exact` requires counters emitted by the provider/tool. Exact data may be priced.
- `estimate` must include its estimation method and must never be visually merged with exact totals without a labeled breakdown.
- `activity_only` carries sessions/messages/artifacts but zero billable tokens and zero cost.
- Unknown models may show token counts but pricing uses a visibly labeled fallback or remains unavailable.
- Cumulative counters must be delta-normalized and handle reset/compaction events.
- Cache semantics are normalized per tool and documented per adapter.

### 2. Collector registry

Replace hard-coded imports in the dashboard build path with a collector registry under `scripts/adapters/`. Each adapter declares:

- tool id and display name;
- discovery/source path;
- supported measurement kinds;
- scan function;
- source-format/version notes;
- whether cost, model, cache, skill, and startup-context attribution are available.

A broken or absent collector is isolated: the dashboard continues and reports that source as unavailable.

Initial supported tools remain Claude Code, Codex, Cursor, Pi, and Antigravity. The registry is the extension point for additional tools without changing dashboard aggregation.

### 3. Two different token views

The UI and CLI must not conflate:

- **Utilization:** provider counters from completed/active sessions.
- **Standing context footprint:** deterministic inventory of installed/indexed instructions, skill descriptions, command aliases, MCP/tool definitions when discoverable, plugin declarations, and session-start injections.

Standing context is reported as bytes/chars and an explicitly labeled token estimate. Where a tool exposes an exact tokenizer/counter, that exact source can be added later, but the baseline implementation remains dependency-light and honest.

### 4. Lean artifact selection

Fresh-install defaults across adapters:

- `skills = must` unless explicitly overridden.
- Keep all must-have modules as native indexed skills/rules.
- Park every other module body outside indexed directories.
- Install exactly one compact `100x-resolver` entry that points to the parked catalog.
- Generate one generic cross-tool route (`100x <slug>` or the closest native equivalent) rather than keeping every non-must slash-command alias resident.
- Explicit `all` and `profile` modes remain reversible escape hatches.
- Project detection may recommend profiles, but it does not widen a fresh must-only install without explicit opt-in.

Generated manifests record mode, included modules, routed modules, estimated standing bytes, and generator version.

### 5. Plugin policy

Split `plugins/plugins.json` into policy groups while preserving one source of truth:

- **core default:**
  - `github@claude-plugins-official`
  - `security-guidance@claude-code-plugins`
- **profile-recommended:** e.g. Playwright/front-end plugins for detected web/design repos.
- **manual only:** overlapping or high-footprint plugins such as superpowers, hookify, claude-mem, broad UI packs, and other optional integrations.

The installer shows why each recommendation exists and its known standing-context status. It never silently installs profile/manual groups.

Reconciliation tracks ownership in the existing sidecar and may automatically remove a plugin only when all are true:

1. 100xprism previously marked it managed;
2. it is no longer selected by the active 100xprism policy;
3. the user did not independently enable/adopt it outside 100xprism.

User-owned plugins are never disabled or removed.

### 6. Hook policy

- No SessionStart hook may inject verbose update text into every session.
- Fresh installs do not enable enforcing hooks silently.
- Gate and secret-scan remain compact, reactive opt-ins.
- Lint-on-save and permission-router remain off by default.
- Hook audit reports trigger frequency, output size where observable, and whether a hook contributes startup context or only reactive latency.
- Reconciliation removes only stale 100xprism-managed hook entries; user-authored hooks survive byte-for-byte.

### 7. CLI

Keep backward compatibility while making the optimized path obvious:

```text
100xprism tokens [--print | --json] [--tool <id>] [--window <range>]
100xprism audit [path] [--json]
100xprism optimize [path] [--dry-run] [--skills must|profile|all]
100xprism slim ...   # compatibility alias for optimize
```

`audit` reports:

- indexed skills/rules and routed modules by tool;
- instruction-file bytes and estimated tokens;
- installed/managed plugins and hooks;
- duplicate/overlapping capabilities;
- exact/estimated/activity-only telemetry coverage;
- ranked, actionable savings with before/after footprint estimates.

`optimize`:

- defaults new installs to `must`;
- re-emits only adapters already present in a project;
- reconciles 100xprism-managed skills, aliases, plugins, and hooks;
- never deletes unmarked user artifacts;
- prints a before/after manifest and undo command.

Fresh install/update flows run managed reconciliation automatically. Destructive scope remains limited to files or settings entries carrying 100xprism ownership markers.

## Inputs

- User config: `~/.100xprism/config.json`.
- Project config: `<project>/.100xprism.json`.
- Source modules: `modules/<slug>/SKILL.md`.
- Tool-local session stores discovered by adapters.
- Tool-local settings/manifests for context inventory.
- CLI overrides (`PRISM_SKILLS`, `PRISM_PROFILES`, command flags).

Precedence: explicit CLI/env override → project config → user config → lean defaults.

## Outputs / side effects

- Local dashboard and text/JSON reports.
- Generated per-tool skills/rules/resolver/catalog artifacts.
- Ownership manifests for safe reconciliation.
- Managed changes to Claude plugin/hook settings only within 100xprism-owned entries.
- No telemetry upload and no remote service requirement.

## Acceptance criteria

### Measurement

- [ ] Claude and Codex fixture tests prove exact counter parsing, cache normalization, duplicate-event handling, and counter-reset handling.
- [ ] Pi fixtures cover both usage-present and activity-only session variants.
- [ ] Cursor and Antigravity never contribute invented token counts or cost.
- [ ] Every displayed total can be broken down by tool and measurement kind.
- [ ] Exact, estimate, and activity-only labels are visible in CLI text, JSON, and dashboard UI.
- [ ] Missing/corrupt source files degrade per collector without failing the entire report.
- [ ] `--json` has a versioned schema and deterministic keys suitable for automation.

### Lean context

- [ ] A fresh Claude install indexes only must-have entries plus one resolver by default.
- [ ] Fresh Cursor, Codex, and Pi project emits apply the same must-first policy.
- [ ] Non-must module bodies remain reachable on demand from the generated resolver/catalog.
- [ ] A generic route can load any routed module without restoring all aliases.
- [ ] `profile` and `all` restore wider behavior reversibly.
- [ ] CI fails if must-mode standing description footprint grows beyond a committed budget without an explicit budget update.
- [ ] CI reports all/profile/must footprint deltas for every adapter.

### Plugins and hooks

- [ ] Fresh Claude installs select only the two core plugins by default.
- [ ] Profile plugins are recommendations, not silent installs.
- [ ] Existing 100xprism-managed plugins no longer selected by policy are removed automatically.
- [ ] User-owned plugin state is preserved.
- [ ] Hooks remain opt-in and reactive; no verbose SessionStart injection is added.
- [ ] Stale managed hooks can be removed without touching user-authored hooks.

### Safety and compatibility

- [ ] Current uncommitted Pi/dashboard/pair-loop changes remain intact.
- [ ] Generated artifacts are edited only through source modules/adapters.
- [ ] macOS, Linux, and Windows adapter parity tests pass.
- [ ] `npm run check` passes.
- [ ] An end-to-end temp-home test proves install → audit → optimize → widen to all → return to must.
- [ ] A migration test proves a legacy all-skills install becomes lean while preserving user-created skills, rules, plugins, and hooks.

## Edge cases and error handling

- Missing tool data directory → report tool as not observed, not zero-cost usage.
- Tool transcript without counters → activity-only, never estimated silently.
- Unknown model pricing → preserve tokens; mark pricing coverage/fallback.
- Context compaction resets cumulative counters → begin a new delta baseline.
- Corrupt JSONL line → skip line and increment a diagnostic counter.
- Symlinked or moved project → resolve canonical path and preserve tracked-project identity.
- Existing non-generated skill/rule with a conflicting slug → skip and warn; never overwrite.
- Resolver target missing → adapter/check fails loudly.
- Invalid mode/config → fail with actionable message rather than widening to `all` silently.
- Offline operation → all local reports still work; optional pricing refresh is not required.

## Out of scope

- Reconstructing subscription invoices, credits, or provider-side billing not present locally.
- Claiming exact token usage for tools that do not expose counters.
- Measuring business ROI from Git activity.
- Installing arbitrary third-party plugins without user consent.
- Uploading prompts, transcripts, code, or telemetry.
- Supporting removed single-file adapters that cannot provide progressive disclosure.

## Implementation sequence

1. Freeze fixture-backed normalized telemetry schema and collector registry.
2. Move existing collectors behind the registry; preserve current dashboard output.
3. Add versioned `tokens --json` and a fast text path that does not perform unrelated GitHub/value scans.
4. Add static context inventory and `audit` report.
5. Change adapter defaults to must + resolver + generic route; update Python/Windows parity logic.
6. Add plugin policy groups and ownership-safe reconciliation.
7. Add hook inventory/reconciliation and remove standing SessionStart noise.
8. Turn `slim` into a compatibility alias for `optimize`.
9. Add committed footprint budgets, migration tests, docs, and full end-to-end checks.

## Open implementation note

The proposed two-plugin core is `github` plus `security-guidance`. If measured plugin metadata shows either has disproportionate resident context or duplicates first-party functionality, the implementation should reduce the core further and record the evidence in the audit output rather than preserving a plugin merely because it was initially named here.
