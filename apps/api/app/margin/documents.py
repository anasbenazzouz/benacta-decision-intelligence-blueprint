"""Governed document corpus and transparent retrieval.

A document is a Markdown file with front matter naming its identifier, title, source, owner, effective date,
version and authorisation. Only authorised documents are indexed; an unauthorised or malformed document is refused
at indexing, with the reason, and can never be cited. Retrieval is keyword scoring over sections, returning the
document, section, snippet, score and matched terms, so the reader always sees why a passage was selected. No
embeddings, no vector store: the investigation needs citations it can show, not similarity it cannot explain.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import sqlalchemy as sa
import yaml
from sqlalchemy.engine import Connection

from app.audit.log import append_event, content_hash
from app.config import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "data" / "documents" / "margin"
REQUIRED_META = ("doc_id", "title", "source", "owner", "effective_date", "version", "authorised")
STOP_WORDS = frozenset("""a an and are as at be by for from has have in is it its of on or that the this to was were with
    without when while than then there their which who will would not no yes any each one two per""".split())
TOKEN = re.compile(r"[a-z0-9]+")


class DocumentError(ValueError):
    pass


@dataclass(frozen=True)
class Section:
    doc_id: str
    heading: str
    text: str

    @property
    def citation(self) -> str:
        return f"doc:{self.doc_id}#{_slug(self.heading)}"


@dataclass
class Document:
    doc_id: str
    title: str
    source: str
    owner: str
    effective_date: date
    version: int
    authorised: bool
    path: Path
    content_hash: str
    sections: list[Section] = field(default_factory=list)


@dataclass(frozen=True)
class Passage:
    doc_id: str
    title: str
    heading: str
    citation: str
    snippet: str
    score: int
    matched_terms: tuple[str, ...]
    source: str
    owner: str
    effective_date: str
    version: int


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _tokens(text: str) -> list[str]:
    return [t for t in TOKEN.findall(text.lower()) if t not in STOP_WORDS and len(t) > 2]


def parse_document(path: Path) -> Document:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise DocumentError(f"{path.name}: missing front matter")
    _, meta_text, body = raw.split("---", 2)
    meta = yaml.safe_load(meta_text) or {}
    missing = [k for k in REQUIRED_META if k not in meta]
    if missing:
        raise DocumentError(f"{path.name}: front matter lacks {', '.join(missing)}")
    if not isinstance(meta["authorised"], bool):
        raise DocumentError(f"{path.name}: authorised must be true or false")
    effective = meta["effective_date"] if isinstance(meta["effective_date"], date) else date.fromisoformat(str(meta["effective_date"]))
    doc = Document(str(meta["doc_id"]), str(meta["title"]), str(meta["source"]), str(meta["owner"]), effective, int(meta["version"]),
                   bool(meta["authorised"]), path, content_hash(raw))
    heading, buffer = "Introduction", []
    for line in body.splitlines():
        if line.startswith("## "):
            if "".join(buffer).strip():
                doc.sections.append(Section(doc.doc_id, heading, "\n".join(buffer).strip()))
            heading, buffer = line[3:].strip(), []
        else:
            buffer.append(line)
    if "".join(buffer).strip():
        doc.sections.append(Section(doc.doc_id, heading, "\n".join(buffer).strip()))
    if not doc.sections:
        raise DocumentError(f"{path.name}: no section")
    return doc


def load_corpus(directory: Path = CORPUS_DIR) -> tuple[list[Document], list[dict[str, str]]]:
    """(authorised documents, refusals). A refusal names the file and the reason; nothing else is kept from it."""
    documents, refusals = [], []
    for path in sorted(directory.glob("*.md")):
        try:
            doc = parse_document(path)
        except DocumentError as exc:
            refusals.append({"file": path.name, "reason": str(exc)})
            continue
        if not doc.authorised:
            refusals.append({"file": path.name, "reason": f"{doc.doc_id} is not authorised for retrieval"})
            continue
        documents.append(doc)
    return documents, refusals


def register_corpus(conn: Connection, directory: Path = CORPUS_DIR, *, actor: str = "service:documents") -> dict[str, Any]:
    documents, refusals = load_corpus(directory)
    conn.execute(sa.text("delete from semantic.governed_document"))
    for doc in documents:
        conn.execute(sa.text("""
            insert into semantic.governed_document (doc_id, title, source, owner, effective_date, version, authorised, path, content_hash, sections)
            values (:i, :t, :s, :o, :e, :v, true, :p, :h, :n)"""),
            {"i": doc.doc_id, "t": doc.title, "s": doc.source, "o": doc.owner, "e": doc.effective_date, "v": doc.version,
             "p": str(doc.path.relative_to(REPO_ROOT)).replace("\\", "/"), "h": doc.content_hash, "n": len(doc.sections)})
    summary = {"indexed": [d.doc_id for d in documents], "refused": refusals}
    append_event(conn, actor=actor, action="documents.indexed", object_type="document_corpus", object_id=str(directory.relative_to(REPO_ROOT)).replace("\\", "/"),
                 payload=summary)
    return summary


def registered_ids(conn: Connection) -> set[str]:
    return set(conn.execute(sa.text("select doc_id from semantic.governed_document where authorised")).scalars().all())


def retrieve(documents: list[Document], query_terms: list[str], *, on: date | None = None, limit: int = 3) -> list[Passage]:
    """Sections scored by distinct matched terms, then by total matches; only documents effective on the date."""
    wanted = {t for term in query_terms for t in _tokens(term)}
    scored: list[tuple[int, int, Section, Document, tuple[str, ...]]] = []
    for doc in documents:
        if on is not None and doc.effective_date > on:
            continue
        for section in doc.sections:
            tokens = _tokens(section.heading + " " + section.text)
            matched = tuple(sorted(wanted & set(tokens)))
            if not matched:
                continue
            total = sum(tokens.count(t) for t in matched)
            scored.append((len(matched), total, section, doc, matched))
    scored.sort(key=lambda s: (-s[0], -s[1], s[3].doc_id, s[2].heading))
    passages = []
    for distinct, total, section, doc, matched in scored[:limit]:
        snippet = section.text if len(section.text) <= 420 else section.text[:417].rsplit(" ", 1)[0] + "..."
        passages.append(Passage(doc.doc_id, doc.title, section.heading, section.citation, snippet, distinct * 10 + total, matched,
                                doc.source, doc.owner, str(doc.effective_date), doc.version))
    return passages
