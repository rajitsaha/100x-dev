# CLAUDE.md — [Project Name]
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
