# /cloud-security — Cloud Security & Data Privacy Scan

Rigorous security and data privacy scan for cloud deployments. Covers GCP infrastructure hardening, data privacy (PII/GDPR/CCPA), API security, container security, and compliance.

## Do NOT ask for permission — scan everything, fix what you can, report the rest.

---

## Step 0 — Detect cloud config

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"

# Detect GCP projects used by this codebase
GCP_PROJECTS=$(grep -rh "project.*=\|gcloud.*--project\|GCP_PROJECT\|GOOGLE_CLOUD_PROJECT" \
  CLAUDE.md .env.example terraform/ 2>/dev/null \
  | grep -oE '[a-z][a-z0-9-]{4,28}' | sort -u | grep -v "^--" || true)

# Detect if Dockerfile present
HAS_DOCKER=$(ls Dockerfile docker-compose.yml deploy/docker-compose.yml 2>/dev/null | head -1 || echo "")

# Detect Terraform
HAS_TERRAFORM=$(ls terraform/*.tf infra/*.tf 2>/dev/null | head -1 || echo "")
```

Also read the project's `CLAUDE.md` to identify all GCP projects. Scan ALL of them.

---

## Section 1 — GCP IAM & Access Control

For each GCP project detected:

```bash
for PROJECT in $GCP_PROJECTS; do
  echo "=== IAM: $PROJECT ==="

  # 1a. Check for overprivileged IAM bindings
  gcloud projects get-iam-policy "$PROJECT" --format=json 2>/dev/null \
    | python3 -c "
import sys, json
policy = json.load(sys.stdin)
dangerous = ['roles/editor', 'roles/owner', 'roles/iam.securityAdmin', 'roles/storage.admin']
for binding in policy.get('bindings', []):
    if binding['role'] in dangerous:
        for member in binding['members']:
            if 'serviceAccount' in member or 'allUsers' in member:
                print(f'[HIGH] Overprivileged: {binding[\"role\"]} → {member}')
"

  # 1b. User-managed service account keys (should use Workload Identity instead)
  gcloud iam service-accounts list --project="$PROJECT" --format="value(email)" 2>/dev/null \
  | while read SA; do
    KEYS=$(gcloud iam service-accounts keys list --iam-account="$SA" \
      --filter="keyType=USER_MANAGED" --format="value(KEY_ID)" 2>/dev/null | wc -l)
    if [ "$KEYS" -gt 0 ]; then
      echo "[HIGH] $SA has $KEYS user-managed key(s) — use Workload Identity Federation instead"
    fi
  done

  # 1c. allUsers / allAuthenticatedUsers in project IAM
  gcloud projects get-iam-policy "$PROJECT" --format=json 2>/dev/null \
    | grep -E "allUsers|allAuthenticatedUsers" \
    && echo "[CRITICAL] Project IAM has public (allUsers) binding" || true
done
```

**Findings required to pass:**
- No `roles/editor` or `roles/owner` assigned to service accounts
- No user-managed SA keys (prefer Workload Identity)
- No `allUsers` bindings in project IAM

---

## Section 2 — GCP Network & Firewall

```bash
for PROJECT in $GCP_PROJECTS; do
  echo "=== Network: $PROJECT ==="

  # 2a. Firewall rules open to 0.0.0.0/0 on sensitive ports
  gcloud compute firewall-rules list --project="$PROJECT" --format=json 2>/dev/null \
    | python3 -c "
import sys, json
rules = json.load(sys.stdin)
sensitive_ports = {'22', '3389', '5432', '6379', '3306', '27017', '6443'}
for rule in rules:
    sources = rule.get('sourceRanges', [])
    if '0.0.0.0/0' in sources or '::/0' in sources:
        for allowed in rule.get('allowed', []):
            ports = allowed.get('ports', [])
            for port in ports:
                if str(port) in sensitive_ports:
                    print(f'[CRITICAL] Firewall {rule[\"name\"]}: port {port} open to 0.0.0.0/0')
"

  # 2b. Cloud SQL — public IP and SSL
  gcloud sql instances list --project="$PROJECT" --format=json 2>/dev/null \
    | python3 -c "
import sys, json
instances = json.load(sys.stdin)
for inst in instances:
    name = inst['name']
    settings = inst.get('settings', {})
    ip_config = settings.get('ipConfiguration', {})

    # Public IP check
    if ip_config.get('ipv4Enabled', False):
        auth_nets = ip_config.get('authorizedNetworks', [])
        for net in auth_nets:
            if net.get('value') in ('0.0.0.0/0', '::/0'):
                print(f'[CRITICAL] Cloud SQL {name}: public IP open to 0.0.0.0/0')
            else:
                print(f'[MEDIUM] Cloud SQL {name}: public IP enabled (authorized: {net.get(\"value\")})')

    # SSL check
    if not ip_config.get('requireSsl', False) and not ip_config.get('sslMode', '') == 'ENCRYPTED_ONLY':
        print(f'[HIGH] Cloud SQL {name}: SSL not required for connections')
    else:
        print(f'[PASS] Cloud SQL {name}: SSL enforced')

    # Backup check
    backup = settings.get('backupConfiguration', {})
    if not backup.get('enabled', False):
        print(f'[HIGH] Cloud SQL {name}: automated backups disabled')
"
done
```

---

## Section 3 — GCP Data Storage (GCS Buckets)

```bash
for PROJECT in $GCP_PROJECTS; do
  echo "=== Storage: $PROJECT ==="

  gcloud storage buckets list --project="$PROJECT" --format="value(name)" 2>/dev/null \
  | while read BUCKET; do
    # Public access check
    IAM=$(gcloud storage buckets get-iam-policy "gs://$BUCKET" --format=json 2>/dev/null || echo "{}")
    if echo "$IAM" | grep -qE "allUsers|allAuthenticatedUsers"; then
      echo "[CRITICAL] Bucket gs://$BUCKET is publicly accessible"
    fi

    # Uniform bucket-level access (prevents per-object ACLs)
    UNIFORM=$(gcloud storage buckets describe "gs://$BUCKET" \
      --format="value(iamConfiguration.uniformBucketLevelAccess.enabled)" 2>/dev/null || echo "False")
    if [ "$UNIFORM" != "True" ]; then
      echo "[MEDIUM] Bucket gs://$BUCKET: uniform bucket-level access not enabled (per-object ACLs allowed)"
    fi

    # Versioning (for critical data buckets)
    VERSIONING=$(gcloud storage buckets describe "gs://$BUCKET" \
      --format="value(versioning.enabled)" 2>/dev/null || echo "False")
    if [ "$VERSIONING" != "True" ]; then
      echo "[LOW] Bucket gs://$BUCKET: versioning not enabled"
    fi
  done
done
```

---

## Section 4 — GCP Cloud Run Security

```bash
for PROJECT in $GCP_PROJECTS; do
  echo "=== Cloud Run: $PROJECT ==="

  gcloud run services list --project="$PROJECT" --format=json \
    --region=us-central1 2>/dev/null \
    | python3 -c "
import sys, json
services = json.load(sys.stdin)
for svc in services:
    name = svc['metadata']['name']
    annotations = svc['metadata'].get('annotations', {})

    # Check for secrets in env vars
    containers = svc.get('spec', {}).get('template', {}).get('spec', {}).get('containers', [])
    for container in containers:
        for env in container.get('env', []):
            val = env.get('value', '')
            # Flag values that look like actual secrets (not references)
            if len(val) > 20 and not val.startswith('$(') and 'secretKeyRef' not in str(env):
                print(f'[HIGH] Cloud Run {name}: env var \"{env[\"name\"]}\" may contain hardcoded secret')
" 2>/dev/null || true

  # Check each service IAM — allUsers means public internet access
  gcloud run services list --project="$PROJECT" --region=us-central1 \
    --format="value(SERVICE)" 2>/dev/null \
  | while read SVC; do
    IAM=$(gcloud run services get-iam-policy "$SVC" \
      --project="$PROJECT" --region=us-central1 --format=json 2>/dev/null || echo "{}")
    if echo "$IAM" | grep -q "allUsers"; then
      echo "[INFO] Cloud Run $SVC: public (allUsers) — verify app-level auth is enforced"
    fi
  done
done
```

---

## Section 5 — GCP Audit Logging

```bash
for PROJECT in $GCP_PROJECTS; do
  echo "=== Audit Logging: $PROJECT ==="

  # Check data access audit logs are enabled for key services
  gcloud projects get-iam-policy "$PROJECT" --format=json 2>/dev/null \
    | python3 -c "
import sys, json
policy = json.load(sys.stdin)
audit_configs = policy.get('auditConfigs', [])
services_with_data_access = set()
for config in audit_configs:
    for log_config in config.get('auditLogConfigs', []):
        if log_config.get('logType') == 'DATA_READ' or log_config.get('logType') == 'DATA_WRITE':
            services_with_data_access.add(config.get('service', ''))

critical_services = ['cloudsql.googleapis.com', 'storage.googleapis.com', 'secretmanager.googleapis.com']
for svc in critical_services:
    if svc not in services_with_data_access:
        print(f'[MEDIUM] Audit logging (DATA_READ/DATA_WRITE) not enabled for {svc}')
    else:
        print(f'[PASS] Audit logging enabled for {svc}')
"
done
```

---

## Section 6 — Secret Manager Hygiene

```bash
for PROJECT in $GCP_PROJECTS; do
  echo "=== Secrets: $PROJECT ==="

  # List all secrets and check for ones without recent rotation
  gcloud secrets list --project="$PROJECT" --format=json 2>/dev/null \
    | python3 -c "
import sys, json
from datetime import datetime, timezone
secrets = json.load(sys.stdin)
now = datetime.now(timezone.utc)
for secret in secrets:
    name = secret['name'].split('/')[-1]
    create_time = secret.get('createTime', '')
    # Flag secrets older than 1 year without rotation config
    labels = secret.get('labels', {})
    rotation = secret.get('rotation', {})
    if not rotation:
        print(f'[LOW] Secret {name}: no rotation policy configured')
"
done
```

---

## Section 7 — Container Security (if Dockerfile present)

```bash
if [ -n "$HAS_DOCKER" ]; then
  echo "=== Container Security ==="

  # 7a. Running as root
  if grep -rq "^USER root\|^RUN.*adduser\|USER 0" Dockerfile 2>/dev/null; then
    echo "[HIGH] Dockerfile: container runs as root — add non-root USER"
  elif ! grep -q "^USER" Dockerfile 2>/dev/null; then
    echo "[HIGH] Dockerfile: no USER directive — defaults to root"
  else
    echo "[PASS] Dockerfile: non-root user configured"
  fi

  # 7b. Secrets in Dockerfile (ARG/ENV with values)
  if grep -E "^(ARG|ENV)\s+\w+(KEY|SECRET|PASSWORD|TOKEN|PASS)=\S+" Dockerfile 2>/dev/null; then
    echo "[CRITICAL] Dockerfile: hardcoded secret in ARG/ENV"
  else
    echo "[PASS] Dockerfile: no hardcoded secrets"
  fi

  # 7c. Pinned base image (no :latest)
  BASE=$(grep "^FROM" Dockerfile 2>/dev/null | head -1)
  if echo "$BASE" | grep -q ":latest\b"; then
    echo "[MEDIUM] Dockerfile: base image uses :latest tag — pin to a specific digest or version"
  else
    echo "[PASS] Dockerfile: base image pinned: $BASE"
  fi

  # 7d. COPY --chown instead of RUN chown (performance + security)
  if grep -q "^RUN chown" Dockerfile 2>/dev/null; then
    echo "[LOW] Dockerfile: use COPY --chown instead of RUN chown"
  fi
fi
```

---

## Section 8 — Data Privacy: PII in Source Code

Scan for PII patterns that should never appear in source code or logs.

```bash
echo "=== PII in Source Code ==="

# Email addresses hardcoded (not in tests or examples)
PII_EMAIL=$(grep -rn '[a-zA-Z0-9._%+-]\+@[a-zA-Z0-9.-]\+\.[a-zA-Z]\{2,\}' \
  --include="*.ts" --include="*.tsx" --include="*.py" --include="*.js" \
  --exclude-dir=node_modules --exclude-dir=venv --exclude-dir=dist \
  . 2>/dev/null \
  | grep -v "example\.com\|test\|mock\|placeholder\|your-email\|\.spec\.\|\.test\." \
  | grep -v "noreply@\|support@\|hello@\|admin@" \
  | head -10 || true)
if [ -n "$PII_EMAIL_PROD" ]; then
  echo "[HIGH] Real email addresses found in source (not test/example)"
  echo "$PII_EMAIL" | head -5
fi

# SSN patterns
SSN=$(grep -rn '[0-9]\{3\}-[0-9]\{2\}-[0-9]\{4\}' \
  --include="*.ts" --include="*.tsx" --include="*.py" \
  --exclude-dir=node_modules --exclude-dir=venv \
  . 2>/dev/null | head -5 || true)
[ -n "$SSN" ] && echo "[CRITICAL] SSN pattern found in source: $SSN"

# Credit card patterns
CC=$(grep -rn '[0-9]\{4\}[- ][0-9]\{4\}[- ][0-9]\{4\}[- ][0-9]\{4\}' \
  --include="*.ts" --include="*.tsx" --include="*.py" \
  --exclude-dir=node_modules --exclude-dir=venv \
  . 2>/dev/null | head -5 || true)
[ -n "$CC" ] && echo "[CRITICAL] Credit card pattern found in source: $CC"

# PII leaking into logs
echo ""
echo "=== PII in Log Statements ==="
LOG_PII=$(grep -rn "console\.log\|logger\.\(info\|debug\|warn\|error\)" \
  --include="*.ts" --include="*.tsx" --include="*.py" \
  --exclude-dir=node_modules --exclude-dir=venv --exclude="*.test.*" --exclude="*.spec.*" \
  . 2>/dev/null \
  | grep -iE "email|password|ssn|credit.card|phone|dob|date.of.birth|social.security" \
  | head -10 || true)
if [ -n "$LOG_PII" ]; then
  echo "[HIGH] PII field names in log statements (may leak PII to logs):"
  echo "$LOG_PII" | head -5
else
  echo "[PASS] No PII field names detected in log statements"
fi

# Error responses leaking PII
echo ""
echo "=== PII in API Error Responses ==="
ERR_PII=$(grep -rn "res\.json\|res\.send\|return.*error" \
  --include="*.ts" \
  --exclude-dir=node_modules --exclude="*.test.*" \
  . 2>/dev/null \
  | grep -iE "email|password|user\..*\b" \
  | grep -v "error\.message\s*=\|//\|generic" \
  | head -10 || true)
if [ -n "$ERR_PII" ]; then
  echo "[MEDIUM] Possible PII in API error responses — verify these are generic:"
  echo "$ERR_PII" | head -5
fi
```

---

## Section 9 — Data Privacy Compliance Checklist

Review these manually and confirm status. Report any gaps.

```
GDPR / CCPA Compliance Checklist
─────────────────────────────────────────────────────────
□ Privacy Policy     — exists and is linked in the app
□ Data Inventory     — all user PII fields documented
□ Consent            — explicit consent collected before processing personal data
□ Right to Delete    — user data deletion endpoint/flow exists
□ Right to Export    — user data export capability exists
□ Data Retention     — retention periods defined and enforced
□ Third-party DPAs   — Data Processing Agreements in place with Stripe, Resend, Firebase, etc.
□ Breach Response    — incident response plan documented (SECURITY.md or equivalent)
□ Data Minimization  — collecting only what's needed (no unnecessary PII)
□ Encryption at Rest — PII fields encrypted in DB (or DB encryption enabled)
□ Encryption Transit — TLS enforced on all endpoints (HTTPS only)
□ Audit Trail        — user data access/modification logged
─────────────────────────────────────────────────────────
```

Check code evidence for each:
- Delete endpoint: `grep -rn "DELETE.*user\|deleteUser\|deactivate" api/ src/ 2>/dev/null | head -5`
- Export endpoint: `grep -rn "export.*user\|userExport\|data.*export" api/ src/ 2>/dev/null | head -5`
- Retention policy: `grep -rn "retention\|expires\|cleanup\|purge" api/ 2>/dev/null | head -5`

---

## Section 10 — API Security Hygiene

```bash
echo "=== API Security ==="

# Security headers (helmet or equivalent)
HELMET=$(grep -rn "helmet\|Content-Security-Policy\|X-Frame-Options\|Strict-Transport" \
  --include="*.ts" --include="*.py" --exclude-dir=node_modules . 2>/dev/null | head -3 || true)
[ -z "$HELMET" ] && echo "[HIGH] No security headers middleware (helmet/CSP) found" \
  || echo "[PASS] Security headers configured"

# Rate limiting
RATELIMIT=$(grep -rn "rateLimit\|rate.limit\|RateLimiter\|throttle" \
  --include="*.ts" --include="*.py" --exclude-dir=node_modules . 2>/dev/null | head -3 || true)
[ -z "$RATELIMIT" ] && echo "[MEDIUM] No rate limiting found on API" \
  || echo "[PASS] Rate limiting configured"

# CORS — wildcard check
CORS_WILD=$(grep -rn "origin.*['\"]\\*['\"]" \
  --include="*.ts" --include="*.py" --exclude-dir=node_modules . 2>/dev/null | head -3 || true)
[ -n "$CORS_WILD" ] && echo "[HIGH] CORS wildcard (*) origin found: $CORS_WILD" \
  || echo "[PASS] CORS does not use wildcard"

# SQL injection — string interpolation in queries
SQL_INJECT=$(grep -rn "query.*\`.*\${" \
  --include="*.ts" --include="*.py" --exclude-dir=node_modules --exclude="*.test.*" \
  . 2>/dev/null | grep -v '\$\${' | head -5 || true)
[ -n "$SQL_INJECT" ] && echo "[CRITICAL] SQL injection risk — string interpolation in queries:" \
  && echo "$SQL_INJECT" | head -3 \
  || echo "[PASS] No SQL injection patterns detected"

# eval() usage
EVAL=$(grep -rn "eval(" --include="*.ts" --include="*.tsx" --include="*.js" \
  --exclude-dir=node_modules --exclude="*.test.*" . 2>/dev/null | head -3 || true)
[ -n "$EVAL" ] && echo "[HIGH] eval() usage found: $EVAL" \
  || echo "[PASS] No eval() usage"
```

---

## Section 11 — Terraform / IaC Security (if present)

```bash
if [ -n "$HAS_TERRAFORM" ]; then
  echo "=== Terraform Security ==="

  # Overly broad IAM roles
  grep -rn "roles/editor\|roles/owner\|storage\.admin\|secretmanager\.admin" \
    terraform/ infra/ 2>/dev/null \
    | grep -v "^#" | grep -v "\.terraform" \
    && echo "[HIGH] Overly broad IAM role in Terraform" || echo "[PASS] No overly broad IAM roles"

  # Default/placeholder passwords
  grep -rn "CHANGE_ME\|password.*default\|default.*password" \
    terraform/ infra/ 2>/dev/null \
    | grep -v "^#" \
    && echo "[CRITICAL] Default/placeholder password in Terraform" || true

  # Public resources
  grep -rn "0\.0\.0\.0/0\|all_traffic\|allUsers" \
    terraform/ infra/ 2>/dev/null \
    | grep -v "^#" | grep -v "egress" \
    && echo "[HIGH] Possible public resource access in Terraform (review above)" || true
fi
```

---

## Final report

```
╔══════════════════════════════════════════════════════════════╗
║              CLOUD SECURITY & PRIVACY SCAN RESULTS           ║
╠══════════════════════════════════════════════════════════════╣
║ S1  IAM & Access:        ✅ PASS | ❌ N findings             ║
║ S2  Network/Firewall:    ✅ PASS | ❌ N findings             ║
║ S3  Storage (GCS):       ✅ PASS | ❌ N findings             ║
║ S4  Cloud Run:           ✅ PASS | ❌ N findings             ║
║ S5  Audit Logging:       ✅ PASS | ❌ N findings             ║
║ S6  Secret Manager:      ✅ PASS | ❌ N findings             ║
║ S7  Container Security:  ✅ PASS | ❌ N findings | skipped   ║
║ S8  PII in Source:       ✅ PASS | ❌ N findings             ║
║ S9  Privacy Compliance:  ✅ PASS | ⚠️ N gaps                 ║
║ S10 API Security:        ✅ PASS | ❌ N findings             ║
║ S11 Terraform:           ✅ PASS | ❌ N findings | skipped   ║
╠══════════════════════════════════════════════════════════════╣
║ CRITICAL: N  HIGH: N  MEDIUM: N  LOW: N                      ║
║ Gate 5: ✅ PASSED | ❌ BLOCKED (critical/high found)          ║
╚══════════════════════════════════════════════════════════════╝
```

**Gate 5 blocks on:** any CRITICAL or HIGH finding across all sections.
**Gate 5 passes on:** zero critical + zero high (MEDIUM and LOW are reported but non-blocking).

$ARGUMENTS
