# db-engine: oracle

Receives pre-resolved variables from the /db router:
- $ORA_HOST — hostname
- $ORA_PORT — port (default 1521)
- $ORA_SERVICE — Oracle service name or SID
- $ORA_USER — username
- $ORA_PASS — resolved password
- $SQL — query to execute

---

## Step 1 — Validate prerequisites

```bash
if python3 -c "import cx_Oracle" 2>/dev/null; then
  echo "Using cx_Oracle ✓"
  USE_CX=true
elif command -v sqlplus >/dev/null 2>&1; then
  echo "Using sqlplus ✓"
  USE_CX=false
else
  echo "ERROR: Neither cx_Oracle nor sqlplus found."
  echo "  Install cx_Oracle: pip install cx_Oracle"
  echo "  Requires Oracle Instant Client: https://oracle.github.io/odpi/doc/installation.html"
  exit 1
fi
```

## Step 2 — Execute query via cx_Oracle

```bash
if [ "$USE_CX" = "true" ]; then
  ORA_HOST="$ORA_HOST" ORA_PORT="${ORA_PORT:-1521}" ORA_SERVICE="$ORA_SERVICE" \
  ORA_USER="$ORA_USER" ORA_PASS="$ORA_PASS" SQL="$SQL" \
  python3 << 'PYEOF'
import os, cx_Oracle

try:
    from tabulate import tabulate
    use_tabulate = True
except ImportError:
    use_tabulate = False

dsn = cx_Oracle.makedsn(
    os.environ['ORA_HOST'],
    int(os.environ.get('ORA_PORT', 1521)),
    service_name=os.environ['ORA_SERVICE'],
)
conn = cx_Oracle.connect(
    user=os.environ['ORA_USER'],
    password=os.environ['ORA_PASS'],
    dsn=dsn,
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
fi
```

## Step 3 — Execute query via sqlplus

```bash
if [ "$USE_CX" = "false" ]; then
  ORA_PASS="$ORA_PASS" sqlplus -S \
    "${ORA_USER}/${ORA_PASS}@${ORA_HOST}:${ORA_PORT:-1521}/${ORA_SERVICE}" \
    <<< "$SQL"
fi
```

## Safety rules
- cx_Oracle requires Oracle Instant Client libraries on the system
- Never log $ORA_PASS
- Always add FETCH FIRST N ROWS ONLY or ROWNUM limit to SELECT queries
- tabulate is optional — falls back to tab-separated output
