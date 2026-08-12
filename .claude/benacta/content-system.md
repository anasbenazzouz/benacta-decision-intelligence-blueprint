# BENACTA — Content System

> Binding doctrine, derived from Architecture Note #001 and the master brief's editorial requirements. Consult before writing the README, the Blueprint PDF, app copy, or any public text.

## 1. Executive-first, always

A CEO or CFO must benefit without looking at code. The default experience never leads with embeddings, vectors, prompts, JSON, RAG internals, Python classes or API payloads. It answers, in order:

1. **WHAT HAPPENED?**
2. **WHY?**
3. **WHAT REQUIRES ATTENTION?**
4. **WHAT ARE THE POSSIBLE NEXT STEPS?**
5. **WHAT EVIDENCE SUPPORTS THIS?**
6. **WHO APPROVED THIS?**

## 2. Two-layer language

Expose an executive phrasing and a technical phrasing wherever possible. Canonical pairs:

| Executive | Technical |
|---|---|
| The system finds the policy or operational note that explains the movement. | Retrieval identifies relevant document sections. |
| Every number remains reproducible. | Metrics are calculated deterministically in Python. |
| A controller remains accountable for published commentary. | Human-in-the-loop approval state machine. |

The project must demonstrate sophisticated architecture **without forcing executives to learn AI engineering vocabulary**.

## 3. The Note #001 editorial pattern (reuse this structure)

1. Header band: BA monogram + publication label in tracked caps ("ARCHITECTURE NOTE · N° 001").
2. Serif display thesis; second line italic champagne.
3. Numbered sections **01 / 02 / 03 …** in tracked caps with gold numerals.
4. Current-state ✗ vs target-state ✓ tables; each target row tagged with its mechanism in italic (*data pipeline · deterministic engine · LLM + evals · audit trail · governed copilot*).
5. Layered architecture diagram with an explicit dashed **trust boundary**, side annotations stating **business outcomes** (not tech): "no more re-keying" · "every figure computed, none invented" · "commentary in hours, not days" · "approved before it ships" · "answers at the speed of questions".
6. A chain line + motto as a closing statement.
7. Principles in a numbered grid (Roman numerals).
8. Sourced benchmarks as KPI blocks.
9. Dark footer band: CTA + author identity + logo.

## 4. README rules (executive-first)

- First screen: **no installation commands.** Open with the BENACTA block, the thesis, and the doctrine (see `positioning.md` slogan hierarchy).
- Sequence: positioning → thesis → business problem → one concrete business example (the €4.72M/€5.00M revenue story with TRUTH/CONTEXT/AI INTERPRETATION/EVIDENCE/HUMAN CONTROL/ACTION blocks) → business architecture → trust boundary → what the demo shows → screenshots → technical architecture → quick start → repo structure → tests → limitations → roadmap → CTA.
- Two architecture views (Mermaid where useful): business view (Enterprise Data → … → Outcome) and technical view (CSV/ERP mock → … → Decision log/audit).
- The README and the PDF must tell **the same story**.

## 5. Blueprint PDF rules

`docs/BENACTA_Controlled_Intelligence_Blueprint.pdf` — 8–10 pages, premium LinkedIn lead magnet, useful even if the reader never opens GitHub. Designed HTML/CSS source retained at `docs/controlled-intelligence-blueprint.html`. **Page architecture: governed by `docs/pdf-storyboard.md` (Phase 8), which supersedes the master brief §27 plan** — §27 was explicitly a starting hypothesis; the storyboard records every deviation and its rationale (trust-boundary page added, standalone reference-implementation page merged into the close, dashboard-maturity ladder folded into pages 2/8).

Quality bar: premium whitespace · strong hierarchy · restrained color · brand typography · consistent section numbering · vector diagrams · no clipped text, overflow, awkward page breaks, rasterized small type, generic AI imagery, or template feel. **Mandatory visual QA loop:** render → inspect every page → compare to charter and Note #001 → fix → re-render → re-inspect. Never declare the PDF complete without it.

## 6. Evidence and claims

- **Zero invented statistics.** Only the four sourced Note #001 benchmarks, with citations: 58 % (Gartner, CFO & Finance AI Survey, Sept. 2024) · 42 % (McKinsey & Company) · −45 % cost gap (PwC, Finance Effectiveness Benchmarking 2024) · ≤ 5 days close (APQC). Derived figures keep the label **"illustrative"**.
- No unsupported factual claims, no invented benchmark claims, no overclaiming autonomous AI, nothing that falsely implies production readiness.
- AI-generated content is always marked as such, with the human control state visible ("AI-generated interpretation · Controller approval required").

## 7. App copy rules

- KPI presentation: metric name, Actual, Budget, Variance €, Variance % — plain executive labels.
- Attention items ranked HIGH / MEDIUM / LOW with a business message, not a rule dump.
- Next steps labeled **Suggested follow-up / Decision option / Question to investigate** — never "AI Decision".
- Evidence blocks list exact business sources (✓ General Ledger · ✓ FY26 Budget · ✓ Project Milestone Note).
- Decision log shows issue, interpretation, reviewer, decision/next step, owner, status, timestamp.

## 8. Demo narrative (fictional, coherent — never random)

Mid-sized industrial / project-based company, Euros, Monthly Performance Review:
- Revenue below plan: two project milestones shifted from July into August (Actual €4.72M · Budget €5.00M · −€280k · −5.6 % · HIGH).
- Travel above budget: unplanned customer workshops.
- External contractors above budget: temporary engineering capacity constraints.
- Gross margin partly protected by lower procurement costs.
