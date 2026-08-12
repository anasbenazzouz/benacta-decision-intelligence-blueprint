# BENACTA — Controlled Intelligence Blueprint · PDF Storyboard

> **Phase 8 deliverable.** This file governs Phase 9 production of
> `docs/controlled-intelligence-blueprint.html` and
> `docs/BENACTA_Controlled_Intelligence_Blueprint.pdf`.
> It supersedes the master brief §27 page plan (recorded there as a starting
> hypothesis; deviations and their rationale are logged in §A.5 below).
> Binding doctrine: `.claude/benacta/*`. Ground truth: `/source` and
> `docs/source-analysis.md`. Nothing in this storyboard may be changed in
> Phase 9 except typographic fitting — see Part F.

---

# Part A — Executive Narrative

## A.1 Audience

Primary: CEO · CFO · COO · Finance Director · Transformation Director.
Secondary: CIO · Enterprise Architect.

Design constraint: the document must be fully valuable to a reader who never
opens GitHub, never runs the application, does not know what RAG is, and does
not write code. Zero AI-engineering vocabulary in body copy; technical terms
appear only as small Stone footnotes for the architect reading over the
executive's shoulder.

## A.2 Objective

The premium lead magnet following Architecture Note #001. The Note is a
one-page compact architecture poster (finance instance, dense). The Blueprint
is a ten-page executive narrative (the general doctrine, breathing room). The
reader finishes understanding one thing:

> **AI should not replace the system of truth.
> It should augment the path from governed data to decision and action.**

## A.3 Core thesis

The document answers one executive question:

> **How should an enterprise introduce AI into a decision process without
> surrendering control, traceability or accountability?**

Not "how do we deploy an LLM", not "how do we build a RAG", not "which model".
Architecture before tools. Decision before AI.

## A.4 Narrative arc

```text
ENTERPRISE DATA EXISTS — the bottleneck is the path from data to decision   (p2)
        ↓
A DECISION INTELLIGENCE SYSTEM ENGINEERS THAT PATH DELIBERATELY              (p3)
        ↓
THE DOCTRINE: CODE COMPUTES. AI EXPLAINS. HUMANS DECIDE.                     (p4)
        ↓
THE ARCHITECTURAL CONSEQUENCE: AN EXPLICIT TRUST BOUNDARY                    (p5)
        ↓
THE FOUNDATION: FROM TABLES TO BUSINESS OBJECTS                              (p6)
        ↓
THE PROOF: ONE MATERIAL VARIANCE, END TO END                                 (p7)
        ↓
THE COMPLETION: INSIGHT CONTINUES INTO OWNED ACTION                          (p8)
        ↓
THE METHOD: START WITH ONE DECISION                                          (p9)
        ↓
CLOSE: DON'T START WITH AI. START WITH THE DECISION.                         (p10)
```

Structure: page 3 is the **map**; pages 4–6 are three **zoom-ins** on the
map's load-bearing ideas (responsibility, boundary, foundation); pages 7–8
are the **lived proof**; page 9 is the **method**; the dark pages 1, 4 and 10
are the emotional spine (open, doctrine, close).

**The six-sentence story test** (the whole PDF in six sentences):

1. Enterprises already own the data; the bottleneck is the fragmented path
   from data to decision and action.
2. Dashboards stop at insight and chatbots guess at truth, so neither closes
   that path — the failure is architectural, not a missing tool.
3. A Decision Intelligence System engineers the path deliberately: governed
   data becomes business objects, deterministic truth, context, AI
   interpretation, human judgment and owned action — traceable end to end.
4. AI belongs on the interpretation side of an explicit trust boundary —
   retrieving context, explaining computed facts, drafting and questioning —
   never computing or owning the truth.
5. Humans keep judgment, approval and accountability: nothing publishes
   without a named reviewer, and every accepted insight becomes an owner and
   a next step.
6. Start not with AI but with one decision process — map its objects,
   engineer its truth, add context and interpretation, keep humans in
   control, connect to action, measure against baseline — and the working
   reference implementation proves that pattern end to end.

## A.5 Challenge log — how the starting hypothesis was improved

The Phase 8 prompt's 10-page hypothesis was reviewed as CFO, CEO,
CIO/Enterprise Architect and BENACTA Brand Director. Changes made:

| # | Change | Rationale |
|---|---|---|
| 1 | **Trust Boundary keeps its own page (p5); the master brief's standalone "Reference implementation" page is removed.** Implementation proof moves into the close (p10) and into small "proven in the reference implementation" notes on pages 5, 7 and 8. | The trust boundary is BENACTA's most load-bearing idea and the CIO's credibility test; a brochure page about the demo is the weakest page for every persona. Doctrine: "the PDF should stand alone; GitHub should strengthen it." |
| 2 | **Pages 4 and 5 sharply differentiated** to remove the overlap risk: p4 is the doctrine as a typography-led dark manifesto (who does what); p5 is the architectural consequence as a diagram page (where determinism ends and probability begins, and why removability proves it). | Same idea seen twice reads as padding; one emotional page + one architectural page reads as depth. CFO keeps p4, CIO keeps p5. |
| 3 | **"From dashboard to decision system" loses its standalone page.** The maturity ladder (REPORTING → ANALYTICS → PREDICTION → DECISION INTELLIGENCE → ACTION) becomes a margin strip on p2; the insight-to-action loop is p8. | The maturity ladder is an industry slide every reader has seen; BENACTA's original claim is the loop into owned action, not the ladder. |
| 4 | **Page 3 is broadened to the domain-neutral Decision Path.** Finance appears only as the instance on p7 (which carries the `FIN-AI-001` continuity reference). | The positioning evolution this Blueprint must perform: Note #001 = finance instance; Blueprint = BENACTA's general doctrine. Finance is the wedge, not the brand. |
| 5 | **PROJECT chosen over INVOICE as the business-object example (p6)**, connected to Customer, Contract, Milestones, Revenue & Forecast, Cost Center, Owner, Documents, Risks. | It makes p6 → p7 one continuous thought: *because* the system knows what a milestone connects to, it knows which revenue, which forecast and which owner move when two milestones slip. The invoice example belongs to a procurement story V1 doesn't tell. |
| 6 | **A chain-locator motif** added: pages 4–8 carry a miniature of the canonical chain with the segment under discussion in ink, the rest in Stone. | Cheap visual coherence; reinforces DATA → … → OUTCOME by repetition; gives every zoom page its place on the map. |
| 7 | **Cover hero = the subtitle, not the document name.** "How to introduce AI into enterprise decision-making without giving up control of the truth." is the hook; "CONTROLLED INTELLIGENCE BLUEPRINT" becomes the publication label, mirroring Note #001's header grammar. | The document name is a label; the promise is the reason to turn the page. |
| 8 | **Statistics almost eliminated.** Three of the four sourced Note #001 benchmarks are used, each exactly once, each where it works: Gartner 58% as a p2 margin note (urgency without hype), APQC ≤5 days and PwC 0.55%-vs-~1% as example baselines on p9. McKinsey 42% and the illustrative €450k are excluded (they narrow the frame to automation economics). | "Architectural clarity is the primary proof." The Note is the dense stats artifact; the Blueprint must not be a stretched Note. |
| 9 | **Zero Palantir/Foundry mentions anywhere in the PDF** — not even as a technical aside. The only permitted technical echo is the Stone footnote "lightweight ontology / domain model" on p6. | The Blueprint is BENACTA's own doctrine. The README already carries the honest technical attribution for readers who go looking; the executive artifact must not borrow positioning. |

Reviewer verdicts after changes: **CFO** — pages 2, 4, 7, 8, 9 speak directly
to me; nothing requires engineering vocabulary; risk is reduced without
banning AI. **CEO** — the difference from dashboards (p8) and chatbots (p5)
is explicit; the idea survives in one sentence. **CIO/EA** — boundary is
testable (removability), semantic layer is concrete (p6 map), auditability is
drawn (p3 rail), scope honesty on p8 protects credibility. **Brand Director**
— unmistakably the Note's family: same header grammar, numbered gold
sections, dashed boundary, margin business-outcome annotations, dark
statement pages; nothing borrowed.

---

# Part B — Page-by-Page Storyboard

Every page: one primary idea. Ten pages. Two background colors across the
publication (Warm Porcelain, Deep Heritage Green — charter maximum). Dark
pages: 1, 4, 10.

---

## PAGE 1 — COVER

- **PAGE ROLE:** Open with authority; name the artifact; state the promise;
  establish continuity with Note #001.
- **EXECUTIVE QUESTION:** "Is this worth ten minutes of my time?"
- **ONE CORE MESSAGE:** There is a way to introduce AI into decision-making
  without giving up control of the truth — and this document is its blueprint.
- **HEADLINE (serif display, porcelain, on deep green):**
  How to introduce AI into enterprise decision-making
  *without giving up control of the truth.*
  (line 2 italic champagne `#BBA06B` — mirrors the Note's two-line thesis
  treatment)
- **SUBHEAD:** none. The cover stays minimal.
- **BODY COPY:** none beyond the elements below.
  - Publication label (top, tracked caps): `BENACTA · N° 001` (small, Stone-on-dark)
    over `CONTROLLED INTELLIGENCE BLUEPRINT` (larger, champagne).
  - Continuity block (lower third): kicker `FROM ARCHITECTURE NOTE N° 001`
    (tracked caps, mineral blue `#6C9BA3`), then serif italic quote in
    porcelain: *"An LLM should never own your numbers. It should explain
    them."*
  - Bottom: supplied **primary dark lockup** PNG (contains the tagline
    "BUILT ON TRUTH. DESIGNED FOR DECISIONS." — the lockup's triangle is this
    page's single triangle occurrence).
- **VISUAL:** Typography only. Deep Heritage Green `#122B20` full-bleed;
  generous negative space; one hairline rule under the publication label.
- **PROOF / EXAMPLE:** The thesis quote is the continuity proof — the reader
  arrived here by commenting BLUEPRINT on the Note.
- **TECHNICAL DEPTH:** EXECUTIVE.
- **BRAND DIRECTION:** Statement-card grammar scaled to a page: dark ground,
  tracked champagne kicker, serif statement with semantic color emphasis,
  lockup as signature. Slogan surface discipline: thesis quote + tagline
  (inside lockup artwork only) — no other slogan on this page.
- **WHAT TO AVOID:** A busy cover. No diagram, no stats, no icons, no second
  serif statement competing with the hero, no reproduction of the tagline
  outside the lockup.

---

## PAGE 2 — 01 / THE DECISION GAP

- **PAGE ROLE:** Establish the problem in the reader's own operating reality —
  without insulting the systems they already bought.
- **EXECUTIVE QUESTION:** "We've invested in ERP, BI and a data platform —
  why does deciding still feel slow and manual?"
- **ONE CORE MESSAGE:** The bottleneck is not the data; it is the fragmented
  path from data to decision.
- **HEADLINE (H1 sans bold, two decks):**
  Your company already has the data.
  The bottleneck is the path from data to decision.
- **OPTIONAL SUBHEAD:** none.
- **BODY COPY (draft):**
  An enterprise of any scale already owns an ERP, an EPM, a CRM, a BI stack,
  document stores and a data platform. The data exists. The reports exist.
  Yet between those systems and an actual decision, people still collect,
  reconcile, search, interpret, explain, email, approve and follow up —
  every month, in every function.

  None of these systems is useless. The problem is that truth lives in one
  place, context in another, judgment in meetings and inboxes, and action in
  whatever tool the owner opens next. Truth, context, judgment and action are
  fragmented — and the fragmentation, not the data, is the bottleneck.

  Closing lines (set apart, H2 weight):
  **The opportunity is not another dashboard.**
  **And it is not another chatbot.**
- **VISUAL:** Editorial two-column composition in the Note's ✗-table grammar,
  lightened: left column "WHAT THE ENTERPRISE OWNS" (ERP · EPM · CRM · BI ·
  documents · data platform — green thin-outline nodes, system-of-record
  style); right column "WHAT PEOPLE STILL DO EVERY CYCLE" (collect ·
  reconcile · search · interpret · explain · email · approve · follow up —
  plain ✗-prefixed text lines). Margin strip (Stone): the maturity ladder
  REPORTING → ANALYTICS → PREDICTION → DECISION INTELLIGENCE → ACTION with
  the italic annotation *most organizations stop here* between ANALYTICS and
  DECISION INTELLIGENCE.
- **PROOF / EXAMPLE:** Margin note (Stone, cited): **58%** of finance
  functions already use AI, up 21 points in one year — Gartner, CFO & Finance
  AI Survey, Sept. 2024. Annotation: *adoption is no longer the question;
  control is.*
- **TECHNICAL DEPTH:** EXECUTIVE.
- **BRAND DIRECTION:** Warm Porcelain ground; gold section numeral `01 /`
  with tracked-caps title THE DECISION GAP; hairline rules; Stone margin
  annotations in italic. First use of the footer system (Part C.10).
- **WHAT TO AVOID:** Trash-talking existing systems ("your BI has failed").
  Consulting-deck pain-point clip art. More than the one statistic. Naming
  vendors.

---

## PAGE 3 — 02 / THE DECISION PATH

- **PAGE ROLE:** Introduce the full BENACTA Decision Intelligence
  architecture as one legible map — the page pages 4–6 zoom into.
- **EXECUTIVE QUESTION:** "What does a complete answer look like?"
- **ONE CORE MESSAGE:** A Decision Intelligence System engineers the path
  from enterprise data to governed decisions — every layer has one
  responsibility, every hand-off is explicit and logged.
- **HEADLINE (H1 sans bold):** From enterprise data to governed decisions.
- **OPTIONAL SUBHEAD:** One system, seven responsibilities, one auditable path.
- **BODY COPY (draft, short — the diagram is the page):**
  A Decision Intelligence System does not replace the systems you own. It
  engineers what is missing between them: the path itself. Each layer below
  has a single responsibility, each hand-off is explicit, and every step is
  logged — so any statement the system makes can be traced back to its
  source.
- **VISUAL (dominates the page):** Full-width layered architecture in the
  Note #001 diagram grammar, domain-neutral labels:

  ```text
  ENTERPRISE SYSTEMS          ERP · EPM · CRM · documents · data platforms   (green, thin outline)
        ↓
  BUSINESS SEMANTIC LAYER     business objects · relationships · rules      (blue-grey, thick left edge)
        ↓
  DETERMINISTIC TRUTH         every figure computed by code — the value core (double-stroke border)
        ↓
  CONTEXT                     policies · notes · events · history            (blue-grey)
        ↓
  AI INTERPRETATION           retrieves · explains · drafts · questions —
                              never owns the numbers                         (mineral blue tint)
        ↓ governed draft
  HUMAN JUDGMENT              review · approval · accountability             (solid porcelain fill)
        ↓ approved
  ACTION                      owner · next step · status                     (solid champagne fill — the one action node)
  [right rail]  AUDIT & FEEDBACK · every step logged                         (dashed rail, full height)
  ```

  Margin annotations (italic Stone, business outcomes, Note grammar): *every
  figure computed, none invented* · *the system knows what things mean, not
  just what they total* · *commentary in hours, not days* · *approved before
  it ships* · *insight becomes an owned next step* · *any statement traces to
  its source*.

  Closing line under the schema (the one permitted serif conclusion):
  **Engineer the truth. Augment the judgment.**
- **PROOF / EXAMPLE:** None needed — the map itself. (Proof arrives on p7.)
- **TECHNICAL DEPTH:** EXECUTIVE + ARCHITECTURE (executive labels primary;
  technical sub-labels in Stone caption size).
- **BRAND DIRECTION:** Porcelain ground; section `02 /`; strict charter node
  grammar (Part C.8); exactly one champagne action node; trust boundary NOT
  drawn on this page (it is p5's reveal — here the layers simply stack).
- **WHAT TO AVOID:** Overloading with technical labels (no retrieval scores,
  no model names, no "RAG"). Drawing the trust boundary twice in the
  document. Making layers so abstract they read as slideware — every layer
  keeps a concrete parenthetical.

---

## PAGE 4 — 03 / CONTROLLED INTELLIGENCE

- **PAGE ROLE:** The doctrine, made memorable. The page a reader photographs.
- **EXECUTIVE QUESTION:** "What's the principle I can carry into my next
  steering committee?"
- **ONE CORE MESSAGE:** Divide the work by nature: deterministic code for
  truth, probabilistic AI for interpretation, humans for judgment.
- **HEADLINE (serif display, large, on deep green — semantic color emphasis
  per the charter's statement-card example):**
  Code computes.        (porcelain)
  AI explains.          (mineral blue #6C9BA3)
  Humans decide.        (champagne #BBA06B)
- **OPTIONAL SUBHEAD:** none — the three lines are the page.
- **BODY COPY (draft):**
  Three columns beneath the statement (sans, tracked-caps column heads):

  **CODE** — facts · calculations · metrics · controls · rules
  **AI** — retrieval · context · interpretation · drafting · questions
  **HUMANS** — judgment · approval · accountability · action

  One paragraph (porcelain, body size):
  This is not a restriction on AI. It is the placement that makes AI usable
  in an enterprise: probabilistic intelligence where interpretation adds
  value, deterministic code where truth is non-negotiable, and human
  judgment where accountability lives. Each does what it is structurally
  best at — and nothing else.
- **VISUAL:** Typography-led manifesto. Kicker `BENACTA · CORE DOCTRINE`
  (tracked champagne caps). Chain locator (miniature canonical chain, Stone;
  TRUTH, INTERPRETATION and DECISION segments lit). Triangle signature
  bottom-left, BENACTA wordmark bottom-right (statement-card pattern).
- **PROOF / EXAMPLE:** None. Doctrine pages don't argue; p5 and p7 carry the
  proof.
- **TECHNICAL DEPTH:** EXECUTIVE.
- **BRAND DIRECTION:** The charter's editorial statement-card composition at
  page scale — this is the second dark page. Blue used *only* on the AI line
  (semantic), champagne *only* on the human/decision line and kicker (≤10%
  of composition).
- **WHAT TO AVOID:** Reading as anti-AI — the paragraph exists precisely to
  prevent that. Decorative icons for code/AI/human. A diagram; this page is
  type. Mixing in any other slogan.

---

## PAGE 5 — 04 / THE TRUST BOUNDARY

- **PAGE ROLE:** Turn the doctrine into an architectural mechanism a CIO can
  test — the credibility page.
- **EXECUTIVE QUESTION:** "Concretely, how do I let AI in without letting it
  touch the numbers?"
- **ONE CORE MESSAGE:** Only computed facts cross the boundary — facts above,
  interpretation below — and the proof of a sound boundary is that the AI is
  removable.
- **HEADLINE (H1 sans bold):** Not every part of the system should be
  probabilistic.
- **OPTIONAL SUBHEAD:** none.
- **BODY COPY (draft):**
  A decision system contains three kinds of components, and they must never
  be confused.

  **The system of truth is deterministic.** Every figure is computed by
  code — reproducible, controlled, tested. It never reasons in natural
  language.

  **The system of interpretation is probabilistic — where that is useful.**
  It retrieves context, explains movements, drafts commentary, raises
  questions. It receives computed facts, control alerts and retrieved
  evidence. It never receives the ledger, and it never owns a number.

  **The system of accountability is human.** A named person approves,
  rejects with feedback, escalates and owns. Nothing publishes without
  sign-off.

  The line between them is not a metaphor. It is a design rule: **only
  computed facts cross the boundary.**

  Pull quote (serif, Quote style): *"The LLM is not the system. It is one
  component inside the system."*

  Removability block (bordered callout):
  **The removability test.** Switch the AI off, and every figure, every
  control and every materiality classification must be unchanged — because
  none of it was ever the AI's to compute. In the reference implementation
  this is a permanent automated test, not a claim.
  (Stone footnote, technical: `test_financial_truth_is_independent_from_llm`
  — the truth layer has no import path to any AI component.)
- **VISUAL (dominates):** Three-zone diagram. Top zone SYSTEM OF TRUTH
  (double-stroke border, deterministic engine + controls). Dashed horizontal
  TRUST BOUNDARY exactly in the Note's treatment: label `TRUST BOUNDARY`
  left, `computed facts only` centre, *facts above · interpretation below*
  right italic. Middle zone SYSTEM OF INTERPRETATION (mineral-blue tinted).
  Below it SYSTEM OF ACCOUNTABILITY (solid porcelain node, `controller
  sign-off · human-in-the-loop`) with the return path *rejected, with
  feedback ↺* drawn as a dashed reasoning line back across the boundary.
  Down-arrow labeled `governed draft` between interpretation and
  accountability.
- **PROOF / EXAMPLE:** The removability test (above) — a working, running
  proof, stated in executive language with the test name in a Stone footnote.
- **TECHNICAL DEPTH:** EXECUTIVE + ARCHITECTURE.
- **BRAND DIRECTION:** Porcelain ground; section `04 /`; this is the page
  most visually reminiscent of Note #001's central band — deliberate family
  resemblance. Chain locator: boundary between TRUTH and INTERPRETATION lit.
- **WHAT TO AVOID:** Vendor or model names. "RAG", "vector", "hallucination"
  vocabulary. Fear-based framing ("AI will destroy your books") — the tone
  is placement, not alarm. Re-drawing the entire p3 stack; this page shows
  three zones and one line.

---

## PAGE 6 — 05 / FROM TABLES TO BUSINESS OBJECTS

- **PAGE ROLE:** The foundation idea that separates BENACTA from "we bolted a
  chatbot onto the warehouse" — meaning before intelligence.
- **EXECUTIVE QUESTION:** "Why isn't our existing data model / lake / BI
  semantic layer enough?"
- **ONE CORE MESSAGE:** Decisions happen around business objects and their
  relationships — data only becomes decidable when the system knows what
  things mean.
- **HEADLINE (H1 sans bold):** Decisions happen around business objects —
  not database rows.
- **OPTIONAL SUBHEAD:** none.
- **BODY COPY (draft):**
  A ledger row records that an amount moved. It does not know that the
  amount belongs to a project; that the project serves a customer under a
  contract; that revenue is recognized when milestones are accepted; that a
  forecast depends on those milestones; or that a named person owns the
  outcome. Today, people carry that knowledge in their heads — which is why
  every review starts with reconciliation and ends with "ask whoever built
  the file."

  A **Business Semantic Layer** makes that knowledge part of the system:
  what an object represents, what it relates to, which rules apply to it,
  who owns it, and which decisions can be taken around it. Only then is AI
  given something worth interpreting — and only then can an insight land on
  the person who can act on it.

  Bridge line (closing, leads into p7):
  In July, two customer acceptance milestones slipped — on two different
  projects, for two different customers. Because each milestone is connected
  to its project, its revenue and its owner, the shortfall resolves to named
  work with a named owner rather than to a number. The next page shows that
  month.

  Stone technical footnote: *Technical readers know this layer as a
  lightweight ontology or domain model. The reference implementation keeps
  it deliberately small — objects, relationships, metric definitions,
  ownership — sized to one decision process.*
- **VISUAL (dominates):** Business-object relationship map. Central node
  **PROJECT** (blue-grey, thick left edge — data/semantic style), connected
  by solid hairlines to: CUSTOMER · CONTRACT · MILESTONES · REVENUE &
  FORECAST · COST CENTER · OWNER · MANAGEMENT NOTES · RISKS. Two or three
  edge labels in connector-caps style state the relationship (*recognizes
  revenue on* · *owned by* · *explained in*). Beneath the map, a one-row
  contrast strip: left `A ROW` (mono-style caption: period · account ·
  amount), right `A BUSINESS OBJECT` (project → relationships → rules →
  owner → possible decisions).
- **PROOF / EXAMPLE:** The bridge line to p7; footnote notes the layer exists
  in the reference implementation and rejects rows that don't match the
  governed model (governance, not tolerance).
- **TECHNICAL DEPTH:** EXECUTIVE + ARCHITECTURE.
- **BRAND DIRECTION:** Porcelain ground; section `05 /`; node grammar per
  Part C.8; no AI-blue on this page (there is no AI here — that's the
  point, and the color system should show it). Chain locator: BUSINESS
  OBJECTS lit.
- **WHAT TO AVOID:** The word "ontology" anywhere except the Stone footnote.
  An abstract ER diagram with crow's feet. More than ~9 satellite nodes.
  Any Palantir/Foundry reference — this page expresses the idea as BENACTA's
  own doctrine, full stop.

---

## PAGE 7 — 06 / ONE MONTH, END TO END

- **PAGE ROLE:** Make the architecture tangible — the doctrine applied to one
  month of one company, with real (fictional, test-guaranteed) numbers.
- **EXECUTIVE QUESTION:** "What would my team actually see?"
- **ONE CORE MESSAGE:** The system answers the six questions a decision-maker
  actually asks — what happened, why, what needs attention, what's next, on
  what evidence, and who approved.
- **HEADLINE (H1 sans bold):** One material variance, end to end.
- **OPTIONAL SUBHEAD (kicker above headline, tracked caps):**
  CONTROLLED INTELLIGENCE ARCHITECTURE · FIN-AI-001 · MONTHLY PERFORMANCE
  REVIEW
- **BODY COPY (draft — the page is a composed decision card, not prose):**

  KPI panel (KPI type, tabular figures, values in ink):

  ```text
  REVENUE · JULY FY26
  Actual        €4.72M
  Budget        €5.00M
  Variance      −€280K        (variance line in unfavourable terracotta)
  Variance %    −5.6%         HIGH  (severity mark, terracotta small caps)
  ```

  Six-question card, in order (tracked-caps labels, Body copy):

  **WHAT HAPPENED?** Revenue finished €280,000 below budget for the month.

  **WHY?** Two customer acceptance milestones planned for July were
  rescheduled into August at the customer's request. No scope change, no
  commercial dispute — a timing shift.

  **EVIDENCE** ✓ FY26 Forecast Assumptions § Revenue Recognition Basis ·
  ✓ Management Commentary — July 2026 § Projects Business Unit · ✓ Project
  Milestone Register — FY26 § July 2026 Milestone Status
  *(listed in the order the retrieval layer actually ranks them — the page
  must not present a curated order under a caption that denies curation)*
  *(retrieved by the system with the reason for each selection — not a
  curated list)*

  **WHAT REQUIRES ATTENTION?** HIGH — the variance exceeds the company's
  €100,000 materiality threshold. The threshold itself is written policy the
  system can cite, not an opinion.

  **SUGGESTED FOLLOW-UP** Review milestone recognition with Project Finance.
  *(A proposal for a human — never labeled a decision.)*

  **HUMAN CONTROL** AI-generated interpretation · Controller approval
  required. `[ REQUEST REVISION ]  [ APPROVE ]`

  **OWNER** Project Finance.

  Footer caption (Stone): *All data fictional — Meridian Industrial Group is
  a reference scenario. Every figure above is computed by code and verified
  by automated tests in the reference implementation.*
- **VISUAL:** The decision card dominates — a print rendering of the
  Executive Decision Cockpit's issue view in charter typography (not a
  screenshot; a re-set composition in the same grammar, which prints sharper
  and stays vector). Chain locator: entire chain lit (this page is the whole
  path in one story).
- **PROOF / EXAMPLE:** The numbers are the acceptance criteria of the
  reference implementation (€4.72M / €5.00M / −€280K / −5.6% / HIGH) — they
  are locked and must not drift in production.
- **TECHNICAL DEPTH:** EXECUTIVE.
- **BRAND DIRECTION:** Porcelain ground; section `06 /`; status-color
  extension applies (variance line and severity mark only — KPI values stay
  ink; direction from metric definition, not sign). This page and p8 are
  where the Blueprint visibly *is* the product's editorial family.
- **WHAT TO AVOID:** A raster screenshot (rasterized small type is a charter
  violation). Inventing new numbers or rounding differently from the app
  (€4.72M / €5.00M / −€280K / −5.6% exactly). AI vocabulary in the card.
  Losing the "fictional data" caption.

---

## PAGE 8 — 07 / FROM INSIGHT TO ACTION

- **PAGE ROLE:** BENACTA's differentiation from BI: the loop continues past
  insight into owned action — with honest V1 scope.
- **EXECUTIVE QUESTION:** "And then what happens? Who does something about
  it?"
- **ONE CORE MESSAGE:** A dashboard's job ends when a chart is seen; a
  decision system's job ends when an owned action exists and its outcome is
  recorded.
- **HEADLINE (H1 sans bold, two decks):**
  A dashboard ends at insight.
  A decision system continues into action.
- **OPTIONAL SUBHEAD:** none.
- **BODY COPY (draft):**
  Insight without action is incomplete. In a decision system, an accepted
  interpretation does not stop at "noted" — it becomes an issue with an
  owner, a next step, a status and a due date, and the loop closes when the
  outcome is recorded.

  From the reference implementation's decision log — one issue, carried all
  the way through:

  ```text
  ISSUE          Travel above budget — +€38K, unplanned customer workshops
  REVIEWED BY    A. Controller — "Consistent with the travel policy;
                 workshops were customer-driven."
  OWNER          Cost Center Manager · Projects
  NEXT STEP      Confirm workshop travel against policy and open the
                 missing budget line.
  STATUS         ACTION REQUIRED        DUE  21 AUG 2026
  ```

  Scope honesty block (two-column, tracked-caps heads):
  **THE REFERENCE IMPLEMENTATION** demonstrates the loop at its smallest
  honest size: issue → reviewer → owner → next step → status, every step
  logged. **THE ENTERPRISE DIRECTION** connects the same loop to real task,
  approval and workflow systems, and measures outcomes — decision latency,
  cycle time, adoption — over time.
- **VISUAL (dominates):** Horizontal progression strip in diagram grammar:
  `SIGNAL → ISSUE → CONTEXT → INTERPRETATION → DECISION → OWNER → ACTION →
  OUTCOME`, with the DECISION node porcelain-filled (human) and ACTION the
  page's single champagne node; a thin return arrow OUTCOME → SIGNAL labeled
  *feedback* (dashed). The decision-log record rendered as a quiet bordered
  card beneath. Chain locator: DECISION → ACTION → OUTCOME lit.
- **PROOF / EXAMPLE:** The travel decision-log record above — real output of
  the running implementation (seeded state), not an invented vignette.
- **TECHNICAL DEPTH:** EXECUTIVE.
- **BRAND DIRECTION:** Porcelain ground; section `07 /`; champagne discipline
  (the ACTION node is the page's only champagne fill).
- **WHAT TO AVOID:** Claiming V1 is a workflow platform — the scope-honesty
  block is mandatory, not optional. Workflow-tool vendor names. A second
  champagne node.

---

## PAGE 9 — 08 / HOW TO START

- **PAGE ROLE:** Convert conviction into a credible, commissionable method —
  the consultative bridge to the CTA.
- **EXECUTIVE QUESTION:** "What would we actually do first, and how would we
  know it worked?"
- **ONE CORE MESSAGE:** Start with one recurring decision process, engineer
  its truth before adding AI, and measure against your own baseline.
- **HEADLINE (H1 sans bold):** Start with one decision.
- **OPTIONAL SUBHEAD:** Prove it on one cycle — six to eight weeks — then
  scale.
- **BODY COPY (draft) — the eight-step path (numbered grid, gold numerals):**

  **01 · PICK ONE DECISION PROCESS** — recurring, material, with a named
  owner. The monthly performance review is a natural first candidate.

  **02 · MAP THE BUSINESS OBJECTS** — the entities and relationships the
  decision is actually about, and who owns each.

  **03 · ENGINEER THE TRUTH** — data, metrics, rules and controls, computed
  by code and reconciled to source. This is the value core.

  **04 · ADD CONTEXT** — the policies, notes, events and history that
  explain movements.

  **05 · ADD AI INTERPRETATION** — explanation, comparison, drafting, open
  questions. Computed facts in; a governed draft out.

  **06 · KEEP HUMANS IN CONTROL** — review, approval and escalation as
  designed paths, with rejection a feature, not a failure.

  **07 · CONNECT TO ACTION** — every accepted insight gets an owner, a next
  step and a status.

  **08 · MEASURE OUTCOMES** — against your own baseline: cycle time,
  accuracy, decision latency, analyst capacity, adoption, business result.

  Margin (Stone, cited — example baselines, finance shown because it is the
  reference vertical): top-quartile finance functions close in **≤ 5 days**
  (APQC, Open Standards Benchmarking) and run at **0.55% of revenue vs ~1%
  median** (PwC, Finance Effectiveness Benchmarking 2024). *Your first
  measurement is your own current cycle.*
- **VISUAL:** The numbered path itself — a 2×4 grid of steps (gold numerals,
  tracked-caps step names, one-line descriptions), echoing Note #001's
  principles grid so the two artifacts rhyme. A thin vertical rule links
  steps 03→05→06 with the italic annotation *truth before interpretation,
  humans before action*.
- **PROOF / EXAMPLE:** The two cited baselines; the implicit proof that steps
  01–08 are exactly the layers the reader has just seen working on pages 7–8.
- **TECHNICAL DEPTH:** EXECUTIVE.
- **BRAND DIRECTION:** Porcelain ground; section `08 /`; grid composition;
  gold numerals are the gold budget for this page.
- **WHAT TO AVOID:** Sounding like a generic transformation roadmap (every
  step must use BENACTA's vocabulary: truth, context, interpretation,
  control, action, outcome). Effort estimates or ROI promises. A Gantt
  chart. Using the full "Don't start with AI…" slogan here — it belongs to
  the close; this page's headline deliberately uses only its second half.

---

## PAGE 10 — CLOSE

- **PAGE ROLE:** Land the doctrine, present the proof artifact, open two
  credible doors — and stay premium doing it.
- **EXECUTIVE QUESTION:** "What do I do with this?"
- **ONE CORE MESSAGE:** Don't start with AI — start with the decision; the
  architecture is proven and the conversation is open.
- **HEADLINE (serif display, on deep green, two decks):**
  Don't start with AI.
  *Start with the decision.*
  (line 2 italic champagne — the method principle is this page's single
  slogan statement)
- **OPTIONAL SUBHEAD:** none.
- **BODY COPY (draft):**

  Proof block (hairline-bordered card, porcelain text on dark):
  **PROOF, NOT PROMISES.** A working reference implementation accompanies
  this Blueprint and demonstrates every layer described here: the Business
  Semantic Layer, the Deterministic Core, the Control Engine, Context
  Retrieval, AI Interpretation, Human Review, Decision & Action, and the
  Audit Trail. It runs entirely without an AI key — because the truth never
  depended on one.
  `github.com/anasbenazzouz/benacta-decision-intelligence-blueprint`
  `[ LIVE DEMO — placeholder ]` · `[ QR — placeholder ]`

  Two-lane CTA (two columns, tracked-caps lane titles):
  **FOR DECISION-MAKERS** — If you are choosing the first decision process
  to prove this on, BENACTA can help you scope it. `[ website — placeholder ]`
  · `[ LinkedIn — placeholder ]`
  **FOR YOUR ARCHITECTS** — Send them the reference implementation. The
  boundaries described in this Blueprint are enforced there by tests, not by
  slideware.

  Brand block (canonical positioning, verbatim):
  **BENACTA**
  Enterprise AI · Decision Intelligence
  **AI-Native Decision Systems**
  Turning enterprise data into decisions and action.

  Author line: Anas Benazzouz — BENACTA · AI Engineering · Finance &
  Operations.

  Bottom: supplied **primary dark lockup** (carries the tagline; its triangle
  is this page's single triangle occurrence).
- **VISUAL:** Typography-led dark close; the proof card and CTA lanes are
  quiet hairline structures, not buttons.
- **PROOF / EXAMPLE:** The repository itself, named once, here only.
- **TECHNICAL DEPTH:** EXECUTIVE.
- **BRAND DIRECTION:** Third dark page — bookend symmetry with the cover.
  Slogan surface discipline: method principle as the statement; tagline
  appears only inside the lockup artwork; canonical positioning block
  verbatim from `positioning.md`.
- **WHAT TO AVOID:** Hard-sell ("book a free strategy call now"). More than
  two CTA lanes. Screenshots. A fake QR code (placeholder box labeled QR
  until the owner supplies one). Restating benchmarks or architecture — the
  close asserts, it does not re-argue.

---

# Part C — Visual System (production tokens)

Grounded in `source/brand/Graphical_Design_Final.pdf` (transcribed in
`docs/source-analysis.md` §5), Architecture Note #001, and
`.claude/benacta/brand-system.md`. Items the charter does not fix are marked
**PROJECT INTERPRETATION** — they adapt the locked system to print; they never
override it.

## C.1 Page format & grid

- **Format:** A4 portrait, 210 × 297 mm. **PROJECT INTERPRETATION** (charter
  does not fix a document format; A4 matches the European executive audience
  and the existing BENACTA lead-magnet family).
- **Margins:** 18 mm outer/inner, 16 mm top, 20 mm bottom (footer zone).
  **PROJECT INTERPRETATION.**
- **Grid:** 12 columns, 4 mm gutter; body copy set on a max measure of
  ~66–70 characters; asymmetry embraced when it serves hierarchy (charter
  composition rule). Margin-annotation rail: outer 2 columns on diagram
  pages (Note #001 pattern). **PROJECT INTERPRETATION** (column count).
- **Vertical rhythm:** 4 pt baseline increments. **PROJECT INTERPRETATION.**

## C.2 Backgrounds (max 2 per publication — charter rule)

- **Primary:** Warm Porcelain `#F1E9DA` — pages 2, 3, 5, 6, 7, 8, 9.
- **Secondary:** Deep Heritage Green `#122B20` — pages 1, 4, 10, full-bleed.
- No third background. Sand `#D6BE98` only as a rare small block accent,
  < 3% of the publication (may be zero).

## C.3 Text colors

- **Primary text on porcelain:** Deep Heritage Green `#122B20` (the system's
  ink).
- **Primary text on dark:** Warm Porcelain `#F1E9DA`.
- **Muted / annotations / legends / footnotes / page numbers:** Stone
  `#7C898B` — never for key content.
- **Secondary diagram hierarchy / data-infrastructure meaning:** Heritage
  Blue-Grey `#536875`.
- Porcelain is never used as text on porcelain or white (charter
  prohibition).

## C.4 Champagne (gold) usage — decision, value, action; always scarce

- Section numerals (`01 /` … `08 /`): champagne — `#8F7440` on porcelain
  (text-contrast variant), `#BBA06B` on dark.
- Kickers on dark pages; italic second decks of serif statements (cover,
  close); the single ACTION node fill per diagram; small `APPROVED`-grammar
  tags.
- Hard cap: ≤ 10% of any composition; exactly **one** champagne-filled node
  per diagram; never large fills, never metallic effects.

## C.5 Mineral blue usage — AI meaning only

- `#6C9BA3` on dark, `#54808A` for text on light.
- Permitted: the "AI explains." statement line (p4), AI-layer nodes and
  their tints, the `FROM ARCHITECTURE NOTE N° 001` kicker (p1 — it points at
  the AI-thesis Note), the A of the monogram (inside supplied lockups).
- Forbidden: decorative use with no AI meaning. Pages with no AI content
  (p6) contain no mineral blue.

## C.6 Status colors (owner-approved Phase 6 extension — p7 only)

- Unfavourable `#A05743` (muted terracotta) · Favourable `#4F6B4F` (muted
  sage) · Neutral `#536875`.
- Applied to the variance line and severity marks **only**; KPI values stay
  ink. Direction comes from the metric's definition, never the sign.
- Severity marks: HIGH terracotta · MEDIUM muted gold `#8F7440` · LOW
  blue-grey.

## C.7 Typography

- **Roles (charter-locked):** Libre Caslon Display — logo only, never
  re-typeset (use supplied lockup PNGs). Instrument Sans — the entire
  system; Bold = technical titles, SemiBold = sections, Medium = labels/
  nodes, Regular = body; **no Light weight**. Source Serif 4 — statements
  and quotes only, **never in diagrams** (at most one conclusion line under
  a schema — used once, p3).
- **Print scale — PROJECT INTERPRETATION** (derived by scaling the charter's
  locked desktop hierarchy to A4 print; relative hierarchy is charter law,
  absolute pt values are print adaptation):

  | Style | Spec |
  |---|---|
  | Display (serif statements: p1, p4, p10) | Source Serif 4, 34–40 pt, 1.12, −0.01em |
  | H1 (page headlines) | Instrument Sans Bold, 26–30 pt, 1.15, −0.015em |
  | H2 (closing statements, card heads) | SemiBold, 16–18 pt, 1.25 |
  | H3 | Medium, 12 pt, 1.35 |
  | Body | Regular, 10 pt, 1.6 (Body large 11 pt) |
  | Label / kicker | Medium caps, 8 pt, +0.16em |
  | Caption / footnote / citation | Regular, 8.5 pt, 1.5, Stone |
  | KPI figures | SemiBold, 26–32 pt, 1.05, tabular numerals |
  | Quote (serif pull quotes: p5) | Source Serif 4, 15–16 pt, 1.4 |
  | Section label (`01 / THE DECISION GAP`) | numeral SemiBold champagne + title Medium caps +0.12em, 11 pt |

- **Diagram type (Instrument Sans exclusive):** node title 9.5–10.5 pt
  SemiBold · node description 8–8.5 pt Regular · connector label 7.5 pt
  Medium caps +0.08em · annotation 8 pt Regular Stone (italic for margin
  business-outcome annotations, per Note #001) · legend 8 pt Medium.
- **Absolute print floor: 7.5 pt.** Any label that cannot hold 7.5 pt is
  enlarged, simplified or removed (print translation of the charter's
  25%-zoom survival rule — **PROJECT INTERPRETATION**).

## C.8 Diagram language (all diagrams, one grammar)

Semantic node styling (charter §"architecture grammar"):

| Node type | Style |
|---|---|
| System of record / enterprise systems | Green, thin 1 px outline, porcelain fill |
| Data / semantic-model nodes | Blue-grey, 3 px thick left edge, 1 px hairline elsewhere |
| AI nodes / zones | Mineral blue 1 px stroke, tinted background (mineral blue at ~12% over porcelain — **PROJECT INTERPRETATION** for the tint value) |
| Deterministic / business-rule nodes | **Double-stroke border** (two 1 px lines, 2 px apart) |
| Human approval | **Solid porcelain fill**, 1 px ink border — "the judgment" |
| Action / write-back | **Solid champagne fill** `#BBA06B`, ink text — **one per diagram** |

Lines & connectors:

- Data flow: solid 1–1.5 px hairline. Reasoning / tool call: dashed.
  Controlled action: champagne stroke.
- Arrows: small, quiet hairline triangles; no heavy arrowheads.
- **Trust boundary:** dashed 1 px rule, Note #001 treatment exactly — label
  `TRUST BOUNDARY` (caps, left), `computed facts only` (centre), *facts
  above · interpretation below* (italic, right). Drawn once in the document
  (p5).
- **Audit rail:** vertical dashed rail on the diagram's right edge, rotated
  caps label `AUDIT & FEEDBACK · EVERY STEP LOGGED` (p3).
- Corners square; no drop shadows, no gradients, no glow, no icons inside
  nodes; all diagram text is real (selectable) text, Instrument Sans only.
- **Chain locator (recurring motif, pages 4–8):** one-line miniature of
  `DATA → BUSINESS OBJECTS → TRUTH → CONTEXT → INTERPRETATION → DECISION →
  ACTION → OUTCOME` at connector-label size; active segment(s) in ink (or
  porcelain on dark), inactive in Stone. **PROJECT INTERPRETATION** (new
  motif, composed entirely from charter elements).

## C.9 Dividers, callouts, tables

- Hairline rules: 1–1.5 px; ink at low strength on porcelain (`#122B20` at
  ~20% — **PROJECT INTERPRETATION**) or Stone; porcelain at ~25% on dark.
- Callouts (removability test p5, proof card p10, decision-log card p8):
  1 px hairline border, no fill (or Sand fill ≤ 3% budget), square corners,
  tracked-caps head.
- ✗ / ✓ list grammar (p2): inherited from Note #001's current/target tables —
  ✗ in ink, ✓ in green, mechanism/annotation in italic Stone.

## C.10 Footer, page numbering, naming system

- **Interior pages (2–9):** hairline rule above a one-line footer — left:
  `BENACTA · CONTROLLED INTELLIGENCE BLUEPRINT` (label caps, Stone); right:
  `PAGE 02 / 10` (caption, Stone). Dark pages carry no footer.
- **Section numbering:** interior pages are sections `01 /` through `08 /`
  (gold numeral + tracked-caps title). Cover and close are unnumbered.
- **Naming system:** publication label `BENACTA · N° 001 · CONTROLLED
  INTELLIGENCE BLUEPRINT` (cover). Artifact classes: *Architecture Note* =
  one-page dense poster (LinkedIn); *Blueprint* = multi-page executive
  narrative (lead magnet). The finance instance keeps its architecture ID
  `CONTROLLED INTELLIGENCE ARCHITECTURE · FIN-AI-001` (p7 kicker only).
  **PROJECT INTERPRETATION** (the Blueprint numbering `N° 001`).

## C.11 Logo placement

- **Cover + close:** supplied primary dark lockup PNG
  (`assets/generated/benacta-primary-dark.png`), min 140 px equivalent
  width, protection zone = triangle height on all sides. The lockup's
  triangle counts as the page's single triangle occurrence.
- **Page 4:** standalone triangle signature bottom-left + `BENACTA` wordmark
  (tracked caps text) bottom-right — the statement-card pattern; no lockup.
- **Interior pages:** wordmark in the footer text only; no monogram
  repetition per page.
- Never: stretch, tilt, shadow, outline, recolor, re-typeset, place on any
  blue or busy ground.

---

# Part D — Content Rules

## D.1 Approved vocabulary

Decision Intelligence · AI-Native Decision Systems · Controlled Intelligence
· Decision Cockpit · Deterministic Core · Business Semantic Layer · Trust
Boundary · Human-in-the-Loop · Audit Trail · Decision Workflow · governed
draft · Controller sign-off · "computed facts only" · "facts above,
interpretation below" · "every step logged" · suggested follow-up · the
value core.

Executive/technical pairs (executive form in body, technical form only in
Stone footnotes): Business Semantic Layer ↔ lightweight ontology / domain
model · "the system finds the note that explains the movement" ↔ retrieval ·
"every number remains reproducible" ↔ deterministic code · "a controller
remains accountable" ↔ human-in-the-loop approval workflow.

## D.2 Prohibited

- Clichés: AI revolution · game-changing · unprecedented · transform
  everything · autonomous enterprise · AI-powered (as seasoning) · unlock
  the power of AI · supercharge · 10x · journey.
- Buzzword excess: agentic · autonomous · multi-agent · copilot · prompt
  engineering · LLM-first. ("Governed copilot" only if quoting Note #001 —
  not planned in this document.)
- AI-engineering vocabulary in body copy: RAG, embeddings, vectors, prompts,
  tokens, JSON, hallucination. (The single test name on p5 appears in a
  Stone footnote only.)
- **Palantir / Foundry: zero mentions in this PDF**, in any form.
- "AI Decision" as a label — AI output is a *suggested follow-up*, a
  *decision option* or a *question to investigate*.
- Em-dash chains, exclamation marks, rhetorical hype questions.

## D.3 Claims policy

- Exactly three sourced statistics, each used once, with citation adjacent:
  1. p2 margin: 58% of finance functions already use AI, up 21 pts in one
     year — *Gartner, CFO & Finance AI Survey, Sept. 2024*.
  2. p9 margin: ≤ 5 days monthly close, top quartile — *APQC, Open Standards
     Benchmarking*.
  3. p9 margin: top-quartile finance costs 0.55% of revenue vs ~1% median —
     *PwC, Finance Effectiveness Benchmarking 2024*.
- No other numbers except the fictional reference-scenario figures, which
  are labeled fictional (p7 caption) and are locked to the test-verified
  values: €4.72M · €5.00M · −€280K · −5.6% · HIGH · €100,000 threshold ·
  +€38K travel · due 21 Aug 2026.
- No ROI claims, no market forecasts, no "illustrative" derivations (none
  needed — if one is ever added it carries the *Illustrative:* label).
- No production-readiness or autonomy claims; the p8 scope-honesty block is
  mandatory.
- AI-generated content in the example is explicitly marked: "AI-generated
  interpretation · Controller approval required."

## D.4 Slogan surface map (one role per surface — `positioning.md`)

| Page | Slogan | Role |
|---|---|---|
| 1 (cover) | "An LLM should never own your numbers. It should explain them." | Thesis, as continuity quote |
| 3 | "Engineer the truth. Augment the judgment." | Motto, as the Note-style closing line under the architecture |
| 4 | "Code computes. AI explains. Humans decide." | Core doctrine, as the manifesto |
| 5 | "The LLM is not the system. It is one component inside the system." | Principle 04, as pull quote |
| 10 (close) | "Don't start with AI. Start with the decision." | Method principle, as the closing statement |
| 1 & 10 | "Built on Truth. Designed for Decisions." | Tagline — inside the lockup artwork only, never set as copy |

No page carries two slogan statements. Page 9's headline uses only the
second half ("Start with one decision.") so the close keeps the full
principle.

## D.5 Language

American English throughout; Euros; no first-person plural sales voice
("we deliver…") — the document speaks as doctrine, the CTA speaks as an
invitation. Sentence case for body, tracked caps for labels. Numbers:
€4.72M-style compact for KPIs, €280,000-style full in prose.

---

# Part E — CTA Architecture

The ladder (each artifact opens the next door):

```text
ARCHITECTURE NOTE #001  →  comment BLUEPRINT           (already live)
BLUEPRINT (this PDF)    →  two doors, both quiet:
                            decision-makers → a scoping conversation
                            architects      → the reference implementation
REPOSITORY / DEMO       →  discuss a decision workflow with BENACTA
```

- **Primary CTA (p10):** the two-lane close — *FOR DECISION-MAKERS: if you
  are choosing the first decision process to prove this on, BENACTA can help
  you scope it* / *FOR YOUR ARCHITECTS: send them the reference
  implementation*. Rationale: a CEO/CFO's next credible step is a scoping
  conversation, not GitHub; the architect lane makes forwarding the document
  an action in itself — the most realistic B2B conversion path for a lead
  magnet. No urgency theatrics, no "book now".
- **GitHub placement:** once, p10 proof card
  (`github.com/anasbenazzouz/benacta-decision-intelligence-blueprint`,
  hyperlinked). Pages 5, 7, 8 refer to "the reference implementation" in
  prose without URL — the document stands alone; the close carries the door.
- **Live demo placement:** placeholder slot in the p10 proof card (owner
  supplies URL at release; remove the slot if no demo ships).
- **Website / LinkedIn placement:** placeholders in the p10 decision-maker
  lane and author line. QR: placeholder box on p10 only, replaced or removed
  by the owner at release.
- No CTA anywhere on pages 1–9. The document earns the close.

---

# Part F — Production Instructions for Phase 9

Phase 9 turns this storyboard into `docs/controlled-intelligence-blueprint.html`
and `docs/BENACTA_Controlled_Intelligence_Blueprint.pdf` **without changing
the story**. Copy above is near-final draft: Phase 9 may tighten lines to fit
composition but may not add ideas, pages, sections, statistics or vocabulary.

## F.1 Files & structure

- One self-contained HTML master: `docs/controlled-intelligence-blueprint.html`.
  First line of `<head>`: `<meta charset="utf-8">` (without it, headless
  Chromium mis-decodes UTF-8 glyphs).
- One `<section class="page">` per page, sized exactly 210 mm × 297 mm;
  `@page { size: A4; margin: 0; }`; `break-after: page` on each section; no
  content may rely on browser pagination inside a section.
- All CSS inline in the file (one `<style>` block, tokenized with CSS custom
  properties matching Part C). No JS required for rendering.

## F.2 Fonts & logo

- Vendor WOFF2 locally (e.g. `assets/fonts/`) and load via `@font-face` so
  rendering is deterministic and offline: Instrument Sans 400/500/600/700
  (+ italic 400 for annotations), Source Serif 4 400/600 (+ italics). Both
  are Google Fonts under the SIL Open Font License — include the OFL texts
  alongside. Do **not** load fonts from the network at render time.
- Libre Caslon Display is **not** needed: the logo is never re-typeset. Use
  the supplied lockup PNGs (`assets/generated/benacta-primary-dark.png` for
  dark pages). The p4 triangle signature and wordmark: derive the triangle
  faithfully from the lockup geometry or crop from the supplied packs; the
  wordmark may be set in Instrument Sans tracked caps as the footer wordmark
  is (it is the *wordmark usage*, not the logo lockup).

## F.3 Diagrams

- Inline SVG only; real `<text>` elements (selectable, searchable);
  Instrument Sans; `vector-effect: non-scaling-stroke` on hairlines; node
  grammar and line legend exactly per Part C.8; one champagne node per
  diagram — count them in QA.
- No raster images anywhere except the supplied logo PNGs.

## F.4 Rendering workflow

```powershell
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" `
  --headless=new --no-sandbox --disable-gpu `
  --user-data-dir="$env:TEMP\edge-prof" `
  --no-pdf-header-footer `
  --print-to-pdf="<absolute path>\docs\BENACTA_Controlled_Intelligence_Blueprint.pdf" `
  "file:///<absolute path>/docs/controlled-intelligence-blueprint.html"
```

Then the **mandatory visual QA loop** (never skip, never declare done
without it): render → inspect every page as an image at 100% and at reduced
zoom → compare against Note #001 and the charter transcription → fix →
re-render → re-inspect. QA specifically for: clipped text · overflow ·
awkward breaks · mojibake (·, ✓, ✗, →, €, −) · type below 7.5 pt · more than
one champagne node per diagram · wrong minus signs (use −, U+2212, in
figures) · tabular alignment of KPI digits · footer/page-number continuity ·
PDF metadata (Title: "BENACTA — Controlled Intelligence Blueprint"; Author:
"Anas Benazzouz — BENACTA") · working hyperlink on the GitHub line.

## F.5 Hard guardrails (Phase 9 must re-verify each)

1. Page count: exactly 10. Story order: exactly as Part B.
2. The reference-scenario numbers are locked (D.3 list) — they are enforced
   by the repository's test suite; if a number in the PDF disagrees with the
   app, the PDF is wrong.
3. Three statistics only, with citations, placed per D.3.
4. Zero Palantir/Foundry mentions; zero AI-engineering vocabulary outside
   Stone footnotes; slogan surface map per D.4.
5. Backgrounds: porcelain + deep green only; champagne ≤ 10% per
   composition; blue only with AI meaning; no gradients, glassmorphism,
   glow, icons, rounded-card styling, or template feel.
6. All body text selectable; no rasterized type; no screenshots.
7. If copy overflows a page: cut body copy (in this order: bridge lines →
   second paragraph → margin annotations), never shrink type below the
   floor, never spill to an eleventh page.
8. Do not push, publish or deploy anything.

---

# Part G — Production Record (Phase 9)

Built and rendered. Story unchanged: 10 pages in the Part B order, every
headline, core message and proof as approved.

- **Source:** `docs/controlled-intelligence-blueprint.html` (self-contained;
  inline SVG diagrams; one `<style>` block tokenised to Part C).
- **Output:** `docs/BENACTA_Controlled_Intelligence_Blueprint.pdf` — 10 pages,
  210 × 297 mm, ~253 KB, all text selectable, no rasterised type.
- **Build:** `python scripts/render_blueprint.py` (headless Edge → PDF →
  page images for QA). Fonts: `python scripts/vendor_fonts.py`.

**Deviations from Part C/F, and why.** Three, all typographic fitting:

1. **Arrows and check marks are drawn, not typed.** Neither charter face
   carries `→`, `≤` or `✓` in its Latin subset, so those glyphs silently fell
   back to Segoe UI in the first render. They are now drawn in the charter's
   own connector grammar (a hairline with a small solid head), `≤ 5 days` is
   set as "5 days or fewer", and the code literal on p5 stays in Instrument
   Sans. Every glyph in the PDF is now set in a charter face — verified.
2. **Static font instances instead of variable fonts.** Chromium embeds a
   variable instance as a Type3 font; static instances give CID subsets and cut
   the file from 672 KB to 253 KB.
3. **Two of the three edge labels on p6 were dropped** in favour of one caption
   line beneath the map ("Every line is a relationship the system knows…").
   At the 7.5 pt floor the labels could not clear the PROJECT node. "governs"
   is kept.

**Interpretation added in production:** diagram panels on p3 sit on a 5.5%
ink tint so that a *solid porcelain fill* — the charter's mark for human
judgment — reads as a fill rather than as the page ground. No new colour is
introduced; it is a transparency of the ink.

**Visual QA:** three render–inspect–fix cycles over all 10 pages. Defects
found and fixed: an L-shaped `<path>` missing `fill:none` (filled black
wedges, p6); a grid that never applied because a modifier class carried no
`display:grid` (p7 collapsed and overflowed); zone headings colliding with
nodes and a rejection path crossing body text (p5); label/box collisions and a
clipped annotation (p6); a caption crossing connector stubs (p2); "THE VALUE
CORE" overrunning its panel and a margin annotation overrunning into the
diagram (p3); a feedback caption sitting on its own dashed line (p8); orphaned
last words in four headlines; hollow whitespace on p3/p7/p9.

**Verified on the finished PDF:** 10 pages, no blanks · forbidden-term scan
clean (no Palantir/Foundry, no clichés, no AI-engineering vocabulary, no "AI
Decision") · every figure matches the running implementation (`€4.72M`,
`€5.00M`, `−€280K`, `−5.6%`, `€100,000`, `€38,000`, `+31.1%`, 21 Aug 2026) ·
exactly three sourced statistics, each with its citation · fictional-data
notice present · one champagne action node per diagram, none elsewhere ·
smallest type 7.5 pt · GitHub link live · metadata stamped.
