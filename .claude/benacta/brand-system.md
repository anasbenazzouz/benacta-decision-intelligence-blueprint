# BENACTA — Brand System

> Binding doctrine, transcribed from the supplied charter `source/brand/Graphical_Design_Final.pdf` ("BENACTA — Visual Identity System · **Master Définitif**"). The charter's own governing rule: **"The system is locked. Future designers select; they do not reinterpret."** Consult before any visual change — app, PDF, diagrams, screenshots, social assets.
>
> If anything here seems to conflict with the charter, the charter wins. Full transcription: `docs/source-analysis.md` §5.
> Note: older BENACTA materials used a previous palette (`#134939` green, `#EEBA2B` gold, Cormorant Garamond). That generation is **superseded** by this charter for this project. Do not mix generations.

## 1. Palette — "colour is information, never decoration"

| Color | Hex | Meaning / use | Forbidden |
|---|---|---|---|
| **Deep Heritage Green** | `#122B20` | Systems, governance, foundation. Master dark background. Pairs: porcelain, champagne, mineral blue | As text on dark ground; large fills on light pages |
| **Warm Porcelain** | `#F1E9DA` | Truth, information, clarity. Light background; text on dark. Pairs with all | As text on porcelain or white |
| **Mineral Intelligence Blue** | `#6C9BA3` | AI, reasoning, agents. The "A", kickers, agent blocks. **Text on light: `#54808A`** | Decorative use without AI meaning |
| **Antique Champagne** | `#BBA06B` | Decision, value, action. "B", wordmark, signature, conclusions. **Text on light: `#8F7440`** | Large fills, metallic effects, **> 10 % of a composition** |
| **Heritage Blue-Grey** | `#536875` | Data, infrastructure, secondary diagram hierarchy | — |
| **Stone** | `#7C898B` | Annotations, legends, metadata | Never for key content |
| **Sand** | `#D6BE98` | Soft editorial accent, rare block backgrounds | Usage **< 3 %** |

RGB/CMYK equivalents: source-analysis §5.2. The semantic mapping is the point: green = foundation/governance · porcelain = truth/judgment · blue = AI/reasoning **only** · champagne = decision/action and always scarce.

### Semantic status extension (owner-approved, Phase 6)

The charter was drawn for publications and carries no favourable/unfavourable
signal, which a variance report needs. Three status tokens extend it, at the
minimum strength required to read:

| Token | Hex | Use |
|---|---|---|
| Favourable | `#4F6B4F` | A muted sage, deliberately unlike a trading-terminal green |
| Unfavourable | `#A05743` | The muted terracotta already used as BENACTA's discreet red |
| Neutral / on plan | `#536875` | Heritage Blue-Grey, unchanged from the charter |

Rules: status colour applies to the **variance line, severity marks and
reconciliation figures only** — never to a KPI value, which stays in ink so the
number remains dominant. Severity uses terracotta (HIGH), muted gold `#8F7440`
(MEDIUM) and blue-grey (LOW). All three clear 5:1 contrast on Warm Porcelain.
Direction is decided by the metric's own definition, never by the sign of the
number: revenue below plan and operating expenses above plan are both
unfavourable.

## 2. Typography — three roles

- **Role 1 · HERITAGE — Libre Caslon Display.** Logo only (BA monogram). Never in running text.
- **Role 2 · ENTERPRISE — Instrument Sans.** The entire system. Bold → technical titles · SemiBold → sections · Medium → labels, nav, nodes · Regular → body. **No Light weight.**
- **Role 3 · EDITORIAL — one serif family, statements only.** Major statements, quotes, editorial heroes. **Never in diagrams** (at most one conclusion line under a schema). Charter candidates with Source Serif 4 marked "my recommendation" → **working choice: Source Serif 4** (owner may override; charter marks the choice "à valider").

All three families are available on Google Fonts.

### Web type scale (desktop / tablet / mobile · leading / tracking)

| Style | D | T | M | Leading / tracking |
|---|---|---|---|---|
| Display — serif éditorial | 64 | 48 | 36 | 1.12 / −0.01em |
| H1 — Sans Bold | 44 | 36 | 29 | 1.15 / −0.015em |
| H2 — SemiBold | 30 | 26 | 23 | 1.25 / −0.01em |
| H3 — Medium | 21 | 19 | 18 | 1.35 / 0 |
| Body large — Regular | 19 | 18 | 17 | 1.6 / 0 |
| Body — Regular | 16 | 16 | 15 | 1.65 / 0 |
| Label — Medium caps | 12 | 12 | 11 | 1.3 / +0.16em |
| Caption — Regular | 13 | 13 | 12 | 1.5 / 0 |
| Button — Medium | 15 | 15 | 15 | 1 / +0.06em |
| KPI — SemiBold | 40 | 34 | 28 | 1.05 / −0.01em |
| Quote — serif éditorial | 26 | 23 | 20 | 1.4 / 0 |

Fluid scale via `clamp()` (charter example — H1: `clamp(29px, 2.3vw + 20px, 44px)`). **Display is used when the content is a statement; otherwise H1 Sans.**

### Infographic / diagram type (Instrument Sans exclusive)

Title 34–40 Bold · Section 22 SemiBold · Node title 15–17 SemiBold · Node description 12–13 Regular · Connector label 10–11 Medium caps +0.08em · Annotation 12 Regular Stone · KPI 40–52 SemiBold · Source/footnote 10–11 Regular Stone · Legend 11 Medium · Process step 14 SemiBold caps +0.12em · System name 13 SemiBold caps · Technology name 13 Medium.

### Carousel type (1080 × 1350, phone-readable)

Hero 88–96 Bold −0.02em · Section 60–68 Bold · Statement 76–88 Bold · Body 28–32 Regular/Medium 1.4 · Number/KPI 96–120 SemiBold · Label/kicker 22–24 Medium caps +0.18em · Diagram label ≥20 Medium caps +0.1em · Footnote ≥22 Regular Stone · Publication header 22 Medium +0.2em · Page number 22 Regular Stone. **Absolute floor 20 px at 1080 scale; any text that does not survive 25 % zoom is enlarged, simplified or removed.**

## 3. Logo system

- Lockup: BA monogram (B champagne, A mineral blue, serif) → BENACTA wordmark in tracked caps → rules flanking the **triangular signature** → tagline "BUILT ON TRUTH. DESIGNED FOR DECISIONS." (TRUTH blue, DECISIONS champagne).
- **Locked rule:** the triangle is optically centered on the complete primary lockup (axis x = 400) — the central architectural punctuation between wordmark and brand promise. (The old "align on the final A" rule is removed.)
- **Primary dark:** on `#122B20` only. **Primary light:** B, triangle and DECISIONS in `#8F7440`; A and TRUTH in `#54808A`; wordmark and tagline in heritage green (`#BBA06B`/`#6C9BA3` fail text contrast on porcelain).
- Family & minimum sizes: PRIMARY min 140 px · SECONDARY (monogram + wordmark; banners, headers, co-branding) min 90 px · below 40 px monogram only · MONOGRAM (avatar, favicon, app) min 16 px · SIGNATURE triangle (section marker, node, watermark) **one occurrence per page** · WORDMARK for running text, footers, mentions.
- Protection zone: triangle height on all four sides.
- Authorized backgrounds: `#122B20`; porcelain `#F1E9DA` or white; monochrome (ink or white) for embossing/stamps. Never on busy photos, never on blue.
- Forbidden: stretch, tilt, shadow, outline, gradients, shiny metallic gold, recoloring outside palette, off-centering the triangle, enlarging it beyond +20 % of calibrated size.
- Supplied assets: full-lockup PNGs only (`source/brand/`). Keep originals under `assets/source-brand-assets/`; derive crops faithfully; flag official SVGs as a future owner deliverable.

## 4. Architecture grammar — READ → REASON → CONTROL → ACT

Semantic node styling for all architecture diagrams:

| Node type | Style |
|---|---|
| System of record | Green, thin outline |
| Data / semantic models | Blue-grey, thick left edge |
| AI | Mineral blue, tinted background · MCP/tool links dotted |
| Business rules · deterministic | **Double-stroke border** |
| Human approval | **Solid porcelain fill** — "the judgment" |
| Action / write-back | **Solid champagne fill** — **one per diagram** |

Line legend: data flow = solid · reasoning/tool call = dashed · controlled action = champagne stroke.

## 5. Composition rules

- Large typography, generous negative space.
- Warm light surfaces or deep dark surfaces; **max 2 background colors per publication**.
- Serif moments rare and controlled.
- Architectural hairlines 1–1.5 px.
- Asymmetry embraced when it serves hierarchy.
- **Zero:** gradients, glassmorphism, AI glow, decorative icons, rounded-card overload.
- Statement-card pattern: dark green card · tracked champagne kicker ("BENACTA · ENTERPRISE AI NOTES — 001") · serif statement with semantic color emphasis · triangle signature bottom-left · wordmark bottom-right.

## 6. Application notes for this project

- The Streamlit app and the Blueprint PDF must read as **the same editorial family as Architecture Note #001**: porcelain ground, deep-green bands, numbered gold section labels (01 /, 02 /…), tracked-caps kickers, hairline rules, margin annotations stating business outcomes, and an "audit trail" rail motif where appropriate.
- Suppress generic Streamlit look where feasible (theming, typography, spacing); no default-widget aesthetic on the executive view.
- Diagrams: vector/SVG where practical, styled per §4; no rasterized small type; every label legible at normal zoom.
