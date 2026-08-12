# BENACTA — Claude Code Execution Playbook
## Empty folder → public-ready Decision Intelligence Blueprint

This file tells you **exactly what to do, in what order, and which Claude model to use**.

The goal is to avoid wasting frontier-model usage on repetitive implementation while still using the strongest reasoning at the moments where it has the highest leverage.

---

# 1. Model routing strategy

Use the models differently.

| Model | Use it for | Do NOT waste it on |
|---|---|---|
| **Fable 5** | doctrine, architecture, ambiguity resolution, brand/source interpretation, major design review, final ruthless audit | routine file edits, repetitive CSS tweaks, simple tests |
| **Opus 5** | primary builder: coding, application integration, PDF system, debugging, architecture implementation | trivial renames / mass formatting |
| **Sonnet 5** | bounded implementation, unit tests, cleanup, documentation passes, UI polish, repetitive fixes | final architecture decisions if Fable/Opus is available |

**Fallback:** if Fable 5 is unavailable or would consume paid usage credits you do not want to use, replace each Fable phase with **Opus 5 at high/max effort**.

---

# 2. Final local folder before Claude starts

Start with:

```text
benacta-decision-intelligence-blueprint/
│
├── 00_START_HERE_BENACTA.md
├── 01_MASTER_BRIEF_BENACTA.md
├── 02_EXECUTION_PLAYBOOK_CLAUDE_CODE.md
│
└── source/
    ├── brand/
    ├── architecture-note/
    └── reference/
```

Put your files here:

```text
source/brand/
    BENACTA graphical charter
    logos
    any brand assets

source/architecture-note/
    Architecture Note 001 PDF
    Architecture Note 001 PNG if available

source/reference/
    any positioning / philosophy / architecture material
```

Do not rename the source PDFs unless necessary.

---

# 3. Before opening Claude Code

In a terminal, enter the empty project folder.

Recommended checks:

```bash
git init
git status
```

Do not create the full application tree yourself.

Let Claude create it after it understands the supplied material.

Open Claude Code:

```bash
claude
```

Then check:

```text
/status
```

and choose the model with:

```text
/model
```

Use the model picker if aliases differ in your installation.

---

# PHASE 0 — SOURCE INGESTION
## Model: FABLE 5
## Goal: Understand BENACTA before touching code

Select Fable.

Do not ask it to build the project yet.

Send:

```text
Read these files completely before doing anything else:

- 00_START_HERE_BENACTA.md
- 01_MASTER_BRIEF_BENACTA.md
- 02_EXECUTION_PLAYBOOK_CLAUDE_CODE.md
- every file under /source

This is a SOURCE-INGESTION phase only.

Do not implement the application yet.

Your tasks:

1. Inventory every supplied source file.
2. Extract the BENACTA positioning.
3. Extract the exact graphical system from the supplied brand charter:
   - colors
   - typography
   - spacing principles
   - logo rules
   - visual motifs
   - tone
4. Analyze Architecture Note #001:
   - core thesis
   - information hierarchy
   - architecture vocabulary
   - visual language
   - design principles
5. Reconcile the supplied materials with the Decision Intelligence direction in 01_MASTER_BRIEF_BENACTA.md.
6. Identify ambiguities or contradictions.
7. Resolve minor ambiguities conservatively.
8. Flag only genuine blockers.
9. Create a written source-analysis at:
   docs/source-analysis.md

Do not create production code.

At the end, give me:
- the 10 most important BENACTA rules you inferred
- what absolutely must not be lost during implementation
- any genuine blocker

If there is no genuine blocker, stop after the analysis and wait.
```

### Your checkpoint

Read Claude's summary.

You should see:

- Finance as first vertical, not entire brand
- Decision Intelligence as larger category
- deterministic truth
- semantic/business-object layer
- AI interpretation
- human control
- action/workflow
- Foundry-like inspiration without cloning
- exact visual charter extracted from your files

If Claude misunderstands one of these, correct it **now**, not after coding.

---

# PHASE 1 — CREATE THE BENACTA PROJECT BRAIN
## Model: FABLE 5
## Goal: Make the repo remember the doctrine

Still on Fable.

Send:

```text
Good. Now create the persistent BENACTA project knowledge described in 01_MASTER_BRIEF_BENACTA.md.

Create or update:

CLAUDE.md

.claude/benacta/
- positioning.md
- decision-intelligence.md
- architecture-principles.md
- brand-system.md
- content-system.md
- vocabulary.md
- anti-patterns.md

Requirements:

1. Base brand-system.md on the actual supplied graphical charter, not on guesses.
2. Base content-system.md on Architecture Note #001 and the BENACTA editorial system.
3. Explicitly capture:
   DATA → BUSINESS OBJECTS → TRUTH → CONTEXT → INTERPRETATION → DECISION → ACTION → OUTCOME
4. Explicitly capture:
   CODE COMPUTES. AI EXPLAINS. HUMANS DECIDE.
5. Explicitly capture the Foundry-like inspiration as a conceptual architecture pattern only.
6. Explicitly forbid:
   - Palantir branding imitation
   - chatbot-first UI
   - autonomous CFO language
   - generic AI gradients
   - needless agentic complexity
7. Add clear instructions for future Claude sessions to consult these files before architectural or visual changes.

Do not implement the product yet.

After writing the files, review them once for contradictions and duplication.

Then give me a concise summary of what is now permanently encoded.
```

### Checkpoint

Open and skim:

```text
CLAUDE.md
.claude/benacta/*
```

Do not skip this.

This is what prevents later sessions from drifting.

---

# PHASE 2 — ARCHITECTURE & ACCEPTANCE PLAN
## Model: FABLE 5
## Goal: Decide what V1 is — and what V1 is not

Send:

```text
Now design V1 before coding.

Using the supplied source material, the new .claude knowledge base and 01_MASTER_BRIEF_BENACTA.md:

Create:

docs/implementation-plan.md
docs/architecture.md
docs/acceptance-criteria.md

The plan must define:

1. the thin vertical slice
2. the fictional management story
3. business objects and relationships
4. deterministic finance calculations
5. control/materiality rules
6. context retrieval
7. demo-mode interpretation
8. optional LLM interpretation
9. controller review
10. decision/action state
11. audit trail
12. executive UI
13. architecture/engineering UI
14. README
15. PDF generation
16. tests

Create explicit NON-GOALS.

Do not build:
- real ERP connectors
- complex ontology platform
- multi-agent systems
- microservices
- Kafka
- Kubernetes
- React/Next.js
- production authentication
- generic workflow engine

Use one coherent reference scenario.

Before finishing, attack your own architecture:
- Is anything unnecessary?
- Is anything missing to support the Decision Intelligence claim?
- Does the semantic/business-object layer add real explanatory value?
- Can the AI layer be completely disabled without breaking financial truth?

Make corrections now.

Do not write application code yet.

Finish with a proposed repository tree and implementation order.
```

### Gate to continue

Only continue if V1 can be explained in one sentence:

> A small monthly-performance Decision System that computes financial truth deterministically, retrieves business context, drafts an explanation, requires human review, and records the resulting action.

If it sounds bigger than this, shrink it.

---

# PHASE 3 — BUILD THE DETERMINISTIC CORE
## Model: OPUS 5
## Goal: Prove the architecture from the inside out

Switch to Opus.

Send:

```text
Implement ONLY the deterministic foundation described in the approved implementation plan.

Build:

- project package structure
- fictional coherent finance dataset
- src/domain.py
- src/finance_engine.py
- src/control_engine.py
- core tests

Requirements:

1. Use entirely fictional data.
2. Implement the business-object / semantic layer simply and clearly.
3. Compute all financial truth deterministically.
4. Implement transparent materiality/control rules.
5. Do not build Streamlit yet.
6. Do not build the AI layer yet.
7. Do not generate the PDF yet.

Tests must cover:
- actual
- budget
- variance
- variance %
- missing budget
- materiality
- control severity
- business object mapping

Most important:
create and pass a test named:

test_financial_truth_is_independent_from_llm

Even though the LLM layer is not yet implemented, structure the test so the truth layer has no dependency on it.

Run all tests.

Do not stop until they pass.

At completion report:
- files created
- test result
- one sample financial fact
- one sample control alert
- any deliberate simplification
```

### Checkpoint

Do not judge UI. There is none yet.

Verify the result makes sense as Finance.

---

# PHASE 4 — CONTEXT, INTERPRETATION, HUMAN CONTROL, ACTION
## Model: OPUS 5
## Goal: Complete the Decision Intelligence loop

Still on Opus.

Send:

```text
Continue V1 by implementing the layers above deterministic truth.

Build:

- fictional context documents
- src/retrieval.py
- src/commentary.py
- src/approval.py
- src/decision_log.py
- src/audit.py

Requirements:

CONTEXT
- transparent retrieval
- evidence returned with source document and snippet
- no vector database in V1 unless there is an overwhelming reason

COMMENTARY
- DEMO_MODE=true must work with no API key
- demo commentary must be evidence-based
- optional real LLM support can be added behind a small provider interface
- the LLM receives computed facts, never authority over truth
- no invented numbers
- no unsupported causal claims
- distinguish evidence from inference
- expose confidence

HUMAN CONTROL
- DRAFT
- AWAITING_REVIEW
- APPROVED
- REVISION_REQUESTED

ACTION
- OPEN
- UNDER_REVIEW
- ACTION_REQUIRED
- CLOSED
- owner
- next step
- due date if useful

AUDIT
Record:
- source data
- calculation
- control rule
- retrieved evidence
- interpretation mode
- model if used
- reviewer
- decision/action
- timestamps

Add tests for all deterministic state transitions and key retrieval behavior.

Run all tests.

Then run a small command-line or Python smoke demonstration proving:

TRUTH → CONTEXT → INTERPRETATION → REVIEW → ACTION → AUDIT

Do not build the final UI yet.
```

---

# PHASE 5 — EXECUTIVE DECISION COCKPIT
## Model: OPUS 5
## Goal: Make it understandable to CFO/CEO in 2 minutes

Send:

```text
Now build the Streamlit application.

The default view is an EXECUTIVE DECISION COCKPIT.

Read:
- .claude/benacta/brand-system.md
- .claude/benacta/content-system.md
- source brand assets
- Architecture Note #001

Before coding the UI, restate the exact visual rules you will apply.

Then implement.

The executive view must prioritize:

1. WHAT HAPPENED?
2. WHY?
3. WHAT REQUIRES ATTENTION?
4. WHAT COULD WE DO NEXT?
5. WHAT EVIDENCE SUPPORTS THIS?
6. WHO APPROVED / OWNS THE NEXT STEP?

Primary KPI set:
- Revenue
- Gross Margin
- Operating Expenses
- EBITDA

Do not make the main screen a generic dashboard.

Do not make the main interaction a chat box.

Do not expose RAG/vector/prompt terminology in the default executive experience.

Include a secondary Architecture / Engineering view showing:
- source
- business semantic layer
- deterministic core
- controls
- context layer
- AI interpretation
- human review
- action
- audit trail

Use the exact BENACTA visual charter.

Run the app.

Inspect the rendered result if your tools allow it.

Fix:
- spacing
- hierarchy
- contrast
- mobile/normal viewport issues
- inconsistent typography
- generic Streamlit appearance where feasible

Do not generate the final PDF yet.
```

### Human checkpoint

Open the app yourself.

Ask only:

> If I were a CFO who knew nothing about RAG, would I understand the value in 60–120 seconds?

If no, do not add features. Simplify the UI.

---

# PHASE 6 — BOUNDED UI POLISH & TEST CLEANUP
## Model: SONNET 5
## Goal: Cheap, focused quality pass

Switch to Sonnet.

Send:

```text
Perform a bounded quality pass.

Do not change the architecture.
Do not add product scope.
Do not add new major features.

Focus on:

1. broken imports
2. test coverage gaps
3. naming consistency
4. dead code
5. duplicate code
6. Streamlit state bugs
7. formatting
8. clear executive copy
9. typos
10. visual consistency with .claude/benacta/brand-system.md

Run the full test suite.

Run the app.

Fix all obvious quality issues.

Then produce:
docs/ui-qa.md

with:
- issues found
- issues fixed
- anything intentionally left simple

Stop after this bounded cleanup.
```

---

# PHASE 7 — README + PUBLIC GITHUB PACKAGE
## Model: OPUS 5
## Goal: Make GitHub credible to executive and technical readers

Switch to Opus.

Send:

```text
Create the public-facing GitHub package.

Write or rewrite README.md according to 01_MASTER_BRIEF_BENACTA.md.

Critical rule:
THE README MUST BE EXECUTIVE-FIRST.

The first screen must not contain installation commands.

The sequence should be:

1. BENACTA positioning
2. thesis
3. business problem
4. one concrete business example
5. business architecture
6. why the trust boundary matters
7. what the demo shows
8. screenshots placeholders
9. technical architecture
10. quick start
11. repository structure
12. tests
13. limitations
14. roadmap
15. BENACTA / CTA

Use Mermaid for architecture where useful.

Also create:
- docs/implementation-guide.md
- docs/demo-script.md
- assets/generated/.gitkeep if needed

Create a concise 3-minute demo script for a CFO and a separate 5-minute demo script for an architect.

Audit the repository for:
- secrets
- real client information
- internal paths
- absolute local paths
- junk files
- TODOs that undermine credibility

Do not push to GitHub.

At the end, show:
- proposed repo description
- proposed GitHub topics
- proposed release title
```

---

# PHASE 8 — EXECUTIVE PDF CONTENT & DESIGN SYSTEM
## Model: FABLE 5
## Goal: Decide the story before generating pages

Fable is used here because the PDF is not merely documentation; it is a positioning asset.

If Fable usage credits are not worth spending, use Opus 5 at max/high effort.

Send:

```text
Now act as:

- CFO audience editor
- enterprise architecture storyteller
- BENACTA brand director
- information designer

Do NOT generate the PDF yet.

First design the editorial story for:
BENACTA_Controlled_Intelligence_Blueprint.pdf

Read:
- source graphical charter
- Architecture Note #001
- .claude/benacta/brand-system.md
- .claude/benacta/content-system.md
- current working application
- README
- 01_MASTER_BRIEF_BENACTA.md

Create:
docs/pdf-storyboard.md

For each page define:
- page objective
- one key message
- headline
- supporting copy
- diagram / visual
- proof / example
- CTA if any
- visual hierarchy
- which brand rule it uses

Use approximately 8–10 pages.

The story must work for CEO/CFO/CIO audiences.

Avoid:
- generic AI education
- long technical passages
- excessive Foundry references
- Palantir branding
- buzzword density
- hype claims

The PDF should communicate a proprietary BENACTA point of view:
governed truth → context → human judgment → action.

Review the storyboard as a CFO and remove anything that is not decision-relevant.

Stop after storyboard approval.
```

### Human checkpoint

Read the storyboard.

If page 7 says "Foundry-like principle", consider whether the public version should instead say:

> **From tables to business objects**

You can discuss Foundry in technical material, but the public executive document should feel like **BENACTA's own doctrine**, not borrowed positioning.

---

# PHASE 9 — GENERATE THE PDF
## Model: OPUS 5
## Goal: Production execution

Switch to Opus.

Send:

```text
Implement the approved PDF storyboard.

Create:
- docs/controlled-intelligence-blueprint.html
- any local CSS/assets required
- docs/BENACTA_Controlled_Intelligence_Blueprint.pdf

Strict requirements:

1. Use the exact BENACTA graphical charter supplied in /source.
2. Stay visually consistent with Architecture Note #001.
3. Do not create a generic Markdown-to-PDF document.
4. Use a maintainable HTML/CSS or appropriate programmatic layout.
5. Prefer vector/SVG diagrams.
6. Keep text selectable where possible.
7. Use strong whitespace.
8. Use restrained visual hierarchy.
9. No clipped content.
10. No awkward page breaks.
11. No tiny unreadable labels.
12. No invented benchmark claims.
13. No unsupported factual claims.
14. No Palantir logo, screenshots, branding or implied affiliation.

After rendering:
- inspect every page visually
- compare with the graphical charter
- compare with Architecture Note #001
- identify layout defects
- fix them
- render again
- inspect again

Do not call the PDF complete until the visual QA is finished.

Also export a small contact sheet / preview if useful for review.

At the end report:
- PDF path
- HTML source path
- visual QA issues found and fixed
```

---

# PHASE 10 — VISUAL / EXECUTIVE RED TEAM
## Model: FABLE 5
## Goal: Find what everyone else missed

Use Fable for one high-value final review.

Send:

```text
Perform a ruthless review of the ENTIRE project.

Do not add scope.

Act as four independent reviewers:

REVIEWER 1 — CFO

Questions:
- Can I understand the business value in under 3 minutes?
- Is this clearly more than a chatbot?
- Do I understand what happened, why, what needs attention, evidence, and next action?
- Does anything sound like AI hype?
- Does the project respect controller accountability?

REVIEWER 2 — ENTERPRISE ARCHITECT

Questions:
- Are responsibilities clean?
- Is the business semantic layer meaningful?
- Is the deterministic/probabilistic boundary explicit?
- Is lineage understandable?
- Is this a Decision Intelligence architecture rather than a RAG demo?
- Does the implementation support future expansion without pretending to be a full platform?

REVIEWER 3 — AI ENGINEER

Questions:
- Is financial truth independent from the LLM?
- Can AI be disabled completely?
- Are evidence and generated interpretation separated?
- Are tests meaningful?
- Does anything falsely imply production readiness?
- Are there hidden calculations happening in the LLM layer?

REVIEWER 4 — BENACTA BRAND DIRECTOR

Questions:
- Does the app match the supplied brand charter?
- Does the PDF belong to the same family as Architecture Note #001?
- Does this feel premium, editorial and enterprise?
- Is anything generic SaaS, gimmicky or visually AI-cliché?
- Is the BENACTA vocabulary coherent?

Create:
docs/final-red-team.md

Rank findings:
P0 = blocks release
P1 = significantly weakens credibility
P2 = polish

Then fix all P0 and P1 issues.

Do not add major features.

Run:
- tests
- app smoke test
- PDF render
- PDF visual inspection

Then give a release recommendation:
GO / NO-GO

with reasons.
```

---

# PHASE 11 — FINAL BOUNDED FIX PASS
## Model: SONNET 5
## Goal: Fix remaining P2s cheaply

If the red team returns small corrections, switch to Sonnet.

Send:

```text
Apply only the remaining P2 release-polish items from docs/final-red-team.md.

Do not change:
- core architecture
- product scope
- brand doctrine
- executive narrative

Allowed:
- copy edits
- spacing
- minor CSS
- naming consistency
- README cleanup
- tests
- dead code cleanup
- small visual fixes

Run all tests and regenerate the PDF if any visual source changed.

Stop when the P2 list is complete.
```

---

# PHASE 12 — RELEASE PACKAGE
## Model: OPUS 5
## Goal: Prepare everything you need for LinkedIn → Blueprint → Demo → GitHub

Send:

```text
Prepare the public release package.

Do not publish or push remotely.

Create:
docs/release-package.md

Include:

1. FINAL ASSET MAP

LinkedIn:
- Architecture Note #001

Lead magnet:
- BENACTA_Controlled_Intelligence_Blueprint.pdf

Live experience:
- Decision Cockpit

Technical proof:
- GitHub repository

2. PERSONA ROUTING

For CEO/CFO:
what should I send first?

For CIO/Architect:
what should I send first?

For AI/Data Engineer:
what should I send first?

3. LINKEDIN CTA

Write the exact short CTA for:
Comment BLUEPRINT

4. DM RESPONSE

Write:
- short version
- warm version
- executive version

for people who comment BLUEPRINT.

5. GITHUB

Provide:
- repo name
- description
- topics
- release title
- release description
- suggested social preview text

6. SCREENSHOTS

List the 5 strongest screenshots to capture.

For each:
- view
- state
- crop
- message it proves

7. DEMO SCRIPT

Produce:
- 30-second explanation
- 2-minute CFO walkthrough
- 5-minute architecture walkthrough

8. WEBSITE COPY

Provide:
- 1-sentence description
- short blueprint landing-page copy
- CTA

9. FINAL CHECKLIST

Create a release checklist I can tick manually.

Do not push to GitHub.
Do not deploy unless I explicitly instruct you.
```

---

# PHASE 13 — MANUAL GITHUB RELEASE
## Model: No frontier model required

You do this yourself after reviewing the files.

Recommended local checks:

```bash
git status
git diff
```

Run tests using the project's documented command.

Run Streamlit using the project's documented command.

Open the PDF manually.

Check:
- title
- author/brand
- hyperlinks
- no personal local paths
- no accidental client names
- no secrets
- no broken screenshots

Then:

```bash
git add .
git commit -m "Release BENACTA Decision Intelligence Blueprint v0.1"
```

Create the GitHub repository manually.

Recommended repository name:

```text
benacta-decision-intelligence-blueprint
```

Then connect and push using the exact commands GitHub gives you.

Do not blindly copy a remote URL from an AI response.

---

# PHASE 14 — DEPLOYMENT
## Model: OPUS 5 or SONNET 5
## Goal: Live demo only after local V1 is good

Do this only after GitHub is clean.

Ask Claude:

```text
The local V1 is approved.

Now prepare the simplest reliable public deployment for the Streamlit Decision Cockpit.

Constraints:
- no production overengineering
- no real enterprise data
- demo mode must be default
- no API key required for visitors
- no secrets in repository
- lowest-maintenance deployment possible

First recommend the deployment approach and explain tradeoffs briefly.

Then make only the required repository changes.

Do not deploy or create external accounts unless I explicitly ask.
```

---

# 4. Model-budget optimization

## Fable 5 — spend it only at high-leverage moments

Use for:

1. Source interpretation
2. `.claude` doctrine
3. V1 architecture
4. PDF story
5. final red-team

That is approximately **5 focused sessions**, not "use Fable for everything".

## Opus 5 — main workhorse

Use for:

1. deterministic core
2. context + workflow
3. executive UI
4. README
5. PDF implementation
6. release package

## Sonnet 5 — bounded cleanup

Use for:

1. tests
2. UI cleanup
3. documentation polish
4. P2 fixes
5. simple deployment changes if desired

---

# 5. Anti-context-bloat rule

Do not keep one Claude Code conversation alive forever.

At meaningful phase boundaries:

1. commit or preserve files
2. start a fresh Claude Code session if the context has become noisy
3. tell the new session to read:
   - `CLAUDE.md`
   - `.claude/benacta/*`
   - `docs/implementation-plan.md`
   - the relevant phase prompt

This is exactly why the persistent project knowledge exists.

Do not repeatedly paste the entire master prompt once it is encoded in the repo.

---

# 6. When a new session starts

Use this short boot prompt:

```text
Before doing any work:

1. Read CLAUDE.md.
2. Read all files under .claude/benacta/.
3. Read docs/implementation-plan.md and docs/acceptance-criteria.md if they exist.
4. Read the current git status and relevant code.
5. Do not change BENACTA architecture or visual doctrine without explicit justification.

Current phase:
[WRITE THE PHASE NAME]

Current objective:
[WRITE THE OBJECTIVE]

Do only this phase.
Run the relevant checks before stopping.
```

---

# 7. Git commit cadence

Recommended commits:

```text
chore: initialize BENACTA project context

docs: define decision intelligence architecture

feat: add deterministic finance truth layer

feat: add context interpretation and approval flow

feat: add executive decision cockpit

docs: add executive-first public README

feat: add controlled intelligence blueprint PDF

fix: apply final architecture and brand review

release: prepare v0.1 public blueprint
```

This makes the public repo itself tell a credible engineering story.

---

# 8. Release gates

Do not release unless all are true.

## Gate A — Truth
- deterministic calculations tested
- AI can be disabled

## Gate B — Evidence
- explanations show supporting sources
- unsupported causality is avoided

## Gate C — Human
- review / approval is visible
- accountability is explicit

## Gate D — Action
- at least one issue can become an owner + next step

## Gate E — Executive
- default screen understandable without AI vocabulary

## Gate F — Architecture
- semantic/business-object layer exists and is meaningful
- trust boundary is explicit

## Gate G — Brand
- app and PDF visually belong to BENACTA
- Architecture Note #001 and Blueprint feel related

## Gate H — Public hygiene
- no secrets
- no client data
- no broken setup
- no accidental absolute paths

---

# 9. The single sentence you should keep testing

If the project drifts, return to this:

> **BENACTA demonstrates how governed enterprise truth becomes context, human judgment and action — without making the LLM the system of record.**

If a feature does not strengthen that sentence, it probably does not belong in V1.
