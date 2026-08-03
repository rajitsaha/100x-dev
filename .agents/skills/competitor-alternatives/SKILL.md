---
name: competitor-alternatives
description: "When the user wants competitor comparison or alternative pages for SEO and sales enablement — 'alternative page,' 'vs page,' '[Product] vs [Product],' 'battle card,' 'competitor teardown.' Covers four formats: singular/plural alternatives, you vs competitor, competitor vs competitor. For sales-specific competitor docs, see sales-enablement."
category: marketing
tier: on-demand
---

# Competitor & Alternative Pages

## Initial Assessment

**Product context:** If `.agents/product-marketing-context.md` exists (or `.claude/product-marketing-context.md` in older setups), read it first and tailor output to it; only ask for what it doesn't cover.

Establish:

1. **Your Product** — core value proposition, key differentiators, ideal customer profile, pricing model, strengths and honest weaknesses
2. **Competitive Landscape** — direct and indirect/adjacent competitors, market positioning of each, search volume for competitor terms
3. **Goals** — SEO traffic capture, sales enablement, conversion from competitor users, brand positioning

---

## Core Principles

### 1. Honesty Builds Trust
Acknowledge competitor strengths, be accurate about your limitations, don't misrepresent competitor features — readers are comparing and will verify claims.

### 2. Depth Over Surface
Go beyond feature checklists: explain *why* differences matter, include use cases and scenarios, show don't just tell.

### 3. Help Them Decide
Different tools fit different needs. Be clear about who you're best for and who the competitor is best for. Reduce evaluation friction.

### 4. Modular Content Architecture
Centralize competitor data — single source of truth per competitor so updates propagate to all pages.

---

## Page Formats

### Format 1: [Competitor] Alternative (Singular)

**Search intent**: Actively looking to switch from a specific competitor

**URL pattern**: `/alternatives/[competitor]` or `/[competitor]-alternative`

**Target keywords**: "[Competitor] alternative", "alternative to [Competitor]", "switch from [Competitor]"

**Page structure**:
1. Why people look for alternatives (validate their pain)
2. Summary: You as the alternative (quick positioning)
3. Detailed comparison (features, service, pricing)
4. Who should switch (and who shouldn't)
5. Migration path
6. Social proof from switchers
7. CTA

---

### Format 2: [Competitor] Alternatives (Plural)

**Search intent**: Researching options, earlier in journey

**URL pattern**: `/alternatives/[competitor]-alternatives`

**Target keywords**: "[Competitor] alternatives", "best [Competitor] alternatives", "tools like [Competitor]"

**Page structure**:
1. Why people look for alternatives (common pain points)
2. What to look for in an alternative (criteria framework)
3. List of alternatives (you first, but include real options)
4. Comparison table (summary)
5. Detailed breakdown of each alternative
6. Recommendation by use case
7. CTA

**Important**: Include 4-7 real alternatives. Being genuinely helpful builds trust and ranks better.

---

### Format 3: You vs [Competitor]

**Search intent**: Directly comparing you to a specific competitor

**URL pattern**: `/vs/[competitor]` or `/compare/[you]-vs-[competitor]`

**Target keywords**: "[You] vs [Competitor]", "[Competitor] vs [You]"

**Page structure**:
1. TL;DR summary (key differences in 2-3 sentences)
2. At-a-glance comparison table
3. Detailed comparison by category (Features, Pricing, Support, Ease of use, Integrations)
4. Who [You] is best for
5. Who [Competitor] is best for (be honest)
6. What customers say (testimonials from switchers)
7. Migration support
8. CTA

---

### Format 4: [Competitor A] vs [Competitor B]

**Search intent**: Comparing two competitors (not you directly)

**URL pattern**: `/compare/[competitor-a]-vs-[competitor-b]`

**Page structure**:
1. Overview of both products
2. Comparison by category
3. Who each is best for
4. The third option (introduce yourself)
5. Comparison table (all three)
6. CTA

**Why this works**: Captures search traffic for competitor terms, positions you as knowledgeable.

---

## Essential Sections

### TL;DR Summary
Start every page with key differences in 2-3 sentences for scanners.

### Paragraph Comparisons
Go beyond tables — for each dimension, a paragraph explaining the differences and when each matters.

### Feature Comparison
Per category: how each handles it, strengths and limitations, bottom-line recommendation.

### Pricing Comparison
Tier-by-tier comparison, what's included, hidden costs, total cost calculation for a sample team size.

### Who It's For
Be explicit about the ideal customer for each option — honest recommendations build trust.

### Migration Section
What transfers, what needs reconfiguration, support offered, quotes from customers who switched.

Detailed templates: [references/templates.md](references/templates.md)

---

## Content Architecture

### Centralized Competitor Data
Create a single source of truth per competitor with: positioning and target audience, pricing (all tiers), feature ratings, strengths and weaknesses, best for / not ideal for, common complaints (from reviews), migration notes.

Data structure and examples: [references/content-architecture.md](references/content-architecture.md)

---

## Research Process

### Deep Competitor Research

For each competitor, gather:

1. **Product research**: Sign up, use it, document features/UX/limitations
2. **Pricing research**: Current pricing, what's included, hidden costs
3. **Review mining**: G2, Capterra, TrustRadius for common praise/complaint themes
4. **Customer feedback**: Talk to customers who switched (both directions)
5. **Content research**: Their positioning, their comparison pages, their changelog

### Ongoing Updates

- **Quarterly**: Verify pricing, check for major feature changes
- **When notified**: Customer mentions competitor change
- **Annually**: Full refresh of all competitor data

---

## SEO Considerations

### Keyword Targeting

| Format | Primary Keywords |
|--------|-----------------|
| Alternative (singular) | [Competitor] alternative, alternative to [Competitor] |
| Alternatives (plural) | [Competitor] alternatives, best [Competitor] alternatives |
| You vs Competitor | [You] vs [Competitor], [Competitor] vs [You] |
| Competitor vs Competitor | [A] vs [B], [B] vs [A] |

### Internal Linking
Link between related competitor pages, from feature pages to relevant comparisons, and create a hub page linking to all competitor content.

### Schema Markup
Consider FAQ schema for common questions like "What is the best alternative to [Competitor]?"

---

## Output Format

### Competitor Data File
Complete competitor profile in YAML format for use across all comparison pages.

### Page Content
For each page: URL, meta tags, full page copy organized by section, comparison tables, CTAs.

### Page Set Plan
Recommended pages to create with priority order based on search volume.

---

## Task-Specific Questions

1. What are common reasons people switch to you?
2. Do you have customer quotes about switching?
3. What's your pricing vs. competitors?
4. Do you offer migration support?

---

## Related Skills

- **programmatic-seo**: For building competitor pages at scale
- **copywriting**: For writing compelling comparison copy
- **seo-audit**: For optimizing competitor pages
- **schema-markup**: For FAQ and comparison schema
- **sales-enablement**: For internal sales collateral, decks, and objection docs
