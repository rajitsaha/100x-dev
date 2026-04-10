# /db — Cloud SQL Database Access

Temporarily expose Cloud SQL to a public IP, run database operations, then restore private-only access.

## Works for any project using GCP Cloud SQL.

---

## Step 0 — Detect project config

Read the project's `CLAUDE.md` to find:
- **Instance name** — the Cloud SQL instance (e.g. `reinvestiq-postgres`, `bong-ops-postgres`)
- **GCP project ID** — the GCP project (e.g. `reinvestiq`, `bong-realty-command-center`)
- **DB name** — the database name
- **DB user** — the application DB user
- **Secret name** — the Secret Manager secret holding the DB password

If the project has a project-level `/db` override with these hardcoded, use those values. Otherwise read from `CLAUDE.md`.

Set shell variables:
```bash
INSTANCE=<detected-instance>
GCP_PROJECT=<detected-project>
DB_NAME=<detected-db-name>
DB_USER=<detected-db-user>
SECRET_NAME=<detected-secret-name>
```

---

## Step 1 — Enable public IP + authorize your current IP

```bash
MY_IP=$(curl -s https://api.ipify.org)
echo "Your IP: $MY_IP"

gcloud sql instances patch "$INSTANCE" \
  --project="$GCP_PROJECT" \
  --assign-ip \
  --authorized-networks="$MY_IP/32" \
  --quiet
```

---

## Step 2 — Wait for patch and capture public IP

```bash
echo "Waiting for Cloud SQL public IP..."
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
```

---

## Step 3 — Fetch password and run queries

**CRITICAL**: Always pass the password as an env variable — never interpolate it into the script string. Special characters (`!`, `"`, `$`, `\`) in the password will corrupt the value if interpolated.

```bash
DB_PASS=$(gcloud secrets versions access latest --secret="$SECRET_NAME" --project="$GCP_PROJECT")

PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT" && \
PUBLIC_IP="$PUBLIC_IP" DB_PASS="$DB_PASS" DB_USER="$DB_USER" DB_NAME="$DB_NAME" node -e "
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
    const r = await client.query(\`<SQL_HERE>\`);
    console.table(r.rows);
  } finally {
    client.release();
    await pool.end();
  }
})().catch(e => { console.error('ERROR:', e.message); process.exit(1); });
"
```

---

## Step 4 — ALWAYS revert to private-only (run even if queries fail)

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

---

## Usage variants

### `/db` — default audit query
Replace `<SQL_HERE>` with the project's standard audit query (subscriptions, users, etc.).

### `/db <custom SQL>` — arbitrary query
Replace `<SQL_HERE>` with the SQL from `$ARGUMENTS`.

### `/db migrate` — run pending migration scripts
```bash
# Replace with project's migration pattern (Alembic, raw SQL scripts, etc.)
```

---

## Safety rules
- **ALWAYS run Step 4** (revert) even if Step 3 fails
- **Never interpolate `$DB_PASS`** into the node/python script string — always pass as env var
- Never commit the public IP or credentials to git
- Authorized network is scoped to your single IP (`/32`), never `0.0.0.0/0`

$ARGUMENTS
