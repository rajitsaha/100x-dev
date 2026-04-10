# db-engine: presto

Supports Presto and Trino (protocol-compatible).

Receives pre-resolved variables from the /db router:
- $PRESTO_HOST — coordinator hostname
- $PRESTO_PORT — port (default 8080 for Presto, 8443 for Trino HTTPS)
- $PRESTO_USER — username
- $PRESTO_CATALOG — catalog name (e.g. hive, iceberg)
- $PRESTO_SCHEMA — schema name
- $PRESTO_TOKEN — auth token (empty if no auth)
- $PRESTO_ENGINE — "presto" | "trino" (default: presto)
- $SSL — "true" | "false" (default: false)
- $SQL — query to execute

---

## Step 1 — Validate prerequisites

```bash
ENGINE="${PRESTO_ENGINE:-presto}"
if [ "$ENGINE" = "trino" ]; then
  python3 -c "import trino" 2>/dev/null \
    || { echo "ERROR: trino client not found. Install: pip install trino"; exit 1; }
  echo "Using trino client ✓"
else
  python3 -c "import prestodb" 2>/dev/null \
    || { echo "ERROR: prestodb not found. Install: pip install presto-python-client"; exit 1; }
  echo "Using prestodb client ✓"
fi
```

## Step 2 — Execute query

```bash
PRESTO_HOST="$PRESTO_HOST" PRESTO_PORT="${PRESTO_PORT:-8080}" \
PRESTO_USER="$PRESTO_USER" PRESTO_CATALOG="$PRESTO_CATALOG" \
PRESTO_SCHEMA="$PRESTO_SCHEMA" PRESTO_TOKEN="${PRESTO_TOKEN:-}" \
PRESTO_ENGINE="${PRESTO_ENGINE:-presto}" SSL="${SSL:-false}" SQL="$SQL" \
python3 << 'PYEOF'
import os

try:
    from tabulate import tabulate
    use_tabulate = True
except ImportError:
    use_tabulate = False

engine = os.environ.get('PRESTO_ENGINE', 'presto')
host   = os.environ['PRESTO_HOST']
port   = int(os.environ.get('PRESTO_PORT', 8080))
user   = os.environ['PRESTO_USER']
catalog = os.environ['PRESTO_CATALOG']
schema  = os.environ['PRESTO_SCHEMA']
token   = os.environ.get('PRESTO_TOKEN', '')
ssl     = os.environ.get('SSL', 'false').lower() == 'true'

if engine == 'trino':
    import trino
    auth = trino.auth.BasicAuthentication(user, token) if token else None
    conn = trino.dbapi.connect(
        host=host, port=port, user=user,
        catalog=catalog, schema=schema,
        auth=auth,
        http_scheme='https' if ssl else 'http',
    )
else:
    import prestodb
    conn = prestodb.dbapi.connect(
        host=host, port=port, user=user,
        catalog=catalog, schema=schema,
        http_scheme='https' if ssl else 'http',
    )

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
```

## Safety rules
- Presto/Trino can scan huge datasets — always use LIMIT for exploratory queries
- For Trino with token auth: token is passed via BasicAuthentication (handled by client)
- tabulate is optional — falls back to tab-separated output
