# External Skill Packs — design

> Status: implemented and shipped in PR #103. This document describes the design as
> built, including corrections from three review rounds; it is the source of truth where
> the implementation plan disagrees.
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
   report that platform as unavailable and print `install.cli.hint`. "Unavailable" is
   not a stored value — it is represented by the platform simply carrying no obligation
   (see the state shape below), because there is nothing there to reverse.

State records *how* each platform was installed, so removal knows what it is entitled
to reverse. Crucially this is a **set of obligations per platform**, not one status:
`installed` (we inserted config we can reverse), `cli` (the pack's own CLI wrote files
we do not track), and `manual` (the user ran something themselves) are **independent
mutations that can accumulate on the same platform**. Installing directly and later
re-installing through the pack's CLI produces both, and each owes its own removal
transition. `unavailable` is the absence of obligation and is never stored.

**Ownership is tracked per entry, not per platform.** Recording a platform as
`installed` is not sufficient: if the user already had the plugin listed (enabled or
explicitly disabled), 100xprism did not add it and must not remove it. State
therefore records the exact `enabledPlugins` keys and the marketplace name that this
install actually inserted. Removal reverses only those, and only when nothing else
still references them. This mirrors the managed-set rule in `sync_plugins.py`.

State also copies each platform's declared `uninstall` commands at install time, so
a pack dropped from the registry is still reversible.

**The ownership record — not the status label — decides what removal reverses.** A
platform's status can legitimately change between installs: an `add` that used the
per-platform path records `claude-code: installed`, and a later `add` with the pack's
CLI available records `claude-code: cli`. If removal keyed off that label it would skip
the reversal and orphan the entries we inserted. So removal always reverses `owned`
when it is non-empty, whatever the label says, and the label only decides what guidance
the user is given.

**Re-installing only ever adds obligation.** A repeat `add` unions the new obligations
into the record rather than replacing it. Two failure modes make this necessary: a
retry that fails must not erase an obligation an earlier attempt really incurred, and a
retry that takes a *different* install path must not overwrite the path already taken.
An earlier ranked-status design was wrong here — ranking implies a total order, and
these obligations are independent.

**Removal checkpoints as it goes**, at both levels. Obligations are discharged one at a
time and each is dropped from the record as it completes; within a platform's declared
`uninstall` array, each command is dropped as it succeeds. A failure partway through
therefore leaves an accurate record of what remains, and a retry resumes rather than
repeating: it will not re-reverse config the user may have restored in the
meantime, nor re-run inverse commands that already succeeded.

**Writes are atomic, and their order is deliberate.** Each file is written to a temp
file and `os.replace`d, so an interrupted run cannot truncate the user's `settings.json`.
Settings are written *before* the state sidecar: dying between the two leaves config we
inserted without a record of owning it — a leak, recoverable by hand. The reverse order
would leave a record claiming ownership of entries we never inserted, and removal would
then delete the user's own configuration. Leak over wrongful deletion, always.

The opt-in model means there is no first-run seeding step. `sync_plugins.py` seeds a
managed set because its plugins install unconditionally and predate the state file;
a pack only ever enters state because the user ran `/pack add`, so an absent entry
unambiguously means "not installed by us."

## Detection

Read-only. Runs against the git toplevel of the current directory, falling back to
the current directory itself when it is not inside a git repository. The predicate is
an OR over `files`, `env`, and `contains`.

**Only exact paths at the project root — no recursive globs.** Detection runs on
every install and update, so it must stay cheap in large repositories.

Surfaced in exactly two places:

- One suggestion line at the end of `install.sh` / `update.sh`. It must sit in each
  script's final section, **not** inside `install_plugins` — that function runs only
  when the user selects both Claude Code and the optional plugins component, so
  Cursor-only, Codex-only, and modules-without-plugins installs would otherwise never
  see a suggestion.
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

Coverage is split by concern across `test/packs-schema.test.js`,
`packs-detect.test.js`, `packs-claude.test.js`, `packs-install-paths.test.js`,
`packs-module.test.js`, and `packs-lifecycle.test.js`:

- Schema parsing and rejection of malformed packs, against a **temporary** registry.
  Tests must never mutate the tracked `packs/packs.json` — `node --test` runs files
  concurrently, so an intentionally-malformed intermediate state would race with the
  suites that read the real registry.
- Detection true/false against fixture project directories created in temp dirs at
  test time. Fixtures must **not** live inside this repository: `project_root()`
  resolves the git toplevel, so a fixture committed under `scripts/fixtures/` would
  resolve to the 100xprism root and never match.
- Detection from a subdirectory of a git repo resolves to that repo's toplevel.
- `add` / `remove` reconciliation against a temporary `HOME`.
- Idempotency — a second `add` is a no-op.
- Ownership — a plugin the user already had is neither flipped on `add` nor deleted
  on `remove`.
- Prune-on-drop — a pack removed from `packs.json` is removed from settings, and
  `remove` still works after the pack leaves the registry.
- Malformed `settings.json` is preserved, never overwritten.

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
