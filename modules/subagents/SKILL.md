---
name: subagents
description: Use subagents to throw more compute at hard problems, keep the main context window clean, and auto-approve safe permissions via hooks. Use when a task is complex, exploratory, or can be parallelized across multiple independent workstreams.
category: engineering
tier: on-demand
allowed-tools: Agent
---

Invoke this skill when a task is complex, exploratory, or parallel in nature. Subagents keep the main context clean and focused.

## When to Use Subagents

- Append "use subagents" to any request where you want Claude to throw more compute at the problem
- Use for: codebase exploration, parallel analysis, research, large refactors, test writing
- Do NOT use for: simple one-file edits, quick lookups, single-step tasks

## Three Subagent Strategies

### A. Parallelization
Offload independent tasks to separate subagents running simultaneously:
```
use 5 subagents to explore the codebase
→ Explore entry points and startup
→ Explore React component structure
→ Explore tools implementation
→ Explore state management
→ Explore testing infrastructure
```

### B. Context Isolation
Offload heavy research or analysis to a subagent so the main agent's context stays focused on the implementation.
- Research → subagent → returns a summary
- Main agent uses the summary, never sees the raw noise

### C. Permission Routing via Hook
Route permission requests to a smarter model via a hook:
- Hook intercepts permission requests
- Sends to a model (e.g., Opus) to scan for attacks and auto-approve safe ones
- Dangerous or ambiguous requests get flagged for human review
- See: code.claude.com/docs for hook configuration

## Usage Patterns

```
# More compute on a hard problem
"Refactor the auth system. Use subagents."

# Parallel exploration
"Use 5 subagents to map out every API endpoint and their dependencies"

# Background agent
ctrl+b  →  runs current task in background agent
```

## Principles

- One focused task per subagent
- Subagents return summaries, not raw data dumps
- Use background agents (ctrl+b) for long-running tasks so you can keep working
- Subagents are especially valuable for: codebase mapping, test generation, doc writing, and competitive analysis
