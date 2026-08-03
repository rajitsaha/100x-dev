---
name: branch
description: Create a feature branch from the default branch with a descriptive, conventional name.
category: lifecycle
tier: core
slash_command: /branch
---

# Branch — Create Feature Branch

Create a feature branch from the default branch with a descriptive, conventional name.

## Do NOT ask for permission. Create the branch and push it.

---

## Step 1 — Detect default branch

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"
DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
DEFAULT_BRANCH="${DEFAULT_BRANCH:-main}"
CURRENT_BRANCH=$(git branch --show-current)
echo "Default branch: $DEFAULT_BRANCH"
echo "Current branch: $CURRENT_BRANCH"
```

If not on the default branch, warn:
```
⚠️ Currently on '$CURRENT_BRANCH', not '$DEFAULT_BRANCH'.
Creating branch from current HEAD. Proceed only if intentional.
```

---

## Step 2 — Pull latest

```bash
git fetch origin
git checkout "$DEFAULT_BRANCH"
git pull origin "$DEFAULT_BRANCH"
```

---

## Step 3 — Generate branch name

Derive a branch name from the task description using conventional prefixes:

| Prefix | Use when |
|:-------|:---------|
| `feat/` | New feature |
| `fix/` | Bug fix |
| `chore/` | Maintenance, deps, config |
| `refactor/` | Code restructuring |
| `docs/` | Documentation only |
| `test/` | Test additions or fixes |

**Naming rules:**
- Lowercase, hyphen-separated: `feat/add-user-auth`
- Max 50 characters for the slug portion
- No special characters beyond hyphens
- Derived from the task description or user input

**Examples:**
```
"Add user authentication"         → feat/add-user-auth
"Fix login timeout bug"           → fix/login-timeout
"Update dependencies"             → chore/update-deps
"Refactor payment module"         → refactor/payment-module
"Add API documentation"           → docs/api-docs
```

---

## Step 4 — Create and push branch

```bash
BRANCH_NAME="<prefix>/<slug>"
git checkout -b "$BRANCH_NAME"
git push -u origin "$BRANCH_NAME"
```

If the branch already exists locally or remotely:
```bash
git checkout "$BRANCH_NAME"
git pull origin "$BRANCH_NAME" 2>/dev/null || true
```

---

## Output

```
╔══════════════════════════════════════════════════════╗
║               BRANCH CREATED                          ║
╠══════════════════════════════════════════════════════╣
║ Branch:   feat/add-user-auth                         ║
║ Base:     main (up to date)                          ║
║ Remote:   origin/feat/add-user-auth ✅                ║
╠══════════════════════════════════════════════════════╣
║ STATUS: Ready to work                                ║
╚══════════════════════════════════════════════════════╝
```
