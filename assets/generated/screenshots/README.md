# Cockpit screenshots

Every image here was captured from the running application
(`DEMO_MODE=true streamlit run app.py`) against the committed fictional
dataset. Nothing is a mockup, a render or a retouched frame — what the
screenshots show is what the code produces.

| File | View | Proves |
|---|---|---|
| `01-executive-decision-cockpit.png` | Executive Decision Cockpit, first load | *What happened?* — the four governed metrics, calculated by code |
| `02-revenue-attention-detail.png` | Attention list, ranked | *What requires attention?* — control findings ordered by materiality |
| `03-evidence-interpretation.png` | Revenue issue detail | *Why?* — AI interpretation beside the figures it was given, with quoted evidence |
| `04-human-review-action.png` | Review + decision log | *Who decides?* — controller sign-off and the issue → owner → next step trail |
| `05-architecture-trust-boundary.png` | Architecture view · layer stack | *This is an architecture* — the trust boundary drawn explicitly |

## Recapturing after a UI change

Viewport **1600 × 1000**, light colour scheme (the charter's porcelain
ground — do not capture in a forced dark OS theme). Reviewer field left at
its default, `A. Controller`. Capture on a fresh session so the entrance
animation and the seeded demo state are in their first-run position, and
crop to the content area — no OS window chrome, no browser tab bar.

Shot 04 is taken *after* pressing **Send for controller review**, so the
stepper shows the `Controller review` stage active with the
Approve / Request-revision controls visible; the initial `AI draft` state
is a less informative frame.
