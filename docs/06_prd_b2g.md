# PRD (B2G Version): Bihar Exam Trust & Verification Infrastructure

## 1. Mission
Build a detection-verification-notification engine for state exam bodies, proven first on BPSC, that a state government can adopt, fund, or formally recognize as trusted civic infrastructure — with a free, high-trust citizen product as both the delivery mechanism and the evidence base.

## 2. Vision
Two audiences, one engine:
- **Citizens** get notified the moment something changes, with every claim traceable to an independent, verifiable record.
- **Government stakeholders** get visibility into how their own exam body is performing — timeliness, complaint patterns, public trust signals — as a factual, non-adversarial dashboard, not an accusation.

## 3. Problem Statement (Dual-Audience)

**For citizens**: Bihar exam aspirants depend on cluttered, ad-optimized aggregators or unverified WhatsApp forwards for time-critical information, while the official source publishes for compliance, not usability, and has a documented pattern of dismissing complaints.

**For government**: BPSC and similar bodies have no visibility tool of their own into how their communication is landing — no data on how many candidates are affected by a given change, no independent record they can point to when disputing a complaint, and no low-cost way to demonstrate improved transparency to a public increasingly primed to distrust exam bodies after the 2026 national exam-integrity crisis.

## 4. Target Users

**Primary citizen persona**: BPSC Teacher Recruitment (TRE) aspirant — see original PRD for full detail; unchanged.

**New: Government stakeholder persona** — a Bihar DIT department official or BPSC administrator evaluating whether to engage with, adopt, or fund this system. Needs: clear evidence of citizen value delivered, a low-risk way to associate with it (no political cost), and eventually operational visibility into how it's performing.

## 5. User Stories

### Citizen-facing (Phase 0 — unchanged from original PRD)
| # | As a... | I want to... | So that... |
|---|---|---|---|
| 1 | Candidate | See active BPSC exams with key stats | I know what's open without hunting |
| 2 | Candidate | Get an instant eligibility verdict | I don't waste prep time on posts I can't apply to |
| 3 | Candidate | Subscribe via WhatsApp | I'm notified without checking manually |
| 4 | Candidate | See a notice feed with visible diffs | I can trust what changed and when |
| 5 | Candidate | Search my result by roll number | I get an instant answer, not a PDF hunt |
| 6 | Candidate | Know a notice is independently archived | I don't have to take the platform's word for it |

### Government-facing (new, phases in from Phase 1 onward)
| # | As a... | I want to... | So that... |
|---|---|---|---|
| 7 | DIT/BPSC official | See engagement and reach metrics for my exam body | I can evaluate whether this system is worth formally supporting |
| 8 | DIT/BPSC official | See a factual timeliness record (notice published vs. detected vs. delivered) | I have independent data, not just candidate complaints, to assess my own communication performance |
| 9 | DIT/BPSC official | Optionally push verified notices directly through the platform | I control the narrative on volatile changes instead of it being scraped after the fact |
| 10 | State government evaluating adoption | See a working, evidenced case study from Bihar | I can justify budget/political capital to bring this to my own state |

## 6. Phase 0 Scope (Citizen Layer — Unchanged, Still the Foundation)

Same as original PRD: 3 live BPSC exams, exam detail pages, eligibility checker, notice feed with diffs, WhatsApp subscribe, roll-number search, backend detection engine, Wayback Machine archival on every capture.

**One architectural addition required even at Phase 0**: the detection/extraction pipeline must be built config-driven per source (see Tech Architecture doc) from the start, not hardcoded to BPSC — this is cheap now and expensive to retrofit once a second state is in scope.

## 7. Phase 1+ Scope — Government-Facing Layer

- **Timeliness dashboard**: for each tracked exam, show official-publish-time vs. detection-time vs. delivery-time, and complaint volume/pattern by category — internal-facing initially, shareable with BPSC once a relationship exists
- **Public Integrity Scorecard**: the citizen-facing version of the same underlying data — factual, not adversarial
- **Verified-source pathway (future, dependent on relationship)**: an intake mechanism allowing BPSC to push notices directly/faster once trust is established, reducing reliance on scraping entirely for that source

## 8. Success Criteria

**Citizen layer (Phase 0 pilot, unchanged)**: speed advantage, activation, retention, zero-error accuracy gate, organic growth ratio — see original PRD for detail.

**Government layer (new, tracked from Phase 1)**:
- Number of substantive government stakeholder conversations secured
- Whether Bihar's Integrity Scorecard/timeliness data is ever referenced or acted on by BPSC or DIT publicly or privately
- Progress toward any formal recognition, data-sharing agreement, or funding conversation
- Case-study readiness: can Bihar's results be credibly presented to a second state's DIT department

## 9. Roadmap

| Phase | Citizen-facing | Government-facing | Architecture requirement |
|---|---|---|---|
| 0 | 3 exams, search, notice feed, WhatsApp subscribe | None yet — this phase is the evidence base | Config-driven ingestion from day one |
| 1 | Admit-card pre-check, full cycle live | First Integrity Scorecard, first pitch to Bihar DIT/BPSC using Phase 0 evidence | Internal timeliness dashboard |
| 2 | Moderated Q&A, rumor-detection responder | Pursue formal recognition or data-sharing relationship with Bihar | Verified-source intake pathway (if relationship permits) |
| 3 | Multi-exam bundling within Bihar | Approach second state's DIT department with Bihar as case study | Prove config-driven onboarding of a second state source |

## 10. Key Risks & Assumptions

- Same technical/accuracy risks as the original PRD (human review gate on high-stakes extraction, WhatsApp API lead time) — unchanged.
- **New risk**: government engagement is a relationship-driven, not metrics-driven, sales motion — strong Phase 0 metrics do not guarantee Phase 1 government interest; budget for this being slower and less predictable than the product roadmap itself.
- **New assumption**: Bihar's own precedent (RTPS/ServicePlus as government-funded, NIC-built civic infrastructure) means the concept of government-funded citizen-service tooling is not a hard sell in principle — the harder sell is trusting a new, unproven external party with it.
