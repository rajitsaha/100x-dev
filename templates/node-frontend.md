# [Project Name] — Project Instructions
Last updated: YYYY-MM-DD

## Project Overview
[One paragraph describing what this project does]

## Tech Stack
- Framework: React + Vite
- Language: TypeScript
- Styling: [Tailwind / shadcn / etc]
- Testing: Vitest + Testing Library
- E2E: Playwright (optional)

## Key Commands
```bash
npm run dev          # Start dev server
npm run build        # Production build
npm run test:unit    # Unit tests
npm run test:coverage # Coverage report
npm run lint         # ESLint
```

## Health Endpoints
- Local: http://localhost:5173

## Security — Known Exceptions
<!-- List any accepted audit exceptions here, e.g.: -->
<!-- - undici via Firebase SDK — requires --force to fix, known safe -->

## Conventions
- Components in src/components/
- Pages in src/pages/
- Utilities in src/lib/
- Tests mirror src/ structure in src/__tests__/

## Common CI Traps

**`opacity-0` breaks Playwright** — `useState(false)` + `useEffect(() => setState(true), [])` to trigger a CSS fade-in is a common pattern, but Playwright's `toBeVisible()` fails on `opacity-0` elements. In a client-only SPA there is no SSR reason to defer visibility — initialize to `true` directly.

```tsx
// Wrong — form is invisible on first render; Playwright times out
const [mounted, setMounted] = useState(false);
useEffect(() => { setMounted(true); }, []);

// Right — immediately visible, no effect needed
const mounted = true;
```

**ESLint plugin version skew** — if CI uses a newer eslint plugin version than is pinned locally, errors appear in CI but not on your machine. Pin exact plugin versions in `package.json` to keep CI and local in sync.

```json
// Pin exact versions, not ranges, for lint plugins
"eslint-plugin-react-hooks": "5.2.0"
```

**npm packages not yet published** — never add a package to `dependencies` that doesn't exist on the npm registry yet. Docker builds will fail with a 404 at `npm install` time. Use `file:` paths or vendor the source instead.
