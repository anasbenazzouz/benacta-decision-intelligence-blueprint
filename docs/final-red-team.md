# BENACTA — Final Red Team

> Adversarial review of the complete system: reference implementation, README,
> Decision Cockpit, Architecture Note #001 continuity, and the Controlled
> Intelligence Blueprint PDF. Six reviewer lenses — CFO, CEO/COO, Enterprise
> Architect, AI Engineer, Brand Director, and a skeptical prospective client
> trying to disprove the claims.
>
> Method: read every doctrine and documentation file; read `app.py` and every
> `src/*.py` module in full; ran the suite, the CLI loop and the app with no API
> key; recomputed the financial story from `data/*.csv` independently of the
> tests; extracted and scanned the rendered PDF; audited the repository for
> publication hygiene.
>
> **Outcome: 2 P0, 9 P1, 6 P2 found. All P0 and P1 fixed. Test suite 150 → 155.**

---

## The core question

> Is this a Decision Intelligence system, or a finance dashboard with an LLM
> bolted on?

It is a Decision Intelligence system, and the distinguishing evidence is
structural rather than rhetorical:

- **The chain is real, not drawn.** `DATA → BUSINESS OBJECTS → TRUTH → CONTEXT →
  INTERPRETATION → DECISION → ACTION → OUTCOME` corresponds to actual modules and
  actual state transitions. Rows are rejected when they disagree with the
  governed model (`SemanticMappingError`), not silently aggregated — raw data and
  business meaning are genuinely different things here.
- **The trust boundary is enforced, not asserted.** `tests/test_ai_independence.py`
  proves it two ways: an AST walk of the transitive import graph, and a re-import
  of the truth layer with every AI path blocked at the import-system level,
  compared field by field against a normal run. A third test proves the blocker
  itself blocks — the guard most projects forget.
- **AI is one component.** `commentary.py` is the only module below the boundary.
  It receives computed facts, alerts and quoted evidence; it never sees the
  ledger. `verify_no_invented_numbers` is production code, not a test helper: the
  LLM path validates its own output and degrades to deterministic commentary with
  the reason recorded.
- **It does not stop at insight.** A finding becomes an issue, a reviewer, an
  owner, a next step, a status and a due date, each logged.
- **It is not a chatbot.** There is no free-text box anywhere, by design.

What it is *not*, and says so: a platform, a workflow engine, a production
application, or an integration to any real system.

---

## P0 — release blockers (2 found, 2 fixed)

### P0-1 · The trace-to-source view produced a false reconciliation on two of the four headline KPIs

**Found by:** Enterprise Architect / skeptical client, testing the central claim
rather than reading it.

The cockpit offers **Trace to source** on every KPI, and the entire promise of
that button is that the rows behind a figure add up to it. `transactions_for_fact`
collected every account composing a metric and summed the raw posting amounts —
correct for Revenue, wrong for anything composed. Clicking Trace on **Gross
Margin** or **EBITDA** returned the 14 *revenue* postings and displayed them as
the source of a different figure, with the reconciliation pill reading
`Difference −€2,255,000` / `−€3,855,000`.

This is the worst class of defect for this project specifically: the system's own
reconciliation visibly failing, on the primary demo surface, under a claim of
traceability. A CFO clicking that button in a demonstration would have watched the
thesis break.

**Root cause:** the transaction ledger is elaborated to posting grain for revenue
accounts only, and composed metrics net their accounts rather than summing them.
Neither condition was checked.

**Fix:** `src/lineage.py` now resolves a figure to postings only when the ledger
can actually reproduce it — every composing account present **and** a single
uniform sign (`_traceable_accounts`, `has_posting_grain`). Otherwise it returns
nothing and the cockpit's existing honest empty state explains why. Revenue and
its business-unit drill-downs still reconcile to the cent. No dataset was
invented to paper over the gap.

### P0-2 · A fabricated ledger row in the flagship PDF

**Found by:** skeptical client, checking whether the example data is real.

Page 6 of the Blueprint contrasted "A ROW" with "A BUSINESS OBJECT" using
`2026-07 · 40100 · BU-PRJ · 4,720,000`. Account `40100` exists nowhere in the
chart of accounts (revenue accounts are `700100`–`700400`, and the semantic layer
would reject that code), and `4,720,000` is the monthly aggregate, never a posting.

A fabricated data row, in a document whose argument is that figures must trace to
their source, is a P0 regardless of how small it looks.

**Fix:** replaced with a real posting taken from `data/transactions.csv` —
`2026-07 · 700100 · BU-PRJ · CC-4100 · 910,000`.

---

## P1 — credibility issues (9 found, 9 fixed)

### P1-1 · README claimed posting-level lineage for every headline figure

`README.md` stated "every headline figure traces to the postings behind it". The
repository's own `tests/test_transactions.py` asserts the opposite. Corrected to
state exactly what is true — Revenue traces to postings and reconciles; the
composed metrics resolve to root-cause source records and stop there — with the
limit added to the Limitations list.

### P1-2 · The PDF presented a curated evidence order under a caption denying curation

Page 7 listed the three retrieved documents in the reverse of the system's actual
ranking, captioned "Retrieved by the system, with the reason each passage was
selected — **not a curated list**". Verified against `src/retrieval.py`: FY26
Forecast Assumptions (0.8) → Management Commentary (0.8) → Milestone Register
(0.6). Reordered to the true ranking; the storyboard was corrected in step so
story and production cannot drift apart again.

### P1-3 · Factual error: "two milestones on one project"

MS-2214 is *Phase 2 customer acceptance* on **Northgate Water Treatment** for
Nordic Water Utilities AB; MS-2231 is *Commissioning acceptance* on **Halden
Terminal** for Halden Port Authority. Two projects, two customers. Rewritten, and
the sentence now does more work than before: the shortfall resolves to named work
with a named owner rather than to a number.

### P1-4 · The business-object map claimed a graph the semantic layer does not hold

The page-6 caption read "Every line is a relationship **the system knows**".
`src/domain.py` models `BusinessUnit → CostCenter → Account`; project, customer,
milestone and owner exist as attributes on lineage records, not as related
objects. The page is doctrine, and its caption now says so: "Every line is a
relationship **a decision depends on**". The claim is unchanged in force and now
true.

### P1-5 · README placed retrieval on the wrong side of the trust boundary

The layer table listed "Context retrieval" under the Knowledge/AI Layer, while
`docs/architecture.md`, `tests/test_ai_independence.py` and README's own diagram
all place it above the boundary. On a project whose entire claim is that boundary,
misplacing a component in the summary table is a credibility issue. Corrected,
with the reason stated: retrieval selects and quotes existing text and generates
nothing, so evidence is quoted source rather than model output.

### P1-6 · Build-process memos would have published

`00_START_HERE_BENACTA.md`, `01_MASTER_BRIEF_BENACTA.md` and
`02_EXECUTION_PLAYBOOK_CLAUDE_CODE.md` were tracked and would have gone public.
They contain model-routing and usage-credit instructions, a "Do NOT waste it on"
table, DM scripts for prospects ("warm version"), and a commit-cadence section
closing on *"This makes the public repo itself tell a credible engineering
story."* Publishing an operating manual for how the repository was produced says
nothing about the architecture and a great deal about the process.

Untracked (kept on disk, added to `.gitignore`) with the rationale recorded there.
`CLAUDE.md` and `docs/source-analysis.md` updated so nothing references a file a
public clone will not have. The doctrine those memos carried already lives in
`.claude/benacta/*` and `docs/` — no project knowledge was lost.

### P1-7 · Documentation read as an AI-agent session log

`docs/ui-qa.md`, `docs/pdf-storyboard.md` and the screenshots README carried
"the browser tooling available in this session", "known issue on this machine",
"Rather than fabricate images", "confirmed by the repository owner". Honest
process notes are an asset; phrasing that reads as agent-session transcript is
not. Rewritten as engineering records without losing a single substantive
caveat.

### P1-8 · Acceptance criteria showed 0 of 52 boxes checked

`docs/acceptance-criteria.md` opened with "V1 is done when **every** item below
holds" and had nothing ticked, while `README.md` said "verified against the
current codebase — nothing here is aspirational". A reader comparing them got
opposite readings of project status. 47 boxes are now ticked against reproducible
evidence; 5 remain open and are marked **PENDING** — three human checkpoints in
front of the running app, two deferred pre-publication tasks. A status header
states the standard of proof used.

### P1-9 · "No postings this period" was about to misreport a scope limit as a business fact

Exposed by the P0-1 fix: with composed metrics correctly returning no rows, the
lineage chain would have captioned them "No postings this period" — which for the
unbudgeted workshop account is a true and meaningful statement, and for EBITDA is
false. Split into two captions with a `posting_grain` flag, and pinned by a test
asserting the two can never share wording.

---

## P2 — polish (6 found, 5 fixed, 1 accepted)

| # | Finding | Action |
|---|---|---|
| P2-1 | Test count stated as 150 in README, demo script and implementation guide; suite is now 155 | Fixed everywhere; historical counts in the dated Phase 6 QA log left as the record of that run |
| P2-2 | PDF page 3 said "eight responsibilities"; the diagram shows seven layers plus an audit rail | Changed to seven |
| P2-3 | Page 7's chain locator lit OUTCOME, which the page does not cover and the demo does not implement | Dimmed |
| P2-4 | `docs/implementation-plan.md` described the seeded demo issue as revenue/Project Finance; the code seeds travel/Cost Center Manager · Projects | Corrected, with `app.py::seed_demo_state` named as the authority |
| P2-5 | Stale Phase-2 repository tree and an incomplete metric enumeration in planning docs; `architecture.md` omitted `lineage.py` and `pipeline.py` | Tree marked as the superseded Phase-2 target with README named as accurate; metric count corrected to eleven; architecture.md now covers both modules and states the lineage limit |
| P2-6 | `acceptance-criteria.md` cited a boundary test at 99,999.99; the test uses 99,999 | Fixed |

**Accepted without change:** hardcoded Edge paths in `scripts/render_blueprint.py`
already fall back to a cross-platform lookup; `data/context/management_notes.md`
says contractor costs ran ~€125,000 over while the metric says €120,000 — both are
correct at different grains (account 604100 is +125,000; the metric nets 604200's
−5,000) and flattening it would make the demo less honest, not more.

---

## Reviewer findings

### CFO

Value is legible in well under three minutes: the cockpit answers what happened,
why, what needs attention, on what evidence, what to do next, and who is
accountable — in that order, with no engineering vocabulary. AI is visibly
controlled: interpretation is subordinated in the visual hierarchy to the derived
root cause, is labelled a draft, and cannot publish without a named controller.
Rejection is a designed path, not an error state. The materiality threshold is
citable written policy rather than an opinion of the tool. Nothing reads as hype;
the strongest verbs in the PDF are "explain" and "propose". The one-decision-first
method on page 9 is specific enough to commission.

*This reviewer raised P1-1 and P1-5 — both about a claim being wider than the
thing it described.*

### CEO / COO

Finance is unambiguously the instance, not the brand: the PDF's architecture page
is domain-neutral and finance appears only as the worked example. The reusable
pattern is legible without the finance detail. Applicability to operations,
procurement, projects and planning is implied by the pattern and never claimed as
existing capability — the "From reference implementation to enterprise" table is
explicitly labelled as direction, not function. Strategic rather than merely
technical, because the argument is about where control sits, not about tooling.

### Enterprise Architect

Responsibilities are clean and the boundary is the real thing — testable, and
tested in both directions. The semantic layer earns its place: metric definitions
carry direction, so favourability is business meaning rather than the sign of a
number, and non-conforming rows are rejected rather than absorbed. Lineage is now
honest about its own limit, which is worth more than broader coverage would have
been. Composability is shown through stable contracts with replaceable
implementations. Nothing is presented as production-grade.

*This reviewer raised P0-1 by clicking the button instead of reading the claim.*

### AI Engineer

Financial truth is independent of the LLM, verified rather than trusted: the
structural test walks the transitive import graph via AST so it holds for code
paths tests never execute; the behavioural test blocks imports at the meta-path
level and compares field by field; a third test proves the blocker blocks.
`DEMO_MODE=true` is the default and the whole system runs with no key. Evidence
and generated interpretation are separate objects with separate provenance. The
no-invented-numbers guard runs in production, not only in tests, and the allowed
set is derived rather than hand-listed. Confidence tracks evidence coverage.
Provider failure degrades to deterministic output with the reason recorded. No
hidden computation below the boundary.

### Brand Director

One company across all four artifacts. The Blueprint is unmistakably the Note's
family — same header grammar, gold numbered sections, dashed trust boundary with
"computed facts only / facts above · interpretation below", italic margin
annotations stating business outcomes, dark statement pages — while being
editorial where the Note is a poster. Palette and type roles are the charter's,
including the discipline that mineral blue appears only where there is AI meaning
and page 6 therefore contains none. Every glyph in the PDF is set in a charter
face: the arrows and check marks are drawn in the charter's own connector grammar
because neither family carries them. Nothing generic, templated, or borrowed.

### Skeptical prospective client

The separation this reader demands is now explicit throughout:

| | |
|---|---|
| **Real and verifiable** | Every figure, computed by code from CSVs and reconciled to postings for Revenue; the controls; the retrieval and its scores; the review state machines; the audit trail; the AI-independence proof |
| **Simulated** | The company, the data, the source systems. `source_system` values are strings in fixtures, not connections — stated wherever the data appears |
| **Deterministic** | Everything above the trust boundary, including retrieval |
| **AI-generated** | The commentary prose only, always labelled, never published unapproved |
| **Future direction** | The Connect/Model/Understand/Augment/Act/Govern/Learn table, workflow-system integration, outcome measurement — all labelled as direction |

Remaining honest gaps, all disclosed in the documents themselves: no real
integration, no outcome object closing the feedback loop, retrieval is keyword
scoring, and posting-grain lineage covers Revenue only.

---

## Verification run

```
pytest -q                                          155 passed  (no API key present)
test_financial_truth_is_independent_from_llm       passed
scripts/demo_decision_loop.py                      exit 0, full loop
streamlit run app.py  (DEMO_MODE=true, no key)     HTTP 200
PDF                                                10 pages · A4 210 × 297 mm · 253 KB
```

PDF re-rendered after the corrections and re-inspected page by page. Text scan of
the finished file: no Palantir/Foundry, no clichés, no AI-engineering vocabulary,
no "AI Decision"; figures limited to the verified set plus the three cited
benchmarks; fictional-data notice present; one champagne action node per diagram;
smallest type 7.5 pt; GitHub link live; metadata stamped.

---

## Deferred — pre-publication

Not release blockers for the work itself; each needs a decision or an action only
the owner can take.

1. **LICENSE.** No license file. A public repository without one is legally
   ambiguous. Owner's choice.
2. **Cockpit screenshots.** Capture plan in `assets/generated/screenshots/README.md`;
   README's "See it" section is updated once they exist. No image is committed
   that was not captured from the running app.
3. **Commit authorship.** The single commit carries a personal Gmail address in
   its author metadata, which becomes permanently public on push. Nothing has been
   pushed, so this is still free to fix: set `user.name`/`user.email` to the
   identity intended for publication and re-create the commit. Doing so also
   removes the untracked build memos from history.
4. **Live demo, website, LinkedIn, QR.** Placeholders in the PDF close, marked
   *to be added*.
5. **Rendered visual pass of the app.** The cockpit is verified functionally and by
   reading `theme.py`/`app.py`; a human should still look at it at full size.
6. **`source/brand/` visibility.** The supplied charter is internal design
   documentation. Architecture Note #001 is already public; whether the full visual
   identity system should be is a business decision, not an engineering one.

---

## Scorecard

| Dimension | Score | Note |
|---|---:|---|
| Executive clarity | 9 | Six questions in order, no jargon, decision-led hierarchy. Held back from 10 only until a human confirms the two-minute CFO checkpoint in front of the running app |
| Decision Intelligence positioning | 9 | Unmistakably not a dashboard and not a chatbot; the loop into owned action is the differentiator and it is demonstrated |
| Architectural credibility | 9 | Boundary enforced and tested; semantic layer earns its place; limits now declared rather than glossed |
| AI governance | 10 | Removability proven three ways, output validated in production, human approval mandatory, rejection a designed path |
| Finance credibility | 9 | Every figure recomputed from source and test-locked; direction-aware favourability; citable materiality policy; the over-explaining 123% attribution is reported rather than netted away |
| Engineering quality | 9 | 155 tests, clean module boundaries, no dead code, honest empty states. Not 10: the P0 showed a public surface that no test covered until now |
| BENACTA brand coherence | 9 | One family across Note, app, README and Blueprint; charter followed to the glyph |
| Public GitHub quality | 8 | Now clean and credible, but LICENSE is absent and the commit history still needs re-creating before it goes public — both owner actions |
| Executive PDF quality | 9 | Ten pages, one idea each, charter-exact, all text selectable, every figure verified. Not 10 until a human reviews it at full size in print |
| Differentiation | 9 | The trust boundary, the removability test and the honest lineage limit are things a competitor deck cannot copy without building them |

**Scores below 8:** none. The single 8 is Public GitHub Quality, and both reasons
are owner decisions rather than engineering gaps.

---

## The final question

> Does this convincingly demonstrate that BENACTA understands how to engineer the
> layer between enterprise data and business decisions and action?

Yes — and the reason is narrower than the volume of work suggests. Most enterprise
AI material argues for a boundary between deterministic truth and probabilistic
interpretation. This project *builds* one, then tries to break it: the truth layer
is re-imported with every AI path blocked and compared field by field, and the
guard that proves the blocker works is itself tested.

The red team's own history is the second piece of evidence. The most serious defect
found was not a broken feature but a reconciliation that silently failed on two
KPIs — and it was caught by pressing the claim rather than reading it, then fixed
by narrowing the claim to what the data supports instead of widening the data to
fit the claim. A project that removes a capability statement to stay accurate is
demonstrating the discipline it is selling.

What it does not demonstrate is scale: one period, one use case, fictional data, no
integration. It never says otherwise, and that restraint is what makes the rest
believable.

---

## Release recommendation

**GO**, conditional on the owner completing items 1–3 under *Deferred —
pre-publication* before the repository is made public. No engineering work
remains outstanding.
