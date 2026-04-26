# Common CI Traps

Three bugs that consistently cause CI failures when AI tools generate pipelines. Each trap passes locally but fails in CI — usually in Docker builds or E2E test runs.

---

## Trap 1 — npm package not published → Docker build 404

**Where it appears:** Any project that injects local packages into a generated `package.json` and builds a Docker image in CI.

**Symptom:**
```
npm error 404 Not Found - GET https://registry.npmjs.org/@yourorg%2finternal-pkg
npm error 404 '@yourorg/internal-pkg@^0.1.0' is not in this registry.
ERROR: failed to solve: process "/bin/sh -c npm install" did not complete successfully
```

**Why it passes locally:** The package exists in your local `node_modules` from a previous install. Docker has no such cache — it runs a clean `npm install` every build.

**Fix A — file: reference**
```json
"dependencies": {
  "@yourorg/internal-pkg": "file:./internal-pkg"
}
```
Include the package directory in the Docker build context.

**Fix B — vendor source directly**
```python
# In your build script: copy source into the Docker build context
shutil.copy("internal-pkg/src/index.ts", build_dir / "internal-pkg.ts")
```
```typescript
// In your template: import from relative path instead of npm
import { MyClass } from './internal-pkg.js'
```

**Fix B is preferred** when the package has no runtime dependencies (just a single TypeScript file). No npm install step needed at all.

---

## Trap 2 — `useState(false)` animation → Playwright `toBeVisible()` timeout

**Where it appears:** React SPAs with CSS enter-animations that use React state to trigger the transition.

**Symptom:**
```
Error: expect(locator).toBeVisible() failed
Locator: locator('input[type="email"]')
Expected: visible
Timeout: 10000ms
Error: element(s) not found
```
The element *is* in the DOM — it just has `opacity: 0`.

**The pattern:**
```tsx
const [mounted, setMounted] = useState(false);

useEffect(() => {
  setMounted(true);   // ← ESLint: react-hooks/set-state-in-effect
}, []);

return (
  <form className={mounted ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2"}>
    <input type="email" />
  </form>
);
```

**Why it was written this way:** This is an SSR hydration guard. In Next.js or Remix, components render on the server before `useEffect` runs, so `mounted=false` prevents a flash of unstyled content. In a client-only Vite/CRA SPA it serves no purpose.

**Why Playwright fails:** `toBeVisible()` evaluates CSS visibility, not just DOM presence. `opacity: 0` makes the element invisible. On the first paint the element is invisible; by the time Playwright checks, the `useEffect` may or may not have run depending on timing.

**Fix — initialize `mounted` to `true`:**
```tsx
const mounted = true;   // no useState, no useEffect
```
Or if you need reactivity for another reason:
```tsx
const [mounted] = useState(true);
```

**For the animation:** Use CSS `@keyframes` directly on the element instead of toggling classes via React state:
```css
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}
.login-form { animation: fadeIn 0.3s ease; }
```

---

## Trap 3 — Integration tests excluded from the CI gate

**Where it appears:** Python projects where the CI was set up quickly and only `tests/unit/` was added.

**Symptom:** Tests pass in CI, but a Docker-build failure, a broken database migration, or an npm 404 only surfaces after the PR is merged — because those tests live in `tests/integration/` which was never included in the gate.

**Wrong:**
```yaml
run: pytest tests/unit/
```

**Right:**
```yaml
run: pytest tests/unit/ tests/integration/
```

**Common integration tests that only run in `tests/integration/`:**
- Docker image builds (`subprocess.run(["docker", "build", ...])`)
- Database migration tests (hit a real Postgres service)
- External API contract tests
- Generated file correctness (Dockerfiles, package.json, YAML schemas)

**Note:** Tests that require Docker are typically marked `@pytest.mark.skipif(not _docker_available(), ...)` and skip locally when Docker isn't running. In GitHub Actions, Docker is always available, so they will run — and fail if the code is broken.

---

## ESLint plugin version skew (bonus trap)

**Symptom:** ESLint errors appear in CI but not locally. Same code, different results.

**Cause:** The CI runner installs the latest versions of ESLint plugins (within the semver range in `package.json`), while your local `node_modules` has an older locked version. A new plugin version may add or tighten rules.

**Fix:** Pin exact versions for ESLint plugins in `package.json`:
```json
"devDependencies": {
  "eslint-plugin-react-hooks": "5.2.0",
  "typescript-eslint": "8.32.1"
}
```
Then regenerate `package-lock.json` and commit it. CI will use exactly the pinned versions.
