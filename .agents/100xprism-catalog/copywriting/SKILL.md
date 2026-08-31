---
name: copywriting
description: When the user wants to write, rewrite, or improve marketing copy for any page — homepage, landing, pricing, feature, about, or product pages; "headline help," "CTA copy," "value proposition," "tagline," "hero section," "make this more compelling," "conversion copy," or complete Figma-ready full-page copy (see Full-Page Mode below). For email copy, see email-sequence. For popups, see popup-cro. For editing existing copy, see copy-editing.
category: marketing
tier: on-demand
---

# Copywriting

Expert conversion copywriter mode: write marketing copy that is clear, compelling, and drives action.

## Before Writing

**Product context:** If `.agents/product-marketing-context.md` exists (or `.claude/product-marketing-context.md` in older setups), read it first and tailor output to it; only ask for what it doesn't cover.

Gather this context (ask if not provided):

### 1. Page Purpose
- Page type? (homepage, landing page, pricing, feature, about)
- The ONE primary action visitors should take?

### 2. Audience
- Ideal customer, and the problem they're trying to solve?
- Objections or hesitations? What language do they use to describe the problem?

### 3. Product/Offer
- What are you selling? What makes it different from alternatives?
- Key transformation or outcome? Proof points (numbers, testimonials, case studies)?

### 4. Context
- Traffic source? (ads, organic, email)
- What do visitors already know before arriving?

---

## Copywriting Principles

### Clarity Over Cleverness
If forced to choose between clear and creative, choose clear.

### Benefits Over Features
Features: what it does. Benefits: what that means for the customer.

### Specificity Over Vagueness
Not "Save time on your workflow" — "Cut your weekly reporting from 4 hours to 15 minutes."

### Customer Language Over Company Language
Mirror voice-of-customer from reviews, interviews, support tickets.

### One Idea Per Section
Each section advances one argument; build a logical flow down the page.

---

## Writing Style Rules

### Core Principles

1. **Simple over complex** — "Use" not "utilize," "help" not "facilitate"
2. **Specific over vague** — Avoid "streamline," "optimize," "innovative"
3. **Active over passive** — "We generate reports" not "Reports are generated"
4. **Confident over qualified** — Remove "almost," "very," "really"
5. **Show over tell** — Describe the outcome instead of using adverbs
6. **Honest over sensational** — Fabricated statistics or testimonials erode trust and create legal liability

### Quick Quality Check

- Jargon that could confuse outsiders? Sentences trying to do too much?
- Passive voice? Exclamation points? (remove them)
- Marketing buzzwords without substance?

For thorough line-by-line review, use the **copy-editing** skill after your draft.

---

## Best Practices

### Be Direct
Get to the point; don't bury the value in qualifications.

❌ Slack lets you share files instantly, from documents to images, directly in your conversations

✅ Need to share a screenshot? Send as many documents, images, and audio files as your heart desires.

### Use Rhetorical Questions
They engage readers and make them think about their own situation: "Hate returning stuff to Amazon?" "Tired of chasing approvals?"

### Use Analogies When Helpful
Analogies make abstract concepts concrete and memorable.

### Pepper in Humor (When Appropriate)
Puns and wit make copy memorable — only if it fits the brand and doesn't undermine clarity.

---

## Page Structure Framework

### Above the Fold

**Headline** — your single most important message; communicate the core value proposition; specific > generic.

**Example formulas:**
- "{Achieve outcome} without {pain point}"
- "The {category} for {audience}"
- "Never {unpleasant event} again"
- "{Question highlighting main pain point}"

**Comprehensive headline formulas**: See [references/copy-frameworks.md](references/copy-frameworks.md)

**Natural transition phrases**: See [references/natural-transitions.md](references/natural-transitions.md)

**Subheadline** — expands on the headline, adds specificity, 1-2 sentences max.

**Primary CTA** — action-oriented button text that communicates what they get: "Start Free Trial" > "Sign Up."

### Core Sections

| Section | Purpose |
|---------|---------|
| Social Proof | Build credibility (logos, stats, testimonials) |
| Problem/Pain | Show you understand their situation |
| Solution/Benefits | Connect to outcomes (3-5 key benefits) |
| How It Works | Reduce perceived complexity (3-4 steps) |
| Objection Handling | FAQ, comparisons, guarantees |
| Final CTA | Recap value, repeat CTA, risk reversal |

**Detailed section types and page templates**: See [references/copy-frameworks.md](references/copy-frameworks.md)

---

## CTA Copy Guidelines

**Weak CTAs (avoid):** Submit, Sign Up, Learn More, Click Here, Get Started

**Strong CTAs (use):** Start Free Trial; Get [Specific Thing]; See [Product] in Action; Create Your First [Thing]; Download the Guide

**Formula:** [Action Verb] + [What They Get] + [Qualifier if needed]

Examples: "Start My Free Trial" — "Get the Complete Checklist" — "See Pricing for My Team"

---

## Page-Specific Guidance

### Homepage
Serve multiple audiences without being generic; lead with the broadest value proposition; give clear paths for different visitor intents.

### Landing Page
Single message, single CTA; match headline to ad/traffic source; complete argument on one page.

### Pricing Page
Help visitors choose the right plan; address "which is right for me?" anxiety; make the recommended plan obvious.

### Feature Page
Connect feature → benefit → outcome; show use cases and examples; clear path to try or buy.

### About Page
Tell the story of why you exist; connect mission to customer benefit; still include a CTA.

---

## Voice and Tone

Establish before writing:

**Formality level:** casual/conversational, professional but friendly, or formal/enterprise.

**Brand personality:** playful or serious? Bold or understated? Technical or accessible?

Maintain consistency but adjust intensity: headlines can be bolder, body copy should be clearer, CTAs should be action-oriented.

---

## Output Format

### Page Copy
Organized by section: headline, subheadline, CTA; section headers and body copy; secondary CTAs.

### Annotations
For key elements, explain why you made this choice and what principle it applies.

### Alternatives
For headlines and CTAs, provide 2-3 options: "Option A: [copy] — [rationale]."

### Meta Content (if relevant)
Page title (for SEO) and meta description.

---

## Full-Page Mode (Figma Make / complete website copy)

When asked for **complete, drop-in website copy** (e.g. for a landing page or
SaaS site, or as input to `figma-translator`), act as a Senior Conversion
Strategist and write every section below with explicit character counts and
labeled hierarchy so it can populate Figma Make layouts without editing:

1. **Hero** — Headline (≤6 words), Subheadline (~15 words), Primary CTA
2. **Feature sections** — three benefit blocks (headline + persuasive description)
3. **Social proof** — testimonial framework, authority indicators, quantifiable results
4. **FAQ** — eight high-intent questions with conversion-focused answers
5. **Footer** — structured navigation, legal disclaimers, social prompts

Requirements: apply persuasion triggers (authority, urgency, exclusivity),
integrate high-impact power words, specify a character count for each field, and
label hierarchy (H1 / H2 / Body).

---

## Related Skills

- **copy-editing**: For polishing existing copy (use after your draft)
- **page-cro**: If page structure/strategy needs work, not just copy
- **email-sequence**: For email copywriting
- **popup-cro**: For popup and modal copy
- **ab-test-setup**: To test copy variations
