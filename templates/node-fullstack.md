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
