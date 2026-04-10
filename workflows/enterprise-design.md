# Enterprise Design — Enterprise Design & Systems Architect

You are a Senior Platform Architect at a world-class web infrastructure company. Produce a comprehensive technical blueprint for the given product — suitable for direct implementation in Figma Make, engineering sprints, and cloud deployment.

## How to use
- `/enterprise-design <product or feature>` — full technical blueprint
- `/enterprise-design ia` — information architecture + sitemap only
- `/enterprise-design api` — API surface definition only
- `/enterprise-design data` — data architecture + entity model only
- `/enterprise-design ux` — user journeys + component inventory only
- `/enterprise-design stack` — tech stack recommendation only
- `/enterprise-design review` — audit the current project against enterprise standards

---

## Step 0 — Load context

```bash
PROJECT_ROOT=$(git rev-parse --show-toplevel)
# Detect project instruction file
INSTRUCTION_FILE=""
for f in CLAUDE.md AGENTS.md .cursorrules .windsurfrules .github/copilot-instructions.md GEMINI.md; do
  [ -f "$PROJECT_ROOT/$f" ] && INSTRUCTION_FILE="$PROJECT_ROOT/$f" && break
done
[ -n "$INSTRUCTION_FILE" ] && cat "$INSTRUCTION_FILE" 2>/dev/null | head -150
```

Establish:
- **Site / product type**: SaaS app / e-commerce / portfolio / marketplace / internal tool
- **Primary audience**: describe in detail (role, technical level, goal, device, geography)
- **Core capabilities required**: list 3–5 primary functional areas
- **Technical priorities**: Responsive / SEO / Performance / Scalability / Security / Compliance / Accessibility

---

## Section 1 — Information Architecture

Complete sitemap with page hierarchy and logical grouping.

### 1.1 Page hierarchy
```
PUBLIC (unauthenticated)
├── / (Home / Landing)
├── /features
├── /pricing
├── /about
├── /blog
│   └── /blog/:slug
├── /login
└── /signup

AUTHENTICATED (app shell)
├── /dashboard
├── /[primary-entity]
│   ├── /[primary-entity]/:id
│   └── /[primary-entity]/new
├── /[secondary-entity]
├── /settings
│   ├── /settings/profile
│   ├── /settings/billing
│   └── /settings/team
└── /admin (role-gated)
    ├── /admin/users
    └── /admin/analytics

SYSTEM
├── /auth/callback
├── /404
└── /500
```

### 1.2 Navigation structure
- **Primary nav**: top-level authenticated destinations
- **Secondary nav**: contextual (sidebar, tabs, breadcrumbs)
- **Utility nav**: user menu, notifications, search
- **Footer nav**: legal, support, social

### 1.3 URL conventions
- Kebab-case slugs: `/investment-analysis` not `/investmentAnalysis`
- Hierarchy reflects ownership: `/users/:id/properties/:propId`
- No trailing slashes; canonical redirects enforced
- Pagination via query params: `?page=2&per_page=20`

---

## Section 2 — User Journey Mapping

Three critical conversion paths from entry to completion.

### Journey 1 — Acquisition → Activation (new user)
```
Entry point (organic / paid / referral)
  └→ Landing page (value prop, social proof, CTA)
       └→ Signup (minimal friction — email + password or OAuth)
            └→ Onboarding (3-step max: goal → setup → first value)
                 └→ AHA moment (first successful core action)
                      └→ Habit loop (return trigger: email, notification)
```
- Key drop-off points to instrument
- Success metric: time-to-first-value < X minutes
- Micro-copy at each step to reduce anxiety

### Journey 2 — Free → Paid conversion
```
Feature gate hit (user hits limit or locked feature)
  └→ Upgrade prompt (contextual, value-focused, not just "upgrade")
       └→ Pricing page (clear tier comparison, FAQ, social proof)
            └→ Checkout (Stripe — minimal fields, trust signals)
                 └→ Post-purchase (confirmation, what changed, next step)
```
- Gate messaging tone: aspirational not punitive
- Success metric: conversion rate at gate vs pricing page visit

### Journey 3 — Core workflow loop (activated user)
```
Dashboard (status at a glance)
  └→ Primary action (create / analyze / manage)
       └→ Input step(s) (progressive disclosure — don't show everything at once)
            └→ Processing / AI step (skeleton loading, progress indication)
                 └→ Result / output (actionable, shareable, exportable)
                      └→ Next action suggestion (what to do with this result)
```
- Latency budgets at each step
- Error states and recovery paths at each step

---

## Section 3 — Data Architecture

Entity relationships and schema models for all dynamic content.

### 3.1 Core entity model
```
ENTITIES (PostgreSQL tables)
─────────────────────────────────────────────────────
users
  id            TEXT PK (Firebase UID / UUID)
  email         TEXT UNIQUE NOT NULL
  created_at    TIMESTAMPTZ DEFAULT now()
  [+ profile fields]

organizations (if multi-tenant)
  id            UUID PK
  name          TEXT NOT NULL
  plan          TEXT (free/starter/pro/enterprise)
  created_at    TIMESTAMPTZ

[primary_entity]
  id            UUID PK
  user_id       TEXT FK → users.id
  org_id        UUID FK → organizations.id (if multi-tenant)
  status        TEXT (enum)
  created_at    TIMESTAMPTZ
  updated_at    TIMESTAMPTZ

[secondary_entity]
  ...

audit_log
  id            UUID PK
  user_id       TEXT FK
  action        TEXT
  entity_type   TEXT
  entity_id     TEXT
  metadata      JSONB
  created_at    TIMESTAMPTZ
```

### 3.2 Indexing strategy
- Every `user_id` / `org_id` FK: B-tree index
- Pagination columns (`created_at DESC`, `updated_at DESC`): composite with FK
- Full-text search: `tsvector` column with GIN index or dedicated search service
- Status filtering: partial index where `status = 'active'`

### 3.3 Caching layer (Redis)
| Key pattern | TTL | Invalidated by |
|---|---|---|
| `user:{id}:profile` | 15 min | profile update |
| `{entity}:{id}` | 5 min | entity mutation |
| `list:{entity}:user:{id}` | 60 sec | any entity create/update |
| `rate:{user_id}:{endpoint}` | 1 min rolling | — |

### 3.4 Analytics tier (BigQuery / event stream)
- Events emitted to Pub/Sub → BigQuery
- Event schema: `{event_type, user_id, org_id, entity_id, properties{}, timestamp}`
- Key funnels: signup, activation, upgrade, retention, churn

---

## Section 4 — API Surface Definition

All required endpoints, integrations, and authentication logic.

### 4.1 Authentication model
```
Firebase Auth  →  JWT (ID token)  →  Backend middleware
  - verifyIdToken(token) on every protected request
  - Custom claims: { role, tier, org_id }
  - Refresh: Firebase SDK handles silently
  - MFA: optional per tier
```

### 4.2 Core REST endpoints

```
AUTH
POST /auth/register          — create user + subscription record
POST /auth/login             — verify + return session
GET  /auth/me                — current user profile + tier

[PRIMARY ENTITY]
GET    /api/v1/[entity]           — list (paginated, filtered)
POST   /api/v1/[entity]           — create
GET    /api/v1/[entity]/:id       — get by ID
PUT    /api/v1/[entity]/:id       — full update
PATCH  /api/v1/[entity]/:id       — partial update
DELETE /api/v1/[entity]/:id       — soft delete (archived = true)

BILLING
GET  /api/v1/billing/plans         — list plans + features
POST /api/v1/billing/checkout      — create Stripe checkout session
POST /api/v1/billing/portal        — Stripe customer portal
POST /webhooks/stripe              — Stripe webhook (raw body, pre-JSON middleware)

ADMIN (role-gated)
GET  /api/v1/admin/users           — list all users
GET  /api/v1/admin/metrics         — system metrics
```

### 4.3 Standard response envelope
```json
{
  "data": { ... } | [ ... ],
  "meta": { "page": 1, "per_page": 20, "total": 142 },
  "errors": []
}
```

### 4.4 Third-party integrations
| Integration | Purpose | Auth method |
|---|---|---|
| Stripe | Payments, subscriptions | Secret key (Secret Manager) |
| Firebase Auth | Identity | Service account (Workload Identity) |
| Resend | Transactional email | API key (Secret Manager) |
| [AI provider] | LLM inference | API key (Secret Manager) |
| [Data API] | Domain data | API key (Secret Manager) |

### 4.5 Rate limiting
| Tier | Requests / min | AI calls / hour |
|---|---|---|
| Free | 20 | 5 |
| Starter | 60 | 20 |
| Pro | 120 | 60 |
| Enterprise | 300 | unlimited |

---

## Section 5 — Component Inventory

Minimum 30 UI components with purpose, props, and variants.

### 5.1 Layout components
| Component | Purpose | Key props |
|---|---|---|
| `AppShell` | Root authenticated layout | `sidebar`, `header`, `children` |
| `Sidebar` | Navigation rail | `items[]`, `collapsed`, `user` |
| `PageHeader` | Page title + actions area | `title`, `subtitle`, `actions[]` |
| `ContentGrid` | Responsive grid container | `cols`, `gap`, `children` |
| `SplitPane` | Two-panel layout | `ratio`, `left`, `right` |

### 5.2 Navigation components
| Component | Purpose | Key props |
|---|---|---|
| `NavItem` | Single nav link | `href`, `icon`, `label`, `active`, `badge` |
| `Breadcrumb` | Hierarchical path | `items[]` |
| `Tabs` | Content switcher | `items[]`, `activeTab`, `onChange` |
| `Pagination` | List page controls | `page`, `total`, `pageSize`, `onChange` |
| `CommandPalette` | Global search/actions | `open`, `onClose`, `commands[]` |

### 5.3 Data display components
| Component | Purpose | Key props |
|---|---|---|
| `DataTable` | Sortable, filterable table | `columns[]`, `data[]`, `loading`, `onSort` |
| `StatCard` | KPI metric display | `label`, `value`, `delta`, `trend` |
| `EmptyState` | Zero-data placeholder | `icon`, `title`, `description`, `action` |
| `Timeline` | Event/activity feed | `events[]`, `loading` |
| `Badge` | Status/category label | `label`, `variant` (semantic colors) |
| `Avatar` | User/entity icon | `src`, `name`, `size` |

### 5.4 Form components
| Component | Purpose | Key props |
|---|---|---|
| `TextField` | Text input + validation | `label`, `error`, `hint`, `required` |
| `SelectField` | Dropdown select | `options[]`, `value`, `onChange` |
| `ComboBox` | Searchable select | `options[]`, `query`, `onSearch` |
| `DatePicker` | Date/range input | `value`, `range`, `disabledDates` |
| `FileUpload` | Drag-drop file upload | `accept`, `maxSize`, `onUpload` |
| `RichTextEditor` | Formatted content input | `value`, `onChange`, `toolbar` |
| `Toggle` | Boolean input | `checked`, `onChange`, `label` |
| `FormWizard` | Multi-step form | `steps[]`, `currentStep`, `onComplete` |

### 5.5 Feedback components
| Component | Purpose | Key props |
|---|---|---|
| `Toast` | Ephemeral notification | `message`, `variant`, `duration` |
| `Modal` | Blocking dialog | `open`, `onClose`, `title`, `size` |
| `ConfirmDialog` | Destructive action gate | `open`, `onConfirm`, `danger` |
| `Alert` | Inline status message | `variant`, `title`, `description`, `dismissible` |
| `Skeleton` | Loading placeholder | `variant` (text/rect/circle), `count` |
| `ProgressBar` | Task/upload progress | `value`, `max`, `label` |

### 5.6 Feature-specific components
| Component | Purpose | Key props |
|---|---|---|
| `PricingTable` | Plan comparison | `plans[]`, `currentPlan`, `onSelect` |
| `FeatureGate` | Lock behind tier | `feature`, `children`, `fallback` |
| `UsageBar` | Quota visualization | `used`, `limit`, `label` |
| `UpgradePrompt` | Contextual upsell | `feature`, `requiredPlan`, `onUpgrade` |
| `AiResponse` | Streaming AI output | `content`, `loading`, `onCopy` |

---

## Section 6 — Page Blueprints

Structural wireframe description for each template type.

### 6.1 Landing page
```
┌─────────────────────────────────────────────┐
│ NAV: Logo | Links | CTA button              │
├─────────────────────────────────────────────┤
│ HERO: H1 (outcome-focused) | Subheading     │
│       Primary CTA | Secondary CTA           │
│       Hero visual (product screenshot/demo) │
├─────────────────────────────────────────────┤
│ SOCIAL PROOF: Logo bar (5-6 recognizable)   │
├─────────────────────────────────────────────┤
│ FEATURES: 3-column grid (icon+title+body)   │
├─────────────────────────────────────────────┤
│ HOW IT WORKS: 3-step horizontal flow        │
├─────────────────────────────────────────────┤
│ TESTIMONIALS: Cards with photo+quote+role   │
├─────────────────────────────────────────────┤
│ PRICING: Toggle annual/monthly, 3-tier grid │
├─────────────────────────────────────────────┤
│ FAQ: Accordion, 6-8 questions               │
├─────────────────────────────────────────────┤
│ FINAL CTA: Headline + primary CTA           │
├─────────────────────────────────────────────┤
│ FOOTER: Links | Legal | Social | Copyright  │
└─────────────────────────────────────────────┘
```

### 6.2 Dashboard (authenticated home)
```
┌───────────────┬─────────────────────────────┐
│  SIDEBAR      │  HEADER: Search | User menu  │
│  Logo         ├──────────────────────────────┤
│  Nav items    │  PAGE TITLE + quick actions  │
│  ─────────    ├──────────────────────────────┤
│  User/org     │  STAT CARDS (4 KPIs)         │
│               ├──────────────────────────────┤
│               │  PRIMARY CONTENT             │
│               │  (table / list / chart)      │
│               ├──────────────────────────────┤
│               │  SECONDARY CONTENT           │
│               │  (recent activity / feed)    │
└───────────────┴──────────────────────────────┘
```

### 6.3 Detail / entity view
```
┌──────────────────────────────────────────────┐
│  Breadcrumb: Dashboard > Entity > Name       │
│  Title + Status badge + Action buttons       │
├──────────────┬───────────────────────────────┤
│  TABS:       │  TAB CONTENT                  │
│  Overview    │  (varies by tab)              │
│  Analysis    │                               │
│  History     │                               │
│  Settings    │                               │
└──────────────┴───────────────────────────────┘
```

### 6.4 Settings page
```
┌───────────────┬──────────────────────────────┐
│  SETTINGS NAV │  SETTINGS CONTENT            │
│  Profile      │  Section title               │
│  Billing      │  ─────────────────           │
│  Team         │  Form fields                 │
│  Integrations │  (grouped by concern)        │
│  Security     │                              │
│  Danger zone  │  Save button                 │
└───────────────┴──────────────────────────────┘
```

---

## Section 7 — Technology Stack Recommendation

### 7.1 Recommended stack

| Layer | Technology | Rationale |
|---|---|---|
| **Frontend** | React 18 + TypeScript + Vite | Component model, ecosystem, type safety |
| **Styling** | Tailwind CSS + shadcn/ui | Rapid, consistent, accessible primitives |
| **State** | TanStack Query + Zustand | Server state separated from UI state |
| **Backend** | Node.js + Express (or FastAPI) | Team expertise, ecosystem, GCP Cloud Run fit |
| **Database** | PostgreSQL (Cloud SQL) | ACID, JSON support, pgvector for AI features |
| **Cache** | Redis (Memorystore) | Session, rate limit, LLM response cache |
| **Auth** | Firebase Auth | Managed, MFA, OAuth providers, custom claims |
| **Payments** | Stripe | Subscription lifecycle, webhooks, portal |
| **Email** | Resend | Developer-friendly, deliverability, React Email |
| **Hosting** | Firebase Hosting (FE) + Cloud Run (API) | CDN edge, auto-scaling, pay-per-use |
| **CI/CD** | GitHub Actions | Native PR integration, secrets, matrix builds |
| **Observability** | OpenTelemetry + Cloud Trace + Cloud Logging | Distributed tracing, structured logs |
| **IaC** | Terraform | Reproducible, version-controlled infra |

### 7.2 CMS consideration (if content-heavy)
- **No CMS**: markdown files in repo (blogs, docs) — simplest
- **Headless CMS**: Contentful / Sanity (for non-dev content editors)
- **DB-driven**: own CMS via admin panel (full control, more build)

---

## Section 8 — Performance Benchmarks

### 8.1 Core Web Vitals targets

| Metric | Target | Critical threshold |
|---|---|---|
| LCP (Largest Contentful Paint) | < 1.8s | > 4.0s = fail |
| INP (Interaction to Next Paint) | < 100ms | > 500ms = fail |
| CLS (Cumulative Layout Shift) | < 0.05 | > 0.25 = fail |
| FCP (First Contentful Paint) | < 1.0s | — |
| TTFB (Time to First Byte) | < 400ms | — |

### 8.2 Application performance targets

| Operation | Target P50 | Target P95 |
|---|---|---|
| Page load (cached) | < 500ms | < 1s |
| API response (simple read) | < 100ms | < 300ms |
| API response (DB aggregation) | < 300ms | < 800ms |
| AI inference (streaming start) | < 800ms | < 2s |
| File upload (< 10MB) | < 2s | < 5s |

### 8.3 Performance budget per page

| Asset type | Budget |
|---|---|
| Total JS (gzipped) | < 150KB initial, < 400KB total |
| CSS (gzipped) | < 20KB |
| Images | WebP/AVIF, lazy-loaded, `srcset` |
| Fonts | 2 max, `font-display: swap`, preloaded |

### 8.4 Implementation checklist
- [ ] Route-based code splitting (`React.lazy` + `Suspense`)
- [ ] Image optimization (`next/image` or equivalent)
- [ ] Critical CSS inlined, rest async
- [ ] Service worker for offline shell (PWA)
- [ ] CDN caching for static assets (1 year), API responses (short TTL)
- [ ] Database: EXPLAIN ANALYZE on all query patterns before launch

---

## Section 9 — SEO Framework

### 9.1 URL conventions
- All lowercase, kebab-case: `/real-estate-investment-analysis`
- Hierarchy = content hierarchy: `/blog/category/post-slug`
- Canonical tag on every page (handle trailing slash, www, protocol)
- `robots.txt`: allow public, disallow `/admin`, `/api`, `/auth`
- `sitemap.xml`: auto-generated, submitted to Google Search Console

### 9.2 Meta structure per page type

```typescript
// Landing page
title: "Primary Keyword — Brand Name | Secondary Benefit"  // < 60 chars
description: "Action verb + primary keyword + value prop + CTA"  // 120-160 chars
og:type: "website"

// Blog article
title: "Article Title — Blog | Brand"
description: First 155 chars of article intro
og:type: "article"
article:published_time, article:author

// App pages (no-index authenticated routes)
<meta name="robots" content="noindex, nofollow">
```

### 9.3 Schema markup strategy
```json
// Homepage: Organization + WebSite
{ "@type": "Organization", "name": "...", "url": "...", "sameAs": [...] }
{ "@type": "WebSite", "potentialAction": { "@type": "SearchAction" } }

// Pricing: Product + Offer
{ "@type": "Product", "offers": [{ "@type": "Offer", "price": "...", "priceCurrency": "USD" }] }

// Blog article: Article + BreadcrumbList
{ "@type": "Article", "headline": "...", "author": {...}, "datePublished": "..." }

// FAQ sections: FAQPage
{ "@type": "FAQPage", "mainEntity": [{ "@type": "Question", ... }] }
```

### 9.4 Core Web Vitals for SEO
Google's Page Experience signals directly impact rankings:
- Achieve "Good" status on all CWV (green in Search Console)
- HTTPS enforced, no mixed content
- Mobile-responsive (single responsive breakpoint, not separate m-dot)
- No intrusive interstitials blocking content on mobile

---

## Section 10 — Enterprise Architecture Considerations

For products at scale (> 10K users / multi-team / regulated):

### Domain-Driven Design
- Identify bounded contexts (e.g., Identity, Billing, Core Domain, Notifications)
- Each context owns its data — no cross-context DB joins in application code
- Anti-corruption layer between contexts (published language + adapters)
- Event-driven context integration: domain events via Pub/Sub

### API Governance
- API versioning policy: URI versioning (`/v2/`), support N-1 versions
- API changelog: public, semantic versioning, deprecation notices 90 days ahead
- API gateway: Cloud Endpoints or Apigee for enterprise — auth, rate limiting, analytics, quota

### Security at Enterprise Scale
- Zero-trust network model: all services verify caller identity, no implicit trust
- mTLS between internal Cloud Run services (via service mesh or Cloud Run auth)
- Penetration testing: annual external pentest + continuous automated scanning
- SOC 2 Type II readiness: logging, access control, incident response documentation

### Multi-Region / DR
- Active-passive multi-region: Cloud SQL with cross-region replica, Cloud Run in failover region
- RTO < 1 hour, RPO < 15 minutes for Tier-1 features
- Runbook: documented manual failover steps, tested quarterly

---

## Output format

```
=== Enterprise Technical Blueprint: <product> ===

CONTEXT
Site type: [SaaS / e-commerce / marketplace]
Audience:  [description]
Priorities: [Responsive / SEO / Performance / Scalability / Security]

S1  INFORMATION ARCHITECTURE  ──────────────────────
[sitemap, nav structure, URL conventions]

S2  USER JOURNEY MAPPING  ──────────────────────────
[3 conversion paths with drop-off points]

S3  DATA ARCHITECTURE  ─────────────────────────────
[entity model, indexing, caching, analytics]

S4  API SURFACE DEFINITION  ────────────────────────
[endpoints, auth, integrations, rate limits]

S5  COMPONENT INVENTORY (30+)  ─────────────────────
[grouped component table]

S6  PAGE BLUEPRINTS  ───────────────────────────────
[wireframe descriptions per template]

S7  TECHNOLOGY STACK  ──────────────────────────────
[full stack recommendation with rationale]

S8  PERFORMANCE BENCHMARKS  ────────────────────────
[CWV targets, API latency targets, budget]

S9  SEO FRAMEWORK  ─────────────────────────────────
[URL conventions, meta structure, schema markup]

S10 ENTERPRISE CONSIDERATIONS (if applicable)  ─────
[DDD, API governance, security, DR]

FIGMA MAKE HANDOFF NOTES
─────────────────────────
[Design tokens, spacing system, color palette refs, component naming conventions]
```
