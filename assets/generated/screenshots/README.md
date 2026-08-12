# Cockpit screenshots — capture instructions

No screenshots are committed here yet: the app is verified end to end
headlessly, and no image is committed that was not captured from the running
cockpit. This file specifies exactly what to capture and how, so the shots can
be taken manually without guessing at intent.

## Setup

```bash
DEMO_MODE=true streamlit run app.py
```

- Viewport: **1600 × 1000**, light color scheme (the charter's porcelain
  ground; do not capture in a forced dark OS theme).
- Reviewer field in the sidebar left at its default, `A. Controller`.
- Take each screenshot on a **fresh session** (first load) unless a step
  says otherwise, so the one-time entrance animation and the seeded demo
  state (`seed_demo_state` in `app.py`) are in their intended first-run
  position.
- Crop to the content area; exclude the OS window chrome and browser tab
  bar. PNG, no compression artifacts on the typography.

## The five shots

### 01 — Executive Decision Cockpit
**Proves:** *"What happened?"*
**State:** Default view, first load, sidebar open. Scroll position: top of
page, hero band and the four-KPI band both fully visible.
**Crop:** Full width, from the hero band down through the KPI band and the
first two or three rows of the attention list.
**File:** `01-executive-cockpit.png`

### 02 — Attention / decision detail
**Proves:** *"What requires attention?"*
**State:** Default view, the HIGH-severity **Revenue** issue selected in
the attention list (it is the first item and is selected by default —
confirm the champagne-tinted selection state is visible on that row).
**Crop:** The attention list (all 5 ranked rows) together with the "03 ·
Why · root cause analysis" section heading and the root-cause block below
it (Actual/Budget/Variance table + the root-cause title and impact).
**File:** `02-attention-and-detail.png`

### 03 — Evidence + interpretation
**Proves:** *"Why?"*
**State:** Same Revenue issue selected. Scroll to the AI-generated
interpretation block ("04 · What evidence supports this") so all evidence
cards are visible.
**Crop:** The AI-generated interpretation block at the top of the issue
detail, down through the evidence blocks (quoted snippets with their
document § section references).
**File:** `03-evidence-and-interpretation.png`

### 04 — Human review + action
**Proves:** *"Humans remain accountable, and insight becomes action."*
**State:** The Revenue issue, scrolled to "06 · Who approves · who owns the
next step". Trigger **Send for controller review** first so the workflow
stepper shows the `Controller review` stage active with the
Approve/Request-revision controls visible (a more interesting frame than
the initial `AI draft` state).
**Crop:** The workflow stepper plus the review-action panel below it.
**File:** `04-human-review-and-action.png`

### 05 — Architecture view
**Proves:** *"This is an architecture, not a chatbot."*
**State:** Switch to the **Architecture** view in the sidebar. Scroll to
"01 · The layer stack" so the full SVG diagram is visible (green
deterministic core, mineral-blue AI layer, porcelain human-approval band,
the single champagne action node, and the dashed trust-boundary line
between retrieval and AI interpretation).
**Crop:** The layer-stack diagram in full, including its labels.
**File:** `05-architecture-view.png`

## After capturing

1. Save all five PNGs directly in this folder (`assets/generated/screenshots/`).
2. Replace the `<!-- SCREENSHOTS_SECTION -->` placeholder block in the root
   `README.md` "See it" section with the five images (suggested: a 2-3-column
   markdown table or simple sequential `![](…)` embeds, each with the one-line
   caption already given above — *"What happened?"*, *"What requires
   attention?"*, etc.).
3. Re-run the reduced-motion check from `docs/ui-qa.md` if re-capturing after
   a UI change, so screenshots don't freeze mid-animation.
