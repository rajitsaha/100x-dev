# Launch — Pre-flight Pipeline: Docker → Test → Lint → Security → Build → Commit → Push → Cleanup

You are a release engineer. Execute each phase in order. Each must fully complete before advancing. Do NOT ask for permission. Stop only if something is truly unfixable.

---

## Phase 0 — Docker Build & Smoke Test (if applicable)

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
ls "$PROJECT_ROOT/Dockerfile" 2>/dev/null && echo "HAS_DOCKERFILE" || echo "NO_DOCKERFILE"
```

**Skip this phase if no Dockerfile exists.**

If Dockerfile exists:

### 0a. Build images
Detect from `docker-compose.yml` whether there are multiple services. Build all:
```bash
cd "$PROJECT_ROOT"
docker build -t $(basename $PROJECT_ROOT)-api:local . 2>&1
# If dashboard/frontend Dockerfile exists:
docker build -t $(basename $PROJECT_ROOT)-dashboard:local ./dashboard 2>&1 || true
```
Fix any build errors. Iterate until all images build successfully.

### 0b. Start stack
```bash
# Use docker-compose.yml or compose.yml if present
COMPOSE_FILE=$(ls docker-compose.yml compose.yml deploy/docker-compose.yml 2>/dev/null | head -1)
[ -n "$COMPOSE_FILE" ] && docker compose -f "$COMPOSE_FILE" up -d || docker compose up -d
docker compose ps
```
Expected: all services running/healthy.

### 0c. Run migrations (if applicable)
```bash
docker compose run --rm migrate 2>/dev/null || true
```

### 0d. Smoke test
Read `CLAUDE.md` or `README.md` for health endpoint. Fall back to common defaults:
```bash
curl -s http://localhost:8000/health 2>/dev/null || \
curl -s http://localhost:3000/health 2>/dev/null || \
curl -s http://localhost:8080/health 2>/dev/null || echo "No health endpoint found"
```

### 0e. Cleanup
```bash
docker compose down 2>/dev/null || true
```

**GATE: All images build, containers healthy, smoke test passes.**

---

## Phase 1 — Tests

Run the **test** workflow. Loop until all thresholds are met with zero failures:
- Lines ≥ 95% | Functions ≥ 95% | Statements ≥ 95% | Branches ≥ 90%

**GATE: The test workflow reports "COVERAGE MET ✅" with zero failures.**

---

## Phase 2 — Lint

Run the **lint** workflow. Fix all errors across frontend, backend, and type checks.

**GATE: Zero lint errors remaining.**

---

## Phase 3 — Security

Run the **security** workflow. Fix critical/high vulnerabilities. Confirm no real secrets in source.

**GATE: No critical/high vulns (outside documented known exceptions) AND no real secrets.**

---

## Phase 4 — Build

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"
```

Detect and run applicable builds:
- **npm frontend**: `npm run build`
- **npm backend**: `cd api && npm run build`
- **Python**: `./venv/bin/python -m build 2>/dev/null || true`

Fix any compiler errors. Re-build only the failing target.

**GATE: All applicable builds succeed with zero errors.**

---

## Phase 5 — Commit

Run the **commit** workflow. Stage, write, and create a conventional commit.

---

## Phase 6 — Push

Run the **push** workflow. Push to origin main, handle hooks, monitor CI/CD.

After CI/CD completes, verify production. Read `CLAUDE.md` for health endpoint URLs:
```bash
grep -E "https?://[^ ]*/health" "$PROJECT_ROOT/CLAUDE.md" 2>/dev/null | head -3
```
Hit each endpoint and confirm 200 OK.

---

## Phase 7 — Post-launch cleanup

### 7a. Close related GitHub issues
Scan commit messages from this launch for issue references:
```bash
git log $(git rev-parse HEAD~10 2>/dev/null || git rev-list --max-parents=0 HEAD)..HEAD \
  --format='%s %b' 2>/dev/null | grep -oE '#[0-9]+' | sort -u
```
For each referenced issue that is still open:
```bash
gh issue close <N> --comment "Resolved in $(git log -1 --format='%h') — $(git log -1 --format='%s')" 2>/dev/null || true
```
Skip issues already closed or in different repos.

### 7b. Update ROADMAP.md (if exists)
```bash
[ -f "$PROJECT_ROOT/ROADMAP.md" ] || exit 0
OPEN=$(gh issue list --state open --json number 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null)
CLOSED=$(gh issue list --state closed --json number --limit 1000 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null)
echo "Open: $OPEN | Closed: $CLOSED"
```
Update the issue count summary line in `ROADMAP.md` if counts changed. Update `Last updated` date.

### 7c. Update CLAUDE.md (if features changed)
If new features were implemented or bugs fixed, update the feature audit table. Update `Last updated` date.

### 7d. Commit doc updates (if any changed)
```bash
git diff --name-only ROADMAP.md CLAUDE.md AGENT.md 2>/dev/null | grep -q . && \
  git add ROADMAP.md CLAUDE.md AGENT.md 2>/dev/null && \
  git commit -m "docs: update issue tracker counts and documentation after launch" && \
  git push origin main || true
```

---

## Summary output

```
=== Launch Summary ===
Phase 0 Docker:     ✅ Built + healthy | skipped (no Dockerfile)
Phase 1 test:       ✅ COVERAGE MET (XX%)
Phase 2 lint:       ✅ PASSED
Phase 3 security:   ✅ PASSED
Phase 4 Build:      ✅ CLEAN
Phase 5 commit:     <short-hash> <message>
Phase 6 push:       main -> origin/main ✅ | CI/CD ✅ | Production ✅
Phase 7 Cleanup:    Issues closed: #N, #M ✅ | Docs updated ✅ | no changes
Status:             LAUNCHED ✅
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Docker build fails | Fix Python/dependency or TypeScript errors, iterate |
| Coverage below 95% | `/test` loops automatically — let it finish |
| Test fails after fix | Re-run only that suite |
| Build fails with TS errors | Run `npm run typecheck` to isolate first |
| Pre-push hook fails | Fix → NEW commit → push again. Never `--no-verify` |
| Push rejected (non-fast-forward) | `git pull --rebase origin main` then push |
| `gh issue close` fails | Issue may be in a different repo — check `gh repo view` |
| ROADMAP counts don't match | Re-run `gh issue list` and reconcile manually |
