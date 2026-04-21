# db-engine: postgres
<!-- Implements _router.md skeleton for PostgreSQL and Supabase -->

Receives pre-resolved variables from /db router: $DB_HOST, $DB_PORT, $DB_NAME, $DB_USER, $DB_PASS, $SQL

**CLI:** `psql` | **Default port:** 5432 | **SSL:** `--set=sslmode=require` (always for non-localhost)

```bash
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "${DB_PORT:-5432}" -U "$DB_USER" -d "$DB_NAME" \
  --set=sslmode=require -c "$SQL"
```

**Driver fallback:** Node `pg` — `new Pool({ host, port, user, password, database, ssl: { rejectUnauthorized: true } })`

**Migration detection:** alembic.ini → `alembic upgrade head` | migrations/*.sql → apply in order
