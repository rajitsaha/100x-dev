# External Skill Packs — design

> Status: approved design, not yet implemented
> Date: 2026-08-03
> First consumer: [databricks/databricks-agent-skills](https://github.com/databricks/databricks-agent-skills)

## Problem

100xprism ships 67 first-party modules and pulls in 14 third-party Claude Code
plugins via `plugins/plugins.json`. That plugin list is always-on, Claude-Code-only,
and unconditional: every user carries every plugin.

Some skill collections are valuable but only to a subset of users. Databricks'
30+ agent skills are the motivating case — indispensable on a Databricks project,
pure token cost everywhere else. Adding them to `plugins.json` would tax all users;
hand-writing Databricks knowledge into `modules/` would duplicate a repo that is
already maintained, versioned, and CI-enforced upstream.

## Goal

A reusable mechanism for declaring optional third-party **skill packs** that users
opt into, with Databricks as the first and only shipped pack.

## Non-goals

- Cloning or vendoring upstream skill content. Packs orchestrate the upstream's own
  installers; 100xprism never renders third-party `SKILL.md` files.
- Per-project sandboxing. Claude Code plugins and Cursor extensions install into
  `~/.claude/` and `~/.cursor/`, so a pack cannot be scoped to a single repo.
  Detection can recommend; it cannot isolate.
- Auto-installing on detection. Global state is never mutated because of the
  directory the user happens to be in.
- A general marketplace. One pack ships. The registry proves the mechanism.

## Architecture

Four new pieces, three touch points.

### New

| Path | Role |
| --- | --- |
| `packs/packs.json` | Declarative registry of available packs. Added to `package.json` `files`. |
| `adapters/lib/packs.py` | Deterministic helper. Subcommands: `status`, `detect`, `add <slug>`, `remove <slug>`, `sync`. |
| `modules/pack/SKILL.md` | The `/pack` slash command. Routes arguments to `packs.py`, renders output. |
| `~/.claude/.100xprism-packs.json` | Managed-state sidecar, mirroring the existing `.100xprism-plugins.json` convention. |

### Touched

- `adapters/claude-code.sh` (`install_plugins`, ~L145) and `update.sh` (~L216, ~L294) —
  a `packs.py sync` call beside each existing `sync_plugins.py` call, then a
  non-mutating `packs.py detect` suggestion line.
- `lib/uninstall.js` — reverse packs installed through the managed Claude Code path.
- `package.json` — add `packs/` to `files`; bump the module count in `description`
  from 67 to 68. `scripts/meta-check.py` enforces that this count, the README's
  counts, and the parsed module total all agree, so the same change must update
  the README's "modules" and "slash commands" mentions (27 → 28).

### Boundary

`packs.py` never talks to the agent. For Claude Code it edits `settings.json`
(`extraKnownMarketplaces` + `enabledPlugins`) using the same primitives
`sync_plugins.py` already uses. For other platforms it runs a shell command, or —
where the upstream installer is an in-agent slash command with no shell equivalent
(Cursor's `/add-plugin`) — prints the command for the user to run and records that
platform as `manual` rather than `installed`.

The `/pack` module contributes no decisions. It selects a subcommand, renders the
helper's JSON, and tells the user to restart their agent.

## Pack schema

`packs/packs.json`:

```json
{
  "schema": 1,
  "packs": {
    "databricks": {
      "title": "Databricks Agent Skills",
      "description": "30+ skills — Unity Catalog, Asset Bundles, Lakeflow, model serving, vector search.",
      "source": "https://github.com/databricks/databricks-agent-skills",
      "detect": {
        "files": ["databricks.yml", "databricks.yaml"],
        "env": ["DATABRICKS_HOST"],
        "contains": [
          { "file": "requirements.txt", "pattern": "^databricks-" },
          { "file": "pyproject.toml",   "pattern": "databricks-" }
        ]
      },
      "install": {
        "preferred": "cli",
        "cli": {
          "requires": "databricks",
          "command": "databricks aitools install",
          "covers": ["claude-code", "cursor", "codex"],
          "hint": "Install the Databricks CLI: https://docs.databricks.com/dev-tools/cli/install.html"
        },
        "claude-code": {
          "marketplace": {
            "name": "databricks-agent-skills",
            "source": { "source": "github", "repo": "databricks/databricks-agent-skills" }
          },
          "plugins": ["databricks@databricks-agent-skills"]
        },
        "codex": {
          "commands": [
            "codex plugin marketplace add databricks/databricks-agent-skills",
            "codex plugin add databricks"
          ]
        },
        "cursor": { "manual": ["/add-plugin databricks"] }
      }
    }
  }
}
```

Identifiers above are taken verbatim from the upstream README, not inferred.

Each per-platform block may also carry an optional `uninstall` array of shell
commands. The `databricks` pack leaves it unset: the upstream README documents no
uninstall path, and inventing one is worse than printing guidance. If a verified
command exists at implementation time, add it then.

### Install resolution

1. If `install.preferred` is `cli` and `install.cli.requires` resolves on `PATH`,
   run `install.cli.command`. One command covers every platform in `covers`.
   This is what makes Cursor work, since Cursor has no shell-invocable installer.
2. Otherwise fall back to per-platform blocks: `claude-code` is performed directly
   by `packs.py`, `codex` shells out, `cursor` is printed for the user.
3. If a platform has no usable path at all — no CLI binary and no per-platform block —
   report that platform as `unavailable` and print `install.cli.hint`.

State records *how* each platform was installed (`installed` | `cli` | `manual`),
so removal knows what it is entitled to reverse.

## Detection

Read-only. Runs against the git toplevel of the current directory, falling back to
the current directory itself when it is not inside a git repository. The predicate is
an OR over `files`, `env`, and `contains`.

**Only exact paths at the project root — no recursive globs.** Detection runs on
every install and update, so it must stay cheap in large repositories.

Surfaced in exactly two places:

- One suggestion line at the end of `install.sh` / `update.sh`.
- On demand, via bare `/pack`.

Detection never installs anything.

## The `/pack` module

`modules/pack/SKILL.md` frontmatter:

```yaml
---
name: pack
description: Install optional third-party skill packs that 100xprism doesn't ship by default — "add the Databricks skills", "what packs are available", "is there a pack for X".
category: engineering
tier: on-demand
model: haiku
slash_command: /pack
---
```

`tier: on-demand` keeps it free until invoked. `model: haiku` matches the mechanical
nature of the work.

| Invocation | Helper call |
| --- | --- |
| `/pack` | `packs.py status` — declared packs, install state, detection hits |
| `/pack add <slug>` | `packs.py add <slug>` |
| `/pack remove <slug>` | `packs.py remove <slug>` |
| `/pack detect` | `packs.py detect` |

Path resolution follows the idiom already used by `modules/gate/SKILL.md`
(`python3 ~/100xprism/adapters/lib/packs.py …`), with an added guard for
npm-global installs where `~/100xprism` does not exist. `/gate` carries that gap
today; `/pack` fixes it rather than propagating it.

### Trigger-overlap risk

`/connect` is described as "Connect, authenticate, and verify any SaaS CLI tool."
A pack install that shells out to the `databricks` CLI sits close to that surface.
The two descriptions must stay disjoint — `/connect` authenticates a CLI you already
have; `/pack` installs skills you do not — and `test/trigger-overlap.test.js` must
stay green.

## Removal

Deliberately asymmetric. `/pack remove` reverses only what 100xprism owns:
the `settings.json` marketplace and plugin entries tracked in
`.100xprism-packs.json`.

For a platform recorded as `cli` or `manual`, `/pack remove` prints the upstream
removal steps and stops. For a platform recorded as `installed` via per-platform
shell commands (Codex), it runs the inverse command when the pack declares one and
otherwise prints guidance. It does **not** delete files under
`~/.claude/skills/` written by a third-party CLI — 100xprism does not know what else
that CLI wrote or what the user has edited since. `lib/uninstall.js` follows the
same rule.

The accepted cost: `/pack remove databricks` after a CLI install leaves skills on
disk and says so plainly. This is preferred over a destructive delete on a directory
100xprism does not own.

## Tests and CI

Precedents: `test/sync-plugins.test.js`, `test/update-plugins.test.js`,
`test/uninstall.test.js`, `test/meta-check.test.js`.

`test/packs.test.js` covers:

- Schema parsing and rejection of malformed packs.
- Detection true/false against fixture project directories under `scripts/fixtures/`.
- `add` / `remove` reconciliation against a temporary `HOME`.
- Idempotency — a second `add` is a no-op.
- Prune-on-drop — a pack removed from `packs.json` is removed from settings.
- First-run state seeding, mirroring `sync_plugins.py`'s rule that the managed set is
  seeded from the current intersection and nothing is removed on the first run.

Shell execution goes through an injected runner, so `databricks aitools install` is
stubbed. No test touches the network.

`scripts/meta-check.py` gains: `packs.json` parses; every pack declares `title`,
`description`, `source`, `detect`, and `install`; no unknown platform keys appear;
and the module/slash-command count assertions move to 68 and 28.

`test/modules-frontmatter.test.js` picks up `modules/pack/SKILL.md` automatically.

## Decision record

| Decision | Chosen | Rejected |
| --- | --- | --- |
| Scope | Generalized skill-pack mechanism | One-off Databricks bundling; deepening native `/db` |
| Install model | Orchestrate upstream installers | Clone + emit through `modules.py`; hybrid |
| Activation | Opt-in, detection suggests | Auto-install on detection; always-on |
| Registry | Separate `packs/packs.json` | Extending `plugins.json`; migrating it |
| Surface | Slash-command module only | CLI subcommands; both |
| Removal | Reverse only what we own | Delete third-party skill directories |
| Shipped packs | One (`databricks`) | Seed several to prove generality |
