# /push — Gate → Push → Monitor CI/CD

Quality gate re-runs before pushing. **Do NOT push if any gate fails.**

## Do NOT ask for permission. Do NOT use `--no-verify` or `--force`.

---

## Phase 0 — Quality Gate (MANDATORY)

Invoke `/gate`. All four gates must pass before pushing:

1. **Tests** — ≥ 95% coverage, zero failures
2. **Security** — zero critical, zero high vulnerabilities
3. **Local build** — zero compiler errors
4. **Docker build** — passes (or skipped if no Dockerfile)

**If `/gate` reports ANY failure → STOP. Do not push. Fix the issue, create a new commit, then push.**

Only continue when gate shows: `✅ ALL GATES PASSED`

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
4. Re-run `/gate` to confirm fixes pass
5. Push again

If push is rejected (non-fast-forward):
```bash
git pull --rebase origin main
git push origin main
```

---

## Phase 3 — Monitor GitHub Actions

```bash
gh run list --limit 3
gh run watch $(gh run list --limit 1 --json databaseId -q '.[0].databaseId')
```

Wait for all triggered workflows to complete. If any fail:
```bash
gh run view <run-id> --log | tail -50
```

Fix the issue, create a new commit, re-run `/gate`, push again.

---

## Phase 4 — Production verification

After all CI/CD workflows succeed:
- Check health endpoints listed in the project's `CLAUDE.md` or `README`
- Confirm the deployment completed successfully

---

## Output

```
=== /push Complete ===
Gate:   ✅ ALL GATES PASSED
Push:   main -> origin/main ✅
CI/CD:  [workflows] ✅
Status: SHIPPED ✅
```
