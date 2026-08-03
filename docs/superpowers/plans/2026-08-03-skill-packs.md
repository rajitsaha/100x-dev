# External Skill Packs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an opt-in mechanism for installing third-party skill packs, with `databricks` as the only shipped pack.

**Architecture:** A declarative registry (`packs/packs.json`) is read by a deterministic Python helper (`adapters/lib/packs.py`) that detects matching projects, installs packs by orchestrating each upstream's own installer, and tracks what it installed in a sidecar state file. A thin `/pack` slash-command module shells out to the helper; it makes no decisions. Nothing installs automatically.

**Tech Stack:** Python 3 (stdlib only, matching `adapters/lib/*.py`), Node's built-in `node:test` runner, bash adapters.

**Spec:** `docs/superpowers/specs/2026-08-03-skill-packs-databricks-design.md`

## Global Constraints

- Python helpers use the **standard library only** — no new dependencies. `package.json` has zero runtime deps and must keep zero.
- `packs.py` **never** deletes files under `~/.claude/skills/` or any third-party skill directory. It reverses only `settings.json` entries it wrote.
- Detection is **read-only** and matches **only exact paths at the project root** — no recursive globs, no directory walking.
- Detection **never** triggers an install.
- Supported platform keys are exactly `claude-code`, `codex`, `cursor`.
- State-file semantics mirror `adapters/lib/sync_plugins.py`: never flip a value the user set; on first run, seed and remove nothing.
- Tests must not touch the network. Shell execution is stubbed via the `PRISM_PACKS_RUNNER_LOG` and `PRISM_PACKS_WHICH` environment variables defined in Task 4.
- `python3 scripts/meta-check.py` and `node --test` must both pass before every commit. The repo has a gate-on-commit hook; run `/gate` then `python3 ~/100xprism/hooks/gate-pass.py` in its own shell call before committing.

---

### Task 1: Registry file and schema validation

Creates the declarative registry and the CI check that keeps it honest. No behavior yet — this task exists so a reviewer can reject the schema before any code depends on it.

**Files:**
- Create: `packs/packs.json`
- Modify: `scripts/meta-check.py` (add `check_packs()`, call it from `main()`)
- Modify: `package.json` (add `"packs/"` to `files`)
- Test: `test/packs-schema.test.js`

**Interfaces:**
- Consumes: nothing.
- Produces: `packs/packs.json` with top-level keys `schema` (int, must be `1`) and `packs` (object keyed by slug). `scripts/meta-check.py` gains `check_packs() -> int` returning the pack count.

- [ ] **Step 1: Write the failing test**

Create `test/packs-schema.test.js`:

```javascript
'use strict'

// Verifies packs/packs.json parses and that scripts/meta-check.py rejects
// malformed pack declarations (unknown platform keys, missing required fields,
// nested detect paths, uncompilable regexes).

const { test } = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

const REPO = path.resolve(__dirname, '..')
const PACKS = path.join(REPO, 'packs', 'packs.json')

function metaCheck() {
  return spawnSync('python3', [path.join(REPO, 'scripts', 'meta-check.py')], {
    cwd: REPO, encoding: 'utf8',
  })
}

function withPacks(mutate, fn) {
  const original = fs.readFileSync(PACKS, 'utf8')
  const data = JSON.parse(original)
  mutate(data)
  fs.writeFileSync(PACKS, JSON.stringify(data, null, 2) + '\n')
  try { return fn() } finally { fs.writeFileSync(PACKS, original) }
}

test('the shipped registry is valid', () => {
  const data = JSON.parse(fs.readFileSync(PACKS, 'utf8'))
  assert.equal(data.schema, 1)
  assert.ok(data.packs.databricks, 'databricks pack declared')
  assert.equal(metaCheck().status, 0)
})

test('rejects an unknown install platform key', () => {
  const r = withPacks(
    (d) => { d.packs.databricks.install.antigravity = { manual: ['x'] } },
    metaCheck,
  )
  assert.equal(r.status, 1)
  assert.match(r.stderr, /unknown install key 'antigravity'/)
})

test('rejects a missing required field', () => {
  const r = withPacks((d) => { delete d.packs.databricks.source }, metaCheck)
  assert.equal(r.status, 1)
  assert.match(r.stderr, /missing required key `source`/)
})

test('rejects a nested detect path', () => {
  const r = withPacks(
    (d) => { d.packs.databricks.detect.files.push('conf/databricks.yml') },
    metaCheck,
  )
  assert.equal(r.status, 1)
  assert.match(r.stderr, /detect path .* must be a bare filename/)
})

test('rejects an uncompilable detect pattern', () => {
  const r = withPacks(
    (d) => { d.packs.databricks.detect.contains[0].pattern = '([' },
    metaCheck,
  )
  assert.equal(r.status, 1)
  assert.match(r.stderr, /pattern invalid/)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test test/packs-schema.test.js`
Expected: FAIL — `ENOENT` reading `packs/packs.json`.

- [ ] **Step 3: Create the registry**

Create `packs/packs.json`. Identifiers below are taken verbatim from the upstream README — do not alter them.

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
          { "file": "pyproject.toml", "pattern": "databricks-" }
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

- [ ] **Step 4: Add the validator to meta-check**

In `scripts/meta-check.py`, add this function after `check_plugins()`:

```python
PACK_PLATFORMS = {"claude-code", "codex", "cursor"}


def check_packs() -> int:
    """Validate packs/packs.json — schema version, required keys, platform names."""
    data = json.loads((REPO / "packs" / "packs.json").read_text())
    if data.get("schema") != 1:
        fail(f"packs.json: unsupported `schema` {data.get('schema')!r} (expected 1)")

    packs = data.get("packs", {})
    for slug, pack in packs.items():
        for key in ("title", "description", "source", "detect", "install"):
            if not pack.get(key):
                fail(f"packs.json: '{slug}' missing required key `{key}`")

        install = pack.get("install", {})
        for key in install:
            if key not in PACK_PLATFORMS | {"preferred", "cli"}:
                fail(f"packs.json: '{slug}' unknown install key '{key}'")

        preferred = install.get("preferred")
        if preferred and preferred != "cli" and preferred not in PACK_PLATFORMS:
            fail(f"packs.json: '{slug}' install.preferred='{preferred}' is not 'cli' or a platform")

        cli = install.get("cli")
        if cli:
            for key in ("requires", "command", "covers"):
                if not cli.get(key):
                    fail(f"packs.json: '{slug}' install.cli missing `{key}`")
            for platform in cli.get("covers", []):
                if platform not in PACK_PLATFORMS:
                    fail(f"packs.json: '{slug}' install.cli.covers has unknown platform '{platform}'")

        detect = pack.get("detect", {})
        for key in detect:
            if key not in {"files", "env", "contains"}:
                fail(f"packs.json: '{slug}' unknown detect key '{key}'")
        # Detection is root-only by design (see spec): reject anything path-like so a
        # nested path can never turn into a directory walk.
        paths = list(detect.get("files", [])) + [e.get("file", "") for e in detect.get("contains", [])]
        for p in paths:
            if "/" in p or "\\" in p or p in ("", ".", ".."):
                fail(f"packs.json: '{slug}' detect path '{p}' must be a bare filename")
        for entry in detect.get("contains", []):
            if not entry.get("file") or not entry.get("pattern"):
                fail(f"packs.json: '{slug}' detect.contains entry needs `file` and `pattern`")
                continue
            try:
                re.compile(entry["pattern"])
            except re.error as exc:
                fail(f"packs.json: '{slug}' detect.contains pattern invalid — {exc}")

    ok(f"packs[] entries: {len(packs)}")
    return len(packs)
```

In `main()`, add the call directly after `counts["plugins"] = check_plugins()`:

```python
    check_packs()
```

- [ ] **Step 5: Add `packs/` to the npm payload**

In `package.json`, inside `files`, add `"packs/",` immediately after `"modules/",`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `node --test test/packs-schema.test.js && python3 scripts/meta-check.py`
Expected: 5 tests PASS; meta-check prints `packs[] entries: 1` and `all checks passed ✓`.

- [ ] **Step 7: Commit**

```bash
git add packs/packs.json scripts/meta-check.py package.json test/packs-schema.test.js
git commit -m "feat(packs): add pack registry and schema validation"
```

---

### Task 2: Detection engine and read-only subcommands

**Files:**
- Create: `adapters/lib/packs.py`
- Create: `scripts/fixtures/packs/databricks-yml/databricks.yml` (empty file)
- Create: `scripts/fixtures/packs/requirements/requirements.txt`
- Create: `scripts/fixtures/packs/plain/README.md`
- Test: `test/packs-detect.test.js`

**Interfaces:**
- Consumes: `packs/packs.json` from Task 1.
- Produces:
  - `load_registry(path: Path) -> dict`
  - `project_root(start: Path) -> Path`
  - `pack_matches(pack: dict, root: Path, env: Mapping[str, str]) -> bool`
  - CLI: `packs.py detect [--project DIR] [--packs FILE] [--json]`
  - CLI: `packs.py status [--project DIR] [--packs FILE] [--settings FILE] [--state FILE] [--json]`
  - `--json` emits `{"packs": [{"slug", "title", "detected", "platforms"}]}`. `platforms` is `{}` until Task 3.

- [ ] **Step 1: Write the failing test**

Create `test/packs-detect.test.js`:

```javascript
'use strict'

// Verifies adapters/lib/packs.py detection: file, env, and content predicates
// match at the project root only, and never below it.

const { test } = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const REPO = path.resolve(__dirname, '..')
const SCRIPT = path.join(REPO, 'adapters', 'lib', 'packs.py')
const FIXTURES = path.join(REPO, 'scripts', 'fixtures', 'packs')

function detect(projectDir, env = {}) {
  const r = spawnSync('python3', [SCRIPT, 'detect', '--project', projectDir, '--json'], {
    encoding: 'utf8',
    env: { ...process.env, DATABRICKS_HOST: '', ...env },
  })
  assert.equal(r.status, 0, r.stderr)
  return JSON.parse(r.stdout).packs
}

function detectedSlugs(projectDir, env) {
  return detect(projectDir, env).filter((p) => p.detected).map((p) => p.slug)
}

test('matches on a root marker file', () => {
  assert.deepEqual(detectedSlugs(path.join(FIXTURES, 'databricks-yml')), ['databricks'])
})

test('matches on file content', () => {
  assert.deepEqual(detectedSlugs(path.join(FIXTURES, 'requirements')), ['databricks'])
})

test('matches on an environment variable', () => {
  assert.deepEqual(
    detectedSlugs(path.join(FIXTURES, 'plain'), { DATABRICKS_HOST: 'https://x.databricks.com' }),
    ['databricks'],
  )
})

test('does not match an unrelated project', () => {
  assert.deepEqual(detectedSlugs(path.join(FIXTURES, 'plain')), [])
})

test('does not match a marker file nested below the root', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pk-'))
  fs.mkdirSync(path.join(dir, 'conf'))
  fs.writeFileSync(path.join(dir, 'conf', 'databricks.yml'), '')
  assert.deepEqual(detectedSlugs(dir), [], 'nested marker must not match')
})

test('status lists every declared pack, detected or not', () => {
  const r = spawnSync(
    'python3',
    [SCRIPT, 'status', '--project', path.join(FIXTURES, 'plain'), '--json'],
    { encoding: 'utf8', env: { ...process.env, DATABRICKS_HOST: '' } },
  )
  assert.equal(r.status, 0, r.stderr)
  const packs = JSON.parse(r.stdout).packs
  assert.equal(packs.length, 1)
  assert.equal(packs[0].slug, 'databricks')
  assert.equal(packs[0].detected, false)
})
```

- [ ] **Step 2: Create the fixtures**

```bash
mkdir -p scripts/fixtures/packs/databricks-yml scripts/fixtures/packs/requirements scripts/fixtures/packs/plain
touch scripts/fixtures/packs/databricks-yml/databricks.yml
printf 'databricks-sql-connector==3.0.0\n' > scripts/fixtures/packs/requirements/requirements.txt
printf '# plain project fixture — matches no pack\n' > scripts/fixtures/packs/plain/README.md
```

- [ ] **Step 3: Run test to verify it fails**

Run: `node --test test/packs-detect.test.js`
Expected: FAIL — `can't open file .../adapters/lib/packs.py`.

- [ ] **Step 4: Write the helper**

Create `adapters/lib/packs.py`:

```python
#!/usr/bin/env python3
"""Manage optional third-party skill packs declared in packs/packs.json.

Packs are opt-in. Nothing here installs anything unless the user explicitly runs
`add`, and detection is strictly read-only: it reports which declared packs look
relevant to the current project and stops there.

Subcommands:
  detect  — which declared packs match the current project (read-only)
  status  — every declared pack, its detection result, and its install state
  add     — install a pack (Task 3/4)
  remove  — reverse what we installed (Task 3/4)
  sync    — re-apply opted-in packs; drop packs no longer declared (Task 3)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Mapping

REPO = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY = REPO / "packs" / "packs.json"
PLATFORMS = ("claude-code", "codex", "cursor")


def load_registry(path: Path) -> dict:
    data = json.loads(path.read_text())
    if data.get("schema") != 1:
        raise SystemExit(f"packs.py: unsupported registry schema {data.get('schema')!r}")
    return data.get("packs", {})


def project_root(start: Path) -> Path:
    """Git toplevel of `start`, or `start` itself when not in a repository."""
    try:
        r = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=False,
        )
    except OSError:
        return start
    if r.returncode == 0 and r.stdout.strip():
        return Path(r.stdout.strip())
    return start


def pack_matches(pack: dict, root: Path, env: Mapping[str, str]) -> bool:
    """OR over files / env / contains. Root-only: never descends into subdirectories."""
    detect = pack.get("detect", {})
    for name in detect.get("files", []):
        if (root / name).is_file():
            return True
    for var in detect.get("env", []):
        if env.get(var):
            return True
    for entry in detect.get("contains", []):
        target = root / entry["file"]
        if not target.is_file():
            continue
        try:
            text = target.read_text(errors="replace")
        except OSError:
            continue
        if re.search(entry["pattern"], text, re.MULTILINE):
            return True
    return False


def describe(packs: dict, root: Path, env: Mapping[str, str], state: dict) -> list[dict]:
    installed = state.get("packs", {})
    return [
        {
            "slug": slug,
            "title": pack.get("title", slug),
            "description": pack.get("description", ""),
            "source": pack.get("source", ""),
            "detected": pack_matches(pack, root, env),
            "platforms": installed.get(slug, {}).get("platforms", {}),
        }
        for slug, pack in sorted(packs.items())
    ]


def load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def state_path(args) -> Path:
    if args.state:
        return Path(args.state)
    settings = Path(args.settings) if args.settings else Path.home() / ".claude" / "settings.json"
    return settings.parent / ".100xprism-packs.json"


def render(rows: list[dict]) -> str:
    lines = []
    for row in rows:
        marks = []
        if row["platforms"]:
            marks.append("installed: " + ", ".join(f"{k}={v}" for k, v in sorted(row["platforms"].items())))
        elif row["detected"]:
            marks.append(f"detected — run `/pack add {row['slug']}` to install")
        else:
            marks.append("not installed")
        lines.append(f"  {row['slug']:<14} {row['title']}\n    {'; '.join(marks)}")
    return "\n".join(lines) if lines else "  (no packs declared)"


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="packs.py")
    ap.add_argument("command", choices=["detect", "status", "add", "remove", "sync"])
    ap.add_argument("slug", nargs="?", default="")
    ap.add_argument("--packs", default=str(DEFAULT_REGISTRY))
    ap.add_argument("--project", default=".")
    ap.add_argument("--settings", default="")
    ap.add_argument("--state", default="")
    ap.add_argument("--json", action="store_true")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    packs = load_registry(Path(args.packs))
    root = project_root(Path(args.project).resolve())
    state = load_state(state_path(args))
    rows = describe(packs, root, os.environ, state)

    if args.command == "detect":
        rows = [r for r in rows if r["detected"]]
    if args.command in ("detect", "status"):
        print(json.dumps({"packs": rows}, indent=2) if args.json else render(rows))
        return 0

    raise SystemExit(f"packs.py: '{args.command}' not implemented yet")


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `node --test test/packs-detect.test.js`
Expected: 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add adapters/lib/packs.py scripts/fixtures/packs test/packs-detect.test.js
git commit -m "feat(packs): add detection engine and read-only detect/status"
```

---

### Task 3: Claude Code install, removal, and state reconciliation

**Files:**
- Modify: `adapters/lib/packs.py` (add install/remove/sync for the `claude-code` platform)
- Test: `test/packs-claude.test.js`

**Interfaces:**
- Consumes: `load_registry`, `pack_matches`, `state_path`, `load_state` from Task 2.
- Produces:
  - `claude_install(pack: dict, settings: dict) -> bool`
  - `claude_remove(pack: dict, settings: dict) -> list[str]`
  - `write_json(path: Path, data: dict) -> None`
  - State file shape: `{"schema": 1, "packs": {"<slug>": {"platforms": {"<platform>": "installed"|"cli"|"manual"|"unavailable"}}}}`
- Task 4 extends `add`/`remove` with the CLI and non-Claude paths; this task wires the Claude Code path only, so `add` records `claude-code` and nothing else.

- [ ] **Step 1: Write the failing test**

Create `test/packs-claude.test.js`:

```javascript
'use strict'

// Verifies adapters/lib/packs.py reconciles settings.json for the claude-code
// platform: adds marketplace + plugins on `add`, is idempotent, never flips a
// value the user set, reverses only what it wrote on `remove`, and prunes on sync.

const { test } = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const REPO = path.resolve(__dirname, '..')
const SCRIPT = path.join(REPO, 'adapters', 'lib', 'packs.py')
const REGISTRY = path.join(REPO, 'packs', 'packs.json')
const PLUGIN = 'databricks@databricks-agent-skills'

function setup(settings = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pkc-'))
  const settingsFile = path.join(dir, 'settings.json')
  fs.writeFileSync(settingsFile, JSON.stringify(settings))
  return { dir, settingsFile, project: dir }
}

function run(ctx, argv, opts = {}) {
  const registry = opts.registry || REGISTRY
  const r = spawnSync('python3', [
    SCRIPT, ...argv,
    '--settings', ctx.settingsFile,
    '--project', ctx.project,
    '--packs', registry,
  ], {
    encoding: 'utf8',
    // Force the per-platform path; Task 4 covers the CLI path.
    env: { ...process.env, PRISM_PACKS_WHICH: '{"databricks": false}' },
  })
  assert.equal(r.status, 0, r.stderr)
  return r
}

const settingsOf = (ctx) => JSON.parse(fs.readFileSync(ctx.settingsFile, 'utf8'))
const stateOf = (ctx) => JSON.parse(fs.readFileSync(path.join(ctx.dir, '.100xprism-packs.json'), 'utf8'))

test('add wires the marketplace and enables the plugin', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'])
  const s = settingsOf(ctx)
  assert.equal(s.enabledPlugins[PLUGIN], true)
  assert.ok(s.extraKnownMarketplaces['databricks-agent-skills'])
  assert.equal(stateOf(ctx).packs.databricks.platforms['claude-code'], 'installed')
})

test('add is idempotent', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'])
  const first = settingsOf(ctx)
  run(ctx, ['add', 'databricks'])
  assert.deepEqual(settingsOf(ctx), first)
})

test('add never flips a plugin the user explicitly disabled', () => {
  const ctx = setup({ enabledPlugins: { [PLUGIN]: false } })
  run(ctx, ['add', 'databricks'])
  assert.equal(settingsOf(ctx).enabledPlugins[PLUGIN], false)
})

test('remove reverses only what we wrote', () => {
  const ctx = setup({ enabledPlugins: { 'user-only@m': true } })
  run(ctx, ['add', 'databricks'])
  run(ctx, ['remove', 'databricks'])
  const s = settingsOf(ctx)
  assert.equal(PLUGIN in s.enabledPlugins, false, 'our plugin removed')
  assert.equal(s.enabledPlugins['user-only@m'], true, 'user plugin preserved')
  assert.equal('databricks-agent-skills' in (s.extraKnownMarketplaces || {}), false)
  assert.equal('databricks' in stateOf(ctx).packs, false)
})

test('remove keeps a marketplace another enabled plugin still needs', () => {
  const ctx = setup({ enabledPlugins: { 'other@databricks-agent-skills': true } })
  run(ctx, ['add', 'databricks'])
  run(ctx, ['remove', 'databricks'])
  const s = settingsOf(ctx)
  assert.ok(s.extraKnownMarketplaces['databricks-agent-skills'], 'marketplace still in use')
})

test('sync re-applies an opted-in pack and prunes one no longer declared', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'])

  // Re-applies after the user hand-deletes the entry.
  const s = settingsOf(ctx)
  delete s.enabledPlugins[PLUGIN]
  fs.writeFileSync(ctx.settingsFile, JSON.stringify(s))
  run(ctx, ['sync'])
  assert.equal(settingsOf(ctx).enabledPlugins[PLUGIN], true, 're-applied')

  // Pack dropped from the registry is pruned.
  const empty = path.join(ctx.dir, 'empty-packs.json')
  fs.writeFileSync(empty, JSON.stringify({ schema: 1, packs: {} }))
  run(ctx, ['sync'], { registry: empty })
  assert.equal(PLUGIN in settingsOf(ctx).enabledPlugins, false, 'pruned')
})

test('add rejects an unknown slug', () => {
  const ctx = setup()
  const r = spawnSync('python3', [
    SCRIPT, 'add', 'nope', '--settings', ctx.settingsFile, '--project', ctx.project,
  ], { encoding: 'utf8' })
  assert.equal(r.status, 1)
  assert.match(r.stderr, /unknown pack 'nope'/)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test test/packs-claude.test.js`
Expected: FAIL — `packs.py: 'add' not implemented yet`.

- [ ] **Step 3: Implement the Claude Code path**

In `adapters/lib/packs.py`, add these functions after `load_state`:

```python
def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def claude_install(pack: dict, settings: dict) -> bool:
    """Add the pack's marketplace + plugins to settings.json. Idempotent.

    Uses setdefault so a plugin the user explicitly disabled is never flipped back
    on — the same rule sync_plugins.py follows.
    """
    block = pack.get("install", {}).get("claude-code")
    if not block:
        return False
    marketplace = block.get("marketplace")
    if marketplace:
        settings.setdefault("extraKnownMarketplaces", {})[marketplace["name"]] = {
            "source": marketplace["source"]
        }
    enabled = settings.setdefault("enabledPlugins", {})
    for plugin in block.get("plugins", []):
        enabled.setdefault(plugin, True)
    return True


def claude_remove(pack: dict, settings: dict) -> list[str]:
    """Drop the pack's plugins, and its marketplace if nothing else references it."""
    block = pack.get("install", {}).get("claude-code") or {}
    enabled = settings.setdefault("enabledPlugins", {})
    removed = [p for p in block.get("plugins", []) if enabled.pop(p, None) is not None]

    marketplace = block.get("marketplace")
    if marketplace:
        name = marketplace["name"]
        still_used = any(p.rsplit("@", 1)[-1] == name for p in enabled)
        if not still_used:
            settings.get("extraKnownMarketplaces", {}).pop(name, None)
    return removed
```

- [ ] **Step 4: Wire the subcommands**

Replace the `raise SystemExit(f"packs.py: '{args.command}' not implemented yet")` line in `main()` with:

```python
    settings_file = Path(args.settings) if args.settings else Path.home() / ".claude" / "settings.json"
    settings = load_state(settings_file)
    if not isinstance(settings, dict):
        settings = {}
    state.setdefault("schema", 1)
    installed = state.setdefault("packs", {})
    messages: list[str] = []

    if args.command == "add":
        if args.slug not in packs:
            print(f"packs.py: unknown pack '{args.slug}'", file=sys.stderr)
            return 1
        platforms = install_pack(packs[args.slug], settings, messages)
        installed[args.slug] = {"platforms": platforms}

    elif args.command == "remove":
        if args.slug not in installed:
            print(f"packs.py: pack '{args.slug}' is not installed", file=sys.stderr)
            return 1
        platforms = installed[args.slug].get("platforms", {})
        if packs.get(args.slug) and platforms.get("claude-code") == "installed":
            claude_remove(packs[args.slug], settings)
        for platform, how in sorted(platforms.items()):
            if how in ("cli", "manual"):
                messages.append(
                    f"{platform}: installed outside 100xprism ({how}) — remove it with the "
                    f"upstream tooling. Skill files on disk were left untouched."
                )
        installed.pop(args.slug, None)

    elif args.command == "sync":
        for slug in sorted(installed):
            platforms = installed[slug].get("platforms", {})
            if slug not in packs:
                if platforms.get("claude-code") == "installed":
                    claude_remove(installed_pack_cache.get(slug, {}), settings)
                installed.pop(slug, None)
                messages.append(f"{slug}: no longer declared — removed")
            elif platforms.get("claude-code") == "installed":
                claude_install(packs[slug], settings)

    write_json(settings_file, settings)
    write_json(state_path(args), state)
    if args.json:
        print(json.dumps({"pack": args.slug, "messages": messages}, indent=2))
    else:
        for line in messages:
            print(f"  {line}")
        print("  Restart your agent to pick up the change.")
    return 0
```

Pruning a pack that is no longer in the registry still needs its old `claude-code` block. Record it in state at `add` time so `sync` can reverse it without the registry. Extend `install_pack`'s state entry and read it back — add this near the top of `main()`, right after `state = load_state(state_path(args))`:

```python
    # A pack dropped from the registry must still be reversible, so `add` records the
    # claude-code block verbatim alongside the platform statuses.
    installed_pack_cache = {
        slug: {"install": {"claude-code": entry.get("claude_code_block", {})}}
        for slug, entry in state.get("packs", {}).items()
    }
```

And in the `add` branch, store the block:

```python
        installed[args.slug] = {
            "platforms": platforms,
            "claude_code_block": packs[args.slug].get("install", {}).get("claude-code", {}),
        }
```

- [ ] **Step 5: Add the install dispatcher stub**

Task 4 fills this in. For now, add above `main()`:

```python
def install_pack(pack: dict, settings: dict, messages: list[str]) -> dict[str, str]:
    """Install a pack. Returns {platform: 'installed'|'cli'|'manual'|'unavailable'}."""
    platforms: dict[str, str] = {}
    if claude_install(pack, settings):
        platforms["claude-code"] = "installed"
    return platforms
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `node --test test/packs-claude.test.js`
Expected: 7 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add adapters/lib/packs.py test/packs-claude.test.js
git commit -m "feat(packs): install, remove, and sync the claude-code platform"
```

---

### Task 4: CLI-preferred install and the non-Claude platforms

**Files:**
- Modify: `adapters/lib/packs.py` (replace the `install_pack` stub; add `which`, `run_command`)
- Test: `test/packs-install-paths.test.js`

**Interfaces:**
- Consumes: `claude_install` from Task 3.
- Produces:
  - `which(binary: str) -> bool` — honours the `PRISM_PACKS_WHICH` JSON override
  - `run_command(command: str) -> tuple[int, str]` — honours `PRISM_PACKS_RUNNER_LOG`
  - `install_pack(pack, settings, messages) -> dict[str, str]` — full resolution order
- Test hooks (production code, used by tests):
  - `PRISM_PACKS_WHICH` — JSON object mapping binary name to boolean, overriding `shutil.which`.
  - `PRISM_PACKS_RUNNER_LOG` — path; commands are appended one per line and **not** executed, returning exit 0.

- [ ] **Step 1: Write the failing test**

Create `test/packs-install-paths.test.js`:

```javascript
'use strict'

// Verifies the install resolution order in adapters/lib/packs.py:
// prefer the pack CLI when its binary exists; otherwise per-platform blocks
// (claude-code direct, codex shelled out, cursor printed for the user).

const { test } = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const REPO = path.resolve(__dirname, '..')
const SCRIPT = path.join(REPO, 'adapters', 'lib', 'packs.py')
const REGISTRY = path.join(REPO, 'packs', 'packs.json')

function setup() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pki-'))
  const settingsFile = path.join(dir, 'settings.json')
  fs.writeFileSync(settingsFile, '{}')
  return { dir, settingsFile, log: path.join(dir, 'commands.log') }
}

function add(ctx, whichMap) {
  const r = spawnSync('python3', [
    SCRIPT, 'add', 'databricks',
    '--settings', ctx.settingsFile, '--project', ctx.dir, '--packs', REGISTRY, '--json',
  ], {
    encoding: 'utf8',
    env: { ...process.env, PRISM_PACKS_WHICH: JSON.stringify(whichMap), PRISM_PACKS_RUNNER_LOG: ctx.log },
  })
  assert.equal(r.status, 0, r.stderr)
  return JSON.parse(r.stdout)
}

const commands = (ctx) => (fs.existsSync(ctx.log) ? fs.readFileSync(ctx.log, 'utf8').trim().split('\n') : [])
const platforms = (ctx) =>
  JSON.parse(fs.readFileSync(path.join(ctx.dir, '.100xprism-packs.json'), 'utf8')).packs.databricks.platforms

test('prefers the pack CLI when its binary is present', () => {
  const ctx = setup()
  add(ctx, { databricks: true })
  assert.deepEqual(commands(ctx), ['databricks aitools install'])
  assert.deepEqual(platforms(ctx), { 'claude-code': 'cli', cursor: 'cli', codex: 'cli' })
})

test('falls back to per-platform blocks when the CLI binary is missing', () => {
  const ctx = setup()
  const out = add(ctx, { databricks: false, codex: true })
  assert.deepEqual(commands(ctx), [
    'codex plugin marketplace add databricks/databricks-agent-skills',
    'codex plugin add databricks',
  ])
  const p = platforms(ctx)
  assert.equal(p['claude-code'], 'installed', 'claude handled in-process')
  assert.equal(p.codex, 'installed')
  assert.equal(p.cursor, 'manual', 'cursor has no shell installer')
  assert.ok(out.messages.some((m) => m.includes('/add-plugin databricks')), 'prints the cursor command')
})

test('reports a platform as unavailable when its binary is missing', () => {
  const ctx = setup()
  const out = add(ctx, { databricks: false, codex: false })
  assert.equal(platforms(ctx).codex, 'unavailable')
  assert.ok(out.messages.some((m) => m.includes('docs.databricks.com')), 'prints the hint')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test test/packs-install-paths.test.js`
Expected: FAIL — the CLI path is not taken; `commands()` is empty.

- [ ] **Step 3: Implement the resolution order**

In `adapters/lib/packs.py`, add `import shlex` and `import shutil` to the imports, then add these functions above `install_pack`:

```python
def which(binary: str) -> bool:
    """Is `binary` on PATH? PRISM_PACKS_WHICH overrides the answer, for tests."""
    override = os.environ.get("PRISM_PACKS_WHICH")
    if override:
        try:
            return bool(json.loads(override).get(binary, False))
        except ValueError:
            pass
    return shutil.which(binary) is not None


def run_command(command: str) -> tuple[int, str]:
    """Run a declared install command.

    When PRISM_PACKS_RUNNER_LOG is set the command is recorded and NOT executed —
    this is how tests exercise install paths without touching the network.
    """
    log = os.environ.get("PRISM_PACKS_RUNNER_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as fh:
            fh.write(command + "\n")
        return 0, ""
    proc = subprocess.run(shlex.split(command), capture_output=True, text=True, check=False)
    return proc.returncode, (proc.stderr or proc.stdout).strip()
```

Replace the `install_pack` stub from Task 3 with:

```python
def install_pack(pack: dict, settings: dict, messages: list[str]) -> dict[str, str]:
    """Install a pack, preferring the upstream's own multi-agent CLI.

    Returns {platform: status}, where status is one of:
      installed   — 100xprism performed it and can reverse it
      cli         — the pack's own CLI did it; not ours to reverse
      manual      — the user must run a command themselves
      unavailable — no usable path for that platform
    """
    install = pack.get("install", {})
    platforms: dict[str, str] = {}
    cli = install.get("cli")

    # 1. The upstream CLI, when present, covers every platform in one command.
    if install.get("preferred") == "cli" and cli and which(cli["requires"]):
        code, err = run_command(cli["command"])
        if code == 0:
            for platform in cli.get("covers", []):
                platforms[platform] = "cli"
            messages.append(f"ran `{cli['command']}` — covers {', '.join(cli.get('covers', []))}")
            return platforms
        messages.append(f"`{cli['command']}` failed ({err or f'exit {code}'}); falling back per platform")

    # 2. Per-platform blocks.
    for platform in PLATFORMS:
        block = install.get(platform)
        if not block:
            platforms[platform] = "unavailable"
            continue
        if platform == "claude-code":
            platforms[platform] = "installed" if claude_install(pack, settings) else "unavailable"
            continue
        if block.get("commands"):
            binary = block["commands"][0].split()[0]
            if not which(binary):
                platforms[platform] = "unavailable"
                continue
            failed = False
            for command in block["commands"]:
                code, err = run_command(command)
                if code != 0:
                    messages.append(f"{platform}: `{command}` failed ({err or f'exit {code}'})")
                    failed = True
                    break
            platforms[platform] = "unavailable" if failed else "installed"
            continue
        if block.get("manual"):
            platforms[platform] = "manual"
            steps = ", ".join(block["manual"])
            messages.append(f"{platform}: run this in your agent yourself — {steps}")

    # 3. Nothing worked for some platform: surface the pack's own hint.
    if cli and cli.get("hint") and any(v == "unavailable" for v in platforms.values()):
        messages.append(cli["hint"])
    return platforms
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test test/packs-install-paths.test.js test/packs-claude.test.js`
Expected: all tests PASS. The Task 3 suite still passes because it pins `PRISM_PACKS_WHICH` to `{"databricks": false}`.

- [ ] **Step 5: Commit**

```bash
git add adapters/lib/packs.py test/packs-install-paths.test.js
git commit -m "feat(packs): prefer upstream CLI, fall back to per-platform installers"
```

---

### Task 5: The `/pack` module

**Files:**
- Create: `modules/pack/SKILL.md`
- Modify: `README.md` (module count 67 → 68; slash-command count 27 → 28)
- Modify: `package.json` (`description`: "67 cross-tool modules" → "68 cross-tool modules")
- Modify: `AGENTS.md`, `docs/USAGE.md`, `install.sh` — only if they carry a stale count; `scripts/meta-check.py` names them, so let it tell you
- Test: `test/packs-module.test.js`

**Interfaces:**
- Consumes: the `packs.py` CLI from Tasks 2–4.
- Produces: a `/pack` slash command with `name: pack`, `tier: on-demand`, `model: haiku`.

- [ ] **Step 1: Write the failing test**

Create `test/packs-module.test.js`:

```javascript
'use strict'

// Verifies modules/pack/SKILL.md is a well-formed on-demand slash-command module
// that delegates to adapters/lib/packs.py and does not overlap /connect's triggers.

const { test } = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

const REPO = path.resolve(__dirname, '..')
const SKILL = path.join(REPO, 'modules', 'pack', 'SKILL.md')

test('frontmatter declares the expected routing', () => {
  const text = fs.readFileSync(SKILL, 'utf8')
  assert.match(text, /^---\n/)
  assert.match(text, /\nname: pack\n/)
  assert.match(text, /\ntier: on-demand\n/)
  assert.match(text, /\nmodel: haiku\n/)
  assert.match(text, /\nslash_command: \/pack\n/)
})

test('delegates to the helper rather than reimplementing install logic', () => {
  const text = fs.readFileSync(SKILL, 'utf8')
  assert.match(text, /adapters\/lib\/packs\.py/)
  for (const sub of ['status', 'detect', 'add', 'remove']) {
    assert.ok(text.includes(`packs.py" ${sub}`) || text.includes(`$SUB`), `mentions ${sub}`)
  }
  assert.ok(!/enabledPlugins/.test(text), 'must not touch settings.json directly')
})

test('resolves the helper for npm-global installs too', () => {
  const text = fs.readFileSync(SKILL, 'utf8')
  assert.match(text, /npm root -g/)
})

test('trigger-overlap check still passes in strict mode', () => {
  const r = spawnSync('python3', [path.join(REPO, 'scripts', 'trigger-overlap.py'), '--strict'], {
    cwd: REPO, encoding: 'utf8',
  })
  assert.equal(r.status, 0, r.stdout + r.stderr)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test test/packs-module.test.js`
Expected: FAIL — `ENOENT` reading `modules/pack/SKILL.md`.

- [ ] **Step 3: Write the module**

Create `modules/pack/SKILL.md`:

````markdown
---
name: pack
description: Install optional third-party skill packs that 100xprism doesn't ship by default — "add the Databricks skills", "what packs are available", "is there a pack for X".
category: engineering
tier: on-demand
model: haiku
slash_command: /pack
---

# Pack — Optional Third-Party Skill Packs

Packs are skill collections 100xprism does not ship by default because they only
matter to some projects. They are opt-in: nothing installs until you ask.

> **Scope:** `/pack` installs skills you don't have. To authenticate a CLI you
> already have, use `/connect`.

## Usage
- `/pack` — list every pack, its install state, and anything detected here
- `/pack detect` — only what matches the current project
- `/pack add databricks` — install a pack
- `/pack remove databricks` — reverse what 100xprism installed

---

## Step 1 — Locate the helper

All decisions live in the helper script. Do not reimplement them here.

```bash
PACKS=""
for candidate in \
  "$HOME/100xprism/adapters/lib/packs.py" \
  "$(npm root -g 2>/dev/null)/100xprism/adapters/lib/packs.py"; do
  if [ -f "$candidate" ]; then PACKS="$candidate"; break; fi
done
if [ -z "$PACKS" ]; then
  echo "100xprism installation not found — reinstall with: npm i -g 100xprism"
  exit 1
fi
```

## Step 2 — Run the requested subcommand

Map the user's argument to a subcommand: no argument → `status`; `detect`,
`add <slug>`, `remove <slug>` pass through unchanged.

```bash
python3 "$PACKS" "$SUB" $SLUG --settings "$HOME/.claude/settings.json"
```

## Step 3 — Report

Print the helper's output verbatim. It already says which platforms were handled
and which need a manual step.

If any pack was added or removed, finish with: **restart your agent to pick up the
change.**

Two things to pass along honestly rather than paper over:

- A platform marked `manual` was **not** installed. Give the user the exact command
  the helper printed.
- `/pack remove` reverses only what 100xprism wrote. A pack installed by an
  upstream CLI leaves its skill files on disk — say so; do not delete them.
````

- [ ] **Step 4: Update the counts**

Run `python3 scripts/meta-check.py`. It fails and names every file with a stale count. Update each to 68 modules / 28 slash commands. The auto-trigger-skills count stays 40 (`68 - 28`).

- [ ] **Step 5: Run tests to verify they pass**

Run: `node --test test/packs-module.test.js && python3 scripts/meta-check.py`
Expected: 4 tests PASS; meta-check reports `modules parsed: 68 (28 slash commands, 40 auto-trigger skills)` and `all checks passed ✓`.

If the trigger-overlap test fails on a `pack` ↔ `connect` pair, sharpen the two
descriptions so they no longer share trigger vocabulary. Add to
`scripts/trigger-overlap-allow.txt` only if the overlap is genuinely intentional —
here it is not, so fix the descriptions.

- [ ] **Step 6: Commit**

```bash
git add modules/pack README.md package.json test/packs-module.test.js
git add -u
git commit -m "feat(packs): add the /pack module"
```

---

### Task 6: Lifecycle wiring — install, update, uninstall

**Files:**
- Modify: `adapters/claude-code.sh` (in `install_plugins`, after the `sync_plugins.py` call at ~L145)
- Modify: `update.sh` (~L216 and ~L294, beside each `sync_plugins.py` call)
- Modify: `lib/uninstall.js` (add `cleanManagedPacks`, call it from `run` and `preinstallCleanup`, export it)
- Test: `test/packs-lifecycle.test.js`

**Interfaces:**
- Consumes: `packs.py sync` and the state file from Task 3.
- Produces: `cleanManagedPacks(home = os.homedir()) -> { file, removed }` exported from `lib/uninstall.js`.

- [ ] **Step 1: Write the failing test**

Create `test/packs-lifecycle.test.js`:

```javascript
'use strict'

// Verifies uninstall reverses 100xprism-managed packs from settings.json,
// leaves user plugins alone, and never deletes third-party skill files.

const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const { cleanManagedPacks } = require('../lib/uninstall.js')
const PLUGIN = 'databricks@databricks-agent-skills'

function fakeHome(state, settings) {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pkl-'))
  const claude = path.join(home, '.claude')
  fs.mkdirSync(claude, { recursive: true })
  fs.writeFileSync(path.join(claude, 'settings.json'), JSON.stringify(settings))
  fs.writeFileSync(path.join(claude, '.100xprism-packs.json'), JSON.stringify(state))
  fs.mkdirSync(path.join(claude, 'skills', 'databricks-core'), { recursive: true })
  fs.writeFileSync(path.join(claude, 'skills', 'databricks-core', 'SKILL.md'), '# upstream')
  return { home, claude }
}

test('removes managed pack plugins and the state file', () => {
  const { home, claude } = fakeHome(
    { schema: 1, packs: { databricks: { platforms: { 'claude-code': 'installed' },
      claude_code_block: { marketplace: { name: 'databricks-agent-skills',
        source: { source: 'github', repo: 'databricks/databricks-agent-skills' } },
        plugins: [PLUGIN] } } } },
    { enabledPlugins: { [PLUGIN]: true, 'user-only@m': true },
      extraKnownMarketplaces: { 'databricks-agent-skills': {} } },
  )
  const result = cleanManagedPacks(home)
  const settings = JSON.parse(fs.readFileSync(path.join(claude, 'settings.json'), 'utf8'))

  assert.equal(result.removed, 1)
  assert.equal(PLUGIN in settings.enabledPlugins, false)
  assert.equal(settings.enabledPlugins['user-only@m'], true, 'user plugin preserved')
  assert.equal(fs.existsSync(path.join(claude, '.100xprism-packs.json')), false)
})

test('never deletes third-party skill files', () => {
  const { home, claude } = fakeHome(
    { schema: 1, packs: { databricks: { platforms: { 'claude-code': 'cli' } } } },
    { enabledPlugins: {} },
  )
  cleanManagedPacks(home)
  assert.ok(
    fs.existsSync(path.join(claude, 'skills', 'databricks-core', 'SKILL.md')),
    'CLI-installed skills left on disk',
  )
})

test('is a no-op when no packs were ever installed', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pkl-'))
  assert.deepEqual(cleanManagedPacks(home).removed, 0)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test test/packs-lifecycle.test.js`
Expected: FAIL — `cleanManagedPacks is not a function`.

- [ ] **Step 3: Implement `cleanManagedPacks`**

In `lib/uninstall.js`, add after `cleanClaudeSessionHooks`:

```javascript
// Reverse packs 100xprism installed via the managed claude-code path. Packs
// installed by an upstream CLI are left alone — we did not write those files and
// do not know what else that CLI put there.
function cleanManagedPacks(home = os.homedir()) {
  const claudeDir = path.join(home, '.claude')
  const stateFile = path.join(claudeDir, '.100xprism-packs.json')
  const settingsFile = path.join(claudeDir, 'settings.json')

  let state
  try {
    state = JSON.parse(fs.readFileSync(stateFile, 'utf8'))
  } catch (err) {
    if (err && err.code === 'ENOENT') return { file: settingsFile, removed: 0 }
    console.warn(`Warning: could not read ${stateFile}: ${err.message}`)
    return { file: settingsFile, removed: 0 }
  }

  let settings
  try {
    settings = JSON.parse(fs.readFileSync(settingsFile, 'utf8'))
  } catch {
    settings = {}
  }
  const enabled = settings.enabledPlugins || {}
  const marketplaces = settings.extraKnownMarketplaces || {}

  let removed = 0
  for (const entry of Object.values(state.packs || {})) {
    if ((entry.platforms || {})['claude-code'] !== 'installed') continue
    const block = entry.claude_code_block || {}
    for (const plugin of block.plugins || []) {
      if (delete enabled[plugin]) removed += 1
    }
    const name = block.marketplace && block.marketplace.name
    if (name && !Object.keys(enabled).some((p) => p.split('@').pop() === name)) {
      delete marketplaces[name]
    }
  }

  if (removed) {
    settings.enabledPlugins = enabled
    settings.extraKnownMarketplaces = marketplaces
    fs.writeFileSync(settingsFile, JSON.stringify(settings, null, 2) + '\n')
  }
  fs.rmSync(stateFile, { force: true })
  return { file: settingsFile, removed }
}
```

Call it from `run()`, right after `const hookCleanup = cleanSessionHooksOnly()`:

```javascript
  const packCleanup = cleanManagedPacks()
  if (packCleanup.removed) {
    console.log(`Removed ${packCleanup.removed} 100xprism-managed pack plugin(s) from ${packCleanup.file}.`)
    console.log('Packs installed by an upstream CLI were left in place — remove those with their own tooling.')
  }
```

Update the "nothing found" guard on the next line to include `&& !packCleanup.removed`, and add `cleanManagedPacks` to `module.exports`.

- [ ] **Step 4: Wire sync + detection into install and update**

In `adapters/claude-code.sh`, inside `install_plugins`, after the `sync_plugins.py` invocation and before the `Plugins merged` echo:

```bash
  # Re-apply opted-in packs and prune any dropped from packs.json. Detection is
  # read-only and only prints a suggestion — it never installs.
  python3 "$REPO_DIR/adapters/lib/packs.py" sync --settings "$SETTINGS_FILE" || true
  python3 "$REPO_DIR/adapters/lib/packs.py" detect --settings "$SETTINGS_FILE" 2>/dev/null | head -4 || true
```

In `update.sh`, add the same two lines after **each** of the two `sync_plugins.py` invocations (~L216 and ~L294), using that file's existing `$SETTINGS_FILE` variable.

- [ ] **Step 5: Run the full suite**

Run: `node --test && python3 scripts/meta-check.py`
Expected: every test PASSES (104 existing + the new suites); meta-check clean.

- [ ] **Step 6: Verify the install path end-to-end in a throwaway HOME**

```bash
HOME=$(mktemp -d) ./adapters/claude-code.sh
```
Expected: exit 0, no traceback, and the pack lines print without installing anything (`packs.json` declares `databricks`, which will not be detected in a temp dir).

- [ ] **Step 7: Commit**

```bash
git add adapters/claude-code.sh update.sh lib/uninstall.js test/packs-lifecycle.test.js
git commit -m "feat(packs): wire pack sync and detection into install, update, uninstall"
```

---

## Self-review notes

- **Spec coverage.** Registry → Task 1. Detection (root-only, git-toplevel fallback) → Task 2. Claude Code install/remove/sync and state semantics → Task 3. CLI-preferred resolution, `installed`/`cli`/`manual`/`unavailable` statuses, Cursor manual path → Task 4. `/pack` module, frontmatter, trigger-overlap risk, count updates → Task 5. Lifecycle wiring and non-destructive removal → Task 6.
- **Deferred from the spec, deliberately:** the optional per-platform `uninstall` array. The spec leaves it unset for `databricks` because upstream documents no uninstall command, so no task implements it; `remove` prints guidance instead. Add it when a verified command exists.
- **Naming consistency:** `install_pack`, `claude_install`, `claude_remove`, `which`, `run_command`, `write_json`, `state_path`, `load_state`, `pack_matches`, `project_root`, `load_registry`, `describe`, `render` are each defined once and referenced with the same signature throughout.
