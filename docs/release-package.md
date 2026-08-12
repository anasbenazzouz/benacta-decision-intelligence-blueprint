# BENACTA — Release Package

> Phase 12 deliverable. The single operational document for launching the
> BENACTA Decision Intelligence Blueprint publicly. Governing doctrine:
> `CLAUDE.md`, `.claude/benacta/*`. Nothing here changes the product, the
> architecture, or the Blueprint's story — it packages what already exists for
> a controlled release. Companion document: `docs/release-checklist.md`
> (execution checkboxes). Nothing in this document has been published,
> pushed, or made public by writing it.

---

## 1. The release funnel

```text
LINKEDIN
Architecture Note #001
        |
        v
Comment "BLUEPRINT"
        |
        v
BENACTA Controlled Intelligence Blueprint
Executive PDF
        |
        +--------------+
        v              v
LIVE DECISION       GITHUB
COCKPIT             REFERENCE
                     IMPLEMENTATION
        |              |
        +------+-------+
               v
            BENACTA
     Conversation / Opportunity
```

Four public assets, four distinct jobs. Each is complete on its own; none
duplicates another's content wholesale — a reader who only ever sees one
still gets something whole, and a reader who follows the whole funnel gets
depth, not repetition.

| Asset | Role | What it proves | What it deliberately withholds |
|---|---|---|---|
| **Architecture Note #001** | **ATTENTION** | There is a real point of view: AI should not own enterprise numbers. | The mechanism. It states the thesis, not the architecture behind it. |
| **Executive Blueprint (PDF)** | **UNDERSTANDING** | The general Decision Intelligence doctrine, argued end to end, with one worked example. | Code, screenshots, raw payloads. It is designed to stand alone without GitHub. |
| **Live Decision Cockpit** | **EXPERIENCE** | The architecture is not a slide — a reader can click "Trace to source" and watch a claim reconcile, or send a draft back for revision and watch it work. | Architecture depth; the cockpit doesn't explain itself in prose, it just runs. |
| **GitHub reference implementation** | **PROOF** | The trust boundary is enforced, not asserted — `test_financial_truth_is_independent_from_llm` is code a skeptical reader can run. | Executive framing; this is the layer for a reader who wants to verify, not be persuaded. |

The funnel converges once, deliberately: both doors at the bottom (cockpit,
GitHub) lead to the same place — a conversation with BENACTA — but they are
different doors for different readers (per `positioning.md`'s two-lane CTA:
decision-makers vs. architects), not a single generic "contact us."

---

## 2. LinkedIn CTA — Architecture Note #001

**Final wording:**

> Want the architecture behind this? Comment **BLUEPRINT** and I'll send you
> the ten-page companion — how to bring AI into a decision process without
> giving up control of the truth.

Notes:
- One sentence of value, one instruction, no urgency language, no emoji, no
  "🔥 don't miss this." Matches `positioning.md`'s brand character
  (premium · editorial · understated) and the anti-pattern against hard-sell
  CTAs (`anti-patterns.md`).
- Deliberately restates the *value* of the Blueprint ("how to bring AI into a
  decision process without giving up control of the truth" — an echo of the
  cover subhead, not the tagline) rather than just naming the artifact, so
  the ask reads as an offer, not a mechanic.
- Keep this as the **only** CTA on the Note itself — no second slogan, per
  the slogan surface discipline in `positioning.md`.

---

## 3. BLUEPRINT comment response — delivery workflow

Trigger: someone comments `BLUEPRINT` on Architecture Note #001. Response
channel: LinkedIn DM, sent manually (no automation infrastructure — V1 has
no marketing stack, and doctrine says not to build one for its own sake).

Send the PDF as an attachment or a direct link (once hosted); do not require
an email-gate form — the whole point of `DEMO_MODE=true` and a public repo is
low friction. Pick the version by what you know about the commenter; default
to **Version A** if you know nothing about them.

### Version A — Short (fast DM, ~3 sentences)

> Thanks for the interest — here's the BENACTA Controlled Intelligence
> Blueprint: [PDF link]. It's the broader idea behind the Note: how to bring
> AI into a decision process without letting it own the numbers. Happy to
> talk if a decision workflow at your company could use this.

### Version B — Warm (~4–6 sentences, relevant target audience)

> Thanks for commenting — here's the BENACTA Controlled Intelligence
> Blueprint: [PDF link]. It's the ten-page version of the thesis in the Note:
> governed data becomes business objects, deterministic truth, context, AI
> interpretation, human judgment and owned action — with one page walking a
> real (fictional) monthly variance through the whole chain.
> There's also a working reference implementation on GitHub if you want to
> see the trust boundary enforced in code rather than just described: [repo
> link]. No pressure either way — if a decision process at your company feels
> like a fit for this, I'd be glad to talk it through.

### Version C — Executive (CFO / CIO / Finance Director / Transformation Director / senior exec)

> Thank you for your interest in the architecture behind the Note. Attached
> is the BENACTA Controlled Intelligence Blueprint — a ten-page executive
> read on how to introduce AI into a decision process without surrendering
> control of the truth, the trust boundary that makes that possible, and one
> worked example end to end.
>
> A live version of the cockpit described on page 7 [is available at
> DEMO_URL / will be available shortly] if you'd like to see it running
> rather than read about it, and the reference implementation is public on
> GitHub for anyone on your team who wants to verify the architecture in
> code: [repo link].
>
> I'm not looking to sell you anything in this message — if the approach is
> relevant to a decision process your team owns, I'd welcome a short
> conversation about where it might apply.

Common rule across all three: never open with "Hi! 👋", never use
exclamation marks, never claim the reader will be "blown away." The Blueprint
and the cockpit do the persuading; the message's job is delivery.

---

## 4. Follow-up message (send days later, only if silent)

Send only if: the Blueprint was delivered **and** there has been no reply or
further engagement. Do not chase; send once.

> Curious whether the Blueprint landed — no need to reply if it didn't
> resonate. If it did: which recurring decision process at your company would
> benefit most from this kind of architecture — the monthly close, a demand
> or capacity review, something else? Happy to think through it with you,
> even informally.

Why this wording: it asks a question the reader can answer from their own
world (not "did you read my PDF"), it explicitly gives permission to not
reply (lowers pressure, matches the brand's restraint), and the question
itself does useful work — the answer is qualification, in the reader's own
language, for BENACTA's next move.

---

## 5. GitHub metadata

**Repository:** `anasbenazzouz/benacta-decision-intelligence-blueprint`
(confirmed against `git remote -v` — matches).

### Description

Doctrine already locks this exact string in `.claude/benacta/vocabulary.md`
§"Naming constants" — it is not free text to be reworded on a whim:

> A reference implementation for governed AI-native decision systems — where
> code computes, AI explains, and humans decide.

The version proposed in the Phase 12 brief drops the leading "A". Recommend
keeping the doctrine-locked wording exactly (with the article) — it reads
better as a sentence and is already the string of record. No materially
better alternative surfaced; not changing it.

### Topics (reviewed and finalized)

Kept nine of the ten candidates, added one, for these reasons:

| Topic | Keep / change | Why |
|---|---|---|
| `decision-intelligence` | keep | Core positioning term, real GitHub topic |
| `enterprise-ai` | keep | Core positioning term |
| `ai-engineering` | keep | Matches the author-line discipline (AI Engineering) |
| `enterprise-architecture` | keep | Speaks to the CIO/EA audience directly |
| `finance-ai` | keep | Accurate — Finance is the proven reference vertical |
| `human-in-the-loop` | keep | Core doctrine term, established GitHub topic |
| `explainable-ai` | keep | Matches "AI explains," real search term |
| `decision-support` | keep | Distinct enough from decision-intelligence to add reach |
| `streamlit` / `python` | keep | Exact tech-stack tags, high discoverability |
| `reference-implementation` | **add** | The repo's own self-description (`vocabulary.md`) — currently missing as a topic despite being the primary framing |

**Final set (11):** `decision-intelligence`, `enterprise-ai`,
`ai-engineering`, `enterprise-architecture`, `finance-ai`,
`human-in-the-loop`, `explainable-ai`, `decision-support`,
`reference-implementation`, `streamlit`, `python`.

Not modified in GitHub — recommendation only, per instruction.

---

## 6. GitHub Release (prepared, not published)

**Tag / version:** `v0.1.0`
**Title:** `BENACTA Decision Intelligence Blueprint v0.1`

**Body:**

```markdown
## What this is

A working reference implementation for governed AI-native decision systems.
Finance — a Monthly Performance Review — is the first vertical slice;
BENACTA is broader than Finance. It shows governed enterprise data moving
through business meaning, deterministic truth, contextual interpretation,
human judgment and owned action, without the LLM ever becoming the system of
record.

## What it demonstrates

- **Business Semantic Layer** (`src/domain.py`) — raw ledger rows mapped onto
  governed business objects; rows that disagree with the model are rejected,
  not silently aggregated.
- **Deterministic Finance Engine** (`src/finance_engine.py`) — every figure
  (actual, budget, variance, variance %) computed by code, once, versioned.
- **Control Engine** (`src/control_engine.py`) — transparent materiality
  rules, direction-aware, citable against written policy.
- **Context Retrieval** (`src/retrieval.py`) — transparent keyword scoring
  with document, section, snippet and score always visible. No vector
  database.
- **AI / Demo Interpretation** (`src/commentary.py`) — the only module
  permitted to talk to an LLM, and the only one below the trust boundary. Runs
  fully on controlled templates with `DEMO_MODE=true` and no API key.
- **Human Review** (`src/approval.py`) — a strict approval state machine;
  nothing publishes without a named controller's sign-off; rejection is a
  designed path.
- **Decision / Action** (`src/decision_log.py`) — an accepted issue becomes an
  owner, a next step, a status — insight without action is incomplete.
- **Audit Trail** (`src/audit.py`) — every step logged; any statement on
  screen traces back to its source.

## Why it matters

**CODE COMPUTES. AI EXPLAINS. HUMANS DECIDE.** The trust boundary is this
project's central claim, and it is enforced, not just asserted:
`tests/test_ai_independence.py::test_financial_truth_is_independent_from_llm`
re-imports the truth layer with every AI import path blocked and proves the
figures, controls and materiality are byte-identical to a normal run. If the
AI layer disappeared tomorrow, every number in this system would still be
correct — because none of it was ever the AI's to compute.

## Demo Mode

`DEMO_MODE=true` is the default and the supported public configuration. The
entire application — cockpit, controls, retrieval, review workflow, audit
trail — runs with **no API key**. Commentary is produced from controlled,
evidence-based templates rather than a live model call.

```bash
pip install -r requirements.txt
cp .env.example .env
pytest -q                 # 155 passed, no API key needed
streamlit run app.py
```

## Scope

This is a reference implementation, not production enterprise software: one
use case, one fictional company, fictional data end to end, no real
integration, read-only by design, retrieval by transparent keyword scoring
rather than a production search/RAG stack. See the README's Limitations
section for the complete, honest list.

## Assets

- Executive Blueprint (PDF): `docs/BENACTA_Controlled_Intelligence_Blueprint.pdf`
- Live Decision Cockpit: [URL once deployed]
- `README.md` — start here
- `docs/architecture.md` — technical architecture and data contracts
- `docs/implementation-guide.md` — how to run, extend and adapt it
```

Not published. Prepared as text only, per instruction.

---

## 7. Screenshot plan (final five)

Manual capture only — no synthetic or mocked images (per doctrine: "Do not
create fake screenshots"). Capture against a running `DEMO_MODE=true`
instance, browser at 100% zoom, light theme (the app is pinned to the
charter light theme regardless of OS setting — see `.streamlit/config.toml`).
Save as PNG under `assets/generated/screenshots/`.

### 01 — Executive overview

- **NAME:** `01-executive-decision-cockpit.png`
- **VIEW:** Executive Decision Cockpit (default view), top of page, no
  selection made yet.
- **STATE:** Fresh session (`seed_demo_state` already applied — travel issue
  shows ACTION REQUIRED in the log). KPI band showing Revenue, Gross Margin,
  Operating Expenses, EBITDA with actual/budget/variance.
- **VIEWPORT:** 1600 × 1000 (matches the QA baseline in `docs/ui-qa.md`).
- **CROP:** Hero band (status rail, "governed data · current") through the
  full KPI band and into the top of the Attention list. Stop before any
  dialog or expander.
- **MESSAGE:** This is a Decision System, not a chatbot — live status,
  computed KPIs, a ranked attention list, all above the fold.

### 02 — Issue requiring attention

- **NAME:** `02-attention-revenue-issue.png`
- **VIEW:** Executive Decision Cockpit, Attention list expanded, Revenue row
  selected/highlighted (HIGH severity).
- **STATE:** Revenue issue selected (−€280,000 / −5.6%, HIGH), before opening
  the trace dialog. The ranked list (5 items, HIGH → MEDIUM) should be fully
  visible with Revenue's row visually distinguished as selected.
- **VIEWPORT:** 1600 × 1000.
- **CROP:** The Attention list in full plus the top of the selected-issue
  detail panel (What happened / Why headline). Do not include the Decision
  Log at the bottom.
- **MESSAGE:** Governed truth ranks what matters — HIGH before MEDIUM,
  unfavorable before favorable at equal severity — before any AI touches it.

### 03 — Evidence + interpretation

- **NAME:** `03-evidence-and-interpretation.png`
- **VIEW:** Executive Decision Cockpit, Revenue issue detail, scrolled to the
  Evidence cards and the AI-generated interpretation block.
- **STATE:** Revenue issue, evidence cards visible (FY26 Forecast Assumptions,
  Management Commentary, Milestone Register — in true retrieval-ranked
  order), interpretation block below showing "AI-generated interpretation ·
  Controller approval required" label and the root-cause block beneath it at
  its correct (larger) visual weight.
- **VIEWPORT:** 1600 × 1000.
- **CROP:** Evidence section through the interpretation block and its label.
  Include the root-cause title/impact line so the visual hierarchy (root
  cause outranking the AI prose) is visible in the crop, not just described.
- **MESSAGE:** Evidence is quoted, sourced and scored — not asserted — and
  the AI's own output is visibly subordinate to the computed root cause.

### 04 — Human review + next action

- **NAME:** `04-human-review-and-action.png`
- **VIEW:** Executive Decision Cockpit, Revenue issue, the human-control
  workflow stepper and the action-assignment form.
- **STATE:** Mid-workflow — either the "Send for controller review" /
  "Approve" / "Request revision" controls visible with the stepper on
  AI DRAFT or CONTROLLER REVIEW, **or** (preferred) just after approval, with
  the owner/next-step assignment form visible and pre-filled with the
  "Owner suggestion" text. Pick whichever state is reachable in one clean
  screenshot without an open modal overlapping the stepper.
- **VIEWPORT:** 1600 × 1000.
- **CROP:** The workflow stepper (AI draft → Controller review → Approved →
  Action required → Closed) through the owner/next-step/status form. Do not
  include the Decision Log table below it — that's implied, not shown.
- **MESSAGE:** Nothing publishes without a named human, and an accepted
  insight becomes an owned action — not just a chart.

### 05 — Architecture / trust boundary

- **NAME:** `05-architecture-trust-boundary.png`
- **VIEW:** Architecture view (sidebar navigation), scrolled to the layer
  stack diagram showing the dashed trust boundary.
- **STATE:** Default architecture view load — no dialog, no expander open.
  The double-stroke deterministic nodes, the mineral-blue AI node, the
  porcelain human-approval node and the single champagne action node should
  all be visible in one frame if the diagram fits, or crop to include at
  minimum the trust-boundary rule itself with a deterministic node above and
  the AI node below it.
- **VIEWPORT:** 1600 × 1000.
- **CROP:** The layer-stack diagram and its "computed facts only / facts
  above, interpretation below" boundary line. Exclude the raw-payload
  inspection expander (keep that non-dominant, per doctrine).
- **MESSAGE:** The trust boundary is drawn, not just claimed — this is the
  same diagram grammar as the Blueprint, proving app and PDF are one family.

### Where these get used

| Screenshot | GitHub README | LinkedIn follow-up | BENACTA website | PDF / landing page |
|---|---|---|---|---|
| 01 Executive overview | hero image | ✓ (intro post) | hero | optional |
| 02 Attention issue | "See it" section | — | — | — |
| 03 Evidence + interpretation | "See it" section | ✓ (trust-boundary post) | ✓ | — |
| 04 Human review + action | "See it" section | ✓ (insight-to-action post) | ✓ | — |
| 05 Architecture view | "See it" section, near architecture.md link | ✓ (technical post) | ✓ | — |

Once captured, update README's "See it" section (currently deferred, per
`docs/acceptance-criteria.md` Gate H) to embed these five in the stated order.

---

## 8. Social preview / repository visual

GitHub's social preview (used in link unfurls on LinkedIn, Slack, etc.) is
**1280 × 640 px**, PNG or JPG, ≤ 1 MB, set under repository Settings → Social
preview.

**Recommendation: do not generate a new bespoke asset yet.** No existing
BENACTA source asset is a clean fit at this exact aspect ratio (the supplied
lockups are square-ish logo lockups, not 2:1 banners) — inventing one now
risks a rushed, off-charter composition. Treat this as a small, well-scoped
follow-up design task rather than something to improvise inside a docs phase.

**Composition brief for that follow-up** (so the next session or a designer
can execute it directly against the charter):

- **Background:** Deep Heritage Green `#122B20`, full bleed — matches the
  cover/close dark pages and Note #001's own dark treatment.
- **Headline (serif, porcelain):** `BENACTA`
- **Subtitle (Instrument Sans, tracked caps, Stone or porcelain):**
  `DECISION INTELLIGENCE REFERENCE ARCHITECTURE`
- **Statement (serif, semantic color per line — same treatment as Blueprint
  p4):**
  `Code computes.` (porcelain) · `AI explains.` (mineral blue `#6C9BA3`) ·
  `Humans decide.` (champagne `#BBA06B`)
- **Logo placement:** primary dark lockup, small, bottom-left or bottom-right
  corner, respecting the triangle protection zone — never centered/dominant
  (this is a preview thumbnail, not a cover).
- **Source asset to start from:** `assets/generated/benacta-primary-dark.png`
  cropped/recomposed at 1280×640, not stretched (brand-system.md forbids
  stretching the logo).
- **What to avoid:** cramming the full tagline, any diagram, any statistic —
  a social preview is read at thumbnail size; it needs three lines max.

---

## 9. Demo scripts

`docs/demo-script.md` already contains three scripts that satisfy this
section's intent — reviewed against the finalization spec in this phase and
left substantively unchanged, because they are already doctrine-correct.
Two deliberate deviations from the brief's suggested outline, both judgment
calls in the "review and improve" spirit rather than oversights:

1. **The 2-minute CFO walkthrough's order follows the actual cockpit
   navigation** (What happened → Attention → Why → Evidence → Human review →
   Action), not the brief's listed order (What happened → Why → Evidence →
   Attention → Follow-up → Approval → Owner). The cockpit's real information
   architecture is KPI band → ranked Attention → issue detail → human control
   → Decision Log (`docs/architecture.md` §7) — a presenter physically cannot
   show "Why" before selecting the item from the Attention list. Matching the
   brief's generic order over the app's real flow would make the script
   wrong the first time someone rehearses it against the running app.
2. **The 5-minute architect walkthrough does not introduce a standalone
   "Knowledge Layer" step positioned before "AI Interpretation."** Retrieval
   sits on the deterministic side of the trust boundary in this
   implementation — deliberately, and only after a red-team finding
   (`docs/final-red-team.md` P1-5) corrected an earlier draft that had
   misplaced it. A walkthrough script that re-introduces a pre-boundary
   "Knowledge Layer" beat would re-create exactly the confusion that fix
   exists to prevent.

One small, genuine gap closed this phase: the 5-minute walkthrough named
`domain.py` and `finance_engine.py` explicitly but never named
`control_engine.py` as its own beat, despite it being a distinct module with
its own Architecture-view row. Added a short explicit Control Engine beat and
an opening "enterprise data" framing sentence — see the diff in
`docs/demo-script.md`. Nothing else changed.

Final three, for reference:

- **A — 30-second pitch:** the one-breath thesis. Say before opening the app.
- **B — 2-minute CFO walkthrough:** KPI band → Attention → Revenue issue →
  Evidence → human review (approve or request revision) → action assignment
  → close on the Decision Log.
- **C — 5-minute architect/AI-engineer walkthrough:** enterprise data in →
  Business Semantic Layer → Deterministic core → Control Engine → Trust
  boundary → Context/retrieval → AI interpretation → Audit Trail → close by
  running `pytest -q` live.

---

## 10. Website / landing page copy

For a future BENACTA Blueprint landing page. Copy only — no page is being
built in this phase.

**EYEBROW**
> BENACTA · DECISION INTELLIGENCE

**HEADLINE**
> An LLM should never own your numbers. It should explain them.

**SUBHEADLINE**
> A working reference implementation showing how governed enterprise data
> becomes business objects, deterministic truth, context, AI interpretation,
> human judgment and action — without making the LLM the system of record.

**3 VALUE POINTS**

1. **See the architecture, not a slide.** A live Decision Cockpit you can
   click through — trace a figure to its postings, approve or reject an
   AI-drafted interpretation, watch an insight become an owned action.
2. **Verify the claim, don't take it on faith.** The reference implementation
   is public. The test that proves the AI layer is fully removable is one
   command away: `pytest -q`.
3. **Start with one decision, not a platform.** The Blueprint's method is
   commissionable in six to eight weeks on a single recurring decision
   process — not a multi-year data-platform program.

**EXECUTIVE BLUEPRINT DESCRIPTION**
> A ten-page executive read: the doctrine, the trust boundary that makes it
> real, and one material variance walked end to end with real (fictional)
> numbers. Built for a reader who never opens GitHub.

**LIVE DEMO DESCRIPTION**
> The same architecture, running. No login, no API key, no risk to any real
> data — because there isn't any. Click "Trace to source" on any KPI and
> watch the reconciliation happen in front of you.

**GITHUB DESCRIPTION**
> The reference implementation, in full — every module, every test,
> including the one that proves the AI layer can be switched off without
> changing a single figure.

**CTA**
> Choosing the first decision process to prove this on? Let's scope it
> together. → [Start a conversation]

Consistent with `positioning.md`'s two-lane close (decision-makers vs.
architects) — if the landing page ever splits into two paths, reuse that
exact framing rather than inventing a third lane.

---

## 11. BENACTA project description

All three keep **Enterprise AI**, **Decision Intelligence** and
**AI-Native Decision Systems**, and state Finance as the first reference
workflow rather than the whole of BENACTA (per `positioning.md`: "Finance is
the wedge — BENACTA is broader than Finance").

**15-word version** (social/profile)
> BENACTA builds AI-Native Decision Systems — Enterprise AI where code
> computes, AI explains, humans decide.

**30-word version** (project cards)
> BENACTA designs AI-Native Decision Systems at the intersection of
> Enterprise AI and Decision Intelligence. This reference implementation
> proves the architecture on Finance — the first of several decision
> workflows.

**75-word version** (website / portfolio)
> BENACTA designs and builds AI-Native Decision Systems at the intersection
> of Enterprise AI, Decision Intelligence, data, business logic, workflows
> and human judgment. Rather than adding a chatbot on top of enterprise data,
> BENACTA engineers the path from governed truth to decision and action —
> code computes every figure, AI explains what changed, humans keep the
> judgment and the accountability. Finance is the first proven reference
> workflow; the architecture is not finance-specific, and BENACTA is not a
> finance-only shop.

---

## 12. LinkedIn follow-up content series

Five assets, deliberately varied in format so the series doesn't read as five
copies of Note #001. The brief's four candidate titles were reviewed; two are
kept as proposed, one is retitled to match a doctrine-locked slogan exactly
(rather than a close paraphrase), and one ("Your enterprise doesn't need
another chatbot") is folded into a carousel instead of standing alone as a
fourth architecture note — the anti-pattern doctrine already leans hard on
"not a chatbot," and five single-page notes making adjacent architectural
points would start to blur together. A carousel earns its place by being a
different reading experience, not just different words.

| # | Title | Thesis | Format | Persona | Supporting asset |
|---|---|---|---|---|---|
| 1 | **Architecture Note #002 — "A dashboard ends at insight. A decision system continues into action."** | BI stops at "what happened"; a decision system closes the loop into an owned, logged action. | Single-page LinkedIn note, same visual family as Note #001. | COO / Transformation Director | Blueprint p8 + the seeded travel decision-log record (`app.py::seed_demo_state`) |
| 2 | **Architecture Note #003 — "From tables to business objects."** | A ledger row isn't business meaning; a Business Semantic Layer is what makes data decidable — and only then is AI worth pointing at it. | Single-page note, business-object relationship map. | Enterprise Architect / CIO | Blueprint p6 + `src/domain.py` |
| 3 | **Carousel — "We didn't build a chatbot. Here's why."** | The deliberate absence of a chat box is a design decision, not an omission — argued from the anti-pattern doctrine, not from hype-fatigue. | LinkedIn carousel, 5–6 slides, phone-readable (per `brand-system.md` carousel type scale) — the series' one non-note format. | CFO / CEO skeptical of AI hype | `anti-patterns.md` + the cockpit screenshots (§7 above) |
| 4 | **Architecture Note #004 — "The LLM is not the system. It is one component inside the system."** | The trust-boundary principle, standalone and quotable — reuses the Blueprint's own locked pull quote rather than a rewritten variant. | Single-page note, statement-card style, matching Note #001's dark-ground family exactly. | AI Engineer / CIO | Blueprint p5 + `test_financial_truth_is_independent_from_llm` |
| 5 | **Long-form text post — "What it took to prove our own AI is removable."** | A builder's-log reflection on the red team's most serious finding (a reconciliation that silently broke on two KPIs) and how it was caught and fixed — engineering discipline shown, not claimed. | Plain-text LinkedIn post, no graphic — deliberate format contrast after four designed assets. | Broad: engineers, CIOs, and prospects who read process as credibility | `docs/final-red-team.md` P0-1 + the public repository itself as proof |

Sequencing note: run #1 or #2 next (both extend the Blueprint without
repeating it), save #5 (the process post) for after the repo is public — it
references "the public repository," which should exist before the post asks
someone to go read it.

---

## 13. License decision support

No license is selected here — **owner decision required before or at
publication.** A concise comparison, not a recommendation:

| Option | What it means for readers | What it means for BENACTA |
|---|---|---|
| **A. No license** | Legally, all rights reserved by default — a reader technically cannot copy, modify or redistribute the code, even though the repo is public. Common on portfolio/reference repos, but ambiguous to enterprise legal teams who may hesitate to even clone it for internal evaluation. | Maximum control; zero obligation to support external use; may quietly deter the "send it to your architects" CTA if a legal team blocks on license ambiguity. |
| **B. MIT** | Reader can use, modify and redistribute freely, including commercially, with attribution. The most permissive common choice; the lowest-friction for an architect who wants to fork and adapt the pattern internally. | Signals confidence and openness; aligns with "send it to your architects" as a real invitation, not just a demo link; no protection against a third party rebranding a close copy. |
| **C. Apache-2.0** | Same practical freedom as MIT, plus an explicit patent grant and a NOTICE-file convention — more common in enterprise/vendor open source. | Slightly more enterprise-legal-team-friendly than MIT for exactly that reason (explicit patent grant); marginally more ceremony (NOTICE file) for a repo this size. |
| **D. Keep source-restricted / private for now** | No public repo yet — the funnel's GitHub leg doesn't exist. Note #001 and the Blueprint could still launch; "the reference implementation" becomes "available on request" rather than a link. | Removes the PROOF leg of the funnel (§1) at launch, which is a real cost — GitHub is what turns "trust me" into "verify it yourself." Reversible later; the safest option only in the sense that it defers rather than resolves the decision. |

**`OWNER DECISION REQUIRED BEFORE OR AT PUBLICATION.`** This does not block
Phase 12; it blocks step 11 in the publication order (§16 below).

---

## 14. Live demo deployment plan

**Recommendation: Streamlit Community Cloud.** It is the purpose-built,
zero-cost option for exactly this shape of app (public Streamlit repo, no
backend, no persistence needed), connects directly to the GitHub repo, and
auto-redeploys on push — the lowest-maintenance option that still counts as
"deployed" rather than "self-hosted infrastructure." Fallback if Community
Cloud is ever unsuitable: Hugging Face Spaces (Streamlit SDK) — same
shape, different host.

**Why this fits the constraints:**
- `DEMO_MODE` defaults to `"true"` even with **zero environment variables
  set** (`src/commentary.py::resolve_provider` — `os.environ.get("DEMO_MODE",
  "true")`). A fresh deploy with no configuration at all is safe by
  construction; there is nothing to forget to set.
- No visitor ever needs a key — the app should be deployed **without** an
  `ANTHROPIC_API_KEY` secret at all, not merely with `DEMO_MODE=true`. Two
  independent reasons the public demo must never carry a real key: it would
  let anonymous visitors burn API spend, and it would let a visitor's input
  reach a live model, which the whole public thesis argues against.
- `st.session_state` is per-browser-session; nothing in the app writes to a
  shared store (no database — session state + JSON export only, per
  `docs/architecture.md` §8). One visitor approving a draft or reassigning an
  owner cannot affect another visitor's session.

**Required repo changes:** none functionally required.
`requirements.txt` is already minimal and un-pinned to exact versions
(`pandas>=2.0`, `streamlit>=1.30`) — fine for a demo deploy; the optional
`anthropic` dependency stays commented out. One config review item, not a
required change:

- `.streamlit/config.toml` currently sets `showErrorDetails = true`. That's
  useful during development; for a **public** demo it means an unhandled
  exception shows a full Python traceback (file paths, internal function
  names) to any visitor. Recommend reviewing this before deploy — Streamlit's
  `client.showErrorDetails` accepts `"stacktrace" | "type" | "none"` in
  recent versions; `"type"` is a reasonable middle ground for a public demo.
  This is a deployment-time judgment call for the owner, not a code defect —
  noted here rather than changed, since Phase 12 makes no application
  changes.

**Environment variables / secrets on the host:**
- `DEMO_MODE=true` — set explicitly even though it's the default, so the
  deployed app's configuration is self-documenting in the host's dashboard.
- No `ANTHROPIC_API_KEY` — omit entirely (see above).

**Security considerations:**
- No secrets to leak (none are configured).
- No real or sensitive data anywhere in the app (fictional dataset only).
- No write path to any external system (read-only by design).
- Cross-visitor isolation is structural (session state, no shared database).
- Public demo cost/abuse surface is effectively zero — without a real
  provider key, there's no metered resource for a visitor to exhaust beyond
  the host's own compute, which Community Cloud manages.
- Free-tier hosts sleep after inactivity and cold-start on the next visit
  (typically 10–30 seconds) — set expectations in any message that links to
  the demo ("give it a moment to wake up").

**Deployment checklist:**

- [ ] Confirm `DEMO_MODE=true` will be set as an explicit environment
      variable / secret on the host (even though it's the safe default)
- [ ] Confirm no `ANTHROPIC_API_KEY` (or any secret) is configured
- [ ] Review `showErrorDetails` in `.streamlit/config.toml` for the public
      deployment
- [ ] Deploy from the `main`/default branch pointed at `app.py`
- [ ] Smoke test immediately after deploy: app loads, KPI band renders,
      "Trace to source" opens and reconciles on Revenue, approve/request
      revision both work, Architecture and Audit Trail views load
- [ ] Confirm the public URL loads in a logged-out / private browser window
- [ ] Record the URL for README, the PDF's placeholder slot (if re-rendered),
      and the release checklist

---

## 15. Placeholders (owner / release tasks — not product defects)

| Placeholder | Where it appears | Status |
|---|---|---|
| Live demo URL | README "See it", PDF p10 proof card | `OWNER / RELEASE TASK` |
| BENACTA website URL | PDF p10 decision-maker lane, author line | `OWNER / RELEASE TASK` |
| LinkedIn URL | PDF p10 decision-maker lane (if used) | `OWNER / RELEASE TASK` |
| QR code | PDF p10 | `OWNER / RELEASE TASK` |
| Cockpit screenshots (5) | README "See it", LinkedIn content | `OWNER / RELEASE TASK` — plan in §7 above |
| LICENSE decision | Repository root | `OWNER DECISION REQUIRED` — options in §13 above |

None of these are engineering defects; all are already called out as
deferred in `docs/final-red-team.md` and `docs/acceptance-criteria.md` §11.

---

## 16. Publication order (reviewed and refined)

The brief's proposed 20-step order was sound; two additions below close real
gaps it left implicit — resolving the git/commit-authorship question (found
during this phase's own git inspection, see `docs/release-checklist.md`
§Code and the Phase 12 final report) before the repository goes public, and
an explicit "decide license" step tied to §13.

1. Final human visual review (app at full size, PDF at full size / print)
2. **Resolve the branch/commit state** — get all outstanding work merged to
   the default branch in a form the owner is comfortable with permanently
   public (see `docs/release-checklist.md` §Code for the specific finding)
3. Choose LICENSE (§13)
4. Capture the five screenshots (§7)
5. Deploy the live demo (§14)
6. Insert final URLs in README / PDF where placeholders exist
7. Generate the QR code, if used
8. Re-render the PDF only if URLs or content changed as a result of steps
   3–7 (otherwise skip — the PDF is already final per `docs/final-polish.md`)
9. Run the full test suite one more time
10. Final hygiene scan (secrets, absolute paths, real names, debug files)
11. Merge any final PRs (including this release-package branch)
12. Make the repository public
13. Create the `v0.1.0` release (§6)
14. Verify the public GitHub repo logged-out (fresh/incognito browser)
15. Verify the live demo logged-out
16. Publish the Architecture Note #001 LinkedIn post with the final CTA (§2)
17. Respond to `BLUEPRINT` comments using the delivery workflow (§3)
18. Send the Executive Blueprint to each commenter
19. Route technical readers to GitHub, executives to the live demo / PDF
20. Begin the follow-up content series (§12), starting with Note #002 or #003

---

## 17. Final content architecture (recap)

This distinction must survive publication — every future BENACTA asset
should know which of these four jobs it's doing before it's written:

- **LinkedIn** → Attention. Earns five seconds of interest; asks for nothing
  but a comment.
- **PDF** → Understanding. Earns ten minutes; makes the doctrine legible to
  someone who will never open GitHub.
- **Live Cockpit** → Experience. Earns a click-through; makes the boundary
  tangible instead of described.
- **GitHub** → Proof. Earns a clone or a read of the test suite; answers
  "is this actually true" for a reader who doesn't take claims on faith.
- **BENACTA (the conversation)** → the only place a sale is even implied, and
  even there, per every DM template in §3, it's an offer to talk, never a
  pitch.

---

## 18. Final quality check (this phase)

Verified before writing this document and again before finalizing it:

- No new unsupported claims introduced — every figure, module name and test
  name referenced above (`test_financial_truth_is_independent_from_llm`,
  `src/domain.py`, the 155-test count, the €4.72M/€5.00M/−€280K story
  figures) was checked against the current README/architecture docs, not
  invented for this document.
- No product-scope changes proposed anywhere in this package — everything
  above describes or repackages what already exists.
- No secrets, no incorrect URLs (all placeholders are explicitly marked, not
  guessed), repository name verified against `git remote -v`
  (`anasbenazzouz/benacta-decision-intelligence-blueprint` — matches).
- No accidental Palantir/Foundry positioning anywhere in this document —
  checked by re-reading every section against `anti-patterns.md` before
  finalizing.
- Messaging checked against `positioning.md`'s slogan hierarchy — no surface
  above mixes two slogan roles; the LinkedIn CTA, DM templates, website copy
  and release notes each use at most one register of BENACTA's own language,
  never invented taglines.
