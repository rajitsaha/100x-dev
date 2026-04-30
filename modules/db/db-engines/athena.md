# db-engine: athena
<!-- Implements _router.md skeleton for AWS Athena -->

Receives pre-resolved variables from /db router: $DB_HOST, $DB_PORT, $DB_NAME, $DB_USER, $DB_PASS, $SQL

**CLI:** `aws athena` | **Port:** HTTPS | **SSL:** always (AWS SDK)

```bash
aws athena start-query-execution --query-string "$SQL" \
  --result-configuration OutputLocation="s3://$S3_BUCKET/" \
  --query-execution-context Database="$DB_NAME"
```

**Driver fallback:** Node `aws-sdk` with Athena client — `AthenaClient` + `StartQueryExecutionCommand`

**Migration detection:** Athena DDL SQL scripts (CREATE TABLE, ALTER TABLE) → apply in order
