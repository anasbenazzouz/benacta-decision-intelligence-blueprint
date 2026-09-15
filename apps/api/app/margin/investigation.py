"""AI-assisted investigation of one exception case, below the trust boundary.

The investigation receives a payload of computed facts only: the evaluation and its evidence, the transactions
behind it, the rules, the reconciliation of the period, the related evaluations and the governed passages
retrieved for the case. It returns a structured report where every statement carries references into that
payload: a metric, a transaction, a rule, a document passage, or is explicitly labelled a hypothesis.

Two providers write the report: a deterministic one (mode DETERMINISTIC_NO_LLM, label "sans LLM") that runs
without any credential, and a language model provider whose output is validated before it is stored. Validation
refuses any number that is not in the payload, any reference that is not in the payload, unlabelled hypotheses
and instruction-like text; a refused draft falls back to the deterministic report with the reason recorded.
The report never changes a figure, never decides, and its draft recommendation follows the same approval path
as a template.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from app.audit.log import append_event, canonical_json, content_hash
from app.margin.decisions import TEMPLATES, current_recommendation
from app.margin.documents import load_corpus, registered_ids, retrieve
from app.margin.service import exception_case
from app.numbers import decimal_text

QUESTION = "Why is this margin exception raised, what does the evidence support, and what should a person decide?"
SCHEMA_VERSION = 1
NUMBER = re.compile(r"(?<![A-Za-z0-9_-])\d(?:[\d ,]*\d)?(?:\.\d+)?%?")
INSTRUCTION_PATTERNS = tuple(re.compile(p, re.IGNORECASE) for p in (r"ignore (?:all |the )?(?:previous|prior|above) instructions", r"you must approve",
                                                                     r"approve (?:this|the) (?:case|recommendation) (?:now|immediately)",
                                                                     r"system prompt", r"disregard (?:the )?(?:evidence|rules)"))
STATEMENT_TYPES = frozenset({"OBSERVED_FACT", "HYPOTHESIS", "MISSING_EVIDENCE", "QUESTION", "TRADE_OFF"})


class ValidationError(ValueError):
    pass


class Provider(Protocol):
    name: str

    def draft(self, payload: dict[str, Any]) -> dict[str, Any]: ...


# --------------------------------------------------------------------------- payload
@dataclass(frozen=True)
class Payload:
    data: dict[str, Any]
    allowed_numbers: frozenset[str]
    allowed_refs: frozenset[str]

    def as_dict(self) -> dict[str, Any]:
        return {**self.data, "allowed_refs": sorted(self.allowed_refs)}


def _numbers_in(value: Any, out: set[str]) -> None:
    if isinstance(value, dict):
        for v in value.values():
            _numbers_in(v, out)
    elif isinstance(value, list):
        for v in value:
            _numbers_in(v, out)
    elif isinstance(value, bool):
        return
    elif isinstance(value, int | float | Decimal):
        out.add(_norm(str(value)))
    elif isinstance(value, str):
        for m in NUMBER.findall(value):
            out.add(_norm(m))


def _norm(text: str) -> str:
    cleaned = text.replace(" ", "").replace(",", "").rstrip("%")
    try:
        d = Decimal(cleaned)
    except InvalidOperation:
        return cleaned
    return format(d.normalize(), "f")


def build_payload(conn: Connection, snapshot_id: uuid.UUID, case_ref: str, *, corpus_dir=None) -> Payload:
    case = exception_case(conn, snapshot_id, case_ref)
    if case is None or case.get("evaluation") is None:
        raise ValueError(f"case {case_ref} has no evaluation in snapshot {snapshot_id}")
    ev, evidence, drill = case["evaluation"], case["evidence"], case["drill_down"]
    documents, refusals = load_corpus(corpus_dir) if corpus_dir else load_corpus()
    authorised = registered_ids(conn)
    documents = [d for d in documents if d.doc_id in authorised]
    order_date = date.fromisoformat(ev["order_date"]) if ev.get("order_date") else None
    terms = [ev["cause"].replace("_", " "), ev["rule_id"].replace("_", " "), ev["exposure_type"] or "", case["rule"]["name"]]
    passages = retrieve(documents, terms, on=order_date, limit=3)
    metrics = {
        "metric:expected_amount": ev["expected_amount"], "metric:actual_amount": ev["actual_amount"],
        "metric:adverse_exposure": ev["adverse_exposure"], "metric:potential_exposure": ev["potential_exposure"],
    }
    transactions = []
    for line in drill.get("order_lines", []):
        transactions.append({"ref": f"tx:sale_order_line:{line['sale_line_id']}", "order": line["order_name"], "product": line.get("default_code"),
                             "qty_ordered": line["qty_ordered"], "price_unit": line["price_unit"], "discount_pct": line["discount_pct"],
                             "subtotal": line["subtotal"], "qty_delivered": line["qty_delivered"], "qty_invoiced": line["qty_invoiced"]})
    for inv in drill.get("invoice_lines", []):
        transactions.append({"ref": f"tx:invoice_line:{inv['invoice_line_id']}", "invoice": inv["invoice_name"], "type": inv["move_type"],
                             "accounting_date": inv["accounting_date"], "subtotal_signed": inv["subtotal_signed"], "link": inv["link_cardinality"]})
    for alloc in drill.get("cost_allocations", []):
        transactions.append({"ref": f"tx:cost_allocation:{alloc['delivery_move_id']}:{alloc['allocation_no']}", "status": alloc["status"],
                             "quantity": alloc["quantity"], "unit_cost": alloc["unit_cost"], "amount": alloc["amount"], "reason": alloc["reason"]})
    if drill.get("invoice_line"):
        inv = drill["invoice_line"]
        transactions.append({"ref": f"tx:invoice_line:{inv['invoice_line_id']}", "invoice": inv["invoice_name"], "type": inv["move_type"],
                             "accounting_date": inv["accounting_date"], "revenue_company_ccy": inv["revenue_company_ccy"]})
    data = {
        "schema_version": SCHEMA_VERSION,
        "question": QUESTION,
        "case": {"case_ref": case["case"]["case_ref"], "subject_ref": case["case"]["subject_ref"], "status": case["case"]["status"],
                 "classification": ev["classification"], "cause": ev["cause"], "severity": ev["severity"], "confidence": ev["confidence"],
                 "controllability": ev["controllability"], "material": ev["material"], "exposure_stage": ev["exposure_stage"],
                 "currency": ev["currency_code"], "period": ev["period"]},
        "rule": {"ref": f"rule:{ev['rule_id']}:v{ev['rule_version']}", "name": case["rule"]["name"], "formula": ev["formula"],
                 "thresholds": ev["thresholds_version"], "reason": evidence.get("reason")},
        "metrics": metrics,
        "policy_context": {k: evidence.get(k) for k in ("applied_policy", "allowed_discount_pct", "derogation", "baseline", "contract", "cost_reference",
                                                          "policies_considered", "conflicting_caps", "attribution_reasons") if evidence.get(k) is not None},
        "transactions": transactions,
        "period_reconciliation": [{"ref": f"metric:reconciliation:{c['check_id']}", "check": c["check_id"], "status": c["status"],
                                   "independence": c["independence"]} for c in case["period_reconciliation"]],
        "related_evaluations": [{"ref": f"rule:{r['rule_id']}:v{r['rule_version']}", "outcome": r["outcome"], "classification": r["classification"],
                                 "cause": r["cause"], "adverse_exposure": r["adverse_exposure"]} for r in case["related_evaluations_same_subject"]],
        "documents": [{"ref": p.citation, "title": p.title, "heading": p.heading, "snippet": p.snippet, "matched_terms": list(p.matched_terms),
                       "score": p.score, "source": p.source, "owner": p.owner, "effective_date": p.effective_date, "version": p.version} for p in passages],
        "documents_refused": refusals,
        "recommendation": case.get("recommendation"),
    }
    numbers: set[str] = set()
    _numbers_in({k: v for k, v in data.items() if k not in ("documents_refused", "question")}, numbers)
    refs = {*metrics, data["rule"]["ref"], *(t["ref"] for t in transactions), *(r["ref"] for r in data["period_reconciliation"]),
            *(r["ref"] for r in data["related_evaluations"]), *(p.citation for p in passages)}
    return Payload(data, frozenset(numbers), frozenset(refs))


# --------------------------------------------------------------------------- deterministic provider
class DeterministicProvider:
    name = "deterministic"

    def draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        case, rule, metrics = payload["case"], payload["rule"], payload["metrics"]
        docs = payload["documents"]
        cause = case["cause"]
        statements: list[dict[str, Any]] = [
            {"type": "OBSERVED_FACT", "text": f"Rule {rule['name']} classified the subject {case['subject_ref']} as {case['classification']} "
                                              f"with cause {cause}: {rule['reason']}.", "refs": [rule["ref"]]},
        ]
        if metrics.get("metric:adverse_exposure"):
            statements.append({"type": "OBSERVED_FACT", "text": f"Expected {metrics['metric:expected_amount']} against actual "
                                                                f"{metrics['metric:actual_amount']} {case['currency']}: adverse exposure "
                                                                f"{metrics['metric:adverse_exposure']} {case['currency']}, stage {case['exposure_stage']}.",
                               "refs": ["metric:expected_amount", "metric:actual_amount", "metric:adverse_exposure"]})
        elif metrics.get("metric:potential_exposure"):
            statements.append({"type": "OBSERVED_FACT", "text": f"No leakage is computed; the potential exposure is at most "
                                                                f"{metrics['metric:potential_exposure']} {case['currency']}.",
                               "refs": ["metric:potential_exposure"]})
        for t in payload["transactions"][:6]:
            if t["ref"].startswith("tx:sale_order_line"):
                statements.append({"type": "OBSERVED_FACT", "text": f"Order line {t['order']} {t['product']}: {t['qty_ordered']} at {t['price_unit']} "
                                                                    f"with {t['discount_pct']}% discount, delivered {t['qty_delivered']}, invoiced {t['qty_invoiced']}.",
                                   "refs": [t["ref"]]})
            elif t["ref"].startswith("tx:invoice_line") and "subtotal_signed" in t:
                statements.append({"type": "OBSERVED_FACT", "text": f"Invoice {t['invoice']} ({t['type']}, {t['accounting_date']}) carries "
                                                                    f"{t['subtotal_signed']} on this line, link {t['link']}.", "refs": [t["ref"]]})
            elif t["ref"].startswith("tx:cost_allocation"):
                statements.append({"type": "OBSERVED_FACT", "text": f"Cost allocation {t['status']}: {t['quantity']} units at {t['unit_cost']} "
                                                                    f"= {t['amount']}{' (' + t['reason'] + ')' if t.get('reason') else ''}.", "refs": [t["ref"]]})
        if payload["period_reconciliation"]:
            listed = ", ".join(f"{r['check']} {r['status']}" for r in payload["period_reconciliation"])
            statements.append({"type": "OBSERVED_FACT", "text": f"Reconciliation of the period: {listed}.",
                               "refs": [r["ref"] for r in payload["period_reconciliation"]]})
        for r in payload["related_evaluations"]:
            if r["classification"] not in ("COMPLIANT", "NOT_APPLICABLE"):
                statements.append({"type": "OBSERVED_FACT", "text": f"The same subject also raises {r['classification']} under {r['cause']}"
                                                                    f"{' for ' + r['adverse_exposure'] + ' ' + case['currency'] if r['adverse_exposure'] else ''}.",
                                   "refs": [r["ref"]]})
        hypotheses = {
            "DISCOUNT_ABOVE_CAP": "The discount was granted commercially without the derogation the policy requires; a late derogation or a recovery invoice are the two outcomes.",
            "PRICE_BELOW_CONTRACT": "The order was entered at a negotiated price the contract does not carry; either an amendment exists outside the register or the price is a billing error.",
            "PRICELIST_MISMATCH": "The order applied another customer's price list at entry; the low price is an order entry error rather than a negotiated gesture.",
            "FREIGHT_NOT_INVOICED": "Freight was omitted when the goods were invoiced; the contractual clause still applies.",
            "FREIGHT_PARTIALLY_INVOICED": "Freight was charged below the clause; a reduction may have been agreed but is not recorded.",
            "PURCHASE_PRICE_VARIANCE": "The supplier price moved after the reference freeze; the variance is a procurement matter, not a customer recovery.",
            "MISSING_COST": "The receipt behind the delivery is not valued or not posted; the margin of the line is unknown until it is.",
            "POLICY_EXPIRED": "The segment policy lapsed and the discount continued under the old cap; renewal or a case-by-case review is needed.",
            "POLICY_CONFLICT": "Two customer policies coexist; one was probably meant to replace the other.",
            "INVOICE_WITHOUT_ORDER": "The invoice was entered directly or the order link was lost; the revenue cannot be checked against terms.",
        }
        if cause in hypotheses:
            statements.append({"type": "HYPOTHESIS", "text": hypotheses[cause], "refs": [rule["ref"], *([d["ref"] for d in docs[:1]])],
                               "support": "consistent with the evidence, not independently verified"})
        for d in docs:
            statements.append({"type": "OBSERVED_FACT", "text": f"Governed document {d['title']}, section {d['heading']} (owner {d['owner']}, "
                                                                f"version {d['version']}, effective {d['effective_date']}): \"{d['snippet']}\"", "refs": [d["ref"]]})
        missing = {
            "DISCOUNT_ABOVE_CAP": ["A derogation for this order in the derogation register, dated before the order confirmation."],
            "PRICE_BELOW_CONTRACT": ["A signed amendment to the contract price for this product and period."],
            "PRICELIST_MISMATCH": ["Confirmation of the price list assigned to the customer at order date."],
            "FREIGHT_NOT_INVOICED": ["A freight invoice referencing the order, or a recorded waiver by the account manager."],
            "FREIGHT_PARTIALLY_INVOICED": ["A recorded approved reduction of the freight amount."],
            "PURCHASE_PRICE_VARIANCE": ["The supplier price change notice and whether it is contractual."],
            "MISSING_COST": ["The valued receipt or the cost attribution for the delivered units."],
            "POLICY_EXPIRED": ["A renewed or replacement discount policy for the segment."],
            "POLICY_CONFLICT": ["The sales director's decision on which policy applies."],
            "INVOICE_WITHOUT_ORDER": ["The order or contract behind the invoice."],
        }.get(cause, ["Any document that explains the exception."])
        for m in missing:
            statements.append({"type": "MISSING_EVIDENCE", "text": m, "refs": []})
        questions = {
            "billing_leakage": ["Was a commercial gesture agreed with the customer, and by whom?", "Can the difference be invoiced without damaging the account?"],
        }.get("billing_leakage" if case["classification"] in ("CONFIRMED_LEAKAGE", "PROBABLE_LEAKAGE") and cause not in ("PURCHASE_PRICE_VARIANCE",) else "",
              ["What evidence would settle the case?"])
        for q in questions:
            statements.append({"type": "QUESTION", "text": q, "refs": []})
        statements.append({"type": "TRADE_OFF", "text": "Recovering the amount protects margin and policy; accepting it as a gesture protects the account "
                                                        "relationship. Either way the decision and its reason are recorded.", "refs": []})
        rec = payload.get("recommendation") or {}
        template = TEMPLATES.get(cause, {"title": "Review the evidence and decide", "rationale": "No template for this cause."})
        return {
            "schema_version": SCHEMA_VERSION,
            "summary": f"{case['subject_ref']} is a {case['classification'].replace('_', ' ').lower()} ({cause.replace('_', ' ').lower()}) of "
                       f"{metrics.get('metric:adverse_exposure') or metrics.get('metric:potential_exposure') or 'an unquantified amount'} {case['currency']}, "
                       f"severity {case['severity']}, confidence {case['confidence']}.",
            "statements": statements,
            "draft_recommendation": {"title": rec.get("title") or template["title"], "rationale": rec.get("rationale") or template["rationale"],
                                     "refs": [rule["ref"], *([d["ref"] for d in docs[:1]])], "requires_role": "finance_approver"},
            "confidence": case["confidence"],
            "limits": ["The investigation cites computed facts and governed documents only; it verifies nothing outside the payload.",
                       "A hypothesis is labelled as such and never becomes a fact without a person's confirmation."],
        }


# --------------------------------------------------------------------------- validation
def _check_statement(statement: dict[str, Any], payload: Payload, errors: list[str], where: str) -> None:
    if statement.get("type") not in STATEMENT_TYPES:
        errors.append(f"{where}: unknown statement type {statement.get('type')!r}")
    text = str(statement.get("text", ""))
    if not text.strip():
        errors.append(f"{where}: empty text")
    for pattern in INSTRUCTION_PATTERNS:
        if pattern.search(text):
            errors.append(f"{where}: instruction-like text refused")
    for m in NUMBER.findall(text):
        norm = _norm(m)
        if norm and norm not in payload.allowed_numbers and not re.fullmatch(r"\d{4}-\d{2}(-\d{2})?", m.strip()):
            errors.append(f"{where}: number {m.strip()!r} is not in the payload")
    refs = statement.get("refs")
    if not isinstance(refs, list):
        errors.append(f"{where}: refs must be a list")
        return
    for ref in refs:
        if ref not in payload.allowed_refs:
            errors.append(f"{where}: reference {ref!r} is not in the payload")
    if statement.get("type") == "OBSERVED_FACT" and not refs:
        errors.append(f"{where}: an observed fact needs at least one reference")
    if statement.get("type") == "HYPOTHESIS" and not statement.get("support"):
        errors.append(f"{where}: a hypothesis must state its support")


def validate_report(report: dict[str, Any], payload: Payload) -> list[str]:
    errors: list[str] = []
    if not isinstance(report, dict):
        return ["report is not an object"]
    for key in ("summary", "statements", "draft_recommendation", "confidence", "limits"):
        if key not in report:
            errors.append(f"missing {key}")
    if errors:
        return errors
    if report["confidence"] not in ("HIGH", "MEDIUM", "LOW"):
        errors.append("confidence must be HIGH, MEDIUM or LOW")
    _check_statement({"type": "OBSERVED_FACT", "text": report["summary"], "refs": ["summary"]}, payload, errors, "summary")
    errors = [e for e in errors if "reference 'summary'" not in e]
    if not isinstance(report["statements"], list) or not report["statements"]:
        errors.append("statements must be a non-empty list")
    else:
        for i, statement in enumerate(report["statements"]):
            _check_statement(statement, payload, errors, f"statement {i}")
    rec = report["draft_recommendation"]
    if not isinstance(rec, dict) or not rec.get("title") or not rec.get("rationale"):
        errors.append("draft_recommendation needs a title and a rationale")
    else:
        _check_statement({"type": "TRADE_OFF", "text": rec["title"] + " " + rec["rationale"], "refs": rec.get("refs", [])}, payload, errors, "draft_recommendation")
        if rec.get("requires_role") not in (None, "finance_approver", "admin"):
            errors.append("draft_recommendation.requires_role must be finance_approver")
    if not isinstance(report["limits"], list) or not report["limits"]:
        errors.append("limits must be a non-empty list")
    return errors


# --------------------------------------------------------------------------- orchestration
def investigate(conn: Connection, snapshot_id: uuid.UUID, case_ref: str, *, provider: Provider | None = None, corpus_dir=None,
                actor: str = "service:investigation") -> dict[str, Any]:
    payload = build_payload(conn, snapshot_id, case_ref, corpus_dir=corpus_dir)
    deterministic = DeterministicProvider()
    mode, label, fallback_reason, provider_name = "DETERMINISTIC_NO_LLM", "sans LLM", None, deterministic.name
    report: dict[str, Any]
    if provider is not None:
        try:
            report = provider.draft(payload.as_dict())
            errors = validate_report(report, payload)
            if errors:
                fallback_reason = "draft refused: " + "; ".join(errors[:5])
            else:
                mode, label, provider_name = "LLM", f"AI-generated interpretation ({provider.name})", provider.name
        except Exception as exc:  # noqa: BLE001 - degradation is the designed path
            fallback_reason = f"{type(exc).__name__}: {str(exc)[:200]}"
    if mode != "LLM":
        report = deterministic.draft(payload.as_dict())
        errors = validate_report(report, payload)
        if errors:
            raise ValidationError("the deterministic report failed its own validation: " + "; ".join(errors))
    result = {
        "schema_version": SCHEMA_VERSION, "question": QUESTION, "case_ref": case_ref, "snapshot_id": str(snapshot_id), "mode": mode, "label": label,
        "provider": provider_name, "fallback_reason": fallback_reason, "status": "COMPLETED", "report": report,
        "payload_hash": content_hash(payload.data), "documents_refused": payload.data["documents_refused"],
        "human_control": ("AI-generated interpretation. Controller approval required. Nothing here is a decision." if mode == "LLM"
                          else "Deterministic interpretation (sans LLM) from computed facts and governed documents. Controller approval required."),
    }
    investigation_id = uuid.uuid4()
    conn.execute(sa.text("""
        insert into decision.investigation (investigation_id, subject_type, subject_id, question, mode, snapshot_id, status, report, report_hash)
        values (:i, 'exception_case', :c, :q, :m, :s, 'COMPLETED', cast(:r as jsonb), :h)"""),
        {"i": investigation_id, "c": case_ref, "q": QUESTION, "m": mode, "s": snapshot_id, "r": canonical_json(result), "h": content_hash(result)})
    result["investigation_id"] = str(investigation_id)
    if mode == "LLM":
        _attach_llm_draft(conn, case_ref, report, snapshot_id, provider_name, investigation_id)
    append_event(conn, actor=actor, action="investigation.saved", object_type="exception_case", object_id=case_ref,
                 payload={"investigation_id": str(investigation_id), "mode": mode, "provider": provider_name, "fallback_reason": fallback_reason,
                          "payload_hash": result["payload_hash"], "report_hash": content_hash(result), "documents_cited": [d["ref"] for d in payload.data["documents"]]})
    return result


def _attach_llm_draft(conn: Connection, case_ref: str, report: dict[str, Any], snapshot_id: uuid.UUID, provider_name: str, investigation_id: uuid.UUID) -> None:
    """A validated model draft becomes a new recommendation version, pending review, only while the case is open."""
    case = conn.execute(sa.text("select * from decision.exception_case where case_ref = :r"), {"r": case_ref}).mappings().first()
    if case is None or case["status"] not in ("NEW", "OPEN", "UNDER_REVIEW", "EVIDENCE_REQUESTED", "DEFERRED"):
        return
    current = current_recommendation(conn, case["case_id"])
    if current is None:
        return
    draft = report["draft_recommendation"]
    conn.execute(sa.text("update decision.margin_recommendation set status = 'SUPERSEDED' where recommendation_id = :r"), {"r": current["recommendation_id"]})
    conn.execute(sa.text("""
        insert into decision.margin_recommendation (recommendation_id, case_id, version, source, action_key, title, rationale, requires_role, estimated_recovery,
            recovery_basis, expected_impact, evidence_refs, status, snapshot_id, rule_version, thresholds_version, payload_hash)
        values (:r, :c, :v, 'LLM_DRAFT', :k, :t, :ra, 'finance_approver', :e, :b, cast(:i as jsonb), cast(:ev as jsonb), 'PENDING_REVIEW', :s, :rv, :tv, :h)"""),
        {"r": uuid.uuid4(), "c": case["case_id"], "v": current["version"] + 1, "k": current["action_key"], "t": draft["title"][:200], "ra": draft["rationale"],
         "e": current["estimated_recovery"], "b": current["recovery_basis"], "i": canonical_json(current["expected_impact"]),
         "ev": canonical_json([*draft.get("refs", []), f"investigation:{investigation_id}"]), "s": snapshot_id, "rv": current["rule_version"],
         "tv": current["thresholds_version"], "h": content_hash({"provider": provider_name, "draft": draft, "investigation": str(investigation_id)})})


def latest_investigation(conn: Connection, case_ref: str) -> dict[str, Any] | None:
    row = conn.execute(sa.text("select investigation_id, mode, status, report, created_at from decision.investigation where subject_type = 'exception_case'"
                               " and subject_id = :c order by created_at desc limit 1"), {"c": case_ref}).mappings().first()
    if row is None:
        return None
    return {**row["report"], "investigation_id": str(row["investigation_id"]), "created_at": row["created_at"].isoformat()}


def report_text(result: dict[str, Any]) -> str:
    report = result["report"]
    lines = [f"{result['label']} | mode {result['mode']} | confidence {report['confidence']}", report["summary"], ""]
    for s in report["statements"]:
        refs = f" [{', '.join(s['refs'])}]" if s.get("refs") else ""
        lines.append(f"  [{s['type']}] {s['text']}{refs}" + (f" ({s['support']})" if s.get("support") else ""))
    rec = report["draft_recommendation"]
    lines.append(f"  Draft recommendation (requires {rec.get('requires_role', 'finance_approver')}): {rec['title']}. {rec['rationale']}")
    for limit in report["limits"]:
        lines.append(f"  [limit] {limit}")
    if result.get("fallback_reason"):
        lines.append(f"  [fallback] {result['fallback_reason']}")
    lines.append(f"  {result['human_control']}")
    return "\n".join(lines)


def to_json(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2, ensure_ascii=False, default=decimal_text)
