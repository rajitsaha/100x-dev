---
name: cloud-security
description: Rigorous security and data privacy scan for cloud deployments. Covers GCP infrastructure hardening, data privacy (PII/GDPR/CCPA), API security, container security, and compliance.
category: quality
tier: on-demand
slash_command: /cloud-security
---

# Cloud Security — Cloud Security & Data Privacy Scan

Rigorous security and data privacy scan for cloud deployments. Covers GCP infrastructure hardening, data privacy (PII/GDPR/CCPA), API security, container security, and compliance.

## Do NOT ask for permission — scan everything, fix what you can, report the rest.

---

## Step 0 — Detect cloud config

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
INSTRUCTION_FILE=$(for f in CLAUDE.md AGENTS.md .cursorrules .windsurfrules; do [ -f "$PROJECT_ROOT/$f" ] && echo "$PROJECT_ROOT/$f" && break; done)
GCP_PROJECTS=$(grep -rh "GCP_PROJECT\|GOOGLE_CLOUD_PROJECT\|gcloud.*--project" ${INSTRUCTION_FILE:-/dev/null} .env.example terraform/ 2>/dev/null | grep -oE '[a-z][a-z0-9-]{4,28}' | sort -u | grep -v "^--" || true)
HAS_DOCKER=$(ls Dockerfile docker-compose.yml 2>/dev/null | head -1 || true)
HAS_TERRAFORM=$(ls terraform/*.tf infra/*.tf 2>/dev/null | head -1 || true)
```

---

## Section 1 — GCP IAM & Access Control

For each GCP project detected:

```bash
for PROJECT in $GCP_PROJECTS; do
  echo "=== IAM: $PROJECT ==="
  gcloud projects get-iam-policy "$PROJECT" --format=json 2>/dev/null \
    | python3 -c "
import sys,json
p=json.load(sys.stdin)
bad=['roles/editor','roles/owner','roles/iam.securityAdmin','roles/storage.admin']
[print('[HIGH]',b['role'],m) for b in p.get('bindings',[]) for m in b['members'] if b['role'] in bad and ('serviceAccount' in m or 'allUsers' in m)]"
  gcloud iam service-accounts list --project="$PROJECT" --format="value(email)" 2>/dev/null \
    | while read SA; do
        n=$(gcloud iam service-accounts keys list --iam-account="$SA" --filter="keyType=USER_MANAGED" --format="value(KEY_ID)" 2>/dev/null | wc -l)
        [ "$n" -gt 0 ] && echo "[HIGH] $SA: $n user-managed key(s) — use Workload Identity instead"
      done
  gcloud projects get-iam-policy "$PROJECT" --format=json 2>/dev/null | grep -E "allUsers|allAuthenticatedUsers" && echo "[CRITICAL] Public IAM binding found" || true
done
```

---

## Section 2 — GCP Network & Firewall

```bash
for PROJECT in $GCP_PROJECTS; do
  echo "=== Network: $PROJECT ==="
  gcloud compute firewall-rules list --project="$PROJECT" --format=json 2>/dev/null \
    | python3 -c "
import sys,json
sp={'22','3389','5432','6379','3306','27017','6443'}
[print('[CRITICAL] Firewall',r['name'],'port',p,'open to 0.0.0.0/0') for r in json.load(sys.stdin) if '0.0.0.0/0' in r.get('sourceRanges',[]) or '::/0' in r.get('sourceRanges',[]) for a in r.get('allowed',[]) for p in a.get('ports',[]) if str(p) in sp]"
  gcloud sql instances list --project="$PROJECT" --format=json 2>/dev/null \
    | python3 -c "
import sys,json
for i in json.load(sys.stdin):
  n,ip=i['name'],i.get('settings',{}).get('ipConfiguration',{})
  [print('[CRITICAL] Cloud SQL',n,'public IP open to',net['value']) if net.get('value') in ('0.0.0.0/0','::/0') else print('[MEDIUM] Cloud SQL',n,'public IP enabled') for net in ip.get('authorizedNetworks',[])] if ip.get('ipv4Enabled') else None
  print('[HIGH] Cloud SQL',n,'SSL not required') if not ip.get('requireSsl') and ip.get('sslMode','')!='ENCRYPTED_ONLY' else print('[PASS] Cloud SQL',n,'SSL enforced')
  print('[HIGH] Cloud SQL',n,'backups disabled') if not i.get('settings',{}).get('backupConfiguration',{}).get('enabled') else None"
done
```

---

## Section 3 — GCP Data Storage (GCS Buckets)

```bash
for PROJECT in $GCP_PROJECTS; do
  echo "=== Storage: $PROJECT ==="
  gcloud storage buckets list --project="$PROJECT" --format="value(name)" 2>/dev/null | while read BUCKET; do
    gcloud storage buckets get-iam-policy "gs://$BUCKET" --format=json 2>/dev/null \
      | grep -qE "allUsers|allAuthenticatedUsers" && echo "[CRITICAL] Bucket gs://$BUCKET is public" || true
    [ "$(gcloud storage buckets describe "gs://$BUCKET" --format="value(iamConfiguration.uniformBucketLevelAccess.enabled)" 2>/dev/null)" != "True" ] \
      && echo "[MEDIUM] Bucket gs://$BUCKET: uniform access not enabled" || true
    [ "$(gcloud storage buckets describe "gs://$BUCKET" --format="value(versioning.enabled)" 2>/dev/null)" != "True" ] \
      && echo "[LOW] Bucket gs://$BUCKET: versioning not enabled" || true
  done
done
```

---

## Section 4 — GCP Cloud Run Security

```bash
for PROJECT in $GCP_PROJECTS; do
  echo "=== Cloud Run: $PROJECT ==="
  gcloud run services list --project="$PROJECT" --format=json --region=us-central1 2>/dev/null \
    | python3 -c "
import sys,json
[print('[HIGH] Cloud Run',s['metadata']['name'],'env',e['name'],'may contain hardcoded secret') for s in json.load(sys.stdin) for c in s.get('spec',{}).get('template',{}).get('spec',{}).get('containers',[]) for e in c.get('env',[]) if len(e.get('value',''))>20 and not e.get('value','').startswith('\$(') and 'secretKeyRef' not in str(e)]" 2>/dev/null || true
  gcloud run services list --project="$PROJECT" --region=us-central1 --format="value(SERVICE)" 2>/dev/null \
    | while read SVC; do
        gcloud run services get-iam-policy "$SVC" --project="$PROJECT" --region=us-central1 --format=json 2>/dev/null \
          | grep -q "allUsers" && echo "[INFO] Cloud Run $SVC: public — verify app-level auth" || true
      done
done
```

---

## Section 5 — GCP Audit Logging

```bash
for PROJECT in $GCP_PROJECTS; do
  echo "=== Audit Logging: $PROJECT ==="
  gcloud projects get-iam-policy "$PROJECT" --format=json 2>/dev/null \
    | python3 -c "
import sys,json
p=json.load(sys.stdin)
svcs={c['service'] for c in p.get('auditConfigs',[]) for l in c.get('auditLogConfigs',[]) if l.get('logType') in ('DATA_READ','DATA_WRITE')}
[print('[PASS] Audit logging:',s) if s in svcs else print('[MEDIUM] Audit logging not enabled:',s) for s in ['cloudsql.googleapis.com','storage.googleapis.com','secretmanager.googleapis.com']]"
done
```

---

## Section 6 — Secret Manager Hygiene

```bash
for PROJECT in $GCP_PROJECTS; do
  echo "=== Secrets: $PROJECT ==="
  gcloud secrets list --project="$PROJECT" --format=json 2>/dev/null \
    | python3 -c "
import sys,json
[print('[LOW] Secret',s['name'].split('/')[-1],'no rotation policy') for s in json.load(sys.stdin) if not s.get('rotation')]"
done
```

---

## Section 7 — Container Security (if Dockerfile present)

```bash
if [ -n "$HAS_DOCKER" ]; then
  echo "=== Container Security ==="
  grep -rq "^USER root\|USER 0" Dockerfile 2>/dev/null && echo "[HIGH] Dockerfile: runs as root" || \
    { grep -q "^USER" Dockerfile 2>/dev/null && echo "[PASS] non-root USER set" || echo "[HIGH] Dockerfile: no USER directive (defaults to root)"; }
  grep -qE "^(ARG|ENV)\s+\w+(KEY|SECRET|PASSWORD|TOKEN|PASS)=\S+" Dockerfile 2>/dev/null \
    && echo "[CRITICAL] Dockerfile: hardcoded secret in ARG/ENV" || echo "[PASS] No hardcoded secrets"
  grep "^FROM" Dockerfile 2>/dev/null | head -1 | grep -q ":latest" \
    && echo "[MEDIUM] Dockerfile: base image uses :latest — pin version" || echo "[PASS] Base image pinned"
  grep -q "^RUN chown" Dockerfile 2>/dev/null && echo "[LOW] Dockerfile: use COPY --chown instead of RUN chown" || true
fi
```

---

## Section 8 — Data Privacy: PII in Source Code

Scan for PII patterns that should never appear in source code or logs.

```bash
echo "=== PII in Source Code ==="
EXCL="--exclude-dir=node_modules --exclude-dir=venv --exclude-dir=dist"
# Hardcoded emails (non-test/example)
grep -rn $EXCL '[a-zA-Z0-9._%+-]\+@[a-zA-Z0-9.-]\+\.[a-zA-Z]\{2,\}' --include="*.ts" --include="*.tsx" --include="*.py" --include="*.js" . 2>/dev/null \
  | grep -v "example\.com\|test\|mock\|\.spec\.\|\.test\.\|noreply@\|support@\|hello@\|admin@" | head -5 \
  | grep -q . && echo "[HIGH] Real email addresses found in source" || true
# SSN / credit card patterns
grep -rn $EXCL '[0-9]\{3\}-[0-9]\{2\}-[0-9]\{4\}' --include="*.ts" --include="*.py" . 2>/dev/null | head -5 | grep -q . && echo "[CRITICAL] SSN pattern in source" || true
grep -rn $EXCL '[0-9]\{4\}[- ][0-9]\{4\}[- ][0-9]\{4\}[- ][0-9]\{4\}' --include="*.ts" --include="*.py" . 2>/dev/null | head -5 | grep -q . && echo "[CRITICAL] Credit card pattern in source" || true
# PII in logs / error responses
grep -rn $EXCL "console\.log\|logger\." --include="*.ts" --include="*.py" --exclude="*.test.*" . 2>/dev/null \
  | grep -iE "email|password|ssn|credit.card|phone|dob|social.security" | head -5 \
  | grep -q . && echo "[HIGH] PII field names in log statements" || echo "[PASS] No PII in log statements"
grep -rn $EXCL "res\.json\|res\.send\|return.*error" --include="*.ts" --exclude="*.test.*" . 2>/dev/null \
  | grep -iE "email|password|user\." | grep -v "error\.message\|//\|generic" | head -5 \
  | grep -q . && echo "[MEDIUM] Possible PII in API error responses — verify generic" || true
```

---

## Section 9 — Data Privacy Compliance Checklist

Review manually. Report gaps.

GDPR/CCPA: □ Privacy Policy □ Data Inventory □ Consent □ Right to Delete □ Right to Export □ Data Retention □ Third-party DPAs □ Breach Response □ Data Minimization □ Encryption at Rest □ Encryption Transit □ Audit Trail

```bash
grep -rn "DELETE.*user\|deleteUser\|deactivate" api/ src/ 2>/dev/null | head -3 || echo "[GAP] No delete user endpoint found"
grep -rn "export.*user\|userExport\|data.*export" api/ src/ 2>/dev/null | head -3 || echo "[GAP] No export user endpoint found"
grep -rn "retention\|expires\|cleanup\|purge" api/ 2>/dev/null | head -3 || echo "[GAP] No retention policy found"
```

---

## Section 10 — API Security Hygiene

```bash
echo "=== API Security ==="
X="--exclude-dir=node_modules"
grep -rn $X "helmet\|Content-Security-Policy\|Strict-Transport" --include="*.ts" --include="*.py" . 2>/dev/null | grep -q . \
  && echo "[PASS] Security headers configured" || echo "[HIGH] No security headers (helmet/CSP) found"
grep -rn $X "rateLimit\|rate.limit\|RateLimiter\|throttle" --include="*.ts" --include="*.py" . 2>/dev/null | grep -q . \
  && echo "[PASS] Rate limiting configured" || echo "[MEDIUM] No rate limiting found"
grep -rn $X "origin.*['\"]\\*['\"]" --include="*.ts" --include="*.py" . 2>/dev/null | grep -q . \
  && echo "[HIGH] CORS wildcard (*) origin found" || echo "[PASS] No CORS wildcard"
grep -rn $X --exclude="*.test.*" "query.*\`.*\${" --include="*.ts" --include="*.py" . 2>/dev/null | grep -v '\$\${' | grep -q . \
  && echo "[CRITICAL] SQL injection risk — string interpolation in queries" || echo "[PASS] No SQL injection patterns"
grep -rn $X --exclude="*.test.*" "eval[(]" --include="*.ts" --include="*.tsx" --include="*.js" . 2>/dev/null | grep -q . \
  && echo "[HIGH] unsafe-eval usage found" || echo "[PASS] No unsafe-eval usage"
```

---

## Section 11 — Terraform / IaC Security (if present)

```bash
if [ -n "$HAS_TERRAFORM" ]; then
  echo "=== Terraform Security ==="
  grep -rn "roles/editor\|roles/owner\|storage\.admin\|secretmanager\.admin" terraform/ infra/ 2>/dev/null \
    | grep -v "^#\|\.terraform" | grep -q . && echo "[HIGH] Overly broad IAM role in Terraform" || echo "[PASS] No overly broad IAM roles"
  grep -rn "CHANGE_ME\|password.*default\|default.*password" terraform/ infra/ 2>/dev/null \
    | grep -v "^#" | grep -q . && echo "[CRITICAL] Default/placeholder password in Terraform" || true
  grep -rn "0\.0\.0\.0/0\|all_traffic\|allUsers" terraform/ infra/ 2>/dev/null \
    | grep -v "^#\|egress" | grep -q . && echo "[HIGH] Possible public resource in Terraform" || true
fi
```

---

## Final report

Summarize results per section: S1 IAM | S2 Network | S3 Storage | S4 Cloud Run | S5 Audit | S6 Secrets | S7 Container | S8 PII | S9 Privacy | S10 API | S11 Terraform

Report totals: CRITICAL: N  HIGH: N  MEDIUM: N  LOW: N

**Gate 5:** BLOCKED if any CRITICAL or HIGH. PASSED if zero critical + zero high.
