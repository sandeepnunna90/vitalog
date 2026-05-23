# Vitalog — Pitch Deck

*Cohort demo — 2026-05-22*

---

## Slide 1 — Problem

**Headline:** Years of lab reports. No way to see the full picture.

**Body:**
- Patients managing chronic conditions accumulate reports across multiple labs, portals, and providers — with no unified view
- Each report is a snapshot. Trends — the thing that actually matters — are invisible across those snapshots
- Raw numbers come with reference ranges but no context for your personal history
- Patients walk into appointments not knowing what changed, what's trending, or what to ask

---

## Slide 2 — Solution

**Headline:** Vitalog turns scattered lab reports into a unified, intelligent health record — in seconds.

**Body:**
- Upload any lab report — PDF, photo, or scanned image → Vitalog extracts, normalises, and stores every biomarker
- Ask questions in plain language: *"How has my HbA1c changed over the last year?"*
- Get a citation-verified one-page summary, ready to share with your doctor
- Every number is traceable back to the original report — nothing fabricated

**One constraint, hard-coded into the architecture:** Vitalog gives you information, not advice. No diagnoses, no medication recommendations, no dietary prescriptions.

---

## Slide 3 — Product Demo

**Headline:** Live demo

**What the audience will see:**

1. Claude Desktop connects to Vitalog via OAuth — one browser login
2. Two real lab reports uploaded via URL
3. Pending taxonomy: a biomarker the system didn't recognise gets queued, resolved live, and immediately becomes queryable — no re-upload
4. Full biomarker list across both reports
5. Trends: HbA1c, cholesterol, kidney function, thyroid — with guideline target bands overlaid
6. Natural-language queries: *"How is my kidney function?"*, *"What do my thyroid levels say?"*
7. One-page health summary generated with citation-verified numerics
8. Exported as PDF
9. Guardrails: diet advice, medication questions, appointment booking — all declined cleanly

*Keep a backup: if network fails, walk through the demo_queries.md script verbally.*

---

## Slide 4 — Traction

**Headline:** Built, deployed, and working on real lab reports.

**What's real:**

- **Live on Render** — not a local notebook. Full OAuth 2.0 (RFC 7591 dynamic client registration), SSE transport, Docker-deployed
- **2 real lab reports processed** end-to-end during testing — 120 biomarker records extracted, normalised, and stored across 65+ unique biomarker types
- **6 MCP tools** fully wired: upload, list, trend, query, summary, export
- **84 biomarkers** across 9 chronic conditions (diabetes, hypertension, thyroid, lipids, kidney, liver, CBC, STI panel, urinalysis)
- **Zero hallucinated values** reach the output — two-mode citation verification is architecturally enforced, not a prompt instruction

**What's not here yet:** user interviews, pilots, revenue. This is a working prototype, not a shipped product.

---

## Slide 5 — Build Journey

**Headline:** 33 stories. 144 points. ~3 weeks. 30 shipped.

**The arc:**

| Week | What was built |
|---|---|
| Week 1 | Foundation: data model, Supabase persistence, 84-biomarker taxonomy, AI Gateway with 3-layer guardrails |
| Week 2 | Ingestion pipeline: AWS Textract OCR, vision-LLM fallback, document classifier, confidence-band routing. Normalization: alias lookup, unit conversion, duplicate detection, pending queue |
| Week 3 | Intelligence: trend engine, NLQ handler, observation generator, summary generator (Mode A citation-verified), PDF/markdown/JSON export. MCP server. Render deployment. OAuth 2.0 auth |

**Hard things that got built:**
- Two citation-verification modes (structured + parse-and-match) so the system can't hallucinate a biomarker value — even under adversarial prompting
- 20+ adversarial prompts trying to extract clinical advice — all blocked
- A pending taxonomy queue so unknown biomarker names are never silently discarded
- Real OAuth on a cloud-deployed MCP server — not just a localhost demo

**What the roadmap was built from:**
- Architecture doc written before any code
- Every story had acceptance criteria before implementation
- Automated PR review on every merge
- 47 code-review issues found and fixed before shipping

---

## Slide 6 — Team

**[YOUR NAME]**
**[YOUR ROLE / BACKGROUND]**
**[1–2 lines on relevant experience]**

Built as part of the 100x Engineers Applied AI Mastery cohort — solo, in ~3 weeks.

---

*Demo script: `docs/demo_queries.md`*
*Full technical review: `VITALOG_REVIEW.md`*
