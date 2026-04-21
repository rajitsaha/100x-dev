# Query — Plain-English Database Analytics
<!-- model: haiku -->

Describe what you want to know — Claude writes and runs the query.

## How to use
- `/query <business question>` — Claude translates to SQL, runs it, returns analysis

## Supported interfaces
- **BigQuery**: `bq` CLI — `bq query`, `bq show`, `bq ls`
- **PostgreSQL**: `psql` CLI
- **MySQL**: `mysql` CLI
- **SQLite**: `sqlite3` CLI

---

## Phase 1 — Understand the question

Restate the business question in concrete terms. If the schema is ambiguous, inspect it first:

```bash
# BigQuery — show table schema
bq show <dataset>.<table>

# PostgreSQL
PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" \
  -c "\d <table_name>"
```

---

## Phase 2 — Write and run the query

Write the SQL for the business question. Run it using the appropriate CLI. Explain the results in plain English.

---

## Phase 3 — Return results

Return:
1. The SQL written
2. A plain-English answer to the original question
3. A table of key numbers

For recurring queries: offer to save as a named script.

## Scope vs `/db`
- `/query` = analytics in plain English (you describe a business question)
- `/db` = execute specific SQL against a named connection (you write the SQL or say "migrate")
