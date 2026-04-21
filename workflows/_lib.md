# _lib — Shared Workflow Conventions
<!-- Reference only — not a slash command. Not included in adapter output. -->

## Standard preamble (paste into every workflow's first bash block)

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
INSTRUCTION_FILE=$(for f in CLAUDE.md AGENTS.md .cursorrules .windsurfrules .github/copilot-instructions.md GEMINI.md; do [ -f "$PROJECT_ROOT/$f" ] && echo "$PROJECT_ROOT/$f" && break; done)
```

## Autonomy banner
Add to any workflow that operates without user prompting:
```
## Do NOT ask for permission — [action]. Do NOT stop until done.
```

## Model hints
- `<!-- model: haiku -->` — mechanical tasks: lint, security scan, branch, docs, update-claude
- `<!-- model: opus -->` — deep reasoning: architect, enterprise-design, cloud-security
- (none) — general purpose: commit, push, pr, gate, test, fix, spec, grill, techdebt, context, query, orchestrate

## GATE line format
```
**GATE: [Condition that must be true before proceeding.]**
```
