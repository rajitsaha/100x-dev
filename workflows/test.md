# Test — Run All Tests: Unit → Integration → E2E

You are a senior test engineer. Auto-detect all test layers (unit, integration, frontend, backend, E2E/system), run them all, write more if coverage is below threshold, and loop until everything passes.

## Do NOT ask for permission. Do NOT stop until coverage is met.

---

## Testing philosophy

**Prefer real implementations over mocks.**

| Layer | Environment | What to mock |
|---|---|---|
| Unit | In-process only | External APIs that cannot run locally (Stripe, Firebase Auth, Resend, Twilio, cloud SDKs) |
| Integration | Real DB + real app via Docker | Only payment gateways and third-party external APIs |
| E2E / System | Full stack via `docker compose up` | Nothing — zero mocks |

**Never mock:** the database, internal services, business logic, utilities, or pure functions.  
**Only mock:** services that are genuinely unreachable locally (payment processors, auth providers, email senders, external SaaS APIs).

---

## How to use

- `/test` — all layers for files changed since last commit
- `/test --all` — full pass across the entire codebase
- `/test <file>` — target a specific source file
- `/test --unit` — unit tests only
- `/test --integration` — integration tests only (spins up Docker services)
- `/test --e2e` — E2E/system tests only (full docker compose stack)
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

## Phase 0 — Docker test environment setup

Before running integration or E2E tests, check if Docker services are required and start them.

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"
```

### Detect test service requirements

```bash
# Check for docker-compose test config
TEST_COMPOSE=""
for f in docker-compose.test.yml docker-compose.testing.yml docker-compose.yml compose.yml; do
  [ -f "$PROJECT_ROOT/$f" ] && TEST_COMPOSE="$f" && break
done

# Check for service dependencies in pyproject.toml or package.json
grep -qE "postgres|redis|mysql|mongodb|elasticsearch" \
  "$PROJECT_ROOT/pyproject.toml" \
  "$PROJECT_ROOT/requirements*.txt" \
  "$PROJECT_ROOT/package.json" \
  "$PROJECT_ROOT/api/package.json" 2>/dev/null && NEEDS_SERVICES=true || NEEDS_SERVICES=false

echo "Test compose file: ${TEST_COMPOSE:-none}"
echo "Needs services: $NEEDS_SERVICES"
```

### Start test services (if needed)

**Option A — docker-compose test file exists:**
```bash
[ -n "$TEST_COMPOSE" ] && docker compose -f "$TEST_COMPOSE" up -d --wait 2>/dev/null
```

**Option B — no test compose, but services needed — start minimal stack:**
```bash
# Start only service containers, not the app itself
if $NEEDS_SERVICES && [ -n "$TEST_COMPOSE" ]; then
  # Start DB + cache only, skip app containers
  docker compose -f "$TEST_COMPOSE" up -d --wait \
    $(docker compose -f "$TEST_COMPOSE" config --services | grep -vE "^(api|app|backend|frontend|dashboard|web)$") 2>/dev/null || \
  docker compose up -d --wait db redis 2>/dev/null || true
fi
```

**Option C — no compose file, project has a Dockerfile — spin up test DB via docker run:**
```bash
if $NEEDS_SERVICES && [ -z "$TEST_COMPOSE" ]; then
  # PostgreSQL
  docker run -d --name test-postgres \
    -e POSTGRES_USER=test -e POSTGRES_PASSWORD=test -e POSTGRES_DB=test \
    -p 5432:5432 postgres:16 2>/dev/null || true
  # Redis (if referenced)
  grep -qE "redis" "$PROJECT_ROOT/pyproject.toml" "$PROJECT_ROOT/requirements*.txt" "$PROJECT_ROOT/package.json" 2>/dev/null && \
    docker run -d --name test-redis -p 6379:6379 redis:7 2>/dev/null || true
  # Wait for health
  sleep 3
  docker exec test-postgres pg_isready -U test 2>/dev/null || sleep 5
fi
```

**Run migrations against test DB:**
```bash
# Django
[ -f manage.py ] && ./venv/bin/python manage.py migrate --settings=config.settings.test 2>/dev/null || true
# Alembic
[ -f alembic.ini ] && ./venv/bin/alembic upgrade head 2>/dev/null || true
# Prisma
[ -f prisma/schema.prisma ] && npx prisma migrate deploy 2>/dev/null || true
# Custom
[ -f scripts/migrate.sh ] && bash scripts/migrate.sh 2>/dev/null || true
```

**Verify services are healthy before proceeding:**
```bash
docker compose ps 2>/dev/null || docker ps --filter "name=test-" 2>/dev/null
```

**GATE: Required services must be running before integration or E2E tests.**

### Cleanup (run after all tests complete)

```bash
# Stop test compose
[ -n "$TEST_COMPOSE" ] && docker compose -f "$TEST_COMPOSE" down -v 2>/dev/null || true
# Stop standalone containers
docker rm -f test-postgres test-redis 2>/dev/null || true
```

---

## Step 1 — Detect test stack

```bash
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
- Mock ONLY genuinely unreachable external services: Stripe, Firebase Auth, Resend, Twilio, AWS SES
- Do NOT mock the database — unit tests that need DB state should use the real test DB started in Phase 0
- Do NOT mock internal services, business logic, or utilities

---

## Phase 2 — Integration Tests

Run against real services started in Phase 0. No mocking of internal infrastructure.

### Frontend integration (Vitest):
```bash
cd "$PROJECT_ROOT"
npm run test:integration 2>&1
```

### Backend integration (Jest + supertest):
```bash
cd "$PROJECT_ROOT/api"
# Set test DB URL — real Docker DB from Phase 0
DATABASE_URL="${TEST_DATABASE_URL:-postgresql://test:test@localhost:5432/test}" \
REDIS_URL="${TEST_REDIS_URL:-redis://localhost:6379}" \
npm run test:integration 2>&1
```

### Python integration (pytest):
```bash
cd "$PROJECT_ROOT"
DATABASE_URL="${TEST_DATABASE_URL:-postgresql+asyncpg://test:test@localhost:5432/test}" \
REDIS_URL="${TEST_REDIS_URL:-redis://localhost:6379}" \
./venv/bin/python -m pytest tests/integration/ -v --tb=short -q
```

**Test patterns:**
- Full HTTP request → response through the real app against a real DB
- Multi-component flows, context providers, routing, auth state
- Real DB reads and writes — assert actual persisted state, not mock return values
- Mock ONLY payment gateways (Stripe) and third-party external APIs (email providers, SMS)
- Do NOT mock: your own DB, Redis, internal queues, internal services

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
DATABASE_URL="${TEST_DATABASE_URL:-postgresql://test:test@localhost:5432/test}" \
npm run test:coverage 2>&1
```

### pytest (Python):
```bash
cd "$PROJECT_ROOT"
DATABASE_URL="${TEST_DATABASE_URL:-postgresql+asyncpg://test:test@localhost:5432/test}" \
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
- Write integration tests that assert real DB state — not mock return values
- Never skip, xfail, or comment-out failing tests — fix the code or the test
- Each iteration targets the files with lowest coverage first

---

## Phase 4 — E2E / System Tests (Docker full-stack)

Run after unit + integration pass. Spins up the complete application stack via Docker and runs real browser or API tests against it. **Zero mocks.**

### Start full stack

```bash
cd "$PROJECT_ROOT"

# Prefer a test-specific compose file, fall back to main
COMPOSE_FILE=""
for f in docker-compose.test.yml docker-compose.testing.yml docker-compose.yml compose.yml; do
  [ -f "$f" ] && COMPOSE_FILE="$f" && break
done

if [ -n "$COMPOSE_FILE" ]; then
  echo "Starting full stack for E2E: $COMPOSE_FILE"
  docker compose -f "$COMPOSE_FILE" up -d --build --wait
  docker compose -f "$COMPOSE_FILE" ps
else
  echo "No compose file found — E2E tests skipped (add docker-compose.test.yml to enable)"
fi
```

**Wait for app health:**
```bash
# Try common health endpoints until one responds 200
for i in $(seq 1 12); do
  curl -sf http://localhost:8000/health 2>/dev/null && echo "API healthy ✅" && break || \
  curl -sf http://localhost:3000/health 2>/dev/null && echo "App healthy ✅" && break || \
  curl -sf http://localhost:8080/health 2>/dev/null && echo "App healthy ✅" && break
  echo "Attempt $i/12 — waiting for app..."
  sleep 5
done
```

### Playwright E2E (JS/TS projects):
```bash
cd "$PROJECT_ROOT"
BASE_URL="${E2E_BASE_URL:-http://localhost:3000}" \
npx playwright test --config=e2e/playwright.config.ts 2>/dev/null \
  || npx playwright test 2>/dev/null \
  || echo "No Playwright config found — skipping"
```

With `--e2e staging`:
```bash
BASE_URL=<staging-url> npx playwright test --config=e2e/playwright.config.ts
```

With `--e2e prod`:
```bash
BASE_URL=<prod-url> npx playwright test --config=e2e/playwright.config.ts
```

### pytest E2E (Python projects):
```bash
cd "$PROJECT_ROOT"
BASE_URL="${E2E_BASE_URL:-http://localhost:8000}" \
./venv/bin/python -m pytest tests/e2e/ -v --tb=short 2>/dev/null \
  || echo "No E2E tests found — skipping"
```

### Teardown full stack after E2E:
```bash
[ -n "$COMPOSE_FILE" ] && docker compose -f "$COMPOSE_FILE" down -v 2>/dev/null || true
```

**If E2E fails:**
1. Capture logs: `docker compose -f "$COMPOSE_FILE" logs --tail=50`
2. Read the error output and diagnose the issue
3. Report which tests failed and why with container logs
4. Suggest fixes — but do NOT block the overall `/test` pass if unit + integration coverage is met

---

## When writing new tests

### Integration test — Python example (real DB, no mocks):
```python
import pytest
import httpx

@pytest.mark.asyncio
async def test_create_agent_persists(async_client: httpx.AsyncClient, db_session):
    # Act — call real API against real test DB
    response = await async_client.post("/api/agents", json={"name": "test-agent"})
    assert response.status_code == 201
    agent_id = response.json()["id"]

    # Assert — verify it actually persisted in the real DB
    row = await db_session.execute("SELECT name FROM agents WHERE id = $1", agent_id)
    assert row["name"] == "test-agent"
```

### Integration test — JS/TS example (real DB via supertest):
```typescript
it("POST /agents persists to database", async () => {
  const res = await request(app).post("/agents").send({ name: "test-agent" })
  expect(res.status).toBe(201)

  // Assert real DB state — not a mock return value
  const row = await db.query("SELECT name FROM agents WHERE id = $1", [res.body.id])
  expect(row.rows[0].name).toBe("test-agent")
})
```

### Unit test — mock only external APIs:
```python
# ✅ Correct: mock only the external payment API
async def test_create_subscription(monkeypatch):
    monkeypatch.setattr("stripe.Subscription.create", AsyncMock(return_value={"id": "sub_test"}))
    result = await billing_service.create_subscription(user_id=1, plan="pro")
    assert result.stripe_subscription_id == "sub_test"

# ❌ Wrong: don't mock the DB
async def test_create_subscription(monkeypatch):
    monkeypatch.setattr("db.session.add", MagicMock())  # Never do this
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
Docker env:  ✅ services running | skipped (not needed)
Unit:        ✅ X passed
Integration: ✅ X passed (real DB)
Frontend:    lines ✅ X% | functions ✅ X% | branches ✅ X%
Backend:     lines ✅ X% | functions ✅ X% | branches ✅ X%
E2E:         ✅ X passed (full-stack Docker) | ⚠️ X failed (non-blocking) | skipped
Failures:    0 ✅
New files:   [list]
Status:      COVERAGE MET ✅
```
