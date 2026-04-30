# db-engine: cloud-sql
<!-- Implements _router.md skeleton for GCP Cloud SQL (PostgreSQL or MySQL) -->

Receives pre-resolved variables from /db router: $DB_HOST, $DB_PORT, $DB_NAME, $DB_USER, $DB_PASS, $SQL

**CLI:** `gcloud sql connect` or `psql`/`mysql` via Cloud SQL Auth Proxy | **Port:** 5432 (PG) or 3306 (MySQL)

```bash
# Start Cloud SQL Auth Proxy then connect
cloud-sql-proxy "$PROJECT:$REGION:$INSTANCE" --port "${DB_PORT:-5432}" &
PGPASSWORD="$DB_PASS" psql -h 127.0.0.1 -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" -c "$SQL"
```

**Driver fallback:** Node `pg` or `mysql2` via Cloud SQL Auth Proxy (standard connection)

**Migration detection:** alembic.ini (PG) → `alembic upgrade head` | Flyway config (MySQL) → `flyway migrate`
