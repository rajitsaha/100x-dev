# External Skill Packs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship an opt-in mechanism for installing third-party skill packs, with `databricks` as the only shipped pack.

**Architecture:** A declarative registry (`packs/packs.json`) is read by a deterministic Python helper (`adapters/lib/packs.py`) that detects matching projects, installs packs by orchestrating each upstream's own installer, and records exactly which config entries it inserted in a sidecar state file. A thin `/pack` slash-command module shells out to the helper; it makes no decisions. Nothing installs automatically.

**Tech Stack:** Python 3 (stdlib only, matching `adapters/lib/*.py`), Node's built-in `node:test` runner, bash adapters.

**Spec:** `docs/superpowers/specs/2026-08-03-skill-packs-databricks-design.md`

## Global Constraints

- Python helpers use the **standard library only** — no new dependencies. `package.json` has zero runtime deps and must keep zero.
- `packs.py` **never** deletes files under `~/.claude/skills/` or any third-party skill directory. It reverses only `settings.json` entries it recorded inserting.
- **Ownership is per entry, not per platform.** A plugin key that already existed in `enabledPlugins` — enabled *or* explicitly disabled — was not added by us and must never be removed by us. Same for a pre-existing marketplace.
- **Never overwrite unreadable config.** If `settings.json` exists but does not parse, abort with a message. Do not replace it with `{}`.
- There is **no first-run seeding**. A pack enters state only because the user ran `/pack add`, so an absent entry unambiguously means "not installed by us." (`sync_plugins.py` seeds because its plugins install unconditionally; packs do not.)
- Detection is **read-only**, matches **only exact paths at the project root**, and **never** triggers an install.
- Supported platform keys are exactly `claude-code`, `codex`, `cursor`.
- **Tests must never mutate tracked repo files.** `node --test` runs 4 files concurrently; a test that rewrites `packs/packs.json` in place races with every suite that reads it. Use temp registries and temp fixture dirs.
- **Test fixtures must live outside this git repository.** `project_root()` resolves the git toplevel, so a fixture committed under `scripts/fixtures/` resolves to the 100xprism root and never matches.
- Tests must not touch the network. Shell execution is stubbed via `PRISM_PACKS_RUNNER_LOG` and `PRISM_PACKS_WHICH` (Task 4).
- `python3 scripts/meta-check.py` and `node --test` must both pass before every commit. The repo has a gate-on-commit hook; run `/gate`, then `python3 ~/100xprism/hooks/gate-pass.py` in its own shell call, before committing.

## State file shape

`~/.claude/.100xprism-packs.json` — the single source of truth for what may be reversed.

```json
{
  "schema": 1,
  "packs": {
    "databricks": {
      "platforms": {
        "claude-code": "installed",
        "codex": "installed",
        "cursor": "manual"
      },
      "owned": {
        "plugins": ["databricks@databricks-agent-skills"],
        "marketplace": "databricks-agent-skills"
      },
      "uninstall": { "codex": [] }
    }
  }
}
```

- `platforms[p]` ∈ `installed` (we did it, we can reverse it) | `cli` (the pack's own CLI did it) | `manual` (the user must run it) | `unavailable` (no usable path).
- `owned.plugins` lists **only** keys this install actually inserted. `owned.marketplace` is the marketplace name only if we inserted it, else `null`.
- `uninstall` copies each platform's declared inverse commands at install time, so a pack dropped from the registry stays reversible.

---

### Task 1: Registry file and schema validation

Creates the declarative registry and the CI check that keeps it honest. No behavior yet — this task exists so a reviewer can reject the schema before any code depends on it.

**Files:**
- Create: `packs/packs.json`
- Modify: `scripts/meta-check.py` (add `check_packs()`, a `--packs` override, and the `main()` call)
- Modify: `package.json` (add `"packs/"` to `files`)
- Test: `test/packs-schema.test.js`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `packs/packs.json` with top-level `schema` (int, must be `1`) and `packs` (object keyed by slug).
  - `scripts/meta-check.py` gains `check_packs(path: Path) -> int` returning the pack count, plus a `--packs PATH` CLI flag so tests can validate a temporary registry **without touching the tracked one**.

- [ ] **Step 1: Write the failing test**

Create `test/packs-schema.test.js`:

```javascript
'use strict'

// Verifies packs/packs.json parses and that scripts/meta-check.py rejects malformed
// pack declarations. Every negative case runs against a TEMPORARY registry passed via
// --packs: node --test runs files concurrently, so mutating the tracked packs.json in
// place would race with the suites that read it.

const { test } = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const REPO = path.resolve(__dirname, '..')
const PACKS = path.join(REPO, 'packs', 'packs.json')
const META = path.join(REPO, 'scripts', 'meta-check.py')

function metaCheck(registryPath) {
  const argv = registryPath ? [META, '--packs', registryPath] : [META]
  return spawnSync('python3', argv, { cwd: REPO, encoding: 'utf8' })
}

// Writes a mutated copy to a temp file and validates THAT — never the tracked file.
function withTempRegistry(mutate) {
  const data = JSON.parse(fs.readFileSync(PACKS, 'utf8'))
  mutate(data)
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pks-'))
  const file = path.join(dir, 'packs.json')
  fs.writeFileSync(file, JSON.stringify(data, null, 2) + '\n')
  return metaCheck(file)
}

test('the shipped registry is valid', () => {
  const data = JSON.parse(fs.readFileSync(PACKS, 'utf8'))
  assert.equal(data.schema, 1)
  assert.ok(data.packs.databricks, 'databricks pack declared')
  assert.equal(metaCheck().status, 0)
})

test('rejects an unknown install platform key', () => {
  const r = withTempRegistry((d) => { d.packs.databricks.install.antigravity = { manual: ['x'] } })
  assert.equal(r.status, 1)
  assert.match(r.stderr, /unknown install key 'antigravity'/)
})

test('rejects a missing required field', () => {
  const r = withTempRegistry((d) => { delete d.packs.databricks.source })
  assert.equal(r.status, 1)
  assert.match(r.stderr, /missing required key `source`/)
})

test('rejects a nested detect path', () => {
  const r = withTempRegistry((d) => { d.packs.databricks.detect.files.push('conf/databricks.yml') })
  assert.equal(r.status, 1)
  assert.match(r.stderr, /detect path .* must be a bare filename/)
})

test('rejects an uncompilable detect pattern', () => {
  const r = withTempRegistry((d) => { d.packs.databricks.detect.contains[0].pattern = '([' })
  assert.equal(r.status, 1)
  assert.match(r.stderr, /pattern invalid/)
})

test('the tracked registry is left untouched by the negative cases', () => {
  assert.equal(metaCheck().status, 0, 'real registry still valid after temp-file tests')
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

There is intentionally no `uninstall` array on any platform: the upstream README documents no uninstall command, and inventing one is worse than printing guidance. The schema supports it (Task 4) for when a verified command exists.

- [ ] **Step 4: Add the validator to meta-check**

In `scripts/meta-check.py`, add after `check_plugins()`:

```python
PACK_PLATFORMS = {"claude-code", "codex", "cursor"}


def check_packs(path: Path) -> int:
    """Validate a pack registry — schema version, required keys, platform names."""
    data = json.loads(path.read_text())
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

In `main()`, add the `--packs` flag beside the existing `--tag` argument:

```python
    ap.add_argument("--packs", default="",
                    help="pack registry to validate (default: packs/packs.json). "
                         "Tests pass a temp copy so the tracked registry is never mutated.")
```

and call it directly after `counts["plugins"] = check_plugins()`:

```python
    check_packs(Path(args.packs) if args.packs else REPO / "packs" / "packs.json")
```

- [ ] **Step 5: Add `packs/` to the npm payload**

In `package.json`, inside `files`, add `"packs/",` immediately after `"modules/",`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `node --test test/packs-schema.test.js && python3 scripts/meta-check.py`
Expected: 6 tests PASS; meta-check prints `packs[] entries: 1` and `all checks passed ✓`.

- [ ] **Step 7: Commit**

```bash
git add packs/packs.json scripts/meta-check.py package.json test/packs-schema.test.js
git commit -m "feat(packs): add pack registry and schema validation"
```

---

### Task 2: Detection engine and read-only subcommands

**Files:**
- Create: `adapters/lib/packs.py`
- Test: `test/packs-detect.test.js`

**Interfaces:**
- Consumes: `packs/packs.json` from Task 1.
- Produces:
  - `load_registry(path: Path) -> dict`
  - `project_root(start: Path) -> Path` — git toplevel, else `start`
  - `pack_matches(pack: dict, root: Path, env: Mapping[str, str]) -> bool`
  - `load_state(path: Path) -> dict` — sidecar only; tolerant, returns `{}` on any failure
  - `load_settings(path: Path) -> dict` — **strict**; aborts rather than overwrite unreadable config
  - `state_path(args) -> Path`
  - CLI: `packs.py {detect,status} [--project DIR] [--packs FILE] [--settings FILE] [--state FILE] [--json]`
  - `--json` emits `{"packs": [{"slug", "title", "description", "source", "detected", "platforms"}]}`. `platforms` is `{}` until Task 3.

Fixtures are built in temp directories inside the test, **not** committed under `scripts/fixtures/` — anything inside this repo resolves to the 100xprism git root and would never match.

- [ ] **Step 1: Write the failing test**

Create `test/packs-detect.test.js`:

```javascript
'use strict'

// Verifies adapters/lib/packs.py detection: file, env, and content predicates match
// at the project root only. Fixtures are built in temp dirs — a fixture committed
// inside this repo would resolve to the 100xprism git toplevel and never match.

const { test } = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const REPO = path.resolve(__dirname, '..')
const SCRIPT = path.join(REPO, 'adapters', 'lib', 'packs.py')

function fixture(files = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pkd-'))
  for (const [name, body] of Object.entries(files)) {
    const target = path.join(dir, name)
    fs.mkdirSync(path.dirname(target), { recursive: true })
    fs.writeFileSync(target, body)
  }
  return dir
}

function detectedSlugs(projectDir, env = {}) {
  const r = spawnSync('python3', [SCRIPT, 'detect', '--project', projectDir, '--json'], {
    encoding: 'utf8',
    env: { ...process.env, DATABRICKS_HOST: '', ...env },
  })
  assert.equal(r.status, 0, r.stderr)
  return JSON.parse(r.stdout).packs.filter((p) => p.detected).map((p) => p.slug)
}

test('matches on a root marker file', () => {
  assert.deepEqual(detectedSlugs(fixture({ 'databricks.yml': '' })), ['databricks'])
})

test('matches on file content', () => {
  assert.deepEqual(
    detectedSlugs(fixture({ 'requirements.txt': 'databricks-sql-connector==3.0.0\n' })),
    ['databricks'],
  )
})

test('matches on an environment variable', () => {
  assert.deepEqual(
    detectedSlugs(fixture({ 'README.md': '# plain' }), { DATABRICKS_HOST: 'https://x.databricks.com' }),
    ['databricks'],
  )
})

test('does not match an unrelated project', () => {
  assert.deepEqual(detectedSlugs(fixture({ 'README.md': '# plain' })), [])
})

test('does not match a marker file nested below the root', () => {
  assert.deepEqual(detectedSlugs(fixture({ 'conf/databricks.yml': '' })), [], 'nested must not match')
})

test('resolves the git toplevel when run from a subdirectory', () => {
  const dir = fixture({ 'databricks.yml': '', 'src/main.py': '' })
  const git = (...args) => spawnSync('git', ['-C', dir, ...args], { encoding: 'utf8' })
  git('init', '-q')
  // Detection from src/ must find the marker at the repo root, not miss it.
  assert.deepEqual(detectedSlugs(path.join(dir, 'src')), ['databricks'])
})

test('status lists every declared pack, detected or not', () => {
  const r = spawnSync(
    'python3',
    [SCRIPT, 'status', '--project', fixture({ 'README.md': '# plain' }), '--json'],
    { encoding: 'utf8', env: { ...process.env, DATABRICKS_HOST: '' } },
  )
  assert.equal(r.status, 0, r.stderr)
  const packs = JSON.parse(r.stdout).packs
  assert.equal(packs.length, 1)
  assert.equal(packs[0].slug, 'databricks')
  assert.equal(packs[0].detected, false)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test test/packs-detect.test.js`
Expected: FAIL — `can't open file .../adapters/lib/packs.py`.

- [ ] **Step 3: Write the helper**

Create `adapters/lib/packs.py`:

```python
#!/usr/bin/env python3
"""Manage optional third-party skill packs declared in packs/packs.json.

Packs are opt-in. Nothing here installs anything unless the user explicitly runs
`add`, and detection is strictly read-only: it reports which declared packs look
relevant to the current project and stops there.

Ownership is tracked per config entry, not per platform — see the state file shape
in docs/superpowers/plans/2026-08-03-skill-packs.md. If the user already had a
plugin listed, we did not add it and will never remove it.

Subcommands:
  detect  — which declared packs match the current project (read-only)
  status  — every declared pack, its detection result, and its install state
  add     — install a pack
  remove  — reverse what we recorded inserting
  sync    — re-apply opted-in packs; drop packs no longer declared
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


def load_state(path: Path) -> dict:
    """Our own sidecar. Tolerant: an unreadable sidecar just means 'nothing installed'."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_settings(path: Path) -> dict:
    """The user's settings.json. Strict: never replace config we could not read.

    load_state's tolerance is wrong here — collapsing a malformed settings.json to {}
    and writing it back would destroy the user's whole configuration.
    """
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise SystemExit(
            f"packs.py: refusing to rewrite {path} — it exists but could not be read ({exc}). "
            "Fix or move the file, then retry."
        )
    return data if isinstance(data, dict) else {}


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


def settings_path(args) -> Path:
    return Path(args.settings) if args.settings else Path.home() / ".claude" / "settings.json"


def state_path(args) -> Path:
    if args.state:
        return Path(args.state)
    return settings_path(args).parent / ".100xprism-packs.json"


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


def render(rows: list[dict]) -> str:
    lines = []
    for row in rows:
        if row["platforms"]:
            note = "installed: " + ", ".join(f"{k}={v}" for k, v in sorted(row["platforms"].items()))
        elif row["detected"]:
            note = f"detected here — run `/pack add {row['slug']}` to install"
        else:
            note = "not installed"
        lines.append(f"  {row['slug']:<14} {row['title']}\n    {note}")
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
    state = load_state(state_path(args))

    if args.command in ("detect", "status"):
        root = project_root(Path(args.project).resolve())
        rows = describe(packs, root, os.environ, state)
        if args.command == "detect":
            rows = [r for r in rows if r["detected"]]
        print(json.dumps({"packs": rows}, indent=2) if args.json else render(rows))
        return 0

    raise SystemExit(f"packs.py: '{args.command}' not implemented yet")


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test test/packs-detect.test.js`
Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add adapters/lib/packs.py test/packs-detect.test.js
git commit -m "feat(packs): add detection engine and read-only detect/status"
```

---

### Task 3: Claude Code install, removal, and state reconciliation

Implements ownership-tracked reconciliation for the `claude-code` platform. The non-Claude platforms arrive in Task 4; this task's `install_pack` handles Claude only, so a reviewer can judge the ownership model in isolation.

**Files:**
- Modify: `adapters/lib/packs.py`
- Test: `test/packs-claude.test.js`

**Interfaces:**
- Consumes: `load_registry`, `load_state`, `load_settings`, `state_path`, `settings_path` from Task 2.
- Produces:
  - `claude_install(pack: dict, settings: dict) -> dict | None` — returns `{"plugins": [...], "marketplace": str | None}` listing **only what it inserted**, or `None` if the pack has no `claude-code` block.
  - `claude_remove(owned: dict, settings: dict) -> list[str]` — takes the recorded ownership record, not the registry entry.
  - `merge_owned(a: dict, b: dict) -> dict` — union, preserving a non-null marketplace.
  - `write_json(path: Path, data: dict) -> None`
  - `install_pack(pack: dict, settings: dict, messages: list[str]) -> tuple[dict[str, str], dict]` — returns `(platforms, owned)`. Task 4 replaces the body; the signature is final.

- [ ] **Step 1: Write the failing test**

Create `test/packs-claude.test.js`:

```javascript
'use strict'

// Verifies adapters/lib/packs.py reconciles settings.json for the claude-code
// platform with per-entry ownership: it removes only what it inserted, survives a
// pack being dropped from the registry, and refuses to overwrite unreadable config.

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
const MARKET = 'databricks-agent-skills'

function setup(settings = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pkc-'))
  const settingsFile = path.join(dir, 'settings.json')
  fs.writeFileSync(settingsFile, typeof settings === 'string' ? settings : JSON.stringify(settings))
  return { dir, settingsFile, project: dir }
}

function run(ctx, argv, opts = {}) {
  const r = spawnSync('python3', [
    SCRIPT, ...argv,
    '--settings', ctx.settingsFile,
    '--project', ctx.project,
    '--packs', opts.registry || REGISTRY,
  ], {
    encoding: 'utf8',
    // Force the per-platform path; Task 4 covers the CLI path.
    env: { ...process.env, PRISM_PACKS_WHICH: '{"databricks": false}' },
  })
  if (!opts.allowFailure) assert.equal(r.status, 0, r.stderr)
  return r
}

const settingsOf = (ctx) => JSON.parse(fs.readFileSync(ctx.settingsFile, 'utf8'))
const stateFile = (ctx) => path.join(ctx.dir, '.100xprism-packs.json')
const stateOf = (ctx) => JSON.parse(fs.readFileSync(stateFile(ctx), 'utf8'))

test('add wires the marketplace, enables the plugin, and records ownership', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'])
  const s = settingsOf(ctx)
  assert.equal(s.enabledPlugins[PLUGIN], true)
  assert.ok(s.extraKnownMarketplaces[MARKET])

  const entry = stateOf(ctx).packs.databricks
  assert.equal(entry.platforms['claude-code'], 'installed')
  assert.deepEqual(entry.owned.plugins, [PLUGIN])
  assert.equal(entry.owned.marketplace, MARKET)
})

test('add is idempotent and does not lose the ownership record', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'])
  const first = settingsOf(ctx)
  run(ctx, ['add', 'databricks'])
  assert.deepEqual(settingsOf(ctx), first)
  // Second add inserts nothing; the record from the first must survive.
  assert.deepEqual(stateOf(ctx).packs.databricks.owned.plugins, [PLUGIN])
})

test('a plugin the user already disabled is neither flipped nor owned nor removed', () => {
  const ctx = setup({ enabledPlugins: { [PLUGIN]: false } })
  run(ctx, ['add', 'databricks'])
  assert.equal(settingsOf(ctx).enabledPlugins[PLUGIN], false, 'not flipped')
  assert.deepEqual(stateOf(ctx).packs.databricks.owned.plugins, [], 'not claimed')

  run(ctx, ['remove', 'databricks'])
  assert.equal(settingsOf(ctx).enabledPlugins[PLUGIN], false, 'user entry survives removal')
})

test('a marketplace the user already had is not claimed and not removed', () => {
  const ctx = setup({ extraKnownMarketplaces: { [MARKET]: { source: { source: 'github', repo: 'u/x' } } } })
  run(ctx, ['add', 'databricks'])
  assert.equal(stateOf(ctx).packs.databricks.owned.marketplace, null, 'not claimed')
  assert.deepEqual(
    settingsOf(ctx).extraKnownMarketplaces[MARKET].source.repo, 'u/x', 'not overwritten')

  run(ctx, ['remove', 'databricks'])
  assert.ok(settingsOf(ctx).extraKnownMarketplaces[MARKET], 'user marketplace survives')
})

test('remove reverses only what we inserted', () => {
  const ctx = setup({ enabledPlugins: { 'user-only@m': true } })
  run(ctx, ['add', 'databricks'])
  run(ctx, ['remove', 'databricks'])
  const s = settingsOf(ctx)
  assert.equal(PLUGIN in s.enabledPlugins, false, 'our plugin removed')
  assert.equal(s.enabledPlugins['user-only@m'], true, 'user plugin preserved')
  assert.equal(MARKET in (s.extraKnownMarketplaces || {}), false)
  assert.equal('databricks' in stateOf(ctx).packs, false)
})

test('remove keeps a marketplace another enabled plugin still needs', () => {
  const ctx = setup({ enabledPlugins: { 'other@databricks-agent-skills': true } })
  run(ctx, ['add', 'databricks'])
  run(ctx, ['remove', 'databricks'])
  assert.ok(settingsOf(ctx).extraKnownMarketplaces[MARKET], 'marketplace still in use')
})

test('remove still works after the pack is dropped from the registry', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'])
  const empty = path.join(ctx.dir, 'empty-packs.json')
  fs.writeFileSync(empty, JSON.stringify({ schema: 1, packs: {} }))

  run(ctx, ['remove', 'databricks'], { registry: empty })
  assert.equal(PLUGIN in settingsOf(ctx).enabledPlugins, false, 'reversed from the state record')
  assert.equal('databricks' in stateOf(ctx).packs, false)
})

test('sync re-applies an opted-in pack and prunes one no longer declared', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'])

  const s = settingsOf(ctx)
  delete s.enabledPlugins[PLUGIN]
  fs.writeFileSync(ctx.settingsFile, JSON.stringify(s))
  run(ctx, ['sync'])
  assert.equal(settingsOf(ctx).enabledPlugins[PLUGIN], true, 're-applied')

  const empty = path.join(ctx.dir, 'empty-packs.json')
  fs.writeFileSync(empty, JSON.stringify({ schema: 1, packs: {} }))
  run(ctx, ['sync'], { registry: empty })
  assert.equal(PLUGIN in settingsOf(ctx).enabledPlugins, false, 'pruned')
})

test('refuses to overwrite an unreadable settings.json', () => {
  const ctx = setup('{ this is not json')
  const r = run(ctx, ['add', 'databricks'], { allowFailure: true })
  assert.notEqual(r.status, 0)
  assert.match(r.stderr, /refusing to rewrite/)
  assert.equal(fs.readFileSync(ctx.settingsFile, 'utf8'), '{ this is not json', 'file untouched')
})

test('add rejects an unknown slug', () => {
  const ctx = setup()
  const r = run(ctx, ['add', 'nope'], { allowFailure: true })
  assert.equal(r.status, 1)
  assert.match(r.stderr, /unknown pack 'nope'/)
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test test/packs-claude.test.js`
Expected: FAIL — `packs.py: 'add' not implemented yet`.

- [ ] **Step 3: Implement ownership-tracked reconciliation**

In `adapters/lib/packs.py`, add these functions after `load_settings`:

```python
def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


EMPTY_OWNED = {"plugins": [], "marketplace": None}


def merge_owned(a: dict, b: dict) -> dict:
    """Union two ownership records; a non-null marketplace wins over null."""
    plugins = list(dict.fromkeys(list(a.get("plugins", [])) + list(b.get("plugins", []))))
    return {"plugins": plugins, "marketplace": a.get("marketplace") or b.get("marketplace")}


def claude_install(pack: dict, settings: dict) -> dict | None:
    """Add the pack's marketplace + plugins. Returns ONLY what this call inserted.

    An entry that already exists — an enabled plugin, an explicitly disabled one, or a
    marketplace the user configured — is left exactly as-is and is NOT claimed. That
    record is what makes removal safe.
    """
    block = pack.get("install", {}).get("claude-code")
    if not block:
        return None

    owned = {"plugins": [], "marketplace": None}

    marketplace = block.get("marketplace")
    if marketplace:
        marketplaces = settings.setdefault("extraKnownMarketplaces", {})
        if marketplace["name"] not in marketplaces:
            marketplaces[marketplace["name"]] = {"source": marketplace["source"]}
            owned["marketplace"] = marketplace["name"]

    enabled = settings.setdefault("enabledPlugins", {})
    for plugin in block.get("plugins", []):
        if plugin not in enabled:
            enabled[plugin] = True
            owned["plugins"].append(plugin)

    return owned


def claude_remove(owned: dict, settings: dict) -> list[str]:
    """Reverse an ownership record. Never consults the registry — a pack dropped from
    packs.json must still be removable."""
    enabled = settings.setdefault("enabledPlugins", {})
    removed = [p for p in owned.get("plugins", []) if enabled.pop(p, None) is not None]

    name = owned.get("marketplace")
    if name and not any(p.rsplit("@", 1)[-1] == name for p in enabled):
        settings.get("extraKnownMarketplaces", {}).pop(name, None)
    return removed


def install_pack(pack: dict, settings: dict, messages: list[str]) -> tuple[dict[str, str], dict]:
    """Install a pack. Returns ({platform: status}, ownership record).

    Task 4 replaces this body with the full CLI-preferred resolution order; the
    signature is final.
    """
    owned = claude_install(pack, settings)
    if owned is None:
        return {}, dict(EMPTY_OWNED)
    return {"claude-code": "installed"}, owned
```

- [ ] **Step 4: Wire the mutating subcommands**

Replace `raise SystemExit(f"packs.py: '{args.command}' not implemented yet")` in `main()` with:

```python
    settings_file = settings_path(args)
    settings = load_settings(settings_file)
    state.setdefault("schema", 1)
    installed = state.setdefault("packs", {})
    messages: list[str] = []

    if args.command == "add":
        if args.slug not in packs:
            print(f"packs.py: unknown pack '{args.slug}'", file=sys.stderr)
            return 1
        platforms, owned = install_pack(packs[args.slug], settings, messages)
        previous = installed.get(args.slug, {})
        installed[args.slug] = {
            "platforms": platforms,
            # Union with any prior record so a second `add` — which inserts nothing —
            # cannot erase what the first one claimed.
            "owned": merge_owned(previous.get("owned", EMPTY_OWNED), owned),
            # Copied from the registry so removal survives the pack being dropped.
            "uninstall": {
                p: list((packs[args.slug].get("install", {}).get(p) or {}).get("uninstall", []))
                for p in PLATFORMS
            },
        }

    elif args.command == "remove":
        entry = installed.get(args.slug)
        if entry is None:
            print(f"packs.py: pack '{args.slug}' is not installed", file=sys.stderr)
            return 1
        remove_pack(entry, settings, messages)
        installed.pop(args.slug, None)

    elif args.command == "sync":
        for slug in sorted(installed):
            entry = installed[slug]
            if slug not in packs:
                claude_remove(entry.get("owned", EMPTY_OWNED), settings)
                installed.pop(slug, None)
                messages.append(f"{slug}: no longer declared — removed")
            elif entry.get("platforms", {}).get("claude-code") == "installed":
                owned = claude_install(packs[slug], settings)
                if owned:
                    entry["owned"] = merge_owned(entry.get("owned", EMPTY_OWNED), owned)

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

- [ ] **Step 5: Add the removal dispatcher**

Task 4 extends this with the shell-command platforms. Add above `main()`:

```python
def remove_pack(entry: dict, settings: dict, messages: list[str]) -> None:
    """Reverse a pack from its recorded state. Registry-independent by design."""
    platforms = entry.get("platforms", {})
    if platforms.get("claude-code") == "installed":
        claude_remove(entry.get("owned", EMPTY_OWNED), settings)
    for platform, how in sorted(platforms.items()):
        if how in ("cli", "manual"):
            messages.append(
                f"{platform}: installed outside 100xprism ({how}) — remove it with the "
                "upstream tooling. Skill files on disk were left untouched."
            )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `node --test test/packs-claude.test.js`
Expected: 10 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add adapters/lib/packs.py test/packs-claude.test.js
git commit -m "feat(packs): ownership-tracked install, remove, and sync for claude-code"
```

---

### Task 4: CLI-preferred install and the non-Claude platforms

**Files:**
- Modify: `adapters/lib/packs.py` (replace `install_pack`; extend `remove_pack`; add `which`, `run_command`)
- Test: `test/packs-install-paths.test.js`

**Interfaces:**
- Consumes: `claude_install`, `claude_remove`, `EMPTY_OWNED` from Task 3.
- Produces:
  - `which(binary: str) -> bool` — honours the `PRISM_PACKS_WHICH` JSON override
  - `run_command(command: str) -> tuple[int, str]` — honours `PRISM_PACKS_RUNNER_LOG`
  - `install_pack(pack, settings, messages) -> tuple[dict[str, str], dict]` — full resolution order
  - `remove_pack(entry, settings, messages) -> None` — now also runs recorded `uninstall` commands for shell-installed platforms
- Test hooks (production code, used by tests):
  - `PRISM_PACKS_WHICH` — JSON object mapping binary name to boolean, overriding `shutil.which`.
  - `PRISM_PACKS_RUNNER_LOG` — path; commands are appended one per line and **not** executed, returning exit 0.

- [ ] **Step 1: Write the failing test**

Create `test/packs-install-paths.test.js`:

```javascript
'use strict'

// Verifies the install resolution order in adapters/lib/packs.py — prefer the pack's
// own multi-agent CLI, else per-platform blocks — and that every recorded platform
// status has a defined removal transition.

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
  fs.writeFileSync(path.join(dir, 'settings.json'), '{}')
  return { dir, settingsFile: path.join(dir, 'settings.json'), log: path.join(dir, 'commands.log') }
}

function run(ctx, argv, whichMap, registry) {
  const r = spawnSync('python3', [
    SCRIPT, ...argv,
    '--settings', ctx.settingsFile, '--project', ctx.dir,
    '--packs', registry || REGISTRY, '--json',
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
  run(ctx, ['add', 'databricks'], { databricks: true })
  assert.deepEqual(commands(ctx), ['databricks aitools install'])
  assert.deepEqual(platforms(ctx), { 'claude-code': 'cli', cursor: 'cli', codex: 'cli' })
})

test('falls back to per-platform blocks when the CLI binary is missing', () => {
  const ctx = setup()
  const out = run(ctx, ['add', 'databricks'], { databricks: false, codex: true })
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
  const out = run(ctx, ['add', 'databricks'], { databricks: false, codex: false })
  assert.equal(platforms(ctx).codex, 'unavailable')
  assert.ok(out.messages.some((m) => m.includes('docs.databricks.com')), 'prints the hint')
})

test('removing a shell-installed platform prints guidance when no inverse is declared', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'], { databricks: false, codex: true })
  const out = run(ctx, ['remove', 'databricks'], { databricks: false, codex: true })
  assert.ok(
    out.messages.some((m) => m.startsWith('codex:') && /no uninstall command/i.test(m)),
    'codex installed-state is not silently forgotten',
  )
})

test('removing a shell-installed platform runs a declared inverse command', () => {
  const ctx = setup()
  const registry = path.join(ctx.dir, 'with-uninstall.json')
  const data = JSON.parse(fs.readFileSync(REGISTRY, 'utf8'))
  data.packs.databricks.install.codex.uninstall = ['codex plugin remove databricks']
  fs.writeFileSync(registry, JSON.stringify(data))

  run(ctx, ['add', 'databricks'], { databricks: false, codex: true }, registry)
  fs.writeFileSync(ctx.log, '')
  run(ctx, ['remove', 'databricks'], { databricks: false, codex: true }, registry)
  assert.deepEqual(commands(ctx), ['codex plugin remove databricks'])
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test test/packs-install-paths.test.js`
Expected: FAIL — the CLI path is not taken; `commands()` is empty.

- [ ] **Step 3: Implement the resolution order**

In `adapters/lib/packs.py`, add `import shlex` and `import shutil` to the imports, then add above `install_pack`:

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
    """Run a declared install/uninstall command.

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

Replace the Task 3 `install_pack` with:

```python
def install_pack(pack: dict, settings: dict, messages: list[str]) -> tuple[dict[str, str], dict]:
    """Install a pack, preferring the upstream's own multi-agent CLI.

    Returns ({platform: status}, ownership record), where status is one of:
      installed   — 100xprism performed it and can reverse it
      cli         — the pack's own CLI did it; not ours to reverse
      manual      — the user must run a command themselves
      unavailable — no usable path for that platform
    """
    install = pack.get("install", {})
    platforms: dict[str, str] = {}
    owned = dict(EMPTY_OWNED)
    cli = install.get("cli")

    # 1. The upstream CLI, when present, covers every platform in one command.
    if install.get("preferred") == "cli" and cli and which(cli["requires"]):
        code, err = run_command(cli["command"])
        if code == 0:
            for platform in cli.get("covers", []):
                platforms[platform] = "cli"
            messages.append(f"ran `{cli['command']}` — covers {', '.join(cli.get('covers', []))}")
            return platforms, owned
        messages.append(f"`{cli['command']}` failed ({err or f'exit {code}'}); falling back per platform")

    # 2. Per-platform blocks.
    for platform in PLATFORMS:
        block = install.get(platform)
        if not block:
            platforms[platform] = "unavailable"
            continue

        if platform == "claude-code":
            claimed = claude_install(pack, settings)
            if claimed is None:
                platforms[platform] = "unavailable"
            else:
                platforms[platform] = "installed"
                owned = merge_owned(owned, claimed)
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
            messages.append(f"{platform}: run this in your agent yourself — {', '.join(block['manual'])}")

    # 3. Nothing worked for some platform: surface the pack's own hint.
    if cli and cli.get("hint") and any(v == "unavailable" for v in platforms.values()):
        messages.append(cli["hint"])
    return platforms, owned
```

- [ ] **Step 4: Extend removal to shell-installed platforms**

Replace the Task 3 `remove_pack` with:

```python
def remove_pack(entry: dict, settings: dict, messages: list[str]) -> None:
    """Reverse a pack from its recorded state. Registry-independent by design.

    Every recorded status has a transition here — a shell-installed platform is never
    silently forgotten, even when the pack declares no inverse command.
    """
    platforms = entry.get("platforms", {})
    declared = entry.get("uninstall", {})

    for platform, how in sorted(platforms.items()):
        if how == "installed" and platform == "claude-code":
            claude_remove(entry.get("owned", EMPTY_OWNED), settings)
        elif how == "installed":
            commands = declared.get(platform) or []
            if not commands:
                messages.append(
                    f"{platform}: 100xprism ran the upstream installer, but this pack declares "
                    "no uninstall command — remove it with the upstream tooling. Skill files on "
                    "disk were left untouched."
                )
                continue
            for command in commands:
                code, err = run_command(command)
                if code != 0:
                    messages.append(f"{platform}: `{command}` failed ({err or f'exit {code}'})")
        elif how in ("cli", "manual"):
            messages.append(
                f"{platform}: installed outside 100xprism ({how}) — remove it with the "
                "upstream tooling. Skill files on disk were left untouched."
            )
        # `unavailable` needs no transition: nothing was installed.
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `node --test test/packs-install-paths.test.js test/packs-claude.test.js`
Expected: all tests PASS. The Task 3 suite still passes because it pins `PRISM_PACKS_WHICH` to `{"databricks": false}`, forcing the per-platform path.

- [ ] **Step 6: Commit**

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
- Modify: `AGENTS.md`, `docs/USAGE.md`, `install.sh` — only where they carry a stale count; `scripts/meta-check.py` names each offending file
- Test: `test/packs-module.test.js`

**Interfaces:**
- Consumes: the `packs.py` CLI from Tasks 2–4.
- Produces: a `/pack` slash command with `name: pack`, `tier: on-demand`, `model: haiku`.

- [ ] **Step 1: Write the failing test**

Create `test/packs-module.test.js`:

```javascript
'use strict'

// Verifies modules/pack/SKILL.md is a well-formed on-demand slash-command module that
// delegates to adapters/lib/packs.py, routes arguments through a validated case
// statement, and quotes them.

const { test } = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

const REPO = path.resolve(__dirname, '..')
const SKILL = path.join(REPO, 'modules', 'pack', 'SKILL.md')
const read = () => fs.readFileSync(SKILL, 'utf8')

test('frontmatter declares the expected routing', () => {
  const text = read()
  assert.match(text, /^---\n/)
  for (const line of ['name: pack', 'tier: on-demand', 'model: haiku', 'slash_command: /pack']) {
    assert.ok(text.includes(`\n${line}\n`), `frontmatter has "${line}"`)
  }
})

test('delegates to the helper rather than reimplementing install logic', () => {
  const text = read()
  assert.match(text, /adapters\/lib\/packs\.py/)
  assert.ok(!/enabledPlugins/.test(text), 'must not touch settings.json directly')
})

test('routes every subcommand through an explicit case statement', () => {
  const text = read()
  // Each supported invocation must appear as a case arm that assigns SUB.
  for (const [arm, sub] of [['""', 'status'], ['detect', 'detect'], ['add', 'add'], ['remove', 'remove']]) {
    const pattern = new RegExp(`${arm}\\)[^\\n]*SUB=["']?${sub}`)
    assert.match(text, pattern, `case arm ${arm} assigns SUB=${sub}`)
  }
  assert.match(text, /\*\)/, 'has a default arm that rejects unknown input')
})

test('quotes the slug when invoking the helper', () => {
  const text = read()
  assert.ok(!/\$SLUG(?!")/.test(text.replace(/"\$SLUG"/g, '')), 'SLUG is always quoted')
  assert.match(text, /"\$SLUG"/)
})

test('resolves the helper for npm-global installs too', () => {
  assert.match(read(), /npm root -g/)
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

## Step 2 — Route the argument

Pass the user's words through this case statement verbatim. Do not invent a
subcommand: anything unrecognised is a usage error, not a guess.

```bash
ARG1="${1:-}"
SLUG="${2:-}"
case "$ARG1" in
  "")       SUB="status" ;;
  detect)   SUB="detect" ;;
  add)      SUB="add" ;;
  remove)   SUB="remove" ;;
  *)        echo "Usage: /pack [detect | add <slug> | remove <slug>]"; exit 1 ;;
esac

if [ "$SUB" = "add" ] || [ "$SUB" = "remove" ]; then
  if [ -z "$SLUG" ]; then
    echo "Usage: /pack $SUB <slug>   (run /pack to list available slugs)"
    exit 1
  fi
fi
```

## Step 3 — Run it

`"$SLUG"` stays quoted so a slug can never split into extra arguments or inject a
flag into the helper.

```bash
python3 "$PACKS" "$SUB" "$SLUG" --settings "$HOME/.claude/settings.json"
```

## Step 4 — Report

Print the helper's output verbatim. It already says which platforms were handled and
which need a manual step.

If any pack was added or removed, finish with: **restart your agent to pick up the
change.**

Two things to pass along honestly rather than paper over:

- A platform marked `manual` was **not** installed. Give the user the exact command
  the helper printed.
- `/pack remove` reverses only what 100xprism wrote. A pack installed by an upstream
  CLI leaves its skill files on disk — say so; do not delete them.
````

- [ ] **Step 4: Update the counts**

Run `python3 scripts/meta-check.py`. It fails and names every file with a stale count. Update each to 68 modules / 28 slash commands. The auto-trigger-skills count stays 40 (`68 - 28`).

- [ ] **Step 5: Run tests to verify they pass**

Run: `node --test test/packs-module.test.js && python3 scripts/meta-check.py`
Expected: 6 tests PASS; meta-check reports `modules parsed: 68 (28 slash commands, 40 auto-trigger skills)` and `all checks passed ✓`.

If the trigger-overlap test fails on a `pack` ↔ `connect` pair, sharpen the two descriptions so they no longer share trigger vocabulary. Add to `scripts/trigger-overlap-allow.txt` only if the overlap is genuinely intentional — here it is not, so fix the descriptions.

- [ ] **Step 6: Commit**

```bash
git add modules/pack README.md package.json test/packs-module.test.js
git add -u
git commit -m "feat(packs): add the /pack module"
```

---

### Task 6: Lifecycle wiring — install, update, uninstall

**Files:**
- Modify: `adapters/claude-code.sh` (`packs.py sync` inside `install_plugins`, after the `sync_plugins.py` call at ~L145)
- Modify: `install.sh` (detection suggestion in the **final section**, after the component dispatch at ~L205)
- Modify: `update.sh` (`sync` beside each `sync_plugins.py` call at ~L216 and ~L294; detection once at the end)
- Modify: `lib/uninstall.js` (add `cleanManagedPacks`, call it from `run()` **only**, export it)
- Test: `test/packs-lifecycle.test.js`

**Interfaces:**
- Consumes: `packs.py sync`/`detect` and the state file from Tasks 2–4.
- Produces: `cleanManagedPacks(home = os.homedir()) -> { file, removed }` exported from `lib/uninstall.js`.

**Do NOT call `cleanManagedPacks` from `preinstallCleanup()`.** `install.sh:111` runs preinstall cleanup *before* `do_install_plugins` at `install.sh:202`, so wiring it there would delete every opted-in pack's state on each install and leave the later `sync` with nothing to restore. Uninstall only.

- [ ] **Step 1: Write the failing test**

Create `test/packs-lifecycle.test.js`:

```javascript
'use strict'

// Verifies uninstall reverses only 100xprism-managed pack entries, counts real
// removals, preserves unreadable settings, and never deletes third-party skill files.

const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const uninstall = require('../lib/uninstall.js')
const { cleanManagedPacks, preinstallCleanup } = uninstall
const PLUGIN = 'databricks@databricks-agent-skills'
const MARKET = 'databricks-agent-skills'

function fakeHome(state, settings) {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pkl-'))
  const claude = path.join(home, '.claude')
  fs.mkdirSync(path.join(claude, 'skills', 'databricks-core'), { recursive: true })
  fs.writeFileSync(path.join(claude, 'skills', 'databricks-core', 'SKILL.md'), '# upstream')
  fs.writeFileSync(
    path.join(claude, 'settings.json'),
    typeof settings === 'string' ? settings : JSON.stringify(settings),
  )
  if (state) fs.writeFileSync(path.join(claude, '.100xprism-packs.json'), JSON.stringify(state))
  return { home, claude }
}

const managedState = (owned) => ({
  schema: 1,
  packs: { databricks: { platforms: { 'claude-code': 'installed' }, owned, uninstall: {} } },
})

test('removes owned plugins and the state file', () => {
  const { home, claude } = fakeHome(
    managedState({ plugins: [PLUGIN], marketplace: MARKET }),
    { enabledPlugins: { [PLUGIN]: true, 'user-only@m': true }, extraKnownMarketplaces: { [MARKET]: {} } },
  )
  const result = cleanManagedPacks(home)
  const settings = JSON.parse(fs.readFileSync(path.join(claude, 'settings.json'), 'utf8'))

  assert.equal(result.removed, 1)
  assert.equal(PLUGIN in settings.enabledPlugins, false)
  assert.equal(settings.enabledPlugins['user-only@m'], true, 'user plugin preserved')
  assert.equal(MARKET in settings.extraKnownMarketplaces, false)
  assert.equal(fs.existsSync(path.join(claude, '.100xprism-packs.json')), false)
})

test('counts only plugins that were actually present', () => {
  // The owned record names a plugin that is no longer in settings — a bare `delete`
  // returns true for absent keys, so a naive counter would over-report here.
  const { home } = fakeHome(managedState({ plugins: [PLUGIN], marketplace: null }), { enabledPlugins: {} })
  assert.equal(cleanManagedPacks(home).removed, 0)
})

test('does not touch a plugin we never claimed', () => {
  const { home, claude } = fakeHome(
    managedState({ plugins: [], marketplace: null }),
    { enabledPlugins: { [PLUGIN]: false } },
  )
  cleanManagedPacks(home)
  const settings = JSON.parse(fs.readFileSync(path.join(claude, 'settings.json'), 'utf8'))
  assert.equal(settings.enabledPlugins[PLUGIN], false, 'user-disabled entry survives')
})

test('preserves an unreadable settings.json and keeps the state file for recovery', () => {
  const { home, claude } = fakeHome(managedState({ plugins: [PLUGIN], marketplace: MARKET }), '{ broken')
  const result = cleanManagedPacks(home)
  assert.equal(result.removed, 0)
  assert.equal(fs.readFileSync(path.join(claude, 'settings.json'), 'utf8'), '{ broken', 'untouched')
  assert.ok(fs.existsSync(path.join(claude, '.100xprism-packs.json')), 'state kept for recovery')
})

test('never deletes third-party skill files', () => {
  const { home, claude } = fakeHome(
    { schema: 1, packs: { databricks: { platforms: { 'claude-code': 'cli' }, owned: {}, uninstall: {} } } },
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
  assert.equal(cleanManagedPacks(home).removed, 0)
})

test('preinstallCleanup does not clear pack state', () => {
  // install.sh runs preinstall cleanup BEFORE installing plugins; clearing pack state
  // there would uninstall every opted-in pack on each install.
  assert.ok(!/cleanManagedPacks/.test(preinstallCleanup.toString()), 'not wired into preinstall')
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test test/packs-lifecycle.test.js`
Expected: FAIL — `cleanManagedPacks is not a function`.

- [ ] **Step 3: Implement `cleanManagedPacks`**

In `lib/uninstall.js`, add after `cleanClaudeSessionHooks`:

```javascript
// Reverse pack entries 100xprism recorded inserting. Packs installed by an upstream
// CLI are left alone — we did not write those files and do not know what else that
// CLI put there. Ownership comes from the state record, never from the registry.
function cleanManagedPacks(home = os.homedir()) {
  const claudeDir = path.join(home, '.claude')
  const stateFile = path.join(claudeDir, '.100xprism-packs.json')
  const settingsFile = path.join(claudeDir, 'settings.json')

  let state
  try {
    state = JSON.parse(fs.readFileSync(stateFile, 'utf8'))
  } catch (err) {
    if (!err || err.code !== 'ENOENT') {
      console.warn(`Warning: could not read ${stateFile}: ${err.message}`)
    }
    return { file: settingsFile, removed: 0 }
  }

  let settings
  try {
    settings = JSON.parse(fs.readFileSync(settingsFile, 'utf8'))
  } catch (err) {
    if (err && err.code === 'ENOENT') {
      fs.rmSync(stateFile, { force: true })
      return { file: settingsFile, removed: 0 }
    }
    // Malformed settings: leave BOTH files alone so the user can recover.
    console.warn(`Warning: ${settingsFile} could not be parsed — leaving pack entries in place.`)
    return { file: settingsFile, removed: 0 }
  }

  const enabled = settings.enabledPlugins || {}
  const marketplaces = settings.extraKnownMarketplaces || {}
  let removed = 0

  for (const entry of Object.values(state.packs || {})) {
    if ((entry.platforms || {})['claude-code'] !== 'installed') continue
    const owned = entry.owned || {}
    for (const plugin of owned.plugins || []) {
      // `delete` returns true even for absent keys, so check ownership explicitly.
      if (Object.prototype.hasOwnProperty.call(enabled, plugin)) {
        delete enabled[plugin]
        removed += 1
      }
    }
    const name = owned.marketplace
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

Call it from `run()` only, right after `const hookCleanup = cleanSessionHooksOnly()`:

```javascript
  const packCleanup = cleanManagedPacks()
  if (packCleanup.removed) {
    console.log(`Removed ${packCleanup.removed} 100xprism-managed pack plugin(s) from ${packCleanup.file}.`)
    console.log('Packs installed by an upstream CLI were left in place — remove those with their own tooling.')
  }
```

Add `&& !packCleanup.removed` to the "nothing found" guard on the following line, and add `cleanManagedPacks` to `module.exports`. Leave `preinstallCleanup()` unchanged.

- [ ] **Step 4: Wire sync into install and update**

In `adapters/claude-code.sh`, inside `install_plugins`, after the `sync_plugins.py` invocation and before the `Plugins merged` echo:

```bash
  # Re-apply opted-in packs and prune any dropped from packs.json.
  python3 "$REPO_DIR/adapters/lib/packs.py" sync --settings "$SETTINGS_FILE" || \
    echo -e "  ${YELLOW}→ Pack sync failed — run /pack to check pack state${NC}"
```

In `update.sh`, add the same block after **each** of the two `sync_plugins.py` invocations (~L216 and ~L294), using that file's existing `$SETTINGS_FILE`.

- [ ] **Step 5: Wire detection where every install sees it**

`install_plugins` runs only when the user selects both Claude Code and the plugins component (`install.sh:202`), so detection must not live there. Add it to `install.sh`'s final section, after the component dispatch (~L205) and before the `✓ Done!` banner:

```bash
# Read-only: reports packs relevant to this project. Never installs.
SUGGESTIONS=$(python3 "$REPO_DIR/adapters/lib/packs.py" detect \
  --settings "$HOME/.claude/settings.json" 2>/dev/null || true)
if [ -n "$SUGGESTIONS" ]; then
  echo ""
  echo -e "${CYAN}Optional skill packs for this project:${NC}"
  echo "$SUGGESTIONS"
  echo -e "${CYAN}Install with: /pack add <slug>${NC}"
fi
```

Add the same block at the end of `update.sh`.

- [ ] **Step 6: Run the full suite**

Run: `node --test && python3 scripts/meta-check.py`
Expected: every test PASSES (104 existing + the six new suites); meta-check clean.

- [ ] **Step 7: Verify the install path end-to-end in a throwaway HOME**

`./adapters/claude-code.sh` with no arguments dispatches to `install_global`, which never reaches `install_plugins`. Use the `--plugins` entry point:

```bash
HOME=$(mktemp -d) ./adapters/claude-code.sh --plugins
```

Expected: exit 0, no traceback, and a `Pack sync` line that installs nothing (no pack is in state, so `sync` is a no-op).

- [ ] **Step 8: Commit**

```bash
git add adapters/claude-code.sh install.sh update.sh lib/uninstall.js test/packs-lifecycle.test.js
git commit -m "feat(packs): wire pack sync and detection into install, update, uninstall"
```

---

## Self-review notes

- **Spec coverage.** Registry → Task 1. Detection (root-only, git-toplevel resolution) → Task 2. Ownership-tracked Claude Code install/remove/sync and strict settings handling → Task 3. CLI-preferred resolution, all four platform statuses, Codex removal transition → Task 4. `/pack` module, argument routing, count updates → Task 5. Lifecycle wiring, non-destructive removal, detection reach → Task 6.
- **Deferred deliberately:** the per-platform `uninstall` array is implemented (Task 4) but left unset for `databricks`, because upstream documents no uninstall command. Task 4's last test proves the mechanism against a temp registry that declares one.
- **State-machine coverage.** Every `platforms[p]` value has a defined removal transition: `installed`+`claude-code` → `claude_remove` from the ownership record; `installed`+shell platform → declared inverse commands, else explicit guidance; `cli`/`manual` → guidance; `unavailable` → no-op (nothing was installed).
- **Naming consistency:** `load_registry`, `load_state`, `load_settings`, `project_root`, `pack_matches`, `settings_path`, `state_path`, `describe`, `render`, `write_json`, `merge_owned`, `claude_install`, `claude_remove`, `install_pack`, `remove_pack`, `which`, `run_command` are each defined once and used with the same signature throughout. `install_pack` returns `(platforms, owned)` in both Task 3 and Task 4.

## Review history

Reviewed by Codex (`--sandbox read-only`) and Cursor (`composer-2.5`, ask mode) against the repo. Twelve findings, all verified against the actual code and all fixed in this revision:

| # | Severity | Finding | Fix |
| --- | --- | --- | --- |
| 1 | Critical | Fixtures under `scripts/fixtures/` resolve to the repo root via `git rev-parse`, so detection tests could never pass | Fixtures built in temp dirs at test time; added a git-toplevel test |
| 2 | Critical | Wiring `cleanManagedPacks` into `preinstallCleanup` would wipe opted-in packs on every install | Uninstall-only, with a test asserting it is not wired into preinstall |
| 3 | Critical | Platform-level ownership let `remove` delete plugins and marketplaces the user owned | Per-entry ownership record; `claude_install` returns only what it inserted |
| 4 | High | `if (delete enabled[plugin])` over-counts — JS `delete` returns `true` for absent keys | Explicit `hasOwnProperty` check before deleting |
| 5 | High | Malformed `settings.json` collapsed to `{}` and written back, destroying user config | `load_settings` aborts; `cleanManagedPacks` preserves both files |
| 6 | High | `remove` consulted the registry, so a dropped pack became unremovable | `remove_pack` works from the state record only |
| 7 | High | Codex `installed` had no removal transition | `remove_pack` runs declared inverse commands, else prints guidance |
| 8 | High | First-run seeding promised in constraints but neither applicable nor implemented | Removed from spec and plan — opt-in packs have nothing to seed |
| 9 | Medium | `/pack` used undefined, unquoted `$SUB`/`$SLUG` | Explicit case statement, usage errors, quoted `"$SLUG"`, tests assert routing |
| 10 | Medium | Schema tests mutated the tracked registry; `node --test` runs 4 files concurrently | `--packs` override validates a temp copy |
| 11 | Medium | Detection lived in `install_plugins`, invisible to Cursor-only/Codex-only installs | Moved to the final section of `install.sh` and `update.sh` |
| 12 | Medium | `./adapters/claude-code.sh` dispatches to `install_global`, so the E2E step tested nothing | Uses the `--plugins` entry point |
