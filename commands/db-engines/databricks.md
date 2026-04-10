# db-engine: databricks

Receives pre-resolved variables from the /db router:
- $DBX_HOST — workspace host (e.g. adb-1234567890.1.azuredatabricks.net)
- $DBX_HTTP_PATH — SQL warehouse HTTP path (e.g. /sql/1.0/warehouses/abc123)
- $DBX_TOKEN — personal access token or OAuth token
- $DBX_CATALOG — Unity Catalog catalog name (default: hive_metastore)
- $DBX_SCHEMA — schema/database name
- $SQL — query to execute

---

## Step 1 — Validate prerequisites

```bash
python3 -c "import databricks.sql" 2>/dev/null \
  || { echo "ERROR: databricks-sql-connector not found. Install: pip install databricks-sql-connector"; exit 1; }
echo "databricks-sql-connector found ✓"
```

## Step 2 — Resolve token (if not pre-resolved by router)

```bash
if [ -z "$DBX_TOKEN" ]; then
  if [ -f "$HOME/.databrickscfg" ]; then
    DBX_TOKEN=$(grep -A5 '\[DEFAULT\]' "$HOME/.databrickscfg" | grep '^token' | cut -d'=' -f2 | tr -d ' ')
    echo "Using token from ~/.databrickscfg ✓"
  elif [ -n "$DATABRICKS_TOKEN" ]; then
    DBX_TOKEN="$DATABRICKS_TOKEN"
    echo "Using DATABRICKS_TOKEN env var ✓"
  else
    echo "ERROR: No Databricks token found. Set DATABRICKS_TOKEN or configure ~/.databrickscfg"
    exit 1
  fi
fi
```

## Step 3 — Execute query

```bash
DBX_HOST="$DBX_HOST" DBX_HTTP_PATH="$DBX_HTTP_PATH" DBX_TOKEN="$DBX_TOKEN" \
DBX_CATALOG="${DBX_CATALOG:-hive_metastore}" DBX_SCHEMA="${DBX_SCHEMA:-default}" SQL="$SQL" \
python3 << 'PYEOF'
import os
from databricks import sql

try:
    from tabulate import tabulate
    use_tabulate = True
except ImportError:
    use_tabulate = False

with sql.connect(
    server_hostname=os.environ['DBX_HOST'],
    http_path=os.environ['DBX_HTTP_PATH'],
    access_token=os.environ['DBX_TOKEN'],
    catalog=os.environ.get('DBX_CATALOG', 'hive_metastore'),
    schema=os.environ.get('DBX_SCHEMA', 'default'),
) as conn:
    with conn.cursor() as cur:
        cur.execute(os.environ['SQL'])
        rows = cur.fetchall()
        headers = [desc[0] for desc in cur.description]
        if use_tabulate:
            print(tabulate(rows, headers=headers, tablefmt='psql'))
        else:
            print('\t'.join(headers))
            for row in rows:
                print('\t'.join(str(v) for v in row))
PYEOF
```

## Safety rules
- Never log $DBX_TOKEN
- Use SQL warehouse HTTP path (not cluster), more cost-efficient
- Prefer Unity Catalog paths (catalog.schema.table) over legacy hive_metastore
- tabulate is optional — falls back to tab-separated output if not installed
