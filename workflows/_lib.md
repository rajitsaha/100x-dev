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

## SaaS credentials
When a workflow requires cloud or SaaS credentials, reference the **connect** workflow:
- Run `/connect` to see status of all 25+ services
- Run `/connect <service>` to install CLI + authenticate a specific service
- Credentials are stored in `.env` (copy `.env.example` to start)
- Services: github · aws · gcp · azure · vercel · netlify · railway · heroku · flyio · supabase · planetscale · firebase · stripe · cloudflare · docker · terraform · sentry · datadog · jira · linear · slack · notion · npm · pypi · digitalocean · render · mongodb
