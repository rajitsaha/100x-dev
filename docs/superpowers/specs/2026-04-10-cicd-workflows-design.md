# CI/CD Workflow Enhancements Design

**Date:** 2026-04-10
**Status:** Approved
**Scope:** Add branch creation and PR workflows, enhance push.md with auto-fix CI failures, enhance launch.md with deployment verification and auto-rollback.

---

## Overview

Fill critical gaps in the 100x Dev workflow system: branch management, PR creation with AI review, automated CI failure remediation, and deployment verification with auto-rollback. All workflows are language-agnostic — detect tools from the project, never hardcode to a specific stack.

---

## New Workflow: `branch.md`

### Purpose

Create feature branches from main with descriptive auto-generated names.

### Behavior

1. Detect current branch
2. If not on main/master, warn and confirm intent
3. Pull latest from main/master
4. Generate branch name from task description using conventional prefixes:
   - `feat/` — new feature
   - `fix/` — bug fix
   - `chore/` — maintenance, deps, config
   - `refactor/` — code restructuring
   - `docs/` — documentation only
   - `test/` — test additions/fixes
5. Create branch: `git checkout -b <prefix>/<slug>`
6. Push upstream: `git push -u origin <prefix>/<slug>`
7. If branch already exists: switch to it, pull latest

### Branch naming rules

- Lowercase, hyphen-separated: `feat/add-user-auth`
- Max 50 characters for the slug
- No special characters beyond hyphens
- Derived from the task description or user input

### Usage patterns

```
"Create a branch for user authentication"     → feat/add-user-auth
"Branch for fixing the login timeout"          → fix/login-timeout
"Branch to update dependencies"                → chore/update-deps
```

### Output

```
Branch: feat/add-user-auth
Base:   main (up to date)
Remote: origin/feat/add-user-auth ✅
Status: Ready to work
```

---

## New Workflow: `pr.md`

### Purpose

Create a GitHub Pull Request with full AI review and human-in-the-loop merge.

### Smart Default Behavior

- **On `main`/`master`:** Run the **branch** workflow first to create a feature branch, then proceed with PR creation
- **On a feature branch:** Create PR directly against `main`/`master`

Default branch detection: `git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@'` — falls back to `main` if not set.

### PR Creation Flow

#### Phase 1 — Pre-flight

1. Run the **gate** workflow (all 5 checks must pass)
2. If gate fails → stop, fix issues first

#### Phase 2 — Push & Create PR

1. Push current branch to origin: `git push -u origin <branch>`
2. Generate PR title from branch name and commit messages (concise, under 70 chars)
3. Generate PR body:
   - Summary (2-3 bullet points from commit diff against main)
   - Test plan (what was tested)
   - Link to related issues if detectable from commits/branch name
4. Create PR: `gh pr create --title "..." --body "..."`

#### Phase 3 — AI Review

Automatically triggered after PR creation. Reviews the full diff (`git diff main...HEAD`) and posts a comment via `gh pr comment`.

**AI Review checks:**

| Category | What it checks |
|:---------|:---------------|
| **Code quality** | Clean code, naming, complexity, DRY, dead code, large functions, unclear logic |
| **Spec compliance** | Does the PR match its title, description, and any linked issues |
| **Security** | Injection risks (SQL, XSS, command), hardcoded secrets, auth gaps, OWASP top 10 patterns |
| **Test coverage** | Are new code paths tested, any obvious gaps, test quality |
| **Breaking changes** | API signature changes, schema changes, config changes, removed exports, changed behavior |

**Review output format (posted as PR comment):**

```markdown
## 100x Dev — AI Review

### Summary
[1-2 sentence overall assessment]

### Findings

#### Critical (must fix before merge)
- [finding with file:line reference]

#### Important (should fix)
- [finding with file:line reference]

#### Minor (consider fixing)
- [finding with file:line reference]

### Checklist
- [ ] All critical findings addressed
- [ ] Tests cover new code paths
- [ ] No secrets in diff
- [ ] No breaking changes (or documented)

### Verdict: ✅ APPROVE / ⚠️ CHANGES REQUESTED / ❌ BLOCK
```

#### Phase 4 — Stop (Human-in-the-Loop)

The workflow explicitly stops. It does NOT merge.

```
╔══════════════════════════════════════════════════════╗
║               PULL REQUEST CREATED                    ║
╠══════════════════════════════════════════════════════╣
║ PR:       #42 — Add user authentication              ║
║ Branch:   feat/add-user-auth → main                  ║
║ Review:   AI review posted                           ║
║ Gate:     ✅ All 5 gates passed                       ║
╠══════════════════════════════════════════════════════╣
║ STATUS: Awaiting human approval. DO NOT auto-merge.   ║
╚══════════════════════════════════════════════════════╝
```

Merge is the human's responsibility. The workflow ensures everything is ready for review.

---

## Enhanced Workflow: `push.md` — Auto-Fix CI Failures

### Current state

Basic `gh run watch` monitoring with manual fix instructions.

### Enhancement

Add a semi-autonomous auto-fix loop after CI failure detection.

### Auto-fix flow

```
Push → Monitor CI (no timeout, watch until completion) →
  If PASS → Phase 4 (production verification) → done
  If FAIL → read logs → classify failure →
    If auto-fixable → apply fix → re-commit → re-run gate → re-push → retry
    If unfamiliar → report full diagnosis → escalate to human
```

### Auto-fixable failures (language-agnostic)

| Failure type | Detection signals | Fix strategy |
|:-------------|:------------------|:-------------|
| Lint/format | ESLint, Prettier, ruff, black, gofmt, rustfmt, checkstyle, rubocop, swiftlint, ktlint | Run the **lint** workflow, commit fixes |
| Type errors | TypeScript (`tsc`), mypy, pyright, Go compiler, Rust compiler (`rustc`), Java compiler (`javac`), Kotlin compiler | Read errors, fix types, commit |
| Test failures | Jest, Vitest, pytest, Go test, cargo test, JUnit, RSpec, PHPUnit, Swift XCTest, Elixir ExUnit | Read failing test output, fix test or underlying code, commit |
| Dependency issues | npm/yarn/pnpm lockfile mismatch, pip requirements, go.mod tidy, Cargo.lock, Maven/Gradle deps, Bundler, Composer | Install/update deps, commit lockfile |
| Build failures | webpack, vite, esbuild, Go build, cargo build, Maven/Gradle build, make, CMake, Swift build | Read build errors, fix, commit |

### Detection logic

1. `gh run view <run-id> --log | tail -100` — capture CI output
2. Identify the tool/framework from error signatures in the log output
3. Match to fix strategy
4. If no match → classify as unfamiliar → escalate

### Unfamiliar failures (escalate to human)

- Infrastructure errors (Docker build fails in CI but not locally)
- Permission / secrets / environment variable errors
- Timeout / flaky test patterns
- Network connectivity issues
- Unknown error codes or tools

### Retry limit

- Max 3 auto-fix attempts per push
- Each attempt: fix → commit → gate → push → monitor
- After 3 failures: stop, report full diagnosis, list all attempted fixes

### Output on auto-fix

```
CI FAILED — Attempt 1/3
Failure: ruff format check (Python)
Fix:     Running lint workflow...
Result:  2 files reformatted
Action:  Committing fix, re-running gate, re-pushing...
```

### Output on escalation

```
╔══════════════════════════════════════════════════════╗
║            CI FAILED — ESCALATING TO HUMAN            ║
╠══════════════════════════════════════════════════════╣
║ Attempts:  3/3 exhausted                             ║
║ Last error: Docker build failed — base image 404     ║
║ Diagnosis:  node:18-alpine image no longer available ║
║ Suggestion: Update Dockerfile base image to node:20  ║
╠══════════════════════════════════════════════════════╣
║ This requires human judgment. Auto-fix not possible.  ║
╚══════════════════════════════════════════════════════╝
```

---

## Enhanced Workflow: `launch.md` — Deployment Verification & Auto-Rollback

### Current state

Basic health endpoint checks after deployment.

### Enhancement

Full post-deployment verification pipeline with auto-rollback on failure.

### Verification pipeline

After CI passes and deployment completes:

#### Step 1 — Health checks (exists today, enhanced)

```bash
# Read health endpoints from project instruction file
# Hit each endpoint, confirm HTTP 200
# Retry up to 5 times with 10-second intervals (deployment may still be rolling out)
```

Enhanced: retry logic for rolling deployments, check response body for `"status": "healthy"` patterns.

#### Step 2 — Smoke tests (new)

If E2E tests exist in the project, run a targeted subset against production:

```bash
# Detect test framework
# Run smoke/critical-path tests only (tagged or in a smoke/ directory)
# E2E against production URL configured in project instruction file
```

Detection patterns:
- `tests/smoke/`, `e2e/smoke/`, `tests/critical/` directories
- Tests tagged with `@smoke`, `@critical`, `mark.smoke`
- If no smoke tests exist, skip gracefully

#### Step 3 — Metrics check (new)

If a monitoring URL is configured in the project instruction file:

```bash
# Check for error rate spikes in the last 5 minutes
# Compare current error rate to pre-deployment baseline
# Flag if error rate > 2x baseline
```

If no monitoring URL configured, skip gracefully.

#### Step 4 — Rollback on failure (new)

If any verification step fails:

```
Verification failed →
  Log which step failed and why →
  Auto-rollback:
    git revert HEAD --no-edit
    git push origin <branch>
  →
  Re-verify health endpoints (confirm rollback succeeded) →
  Report to human with full diagnosis
```

**Rollback is safe:** Uses `git revert` (creates a new commit), not `git reset` (destructive). The bad commit stays in history for debugging.

### Configuration via project instruction file

```markdown
## Deployment
health: https://api.example.com/health
smoke_tests: true
monitoring: https://grafana.example.com/d/api-latency
rollback: auto
```

| Field | Required | Default |
|:------|:---------|:--------|
| `health` | No | Auto-detect from README or common patterns (`/health`, `/healthz`, `/api/health`) |
| `smoke_tests` | No | `true` if smoke test directory exists |
| `monitoring` | No | Skip metrics check |
| `rollback` | No | `auto` (revert on failure). Set to `manual` to disable auto-rollback |

If no `## Deployment` section exists, verification degrades gracefully:
- Health checks: try common endpoints
- Smoke tests: run if test directory exists
- Metrics: skip
- Rollback: auto

### Output on success

```
╔══════════════════════════════════════════════════════╗
║           DEPLOYMENT VERIFIED                         ║
╠══════════════════════════════════════════════════════╣
║ Health:      ✅ https://api.example.com/health (200) ║
║ Smoke tests: ✅ 4/4 passed                           ║
║ Metrics:     ✅ Error rate normal (0.1%)              ║
╠══════════════════════════════════════════════════════╣
║ STATUS: SHIPPED ✅                                    ║
╚══════════════════════════════════════════════════════╝
```

### Output on rollback

```
╔══════════════════════════════════════════════════════╗
║           DEPLOYMENT FAILED — ROLLED BACK             ║
╠══════════════════════════════════════════════════════╣
║ Health:      ✅ PASSED                                ║
║ Smoke tests: ❌ FAILED (2/4 — login flow, checkout)  ║
║ Action:      Auto-reverted commit abc1234             ║
║ Rollback:    ✅ Health check confirms rollback OK     ║
╠══════════════════════════════════════════════════════╣
║ STATUS: ROLLED BACK — human review required           ║
║ Diagnosis:   Login endpoint returning 500 after       ║
║              auth middleware change in commit abc1234  ║
╚══════════════════════════════════════════════════════╝
```

---

## Cross-Cutting: Language-Agnostic Detection

All workflows detect the project's language and toolchain from the project itself:

```bash
# Detection order (check file existence)
# Node.js:  package.json
# Python:   pyproject.toml, requirements.txt, setup.py
# Go:       go.mod
# Rust:     Cargo.toml
# Java:     pom.xml, build.gradle, build.gradle.kts
# Ruby:     Gemfile
# PHP:      composer.json
# Swift:    Package.swift
# Kotlin:   build.gradle.kts with kotlin plugin
# Elixir:   mix.exs
# C/C++:    CMakeLists.txt, Makefile
```

This detection pattern is already used in existing workflows (test.md, lint.md, gate.md) for Node.js and Python. The enhancement extends it to all languages listed above.

---

## Integration with Existing Workflows

| Workflow | Changes |
|:---------|:--------|
| `branch.md` | New file |
| `pr.md` | New file. References: gate, branch workflows |
| `push.md` | Enhanced: add auto-fix loop after Phase 3, language-agnostic detection |
| `launch.md` | Enhanced: add smoke tests, metrics check, auto-rollback after Phase 6 |
| `gate.md` | No changes |
| `commit.md` | No changes |
| All others | No changes |

---

## Updates Required

- Add `branch.md` and `pr.md` to `workflows/`
- Update `push.md` with auto-fix loop
- Update `launch.md` with verification pipeline
- Update all adapters to include new workflows in concatenation
- Update `adapters/claude-code.sh` to copy new workflow files
- Update `README.md` to list branch and pr workflows
- Update `docs/USAGE.md` with new workflow usage patterns
- Update installer workflow count (13 → 15)

---

## Out of Scope

- Merge automation (human-in-the-loop by design)
- Branch protection rule configuration (GitHub settings, not workflow)
- Multi-environment deployment (staging → production pipeline)
- Canary / blue-green deployment strategies
- CI configuration file generation (.github/workflows/*.yml)
