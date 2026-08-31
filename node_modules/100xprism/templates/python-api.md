# [Project Name] — Project Instructions
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

## Common CI Traps

**Integration tests not in the gate** — `pytest tests/unit/` is the default but `tests/integration/` must be added explicitly. If integration tests only run locally, regressions ship silently.

```bash
# Wrong — misses integration tests
pytest tests/unit/

# Right — gate both
pytest tests/unit/ tests/integration/
```

**Docker builds referencing local packages** — if a package is injected as a dependency but not yet published to a registry, `npm install` / `pip install` will fail in CI with a 404. Fix: vendor the source directly into the build context or use a `file:` path.

```python
# Wrong — package not on PyPI yet
deps = {"my-internal-pkg": "^0.1.0"}

# Right — vendor source into container
shutil.copy(LOCAL_SRC, build_dir / "my_internal_pkg.py")
```
