---
name: onboarding-cro
description: When the user wants to optimize post-signup onboarding, user activation, first-run experience, or time-to-value — "activation rate," "empty states," "onboarding checklist," "aha moment," "users sign up but don't use the product." Use when users sign up but don't stick around. For signup/registration optimization, see signup-flow-cro. For email sequences, see email-sequence.
category: marketing
tier: on-demand
---

# Onboarding CRO

Get users to their "aha moment" fast and build habits that drive long-term retention.

## Initial Assessment

**Product context:** If `.agents/product-marketing-context.md` exists (or `.claude/product-marketing-context.md` in older setups), read it first and tailor output to it; only ask for what it doesn't cover.

Understand first:

1. **Product Context** - product type? B2B or B2C? Core value proposition?
2. **Activation Definition** - the "aha moment"? What action shows a user "gets it"?
3. **Current State** - what happens after signup? Where do users drop off?

---

## Core Principles

1. **Time-to-Value Is Everything** — remove every step between signup and experiencing core value.
2. **One Goal Per Session** — focus the first session on one successful outcome; save advanced features for later.
3. **Do, Don't Show** — interactive > tutorial; doing the thing > learning about the thing.
4. **Progress Creates Motivation** — show advancement, celebrate completions, make the path visible.

---

## Defining Activation

### Find Your Aha Moment

The action most strongly correlated with retention: what retained users do that churned users don't; the earliest indicator of future engagement.

**Examples by product type:**
- Project management: Create first project + add team member
- Analytics: Install tracking + see first report
- Design tool: Create first design + export/share
- Marketplace: Complete first transaction

**Activation metrics:** % of signups reaching activation, time to activation, steps to activation, activation by cohort/source.

---

## Onboarding Flow Design

### Immediate Post-Signup (First 30 Seconds)

| Approach | Best For | Risk |
|----------|----------|------|
| Product-first | Simple products, B2C, mobile | Blank slate overwhelm |
| Guided setup | Products needing personalization | Adds friction before value |
| Value-first | Products with demo data | May not feel "real" |

**Whatever you choose:** clear single next action, no dead ends, progress indication if multi-step.

### Onboarding Checklist Pattern

**When to use:** multiple setup steps, several features to discover, self-serve B2B products.

**Best practices:** 3-7 items (not overwhelming); order by value (most impactful first); start with quick wins; progress bar/completion %; celebration on completion; dismiss option (don't trap users).

### Empty States

Onboarding opportunities, not dead ends: explain what the area is for, show what it looks like with data, offer one clear action to add the first item, optionally pre-populate example data.

### Tooltips and Guided Tours

**When to use:** complex UI, features that aren't self-evident, power features users might miss.

**Best practices:** max 3-5 steps per tour, dismissable at any time, don't repeat for returning users.

---

## Multi-Channel Onboarding

### Email + In-App Coordination

**Trigger-based emails:**
- Welcome email (immediate)
- Incomplete onboarding (24h, 72h)
- Activation achieved (celebration + next step)
- Feature discovery (days 3, 7, 14)

**Email should:** reinforce in-app actions (not duplicate them), drive back to product with a specific CTA, personalize based on actions taken.

---

## Handling Stalled Users

**Detection:** define "stalled" criteria (X days inactive, incomplete setup).

**Re-engagement tactics:**
1. **Email sequence** - reminder of value, address blockers, offer help
2. **In-app recovery** - welcome back, pick up where left off
3. **Human touch** - personal outreach for high-value accounts

---

## Measurement

### Key Metrics

| Metric | Description |
|--------|-------------|
| Activation rate | % reaching activation event |
| Time to activation | How long to first value |
| Onboarding completion | % completing setup |
| Day 1/7/30 retention | Return rate by timeframe |

### Funnel Analysis

Track drop-off at each step; focus on the biggest drops.
```
Signup → Step 1 → Step 2 → Activation → Retention
100%      80%       60%       40%         25%
```

---

## Output Format

**Onboarding Audit** — per issue: Finding → Impact → Recommendation → Priority

**Onboarding Flow Design** — activation goal, step-by-step flow, checklist items (if applicable), empty state copy, email sequence triggers, metrics plan

---

## Common Patterns by Product Type

| Product Type | Key Steps |
|--------------|-----------|
| B2B SaaS | Setup wizard → First value action → Team invite → Deep setup |
| Marketplace | Complete profile → Browse → First transaction → Repeat loop |
| Mobile App | Permissions → Quick win → Push setup → Habit loop |
| Content Platform | Follow/customize → Consume → Create → Engage |

---

## Experiment Ideas

Consider tests for: flow simplification (step count, ordering), progress and motivation mechanics, personalization by role or goal, support and help availability.

**For comprehensive experiment ideas**: See [references/experiments.md](references/experiments.md)

---

## Task-Specific Questions

1. What action most correlates with retention?
2. What happens immediately after signup?
3. Where do users currently drop off?
4. What's your activation rate target?
5. Any cohort analysis on successful vs. churned users?

---

## Related Skills

- **signup-flow-cro** — optimizing the signup before onboarding
- **email-sequence** — onboarding email series
- **paywall-upgrade-cro** — converting to paid during/after onboarding
- **ab-test-setup** — testing onboarding changes
