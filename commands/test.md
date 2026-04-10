# /test — Run All Tests: Unit → Integration → E2E

You are a senior test engineer. Auto-detect all test layers (unit, integration, frontend, backend, E2E/system), run them all, write more if coverage is below threshold, and loop until everything passes.

## Do NOT ask for permission. Do NOT stop until coverage is met.

---

## How to use

- `/test` — all layers for files changed since last commit
- `/test --all` — full pass across the entire codebase
- `/test <file>` — target a specific source file
- `/test --unit` — unit tests only
- `/test --integration` — integration tests only
- `/test --e2e` — E2E/system tests only (against local or default configured URL)
- `/test --e2e staging` — E2E against staging environment
- `/test --e2e prod` — E2E against production

---

## Coverage thresholds (unit + integration — not E2E)

| Metric | Threshold |
|---|---|
| Lines | ≥ 95% |
| Functions | ≥ 95% |
| Statements | ≥ 95% |
| Branches | ≥ 90% |

**The coverage loop does not exit until ALL thresholds are met AND zero unit/integration tests fail.**

---

## Step 1 — Detect test stack

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"
ls package.json api/package.json requirements.txt pyproject.toml 2>/dev/null
cat package.json 2>/dev/null | grep -E '"vitest"|"jest"' || true
cat api/package.json 2>/dev/null | grep '"jest"' || true
ls e2e/ tests/e2e/ playwright.config.* e2e/playwright.config.* 2>/dev/null || true
```

Determine which layers apply:
- **Frontend unit/integration (Vitest)**: root `package.json` has `vitest`
- **Backend unit/integration (Jest)**: `api/package.json` has `jest`
- **Python unit/integration (pytest)**: `pyproject.toml` or `requirements.txt` present
- **E2E/System (Playwright)**: `playwright.config.*` found anywhere
- **E2E/System (pytest)**: `tests/e2e/` directory found in Python project

---

## Phase 1 — Unit Tests

Run smallest-scope tests first to get fast feedback.

### Frontend unit (Vitest):
```bash
cd "$PROJECT_ROOT"
npm run test:unit 2>&1
```

### Backend unit (Jest):
```bash
cd "$PROJECT_ROOT/api"
npm run test:unit 2>&1
```

### Python unit (pytest):
```bash
cd "$PROJECT_ROOT"
./venv/bin/python -m pytest tests/unit/ -v --tb=short -q
```

**Test patterns:**
- Pure functions, hooks, utilities, lib modules
- Every code path: success, error, edge cases, empty input, boundary values
- Mock ALL external services (Firebase, Stripe, cloud APIs, DB in unit tests)

---

## Phase 2 — Integration Tests

### Frontend integration (Vitest):
```bash
cd "$PROJECT_ROOT"
npm run test:integration 2>&1
```

### Backend integration (Jest + supertest):
```bash
cd "$PROJECT_ROOT/api"
npm run test:integration 2>&1
```

### Python integration (pytest):
```bash
cd "$PROJECT_ROOT"
./venv/bin/python -m pytest tests/integration/ -v --tb=short -q
```

**Test patterns:**
- Full HTTP request → response through the real app
- Multi-component flows, context providers, routing, auth state
- Mock only the outermost network boundary (external APIs) — not internal logic

---

## Phase 3 — Coverage loop (unit + integration)

Run coverage for all detected stacks and loop until thresholds are met:

### Vitest (frontend):
```bash
cd "$PROJECT_ROOT"
npm run test:coverage 2>&1
```

### Jest (backend):
```bash
cd "$PROJECT_ROOT/api"
npm run test:coverage 2>&1
```

### pytest (Python):
```bash
cd "$PROJECT_ROOT"
./venv/bin/python -m pytest tests/unit/ tests/integration/ --cov=. --cov-report=term-missing -q
```

**Loop logic:**
1. Parse coverage output — find files below threshold, find failing tests
2. If all thresholds met AND zero failures → **exit loop ✅**
3. Otherwise:
   - For each uncovered file: read it, write tests targeting uncovered lines/branches
   - For each failing test: fix the test or the underlying code
   - Re-run from top of loop

**Rules inside the loop:**
- Read the source file before writing tests — understand all code paths
- Test ALL paths: success, error, edge cases, auth failures, DB errors, empty state
- Never skip, xfail, or comment-out failing tests — fix the code or the test
- Each iteration targets the files with lowest coverage first

---

## Phase 4 — E2E / System Tests

Run after unit + integration pass. E2E failures are reported but do NOT cause the coverage loop to re-run.

### Playwright (JS/TS projects):

```bash
cd "$PROJECT_ROOT"
# Default: against local/configured environment
npx playwright test --config=e2e/playwright.config.ts 2>/dev/null \
  || npx playwright test 2>/dev/null \
  || echo "No Playwright config found — skipping E2E"
```

With `--e2e staging`:
```bash
BASE_URL=<staging-url> npx playwright test --config=e2e/playwright.config.ts
```

With `--e2e prod`:
```bash
BASE_URL=<prod-url> npx playwright test --config=e2e/playwright.config.ts
```

With `--e2e <test-file>`:
```bash
npx playwright test --config=e2e/playwright.config.ts <test-file>
```

### pytest E2E (Python projects):
```bash
cd "$PROJECT_ROOT"
./venv/bin/python -m pytest tests/e2e/ -v --tb=short 2>/dev/null \
  || echo "No E2E tests found — skipping"
```

**If E2E fails:**
1. Read the error output and diagnose the issue
2. Report which tests failed and why
3. Suggest fixes — but do NOT block the overall `/test` pass if unit + integration coverage is met

---

## Mock rules

**Prefer real implementations.** Only mock:
- External APIs that cannot run locally (Firebase Auth, Stripe, Resend, payment gateways, cloud services)
- Database client in unit tests only — integration tests use the real app/DB
- Do NOT mock internal business logic, utilities, or pure functions

### JS/TS backend mock pattern:
```typescript
// Always include __esModule: true in mock factories
jest.mock('../../db/client', () => ({
  __esModule: true,
  default: { query: jest.fn(), queryOne: jest.fn(), getPool: jest.fn() },
}))
```

### Python mock pattern:
```python
from unittest.mock import AsyncMock, patch

async def test_something(monkeypatch):
    monkeypatch.setattr("module.external_client.call", AsyncMock(return_value={"ok": True}))
```

---

## Output at each coverage iteration

```
=== Test Iteration N ===
Frontend:  lines X% | functions X% | branches X%
Backend:   lines X% | functions X% | branches X%
Python:    lines X% | functions X% | branches X%
Failing:   N tests
Action:    [what's being written / fixed]
```

## Final output

```
=== /test Complete ===
Unit:        ✅ X passed
Integration: ✅ X passed
Frontend:    lines ✅ X% | functions ✅ X% | branches ✅ X%
Backend:     lines ✅ X% | functions ✅ X% | branches ✅ X%
E2E:         ✅ X passed | ⚠️ X failed (non-blocking) | skipped
Failures:    0 ✅
New files:   [list]
Status:      COVERAGE MET ✅
```

$ARGUMENTS
