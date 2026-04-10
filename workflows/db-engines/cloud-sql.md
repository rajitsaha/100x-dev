# db-engine: cloud-sql

Receives pre-resolved variables from the /db router:
- $INSTANCE — Cloud SQL instance name
- $GCP_PROJECT — GCP project ID
- $DB_NAME — database name
- $DB_USER — database user
- $DB_PASS — resolved password (from Secret Manager)
- $SQL — query to execute (or "migrate")

---

## Step 1 — Validate prerequisites

```bash
command -v gcloud >/dev/null 2>&1 || { echo "ERROR: gcloud CLI not installed. Install from https://cloud.google.com/sdk/docs/install"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "ERROR: node not installed. Install from https://nodejs.org"; exit 1; }
node -e "require('pg')" 2>/dev/null || { echo "ERROR: pg package not found. Run: npm install pg"; exit 1; }
echo "Prerequisites OK ✓"
```

## Step 2 — Enable public IP and authorize your current IP

```bash
MY_IP=$(curl -s https://api.ipify.org)
echo "Your IP: $MY_IP"

gcloud sql instances patch "$INSTANCE" \
  --project="$GCP_PROJECT" \
  --assign-ip \
  --authorized-networks="$MY_IP/32" \
  --quiet
```

## Step 3 — Wait for public IP

```bash
echo "Waiting for Cloud SQL public IP..."
PUBLIC_IP=""
for i in $(seq 1 20); do
  PUBLIC_IP=$(gcloud sql instances describe "$INSTANCE" \
    --project="$GCP_PROJECT" \
    --format="json" 2>/dev/null \
    | node -e "const d=JSON.parse(require('fs').readFileSync('/dev/stdin','utf8')); \
               const pub=d.ipAddresses?.find(a=>a.type==='PRIMARY'); \
               if(pub)process.stdout.write(pub.ipAddress);" 2>/dev/null)
  if [ -n "$PUBLIC_IP" ]; then
    echo "Public IP: $PUBLIC_IP"
    break
  fi
  echo "  attempt $i — not ready, waiting 10s..."
  sleep 10
done

if [ -z "$PUBLIC_IP" ]; then
  echo "ERROR: Timed out waiting for public IP"
  exit 1
fi
```

## Step 4 — Execute query

**CRITICAL**: Always pass DB_PASS as env variable — never interpolate. Special characters corrupt the value.

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "$HOME")
cd "$PROJECT_ROOT"

PUBLIC_IP="$PUBLIC_IP" DB_PASS="$DB_PASS" DB_USER="$DB_USER" DB_NAME="$DB_NAME" SQL="$SQL" \
node -e "
const { Pool } = require('pg');
const pool = new Pool({
  host: process.env.PUBLIC_IP,
  user: process.env.DB_USER,
  password: process.env.DB_PASS,
  database: process.env.DB_NAME,
  ssl: { rejectUnauthorized: false },
});
(async () => {
  const client = await pool.connect();
  try {
    const r = await client.query(process.env.SQL);
    console.table(r.rows);
  } finally {
    client.release();
    await pool.end();
  }
})().catch(e => { console.error('ERROR:', e.message); process.exit(1); });
"
```

## Step 5 — ALWAYS revert to private-only (run even if Step 4 fails)

```bash
gcloud sql instances patch "$INSTANCE" \
  --project="$GCP_PROJECT" \
  --no-assign-ip \
  --clear-authorized-networks \
  --quiet

echo "✔ Public IP disabled — instance is private-only again"
```

Verify:
```bash
gcloud sql instances describe "$INSTANCE" --project="$GCP_PROJECT" --format="value(ipAddresses)"
```

## Safety rules
- ALWAYS run Step 5 (revert) even if Step 4 fails — wrap in trap if calling from shell
- NEVER interpolate $DB_PASS into script strings — always pass as env var
- Never commit credentials or public IPs to git
- Authorized network is always /32 (your single IP), never 0.0.0.0/0
