# Release — Local Gate → Install Test → Version Bump → Tag → Publish → Verify

You are a release engineer. Execute each phase in order. Each must fully complete before advancing. Do NOT ask for permission. Do NOT skip phases.

## Usage

```
/release patch    # 1.2.3 → 1.2.4
/release minor    # 1.2.3 → 1.3.0
/release major    # 1.2.3 → 2.0.0
/release 1.4.0    # explicit version
```

If no argument is given, ask: `patch, minor, or major?`

---

## Phase 0 — Detect registries

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"

[ -f pyproject.toml ] || [ -f setup.py ] && PYPI=true || PYPI=false
[ -f package.json ] && node -e "const d=require('./package.json'); process.exit(d.private ? 1 : 0)" 2>/dev/null && NPM=true || NPM=false
[ -f Dockerfile ] && DOCKER=true || DOCKER=false
```

Print detected registries before continuing:

```
Detected registries:
  PyPI:       true | false
  npm:        true | false
  Docker:     true | false
```

---

## Phase 1 — Quality Gate (MANDATORY)

Run the **gate** workflow. All gates must pass. **If any gate fails → STOP. Do not continue.**

Only continue when gate shows: `✅ ALL GATES PASSED`

---

## Phase 2 — Confirm current version

Print current → new version before proceeding. Do not proceed without confirming the version transition is correct.

```bash
python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])" 2>/dev/null || true
node -e "console.log(require('./package.json').version)" 2>/dev/null || true
```

Print:
```
Current version: X.Y.Z
New version:     A.B.C
```

---

## Phase 3 — Build packages locally

### PyPI (if PYPI=true)

```bash
pip install build twine --quiet
python -m build
twine check dist/*
```

GATE: `twine check` must report PASSED for all distributions. If it fails → STOP.

### npm (if NPM=true)

```bash
npm pack --dry-run
```

GATE: must complete with no errors. If it fails → STOP.

### Docker (if DOCKER=true)

```bash
docker build -t "$(basename $PROJECT_ROOT):release-candidate" .
```

GATE: build must succeed. If it fails → STOP.

---

## Phase 4 — Local install smoke test (BEFORE tagging)

This is the most important phase. It catches broken imports, missing files, and broken CLI entrypoints BEFORE anything is published.

### PyPI smoke test (if PYPI=true)

```bash
python3 -m venv /tmp/release-test-venv
/tmp/release-test-venv/bin/pip install dist/*.whl --quiet
PACKAGE_NAME=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['name'].replace('-','_'))")
/tmp/release-test-venv/bin/python -c "import $PACKAGE_NAME; print('Import OK')"
CLI_CMD=$(python3 -c "import tomllib; scripts=tomllib.load(open('pyproject.toml','rb')).get('project',{}).get('scripts',{}); print(list(scripts.keys())[0] if scripts else '')" 2>/dev/null)
[ -n "$CLI_CMD" ] && /tmp/release-test-venv/bin/$CLI_CMD --version || echo "No CLI entrypoint"
rm -rf /tmp/release-test-venv
```

### Docker smoke test (if DOCKER=true)

```bash
IMAGE="$(basename $PROJECT_ROOT):release-candidate"
docker run --rm "$IMAGE" --version 2>/dev/null || \
docker run --rm "$IMAGE" --help 2>/dev/null || \
docker run --rm "$IMAGE" echo "container starts OK"
```

**GATE: All smoke tests must pass. If any fail → STOP. Fix the package, re-run from Phase 3.**

Print summary:

```
Phase 4 Smoke Tests:
  PyPI install:   ✅ PASSED | ❌ FAILED
  Docker run:     ✅ PASSED | ❌ FAILED | ⬜ skipped
```

---

## Phase 5 — Bump version

### pyproject.toml (if PYPI=true)

```bash
OLD_VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
sed -i.bak "s/^version = \"$OLD_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml && rm pyproject.toml.bak
```

### package.json (if NPM=true)

```bash
npm version $NEW_VERSION --no-git-tag-version
```

Verify the bump applied by printing the new version from each file.

---

## Phase 6 — Update CHANGELOG

```bash
if [ -f CHANGELOG.md ]; then
  TODAY=$(date +%Y-%m-%d)
  # Rename [Unreleased] header to versioned header
  sed -i.bak "s/^## \[Unreleased\]/## [$NEW_VERSION] - $TODAY/" CHANGELOG.md
  # Insert new [Unreleased] section above the versioned header
  sed -i.bak "/^## \[$NEW_VERSION\]/i\\
## [Unreleased]\\
\\
" CHANGELOG.md
  rm -f CHANGELOG.md.bak
  echo "CHANGELOG.md updated for v$NEW_VERSION"
else
  echo "No CHANGELOG.md — skipping"
fi
```

---

## Phase 7 — Commit version bump + tag

```bash
git add pyproject.toml package.json CHANGELOG.md 2>/dev/null || true
git add -u
git commit -m "$(cat <<'EOF'
chore(release): bump version to $NEW_VERSION

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
git tag -a "v$NEW_VERSION" -m "Release v$NEW_VERSION"
git log --oneline -2
```

---

## Phase 8 — Push tag

```bash
git push origin main
git push origin "v$NEW_VERSION"
```

Print: `Tag v$NEW_VERSION pushed → CI release pipeline triggered`

---

## Phase 9 — Watch CI release run

```bash
sleep 10
RUN_ID=$(gh run list --workflow=release.yml --limit 1 --json databaseId -q '.[0].databaseId' 2>/dev/null)
[ -n "$RUN_ID" ] && gh run watch "$RUN_ID" || echo "No release.yml found — check manually: gh run list --limit 5"
```

If CI fails: read logs with `gh run view "$RUN_ID" --log | tail -100`, fix locally, push fix to main (do NOT re-tag). Max 3 attempts, then escalate with full diagnosis.

```
CI FAILED — Attempt N/3
Failure:  [error summary]
Fix:      [what was done]
Action:   Committing fix, pushing to main...
```

After 3 failed attempts → STOP and escalate:

```
╔══════════════════════════════════════════════════════╗
║         CI RELEASE FAILED — ESCALATING TO HUMAN     ║
╠══════════════════════════════════════════════════════╣
║ Attempts:   N/3 exhausted                            ║
║ Last error: [error summary]                          ║
║ Diagnosis:  [root cause analysis]                    ║
║ Suggestion: [recommended fix]                        ║
╠══════════════════════════════════════════════════════╣
║ This requires human judgment. Auto-fix not possible. ║
╚══════════════════════════════════════════════════════╝
```

---

## Phase 10 — Post-release verification (from live registry)

After CI passes, verify packages are installable from the live registry.

### PyPI (if PYPI=true)

```bash
sleep 60
python3 -m venv /tmp/pypi-verify-venv
/tmp/pypi-verify-venv/bin/pip install "$PACKAGE_NAME==$NEW_VERSION" --quiet
/tmp/pypi-verify-venv/bin/python -c "import $PACKAGE_NAME; print('PyPI install verified OK')"
rm -rf /tmp/pypi-verify-venv
```

### Docker Hub (if DOCKER=true)

```bash
DOCKER_REPO=$(grep -m1 'DOCKERHUB_REPO' .env.release 2>/dev/null | cut -d= -f2 || echo "")
[ -n "$DOCKER_REPO" ] && docker pull "$DOCKER_REPO:$NEW_VERSION" && docker run --rm "$DOCKER_REPO:$NEW_VERSION" --version || echo "Docker Hub verify skipped — set DOCKERHUB_REPO in .env.release"
```

---

## Output

```
╔══════════════════════════════════════════════════════╗
║              RELEASE COMPLETE                        ║
╠══════════════════════════════════════════════════════╣
║ Version:       v$NEW_VERSION                         ║
║ Tag:           ✅ pushed                             ║
║ CI:            ✅ release.yml passed                 ║
╠══════════════════════════════════════════════════════╣
║ Registries published:                                ║
║   PyPI:        ✅ verified installable               ║
║   npm:         ✅ verified | ⬜ skipped               ║
║   Docker Hub:  ✅ verified | ⬜ skipped               ║
║   Homebrew:    ✅ tap updated | ⬜ skipped            ║
╠══════════════════════════════════════════════════════╣
║ STATUS: RELEASED ✅                                  ║
╚══════════════════════════════════════════════════════╝
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `twine check` fails | Fix metadata in `pyproject.toml` |
| PyPI smoke test fails (ImportError) | Missing file in `[tool.setuptools] packages` |
| Docker smoke test fails | Add `CMD ["--version"]` to Dockerfile |
| Version already exists on PyPI | PyPI versions are immutable — bump again, create new tag |
| CI release run not found | Workflow must be named `release.yml` triggered on `push: tags: ["v*.*.*"]` |
| Homebrew update fails | `HOMEBREW_TAP_TOKEN` secret not set |
