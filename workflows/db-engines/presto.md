# db-engine: presto
<!-- Implements _router.md skeleton for Presto / Trino -->

Receives pre-resolved variables from /db router: $DB_HOST, $DB_PORT, $DB_NAME, $DB_USER, $DB_PASS, $SQL

**CLI:** `presto` | **Default port:** 8080 | **SSL:** `--server https://...`

```bash
presto --server "$DB_HOST:${DB_PORT:-8080}" --catalog hive --schema "$DB_NAME" --execute "$SQL"
```

**Driver fallback:** Node `presto-client` or Python `pyhive`

**Migration detection:** SQL scripts only (Presto is query-only, no DDL migrations)
