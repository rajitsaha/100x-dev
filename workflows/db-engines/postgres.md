# db-engine: postgres

Supports PostgreSQL and Supabase connections.

Receives pre-resolved variables from the /db router:
- $DB_HOST — hostname (e.g. db.supabase.co or localhost)
- $DB_PORT — port (default 5432)
- $DB_NAME — database name
- $DB_USER — database user
- $DB_PASS — resolved password
- $SQL — query to execute (or "migrate")

---

## Step 1 — Validate prerequisites

```bash
if command -v psql >/dev/null 2>&1; then
  echo "Using psql ✓"
  USE_PSQL=true
elif node -e "require('pg')" 2>/dev/null; then
  echo "Using Node pg ✓"
  USE_PSQL=false
else
  echo "ERROR: Neither psql nor Node pg found."
  echo "  Install psql: brew install postgresql"
  echo "  Or install pg: npm install pg"
  exit 1
fi
```

## Step 2 — Execute query via psql

```bash
if [ "$USE_PSQL" = "true" ] && [ "$SQL" != "migrate" ]; then
  PGPASSWORD="$DB_PASS" psql \
    -h "$DB_HOST" \
    -p "${DB_PORT:-5432}" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    --set=sslmode=require \
    -c "$SQL"
fi
```

## Step 3 — Execute query via Node pg

```bash
if [ "$USE_PSQL" = "false" ] && [ "$SQL" != "migrate" ]; then
  DB_HOST="$DB_HOST" DB_PORT="${DB_PORT:-5432}" DB_USER="$DB_USER" \
  DB_PASS="$DB_PASS" DB_NAME="$DB_NAME" SQL="$SQL" \
  node -e "
  const { Pool } = require('pg');
  const pool = new Pool({
    host: process.env.DB_HOST,
    port: parseInt(process.env.DB_PORT),
    user: process.env.DB_USER,
    password: process.env.DB_PASS,
    database: process.env.DB_NAME,
    ssl: process.env.DB_HOST !== 'localhost' ? { rejectUnauthorized: false } : false,
  });
  (async () => {
    const client = await pool.connect();
    try {
      const r = await client.query(process.env.SQL);
      console.table(r.rows);
    } finally {
      client.release();
      await pool.end();
    }
  })().catch(e => { console.error('ERROR:', e.message); process.exit(1); });
  "
fi
```

## Step 4 — Migrate (if SQL = "migrate")

```bash
if [ "$SQL" = "migrate" ]; then
  PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME")
  if [ -f "$PROJECT_ROOT/alembic.ini" ]; then
    echo "Running Alembic migrations..."
    cd "$PROJECT_ROOT" && ./venv/bin/alembic upgrade head
  elif ls "$PROJECT_ROOT"/migrations/*.sql 2>/dev/null | head -1 > /dev/null 2>&1; then
    echo "Running SQL migration scripts..."
    for f in "$PROJECT_ROOT"/migrations/*.sql; do
      echo "  Applying $(basename "$f")..."
      PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" -f "$f"
    done
  else
    echo "No migration tool detected. Check for alembic.ini or migrations/*.sql"
    exit 1
  fi
fi
```

## Safety rules
- Never log or print $DB_PASS
- For Supabase: SSL is always required (use connection pooler host, not direct host)
- Never commit connection strings containing passwords
- Local connections (localhost) skip SSL automatically
