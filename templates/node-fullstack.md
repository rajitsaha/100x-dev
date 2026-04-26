# [Project Name] — Project Instructions
Last updated: YYYY-MM-DD

## Project Overview
[One paragraph describing what this project does]

## Tech Stack
- Frontend: React + Vite + TypeScript
- Backend: Node.js + Express/Fastify + TypeScript
- Database: PostgreSQL
- Auth: [Firebase / JWT / etc]
- Testing: Vitest (frontend) + Jest + supertest (backend)
- E2E: Playwright

## Key Commands
```bash
# Frontend (root)
npm run dev            # Start frontend dev server
npm run build          # Frontend production build
npm run test:coverage  # Frontend coverage

# Backend (api/)
cd api && npm run dev        # Start API server
cd api && npm run build      # Backend build
cd api && npm run test:coverage # Backend coverage
```

## Health Endpoints
- Local API: http://localhost:3001/health
- Local Frontend: http://localhost:5173
- Production API: https://[your-api-url]/health
- Production Frontend: https://[your-frontend-url]

## Security — Known Exceptions
<!-- List any accepted audit exceptions here -->

## Conventions
- API routes in api/src/routes/
- Frontend components in src/components/
- Shared types in src/types/ or api/src/types/
- All routes require auth middleware except /health and /webhooks

## Common CI Traps

**npm packages not yet published** — if a package is listed in `dependencies` but not on the npm registry, Docker builds fail with a 404 at `npm install`. Use `file:` paths for local packages or vendor the source directly into the build context.

```json
// Wrong — 404 in Docker if package isn't published
"dependencies": { "@yourorg/internal-pkg": "^0.1.0" }

// Right — reference local source
"dependencies": { "@yourorg/internal-pkg": "file:./internal-pkg" }
```

**`opacity-0` breaks Playwright** — `useState(false)` + `useEffect(() => setState(true), [])` for CSS enter-animations makes elements invisible on first render. Playwright's `toBeVisible()` fails. In SPAs initialize to `true` and use CSS `@keyframes` for animations instead.

**ESLint plugin version skew** — CI may use a newer plugin version than is installed locally, causing errors in CI that don't reproduce. Pin exact versions for lint plugins in `package.json`.

**Integration tests silently excluded from gate** — always run both `tests/unit/` and `tests/integration/` in CI. Omitting integration tests means Docker-build failures and DB regressions only surface after merge.
