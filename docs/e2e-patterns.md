# E2E Test Patterns

Reference patterns for Playwright fixtures, auth helpers, smoke tests, and CRUD tests.
These are used by the `/test` workflow (Phase 4) when setting up E2E tests.

---

### 4c. API helper + real auth fixture

E2E tests need an authenticated browser page. **Create test users via the real API — never hardcode credentials or mock auth.**

**`e2e/fixtures/api.ts`** — authenticated HTTP client:
```typescript
import { APIRequestContext } from '@playwright/test'

export async function createTestUser(
  request: APIRequestContext,
  overrides?: Partial<{ email: string; password: string; name: string }>
) {
  const email = overrides?.email ?? `test-${Date.now()}@example.com`
  const password = overrides?.password ?? 'TestPass123!'
  const name = overrides?.name ?? 'Test User'

  const res = await request.post('/api/auth/register', {
    data: { email, password, name },
  })
  if (!res.ok()) throw new Error(`User creation failed: ${await res.text()}`)
  return { email, password, name, id: (await res.json()).id }
}

export async function getAuthToken(
  request: APIRequestContext,
  email: string,
  password: string
): Promise<string> {
  const res = await request.post('/api/auth/login', {
    data: { email, password },
  })
  if (!res.ok()) throw new Error(`Login failed: ${await res.text()}`)
  return (await res.json()).token
}
```

**`e2e/fixtures/auth.ts`** — real auth fixture (actual login, not mocked JWT):
```typescript
import { test as base, expect } from '@playwright/test'
import { createTestUser, getAuthToken } from './api'

type AuthFixtures = {
  authToken: string
  authenticatedPage: import('@playwright/test').Page
  testUser: { email: string; password: string; name: string; id: string }
}

export const test = base.extend<AuthFixtures>({
  testUser: async ({ request }, use) => {
    const user = await createTestUser(request)
    await use(user)
    // Cleanup: delete user after test (or let DB reset handle it)
  },

  authToken: async ({ request, testUser }, use) => {
    const token = await getAuthToken(request, testUser.email, testUser.password)
    await use(token)
  },

  authenticatedPage: async ({ page, authToken }, use) => {
    // Inject real token into browser storage (not mocked)
    await page.goto('/')
    await page.evaluate(
      (token) => localStorage.setItem('authToken', token),
      authToken
    )
    await page.reload()
    await use(page)
  },
})

export { expect }
```

### 4d. Smoke + health tests

Smoke tests verify the stack is up and critical paths respond before running full E2E. Run these first.

**`e2e/smoke/health.spec.ts`**:
```typescript
import { test, expect } from '@playwright/test'

test.describe('Health checks', () => {
  test('API /health returns 200', async ({ request }) => {
    const res = await request.get('/health')
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body.status).toBe('ok')
  })

  test('API /health/db confirms DB connection', async ({ request }) => {
    const res = await request.get('/health/db')
    expect(res.status()).toBe(200)
    const body = await res.json()
    expect(body.database).toBe('connected')
  })

  test('frontend loads without JS errors', async ({ page }) => {
    const errors: string[] = []
    page.on('console', (msg) => {
      if (msg.type() === 'error') errors.push(msg.text())
    })
    await page.goto('/')
    await expect(page).toHaveTitle(/your app name/i)
    expect(errors).toHaveLength(0)
  })

  test('login page renders', async ({ page }) => {
    await page.goto('/login')
    await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible()
  })
})
```

**Run smoke tests first, gate on them:**
```bash
# Run smoke only — fast check before full suite
BASE_URL="${E2E_BASE_URL:-http://localhost:3000}" \
npx playwright test e2e/smoke/ --config=playwright.e2e.config.ts
```

### 4e. Real auth E2E tests

Browser flows that use the real auth fixture — **no mocked JWT, no bypassed login**.

**`e2e/auth/login.spec.ts`**:
```typescript
import { test, expect } from '../fixtures/auth'

test.describe('Authentication — real browser flow', () => {
  test('user can register and land on dashboard', async ({ page, request }) => {
    const email = `e2e-${Date.now()}@example.com`
    const password = 'TestPass123!'

    // Register via UI
    await page.goto('/register')
    await page.getByLabel('Email').fill(email)
    await page.getByLabel('Password').fill(password)
    await page.getByRole('button', { name: /create account/i }).click()

    // Assert redirect to dashboard after real registration
    await expect(page).toHaveURL(/\/dashboard/)
    await expect(page.getByText(/welcome/i)).toBeVisible()

    // Confirm user actually exists in DB (via API)
    const token = await (
      await request.post('/api/auth/login', { data: { email, password } })
    ).json()
    expect(token.token).toBeTruthy()
  })

  test('user can log in with real credentials', async ({ page, testUser }) => {
    await page.goto('/login')
    await page.getByLabel('Email').fill(testUser.email)
    await page.getByLabel('Password').fill(testUser.password)
    await page.getByRole('button', { name: /sign in/i }).click()

    await expect(page).toHaveURL(/\/dashboard/)
    await expect(page.getByText(testUser.name)).toBeVisible()
  })

  test('invalid credentials show error', async ({ page }) => {
    await page.goto('/login')
    await page.getByLabel('Email').fill('nobody@example.com')
    await page.getByLabel('Password').fill('wrongpassword')
    await page.getByRole('button', { name: /sign in/i }).click()

    await expect(page.getByRole('alert')).toContainText(/invalid/i)
    await expect(page).toHaveURL(/\/login/)  // stays on login
  })
})
```

### 4f. Real CRUD E2E tests

Browser creates an entity → API confirms it actually persisted. **No mock return values.**

**`e2e/agents/crud.spec.ts`** (example — adapt to your entity):
```typescript
import { test, expect } from '../fixtures/auth'

test.describe('Agent CRUD — real browser + DB', () => {
  test('create agent via UI and verify persistence', async ({
    authenticatedPage: page,
    request,
    authToken,
  }) => {
    await page.goto('/dashboard/agents')
    await page.getByRole('button', { name: /new agent/i }).click()

    const agentName = `Test Agent ${Date.now()}`
    await page.getByLabel('Name').fill(agentName)
    await page.getByLabel('Description').fill('Created by E2E test')
    await page.getByRole('button', { name: /create/i }).click()

    // UI confirms creation
    await expect(page.getByText(agentName)).toBeVisible()

    // API confirms it actually persisted — not just UI state
    const res = await request.get('/api/agents', {
      headers: { Authorization: `Bearer ${authToken}` },
    })
    const agents = await res.json()
    const created = agents.find((a: { name: string }) => a.name === agentName)
    expect(created).toBeDefined()
    expect(created.description).toBe('Created by E2E test')
  })

  test('edit agent updates DB record', async ({
    authenticatedPage: page,
    request,
    authToken,
    testUser,
  }) => {
    // Create agent via API (not UI — faster setup)
    const createRes = await request.post('/api/agents', {
      headers: { Authorization: `Bearer ${authToken}` },
      data: { name: 'Original Name', description: 'Original' },
    })
    const agent = await createRes.json()

    // Edit via UI
    await page.goto(`/dashboard/agents/${agent.id}`)
    await page.getByLabel('Name').clear()
    await page.getByLabel('Name').fill('Updated Name')
    await page.getByRole('button', { name: /save/i }).click()

    await expect(page.getByText('Updated Name')).toBeVisible()

    // Confirm DB was updated
    const fetchRes = await request.get(`/api/agents/${agent.id}`, {
      headers: { Authorization: `Bearer ${authToken}` },
    })
    expect((await fetchRes.json()).name).toBe('Updated Name')
  })

  test('delete agent removes from DB', async ({
    authenticatedPage: page,
    request,
    authToken,
  }) => {
    const createRes = await request.post('/api/agents', {
      headers: { Authorization: `Bearer ${authToken}` },
      data: { name: 'To Be Deleted', description: 'Temp' },
    })
    const agent = await createRes.json()

    await page.goto('/dashboard/agents')
    await page.getByTestId(`agent-row-${agent.id}`).getByRole('button', { name: /delete/i }).click()
    await page.getByRole('button', { name: /confirm/i }).click()

    await expect(page.getByText('To Be Deleted')).not.toBeVisible()

    // Confirm gone from DB
    const fetchRes = await request.get(`/api/agents/${agent.id}`, {
      headers: { Authorization: `Bearer ${authToken}` },
    })
    expect(fetchRes.status()).toBe(404)
  })
})
```

### 4g. Running E2E

**Start full stack:**
```bash
cd "$PROJECT_ROOT"

if [ -f docker-compose.e2e.yml ] && [ -f docker-compose.yml ]; then
  COMPOSE_CMD="docker compose -f docker-compose.yml -f docker-compose.e2e.yml"
elif [ -f docker-compose.test.yml ]; then
  COMPOSE_CMD="docker compose -f docker-compose.test.yml"
else
  COMPOSE_CMD="docker compose"
fi

$COMPOSE_CMD up -d --build --wait
```

**Wait for app health:**
```bash
for i in $(seq 1 12); do
  curl -sf http://localhost:8000/health 2>/dev/null && echo "API healthy ✅" && break || \
  curl -sf http://localhost:3000/health 2>/dev/null && echo "App healthy ✅" && break || \
  curl -sf http://localhost:8080/health 2>/dev/null && echo "App healthy ✅" && break
  echo "Attempt $i/12 — waiting for app..."
  sleep 5
done
```

**Run in order — smoke first, then full suite:**
```bash
# 1. Smoke tests (fast gate)
BASE_URL="${E2E_BASE_URL:-http://localhost:3000}" \
npx playwright test e2e/smoke/ --config=playwright.e2e.config.ts

# 2. Full E2E suite
BASE_URL="${E2E_BASE_URL:-http://localhost:3000}" \
npx playwright test --config=playwright.e2e.config.ts
```

With `--e2e staging`:
```bash
BASE_URL=<staging-url> npx playwright test --config=playwright.e2e.config.ts
```

With `--e2e prod`:
```bash
BASE_URL=<prod-url> npx playwright test --config=playwright.e2e.config.ts
```

**pytest E2E (Python projects):**
```bash
cd "$PROJECT_ROOT"
BASE_URL="${E2E_BASE_URL:-http://localhost:8000}" \
./venv/bin/python -m pytest tests/e2e/ -v --tb=short 2>/dev/null \
  || echo "No E2E tests found — skipping"
```

**Teardown full stack after E2E:**
```bash
$COMPOSE_CMD down -v 2>/dev/null || true
```

**If E2E fails:**
1. Capture logs: `$COMPOSE_CMD logs --tail=100`
2. Check Playwright artifacts: `playwright-report/index.html` (screenshots, traces, videos)
3. Read the error output and diagnose the issue
4. Report which tests failed and why with container logs
5. Suggest fixes — but do NOT block the overall `/test` pass if unit + integration coverage is met

