# db-engine: snowflake
<!-- Implements _router.md skeleton for Snowflake -->

Receives pre-resolved variables from /db router: $DB_HOST, $DB_PORT, $DB_NAME, $DB_USER, $DB_PASS, $SQL

**CLI:** `snowsql` | **Default port:** 443 (HTTPS) | **SSL:** always (no flag needed)

```bash
snowsql -a "$DB_HOST" -u "$DB_USER" -d "$DB_NAME" -r "$DB_ROLE" -q "$SQL"
```

**Driver fallback:** Node `snowflake-sdk` — `snowflake.createConnection({ account, username, password, database })`

**Migration detection:** Flyway config → `flyway migrate` | migrations/*.sql → apply in order
