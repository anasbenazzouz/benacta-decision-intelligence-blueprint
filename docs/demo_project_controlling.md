# Demo script: why is this project's margin at completion falling?

Audience: a CFO and a project controller. Duration: about seven minutes. Data: the synthetic company of `demo_v2`
(fictional projects, people and contracts, cutoff 31 August 2026). No Odoo access and no language model are needed.

State of the demo: command line and JSON exports. The six screens (Portfolio, Project Workspace, Resources Monitoring,
Flash Report, Treasury, Planning) are not built yet; this script shows the engine they will read.

## Preparation

```bash
uv run --project apps/api benacta seed-fixtures
export BENACTA_MODE=fixture
```

Expected: 10 401 source records ingested, 62 plan versions, revenue and cost of sales `RECONCILED` for 12 months.
Run it a second time: 0 new versions, 62 versions skipped.

## 1. The portfolio, one table (1 min)

```bash
uv run --project apps/api benacta portfolio
```

Point at:

- totals: revenue at completion 11 187 000 EUR, EAC 8 995 500 EUR, margin 2 191 500 EUR (19.59 %);
- PRJ-08 shows `UNKNOWN` and is excluded from the totals. The forecast is missing, so the system does not invent one;
- PRJ-02 carries four exceptions: budget overrun at completion, margin erosion, late milestone, overdue receivable.

Line to say: the portfolio does not average what it does not know.

## 2. The project status report (2 min)

```bash
uv run --project apps/api benacta psr --project PRJ-02
```

Point at:

- EAC 1 764 000 = actual cost 840 000 + ETC 924 000. The ETC already contains the 440 000 of open commitments, so
  they are not added a second time (PRJ-03 shows the 400 000 error a naive sum would make);
- declared physical progress 42 % next to cost consumption 47.62 %: two different measures, never derived from each other;
- billed 600 000 and collected 540 000 incl. taxes, reported apart from recognised revenue, which is `UNAVAILABLE`
  because no recognition policy has been approved;
- status `DRAFT`. Publishing requires a second person and a validated comment; a published report can no longer change.

## 3. The question (2 min)

```bash
uv run --project apps/api benacta investigate --project PRJ-02
```

Question: "Pourquoi la marge à terminaison de ce projet baisse-t-elle ?"

Point at the order of the answer:

1. facts: margin moved from 400 000 to 236 000 EUR, −164 000;
2. decomposition: labour +124 000 (EN +1 250 h at 80, LE +200 h at 120) and subcontracting +40 000, residual 0;
3. observation: engineers logged 900 h in August against 437 h planned by the previous forecast;
4. hypothesis, labelled as such: rework after client comments on the design package, taken from the controller's note;
5. limits: the note is a statement, the hours are consistent with it but do not prove client responsibility;
6. two proposals, `PENDING_REVIEW`: assess a change order, review the engineering hours to completion.

Then the counter-example:

```bash
uv run --project apps/api benacta investigate --project PRJ-08
```

`ABSTAINED`: without a forecast there is no margin at completion to explain.

Line to say: code computes, the explanation cites only computed facts, and the decision stays with people.

## 4. What protects the figures (1 min)

Show the tests rather than claiming them:

```bash
cd apps/api && uv run pytest -q tests/integration/test_project_controlling.py
```

35 tests: a locked forecast refuses edits in the database, the same person cannot submit and approve, a rejected CSV
leaves an error report and no version, revision 2 of a status report leaves revision 1 intact, and the portfolio shows
exactly the numbers of each status report.

## What not to claim

- Not connected to a real Odoo project company yet: the sandbox company is blocked and Timesheets is not installed.
- Not production-ready: local tests on synthetic data.
- No language model in this run: every sentence is produced deterministically and labelled "sans LLM".
