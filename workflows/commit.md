# /commit — Gate → Stage → Commit

Quality gate runs FIRST. **Do NOT commit if any gate fails.**

## Do NOT ask for permission. Do NOT skip the gate.

---

## Phase 0 — Quality Gate (MANDATORY)

Invoke `/gate`. All four gates must pass before proceeding:

1. **Tests** — ≥ 95% coverage, zero failures
2. **Security** — zero critical, zero high vulnerabilities
3. **Local build** — zero compiler errors
4. **Docker build** — passes (or skipped if no Dockerfile)

**If `/gate` reports ANY failure → STOP. Do not stage. Do not commit. Fix the issue and re-run `/gate`.**

Only continue to Phase 1 when the gate summary shows: `✅ ALL GATES PASSED`

---

## Phase 1 — Review changes

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"
git status
git diff --stat
git diff --name-only HEAD 2>/dev/null || true
```

---

## Phase 2 — Update docs (if needed)

Based on what changed, update corresponding documentation:

| Changed files | Doc to update |
|---|---|
| API routes or handlers | API reference doc (README, CLAUDE.md, or `docs/`) |
| CLI commands or flags | CLI reference doc |
| New features or config | README.md or project-equivalent |
| Removed files/features | Remove stale references from all docs |
| `.claude/commands/**` | No doc update needed |

Read the project's `CLAUDE.md` for specific doc file paths. Skip if no docs are affected.

---

## Phase 3 — Stage files

Stage only task-related files. Never stage `.env`, `dist/`, `node_modules/`, `venv/`, unrelated work:

```bash
git add -u
# Or stage specific files if -u picks up unrelated changes:
# git add path/to/file1 path/to/file2
git diff --staged --stat
```

---

## Phase 4 — Write and create commit

Use [Conventional Commits](https://www.conventionalcommits.org/). Focus on **why**, not just what.

| Type | When to use |
|---|---|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `test` | Adding or updating tests |
| `chore` | Tooling, config, scripts, CI |
| `docs` | Documentation only |
| `refactor` | Code change with no behavior change |
| `perf` | Performance improvement |
| `security` | Vulnerability fix |

```bash
git commit -m "$(cat <<'EOF'
<type>(<scope>): <short summary under 72 chars>

- <Key change 1 and why>
- <Key change 2 and why>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Phase 5 — Verify

```bash
git log --oneline -3
```

---

## Output

```
=== /commit Complete ===
Gate:         ✅ ALL GATES PASSED
Staged files: N
Commit:       <short-hash> <message>
Status:       COMMITTED ✅
```
