# db-engine: snowflake

Receives pre-resolved variables from the /db router:
- $SF_ACCOUNT — Snowflake account identifier (e.g. xy12345.us-east-1)
- $SF_WAREHOUSE — compute warehouse name
- $SF_DATABASE — database name
- $SF_SCHEMA — schema (default PUBLIC)
- $SF_ROLE — role to use
- $SF_USER — username
- $SF_TOKEN — resolved token/password (empty for SSO)
- $SF_AUTH — "sso" | "password"
- $SQL — query to execute

---

## Step 1 — Validate prerequisites

```bash
if command -v snowsql >/dev/null 2>&1; then
  echo "Using snowsql ✓"
  USE_SNOWSQL=true
elif python3 -c "import snowflake.connector" 2>/dev/null; then
  echo "Using Python snowflake-connector ✓"
  USE_SNOWSQL=false
else
  echo "ERROR: Neither snowsql nor snowflake-connector-python found."
  echo "  Install snowsql: https://docs.snowflake.com/en/user-guide/snowsql-install-config"
  echo "  Or: pip install snowflake-connector-python"
  exit 1
fi
```

## Step 2 — Execute query via snowsql

```bash
if [ "$USE_SNOWSQL" = "true" ]; then
  if [ "$SF_AUTH" = "sso" ]; then
    snowsql -a "$SF_ACCOUNT" -u "$SF_USER" --authenticator externalbrowser \
      -w "$SF_WAREHOUSE" -d "$SF_DATABASE" --schemaname "${SF_SCHEMA:-PUBLIC}" \
      -r "$SF_ROLE" -q "$SQL"
  else
    SNOWSQL_PWD="$SF_TOKEN" snowsql -a "$SF_ACCOUNT" -u "$SF_USER" \
      -w "$SF_WAREHOUSE" -d "$SF_DATABASE" --schemaname "${SF_SCHEMA:-PUBLIC}" \
      -r "$SF_ROLE" -q "$SQL"
  fi
fi
```

## Step 3 — Execute query via Python connector

```bash
if [ "$USE_SNOWSQL" = "false" ]; then
  SF_ACCOUNT="$SF_ACCOUNT" SF_USER="$SF_USER" SF_TOKEN="$SF_TOKEN" \
  SF_WAREHOUSE="$SF_WAREHOUSE" SF_DATABASE="$SF_DATABASE" \
  SF_SCHEMA="${SF_SCHEMA:-PUBLIC}" SF_ROLE="$SF_ROLE" \
  SF_AUTH="$SF_AUTH" SQL="$SQL" \
  python3 << 'PYEOF'
import os, snowflake.connector

try:
    from tabulate import tabulate
    use_tabulate = True
except ImportError:
    use_tabulate = False

auth = os.environ['SF_AUTH']
conn_params = {
    'account':   os.environ['SF_ACCOUNT'],
    'user':      os.environ['SF_USER'],
    'warehouse': os.environ['SF_WAREHOUSE'],
    'database':  os.environ['SF_DATABASE'],
    'schema':    os.environ['SF_SCHEMA'],
    'role':      os.environ['SF_ROLE'],
}
if auth == 'sso':
    conn_params['authenticator'] = 'externalbrowser'
else:
    conn_params['password'] = os.environ['SF_TOKEN']

conn = snowflake.connector.connect(**conn_params)
cur = conn.cursor()
cur.execute(os.environ['SQL'])
rows = cur.fetchall()
headers = [desc[0] for desc in cur.description]
if use_tabulate:
    print(tabulate(rows, headers=headers, tablefmt='psql'))
else:
    print('\t'.join(headers))
    for row in rows:
        print('\t'.join(str(v) for v in row))
cur.close()
conn.close()
PYEOF
fi
```

## Safety rules
- For SSO auth: a browser window will open — this is expected behaviour
- Never log $SF_TOKEN
- Role determines data access — use least-privilege role for queries
- tabulate is optional — falls back to tab-separated output if not installed
