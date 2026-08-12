# Vendored fonts

The two type families of the BENACTA charter, vendored locally so
`docs/controlled-intelligence-blueprint.html` renders
identically offline and the PDF can be regenerated without a network.

Regenerate with `python scripts/vendor_fonts.py`.

| Files | Family | Role in the charter |
|---|---|---|
| `InstrumentSans-{400,500,600,700}.woff2` · `InstrumentSans-Italic-400.woff2` | Instrument Sans | Role 2 · ENTERPRISE — the entire system (titles, sections, labels, body, all diagram text) |
| `SourceSerif4-{400,600}.woff2` · `SourceSerif4-Italic-{400,600}.woff2` | Source Serif 4 | Role 3 · EDITORIAL — statements and quotes only, never in diagrams |

**Static instances, not variable fonts.** Upstream ships both families as
variable fonts, and Chromium embeds a variable instance into a PDF as a *Type3*
font — which searches and prints less reliably than a CID subset, and in this
document inflated the PDF by roughly 2.5×. `vendor_fonts.py` therefore bakes
each weight the Blueprint uses into its own static instance (Source Serif 4 at
`opsz=11`, the optical size for text setting). Latin subset only. The charter
forbids the Light weight and nothing here requests below 400.

Role 1 · HERITAGE (Libre Caslon Display) is deliberately **not** vendored: the
charter reserves it for the logo, and the logo is never re-typeset — the
supplied lockup artwork in `assets/generated/` is used instead.

Neither family carries `→`, `≤` or `✓` in its Latin subset. Rather than let
those glyphs fall back to a system font, the Blueprint draws its arrows and
check marks (`.arw`, `.ev li::before`) in the charter's own connector grammar,
so every glyph in the PDF is set in a charter face.

Both families are licensed under the SIL Open Font License 1.1 (`OFL.txt`),
which permits redistribution and embedding. Source: Google Fonts.
Copyright 2022 The Instrument Sans Project Authors ·
Copyright 2014–2021 Adobe (Source Serif).
