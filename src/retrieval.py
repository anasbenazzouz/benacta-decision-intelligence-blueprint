"""
BENACTA Knowledge & Context Layer.

Finds the business documents that explain a movement, and shows its working.

Retrieval here is deliberately simple: a section scores by how much of the query
it covers, and every evidence item carries the exact terms that matched. There
is no vector store and no embedding model, because the point of this layer is
not retrieval sophistication it is that a controller can always answer
*why did the system show me this note?*

Retrieval sits **above** the trust boundary. It selects and quotes text that
already exists; it generates nothing and computes nothing. No AI dependency.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from src.domain import SEMANTIC_MODEL, SemanticMappingError, SemanticModel

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONTEXT_DIR = _REPO_ROOT / "data" / "context"

#: Minimum share of the query a section must cover to be offered as evidence.
DEFAULT_MIN_SCORE = 0.15
DEFAULT_LIMIT = 3

_MAX_SNIPPET_CHARS = 320
_MIN_TERM_LENGTH = 3
_SCORE_DP = 4

_STOPWORDS = frozenset(
    """
    and are but for from has have its not the that this was were will with
    into than then they their there these those which while your you our
    all any been being can could did does each how may more most must now
    off out over per should some such very what when where who why would
    about above after again against below between during before under
    """.split()
)

#: Business vocabulary per metric the words a finance document would use when
#: it is talking about this metric. Kept beside the retrieval logic because it
#: is search vocabulary, not accounting definition; a test asserts every metric
#: in the semantic model is covered here.
METRIC_SEARCH_TERMS: Mapping[str, tuple[str, ...]] = {
    "revenue": ("revenue", "milestone", "milestones", "acceptance", "recognition",
                "recognised", "customer", "contract", "order", "backlog"),
    # Composite metrics carry the vocabulary of what drives them: no operational
    # note discusses "EBITDA", it discusses the revenue and cost movements that
    # produce it. Naming those drivers here is what lets a composite variance
    # reach the documents that actually explain it.
    "gross_margin": ("margin", "gross", "materials", "procurement", "direct",
                     "costs", "revenue", "milestone", "prices"),
    "operating_expenses": ("operating", "expenses", "overhead", "administration",
                           "costs", "travel", "workshops", "salaries"),
    "ebitda": ("ebitda", "earnings", "profitability", "operating", "result",
               "revenue", "milestone", "costs", "margin", "plan"),
    "direct_materials": ("materials", "procurement", "steel", "components", "spare",
                         "parts", "supplier", "prices", "index", "rebate", "purchases"),
    "external_contractors": ("contractor", "contractors", "external", "engineering",
                             "subcontracted", "capacity", "recruitment", "vacancies"),
    "direct_project_costs": ("site", "installation", "commissioning", "equipment",
                             "rental", "milestone", "deferred", "project", "costs"),
    "personnel_costs": ("salaries", "personnel", "headcount", "staff", "employment"),
    "travel": ("travel", "accommodation", "workshop", "workshops", "customer",
               "visits", "trips", "policy"),
    "facilities": ("facilities", "utilities", "premises"),
    "other_opex": ("professional", "fees", "logistics", "workshop", "workshops",
                   "communications", "budget", "line"),
}


@dataclass(frozen=True)
class Section:
    """One addressable chunk of a context document."""

    document: str
    section: str
    text: str
    terms: frozenset[str]

    @property
    def reference(self) -> str:
        return f"{self.document} § {self.section}"


@dataclass(frozen=True)
class Evidence:
    """A quoted passage, with the reason it was selected."""

    document: str
    section: str
    snippet: str
    score: float
    matched_terms: tuple[str, ...]

    @property
    def reference(self) -> str:
        return f"{self.document} § {self.section}"


@dataclass(frozen=True)
class Query:
    """Weighted business vocabulary describing what we are looking for."""

    weights: Mapping[str, float]

    @property
    def terms(self) -> tuple[str, ...]:
        return tuple(sorted(self.weights))

    @property
    def total_weight(self) -> float:
        return sum(self.weights.values())


# --------------------------------------------------------------------------- #
# Tokenisation
# --------------------------------------------------------------------------- #


def tokenize(text: str) -> tuple[str, ...]:
    """Lowercase word tokens, minus stopwords and very short fragments."""
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return tuple(
        word for word in words if len(word) >= _MIN_TERM_LENGTH and word not in _STOPWORDS
    )


# --------------------------------------------------------------------------- #
# Corpus
# --------------------------------------------------------------------------- #


def _document_title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _split_sections(body: str) -> list[tuple[str, str]]:
    """Split a markdown document on its level-2 headings."""
    sections: list[tuple[str, str]] = []
    heading: str | None = None
    buffer: list[str] = []

    for line in body.splitlines():
        if line.startswith("## "):
            if heading is not None:
                sections.append((heading, "\n".join(buffer).strip()))
            heading = line[3:].strip()
            buffer = []
        elif heading is not None:
            buffer.append(line)

    if heading is not None:
        sections.append((heading, "\n".join(buffer).strip()))
    return [(title, text) for title, text in sections if text]


def load_corpus(context_dir: Path = DEFAULT_CONTEXT_DIR) -> tuple[Section, ...]:
    """
    Read every context document into searchable sections.

    Files are read in sorted order so the corpus and therefore every
    tie-break in ranking is deterministic.
    """
    sections: list[Section] = []

    for path in sorted(context_dir.glob("*.md")):
        body = path.read_text(encoding="utf-8")
        document = _document_title(body, path.stem)
        parts = _split_sections(body)

        if not parts:  # a document with no level-2 headings is one section
            parts = [(document, body.strip())]

        for title, text in parts:
            sections.append(
                Section(
                    document=document,
                    section=title,
                    text=text,
                    terms=frozenset(tokenize(f"{title}\n{text}")),
                )
            )
    return tuple(sections)


# --------------------------------------------------------------------------- #
# Query construction
# --------------------------------------------------------------------------- #


def build_query(
    *,
    label: str,
    metric_key: str | None = None,
    business_unit_name: str | None = None,
    extra_terms: Sequence[str] = (),
) -> Query:
    """
    Build the search vocabulary for a fact or alert.

    The label and the metric's business vocabulary carry full weight; the
    business unit is a weaker hint, since a note about the right subject in the
    wrong unit is still usually relevant.
    """
    weights: dict[str, float] = {}

    def add(terms: Iterable[str], weight: float) -> None:
        for term in terms:
            weights[term] = max(weights.get(term, 0.0), weight)

    add(tokenize(label), 1.0)
    if metric_key:
        add(METRIC_SEARCH_TERMS.get(metric_key, ()), 1.0)
    add((t.lower() for t in extra_terms), 1.0)
    if business_unit_name:
        add(tokenize(business_unit_name), 0.4)

    return Query(weights=weights)


def query_for_alert(alert, model: SemanticModel = SEMANTIC_MODEL) -> Query:
    """
    Build a query from a control alert.

    Account-level alerts carry an account code rather than a metric key; their
    label is the business vocabulary in that case.
    """
    metric_key: str | None = None
    try:
        metric_key = model.metric(alert.metric).key
    except SemanticMappingError:
        metric_key = None

    unit_name = None
    if alert.business_unit:
        try:
            unit_name = model.business_unit(alert.business_unit).name
        except SemanticMappingError:
            unit_name = None

    return build_query(
        label=alert.label, metric_key=metric_key, business_unit_name=unit_name
    )


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #


def _matched_terms(section: Section, query: Query) -> tuple[str, ...]:
    return tuple(sorted(term for term in query.weights if term in section.terms))


def score_section(section: Section, query: Query) -> float:
    """
    The share of the query's weight this section covers.

    A score of 0.5 reads as "this section matches half of what we were looking
    for" which is exactly what gets shown to the user.
    """
    if query.total_weight == 0:
        return 0.0
    matched = sum(query.weights[term] for term in _matched_terms(section, query))
    return round(matched / query.total_weight, _SCORE_DP)


def _snippet(section: Section, matched: Iterable[str]) -> str:
    """Quote the sentences that actually carry the matched terms."""
    matched = set(matched)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", section.text) if s.strip()]
    if not sentences:
        return section.text[:_MAX_SNIPPET_CHARS]

    scored = [
        (sum(1 for term in tokenize(sentence) if term in matched), index)
        for index, sentence in enumerate(sentences)
    ]
    best_count, best_index = max(scored, key=lambda pair: (pair[0], -pair[1]))
    if best_count == 0:
        best_index = 0

    snippet = sentences[best_index]
    if best_index + 1 < len(sentences):
        extended = f"{snippet} {sentences[best_index + 1]}"
        if len(extended) <= _MAX_SNIPPET_CHARS:
            snippet = extended

    snippet = " ".join(snippet.split())
    if len(snippet) > _MAX_SNIPPET_CHARS:
        snippet = snippet[: _MAX_SNIPPET_CHARS - 1].rstrip() + "…"
    return snippet


def retrieve(
    query: Query,
    corpus: Iterable[Section],
    *,
    limit: int = DEFAULT_LIMIT,
    min_score: float = DEFAULT_MIN_SCORE,
) -> tuple[Evidence, ...]:
    """
    Rank sections against the query and return inspectable evidence.

    Ordering is score first, then document and section name, so identical
    scores always resolve the same way.
    """
    results: list[Evidence] = []

    for section in corpus:
        matched = _matched_terms(section, query)
        if not matched:
            continue
        score = score_section(section, query)
        if score < min_score:
            continue
        results.append(
            Evidence(
                document=section.document,
                section=section.section,
                snippet=_snippet(section, matched),
                score=score,
                matched_terms=matched,
            )
        )

    results.sort(key=lambda e: (-e.score, e.document, e.section))
    return tuple(results[:limit])


def retrieve_for_alert(
    alert,
    corpus: Iterable[Section],
    *,
    model: SemanticModel = SEMANTIC_MODEL,
    limit: int = DEFAULT_LIMIT,
    min_score: float = DEFAULT_MIN_SCORE,
) -> tuple[Evidence, ...]:
    """Find the business context that explains a control alert."""
    return retrieve(
        query_for_alert(alert, model), corpus, limit=limit, min_score=min_score
    )
