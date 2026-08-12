"""
BENACTA — visual system for the Decision Cockpit.

Tokens and components taken from the supplied graphical charter
(`source/brand/Graphical_Design_Final.pdf`, "Master Définitif") and transcribed
in `.claude/benacta/brand-system.md`. The charter's own governing rule applies:
the system is locked — select from it, do not reinterpret it.

Three principles drive everything here:

  * **Colour is information, never decoration.** Green is foundation and
    governance, porcelain is truth, mineral blue means AI and nothing else,
    champagne means a decision or an action and stays scarce.
  * **There is no red in this palette.** An unfavourable variance is therefore
    signalled by typography and wording — a minus sign, "below budget", a
    severity label — never by colour. That is a charter constraint, and it also
    happens to be how a finance publication reads.
  * **Motion for state, not decoration.** The only things that move are the
    signals of a live, governed system: the data-current pulse, a one-time
    entrance, a selection change. Financial figures never blink, count or
    shimmer — a number the reader cannot trust to hold still is not a fact.
    Every animation is wrapped in `prefers-reduced-motion: no-preference`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

_ASSETS = Path(__file__).resolve().parent.parent / "assets" / "generated"

LOGO_DARK = _ASSETS / "benacta-primary-dark.png"
LOGO_LIGHT = _ASSETS / "benacta-primary-light.png"

# --------------------------------------------------------------------------- #
# Palette — exact charter values
# --------------------------------------------------------------------------- #

GREEN = "#122B20"        # Deep Heritage Green — systems, governance, foundation
PORCELAIN = "#F1E9DA"    # Warm Porcelain — truth, information, clarity
BLUE = "#6C9BA3"         # Mineral Intelligence Blue — AI, reasoning
BLUE_TEXT = "#54808A"    # blue that holds contrast on porcelain
CHAMPAGNE = "#BBA06B"    # Antique Champagne — decision, value, action
CHAMPAGNE_TEXT = "#8F7440"  # champagne that holds contrast on porcelain
BLUE_GREY = "#536875"    # Heritage Blue-Grey — data, infrastructure
STONE = "#7C898B"        # Stone — annotations, legends, metadata
SAND = "#D6BE98"         # Sand — rare editorial accent, under 3%

SANS = "'Instrument Sans', 'Segoe UI', system-ui, -apple-system, sans-serif"
SERIF = "'Source Serif 4', Georgia, 'Times New Roman', serif"

# --------------------------------------------------------------------------- #
# Semantic status — an owner-approved extension to the locked charter
#
# The charter palette carries no favourable/unfavourable signal, because it was
# drawn for publications rather than for a variance report. These three tokens
# add that signal at the minimum strength needed to read, and no more:
#
#   * FAVOURABLE   a muted sage, deliberately far from a trading-terminal green
#   * UNFAVOURABLE the muted terracotta already used as BENACTA's discreet red
#   * NEUTRAL      Heritage Blue-Grey, straight from the charter
#
# They colour the variance line and severity marks only. The KPI figure itself
# stays in ink so the number, not the status, remains the dominant element.
# All three clear 5:1 contrast on Warm Porcelain.
# --------------------------------------------------------------------------- #

FAVORABLE = "#4F6B4F"
UNFAVORABLE = "#A05743"
NEUTRAL = BLUE_GREY

DIRECTION_COLORS = {
    "FAVORABLE": FAVORABLE,
    "UNFAVORABLE": UNFAVORABLE,
    "NEUTRAL": NEUTRAL,
}

DIRECTION_LABELS = {
    "FAVORABLE": "Favourable",
    "UNFAVORABLE": "Unfavourable",
    "NEUTRAL": "On plan",
}

#: HIGH terracotta · MEDIUM muted gold · LOW desaturated blue-grey.
SEVERITY_COLORS = {
    "HIGH": UNFAVORABLE,
    "MEDIUM": CHAMPAGNE_TEXT,
    "LOW": BLUE_GREY,
}


def direction_color(direction: str) -> str:
    return DIRECTION_COLORS.get(direction, NEUTRAL)


def severity_color(severity: str) -> str:
    return SEVERITY_COLORS.get(severity, BLUE_GREY)


def inject_theme() -> str:
    """The complete stylesheet. Injected once per run."""
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;1,8..60,400&display=swap');

/* ---- ground ------------------------------------------------------------ */
[data-testid="stAppViewContainer"] {{ background: {PORCELAIN}; }}
[data-testid="stHeader"] {{ display: none; }}
[data-testid="stToolbar"] {{ display: none; }}
footer {{ display: none; }}
[data-testid="stMainBlockContainer"] {{
    padding: 2.4rem 3.2rem 4rem 3.2rem;
    max-width: 1180px;
}}
html, body, [data-testid="stAppViewContainer"] * {{
    font-family: {SANS};
    color: {GREEN};
}}
/* Streamlit draws its chevrons and collapse controls as icon-font ligatures.
   The blanket font rule above would render them as literal text, so the icon
   font has to be handed back. */
[data-testid="stIconMaterial"], span[class*="material-symbols"] {{
    font-family: 'Material Symbols Rounded', 'Material Icons' !important;
}}

/* ---- type scale (charter §06) ------------------------------------------ */
.ba-display {{
    font-family: {SERIF};
    font-size: 40px; line-height: 1.12; letter-spacing: -0.01em;
    font-weight: 400; margin: 0;
}}
.ba-h1 {{ font-size: 40px; font-weight: 700; line-height: 1.15; letter-spacing: -0.015em; margin: 0; }}
.ba-h2 {{ font-size: 28px; font-weight: 600; line-height: 1.25; letter-spacing: -0.01em; margin: 0; }}
.ba-h3 {{ font-size: 20px; font-weight: 500; line-height: 1.35; margin: 0; }}
.ba-body {{ font-size: 16px; font-weight: 400; line-height: 1.65; }}
.ba-body-lg {{ font-size: 18px; font-weight: 400; line-height: 1.6; }}
.ba-label {{
    font-size: 12px; font-weight: 500; line-height: 1.3;
    letter-spacing: 0.16em; text-transform: uppercase;
}}
.ba-caption {{ font-size: 13px; line-height: 1.5; color: {STONE}; }}
.ba-kpi {{ font-size: 38px; font-weight: 600; line-height: 1.05; letter-spacing: -0.01em; }}

.ba-stone {{ color: {STONE}; }}
.ba-blue {{ color: {BLUE_TEXT}; }}
.ba-champagne {{ color: {CHAMPAGNE_TEXT}; }}

/* ---- editorial section rule (Note #001 pattern) ------------------------ */
.ba-section {{
    display: flex; align-items: baseline; gap: 14px;
    border-bottom: 1px solid {GREEN};
    padding-bottom: 7px; margin: 44px 0 22px 0;
}}
.ba-section .num {{ color: {CHAMPAGNE_TEXT}; font-weight: 600; }}
.ba-section .title {{ letter-spacing: 0.16em; text-transform: uppercase;
    font-size: 12px; font-weight: 600; }}
.ba-section .note {{ margin-left: auto; color: {STONE}; font-size: 12px;
    letter-spacing: 0.04em; font-style: italic; }}

/* ---- header band ------------------------------------------------------- */
.ba-band {{
    background: {GREEN}; color: {PORCELAIN};
    padding: 26px 30px; margin-bottom: 6px;
}}
.ba-band * {{ color: {PORCELAIN}; }}
.ba-band .kicker {{ color: {CHAMPAGNE}; }}

/* Two-zone hero: the review on the left, a quiet status rail on the right.
   The rail is deliberately smaller type than anything else on the page — a
   system panel, not a second dashboard. */
.ba-hero-zones {{ display: flex; align-items: stretch; gap: 40px; }}
.ba-hero-main {{ flex: 1 1 auto; min-width: 0; }}
.ba-hero-status {{
    flex: 0 0 292px; border-left: 1px solid rgba(241,233,218,0.20);
    padding: 2px 0 2px 30px;
}}
.ba-hero-status .panel-kicker {{
    font-size: 10px; font-weight: 600; letter-spacing: 0.2em;
    text-transform: uppercase; opacity: 0.5; margin-bottom: 13px;
}}
.ba-hero-rows {{ margin-top: 15px; }}
.ba-hero-rows .row {{
    display: flex; justify-content: space-between; gap: 16px;
    padding: 6px 0; border-bottom: 1px solid rgba(241,233,218,0.10);
    font-size: 12.5px; line-height: 1.45;
}}
.ba-hero-rows .row:last-child {{ border-bottom: none; }}
.ba-hero-rows .k {{ opacity: 0.55; white-space: nowrap; }}
.ba-hero-rows .v {{ opacity: 0.92; font-weight: 500; text-align: right;
    font-variant-numeric: tabular-nums; }}
@media (max-width: 1050px) {{
    .ba-hero-zones {{ flex-direction: column; gap: 20px; }}
    .ba-hero-status {{ border-left: none; padding: 16px 0 0 0;
        border-top: 1px solid rgba(241,233,218,0.20); flex-basis: auto; }}
}}

/* The one "alive" signal of the application. The dot breathes on a slow
   cycle (motion block below); everything else on the page holds still. */
.ba-live {{
    display: inline-flex; align-items: center; gap: 9px;
    font-size: 11px; font-weight: 600; letter-spacing: 0.16em;
    text-transform: uppercase;
}}
.ba-live .dot {{
    width: 7px; height: 7px; border-radius: 50%; background: {FAVORABLE};
    box-shadow: 0 0 0 0 rgba(79,107,79,0); flex-shrink: 0;
}}

/* The decision chain — the doctrine, drawn once, as the hero's closing rule.
   Champagne is permitted here because every dot marks a step toward decision
   and action; five 5px dots keep it far inside the <10% champagne budget. */
.ba-chain {{
    display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
    margin-top: 24px; padding-top: 16px;
    border-top: 1px solid rgba(241,233,218,0.14);
}}
.ba-chain .node {{ display: inline-flex; align-items: center; gap: 8px; }}
.ba-chain .node .dot {{ width: 5px; height: 5px; border-radius: 50%;
    background: {CHAMPAGNE}; opacity: 0.9; }}
.ba-chain .node .lbl {{ font-size: 10px; font-weight: 500;
    letter-spacing: 0.18em; text-transform: uppercase; opacity: 0.55; }}
.ba-chain .link {{ width: 22px; height: 1px; background: rgba(241,233,218,0.25); }}

/* ---- KPI band ---------------------------------------------------------- */
.ba-kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 0; }}
.ba-kpi-cell {{
    padding: 18px 22px 16px 22px; border-left: 1px solid rgba(18,43,32,0.16);
    transition: background-color 0.18s ease, box-shadow 0.18s ease;
}}
.ba-kpi-cell:first-child {{ border-left: none; padding-left: 0; }}
/* Hover: a barely-there warm wash and a champagne base rule — the cell can
   act (trace), and the rule says so without lifting, shading or bouncing. */
.ba-kpi-cell:hover {{
    background: rgba(18,43,32,0.03);
    box-shadow: inset 0 -1px 0 0 rgba(187,160,107,0.65);
}}
.ba-kpi-cell .ba-label {{ color: {STONE}; margin-bottom: 10px; }}
.ba-kpi-meta {{ font-size: 13px; line-height: 1.7; color: {GREEN}; margin-top: 10px; }}
.ba-kpi-meta .k {{ color: {STONE}; display: inline-block; min-width: 62px; }}

/* ---- attention rows ---------------------------------------------------- */
div[class*="st-key-att_"] button {{
    width: 100%; background: transparent; border: none; border-radius: 0;
    border-bottom: 1px solid rgba(18,43,32,0.14);
    border-left: 3px solid transparent;
    padding: 15px 18px 14px 18px; margin: 0;
    color: {GREEN}; white-space: normal; height: auto;
    justify-content: flex-start !important;
}}
/* Three markdown paragraphs give the row its scanning hierarchy:
   severity + metric, then the movement, then the rule that fired. */
div[class*="st-key-att_"] button p {{ margin: 0 !important; }}
div[class*="st-key-att_"] button p:nth-of-type(1) {{
    font-size: 11px !important; font-weight: 600 !important;
    letter-spacing: 0.16em; text-transform: uppercase; margin-bottom: 7px !important;
}}
div[class*="st-key-att_"] button p:nth-of-type(2) {{
    font-size: 17px !important; font-weight: 500 !important; line-height: 1.3 !important;
    color: {GREEN}; margin-bottom: 5px !important;
}}
div[class*="st-key-att_"] button p:nth-of-type(3) {{
    font-size: 12.5px !important; font-weight: 400 !important; color: {STONE};
    line-height: 1.4 !important;
}}
/* Streamlit centres the button's inner div and span; both must be overridden
   or the row text floats in the middle of the rule. */
div[class*="st-key-att_"] button > div,
div[class*="st-key-att_"] button span,
div[class*="st-key-att_"] button [data-testid="stMarkdownContainer"] {{
    width: 100% !important; text-align: left !important;
    justify-content: flex-start !important;
}}
div[class*="st-key-att_"] button p {{
    text-align: left !important; font-size: 15px; font-weight: 400; line-height: 1.55;
}}
/* Contrast rule: body text on a light surface is never inverted. The global
   button hover fills with green and lightens its label, which would put
   porcelain text on a pale row — so attention rows opt out explicitly. */
div[class*="st-key-att_"] button:hover {{
    background: rgba(18,43,32,0.055) !important;
    border-bottom-color: rgba(18,43,32,0.22);
}}
div[class*="st-key-att_"] button:hover *,
div[class*="st-key-att_"] button:focus * {{
    background: transparent !important;
}}
div[class*="st-key-att_"] button:hover p:nth-of-type(2),
div[class*="st-key-att_"] button:focus p:nth-of-type(2) {{ color: {GREEN} !important; }}
div[class*="st-key-att_"] button:hover p:nth-of-type(3) {{ color: {STONE} !important; }}
div[class*="st-key-att_"] button:focus {{ outline: none; }}
div[class*="st-key-att_"] button:focus-visible {{ outline: 2px solid {GREEN}; outline-offset: -2px; }}

/* ---- trace-to-source actions --------------------------------------------
   The KPI value is the hero; traceability is its supporting action. A small
   hairline outline button in tracked caps — the same quiet button grammar as
   the panel toggle — so it reads as clickable at a glance without competing
   with the figures. Hover fills green like every other button in the app. */
div[class*="st-key-trace_"] button {{
    border: 1px solid rgba(18,43,32,0.35) !important;
    background: transparent !important;
    padding: 7px 14px !important; min-height: 0 !important;
    justify-content: flex-start !important;
    transition: background-color 0.15s ease, border-color 0.15s ease;
}}
div[class*="st-key-trace_"] button p {{
    font-size: 11px !important; font-weight: 600 !important;
    letter-spacing: 0.15em !important; text-transform: uppercase;
    color: rgba(18,43,32,0.72) !important;
}}
div[class*="st-key-trace_"] button:hover {{
    background: {GREEN} !important; border-color: {GREEN} !important;
}}
div[class*="st-key-trace_"] button:hover p {{
    color: {PORCELAIN} !important;
}}
div[class*="st-key-trace_"] button:focus-visible {{
    outline: 2px solid {GREEN}; outline-offset: 2px;
}}
/* Align each KPI trace button with its KPI cell's left edge. */
div[class*="st-key-trace_kpi_"] button {{ margin-left: 22px !important; }}
div[class*="st-key-trace_kpi_revenue"] button {{ margin-left: 0 !important; }}

/* ---- evidence ---------------------------------------------------------- */
.ba-evidence {{ border-left: 1px solid {BLUE_GREY}; padding: 2px 0 2px 16px; margin-bottom: 18px; }}
.ba-evidence .src {{ font-size: 12px; font-weight: 600; letter-spacing: 0.08em;
    text-transform: uppercase; color: {BLUE_GREY}; }}
.ba-evidence .quote {{ font-family: {SERIF}; font-size: 16px; line-height: 1.55;
    margin-top: 6px; }}

/* ---- semantic tags ------------------------------------------------------
   Restrained by design: a small dot carries the colour, the label stays ink.
   The eye notices the exception; the page does not turn into a traffic light. */
.ba-tag {{
    display: inline-flex; align-items: center; gap: 6px;
    font-size: 10px; font-weight: 600; letter-spacing: 0.14em;
    text-transform: uppercase; color: {GREEN}; opacity: 0.72;
}}
.ba-tag .dot {{
    width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
}}

/* ---- root cause ---------------------------------------------------------
   Held clear of the interpretation block above it: a derived cause and an AI
   draft are different kinds of claim and must not read as one nested card.
   The cause now leads the hierarchy — a business user asks "what is the
   cause?" before "what did the AI write?" — so its title and impact carry
   more weight than the interpretation's body text. No container fill; the
   accent is a hairline in the semantic direction colour. Not champagne:
   champagne means decision or action, and a root cause is analysis. */
.ba-cause {{
    border-left: 2px solid {STONE};
    padding: 16px 0 16px 20px; margin: 26px 0 14px 0;
}}
.ba-cause .title {{ font-size: 20px; font-weight: 600; line-height: 1.3;
    letter-spacing: -0.005em; margin-top: 8px; }}
.ba-cause .impact {{ font-size: 25px; font-weight: 600; letter-spacing: -0.01em;
    font-variant-numeric: tabular-nums; }}
/* A 2px contribution rule under the impact: how much of the headline
   variance this cause accounts for. Typography still leads; the bar only
   makes the proportion visible at a glance. */
.ba-share {{ width: 220px; max-width: 100%; height: 2px;
    background: rgba(18,43,32,0.10); margin-top: 12px; }}
.ba-share span {{ display: block; height: 2px; }}

/* ---- reconciliation ---------------------------------------------------- */
.ba-rec {{ width: 100%; border-collapse: collapse; font-size: 15px; }}
.ba-rec td {{ padding: 9px 0; border: none;
    border-bottom: 1px solid rgba(18,43,32,0.10); background: transparent; }}
.ba-rec td.v {{ text-align: right; font-weight: 500; font-variant-numeric: tabular-nums;
    white-space: nowrap; }}
.ba-rec tr.total td {{ border-top: 1px solid {GREEN}; border-bottom: none;
    font-weight: 600; padding-top: 11px; }}
.ba-rec tr.residual td {{ color: {STONE}; font-style: italic; }}

/* ---- lineage chain -------------------------------------------------------
   A controlled chain, not a table: each step carries a marker on a thin
   vertical rail, in the charter's architecture grammar — green outline for
   governed truth, blue-grey for data, mineral blue for the AI step, solid
   porcelain for human judgment, and exactly one champagne mark on Action. */
.ba-step {{ display: grid; grid-template-columns: 14px 158px 1fr;
    gap: 0 18px; padding: 13px 0 15px 0; position: relative; }}
.ba-step .rail {{ position: relative; }}
.ba-step .rail .dot {{ width: 7px; height: 7px; border-radius: 50%;
    border: 1px solid {BLUE_GREY}; background: transparent; margin-top: 5px; }}
.ba-step .rail .dot.truth {{ border-color: {GREEN}; }}
.ba-step .rail .dot.ai {{ border-color: {BLUE}; background: rgba(108,155,163,0.35); }}
.ba-step .rail .dot.human {{ border-color: {GREEN}; background: #FFFFFF; }}
.ba-step .rail .dot.action {{ border-color: {CHAMPAGNE}; background: {CHAMPAGNE}; }}
.ba-step:not(:last-of-type) .rail::after {{ content: ""; position: absolute;
    left: 3px; top: 17px; bottom: -15px; width: 1px;
    background: rgba(83,104,117,0.35); }}
.ba-step .stage {{ font-size: 11px; font-weight: 600; letter-spacing: 0.14em;
    text-transform: uppercase; color: {BLUE_GREY}; padding-top: 2px; }}
.ba-step .headline {{ font-size: 15px; font-weight: 500; }}
.ba-step .detail {{ font-size: 13.5px; line-height: 1.55; color: {GREEN}; margin-top: 3px; }}
.ba-step .tech {{ font-size: 11.5px; color: {STONE}; margin-top: 5px;
    font-family: {SANS}; }}

/* ---- source record -------------------------------------------------------
   The business event leads: what happened, to which project and milestone,
   with what financial impact. Where to verify it — system, document, record
   id — is one step down, behind a restrained disclosure. */
.ba-record {{ border: 1px solid rgba(18,43,32,0.20); padding: 18px 22px 14px 22px;
    margin-bottom: 14px; }}
.ba-record .obj {{ font-size: 11px; font-weight: 600; letter-spacing: 0.14em;
    text-transform: uppercase; color: {BLUE_GREY}; }}
.ba-record .subject {{ font-size: 17px; font-weight: 600; line-height: 1.35;
    margin-top: 6px; }}
.ba-record .impact-label {{ font-size: 11px; color: {STONE};
    letter-spacing: 0.08em; text-transform: uppercase; }}
.ba-record .impact {{ font-size: 20px; font-weight: 600; margin-top: 2px;
    font-variant-numeric: tabular-nums; white-space: nowrap; }}
.ba-record .kv2 {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px 28px; margin-top: 14px; }}
.ba-record .kv2 .f {{ font-size: 11px; color: {STONE}; letter-spacing: 0.06em;
    text-transform: uppercase; }}
.ba-record .kv2 .val {{ font-size: 14px; margin-top: 2px; line-height: 1.45; }}
.ba-record .reason {{ font-size: 14.5px; line-height: 1.6; margin-top: 14px; }}
.ba-verify {{ margin-top: 14px; border-top: 1px solid rgba(18,43,32,0.14);
    padding-top: 10px; }}
.ba-verify summary {{ list-style: none; cursor: pointer;
    display: inline-flex; align-items: center; gap: 8px;
    font-size: 11px; font-weight: 600; letter-spacing: 0.15em;
    text-transform: uppercase; color: rgba(18,43,32,0.62); }}
.ba-verify summary::-webkit-details-marker {{ display: none; }}
.ba-verify summary:hover {{ color: {CHAMPAGNE_TEXT}; text-decoration: underline;
    text-underline-offset: 4px; }}
.ba-verify summary:focus-visible {{ outline: 2px solid {GREEN}; outline-offset: 2px; }}
.ba-verify .body {{ margin-top: 12px; }}

/* ---- status + severity ------------------------------------------------- */
.ba-status {{
    display: inline-block; font-size: 11px; font-weight: 600;
    letter-spacing: 0.16em; text-transform: uppercase;
    padding: 6px 12px; border: 1px solid {GREEN};
}}
.ba-status.approved {{ background: {GREEN}; color: {PORCELAIN}; }}
.ba-status.action {{ background: {CHAMPAGNE}; border-color: {CHAMPAGNE}; color: {GREEN}; }}
.ba-status.draft {{ background: transparent; color: {GREEN}; }}

/* ---- workflow progression -----------------------------------------------
   The review chain as a quiet stepper: past stages in ink outline, the
   current stage filled — green while judgment is pending, champagne only
   when the stage IS the action. Future stages stay stone. Reads as a
   workflow, not administration. */
.ba-flow {{ display: flex; align-items: center; flex-wrap: wrap;
    margin: 2px 0 24px 0; }}
.ba-flow .stp {{ font-size: 10px; font-weight: 600; letter-spacing: 0.14em;
    text-transform: uppercase; padding: 6px 12px; white-space: nowrap;
    border: 1px solid rgba(18,43,32,0.25); color: {STONE}; background: transparent; }}
.ba-flow .stp.done {{ color: {GREEN}; border-color: rgba(18,43,32,0.55); }}
.ba-flow .stp.current {{ background: {GREEN}; color: {PORCELAIN}; border-color: {GREEN}; }}
.ba-flow .stp.current.warm {{ background: {CHAMPAGNE}; color: {GREEN}; border-color: {CHAMPAGNE}; }}
.ba-flow .lnk {{ width: 16px; height: 1px; background: rgba(18,43,32,0.30);
    flex-shrink: 0; }}

/* ---- interpretation block (AI = mineral blue, and only here) ----------- */
.ba-ai {{ border-left: 3px solid {BLUE}; background: rgba(108,155,163,0.07);
    padding: 16px 20px; margin-bottom: 4px; }}
.ba-ai .tag {{ color: {BLUE_TEXT}; }}

/* ---- decision log ------------------------------------------------------ */
.ba-log {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
.ba-log th {{ text-align: left; font-size: 11px; font-weight: 600;
    letter-spacing: 0.16em; text-transform: uppercase; color: {STONE};
    padding: 0 14px 8px 0; border: none;
    border-bottom: 1px solid {GREEN}; background: transparent; }}
.ba-log td {{ padding: 13px 14px 13px 0; vertical-align: top; border: none;
    border-bottom: 1px solid rgba(18,43,32,0.12); line-height: 1.5;
    background: transparent; }}
.ba-log td.sec, .ba-log th.sec {{ font-size: 12px; color: {STONE}; }}

/* key/value figures — hairlines only, never a grid */
.ba-kv {{ width: 100%; border-collapse: collapse; }}
.ba-kv td {{ padding: 8px 0; border: none;
    border-bottom: 1px solid rgba(18,43,32,0.12); background: transparent; }}
.ba-kv td.k {{ font-size: 13px; color: {STONE}; }}
.ba-kv td.v {{ text-align: right; font-size: 16px; font-weight: 500;
    font-variant-numeric: tabular-nums; white-space: nowrap; }}

/* ---- sidebar ----------------------------------------------------------- */
[data-testid="stSidebar"] {{ background: {GREEN}; }}
[data-testid="stSidebar"] * {{ color: {PORCELAIN}; }}
[data-testid="stSidebar"] hr {{ border-color: rgba(241,233,218,0.22); }}
/* The native collapse arrow is hidden deliberately: in this build, once the
   sidebar is collapsed natively there is no control left in the DOM to
   reopen it (the reopen chevron lives in the header, which this theme
   removes). The explicit Close/Menu pair below is the only toggle. */
[data-testid="stSidebarCollapseButton"] {{ display: none !important; }}
/* Navigation: the radio is restyled as an editorial nav list — no widget
   circles; a champagne left rule marks the active view. */
[data-testid="stSidebar"] [data-testid="stRadioOption"] {{
    display: block; padding: 9px 12px; margin: 0 0 2px 0;
    border-left: 2px solid transparent; cursor: pointer;
    transition: background-color 0.15s ease;
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"] > div > div > div:first-of-type {{
    display: none;
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"] p {{
    font-size: 12px !important; font-weight: 500;
    letter-spacing: 0.14em; text-transform: uppercase;
    color: rgba(241,233,218,0.66) !important;
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover {{
    background: rgba(241,233,218,0.06);
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover p {{
    color: {PORCELAIN} !important;
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] {{
    border-left-color: {CHAMPAGNE}; background: rgba(241,233,218,0.05);
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] p {{
    color: {PORCELAIN} !important; font-weight: 600;
}}
[data-testid="stSidebar"] [data-testid="stRadioOption"]:focus-within {{
    outline: 1px solid rgba(241,233,218,0.55); outline-offset: 1px;
}}
/* Inputs sit on a light ground inside the dark sidebar, so ink, not porcelain. */
[data-testid="stSidebar"] input {{
    color: {GREEN} !important; background: {PORCELAIN};
    border-radius: 0; font-size: 14px;
}}
/* Only the widget's own caption is a tracked-caps label; the radio options
   are navigation and stay as styled above. */
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
    font-size: 11px; letter-spacing: 0.14em; text-transform: uppercase; opacity: 0.65;
}}

/* ---- controls ---------------------------------------------------------- */
.stButton button {{
    border-radius: 0; font-family: {SANS}; font-size: 13px; font-weight: 500;
    letter-spacing: 0.06em; padding: 10px 18px;
    border: 1px solid {GREEN}; background: transparent; color: {GREEN};
}}
.stButton button:hover, .stButton button:hover * {{ color: {PORCELAIN}; }}
.stButton button:hover {{ background: {GREEN}; border-color: {GREEN}; }}
/* The primary action reads as a filled block, so its label must be porcelain
   on every nested element — the inner <p> otherwise inherits the ink colour. */
div[class*="st-key-primary_"] button,
div[class*="st-key-primary_"] button * {{ background: {GREEN}; color: {PORCELAIN}; }}
div[class*="st-key-primary_"] button:hover,
div[class*="st-key-primary_"] button:hover * {{ background: {CHAMPAGNE}; color: {GREEN};
    border-color: {CHAMPAGNE}; }}

/* Widget captions in the main area read as quiet tracked labels. */
[data-testid="stMain"] [data-testid="stWidgetLabel"] p,
[data-testid="stDialog"] [data-testid="stWidgetLabel"] p {{
    font-size: 11px !important; font-weight: 500;
    letter-spacing: 0.1em; text-transform: uppercase; color: {STONE};
}}

[data-testid="stExpander"] {{ border: 1px solid rgba(18,43,32,0.18); border-radius: 0;
    background: transparent; }}
[data-testid="stExpander"] summary {{ font-size: 12px; font-weight: 500;
    letter-spacing: 0.12em; text-transform: uppercase; }}
[data-testid="stTextArea"] textarea {{ border-radius: 0; border-color: rgba(18,43,32,0.3);
    background: rgba(255,255,255,0.5); font-family: {SANS}; font-size: 14px; }}
hr {{ border: none; border-top: 1px solid rgba(18,43,32,0.16); margin: 26px 0; }}

/* Square every input container the charter would otherwise inherit rounded. */
[data-baseweb="input"], [data-baseweb="base-input"],
[data-testid="stTextInputRootElement"], [data-testid="stDateInputRootElement"],
[data-testid="stTextInput"] input, [data-testid="stDateInput"] input,
[data-testid="stSelectbox"] > div > div,
[data-baseweb="select"] > div {{ border-radius: 0 !important; }}

/* ---- panel toggle -------------------------------------------------------
   An explicit, always-discoverable open/close control, standing in for
   Streamlit's native collapse arrow (hidden above — this build renders no
   way to undo the native collapse). Small, hairline, never a navigation
   bar of its own. */
div[class*="st-key-open_panel"] button {{
    border-radius: 0 !important; font-size: 11px !important; font-weight: 500 !important;
    letter-spacing: 0.12em !important; text-transform: uppercase !important;
    padding: 7px 14px !important; border: 1px solid rgba(18,43,32,0.35) !important;
    background: transparent !important; color: {GREEN} !important; white-space: nowrap;
    transition: background-color 0.15s ease, border-color 0.15s ease;
}}
div[class*="st-key-open_panel"] button:hover,
div[class*="st-key-open_panel"] button:hover * {{
    background: {GREEN} !important; color: {PORCELAIN} !important;
}}
[data-testid="stSidebar"] div[class*="st-key-close_panel"] button {{
    width: 100%; border-radius: 0; font-size: 11px; font-weight: 500;
    letter-spacing: 0.12em; text-transform: uppercase;
    background: transparent; border: 1px solid rgba(241,233,218,0.4);
    color: {PORCELAIN}; padding: 7px 14px;
    transition: background-color 0.15s ease, border-color 0.15s ease;
}}
[data-testid="stSidebar"] div[class*="st-key-close_panel"] button:hover {{
    background: rgba(241,233,218,0.12); border-color: rgba(241,233,218,0.6);
}}

/* ---- tabs (Trace to Source) ----------------------------------------------
   This Streamlit build renders tabs as react-aria stTab nodes, not BaseWeb.
   Restyled to the charter: tracked sans labels, stone at rest, ink when
   active — never champagne text on porcelain, which fails contrast — with
   the champagne kept for the 2px active indicator only. */
[data-testid="stTabs"] [role="tablist"] {{
    gap: 28px; border-bottom: 1px solid rgba(18,43,32,0.18);
}}
[data-testid="stTab"] {{ padding: 0 0 9px 0 !important; background: transparent !important; }}
[data-testid="stTab"] p {{
    font-size: 12px !important; font-weight: 500;
    letter-spacing: 0.12em; text-transform: uppercase; color: {STONE};
}}
[data-testid="stTab"][aria-selected="true"] p {{ color: {GREEN}; font-weight: 600; }}
[data-testid="stTab"] .react-aria-SelectionIndicator {{
    background: {CHAMPAGNE} !important; height: 2px !important;
}}
[data-testid="stTab"]:focus-visible {{ outline: 2px solid {GREEN}; outline-offset: 2px; }}

/* ---- dialog (Trace to Source) --------------------------------------------
   Squared to the charter — no rounded modal chrome — and the dialog's fixed
   title becomes a quiet kicker so the metric heading inside leads. */
[data-testid="stDialog"] > div,
[data-testid="stDialog"] > div > div {{ border-radius: 0 !important; }}
[data-testid="stDialog"] h2[slot="title"] p {{
    font-size: 11px !important; font-weight: 600;
    letter-spacing: 0.18em; text-transform: uppercase; color: {STONE};
}}

/* ---- reconciliation status pill -----------------------------------------
   Deliberately not a banner: a small inline mark, ink text, a single-word
   colour cue only when it disagrees. */
.ba-recon {{
    display: inline-flex; align-items: center; gap: 7px;
    font-size: 11px; font-weight: 600; letter-spacing: 0.1em; text-transform: uppercase;
}}
.ba-recon .dot {{ width: 6px; height: 6px; border-radius: 50%; }}
.ba-recon.ok {{ color: {GREEN}; }}
.ba-recon.ok .dot {{ background: {FAVORABLE}; }}
.ba-recon.gap {{ color: {UNFAVORABLE}; }}
.ba-recon.gap .dot {{ background: {UNFAVORABLE}; }}

/* dataframe (Financial Transactions table) — quiet the default grid chrome */
[data-testid="stDataFrame"] {{ border: 1px solid rgba(18,43,32,0.18); }}

/* ---- motion — for state, never decoration --------------------------------
   Everything that moves lives inside this block, so a reduced-motion
   preference silences the entire system at once. Durations are slow and
   singular: the data pulse breathes at 2.8s; entrances play once per
   session; selection flashes once and settles. Nothing loops but the pulse. */
@media (prefers-reduced-motion: no-preference) {{
    .ba-live .dot {{ animation: ba-pulse 2.8s cubic-bezier(0.45, 0, 0.55, 1) infinite; }}
    @keyframes ba-pulse {{
        0%, 100% {{ box-shadow: 0 0 0 0 rgba(79,107,79,0); opacity: 0.8; }}
        50% {{ box-shadow: 0 0 0 5px rgba(79,107,79,0.22); opacity: 1; }}
    }}

    .entrance .ba-chain .node {{ animation: ba-chain-in 0.5s ease both; }}
    @keyframes ba-chain-in {{
        from {{ opacity: 0.08; }}
        to {{ opacity: 1; }}
    }}

    .ba-kpis.entrance .ba-kpi-cell {{
        animation: ba-rise 0.6s cubic-bezier(0.2, 0.65, 0.25, 1) both;
    }}
    .ba-kpis.entrance .ba-kpi-cell:nth-child(2) {{ animation-delay: 0.07s; }}
    .ba-kpis.entrance .ba-kpi-cell:nth-child(3) {{ animation-delay: 0.14s; }}
    .ba-kpis.entrance .ba-kpi-cell:nth-child(4) {{ animation-delay: 0.21s; }}
    @keyframes ba-rise {{
        from {{ opacity: 0.55; transform: translateY(3px); }}
        to {{ opacity: 1; transform: none; }}
    }}
    .ba-kpis.entrance .ba-kpi-meta,
    .ba-kpis.entrance .ba-tag {{ animation: ba-fade 0.45s ease both; animation-delay: 0.32s; }}
    @keyframes ba-fade {{
        from {{ opacity: 0; }}
        to {{ opacity: 1; }}
    }}
    /* One soft pulse for unfavourable marks on first load — then stillness. */
    .ba-kpis.entrance .ba-tag .dot.once {{ animation: ba-dot-once 1.1s ease-out 0.8s 1; }}
    @keyframes ba-dot-once {{
        0%, 100% {{ transform: scale(1); }}
        40% {{ transform: scale(1.5); }}
    }}

    @keyframes ba-select {{
        from {{ box-shadow: inset 0 0 0 999px rgba(187,160,107,0.16); }}
        to {{ box-shadow: inset 0 0 0 999px rgba(187,160,107,0); }}
    }}
    @keyframes ba-panel-in {{
        from {{ transform: translateX(-14px); opacity: 0.4; }}
        to {{ transform: none; opacity: 1; }}
    }}
}}
</style>
"""


# --------------------------------------------------------------------------- #
# Components
# --------------------------------------------------------------------------- #


def money(value: float | None, decimals: int = 0) -> str:
    """Charter-consistent money: the sign leads, then the symbol."""
    if value is None:
        return "—"
    sign = "-" if value < 0 else ""
    return f"{sign}€{abs(value):,.{decimals}f}"


def money_compact(value: float | None) -> str:
    if value is None:
        return "—"
    sign = "-" if value < 0 else ""
    magnitude = abs(value)
    if magnitude >= 1_000_000:
        return f"{sign}€{magnitude / 1_000_000:.2f}M"
    if magnitude >= 1_000:
        return f"{sign}€{magnitude / 1_000:,.0f}k"
    return f"{sign}€{magnitude:,.0f}"


def percent(value: float | None) -> str:
    return "—" if value is None else f"{value:+.1%}"


_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def period_label(period: str) -> str:
    """'2026-07' → 'July 2026'. Unparseable periods pass through unchanged."""
    try:
        year, month = period.split("-")
        return f"{_MONTHS[int(month) - 1]} {year}"
    except (ValueError, IndexError):
        return period


def section(number: str, title: str, note: str | None = None) -> str:
    """The Note #001 numbered section rule."""
    annotation = f'<span class="note">{note}</span>' if note else ""
    return (
        f'<div class="ba-section"><span class="num ba-label">{number}</span>'
        f'<span class="title">{title}</span>{annotation}</div>'
    )


def header_band(
    kicker: str,
    title: str,
    meta: str,
    *,
    status_rows: Sequence[tuple[str, str]] | None = None,
    live_label: str | None = None,
    status_kicker: str = "Controlled Intelligence",
    chain: Sequence[str] | None = None,
    entrance: bool = False,
) -> str:
    """
    The application header. One zone by default; with `status_rows` or
    `live_label` it becomes the two-zone hero — review identity on the left,
    a quiet system-status rail on the right — and `chain` closes the band
    with the decision chain drawn as a hairline motif.
    """
    main = (
        f'<div class="ba-hero-main">'
        f'<div class="ba-label kicker">{kicker}</div>'
        f'<div class="ba-h1" style="margin-top:10px">{title}</div>'
        f'<div class="ba-body" style="margin-top:8px;opacity:0.78">{meta}</div>'
        f"</div>"
    )

    status = ""
    if status_rows or live_label:
        live = (
            f'<div class="ba-live"><span class="dot"></span>{live_label}</div>'
            if live_label
            else ""
        )
        rows = "".join(
            f'<div class="row"><span class="k">{key}</span><span class="v">{value}</span></div>'
            for key, value in (status_rows or ())
        )
        status = (
            f'<div class="ba-hero-status">'
            f'<div class="panel-kicker">{status_kicker}</div>'
            f"{live}"
            f'<div class="ba-hero-rows">{rows}</div>'
            f"</div>"
        )

    chain_html = ""
    if chain:
        nodes = []
        for index, label in enumerate(chain):
            if index:
                nodes.append('<span class="link"></span>')
            delay = 0.35 + index * 0.14
            nodes.append(
                f'<span class="node" style="animation-delay:{delay:.2f}s">'
                f'<span class="dot"></span><span class="lbl">{label}</span></span>'
            )
        chain_html = f'<div class="ba-chain">{"".join(nodes)}</div>'

    classes = "ba-band" + (" entrance" if entrance else "")
    return (
        f'<div class="{classes}">'
        f'<div class="ba-hero-zones">{main}{status}</div>'
        f"{chain_html}</div>"
    )


def kpi_band(facts, entrance: bool = False) -> str:
    """
    The four headline KPIs, with financial-semantic conditional formatting.

    Direction comes from the metric's own definition, not the sign: revenue
    below plan and operating expenses above plan are both unfavourable, and are
    coloured the same way even though their variances have opposite signs. The
    actual stays in ink and stays the largest thing in the cell — the status
    colour sits on the variance line, where interpretation happens.

    `entrance` plays the one-time first-render rise; reruns render still.
    """
    cells = []
    for fact in facts:
        direction = fact.direction.value
        colour = direction_color(direction)
        dot_class = "dot once" if direction == "UNFAVORABLE" else "dot"

        tag = (
            f'<span class="ba-tag"><span class="{dot_class}" style="background:{colour}"></span>'
            f"{DIRECTION_LABELS.get(direction, direction)}</span>"
            if fact.variance is not None
            else '<span class="ba-tag ba-stone">'
            '<span class="dot" style="background:currentColor"></span>Not assessed</span>'
        )

        cells.append(
            f'<div class="ba-kpi-cell">'
            f'<div class="ba-label">{fact.label}</div>'
            f'<div class="ba-kpi">{money_compact(fact.actual)}</div>'
            f'<div class="ba-kpi-meta">'
            f'<span class="k">Budget</span>{money_compact(fact.budget)}<br>'
            f'<span class="k">Variance</span>'
            f'<span style="color:{colour}">{money_compact(fact.variance)}'
            f" &nbsp;{percent(fact.variance_pct)}</span></div>"
            f'<div style="margin-top:11px">{tag}</div>'
            f"</div>"
        )
    classes = "ba-kpis" + (" entrance" if entrance else "")
    return f'<div class="{classes}">{"".join(cells)}</div>'


#: How each control rule reads to a controller on the attention row.
_RULE_PHRASING = {
    "ABS_MATERIALITY": "Absolute materiality threshold breached",
    "REL_MATERIALITY": "Relative materiality threshold breached",
    "MISSING_BUDGET": "No approved budget line for this account",
}


def attention_label(alert) -> str:
    """
    Three markdown paragraphs, styled as a scanning hierarchy:

        HIGH · REVENUE
        €280k below budget · -5.6%
        Absolute materiality threshold breached
    """
    heading = f"{alert.severity.value} · {alert.label.upper()}"

    if alert.variance is None:
        movement = f"{money_compact(alert.actual)} recorded with no budget line"
    else:
        position = "below" if alert.variance < 0 else "above"
        movement = f"{money_compact(abs(alert.variance))} {position} budget"
        if alert.variance_pct is not None:
            movement += f" · {alert.variance_pct:+.1%}"

    rule = _RULE_PHRASING.get(alert.rule_id, alert.rule_name)
    return f"{heading}\n\n{movement}\n\n{rule}"


def attention_styles(items, selected_key: str) -> str:
    """
    Per-row severity accent, plus a selected state distinct from hover.

    Hover is a neutral warm wash; selection is a champagne-tinted ground with a
    solid severity rule on the left, and a single 550ms settle when the
    selection changes (`ba-select` flashes once because the rule only newly
    applies on a selection change — an unchanged rerun does not replay it).
    """
    rules = []
    for item in items:
        key = f"att_{item.issue_id}"
        colour = severity_color(item.alert.severity.value)
        rules.append(
            f"div[class*='st-key-{key}'] button {{ border-left-color:{colour}44; }}"
            f"div[class*='st-key-{key}'] button p:nth-of-type(1) {{ color:{colour} !important; }}"
        )

    rules.append(
        f"div[class*='st-key-{selected_key}'] button {{"
        f"background:rgba(187,160,107,0.22) !important;"
        f"border-left-width:4px;"
        f"border-left-color:{CHAMPAGNE} !important; }}"
        f"div[class*='st-key-{selected_key}'] button:hover {{"
        f"background:rgba(187,160,107,0.22) !important; }}"
        f"div[class*='st-key-{selected_key}'] button p:nth-of-type(2) {{ font-weight:600 !important; }}"
        f"@media (prefers-reduced-motion: no-preference) {{"
        f"div[class*='st-key-{selected_key}'] button {{ animation: ba-select 0.55s ease-out 1; }}"
        f"}}"
    )
    return f"<style>{''.join(rules)}</style>"


def evidence_block(evidence, show_relevance: bool = False) -> str:
    """Quoted source text with its reference. The 'why it said that'."""
    detail = ""
    if show_relevance:
        detail = (
            f'<div class="ba-caption" style="margin-top:6px">'
            f"relevance {evidence.score:.2f} · matched: "
            f'{", ".join(evidence.matched_terms[:10])}</div>'
        )
    return (
        f'<div class="ba-evidence">'
        f'<div class="src">{evidence.document} &nbsp;§&nbsp; {evidence.section}</div>'
        f'<div class="quote">“{evidence.snippet}”</div>{detail}</div>'
    )


def root_cause_block(cause, direction: str, share: float | None = None) -> str:
    """
    A derived cause: what happened, what it cost, and why — in that order.

    The financial impact is the one place colour carries meaning here; the
    border accent, title and explanation stay ink. `share` — this cause's
    portion of the headline variance — draws a 2px contribution rule under
    the impact, typography-first. Supporting evidence is rendered separately
    by the caller — an analytical driver and the document that corroborates
    it are different kinds of claim.
    """
    colour = direction_color(direction)

    caption = (
        f"attributed financial impact · {len(cause.records)} source "
        f"record{'' if len(cause.records) == 1 else 's'}"
    )
    share_html = ""
    if share is not None:
        width = min(abs(share), 1.0) * 100
        share_html = (
            f'<div class="ba-share"><span style="width:{width:.0f}%;'
            f'background:{colour}"></span></div>'
        )
        caption += f" · {abs(share):.0%} of the variance"

    return (
        f'<div class="ba-cause" style="border-left-color:{colour}77">'
        f'<div class="ba-label ba-stone">Root cause</div>'
        f'<div class="title">{cause.title}</div>'
        f'<div class="impact" style="color:{colour};margin-top:10px">'
        f"{money(cause.impact_eur)}</div>"
        f"{share_html}"
        f'<div class="ba-caption" style="margin-top:6px">{caption}</div>'
        f'<div class="ba-body" style="margin-top:14px">{cause.explanation}</div>'
        f"</div>"
    )


def reconciliation_table(rows, total_label: str, total_value: float | None,
                         residual_label: str | None = None,
                         residual_value: float | None = None) -> str:
    """Contributions that visibly add up to the headline figure."""
    body = "".join(
        f'<tr><td>{label}</td><td class="v" style="color:{colour}">{money(value)}</td></tr>'
        for label, value, colour in rows
    )
    if residual_label is not None:
        body += (
            f'<tr class="residual"><td>{residual_label}</td>'
            f'<td class="v">{money(residual_value)}</td></tr>'
        )
    body += (
        f'<tr class="total"><td>{total_label}</td>'
        f'<td class="v">{money(total_value)}</td></tr>'
    )
    return f'<table class="ba-rec">{body}</table>'


#: Lineage marker per stage, in the charter's architecture grammar. Stages
#: not listed default to the blue-grey data outline.
_STAGE_DOTS = {
    "Source record": "truth",
    "Financial metric": "truth",
    "Control finding": "truth",
    "Root cause / interpretation": "ai",
    "Decision issue": "human",
    "Action": "action",
}


def lineage_chain(steps) -> str:
    """
    The business lineage as a controlled chain: marker dots on a thin
    vertical rail, business language first, metadata second. The dot grammar
    follows the charter — truth green, data blue-grey, AI mineral blue,
    human judgment porcelain, and one champagne mark on Action.
    """
    rendered = []
    for step in steps:
        dot = _STAGE_DOTS.get(step.stage, "")
        tech = f'<div class="tech">{step.technical}</div>' if step.technical else ""
        rendered.append(
            f'<div class="ba-step">'
            f'<div class="rail"><div class="dot {dot}"></div></div>'
            f'<div class="stage">{step.stage}</div>'
            f'<div><div class="headline">{step.headline}</div>'
            f'<div class="detail">{step.detail}</div>{tech}</div></div>'
        )
    return "".join(rendered)


def source_record_card(record) -> str:
    """
    One business event, business-first: what happened, to which project and
    milestone, in which period, at what financial impact, and why. Where a
    controller verifies it — source system, document, record id — sits
    behind a restrained "Verify source record" disclosure.
    """
    kv2 = "".join(
        f'<div><div class="f">{field}</div><div class="val">{value}</div></div>'
        for field, value in (
            (
                "Project",
                f"{record.project_name} ({record.project_id})"
                if record.project_id
                else "—",
            ),
            (
                "Milestone",
                f"{record.milestone_name} ({record.milestone_id})"
                if record.milestone_id
                else "—",
            ),
            ("Original period", period_label(record.original_period)),
            (
                "Current period",
                period_label(record.current_period)
                + (" · moved" if record.deferred else " · unchanged"),
            ),
        )
    )

    verify_rows = "".join(
        f'<tr><td class="k">{field}</td><td class="v" style="text-align:left;'
        f'font-size:14px">{value}</td></tr>'
        for field, value in (
            ("Source system", record.source_system),
            ("Source document", f"{record.source_document} § {record.source_section}"),
            ("Record ID", record.source_record_id),
            ("Account", record.account),
            ("Customer", record.customer or "—"),
        )
    )

    return (
        f'<div class="ba-record">'
        f'<div style="display:flex;justify-content:space-between;'
        f'align-items:flex-start;gap:24px">'
        f"<div>"
        f'<div class="obj">{record.business_object}</div>'
        f'<div class="subject">{record.subject}</div>'
        f"</div>"
        f'<div style="text-align:right;flex-shrink:0">'
        f'<div class="impact-label">Financial impact</div>'
        f'<div class="impact">{money(record.impact_eur)}</div>'
        f"</div></div>"
        f'<div class="kv2">{kv2}</div>'
        f'<div class="reason">{record.reason}</div>'
        f'<details class="ba-verify"><summary>Verify source record</summary>'
        f'<div class="body"><table class="ba-kv">{verify_rows}</table>'
        f'<div class="ba-caption" style="margin-top:10px">Demo source: '
        f"{record.source_system}. A connected implementation resolves this "
        f"reference directly in the source system.</div>"
        f"</div></details>"
        f"</div>"
    )


def reconciliation_status(check) -> str:
    """
    RECONCILED, or the exact gap — never a large banner, never hidden.

    `check` is a `src.lineage.ReconciliationCheck`.
    """
    if check.displayed is None:
        return (
            '<span class="ba-recon ok"><span class="dot"></span>'
            "No comparable figure for this row</span>"
        )
    if check.reconciled:
        return '<span class="ba-recon ok"><span class="dot"></span>Reconciled</span>'
    return (
        f'<span class="ba-recon gap"><span class="dot"></span>'
        f"Difference {money(check.difference)}</span>"
    )


def reconciliation_detail_table(check) -> str:
    """The three-line arithmetic behind the status pill, for the controller who wants it."""
    rows = [
        ("Displayed figure", money(check.displayed) if check.displayed is not None else "—"),
        ("Source row total", money(check.source_total)),
        ("Difference", money(check.difference)),
    ]
    body = "".join(
        f'<tr><td class="k">{key}</td><td class="v">{value}</td></tr>' for key, value in rows
    )
    return f'<table class="ba-kv">{body}</table>'


def workflow_chips(stages: Sequence[tuple[str, str]]) -> str:
    """
    The review progression as a quiet stepper.

    `stages` is (label, state) with state one of `done`, `current`,
    `current-warm` (the action stage, champagne) or `todo`.
    """
    classes = {
        "done": "stp done",
        "current": "stp current",
        "current-warm": "stp current warm",
        "todo": "stp",
    }
    parts = []
    for index, (label, state) in enumerate(stages):
        if index:
            parts.append('<span class="lnk"></span>')
        parts.append(f'<span class="{classes[state]}">{label}</span>')
    return f'<div class="ba-flow">{"".join(parts)}</div>'


def panel_visibility_css(open: bool) -> str:
    """
    Collapse the sidebar entirely under our own session-state control.

    Not Streamlit's native collapse: verified in this build that once a user
    collapses the native sidebar, there is no control anywhere in the DOM to
    reopen it (so the native arrow is hidden in the main stylesheet). This
    CSS switch, driven by `st.session_state.panel_open`, is the whole
    mechanism — reliable because it is plain state, not frontend-only UI
    state Python cannot see.
    """
    if open:
        return ""
    return '<style>[data-testid="stSidebar"] { display: none !important; }</style>'


def panel_open_animation_css() -> str:
    """
    A single 220ms slide when the panel is explicitly reopened. Emitted for
    one run only (the caller pops its flag), so reruns never replay it; the
    keyframes live in the reduced-motion block, so the preference silences it.
    """
    return (
        "<style>@media (prefers-reduced-motion: no-preference) {"
        '[data-testid="stSidebar"] { animation: ba-panel-in 0.22s ease-out; }'
        "}</style>"
    )


def status_chip(label: str) -> str:
    tone = "draft"
    if label == "APPROVED":
        tone = "approved"
    elif label == "ACTION REQUIRED":
        tone = "action"
    return f'<span class="ba-status {tone}">{label}</span>'


def footer_band() -> str:
    return (
        f'<div class="ba-band" style="margin-top:56px;padding:22px 30px">'
        f'<div class="ba-label kicker">Built on Truth. Designed for Decisions.</div>'
        f'<div class="ba-body" style="margin-top:8px;opacity:0.72">'
        f"Code computes. AI explains. Humans decide.</div></div>"
    )


# --------------------------------------------------------------------------- #
# Architecture diagram — charter §09 grammar, as vector
# --------------------------------------------------------------------------- #


#: The diagram's intrinsic proportions, used to size its frame.
DIAGRAM_RATIO = 660 / 940


def architecture_document(width: int = 1100) -> tuple[str, int]:
    """
    The diagram wrapped as a standalone document, with its height.

    Streamlit's markdown sanitiser strips `<svg>`, so the diagram is served
    through an isolated frame instead. That frame is its own document, which
    means it needs the charter font imported again — a diagram set in a
    fallback typeface is not the charter's diagram.
    """
    height = int(width * DIAGRAM_RATIO) + 8
    document = f"""<!doctype html>
<html><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&display=swap');
html,body {{ margin:0; padding:0; background:{PORCELAIN}; }}
svg {{ width:100%; height:auto; display:block; }}
</style></head>
<body>{architecture_diagram()}</body></html>"""
    return document, height


def architecture_diagram() -> str:
    """
    The layer stack, drawn in the charter's architecture grammar.

    System of record: green thin outline. Semantic and knowledge layers:
    blue-grey thick left edge. Deterministic rules: double stroke. AI: mineral
    blue tint with a dotted edge. Human approval: solid porcelain. Action:
    solid champagne — exactly one node in the diagram carries it.
    """
    label = f'font-family:{SANS};font-size:13px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase'
    node = f'font-family:{SANS};font-size:15px;font-weight:600'
    desc = f'font-family:{SANS};font-size:12px;fill:{STONE}'
    connector = f'font-family:{SANS};font-size:10px;font-weight:500;letter-spacing:0.1em;text-transform:uppercase;fill:{STONE}'

    def source_box(x: int, title: str, sub: str) -> str:
        return (
            f'<rect x="{x}" y="24" width="248" height="54" fill="none" '
            f'stroke="{GREEN}" stroke-width="1"/>'
            f'<text x="{x + 16}" y="47" style="{node}" fill="{GREEN}">{title}</text>'
            f'<text x="{x + 16}" y="65" style="{desc}">{sub}</text>'
        )

    return f"""
<svg viewBox="0 0 940 660" width="100%" role="img"
     aria-label="BENACTA decision intelligence layer stack">
  <rect width="940" height="660" fill="{PORCELAIN}"/>

  {source_box(24, "ERP · General Ledger", "read-only extract")}
  {source_box(288, "Budget &amp; Forecast", "approved plan")}
  {source_box(552, "Docs &amp; Policies", "notes, milestones, policy")}

  <line x1="424" y1="78" x2="424" y2="104" stroke="{GREEN}" stroke-width="1"/>
  <text x="434" y="96" style="{connector}">extract</text>

  <!-- semantic layer: blue-grey thick left edge -->
  <rect x="24" y="104" width="776" height="56" fill="none" stroke="{GREEN}" stroke-width="1"/>
  <rect x="24" y="104" width="5" height="56" fill="{BLUE_GREY}"/>
  <text x="44" y="128" style="{node}" fill="{GREEN}">Business Semantic Layer</text>
  <text x="44" y="146" style="{desc}">business units · cost centers · accounts · metric definitions</text>

  <line x1="424" y1="160" x2="424" y2="182" stroke="{GREEN}" stroke-width="1"/>

  <!-- deterministic core: double stroke -->
  <rect x="24" y="182" width="776" height="104" fill="none" stroke="{GREEN}" stroke-width="1.5"/>
  <rect x="28" y="186" width="768" height="96" fill="none" stroke="{GREEN}" stroke-width="1"/>
  <text x="44" y="210" style="{node}" fill="{GREEN}">Deterministic Core</text>
  <text x="196" y="210" style="{desc}">code computes every figure</text>
  <rect x="44" y="224" width="360" height="44" fill="none" stroke="{GREEN}" stroke-width="1"/>
  <text x="60" y="251" style="{node}" fill="{GREEN}">Finance Engine</text>
  <rect x="420" y="224" width="360" height="44" fill="none" stroke="{GREEN}" stroke-width="1"/>
  <text x="436" y="251" style="{node}" fill="{GREEN}">Control Engine</text>

  <line x1="424" y1="286" x2="424" y2="308" stroke="{GREEN}" stroke-width="1"/>

  <!-- knowledge layer -->
  <rect x="24" y="308" width="776" height="56" fill="none" stroke="{GREEN}" stroke-width="1"/>
  <rect x="24" y="308" width="5" height="56" fill="{BLUE_GREY}"/>
  <text x="44" y="332" style="{node}" fill="{GREEN}">Knowledge &amp; Context Layer</text>
  <text x="44" y="350" style="{desc}">transparent retrieval · quoted evidence · relevance shown</text>

  <!-- trust boundary -->
  <line x1="24" y1="392" x2="800" y2="392" stroke="{GREEN}" stroke-width="1"
        stroke-dasharray="6 5"/>
  <text x="24" y="385" style="{connector}">trust boundary</text>
  <text x="800" y="385" style="{connector}" text-anchor="end">computed facts only · facts above, interpretation below</text>

  <!-- AI layer: mineral blue, dotted -->
  <rect x="24" y="404" width="776" height="56" fill="{BLUE}" fill-opacity="0.10"
        stroke="{BLUE}" stroke-width="1" stroke-dasharray="3 3"/>
  <text x="44" y="428" style="{node}" fill="{BLUE_TEXT}">AI Interpretation Layer</text>
  <text x="44" y="446" style="{desc}">retrieves, explains, drafts · never owns the numbers</text>

  <line x1="424" y1="460" x2="424" y2="482" stroke="{BLUE}" stroke-width="1"
        stroke-dasharray="3 3"/>
  <text x="434" y="475" style="{connector}">governed draft</text>

  <!-- human approval: solid porcelain -->
  <rect x="24" y="482" width="776" height="56" fill="#FFFFFF" stroke="{GREEN}" stroke-width="1"/>
  <text x="44" y="506" style="{node}" fill="{GREEN}">Controller Sign-off</text>
  <text x="44" y="524" style="{desc}">human-in-the-loop · rejection is a designed path</text>

  <line x1="424" y1="538" x2="424" y2="560" stroke="{CHAMPAGNE}" stroke-width="2"/>
  <text x="434" y="553" style="{connector}">approved</text>

  <!-- action: solid champagne, the single action node -->
  <rect x="24" y="560" width="776" height="56" fill="{CHAMPAGNE}"/>
  <text x="44" y="584" style="{node}" fill="{GREEN}">Decision · Owner · Next Step</text>
  <text x="44" y="602" style="{desc}" fill="{GREEN}">insight becomes an owned action</text>

  <!-- audit rail -->
  <rect x="824" y="24" width="92" height="592" fill="none" stroke="{GREEN}"
        stroke-width="1" stroke-dasharray="4 4"/>
  <text x="870" y="320" style="{label}" fill="{GREEN}" text-anchor="middle"
        transform="rotate(-90 870 320)">Audit trail · every step logged</text>
</svg>
"""
