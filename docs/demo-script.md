# BENACTA Demo Script

> Three walkthroughs of the same running app (`DEMO_MODE=true streamlit run app.py`), scaled to how much time the audience has. Same story, same numbers, every time see `docs/architecture.md` and the README's worked example for the full reference scenario.

## 30-second explanation

> "This is a working reference implementation of a Decision Intelligence system. Code computes every financial figure actual, budget, variance deterministically, from a fictional monthly close. Transparent rules flag what's material. The system retrieves the business context that explains a movement, and AI drafts an interpretation from that never from the raw numbers themselves. A controller has to approve it before it means anything, and every step is logged. If you removed the AI layer entirely, the numbers wouldn't change that's the point, and there's a test that proves it."

Say this before opening the app. It's the whole thesis in one breath.

## 2-minute CFO walkthrough

Open the **Executive Decision Cockpit** (default view). Don't explain the architecture yet let the screen answer the questions in order.

1. **What happened?** Point at the KPI band. "Revenue finished at €4.72M against a €5.00M budget €280,000 below plan, −5.6%. Gross Margin, Operating Expenses and EBITDA are all computed the same way, from the same ledger."
2. **What requires attention?** Point at the ranked attention list. "Five items, ranked HIGH to MEDIUM. Revenue leads because it breaches the company's own €100,000 materiality threshold not because the app decided it was interesting."
3. **Why?** Click the Revenue row. Read the root-cause block: "Two customer milestones were rescheduled from July into August. Nothing lost, nothing disputed a timing shift."
4. **Evidence.** Scroll to the evidence cards. "These are quoted passages from the actual management notes and milestone register not a summary the AI invented. You can see exactly why the system thinks this note is relevant."
5. **Human review.** Scroll to the review panel. Click **Send for controller review**, then **Approve** (or **Request revision** to show the rejection path mention it's a designed path, not an error). "Nothing publishes without a named person approving it."
6. **Action.** Assign an owner and a next step live. "That's the loop: insight becomes an owned action, not just a chart."

Close on the Decision Log at the bottom "every issue this cycle raised, who reviewed it, and where it stands."

## 5-minute Enterprise Architect / AI Engineer walkthrough

Start the same way (KPI band → attention → Revenue issue), then switch to the **Architecture** view. Frame it before diving in: "Everything you're about to see starts from two CSVs and five markdown files `data/actuals.csv`, `data/budget.csv`, `data/context/*.md`. No ERP, no live feed, by design; the point is the path the data takes, not where it comes from."

1. **Business Semantic Layer.** "Raw ledger rows carry codes. `src/domain.py` maps them onto governed business objects business unit, cost center, account and rejects rows that disagree with the chart of accounts, rather than silently aggregating them. That's the proof that raw data isn't business meaning yet."
2. **Deterministic core.** "`variance = actual − budget`, computed once in `src/finance_engine.py`. Nothing downstream recomputes it not the control engine, not the AI layer, not the UI."
3. **Control engine.** "`src/control_engine.py` applies transparent materiality rules to those facts absolute threshold, relative threshold, missing-budget governance gap each one data, not a model, and each one citable against `data/context/finance_policy.md`."
4. **Trust boundary.** Point at the dashed line in the layer-stack diagram. "This is the one architectural claim the whole project rests on: only computed facts, control alerts and retrieved evidence cross it. `src/commentary.py` is the only module on the far side, and it's the only module allowed to import an LLM SDK."
5. **Context layer.** "Retrieval is transparent keyword scoring, not embeddings `src/retrieval.py` returns the document, section, snippet and matched terms for every piece of evidence, so 'why did it say that' is always inspectable, not a black box."
6. **AI interpretation.** Open the "Inspect payload" expander under AI Interpretation in the live trace. "This is the entire payload the model or the demo template receives: computed facts, the control alert, quoted evidence. No ledger access."
7. **Workflow and auditability.** Switch to the **Audit Trail** view. "Every pipeline step for this issue, in sequence, with a timestamp source load, fact computation, control evaluation, evidence retrieval, interpretation, review, decision."
8. **AI independence the load-bearing test.** "`tests/test_ai_independence.py::test_financial_truth_is_independent_from_llm` re-imports the truth layer with every LLM import path actively blocked at the import-system level, and asserts the facts and alerts are byte-identical to a normal run. That's not a design principle stated in a doc it's enforced in CI."

Close by running it live: `pytest -q` in a terminal, pointing at "155 passed."
