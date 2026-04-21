# Grill — Adversarial Code Review

Enter adversarial review mode. Challenge the current changes before a PR is created. Do not approve until satisfied.

## How to use
- `/grill` — adversarial review of current diff before `/pr`
- `/grill rewrite` — scrap and implement the elegant solution
- `/grill spec` — write detailed specs before handing off work

---

## Mode A — Code Review (default)

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
cd "$PROJECT_ROOT"
git diff main
git diff --staged
```

Read the diff. Identify risks:

- [ ] Does this handle the unhappy path?
- [ ] Are there race conditions or async issues?
- [ ] Is this the right abstraction (over- or under-engineered)?
- [ ] Will this break anything that depends on it?
- [ ] Are tests missing for the new behaviour?
- [ ] Is the naming clear to someone reading this cold?
- [ ] Could this be 50% simpler?

Ask the user **3–5 hard, specific questions** about the changes. Do not accept vague answers — probe further. Only approve (and proceed with `/pr`) once satisfied.

---

## Mode B — Elegant Rewrite

After a messy fix, start fresh:
- Identify the root insight that makes the solution simple
- Rewrite with that insight as the foundation — no legacy cruft
- The elegant solution is usually 30–50% less code

---

## Mode C — Spec-Driven Development

Ask clarifying questions until requirements are unambiguous. Produce a written spec (inputs, outputs, edge cases, acceptance criteria). Only begin implementation once spec is approved.

---

**GATE: User has answered all questions satisfactorily. Only then proceed to `/pr`.**
