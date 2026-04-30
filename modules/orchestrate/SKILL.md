---
name: orchestrate
description: Apply the Workflow Orchestration methodology for complex, multi-step tasks — plan-first approach, subagent strategy, self-improvement loop, verification before done, elegant solutions, and autonomous bug fixing. Use for any non-trivial task with 3+ steps or architectural decisions.
category: engineering
tier: core
slash_command: /orchestrate
allowed-tools: Bash Read Edit Write Grep Glob Agent
---

# Orchestrate — Complex Task Orchestration

Apply workflow orchestration methodology for multi-step tasks with 3+ steps or architectural decisions.

## How to use
- `/orchestrate <task>` — plan-first approach for any non-trivial task

---

## Methodology

### 1. Plan first (invoke `writing-plans` skill)

**Always start by invoking the `writing-plans` skill** to produce a structured plan document at `docs/superpowers/plans/YYYY-MM-DD-<feature>.md` with TDD-style task steps. Do not proceed to coding until the plan is written and reviewed.

- If something goes sideways mid-task: STOP, re-plan using `writing-plans` again
- Track progress via `tasks/todo.md` checkboxes

### 2. Use subagents
- Offload research, exploration, and parallel analysis to subagents
- Keep main context window clean and focused
- One task per subagent for precision

### 3. Self-improvement loop
- After any correction: note the pattern in `tasks/lessons.md`
- Review lessons at session start for relevant context

### 4. Verify before done
- Never mark complete without proving it works
- Run tests, check logs, diff behaviour vs main
- Ask: "Would a staff engineer approve this?"

### 5. Demand elegance
- After a working but messy fix: "Implement the elegant solution"
- Skip this for simple, obvious fixes

### 6. Autonomous bug fixing
- When given a bug: investigate and fix. Do not wait for hand-holding.
- Pair with `/fix` for CI failures and log-based bugs.

---

## Task Management

1. Write plan → `tasks/todo.md`
2. Check in before implementation starts
3. Mark items complete as you go
4. Document results in review section
5. Capture lessons → `tasks/lessons.md`
