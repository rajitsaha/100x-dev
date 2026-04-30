# db-engine: databricks
<!-- Implements _router.md skeleton for Databricks SQL -->

Receives pre-resolved variables from /db router: $DB_HOST, $DB_PORT, $DB_NAME, $DB_USER, $DB_PASS, $SQL

**CLI:** `databricks-sql-cli` | **Default port:** 443 | **SSL:** always

```bash
databricks-sql-cli --server-hostname "$DB_HOST" --http-path "$DB_HTTP_PATH" --access-token "$DB_PASS" -e "$SQL"
```

**Driver fallback:** Node `@databricks/sql` — connect via HTTP path and personal access token

**Migration detection:** Delta Lake SQL scripts → apply in order via CLI
