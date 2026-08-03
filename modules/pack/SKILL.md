---
name: pack
description: Install, list, or uninstall optional vendor skill packs not bundled by default — "add the Databricks pack", "what packs are available", "is there a pack for X", "get me the Databricks skills".
category: engineering
tier: on-demand
model: haiku
slash_command: /pack
---

# Pack — Optional Third-Party Skill Packs

Packs are skill collections 100xprism does not ship by default because they only
matter to some projects. They are opt-in: nothing installs until you ask.

> **Scope:** `/pack` installs skills you don't have. To authenticate a CLI you
> already have, use `/connect`.

## Usage
- `/pack` — list every pack, its install state, and anything detected here
- `/pack detect` — only what matches the current project
- `/pack add databricks` — install a pack
- `/pack remove databricks` — reverse what 100xprism installed

---

## Step 1 — Locate the helper

All decisions live in the helper script. Do not reimplement them here.

```bash
PACKS=""
for candidate in \
  "$HOME/100xprism/adapters/lib/packs.py" \
  "$(npm root -g 2>/dev/null)/100xprism/adapters/lib/packs.py"; do
  if [ -f "$candidate" ]; then PACKS="$candidate"; break; fi
done
if [ -z "$PACKS" ]; then
  echo "100xprism installation not found — reinstall with: npm i -g 100xprism"
  exit 1
fi
```

## Step 2 — Route the argument

Pass the user's words through this case statement verbatim. Do not invent a
subcommand: anything unrecognised is a usage error, not a guess.

```bash
ARG1="${1:-}"
SLUG="${2:-}"
case "$ARG1" in
  "")       SUB="status" ;;
  detect)   SUB="detect" ;;
  add)      SUB="add" ;;
  remove)   SUB="remove" ;;
  *)        echo "Usage: /pack [detect | add <slug> | remove <slug>]"; exit 1 ;;
esac

if [ "$SUB" = "add" ] || [ "$SUB" = "remove" ]; then
  if [ -z "$SLUG" ]; then
    echo "Usage: /pack $SUB <slug>   (run /pack to list available slugs)"
    exit 1
  fi
fi
```

## Step 3 — Run it

`"$SLUG"` stays quoted so a slug can never split into extra arguments or inject a
flag into the helper.

```bash
python3 "$PACKS" "$SUB" "$SLUG" --settings "$HOME/.claude/settings.json"
```

## Step 4 — Report

Print the helper's output verbatim. It already says which platforms were handled and
which need a manual step.

If any pack was added or removed, finish with: **restart your agent to pick up the
change.**

Two things to pass along honestly rather than paper over:

- A platform marked `manual` was **not** installed. Give the user the exact command
  the helper printed.
- `/pack remove` reverses only what 100xprism wrote. A pack installed by an upstream
  CLI leaves its skill files on disk — say so; do not delete them.
