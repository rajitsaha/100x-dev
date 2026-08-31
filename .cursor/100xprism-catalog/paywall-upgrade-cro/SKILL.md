---
name: paywall-upgrade-cro
description: When the user wants to create or optimize in-app paywalls, upgrade screens, upsell modals, or feature gates — "convert free to paid," "freemium conversion," "trial expiration screen," "limit reached," "free users won't upgrade." Covers in-product upgrade moments where the user has already experienced value — distinct from public pricing pages (see page-cro). For pricing decisions, see pricing-strategy.
category: marketing
tier: on-demand
---

# Paywall and Upgrade Screen CRO

Convert free users to paid — or users to higher tiers — at moments when they've experienced enough value to justify the commitment.

## Initial Assessment

**Product context:** If `.agents/product-marketing-context.md` exists (or `.claude/product-marketing-context.md` in older setups), read it first and tailor output to it; only ask for what it doesn't cover.

Understand first:

1. **Upgrade Context** - Freemium → Paid? Trial → Paid? Tier upgrade? Feature upsell? Usage limit?
2. **Product Model** - What's free? What's behind paywall? What triggers prompts? Current conversion rate?
3. **User Journey** - When does this appear? What have they experienced? What are they trying to do?

---

## Core Principles

1. **Value Before Ask** — user has experienced real value first; upgrade feels like the natural next step. Timing: after "aha moment," not before.
2. **Show, Don't Just Tell** — demonstrate paid-feature value, preview what they're missing, make the upgrade tangible.
3. **Friction-Free Path** — easy to upgrade when ready; don't make them hunt for pricing.
4. **Respect the No** — don't trap or pressure; easy to continue free; maintain trust for future conversion.

---

## Paywall Trigger Points

- **Feature gates** (user clicks a paid-only feature): explain why it's paid, show what the feature does, quick path to unlock, option to continue without.
- **Usage limits** (user hits a limit): clear indication of limit reached, show what upgrading provides, don't block abruptly.
- **Trial expiration**: early warnings (7, 3, 1 day), clear "what happens" on expiration, summarize value received.
- **Time-based prompts** (after X days of free use): gentle reminder, highlight unused paid features, easy to dismiss.

---

## Paywall Screen Components

1. **Headline** - focus on what they get: "Unlock [Feature] to [Benefit]"
2. **Value Demonstration** - preview, before/after, "With Pro you could..."
3. **Feature Comparison** - highlight key differences, current plan marked
4. **Pricing** - clear, simple, annual vs. monthly options
5. **Social Proof** - customer quotes, "X teams use this"
6. **CTA** - specific and value-oriented: "Start Getting [Benefit]"
7. **Escape Hatch** - clear "Not now" or "Continue with Free"

---

## Specific Paywall Types

### Feature Lock Paywall
```
[Lock Icon]
This feature is available on Pro

[Feature preview/screenshot]

[Feature name] helps you [benefit]:
• [Capability]
• [Capability]

[Upgrade to Pro - $X/mo]
[Maybe Later]
```

### Usage Limit Paywall
```
You've reached your free limit

[Progress bar at 100%]

Free: 3 projects | Pro: Unlimited

[Upgrade to Pro]  [Delete a project]
```

### Trial Expiration Paywall
```
Your trial ends in 3 days

What you'll lose:
• [Feature used]
• [Data created]

What you've accomplished:
• Created X projects

[Continue with Pro]
[Remind me later]  [Downgrade]
```

---

## Timing and Frequency

**Show:** after value moment (activation/aha), before frustration; when hitting genuine limits.

**Don't show:** during onboarding (too early), mid-flow, repeatedly after dismissal.

**Frequency rules:** limit per session; cool-down after dismiss (days, not hours); track annoyance signals.

---

## Upgrade Flow Optimization

**Paywall to payment:** minimize steps, keep in-context if possible, pre-fill known information.

**Post-upgrade:** immediate feature access, confirmation and receipt, guide to new features.

---

## A/B Testing

**Test:** trigger timing, headline/copy variations, price presentation, trial length, feature emphasis, design/layout.

**Track:** paywall impression rate, click-through to upgrade, completion rate, revenue per user, churn rate post-upgrade.

**For comprehensive experiment ideas**: See [references/experiments.md](references/experiments.md)

---

## Anti-Patterns to Avoid

**Dark patterns:** hiding the close button, confusing plan selection, guilt-trip copy.

**Conversion killers:** asking before value delivered, too-frequent prompts, blocking critical flows, complicated upgrade process.

---

## Task-Specific Questions

1. Current free → paid conversion rate?
2. What triggers upgrade prompts today?
3. What features are behind the paywall?
4. What's your "aha moment" for users?
5. Pricing model? (per seat, usage, flat)
6. Mobile app, web app, or both?

---

## Related Skills

- **churn-prevention** — cancel flows, save offers, reducing churn post-upgrade
- **page-cro** — public pricing page optimization
- **onboarding-cro** — driving to aha moment before upgrade
- **ab-test-setup** — testing paywall variations
