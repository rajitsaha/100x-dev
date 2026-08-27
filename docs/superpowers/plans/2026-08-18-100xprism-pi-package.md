# 100xprism Pi Package Implementation Plan

> **For agentic workers:** Implement task-by-task. Checkboxes track progress.

**Goal:** Ship 100xprism as a retention-filtered Pi package with gate/secret extensions and Pi pair-loop support.

**Architecture:** `emit-pi` filters modules into `.pi/skills/` + package `pi` manifest; TypeScript extensions shell out to existing Python hooks; `reviewer.py` gains a `pi` vendor.

**Tech Stack:** Python (`modules.py`), TypeScript Pi extensions, existing hooks/pair-loop.

## Global Constraints

- Modules remain source of truth; no Pi forks in SKILL bodies
- Pi retention ON by default; plugins.json stays Claude-only
- Different provider required for pair-loop; $5 budget default when coder=pi
- v1 extensions shell out to Python hooks (no logic drift)

---

## Task 1: emit-pi

- [ ] Add `cmd_emit_pi` writing filtered skills to `.pi/skills/`, prompts for alias-only slash commands, AGENTS.md if missing, resolver catalog
- [ ] Wire CLI subcommand + `install-project.sh`
- [ ] Tests: retention count < 68; alias prompts only when name differs

## Task 2: package.json + extensions

- [ ] `pi` key + `pi-package` keyword; include `pi/` in `files`
- [ ] `pi/extensions/gate-secret.ts` — tool_call block via Python hooks
- [ ] `pi/extensions/retention.ts` — filter resolver from discover/index
- [ ] Package-level skills/prompts dirs populated by emit or committed generated layout for `pi install`

## Task 3: docs

- [ ] USAGE.md Pi section
- [ ] AGENTS.md mention Pi

## Task 4: Phase 2 loop

- [ ] `scripts/adapters/pi.py` + register in ADAPTERS
- [ ] `reviewer.py` vendor `pi` + config providers/models + $5 default
- [ ] Update `modules/pair-loop/SKILL.md`

## Task 5: verify

- [ ] `npm run check`
- [ ] Unit tests green
