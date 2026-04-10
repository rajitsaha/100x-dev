# CI/CD Workflow Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add branch creation and PR workflows, enhance push.md with auto-fix CI failures, and enhance launch.md with deployment verification and auto-rollback.

**Architecture:** Two new workflow markdown files (branch.md, pr.md), two enhanced existing workflows (push.md, launch.md), adapter updates to include new workflows, and README/USAGE updates.

**Tech Stack:** Markdown (workflows), Bash (adapters), gh CLI (PR/CI operations)

---

## File Structure

**Create:**
- `workflows/branch.md` — branch creation workflow
- `workflows/pr.md` — PR creation with AI review workflow

**Modify:**
- `workflows/push.md` — add auto-fix CI loop after Phase 3
- `workflows/launch.md` — add deployment verification pipeline after Phase 6
- `adapters/cursor.sh` — add branch, pr to workflow list
- `adapters/codex.sh` — add branch, pr to workflow list
- `adapters/windsurf.sh` — add branch, pr to workflow list
- `adapters/copilot.sh` — add branch, pr to workflow list
- `adapters/gemini.sh` — add branch, pr to workflow list
- `adapters/antigravity.sh` — add branch, pr to workflow list
- `README.md` — add branch, pr to workflow table
- `docs/USAGE.md` — add branch, pr usage patterns

---

### Task 1: Create `workflows/branch.md`

**Files:**
- Create: `workflows/branch.md`

- [ ] **Step 1: Write branch.md**

Write to `workflows/branch.md`:

```markdown
# Branch — Create Feature Branch

Create a feature branch from the default branch with a descriptive, conventional name.

## Do NOT ask for permission. Create the branch and push it.

---

## Step 1 — Detect default branch

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
DEFAULT_BRANCH="${DEFAULT_BRANCH:-main}"
CURRENT_BRANCH=$(git branch --show-current)
echo "Default branch: $DEFAULT_BRANCH"
echo "Current branch: $CURRENT_BRANCH"
```

If not on the default branch, warn:
```
⚠️ Currently on '$CURRENT_BRANCH', not '$DEFAULT_BRANCH'.
Creating branch from current HEAD. Proceed only if intentional.
```

---

## Step 2 — Pull latest

```bash
git fetch origin
git checkout "$DEFAULT_BRANCH"
git pull origin "$DEFAULT_BRANCH"
```

---

## Step 3 — Generate branch name

Derive a branch name from the task description using conventional prefixes:

| Prefix | Use when |
|:-------|:---------|
| `feat/` | New feature |
| `fix/` | Bug fix |
| `chore/` | Maintenance, deps, config |
| `refactor/` | Code restructuring |
| `docs/` | Documentation only |
| `test/` | Test additions or fixes |

**Naming rules:**
- Lowercase, hyphen-separated: `feat/add-user-auth`
- Max 50 characters for the slug portion
- No special characters beyond hyphens
- Derived from the task description or user input

**Examples:**
```
"Add user authentication"         → feat/add-user-auth
"Fix login timeout bug"           → fix/login-timeout
"Update dependencies"             → chore/update-deps
"Refactor payment module"         → refactor/payment-module
"Add API documentation"           → docs/api-docs
```

---

## Step 4 — Create and push branch

```bash
BRANCH_NAME="<prefix>/<slug>"
git checkout -b "$BRANCH_NAME"
git push -u origin "$BRANCH_NAME"
```

If the branch already exists locally or remotely:
```bash
git checkout "$BRANCH_NAME"
git pull origin "$BRANCH_NAME" 2>/dev/null || true
```

---

## Output

```
╔══════════════════════════════════════════════════════╗
║               BRANCH CREATED                          ║
╠══════════════════════════════════════════════════════╣
║ Branch:   feat/add-user-auth                         ║
║ Base:     main (up to date)                          ║
║ Remote:   origin/feat/add-user-auth ✅                ║
╠══════════════════════════════════════════════════════╣
║ STATUS: Ready to work                                ║
╚══════════════════════════════════════════════════════╝
```
```

- [ ] **Step 2: Verify file created**

```bash
cat workflows/branch.md | head -5
```
Expected: `# Branch — Create Feature Branch`

- [ ] **Step 3: Commit**

```bash
git add workflows/branch.md
git commit -m "feat: add branch creation workflow"
```

---

### Task 2: Create `workflows/pr.md`

**Files:**
- Create: `workflows/pr.md`

- [ ] **Step 1: Write pr.md**

Write to `workflows/pr.md`:

```markdown
# PR — Create Pull Request with AI Review

Create a GitHub Pull Request with full AI review. Human approves and merges.

## Do NOT merge automatically. Always stop after PR creation and AI review.

---

## Step 0 — Smart default: ensure feature branch

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
DEFAULT_BRANCH="${DEFAULT_BRANCH:-main}"
CURRENT_BRANCH=$(git branch --show-current)
```

**If on the default branch:** Run the **branch** workflow first to create a feature branch. Then continue.

**If on a feature branch:** Continue with PR creation.

---

## Phase 1 — Pre-flight

Run the **gate** workflow. All 5 gates must pass before creating a PR.

**If any gate fails → STOP. Fix issues first. Do NOT create a PR with failing gates.**

---

## Phase 2 — Push branch

```bash
git push -u origin "$CURRENT_BRANCH"
```

---

## Phase 3 — Generate PR content

### Title
- Derive from branch name and commit messages
- Under 70 characters
- Use conventional format: `feat: add user authentication`

### Body
Generate from the diff against the default branch:

```bash
git log "$DEFAULT_BRANCH"..HEAD --oneline
git diff "$DEFAULT_BRANCH"...HEAD --stat
```

Structure the body as:

```markdown
## Summary
- [2-3 bullet points describing what changed and why]

## Changes
- [list of key files/areas modified]

## Test plan
- [ ] [How this was tested]
- [ ] [What to verify during review]

## Related issues
[Auto-detected from commit messages: "fixes #42", "closes #13", etc.]
```

---

## Phase 4 — Create PR

```bash
gh pr create \
  --title "<generated title>" \
  --body "<generated body>" \
  --base "$DEFAULT_BRANCH" \
  --head "$CURRENT_BRANCH"
```

Capture the PR number and URL from the output.

---

## Phase 5 — AI Review

Review the full diff and post findings as a PR comment.

### What to review

```bash
# Get the full diff for review
git diff "$DEFAULT_BRANCH"...HEAD
```

Analyze the diff across 5 categories:

**1. Code quality**
- Clean code, naming, complexity, DRY, dead code
- Large functions or files that need splitting
- Unclear logic that needs comments

**2. Spec compliance**
- Does the code match the PR title and description
- Are all claimed changes actually present
- Are there unclaimed changes (scope creep)

**3. Security**
- SQL injection, XSS, command injection risks
- Hardcoded secrets, API keys, tokens
- Authentication and authorization gaps
- OWASP top 10 patterns

**4. Test coverage**
- Are new code paths tested
- Are edge cases covered
- Test quality — do tests verify behavior or just mock everything

**5. Breaking changes**
- API signature changes (added/removed/changed parameters)
- Database schema changes
- Configuration changes
- Removed or renamed exports
- Changed default behavior

### Post review as PR comment

```bash
gh pr comment <PR_NUMBER> --body "<review content>"
```

**Review format:**

```markdown
## 100x Dev — AI Review

### Summary
[1-2 sentence overall assessment]

### Findings

#### Critical (must fix before merge)
- [file:line] [description]

#### Important (should fix)
- [file:line] [description]

#### Minor (consider fixing)
- [file:line] [description]

### Checklist
- [ ] All critical findings addressed
- [ ] Tests cover new code paths
- [ ] No secrets in diff
- [ ] No breaking changes (or documented)

### Verdict: ✅ APPROVE / ⚠️ CHANGES REQUESTED / ❌ BLOCK
```

If no issues found:

```markdown
## 100x Dev — AI Review

### Summary
Clean implementation. No issues found.

### Verdict: ✅ APPROVE
```

---

## Phase 6 — Stop (Human-in-the-Loop)

**DO NOT MERGE.** Print the PR summary and stop.

```
╔══════════════════════════════════════════════════════╗
║               PULL REQUEST CREATED                    ║
╠══════════════════════════════════════════════════════╣
║ PR:       #<number> — <title>                        ║
║ Branch:   <branch> → <default_branch>                ║
║ Review:   AI review posted ✅                         ║
║ Gate:     ✅ All 5 gates passed                       ║
╠══════════════════════════════════════════════════════╣
║ URL:      <pr_url>                                   ║
║ STATUS:   Awaiting human approval. DO NOT auto-merge. ║
╚══════════════════════════════════════════════════════╝
```

Merge is the human's responsibility. This workflow ensures everything is ready for review.
```

- [ ] **Step 2: Verify file created**

```bash
cat workflows/pr.md | head -5
```
Expected: `# PR — Create Pull Request with AI Review`

- [ ] **Step 3: Commit**

```bash
git add workflows/pr.md
git commit -m "feat: add PR creation workflow with AI review"
```

---

### Task 3: Enhance `workflows/push.md` — auto-fix CI failures

**Files:**
- Modify: `workflows/push.md`

- [ ] **Step 1: Replace Phase 3 and Phase 4 in push.md**

The current Phase 3 (lines 53-65) is basic monitoring. Replace it with the auto-fix loop. Also enhance Phase 4 (lines 69-73) with better verification.

Replace everything from `## Phase 3` through to the `## Output` section (lines 53-85) with:

```markdown
## Phase 3 — Monitor GitHub Actions & Auto-Fix

```bash
gh run list --limit 3
RUN_ID=$(gh run list --limit 1 --json databaseId -q '.[0].databaseId')
gh run watch "$RUN_ID"
```

No timeout — watch until CI completes or fails.

### If CI passes → continue to Phase 4.

### If CI fails → Auto-fix loop (max 3 attempts)

```bash
gh run view "$RUN_ID" --log | tail -100
```

Read the failure logs and classify the error:

**Auto-fixable failures (language-agnostic):**

| Failure type | Detection signals | Fix strategy |
|:-------------|:------------------|:-------------|
| Lint/format | ESLint, Prettier, ruff, black, gofmt, rustfmt, checkstyle, rubocop, swiftlint, ktlint | Run the **lint** workflow, commit fixes |
| Type errors | TypeScript (`tsc`), mypy, pyright, Go compiler, Rust compiler (`rustc`), Java (`javac`), Kotlin | Read errors, fix types, commit |
| Test failures | Jest, Vitest, pytest, Go test, cargo test, JUnit, RSpec, PHPUnit, XCTest, ExUnit | Read failing test, fix test or code, commit |
| Dependency issues | npm/yarn/pnpm lockfile, pip requirements, go.mod, Cargo.lock, Maven/Gradle, Bundler, Composer | Install/update deps, commit lockfile |
| Build failures | webpack, vite, esbuild, Go build, cargo build, Maven/Gradle build, make, CMake, Swift build | Read build errors, fix, commit |

**Detection logic:**
1. Read CI log output
2. Identify the tool/framework from error signatures
3. Match to the fix strategy above
4. If no match → classify as unfamiliar → escalate

**For each auto-fix attempt:**
1. Apply the fix
2. Create a new commit (never amend)
3. Re-run the **gate** workflow
4. Push again
5. Monitor CI again

```
CI FAILED — Attempt N/3
Failure:  [tool/framework] [error type]
Fix:      [what was done]
Action:   Committing fix, re-running gate, re-pushing...
```

**Unfamiliar failures (escalate to human after any attempt):**
- Infrastructure errors (Docker build fails in CI but not locally)
- Permission / secrets / environment variable errors
- Timeout / flaky test patterns (same test passes locally)
- Network connectivity issues
- Unknown error codes or tools

```
╔══════════════════════════════════════════════════════╗
║            CI FAILED — ESCALATING TO HUMAN            ║
╠══════════════════════════════════════════════════════╣
║ Attempts:   N/3 exhausted (or unfamiliar failure)    ║
║ Last error: [error summary]                          ║
║ Diagnosis:  [root cause analysis]                    ║
║ Suggestion: [recommended fix]                        ║
╠══════════════════════════════════════════════════════╣
║ This requires human judgment. Auto-fix not possible.  ║
╚══════════════════════════════════════════════════════╝
```

**After 3 failed auto-fix attempts → STOP. Report all attempted fixes and escalate.**

---

## Phase 4 — Production verification

After all CI/CD workflows succeed:

```bash
# Detect project instruction file
INSTRUCTION_FILE=""
for f in CLAUDE.md AGENTS.md .cursorrules .windsurfrules .github/copilot-instructions.md GEMINI.md; do
  [ -f "$PROJECT_ROOT/$f" ] && INSTRUCTION_FILE="$PROJECT_ROOT/$f" && break
done
```

1. **Health checks** — read health endpoint URLs from the project instruction file or README. Hit each and confirm HTTP 200:
```bash
[ -n "$INSTRUCTION_FILE" ] && grep -E "https?://[^ ]*/health" "$INSTRUCTION_FILE" 2>/dev/null | head -3
# Also try common defaults:
# /health, /healthz, /api/health, /status
```

Retry up to 5 times with 10-second intervals (deployment may still be rolling out).

2. **Confirm deployment** — verify the deployed version matches the pushed commit if a version endpoint exists.

---

## Output

```
=== Push Complete ===
Gate:     ✅ ALL GATES PASSED
Push:     <branch> → origin/<branch> ✅
CI/CD:    ✅ All workflows passed (N auto-fixes applied)
Health:   ✅ All endpoints responding
Status:   SHIPPED ✅
```
```

- [ ] **Step 2: Verify the edit**

```bash
grep -c "Auto-fixable failures" workflows/push.md
grep -c "ESCALATING TO HUMAN" workflows/push.md
```
Expected: 1 and 1

- [ ] **Step 3: Commit**

```bash
git add workflows/push.md
git commit -m "feat: add auto-fix CI failure loop to push workflow"
```

---

### Task 4: Enhance `workflows/launch.md` — deployment verification & auto-rollback

**Files:**
- Modify: `workflows/launch.md`

- [ ] **Step 1: Replace Phase 6 in launch.md**

Replace the current Phase 6 (lines 108-121, starting from `## Phase 6 — Push` through to the `---` before Phase 7) with an enhanced version that includes deployment verification and auto-rollback.

Replace:
```markdown
## Phase 6 — Push

Run the **push** workflow. Push to origin main, handle hooks, monitor CI/CD.

After CI/CD completes, verify production. Read the project instruction file for health endpoint URLs:
```bash
# Detect project instruction file
INSTRUCTION_FILE=""
for f in CLAUDE.md AGENTS.md .cursorrules .windsurfrules .github/copilot-instructions.md GEMINI.md; do
  [ -f "$PROJECT_ROOT/$f" ] && INSTRUCTION_FILE="$PROJECT_ROOT/$f" && break
done
[ -n "$INSTRUCTION_FILE" ] && grep -E "https?://[^ ]*/health" "$INSTRUCTION_FILE" 2>/dev/null | head -3
```
Hit each endpoint and confirm 200 OK.
```

With:

```markdown
## Phase 6 — Push & Deploy

Run the **push** workflow. Push, handle hooks, monitor CI/CD, auto-fix failures if needed.

---

## Phase 6b — Deployment Verification

After CI/CD passes and deployment completes, run the full verification pipeline.

```bash
# Detect project instruction file
INSTRUCTION_FILE=""
for f in CLAUDE.md AGENTS.md .cursorrules .windsurfrules .github/copilot-instructions.md GEMINI.md; do
  [ -f "$PROJECT_ROOT/$f" ] && INSTRUCTION_FILE="$PROJECT_ROOT/$f" && break
done
```

### Step 1 — Health checks

Read health endpoint URLs from the project instruction file, README, or use common defaults:

```bash
# From project instruction file
[ -n "$INSTRUCTION_FILE" ] && grep -E "https?://[^ ]*/health" "$INSTRUCTION_FILE" 2>/dev/null | head -3

# Common defaults to try
# /health, /healthz, /api/health, /status
```

Hit each endpoint. Retry up to 5 times with 10-second intervals (deployment may still be rolling out). Confirm HTTP 200 and a healthy response body.

**If health checks fail after 5 retries → trigger rollback (Step 4).**

### Step 2 — Smoke tests

If E2E or smoke tests exist, run a targeted subset against production:

```bash
# Detect smoke test locations
ls tests/smoke/ e2e/smoke/ tests/critical/ 2>/dev/null || true
```

Detection patterns:
- Directories: `tests/smoke/`, `e2e/smoke/`, `tests/critical/`
- Tagged tests: `@smoke`, `@critical`, `mark.smoke`
- If no smoke tests exist, skip this step gracefully

Run detected smoke tests against the production URL configured in the project instruction file:

```bash
# Look for production URL in project instruction file
[ -n "$INSTRUCTION_FILE" ] && grep -E "https?://[^ ]+" "$INSTRUCTION_FILE" 2>/dev/null | grep -iE "prod|production|live" | head -1
```

**If smoke tests fail → trigger rollback (Step 4).**

### Step 3 — Metrics check

If a monitoring URL is configured in the project instruction file:

```bash
[ -n "$INSTRUCTION_FILE" ] && grep -iE "monitoring|grafana|datadog|newrelic" "$INSTRUCTION_FILE" 2>/dev/null | head -1
```

If found:
- Note the monitoring URL for manual review
- Check for error rate information if accessible via API
- Flag if error rate appears elevated compared to normal

If no monitoring URL configured, skip this step gracefully.

### Step 4 — Auto-rollback (on failure)

If any verification step fails:

```bash
echo "Deployment verification FAILED. Rolling back..."

# Revert the last commit (safe — creates a new commit, not destructive)
git revert HEAD --no-edit

# Push the revert
git push origin "$(git branch --show-current)"
```

After rollback:
1. Re-run health checks to confirm rollback succeeded
2. Report which verification step failed and why
3. Provide full diagnosis

```
╔══════════════════════════════════════════════════════╗
║           DEPLOYMENT FAILED — ROLLED BACK             ║
╠══════════════════════════════════════════════════════╣
║ Health:      ✅ PASSED / ❌ FAILED                    ║
║ Smoke tests: ✅ PASSED / ❌ FAILED (details)          ║
║ Metrics:     ✅ NORMAL / ⚠️ ELEVATED / skipped        ║
║ Action:      Auto-reverted commit <hash>              ║
║ Rollback:    ✅ Health confirms rollback OK            ║
╠══════════════════════════════════════════════════════╣
║ STATUS: ROLLED BACK — human review required           ║
║ Diagnosis:   [what failed and why]                    ║
╚══════════════════════════════════════════════════════╝
```

If rollback is set to `manual` in the project instruction file (`rollback: manual`), report the failure but do NOT auto-revert. Wait for human decision.

### Verification output (on success)

```
╔══════════════════════════════════════════════════════╗
║           DEPLOYMENT VERIFIED                         ║
╠══════════════════════════════════════════════════════╣
║ Health:      ✅ All endpoints responding (200)        ║
║ Smoke tests: ✅ N/N passed | skipped                  ║
║ Metrics:     ✅ Error rate normal | skipped            ║
╠══════════════════════════════════════════════════════╣
║ STATUS: DEPLOYED & VERIFIED ✅                        ║
╚══════════════════════════════════════════════════════╝
```
```

- [ ] **Step 2: Update the summary output section**

In the summary output at the bottom of launch.md, update Phase 6 line:

Replace:
```
Phase 6 push:       main -> origin/main ✅ | CI/CD ✅ | Production ✅
```

With:
```
Phase 6 Push:       ✅ CI/CD passed | Health ✅ | Smoke ✅ | Metrics ✅
```

- [ ] **Step 3: Verify the edit**

```bash
grep -c "Auto-rollback" workflows/launch.md
grep -c "Smoke tests" workflows/launch.md
grep -c "Metrics check" workflows/launch.md
```
Expected: 1, at least 2, at least 2

- [ ] **Step 4: Commit**

```bash
git add workflows/launch.md
git commit -m "feat: add deployment verification and auto-rollback to launch workflow"
```

---

### Task 5: Update all project-level adapters

Add `branch` and `pr` to the workflow list in all 6 project-level adapters.

**Files:**
- Modify: `adapters/cursor.sh`
- Modify: `adapters/codex.sh`
- Modify: `adapters/windsurf.sh`
- Modify: `adapters/copilot.sh`
- Modify: `adapters/gemini.sh`
- Modify: `adapters/antigravity.sh`

- [ ] **Step 1: Update all 6 adapters**

In each adapter file, find the line:
```bash
    for f in gate test commit push launch lint security docs issue architect cloud-security enterprise-design db; do
```

Replace with:
```bash
    for f in gate test commit push pr branch launch lint security docs issue architect cloud-security enterprise-design db; do
```

Note: `pr` and `branch` are placed after `push` and before `launch` — this groups the git workflow commands together logically.

Apply this change to all 6 files:
- `adapters/cursor.sh`
- `adapters/codex.sh`
- `adapters/windsurf.sh`
- `adapters/copilot.sh`
- `adapters/gemini.sh`
- `adapters/antigravity.sh`

- [ ] **Step 2: Verify all 6 adapters updated**

```bash
grep -c "pr branch launch" adapters/*.sh
```
Expected: 6 files, each showing count of 1

- [ ] **Step 3: Commit**

```bash
git add adapters/
git commit -m "feat: add branch and pr workflows to all project-level adapters"
```

---

### Task 6: Update README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add branch and pr to the workflow table**

In the "What You Get" / "13 Production Workflows" section, add two new rows after the **push** row and before the **launch** row:

```markdown
| **pr** | Gate → push branch → create PR → full AI review → human merges. Never auto-merges. |
| **branch** | Create conventional feature branches from main — `feat/`, `fix/`, `chore/`, auto-push upstream. |
```

Also update "13 Production Workflows" → "15 Production Workflows" in the heading and anywhere the count "13" appears.

- [ ] **Step 2: Update the hero section**

Find:
```
**13 battle-tested AI development workflows**
```

Replace with:
```
**15 battle-tested AI development workflows**
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add branch and pr workflows to README"
```

---

### Task 7: Update docs/USAGE.md

**Files:**
- Modify: `docs/USAGE.md`

- [ ] **Step 1: Add branch and pr to the Claude Code usage section**

In the "In Claude Code" section where slash commands are listed, add after `/push`:

```
/branch            Create a feature branch from main with auto-naming
/pr                Create a PR with AI review (human merges)
```

- [ ] **Step 2: Add branch and pr to the "In Other Tools" section**

In the prompt examples, add:

```
"Run the branch workflow — I need a feature branch for user auth"
"Run the pr workflow — create a PR with AI review"
```

- [ ] **Step 3: Add a typical PR workflow example**

In the "Typical daily workflow" section, add after the existing example:

```
# PR-based workflow (recommended for teams)
/branch                     # create feature branch
# ... make changes ...
/test                       # run tests
/pr                         # runs gate, pushes, creates PR, AI review
# → human reviews and merges on GitHub
```

- [ ] **Step 4: Update workflow count**

Find any mention of "13 workflows" and update to "15 workflows".

- [ ] **Step 5: Commit**

```bash
git add docs/USAGE.md
git commit -m "docs: add branch and pr workflow usage patterns"
```

---

### Task 8: Push all changes

**Files:** None (git operation only)

- [ ] **Step 1: Push to remote**

```bash
git push origin main
```

- [ ] **Step 2: Verify on GitHub**

```bash
gh repo view rajitsaha/100x-dev --json description -q '.description'
```
