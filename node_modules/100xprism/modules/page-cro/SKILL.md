---
name: page-cro
description: When the user wants to increase conversions on any marketing page — homepage, landing, pricing, feature, or blog; "CRO," "this page isn't converting," "low conversion rate," "bounce rate," "my landing page sucks" — or just shares a URL asking for feedback. For signup flows, see signup-flow-cro; post-signup activation, onboarding-cro; forms, form-cro; popups, popup-cro.
category: marketing
tier: on-demand
---

# Page Conversion Rate Optimization (CRO)

Analyze marketing pages and deliver actionable recommendations to improve conversion rates.

## Initial Assessment

**Product context:** If `.agents/product-marketing-context.md` exists (or `.claude/product-marketing-context.md` in older setups), read it first and tailor output to it; only ask for what it doesn't cover.

Identify first:

1. **Page Type**: homepage, landing page, pricing, feature, blog, about, other
2. **Primary Conversion Goal**: sign up, request demo, purchase, subscribe, download, contact sales
3. **Traffic Context**: where are visitors coming from? (organic, paid, email, social)

---

## CRO Analysis Framework

Analyze these dimensions, in order of impact:

### 1. Value Proposition Clarity (Highest Impact)

Can a visitor grasp what this is and why they should care within 5 seconds? Is the primary benefit clear, specific, differentiated, and in customer language (not company jargon)?

**Common issues:** feature-focused instead of benefit-focused; too vague or too clever (sacrificing clarity); saying everything instead of the most important thing.

### 2. Headline Effectiveness

Does it communicate the core value proposition? Specific enough to be meaningful? Does it match the traffic source's messaging?

**Strong patterns:**
- Outcome-focused: "Get [desired outcome] without [pain point]"
- Specificity: numbers, timeframes, concrete details
- Social proof: "Join 10,000+ teams who..."

### 3. CTA Placement, Copy, and Hierarchy

One clear primary action, visible without scrolling, with button copy that communicates value, not just action:
- Weak: "Submit," "Sign Up," "Learn More"
- Strong: "Start Free Trial," "Get My Report," "See Pricing"

**Hierarchy:** logical primary vs. secondary CTA structure; CTAs repeated at key decision points.

### 4. Visual Hierarchy and Scannability

Can someone scanning get the main message? Are the most important elements visually prominent? Enough white space? Do images support or distract from the message?

### 5. Trust Signals and Social Proof

**Types:** customer logos (especially recognizable), testimonials (specific, attributed, with photos), case study snippets with real numbers, review scores and counts, security badges (where relevant).

**Placement:** near CTAs and after benefit claims.

### 6. Objection Handling

**Common objections:** price/value; "Will this work for my situation?"; implementation difficulty; "What if it doesn't work?"

**Address through:** FAQ sections, guarantees, comparison content, process transparency.

### 7. Friction Points

Too many form fields, unclear next steps, confusing navigation, required information that shouldn't be, mobile experience issues, long load times.

---

## Output Format

- **Quick Wins (Implement Now)** — easy changes with likely immediate impact
- **High-Impact Changes (Prioritize)** — bigger-effort changes that significantly improve conversions
- **Test Ideas** — hypotheses worth A/B testing rather than assuming
- **Copy Alternatives** — for key elements (headlines, CTAs), 2-3 alternatives with rationale

---

## Page-Specific Frameworks

**Homepage:** clear positioning for cold visitors; quick path to most common conversion; handle both "ready to buy" and "still researching."

**Landing page:** message match with traffic source; single CTA (remove navigation if possible); complete argument on one page.

**Pricing page:** clear plan comparison; recommended plan indication; address "which plan is right for me?" anxiety.

**Feature page:** connect feature to benefit; use cases and examples; clear path to try/buy.

**Blog post:** contextual CTAs matching content topic; inline CTAs at natural stopping points.

---

## Experiment Ideas

Consider tests for: hero section (headline, visual, CTA), trust signals and social proof placement, pricing presentation, form optimization, navigation and UX.

**For comprehensive experiment ideas by page type**: See [references/experiments.md](references/experiments.md)

---

## Task-Specific Questions

1. Current conversion rate and goal?
2. Where is traffic coming from?
3. What does the signup/purchase flow look like after this page?
4. Any user research, heatmaps, or session recordings?
5. What have you already tried?

---

## Related Skills

- **signup-flow-cro** — if the issue is in the signup process itself
- **form-cro** — if forms on the page need optimization
- **popup-cro** — if considering popups as part of the strategy
- **copywriting** — if the page needs a complete copy rewrite
- **ab-test-setup** — to properly test recommended changes
