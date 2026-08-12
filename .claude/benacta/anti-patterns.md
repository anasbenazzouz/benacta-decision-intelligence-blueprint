# BENACTA — Anti-Patterns

> Binding doctrine. Check this file **before** adding any feature, dependency, copy, or styling. If a proposed change matches anything here, stop and reconsider.

## Architecture anti-patterns (never)

- The LLM computing, recomputing, altering or "correcting" any financial figure — or consuming raw source rows to derive truth.
- Hidden calculations inside the AI layer; unsupported causal claims; invented numbers.
- AI output presented as a decision ("AI Decision", "the AI decided", autonomous-CFO language).
- Chatbot-first UI: the main interaction must never be a chat box; the default screen must never be a generic dashboard.
- Making the LLM the system of record, or the system unusable when AI is disabled — the deterministic layer must stand alone (`test_financial_truth_is_independent_from_llm`).
- Bypassing the controller: no publishing path without human review; rejection must be a designed path.
- Untraceable output: any important output whose source, rule, evidence, mode, reviewer or timestamp cannot be inspected.

## Palantir / Foundry anti-patterns (never)

- Palantir branding, logos, screenshots, UI imitation, or implied affiliation/partnership.
- "Palantir clone" / "Foundry for X" framing; Foundry terminology sprayed through public documents.
- Building a horizontal data platform or ontology engine instead of the focused vertical slice. The inspiration is conceptual only: **from tables to business objects**.

## Visual anti-patterns (never)

- AI purple gradients, neon, cyberpunk, generic SaaS aesthetics, glassmorphism, AI glow, robot imagery, decorative icons, gratuitous rounded-card dashboards, emojis in brand assets.
- Colors outside the locked charter palette; mixing the old brand generation (`#134939`/`#EEBA2B`/Cormorant) into this project.
- Champagne as large fills or > 10 % of a composition; blue used decoratively without AI meaning; Stone for key content; more than 2 background colors per publication.
- Logo abuse: stretching, tilting, shadows, outlines, gradients, metallic gold, recoloring, off-centering or enlarging the triangle (> +20 %), logos on busy photos or blue grounds.
- Serif in technical diagrams; Instrument Sans Light; rasterized small typography; clipped text; awkward page breaks; obvious template feel; generic AI imagery.
- Generic default-Streamlit appearance on the executive view.

## Content anti-patterns (never)

- Leading the default experience with embeddings, vectors, prompts, JSON, RAG internals, Python classes, API payloads.
- Invented statistics or benchmarks; sourced figures without their citation; derived figures without the "illustrative" label.
- Overclaiming: autonomous AI, production readiness, real integrations that don't exist.
- Generic AI-consulting language replacing BENACTA's own philosophy; buzzword density (agentic, autonomous, multi-agent, copilot, LLM-first).
- README starting with installation commands; PDF as a plain Markdown export.
- Mixing slogan roles on one surface (see `positioning.md` hierarchy).

## Scope anti-patterns — V1 must NOT contain

Full ERP · real Foundry clone · complex ontology engine · multi-agent swarms · Kafka · Kubernetes · microservice meshes · enterprise IAM · real SAP integration · production-grade event buses · generic no-code builders · complex React/Next.js frontend · full workflow engines · vector databases / unnecessary vector infrastructure · production authentication · heavy provider abstractions.

The elegance of V1 comes from proving the architecture with minimal implementation. Do not create complexity for its own sake.

## Process anti-patterns (never)

- Pushing to a remote repository, deploying, or creating external accounts without explicit instruction.
- Real client data, secrets, personal absolute paths, generated junk, dead code, credibility-undermining TODOs in the repo.
- Declaring the PDF complete without the visual QA loop; declaring the project complete without running tests, the app, and demo mode without an API key.
- Changing BENACTA architecture or visual doctrine without explicit justification grounded in `/source` or these doctrine files.
