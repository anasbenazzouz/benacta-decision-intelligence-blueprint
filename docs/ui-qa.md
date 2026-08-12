# UI QA — Premium refinement pass

> Phase 6 record. Scope: polish, not rebuild — no architecture, information-model
> or feature change. Doctrine: `.claude/benacta/brand-system.md`,
> `anti-patterns.md`. Verified against the running app (Playwright, 1600×1000
> and reduced-motion emulation) with the full test suite green before and after
> (150 passed).

## Baseline assessment (before changes)

- **Executive clarity** — strong; the six questions read in order. Gap: nothing
  above the fold said the system was *live* (no refresh time, no findings or
  review counts without scrolling).
- **Density** — two hotspots: the Lineage tab's Financial-transaction row
  (inline dump of transaction IDs) and the trace-dialog header (three figures
  compressed into one grey line).
- **Hierarchy** — the AI interpretation block visually outranked the root cause
  beneath it (inverted priority), and the boxed *Trace to source* buttons
  outranked the KPI values; their hover inverted to a heavy solid-green fill.
- **Traceability** — structurally excellent; Source Records led with system
  metadata instead of the business event.
- **Brand** — distinctly BENACTA, with residual Streamlit artifacts: 16px-radius
  dialog, default radio circles in the nav, rounded input wrappers, dead BaseWeb
  tab CSS (this Streamlit build renders tabs as react-aria `stTab` nodes), and
  the native sidebar-collapse arrow which — with the header hidden — left **no
  way to reopen the panel** once used.

## Issues found and fixed

| # | Issue | Fix |
|---|---|---|
| 1 | Hero band passive; no live-system signal | Two-zone hero: review identity left; quiet status rail right (Controlled Intelligence kicker, pulsing *Governed data · current*, last refresh, findings, review counts — all derived from session truth) |
| 2 | No "alive" indicator | One 2.8s breathing dot (muted sage, low-opacity ring); the only looping animation in the app |
| 3 | KPI band rendered statically | One-time entrance (opacity 0.55→1, 3px rise, staggered; variance line fades in after; single soft pulse on unfavourable dots). Gated by a session flag so reruns render still |
| 4 | Trace buttons competed with KPI values; hover inverted to a solid block | Restyled as tracked-caps text actions (*Trace to source ↗*), muted-champagne underline hover, aligned to each KPI cell edge |
| 5 | Selection change had no transition | One-time 550ms champagne settle on the newly selected attention row (rule applies only on selection change, so unchanged reruns never replay it) |
| 6 | AI interpretation visually outranked the root cause | Interpretation body reduced to 16px; root-cause title 20px/600 and impact 25px/600 with a 2px contribution rule showing its share of the variance |
| 7 | Trace-dialog header hard to scan | Metric heading (*Revenue · July 2026*), compact Actual/Budget/Variance key-value column, reconciliation pill + root-cause count on one line; dialog title demoted to a kicker |
| 8 | Lineage read as a table; transaction row dumped TX IDs | Vertical rail with charter-grammar markers (truth green, data blue-grey, AI mineral blue, human porcelain, one champagne Action); transaction step now summarises *14 postings · €4,720,000* + main accounts and points to the Financial Transactions tab (`src/lineage.py`) |
| 9 | Transactions tab summary wordy; no filters; no closing reconciliation | *Financial truth* key-value block; business-unit / account / search filters (display-only — reconciliation always covers the full set); footer line `14 postings · source total €4,720,000 · difference to KPI €0 · RECONCILED`; CSV exports exactly the rows shown |
| 10 | Source records led with system metadata | Business event leads (object, subject, impact, periods, reason); source system / document / record ID moved behind a *Verify source record* disclosure with a demo-source caption |
| 11 | Audit tab ordering | Reordered per brief (Fact ID → … → Action owner) + last-recorded-step timestamp |
| 12 | Sidebar could vanish permanently (native collapse arrow + hidden header) | Native collapse control hidden; the explicit Close panel / ☰ Menu pair is the only toggle, with a one-shot 220ms slide on reopen |
| 13 | Nav looked like a form widget | Radio restyled as an editorial nav list: no circles, tracked caps, champagne left rule on the active view; `:focus-within` ring kept |
| 14 | Tab CSS targeted BaseWeb markup this build no longer uses; active tab was champagne-on-porcelain (contrast fail) | Rewritten for `stTab`: stone at rest, ink when active, champagne kept for the 2px indicator only |
| 15 | Dialog chrome: 16px radius | Squared; inputs' rounded wrappers (`stTextInputRootElement` etc.) squared globally |
| 16 | Human control read as administration | Workflow stepper (AI draft → Controller review → Approved → Action required → Closed; current stage filled, champagne only on the action stage); labels renamed to *Interpretation* / *Decision issue* |
| 17 | Follow-up lacked actionability | First suggestion carries `Owner suggestion · Project Finance · Reason · HIGH finding · Revenue €280k below budget` — derived from the alert, never auto-assigned |
| 18 | Money values wrapped after the minus sign in narrow tables | `white-space: nowrap` on `.ba-rec td.v` / `.ba-kv td.v` |
| 19 | Decision log "Updated" column weighed like the decision columns | Demoted to small stone type |

## Motion system

Doctrine: **motion for state, not decoration.** Every animation lives in one
`@media (prefers-reduced-motion: no-preference)` block. Verified by emulation:
with reduce set, computed `animation-name` is `none` on the pulse and the KPI
cells. The only loop is the 2.8s data pulse; entrances play once per session
(session-state gate confirmed: `entrance` class present on first render, absent
after a rerun); financial figures never blink, count or shimmer.

## Reconciliation integrity (verified in UI and tests)

Revenue actual €4,720,000 · budget €5,000,000 · variance −€280,000; transaction
total €4,720,000 (difference to KPI €0); budget-line total €5,000,000; business
units Projects −€310,000 + Service & Maintenance €30,000 = −€280,000; attribution
−€345,000 + €65,000 unattributed = −€280,000. The cause caption honestly reports
123% of the variance — the offsetting movements are shown, never netted away.

## Intentionally left simple

- **Basis radio keeps its native circles** — it is a genuine input, not
  navigation; only labels were restyled.
- **No column sorting / pagination on the transaction table** — filters and CSV
  are enough for a demo ledger of 14 rows; anything more is an analytics
  workbench.
- **Contribution shown as a 2px rule, not a chart** — typography-first per the
  charter; the reconciliation tables already carry the arithmetic.
- **The chain motif animates once and stops** — it is doctrine drawn as a rule,
  not a progress indicator.
- **Streamlit dataframe keeps its default grid interior** — bordered quietly;
  replacing it wholesale would trade reliability for cosmetics.
- **`123% of the variance`** on the over-explaining cause is kept — reporting
  what the records actually attribute is the honest part of the lineage layer.

## Checks run

`python -m pytest -q` → **150 passed** (after every change). App exercised
end-to-end headless: cockpit (entrance, hover, selection), trace dialog (all
four tabs, filters, verify disclosure), sidebar closed/reopened, Architecture
and Audit Trail views, reduced-motion pass. `DEMO_MODE=true`, no API key.

## Follow-up bounded pass — 2026-08-12

A second Phase 6 pass, re-verifying the state above against the current
working tree rather than re-doing it. Scope: same as the original pass —
polish and correctness, no architecture or feature change.

**Method:** read every doctrine file and `docs/*.md` again; read `app.py` and
every `src/*.py` module in full against `anti-patterns.md` and
`architecture-principles.md`; independently recomputed the four story
variances (Revenue, Materials, Contractors, Travel) and the unbudgeted
workshop-logistics account straight from `data/actuals.csv` /
`data/budget.csv` with pandas, outside the test suite, and confirmed they
match `docs/implementation-plan.md` §3 exactly; ran the full test suite;
launched `streamlit run app.py` under `DEMO_MODE=true` and confirmed it serves
(HTTP 200) with no API key; ran `scripts/demo_decision_loop.py` end-to-end as
a non-visual functional trace of TRUTH → CONTEXT → INTERPRETATION → REVIEW →
DECISION/ACTION → AUDIT.

**Limitation this pass:** the browser tooling available in this session runs
against the user's local Chrome, which cannot reach the sandboxed process
that serves the Streamlit app, so the CSS/typography/motion assertions above
could not be re-verified pixel-by-pixel here. They were instead checked by
reading `src/theme.py` and `app.py` in full and confirming the markup and
rules the previous pass describes are still present and unchanged (hero
zones, KPI entrance classes, trace-button styling, workflow stepper, lineage
rail markers, hidden native sidebar-collapse control, tab/dialog overrides).
A future session with browser access to the same host as the app should still
re-run the visual pass before public release.

**Issue found and fixed:**

| # | Issue | Fix |
|---|---|---|
| 20 | `scripts/demo_decision_loop.py` raised `UnicodeEncodeError` and exited non-zero whenever stdout was not an interactive UTF-8 console — piped, redirected, or a Windows legacy-codepage terminal — because it prints em dashes, curly quotes, `→` and box-drawing rule lines. Reproduced on this Windows machine via `python scripts/demo_decision_loop.py > out.txt`. This is the CLI companion to `streamlit run app.py` and acceptance criteria require documented commands to run as written. | Added a guarded `sys.stdout.reconfigure(encoding="utf-8")` at the top of the script. Re-ran with stdout redirected to a file: exit code 0, all 96 lines printed, revenue/EBITDA figures match the story targets. |

No other issues found: no dead code, unused imports, hard-coded absolute
paths, print statements outside `scripts/`, secrets, deprecated Streamlit
APIs, or forbidden vocabulary on the default cockpit view.

**Checks run:** `python -m pytest -q` → **150 passed**. Streamlit served
successfully under `DEMO_MODE=true` with no API key (verified by HTTP
request; visual walkthrough not possible this session, see limitation
above). `scripts/demo_decision_loop.py` runs clean with output redirected
to a file (previously crashed; now exit code 0).
