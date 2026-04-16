# Push — Gate → Push → Monitor CI/CD

Quality gate re-runs before pushing. **Do NOT push if any gate fails.**

## Do NOT ask for permission. Do NOT use `--no-verify` or `--force`.

---

## Phase 0 — Quality Gate (MANDATORY)

Run the **gate** workflow. Do NOT push until it reports `✅ ALL GATES PASSED`. If any gate fails → STOP, fix the issue, create a new commit, then re-run gate.

---

## Phase 1 — Push

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"
git push origin main
```

Let any pre-push hooks run. **Never bypass with `--no-verify`.**

---

## Phase 2 — Handle pre-push hook failures

If the hook fails:
1. Read the failure output carefully
2. Fix the root cause — never bypass
3. Create a **NEW commit** with the fix (never `--amend` over a pushed commit)
4. Re-run the **gate** workflow to confirm fixes pass
5. Push again

If push is rejected (non-fast-forward):
```bash
git pull --rebase origin main
git push origin main
```

---

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
INSTRUCTION_FILE=$(for f in CLAUDE.md AGENTS.md .cursorrules .windsurfrules .github/copilot-instructions.md GEMINI.md; do [ -f "$PROJECT_ROOT/$f" ] && echo "$PROJECT_ROOT/$f" && break; done)
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
