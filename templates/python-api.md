# CLAUDE.md — [Project Name]
Last updated: YYYY-MM-DD

## Project Overview
[One paragraph describing what this project does]

## Tech Stack
- Language: Python 3.11+
- Framework: FastAPI / Flask
- Database: PostgreSQL / SQLite
- Testing: pytest + pytest-cov
- Linting: ruff

## Key Commands
```bash
source venv/bin/activate          # Activate virtualenv
./venv/bin/python -m uvicorn main:app --reload  # Start dev server
./venv/bin/python -m pytest tests/ -v           # Run tests
./venv/bin/python -m pytest --cov=. --cov-report=term-missing  # Coverage
./venv/bin/ruff check . --fix     # Lint + fix
./venv/bin/ruff format .          # Format
```

## Health Endpoints
- Local: http://localhost:8000/health
- Production: https://[your-api-url]/health

## Security — Known Exceptions
<!-- List any accepted pip-audit exceptions here -->

## Conventions
- Routes in routes/ or api/routes/
- Models in models/
- Tests in tests/unit/ and tests/integration/
- All routes require auth except /health
