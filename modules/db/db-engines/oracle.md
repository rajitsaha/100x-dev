# db-engine: oracle
<!-- Implements _router.md skeleton for Oracle Database -->

Receives pre-resolved variables from /db router: $DB_HOST, $DB_PORT, $DB_NAME, $DB_USER, $DB_PASS, $SQL

**CLI:** `sqlplus` | **Default port:** 1521 | **SSL:** wallet-based

```bash
sqlplus "$DB_USER/$DB_PASS@$DB_HOST:${DB_PORT:-1521}/$DB_NAME" <<< "$SQL"
```

**Driver fallback:** Node `oracledb` — `oracledb.getConnection({ user, password, connectString })`

**Migration detection:** Flyway or Liquibase config → run migrate
