# db-engines/_router — Shared DB Engine Skeleton
<!-- Reference only — sourced by /db; not a slash command. -->

## Shared execution skeleton

Each engine file receives pre-resolved variables from the /db router:
`$DB_HOST`, `$DB_PORT`, `$DB_NAME`, `$DB_USER`, `$DB_PASS`, `$SQL`

### Step 1 — Validate prerequisites
Check that the engine CLI is available. If not, print install instructions and exit.

### Step 2 — Execute query via CLI (if available)
Use the engine's native CLI with SSL/TLS as required. Never log $DB_PASS.

### Step 3 — Execute query via driver (fallback)
If CLI unavailable, use a Node.js or Python driver equivalent.

### Step 4 — Migrate (if SQL = "migrate")
Detect migration tool (alembic, prisma, raw SQL scripts) and run it.

### Safety rules
- Never log or print $DB_PASS
- Always require SSL for non-localhost hosts
- Never commit connection strings with passwords
