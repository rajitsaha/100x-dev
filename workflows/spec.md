# Spec — Implementation-Ready Specification

Turn a vague request into an unambiguous, implementation-ready specification. Do not write any code until the spec is approved.

## How to use
- `/spec <feature request>` — clarify, read codebase, produce spec, get approval

---

## Phase 1 — Clarify (ask, don't assume)

Ask targeted questions to eliminate ambiguity:
- **Who** triggers this? (user action, background job, webhook, cron?)
- **What** is the exact input? (types, shapes, valid ranges, optional vs required)
- **What** is the exact output? (return value, side effects, UI state change)
- **What** are the error cases? (invalid input, missing data, network failure, auth failure)
- **What** are the constraints? (performance, backwards-compatibility, permissions, rate limits)
- **What** does "done" look like? (how do you know it works?)

Only ask questions that materially change the spec. Infer what you can from the codebase.

---

## Phase 2 — Read context

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"
git log --oneline -10
```

Read relevant existing code: find related files with Grep/Glob, understand existing data shapes, API contracts, naming conventions. Note anything constraining the implementation.

---

## Phase 3 — Write the spec

```
## Feature: [name]

### Summary
One paragraph: what this does and why.

### Inputs
- [param]: [type] — [description, valid values, required/optional]

### Outputs / Side Effects
- [what changes, what is returned, what events are fired]

### Acceptance Criteria
- [ ] [specific, testable condition]
- [ ] [specific, testable condition]

### Edge Cases & Error Handling
- [condition] → [expected behavior]

### Out of Scope
- [explicitly list what this does NOT do]

### Open Questions
- [anything unresolved — flag for user to decide]
```

---

## Phase 4 — Get approval

Present the spec. Do **not** proceed to implementation until the user says "approved", "lgtm", "ship it", or similar.

If the user requests changes: update the spec and re-present it.

**Once approved:** run `/commit` or hand off to implementation.
