---
name: form-cro
description: When the user wants to optimize any form that is NOT signup/registration — lead capture, contact, demo request, application, survey, or checkout forms; "form friction," "form completion rate," "form abandonment," "too many fields," "nobody fills out our form." For signup/registration forms, see signup-flow-cro. For popups containing forms, see popup-cro.
category: marketing
tier: on-demand
---

# Form CRO

Maximize form completion rates while capturing the data that matters.

## Initial Assessment

**Product context:** If `.agents/product-marketing-context.md` exists (or `.claude/product-marketing-context.md` in older setups), read it first and tailor output to it; only ask for what it doesn't cover.

Before recommending, identify:

1. **Form Type** — lead capture (gated content, newsletter), contact, demo/sales request, application, survey/feedback, checkout, quote request
2. **Current State** — field count, current completion rate, mobile vs. desktop split, where users abandon
3. **Business Context** — what happens with submissions, which fields are actually used in follow-up, compliance/legal requirements

---

## Core Principles

### 1. Every Field Has a Cost
Each field reduces completion. Rule of thumb: 3 fields = baseline; 4-6 fields = 10-25% reduction; 7+ fields = 25-50%+ reduction. For each field ask: Is it absolutely necessary before we can help them? Can we get it another way? Can we ask later?

### 2. Value Must Exceed Effort
Clear value proposition above the form; make what they get obvious; reduce perceived effort (field count, labels).

### 3. Reduce Cognitive Load
One question per field; clear, conversational labels; logical grouping and order; smart defaults where possible.

---

## Field-by-Field Optimization

### Email
Single field, no confirmation; inline validation; typo detection (did you mean gmail.com?); proper mobile keyboard.

### Name
Test single "Name" vs. First/Last — single field reduces friction; split only if personalization requires it.

### Phone Number
Make optional if possible; if required, explain why; auto-format as they type; handle country codes.

### Company/Organization
Auto-suggest for faster entry; enrich after submission (Clearbit, etc.); consider inferring from email domain.

### Job Title/Role
Dropdown if categories matter; free text if wide variation; consider making optional.

### Message/Comments (Free Text)
Optional; reasonable character guidance; expand on focus.

### Dropdown Selects
"Select one..." placeholder; searchable if many options; radio buttons if < 5 options; "Other" option with text field.

### Checkboxes (Multi-select)
Clear, parallel labels; reasonable option count; consider "Select all that apply" instruction.

---

## Form Layout Optimization

### Field Order
Start with easiest fields (name, email); build commitment before asking more; sensitive fields last (phone, company size); logical grouping if many fields.

### Labels and Placeholders
Labels: keep visible (not just placeholder) — placeholders disappear when typing, leaving users unsure what they're filling in. Placeholders: examples, not labels. Help text: only when genuinely helpful.

**Good:**
```
Email
[name@company.com]
```

**Bad:**
```
[Enter your email address]  ← Disappears on focus
```

### Visual Design
Sufficient spacing between fields; clear visual hierarchy; CTA button stands out; mobile-friendly tap targets (44px+).

### Single Column vs. Multi-Column
Single column: higher completion, mobile-friendly. Multi-column: only for short related fields (First/Last name). When in doubt, single column.

---

## Multi-Step Forms

### When to Use
More than 5-6 fields; logically distinct sections; conditional paths based on answers; complex forms (applications, quotes).

### Best Practices
Progress indicator (step X of Y); start easy, end with sensitive; one topic per step; allow back navigation; save progress (don't lose data on refresh); clear indication of required vs. optional.

### Progressive Commitment Pattern
1. Low-friction start (just email) → 2. More detail (name, company) → 3. Qualifying questions → 4. Contact preferences

---

## Error Handling

### Inline Validation
Validate as they move to the next field, not aggressively while typing; clear visual indicators (green check, red border).

### Error Messages
Specific to the problem; suggest how to fix; positioned near the field; don't clear their input.

**Good:** "Please enter a valid email address (e.g., name@company.com)"
**Bad:** "Invalid input"

### On Submit
Focus on first error field; summarize errors if multiple; preserve all entered data; don't clear the form on error.

---

## Submit Button Optimization

### Button Copy
Weak: "Submit" | "Send"
Strong: "[Action] + [What they get]" — "Get My Free Quote," "Download the Guide," "Request Demo," "Send Message," "Start Free Trial"

### Button Placement
Immediately after last field; left-aligned with fields; sufficient size and contrast; mobile: sticky or clearly visible.

### Post-Submit States
Loading (disable button, show spinner); success confirmation (clear next steps); error handling (clear message, focus on issue).

---

## Trust and Friction Reduction

### Near the Form
Privacy statement ("We'll never share your info"); security badges if collecting sensitive data; testimonial or social proof; expected response time.

### Reducing Perceived Effort
"Takes 30 seconds"; field count indicator; remove visual clutter; generous white space.

### Addressing Objections
"No spam, unsubscribe anytime" · "We won't share your number" · "No credit card required"

---

## Form Types: Specific Guidance

### Lead Capture (Gated Content)
Minimum viable fields (often just email); clear value proposition for what they get; consider enrichment questions post-download; test email-only vs. email + name.

### Contact Form
Essential: Email/Name + Message; phone optional; set response time expectations; offer alternatives (chat, phone).

### Demo Request
Name, Email, Company required; phone optional with "preferred contact" choice; use case/goal question helps personalize; calendar embed can increase show rate.

### Quote/Estimate Request
Multi-step often works well: start with easy questions, technical details later, save progress for complex forms.

### Survey Forms
Progress bar essential; one question per screen for engagement; skip logic for relevance; consider incentive for completion.

---

## Mobile Optimization

Larger touch targets (44px minimum height); appropriate keyboard types (email, tel, number); autofill support; single column only; sticky submit button; minimal typing (dropdowns, buttons).

---

## Measurement

### Key Metrics
**Form start rate** (page views → started); **completion rate** (started → submitted); **field drop-off** (which fields lose people); **error rate** by field; **time to complete** (total and by field); **mobile vs. desktop** completion by device.

### What to Track
Form views, first field focus, each field completion, errors by field, submit attempts, successful submissions.

---

## Output Format

### Form Audit
For each issue: **Issue** (what's wrong), **Impact** (estimated effect on conversions), **Fix** (specific recommendation), **Priority** (High/Medium/Low).

### Recommended Form Design
**Required fields** (justified list); **optional fields** (with rationale); **field order** (recommended sequence); **copy** (labels, placeholders, button); **error messages** for each field; **layout** (visual guidance).

### Test Hypotheses
Ideas to A/B test with expected outcomes

---

## Experiment Ideas

### Form Structure Experiments

**Layout & Flow** — single-step vs. multi-step with progress bar; 1-column vs. 2-column layout; embedded on page vs. separate page; vertical vs. horizontal field alignment; form above fold vs. after content.

**Field Optimization** — reduce to minimum viable fields; add/remove phone number field; add/remove company/organization field; required vs. optional field balance; field enrichment to auto-fill known data; hide fields for returning/known visitors.

**Smart Forms** — real-time validation for emails and phone numbers; progressive profiling (ask more over time); conditional fields based on earlier answers; auto-suggest for company names.

### Copy & Design Experiments

**Labels & Microcopy** — field label clarity and length; placeholder text; help text show vs. hide vs. on-hover; error message tone (friendly vs. direct).

**CTAs & Buttons** — button text ("Submit" vs. "Get My Quote" vs. specific action); color and size; placement relative to fields.

**Trust Elements** — privacy assurance near form; trust badges next to submit; testimonial near form; expected response time display.

### Form Type-Specific Experiments

**Demo Request** — with/without phone requirement; "preferred contact method" choice; "What's your biggest challenge?" question; calendar embed vs. form submission.

**Lead Capture** — email-only vs. email + name; value proposition messaging above form; gated vs. ungated content; post-submission enrichment questions.

**Contact** — department/topic routing dropdown; with/without message field requirement; alternative contact methods (chat, phone); expected response time messaging.

### Mobile & UX Experiments

Larger touch targets; keyboard types by field; sticky submit button; auto-focus first field on page load; form container styling (card vs. minimal).

---

## Task-Specific Questions

1. What's your current form completion rate?
2. Do you have field-level analytics?
3. What happens with the data after submission?
4. Which fields are actually used in follow-up?
5. Are there compliance/legal requirements?
6. What's the mobile vs. desktop split?

---

## Related Skills

- **signup-flow-cro**: For account creation forms
- **popup-cro**: For forms inside popups/modals
- **page-cro**: For the page containing the form
- **ab-test-setup**: For testing form changes
