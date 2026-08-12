# BENACTA — Release Checklist

> Phase 12 deliverable. Practical execution checklist for the controlled
> public launch. Companion document: `docs/release-package.md` (the messaging
> and asset content this checklist points at). Nothing here is checked off by
> writing this file — every box reflects a verification actually run during
> Phase 11/12 unless marked otherwise.

---

## CODE

- [x] Full test suite passing — `pytest -q` → 155 passed, no API key present
      (re-verified Phase 12, unchanged from `docs/final-polish.md`)
- [x] AI-independence test passing —
      `tests/test_ai_independence.py::test_financial_truth_is_independent_from_llm`
      and the full 6-test file
- [x] `DEMO_MODE=true` verified — `streamlit run app.py` serves HTTP 200 with
      no `ANTHROPIC_API_KEY` in the environment
- [x] No secrets in the repository — no `.env`, no committed API keys
      (`.env.example` only, gitignored `.env*` except the example)
- [ ] **Finding — resolve before making the repository public:** the working
      tree has substantial uncommitted work (all of the Phase 3–11 build:
      README, PDF/HTML, `src/*.py`, `docs/*`, `assets/*`, `scripts/*`) sitting
      on top of a single existing commit (`f52af12`) that is already pushed
      to `origin/master`. That commit's author email
      (`git config user.email`) is a personal Gmail address, which
      `docs/final-red-team.md`'s deferred item #3 flagged for correction
      "while nothing has been pushed" — that condition no longer holds for
      `f52af12` specifically. **This is a decision about repository history,
      not a code defect — the owner should decide how the outstanding work
      gets committed (and whether commit authorship is revisited) before the
      repository goes public.** See the Phase 12 final report for detail.
- [x] No dead code / unused imports — `pyflakes app.py src/*.py scripts/*.py`
      clean (Phase 11 finding, fixed; re-verified Phase 12)

## GITHUB

- [x] README reviewed (Phase 11 polish pass; executive-first structure intact)
- [ ] About / description set to the doctrine-locked string (`docs/release-package.md` §5) — **owner action, not modified automatically**
- [ ] Topics set to the finalized 11-item list (`docs/release-package.md` §5) — **owner action**
- [ ] Screenshots captured and README "See it" section updated (`docs/release-package.md` §7) — **owner action**
- [ ] Social preview image created and set (`docs/release-package.md` §8 — composition brief only, asset not yet generated) — **owner action**
- [ ] LICENSE decision made (`docs/release-package.md` §13) — **owner decision required**
- [ ] Repository visibility switched to public — **do not do this until every other box in this section is checked**
- [ ] `v0.1.0` release created from the prepared text (`docs/release-package.md` §6) — **not published this phase, by instruction**

## PDF

- [x] Ten pages, A4 portrait, confirmed via `pypdf` (`docs/final-polish.md`)
- [x] Metadata correct — Title `BENACTA — Controlled Intelligence Blueprint`,
      Author `Anas Benazzouz — BENACTA` (verified as UTF-8 bytes, not just
      console display, in Phase 11)
- [x] GitHub link present and hyperlinked (page 10)
- [ ] Human visual review at full size / print — still the one Gate-G item
      marked PENDING in `docs/acceptance-criteria.md` §12
- [ ] Final URLs (live demo, website, LinkedIn) inserted once available
- [ ] QR code inserted, if used
- [ ] Re-render only if the above insertions change any page — otherwise the
      current PDF stands as final (`docs/final-polish.md`)

## LIVE DEMO

- [ ] Deployed (recommended: Streamlit Community Cloud — `docs/release-package.md` §14)
- [ ] Demo URL recorded and inserted into README / PDF placeholders
- [ ] No secrets configured on the host (no `ANTHROPIC_API_KEY`)
- [ ] `DEMO_MODE=true` set explicitly in the host's environment configuration
- [ ] Smoke test passed on the deployed instance: cockpit loads, KPI band
      renders, "Trace to source" reconciles on Revenue, approve / request
      revision both work, Architecture and Audit Trail views load
- [ ] Verified reachable in a logged-out / private browser window

## LINKEDIN

- [ ] Architecture Note #001 already live (per `docs/release-package.md` §1 —
      confirm still live and CTA is current)
- [ ] Post copy / CTA finalized on the Note itself (`docs/release-package.md` §2)
- [ ] `BLUEPRINT` DM templates ready — Versions A/B/C (`docs/release-package.md` §3)
- [ ] Follow-up message ready (`docs/release-package.md` §4)
- [ ] PDF delivery mechanism ready (direct link or attachment — no email-gate
      form, per doctrine on low friction)

## BENACTA

- [ ] Website URL confirmed (if the landing page from `docs/release-package.md` §10 exists yet — otherwise this stays a placeholder)
- [ ] Profile / bio positioning aligned with `positioning.md`'s canonical block
- [ ] Contact path working (whatever channel the CTA in `docs/release-package.md` §10 actually points to)

## FINAL

- [ ] Test every link in README, PDF and release notes (no 404s, no `localhost` left in place of a real URL)
- [ ] Test the PDF on a mobile device (readability, not just that it opens)
- [ ] Test the GitHub repo logged out (private/incognito browser)
- [ ] Test the live demo logged out (private/incognito browser)
- [ ] Final repository privacy switch (public)
- [ ] Publish

---

## Notes on this checklist

- Boxes checked `[x]` above were verified during Phase 11 or this Phase 12
  pass, with the method recorded in `docs/final-polish.md` or this session's
  final report — not assumed.
- Every unchecked box in **GITHUB**, **LIVE DEMO**, **LINKEDIN** and
  **BENACTA** is an owner/release action, not an engineering gap — consistent
  with `docs/final-red-team.md`'s deferred-items list and
  `docs/acceptance-criteria.md` §11.
- The one unchecked box under **CODE** is the exception: it is a genuine
  finding from this phase's git inspection (not a deferred placeholder) and
  is the reason `docs/release-package.md`'s publication order (§16) inserts
  an explicit "resolve the branch/commit state" step before "make the
  repository public."
