# CLAUDE.md — [Project Name]
Last updated: YYYY-MM-DD

## Project Overview
[One paragraph describing what this project does]

## Tech Stack
- Services: [api, dashboard, postgres, redis, etc]
- Orchestration: Docker Compose
- Testing: [per-service test stacks]

## Key Commands
```bash
# Build
docker build -t [project]-api:local .
docker build -t [project]-dashboard:local ./dashboard

# Run
docker compose up -d
docker compose ps
docker compose logs -f [service]

# Migrations
docker compose run --rm migrate

# Stop
docker compose down
```

## Health Endpoints
- API: http://localhost:8000/health
- Dashboard: http://localhost:3001

## Smoke Test
```bash
curl -s http://localhost:8000/health   # Should return {"status":"healthy"}
curl -s -o /dev/null -w "%{http_code}" http://localhost:3001/  # Should return 200
```

## Security — Known Exceptions
<!-- List any accepted audit exceptions here -->

## Conventions
- Migrations in alembic/ or migrations/
- Each service has its own Dockerfile
- Compose file at docker-compose.yml or deploy/docker-compose.yml
