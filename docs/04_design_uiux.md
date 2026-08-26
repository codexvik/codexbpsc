# UI/UX Design Doc: Bihar Exam Trust & Notification Platform (Phase 0)

## 1. Design Principles

1. **Trust over engagement.** No popups, no interstitials, no infinite-scroll ad blocks, no artificial friction between the user and their answer. Every incumbent in this space (Sarkari Result and its clones) optimizes for time-on-site because that's what ad revenue rewards. This product does the opposite on purpose — get the user their answer fast, and let that speed itself be the differentiator.
2. **Evidence, not claims.** Wherever the product states a fact that could be disputed (a date, a vacancy count, a result), show the source and the independent archive link inline, not buried in a footnote. Trust is built by making verification easy, not by asserting credibility.
3. **Mobile-first, low-bandwidth tolerant.** The demographic (semi-urban/rural Bihar, largely 25-34, mobile-primary) means the interface must load fast on average Indian mobile networks — minimal JS bundle weight, no heavy hero imagery, no auto-playing media.
4. **Bilingual by default.** Hindi and English toggle available on every page, matching BPSC's own site convention and the audience's actual reading preference. Default to Hindi for first-time mobile visitors given the target cohort skew; allow instant toggle, no page reload.
5. **Plain language over bureaucratic language.** Every extracted notice should be shown in a one-line plain-language summary first ("Your exam has been postponed to a new date — details below"), with the original official wording available as a secondary, expandable "official text" section — never hidden entirely, since the platform's credibility depends on being traceable back to the source.

## 2. Visual Direction

- **Palette**: calm, official-feeling blues/greens rather than the cluttered red/yellow/orange common to ad-driven aggregator sites in this space — the goal is to visually read as credible and institutional-adjacent, not as another SEO content farm.
- **Typography**: clean, high-legibility sans-serif for body text (important for Hindi/Devanagari rendering quality at small sizes on low-end devices); avoid decorative fonts entirely.
- **No ad placements in Phase 0.** This is a visual commitment as much as a business one — there should be nothing on the page that looks like or could be mistaken for a paid placement, reinforcing the neutrality position.
- **Status indicators**: use consistent, simple color coding for exam status (e.g., open/green, postponed/amber, closed/gray, result declared/blue) — repeated consistently across every exam card and detail page so users learn the pattern once.

## 3. Page-by-Page Specification

### 3.1 Home / Exam List Page
- Header: platform name/logo, Hindi/English toggle, no navigation clutter
- 3 exam cards (Phase 0 scope): each showing exam name, vacancy count, current status badge, next key date, a one-line "what changed most recently" snippet
- Tapping a card opens the Exam Detail Page
- No search bar needed yet in Phase 0 (only 3 exams) — defer full search/discovery to a later phase once the exam list grows

### 3.2 Exam Detail Page
Sections, top to bottom:
1. **Header block**: exam name, Advt. No., vacancy count, current status
2. **Key dates timeline**: application window, admit card, exam date, result — visually laid out as a simple horizontal or vertical timeline, with the current stage highlighted
3. **Eligibility Checker widget**: 3 simple inputs (degree, age, category) → instant verdict, shown inline without a page navigation
4. **Subscribe button**: prominent, opens a WhatsApp opt-in flow (deep-links to WhatsApp with a pre-filled opt-in message, or a phone-number entry field depending on chosen WhatsApp integration pattern)
5. **Notice feed**: reverse-chronological list of every detected change for this exam. Each entry shows:
   - Plain-language summary
   - Old value → new value (if a revision)
   - Timestamp of detection
   - A small "verified" link to the independent Wayback Machine archive of that notice
   - An expandable "see official text" toggle showing the original BPSC wording
6. **Result search** (once applicable for this exam): roll-number input field, instant yes/no + rank display

### 3.3 Eligibility Checker (component, embedded in 3.2)
- Step 1: select highest qualification/degree
- Step 2: enter age (or date of birth)
- Step 3: select reservation category (General/OBC/EWS/SC/ST, with a plain-language note on which certificate this maps to)
- Result: a clear, large-text "You are eligible" / "You are not eligible — reason: [specific criterion not met]" — never a vague or ambiguous verdict

### 3.4 Subscribe Flow
- Single tap from the exam detail page
- Minimal friction: phone number entry (if not using WhatsApp deep-link opt-in) + one confirmation step
- Immediate confirmation message sent via WhatsApp so the user knows it worked, without needing to return to the website
- Unsubscribe must be equally easy — a clear opt-out instruction included in every message sent, consistent with WhatsApp Business API policy requirements

### 3.5 Result Search
- Single input field: roll number
- Optional secondary field if needed for disambiguation (e.g., exam phase/session)
- Result displayed instantly: status (qualified/not qualified/pending), rank if applicable, and a direct link to the official source PDF for the user's own records

## 4. Deferred to Later Phases (do not build in Phase 0)

- Public Integrity Scorecard page (Phase 1)
- Open-ended chatbot/Q&A interface (Phase 2)
- Multi-exam search and filtering across bodies beyond BPSC (Phase 3)
- Any account/login system beyond WhatsApp opt-in
- Any payment or subscription-tier UI

## 5. Accessibility Notes

- Sufficient color contrast for outdoor mobile viewing (common usage context for this demographic)
- Avoid relying on color alone for status indicators — pair with text labels
- Keep tap targets large enough for one-handed mobile use
- Test Devanagari rendering specifically on lower-end Android devices before launch, given the target audience's likely device profile
