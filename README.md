# Claude Dev Setup

Replicate the full Claude Code development environment on any machine in one command.

## What's included

| Component | Contents |
|-----------|----------|
| **Commands** | 13 slash commands: `/launch`, `/commit`, `/push`, `/test`, `/security`, `/lint`, `/gate`, `/docs`, `/architect`, `/cloud-security`, `/db`, `/enterprise-design`, `/issue` + 7 db engine files |
| **Plugins** | 14 plugins: superpowers, frontend-design, stripe, hookify, pr-review-toolkit, code-review, playwright, firecrawl, github, remember, skill-creator, code-simplifier, security-guidance, brightdata |
| **Shell aliases** | `cc`, `ccc`, `claude-update`, `claude-check` |
| **Templates** | CLAUDE.md starters for node-frontend, node-fullstack, python-api, docker-compose |

## Install

```bash
git clone https://github.com/rajitsaha/claude-dev-setup.git ~/claude-dev-setup
cd ~/claude-dev-setup
./install.sh
```

The installer will ask which components to install (all selected by default).

After installing:
1. Restart Claude Code (or run `source ~/.zshrc`)
2. Run `/reload-plugins` inside Claude Code to activate plugins

## Update

Check for updates:
```bash
claude-check
# or
~/claude-dev-setup/update.sh --check-only
```

Apply updates:
```bash
claude-update
# or
~/claude-dev-setup/update.sh
```

Auto-notify weekly (add to crontab with `crontab -e`):
```
0 9 * * 1 ~/claude-dev-setup/update.sh --check-only
```

## Shell aliases

| Alias | What it does |
|-------|-------------|
| `cc` | `claude` — launch Claude in current directory |
| `ccc` | `claude --continue` — continue last session |
| `claude-update` | Pull and apply latest setup |
| `claude-check` | Check for updates without applying |

## CLAUDE.md templates

Copy a template into any new project as `CLAUDE.md`:

```bash
cp ~/claude-templates/node-fullstack.md ./CLAUDE.md
# Edit with your project's specific details
```

Available templates: `node-frontend`, `node-fullstack`, `python-api`, `docker-compose`

## /db — Multi-engine database access

The `/db` command supports 7 database engines via a thin router + per-engine files:

| Engine | Connection method |
|--------|-----------------|
| `cloud-sql` | GCP Cloud SQL via temporary public IP |
| `postgres` | Direct TCP — PostgreSQL, Supabase |
| `snowflake` | Snowflake via snowsql or Python connector |
| `databricks` | Databricks SQL warehouse via Python connector |
| `athena` | AWS Athena via boto3 |
| `presto` | Presto / Trino via Python client |
| `oracle` | Oracle via cx_Oracle or sqlplus |

### Usage

```bash
/db                              # Default connectivity check for current project DB
/db "SELECT count(*) FROM users" # Arbitrary SQL on current project DB
/db migrate                      # Run pending migrations
/db prod-snowflake               # Named connection from global registry
/db prod-snowflake "SELECT ..."  # Named connection + custom SQL
```

### Configuration

**Project-level** — add a `## Database` section to your project's `CLAUDE.md`:

```markdown
## Database
engine: postgres
host: db.example.supabase.co
port: 5432
database: postgres
user: postgres
auth: env:DATABASE_URL
```

**Global registry** — create `~/.claude/db-connections.json` with named connections (see `commands/db-engines/` for examples). This file is personal and never committed to git.

---

## Adding a new plugin

1. Add the plugin identifier to `plugins.json`
2. Commit and push
3. Teammates run `claude-update` to get it
