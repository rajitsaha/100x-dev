# Release Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/release` workflow to 100x-dev that handles local pre-release testing, version bumping, tagging, publishing to npm/PyPI/Docker Hub, post-release verification, and a GitHub Actions CI workflow file template — all auto-detected from what's in the repo.

**Architecture:** Single `workflows/release.md` workflow file following the same phase-based pattern as `/push`, `/launch`, and `/commit`. Auto-detects which registries apply (npm, PyPI, Docker Hub) by inspecting repo contents. Includes a companion `github-actions/release.yml` template that projects can copy into `.github/workflows/`. The workflow covers: local install smoke test before tagging, version bump, tag, push, watch CI release run, post-release verification from live registry.

**Tech Stack:** Bash, `gh` CLI, `pip`/`twine`, `npm`, Docker CLI, `git`, GitHub Actions YAML

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `workflows/release.md` | **Create** | The `/release` slash command workflow |
| `github-actions/release.yml` | **Create** | Reusable GitHub Actions release pipeline template |
| `README.md` | **Modify** | Add `/release` to the workflow table |

---

## Task 1: Create the `/release` workflow file

**Files:**
- Create: `workflows/release.md`

- [ ] **Step 1: Create `workflows/release.md` with the following content**

The file should contain these phases in order:

**Header:**
```
# Release — Local Gate → Install Test → Version Bump → Tag → Publish → Verify

You are a release engineer. Execute each phase in order. Each must fully complete before advancing. Do NOT ask for permission. Do NOT skip phases.
```

**Usage section:**
```
## Usage

/release patch    # 1.2.3 → 1.2.4
/release minor    # 1.2.3 → 1.3.0
/release major    # 1.2.3 → 2.0.0
/release 1.4.0    # explicit version

If no argument is provided, ask: patch, minor, or major?
```

**Phase 0 — Detect registries:**
Run these checks and print a summary of which registries will be targeted:
```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"

[ -f pyproject.toml ] || [ -f setup.py ] && PYPI=true || PYPI=false
[ -f package.json ] && node -e "const d=require('./package.json'); process.exit(d.private ? 1 : 0)" 2>/dev/null && NPM=true || NPM=false
[ -f Dockerfile ] && DOCKER=true || DOCKER=false
```
Print: `Detected registries: PyPI ✅ | npm ✅ | Docker Hub ✅ | Homebrew ⬜`

**Phase 1 — Quality Gate (MANDATORY):**
Run the **gate** workflow. All gates must pass. If any gate fails → STOP. Only continue when gate shows `✅ ALL GATES PASSED`.

**Phase 2 — Confirm current version:**
```bash
# Python
python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])" 2>/dev/null || true
# npm
node -e "console.log(require('./package.json').version)" 2>/dev/null || true
```
Print current version and new version before proceeding.

**Phase 3 — Build packages locally:**

PyPI:
```bash
pip install build twine --quiet
python -m build
twine check dist/*
```
GATE: `twine check` must report PASSED.

npm:
```bash
npm pack --dry-run
```
GATE: must complete with no errors.

Docker:
```bash
docker build -t "$(basename $PROJECT_ROOT):release-candidate" .
```
GATE: build must succeed.

**Phase 4 — Local install smoke test (BEFORE tagging):**

PyPI smoke test:
```bash
python3 -m venv /tmp/release-test-venv
/tmp/release-test-venv/bin/pip install dist/*.whl --quiet
PACKAGE_NAME=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['name'].replace('-','_'))")
/tmp/release-test-venv/bin/python -c "import $PACKAGE_NAME; print('Import OK')"
CLI_CMD=$(python3 -c "import tomllib; scripts=tomllib.load(open('pyproject.toml','rb')).get('project',{}).get('scripts',{}); print(list(scripts.keys())[0] if scripts else '')" 2>/dev/null)
[ -n "$CLI_CMD" ] && /tmp/release-test-venv/bin/$CLI_CMD --version || echo "No CLI entrypoint"
rm -rf /tmp/release-test-venv
```

Docker smoke test:
```bash
IMAGE="$(basename $PROJECT_ROOT):release-candidate"
docker run --rm "$IMAGE" --version 2>/dev/null || \
docker run --rm "$IMAGE" --help 2>/dev/null || \
docker run --rm "$IMAGE" echo "container starts OK"
```

GATE: All smoke tests must pass. If any fail → STOP. Fix the package, re-run from Phase 3.

Print summary:
```
Phase 4 Smoke Tests:
  PyPI install:   ✅ PASSED | ❌ FAILED
  Docker run:     ✅ PASSED | ❌ FAILED | ⬜ skipped
```

**Phase 5 — Bump version:**

pyproject.toml:
```bash
OLD_VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
sed -i.bak "s/^version = \"$OLD_VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml && rm pyproject.toml.bak
```

package.json (if npm):
```bash
npm version $NEW_VERSION --no-git-tag-version
```

Verify bump applied by printing the new version from each file.

**Phase 6 — Update CHANGELOG:**
If `CHANGELOG.md` exists: rename `[Unreleased]` section to `[$NEW_VERSION] - $(date +%Y-%m-%d)` and add a new empty `[Unreleased]` section above it. If no CHANGELOG, skip.

**Phase 7 — Commit version bump + tag:**
```bash
git add pyproject.toml package.json CHANGELOG.md 2>/dev/null || true
git add -u
git commit -m "chore(release): bump version to $NEW_VERSION"
git tag -a "v$NEW_VERSION" -m "Release v$NEW_VERSION"
git log --oneline -2
```

**Phase 8 — Push tag:**
```bash
git push origin main
git push origin "v$NEW_VERSION"
```
Print: `Tag v$NEW_VERSION pushed → CI release pipeline triggered`

**Phase 9 — Watch CI release run:**
```bash
sleep 10
RUN_ID=$(gh run list --workflow=release.yml --limit 1 --json databaseId -q '.[0].databaseId' 2>/dev/null)
[ -n "$RUN_ID" ] && gh run watch "$RUN_ID" || echo "No release.yml found — check manually: gh run list --limit 5"
```

If CI fails: read logs with `gh run view "$RUN_ID" --log | tail -100`, fix locally, push fix to main (do NOT re-tag). Max 3 attempts then escalate.

**Phase 10 — Post-release verification (from live registry):**

PyPI:
```bash
sleep 60
python3 -m venv /tmp/pypi-verify-venv
/tmp/pypi-verify-venv/bin/pip install "$PACKAGE_NAME==$NEW_VERSION" --quiet
/tmp/pypi-verify-venv/bin/python -c "import $PACKAGE_NAME; print('PyPI install verified OK')"
rm -rf /tmp/pypi-verify-venv
```

Docker Hub:
```bash
DOCKER_REPO=$(grep -m1 'DOCKERHUB_REPO' .env.release 2>/dev/null | cut -d= -f2 || echo "")
[ -n "$DOCKER_REPO" ] && docker pull "$DOCKER_REPO:$NEW_VERSION" && docker run --rm "$DOCKER_REPO:$NEW_VERSION" --version || echo "Docker Hub verify skipped — set DOCKERHUB_REPO in .env.release"
```

**Summary output:**
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

**Troubleshooting table:**

| Problem | Fix |
|---|---|
| `twine check` fails | Fix metadata in `pyproject.toml` — check description, classifiers, urls |
| PyPI smoke test fails (ImportError) | Missing file in `[tool.setuptools] packages` — check find: config |
| Docker smoke test fails | Add `CMD ["--version"]` or `ENTRYPOINT` to your Dockerfile |
| Version already exists on PyPI | PyPI versions are immutable — bump again, create new tag |
| CI release run not found | Workflow file must be named `release.yml` triggered on `push: tags: ["v*.*.*"]` |
| Homebrew update fails | `HOMEBREW_TAP_TOKEN` secret not set in repo settings |

- [ ] **Step 2: Verify file was created**

```bash
ls -la workflows/release.md
wc -l workflows/release.md
```

Expected: file exists, 150+ lines.

- [ ] **Step 3: Commit**

```bash
git add workflows/release.md
git commit -m "feat(workflow): add /release workflow — local smoke test, version bump, tag, publish, verify"
```

---

## Task 2: Create GitHub Actions `release.yml` template

**Files:**
- Create: `github-actions/release.yml`

This is a drop-in template that project owners copy to `.github/workflows/release.yml`.

- [ ] **Step 1: Create `github-actions/` directory**

```bash
mkdir -p github-actions
```

- [ ] **Step 2: Create `github-actions/release.yml`**

The file must contain these jobs in dependency order:

```
pre-release-checks
  → build-python (if pyproject.toml)
  → build-npm    (if package.json)
  → build-docker (if Dockerfile)
      → github-release
          → publish-pypi
          → publish-npm
              → verify-releases
                  → update-homebrew
```

**Job: `pre-release-checks`** — runs on `ubuntu-latest`, steps:
1. `actions/checkout@v4`
2. Set up Python 3.12 (conditional: `if: hashFiles('pyproject.toml') != ''`)
3. `pip install -e ".[dev]"` → `ruff check .` → `ruff format --check .` → `pytest tests/unit/ -v` → `coverage report --fail-under=95`
4. Set up Node 22 (conditional: `if: hashFiles('package.json') != ''`)
5. `npm ci` → `npm run lint` → `npm test`
6. Version consistency check for pyproject.toml:
```bash
TAG_VERSION="${GITHUB_REF#refs/tags/v}"
PKG_VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")
[ "$TAG_VERSION" = "$PKG_VERSION" ] || (echo "Tag $TAG_VERSION != pyproject.toml $PKG_VERSION" && exit 1)
```
7. Version consistency check for package.json:
```bash
TAG_VERSION="${GITHUB_REF#refs/tags/v}"
PKG_VERSION=$(node -e "console.log(require('./package.json').version)")
[ "$TAG_VERSION" = "$PKG_VERSION" ] || (echo "Tag $TAG_VERSION != package.json $PKG_VERSION" && exit 1)
```

**Job: `build-python`** — `needs: pre-release-checks`, `if: hashFiles('pyproject.toml') != ''`, steps:
1. checkout, setup-python 3.12
2. `pip install build twine --quiet && python -m build && twine check dist/*`
3. Smoke test in fresh venv:
```bash
python3 -m venv /tmp/smoke-venv
/tmp/smoke-venv/bin/pip install dist/*.whl --quiet
PACKAGE=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['name'].replace('-','_'))")
/tmp/smoke-venv/bin/python -c "import $PACKAGE; print('Import OK')"
rm -rf /tmp/smoke-venv
```
4. `actions/upload-artifact@v4` → `name: python-dist`, `path: dist/`

**Job: `build-npm`** — `needs: pre-release-checks`, `if: hashFiles('package.json') != ''`, steps:
1. checkout, setup-node 22 with `registry-url: https://registry.npmjs.org`
2. `npm ci` → `npm run build --if-present` → `npm pack --dry-run`
3. `actions/upload-artifact@v4` → `name: npm-dist`, `path: "*.tgz"`

**Job: `build-docker`** — `needs: pre-release-checks`, `if: hashFiles('Dockerfile') != ''`, steps:
1. checkout
2. Extract version: `echo "version=${GITHUB_REF#refs/tags/v}" >> $GITHUB_OUTPUT`
3. `docker/setup-buildx-action@v3`
4. Login to Docker Hub with `secrets.DOCKERHUB_USERNAME` / `secrets.DOCKERHUB_TOKEN`
5. Login to GHCR with `github.actor` / `secrets.GITHUB_TOKEN`
6. `docker/build-push-action@v6` with:
   - `push: true`
   - `platforms: linux/amd64,linux/arm64`
   - tags: `ghcr.io/${{ github.repository }}:${{ steps.version.outputs.version }}`, `:latest`, `${{ secrets.DOCKERHUB_USERNAME }}/${{ github.event.repository.name }}:${{ steps.version.outputs.version }}`, `:latest`
   - `cache-from: type=gha`, `cache-to: type=gha,mode=max`

**Job: `github-release`** — `needs: [build-python, build-npm, build-docker]`, `if: always() && needs.pre-release-checks.result == 'success'`, steps:
1. checkout with `fetch-depth: 0`
2. Extract version
3. Extract changelog section using awk between version headers
4. `actions/download-artifact@v4` → `path: release-artifacts/`, `merge-multiple: true`
5. `softprops/action-gh-release@v2` with name, body from changelog, files from artifacts, prerelease detection for `-rc`/`-beta`/`-alpha`

**Job: `publish-pypi`** — `needs: github-release`, `if: needs.build-python.result == 'success'`, environment `pypi`, `permissions: id-token: write`:
1. Download artifact `python-dist` → `path: dist/`
2. `pypa/gh-action-pypi-publish@release/v1`

**Job: `publish-npm`** — `needs: github-release`, `if: needs.build-npm.result == 'success'`:
1. checkout, setup-node 22 with `registry-url: https://registry.npmjs.org`
2. `npm ci` → `npm publish --access public` with `NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}`

**Job: `verify-releases`** — `needs: [publish-pypi, publish-npm]`, `if: always() && needs.github-release.result == 'success'`:
1. Extract version
2. `sleep 60` for PyPI propagation (if publish-pypi succeeded)
3. Install from PyPI and verify import:
```bash
PACKAGE=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['name'])")
pip install "$PACKAGE==${{ steps.version.outputs.version }}"
PACKAGE_IMPORT=$(echo $PACKAGE | tr '-' '_')
python3 -c "import $PACKAGE_IMPORT; print('PyPI verified ✅')"
```
4. `sleep 30` for npm propagation (if publish-npm succeeded)
5. npm verify: `npm install "$PKG@$VERSION" --dry-run` where PKG comes from package.json
6. Docker pull verify: `docker pull $DOCKERHUB_USERNAME/$REPO:$VERSION`

**Job: `update-homebrew`** — `needs: verify-releases`, `if: env.HOMEBREW_TAP != ''`:
1. `sleep 30`
2. `mislav/bump-homebrew-formula-action@v3` with `formula-name: ${{ github.event.repository.name }}`, `homebrew-tap: ${{ vars.HOMEBREW_TAP }}`, `COMMITTER_TOKEN: ${{ secrets.HOMEBREW_TAP_TOKEN }}`

**File header comment (top of file):**
```yaml
# 100x Dev — Release Pipeline Template
# Copy to .github/workflows/release.yml in your project.
#
# Required secrets (GitHub repo Settings → Secrets):
#   DOCKERHUB_USERNAME    — Docker Hub username (if using Docker)
#   DOCKERHUB_TOKEN       — Docker Hub access token (if using Docker)
#   NPM_TOKEN             — npm publish token (if using npm)
#   HOMEBREW_TAP_TOKEN    — PAT with repo scope for homebrew tap (optional)
#
# Required variables (GitHub repo Settings → Variables):
#   HOMEBREW_TAP          — e.g. "yourorg/homebrew-tap" (optional)
#
# PyPI: uses OIDC trusted publishing — no API key needed.
# Configure at: https://pypi.org/manage/account/publishing/
```

- [ ] **Step 3: Verify file was created**

```bash
ls -la github-actions/release.yml
wc -l github-actions/release.yml
```

Expected: file exists, 200+ lines.

- [ ] **Step 4: Commit**

```bash
git add github-actions/release.yml
git commit -m "feat(github-actions): add release.yml CI template — build, smoke test, publish, verify for PyPI/npm/Docker/Homebrew"
```

---

## Task 3: Update README workflow table

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add `/release` row to the workflow table**

Find the `**launch**` row in the workflow table and insert a new row after it:

```markdown
| **release** | Full release pipeline: local smoke test → version bump → tag → publish to PyPI/npm/Docker Hub → verify from live registry. |
```

- [ ] **Step 2: Add GitHub Actions template section**

After the existing Templates section, add a new section:

```markdown
## GitHub Actions Template

A production-ready release pipeline is included — copy it into any project:

```bash
mkdir -p .github/workflows
cp ~/100x-dev/github-actions/release.yml .github/workflows/release.yml
```

Covers: pre-release checks (lint, tests, 95% coverage, version consistency), build + local smoke test, publish to PyPI/npm/Docker Hub/GHCR, post-release verification from live registry, Homebrew tap update.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add /release workflow and github-actions template to README"
```

---

## Task 4: Run install.sh to propagate to local tools

- [ ] **Step 1: Run installer**

```bash
cd ~/100x-dev && ./install.sh
```

Select the same tools as the previous install.

- [ ] **Step 2: Verify `/release` is available in Claude Code**

```bash
ls ~/.claude/commands/ | grep release
```

Expected: `release.md` appears.

- [ ] **Step 3: Commit any install-generated changes**

```bash
cd ~/100x-dev
git status
# Only commit if something changed
```

---

## Self-Review

- [x] **Spec coverage:** All phases covered — detect, gate, build, local smoke, bump, tag, push, watch CI, post-release verify.
- [x] **No placeholders:** All phases have concrete bash commands. No TBDs.
- [x] **GitHub Actions template:** Matches phases in release.md. Version consistency check, 95% coverage gate, smoke test, OIDC for PyPI, post-release verify job.
- [x] **README:** Both workflow table row and GitHub Actions template section included.
- [x] **Install step:** Task 4 propagates to local tools immediately.
