---
name: programmatic-seo
description: When the user wants SEO pages generated at scale from templates plus a dataset — "programmatic SEO," "pSEO," "directory pages," "location pages," "[keyword] + [city] pages," "integration pages," "generate 100 pages," "templated landing pages." For auditing an existing site, see seo-audit. For planning, see content-strategy.
category: marketing
tier: on-demand
---

# Programmatic SEO

Build template- and data-driven SEO pages at scale that rank, provide value, and avoid thin-content penalties.

## Initial Assessment

**Product context:** If `.agents/product-marketing-context.md` exists (or `.claude/product-marketing-context.md` in older setups), read it first and tailor output to it; only ask for what it doesn't cover.

Understand first:

1. **Business Context** — product/service? Target audience? Conversion goal for these pages?
2. **Opportunity** — what search patterns exist? How many potential pages? Search volume distribution?
3. **Competition** — who ranks now? What do their pages look like? Can you realistically compete?

---

## Core Principles

1. **Unique value per page** — value specific to that page, not just swapped variables in a template; the more differentiated, the better.
2. **Proprietary data wins** — data defensibility hierarchy: (1) proprietary (you created it), (2) product-derived (from your users), (3) user-generated (your community), (4) licensed (exclusive access), (5) public (anyone can use—weakest).
3. **Clean URL structure** — use subfolders, not subdomains; subfolders consolidate domain authority, subdomains split it. Good: `yoursite.com/templates/resume/`. Bad: `templates.yoursite.com/resume/`.
4. **Genuine search intent match** — pages must actually answer what people search for.
5. **Quality over quantity** — better 100 great pages than 10,000 thin ones.
6. **Avoid Google penalties** — no doorway pages, keyword stuffing, or duplicate content; genuine utility for users.

---

## The 12 Playbooks (Overview)

| Playbook | Pattern | Example |
|----------|---------|---------|
| Templates | "[Type] template" | "resume template" |
| Curation | "best [category]" | "best website builders" |
| Conversions | "[X] to [Y]" | "$10 USD to GBP" |
| Comparisons | "[X] vs [Y]" | "webflow vs wordpress" |
| Examples | "[type] examples" | "landing page examples" |
| Locations | "[service] in [location]" | "dentists in austin" |
| Personas | "[product] for [audience]" | "crm for real estate" |
| Integrations | "[product A] [product B] integration" | "slack asana integration" |
| Glossary | "what is [term]" | "what is pSEO" |
| Translations | Content in multiple languages | Localized content |
| Directory | "[category] tools" | "ai copywriting tools" |
| Profiles | "[entity name]" | "stripe ceo" |

**For detailed playbook implementation**: See [references/playbooks.md](references/playbooks.md)

---

## Choosing Your Playbook

| If you have... | Consider... |
|----------------|-------------|
| Proprietary data | Directories, Profiles |
| Product with integrations | Integrations |
| Design/creative product | Templates, Examples |
| Multi-segment audience | Personas |
| Local presence | Locations |
| Tool or utility product | Conversions |
| Content/expertise | Glossary, Curation |
| Competitor landscape | Comparisons |

Playbooks can layer (e.g., "Best coworking spaces in San Diego").

---

## Implementation Framework

### 1. Keyword Pattern Research
Identify the pattern: repeating structure, variables, number of unique combinations. Validate demand: aggregate search volume, distribution (head vs. long tail), trend direction.

### 2. Data Requirements
What data populates each page? First-party, scraped, licensed, or public? How is it updated?

### 3. Template Design
**Page structure:** header with target keyword; unique intro (not just variables swapped); data-driven sections; related pages/internal links; CTAs appropriate to intent.

**Uniqueness:** unique value per page, conditional content based on data, original insights/analysis per page.

### 4. Internal Linking Architecture
**Hub and spoke:** hub = main category page; spokes = individual programmatic pages; cross-links between related spokes.

**No orphan pages:** every page reachable from main site, XML sitemap for all pages, breadcrumbs with structured data.

### 5. Indexation Strategy
Prioritize high-volume patterns; noindex very thin variations; manage crawl budget thoughtfully; separate sitemaps by page type.

---

## Quality Checks

### Pre-Launch Checklist

**Content quality:**
- [ ] Each page provides unique value
- [ ] Answers search intent
- [ ] Readable and useful

**Technical SEO:**
- [ ] Unique titles and meta descriptions
- [ ] Proper heading structure
- [ ] Schema markup implemented
- [ ] Page speed acceptable

**Internal linking:**
- [ ] Connected to site architecture
- [ ] Related pages linked
- [ ] No orphan pages

**Indexation:**
- [ ] In XML sitemap
- [ ] Crawlable
- [ ] No conflicting noindex

### Post-Launch Monitoring

Track: indexation rate, rankings, traffic, engagement, conversion. Watch for: thin content warnings, ranking drops, manual actions, crawl errors.

---

## Common Mistakes

- **Thin content**: just swapping city names in identical content
- **Keyword cannibalization**: multiple pages targeting same keyword
- **Over-generation**: pages with no search demand
- **Poor data quality**: outdated or incorrect information
- **Ignoring UX**: pages exist for Google, not users

---

## Output Format

**Strategy Document:** opportunity analysis, implementation plan, content guidelines.
**Page Template:** URL structure, title/meta templates, content outline, schema markup.

---

## Task-Specific Questions

1. What keyword patterns are you targeting?
2. What data do you have (or can acquire)?
3. How many pages are you planning?
4. What does your site authority look like?
5. Who currently ranks for these terms?
6. What's your technical stack?

---

## Related Skills

- **seo-audit** — auditing programmatic pages after launch
- **schema-markup** — adding structured data
- **site-architecture** — page hierarchy, URL structure, internal linking
- **competitor-alternatives** — comparison page frameworks
