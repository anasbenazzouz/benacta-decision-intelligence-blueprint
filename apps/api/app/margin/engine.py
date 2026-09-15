"""Margin exception engine: reads governed facts and terms, applies the rules, stores computed evaluations,
keeps exception cases stable across snapshots and materialises gross margin per period.

Everything here is deterministic. It runs after `reconcile` because confidence reads the reconciliation status
of the period. It never reads the oracle and never calls a language model.
"""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection, Engine

from app.audit.log import append_event, canonical_json
from app.margin import kpis, rules
from app.margin.baseline import PricelistItem, resolve_baseline
from app.margin.decisions import ensure_recommendation
from app.margin.impact import measure_impacts
from app.margin.reference import ReferenceData, read_reference
from app.margin.rules import (
    Allocation,
    Baseline,
    CostFacts,
    InvoiceRef,
    LineFacts,
    OrderFacts,
    RuleResult,
    UnlinkedInvoiceLine,
)
from app.margin.thresholds import Thresholds, load_thresholds
from app.numbers import decimal_text

ENGINE_VERSION = "margin-engine.2026.09.1"
LEAKAGE_CLASSES = ("CONFIRMED_LEAKAGE", "PROBABLE_LEAKAGE")


def _rows(conn: Connection, sql: str, **params: Any) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(sa.text(sql), params).mappings()]


def _month_before(period: str, months: int) -> str:
    year, month = int(period[:4]), int(period[5:7])
    total = year * 12 + (month - 1) - months
    return f"{total // 12}-{total % 12 + 1:02d}"


@dataclass
class Evaluation:
    subject_type: str
    subject_id: int
    subject_ref: str
    company_id: int
    customer_id: int | None
    product_id: int | None
    sale_order_id: int | None
    order_date: date | None
    period: str
    currency_code: str
    overlap_group: str | None
    result: RuleResult


@dataclass
class EngineRun:
    snapshot_id: uuid.UUID
    source_instance: str
    thresholds: Thresholds
    evaluations: list[Evaluation] = field(default_factory=list)
    cases_created: int = 0
    cases_updated: int = 0
    cases_resolved: int = 0
    periods: int = 0
    reference_load: dict[str, Any] | None = None
    recommendations: dict[str, int] = field(default_factory=dict)
    impacts: dict[str, int] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        by_class: dict[str, int] = defaultdict(int)
        for e in self.evaluations:
            by_class[e.result.classification] += 1
        return {
            "snapshot_id": str(self.snapshot_id),
            "evaluations": len(self.evaluations),
            "by_classification": dict(sorted(by_class.items())),
            "cases_created": self.cases_created,
            "cases_updated": self.cases_updated,
            "cases_resolved": self.cases_resolved,
            "periods": self.periods,
            "recommendations": dict(sorted(self.recommendations.items())),
            "impacts": dict(sorted(self.impacts.items())),
            "thresholds": self.thresholds.stamp,
            "engine_version": ENGINE_VERSION,
        }


# --------------------------------------------------------------------------- loading facts
class _Facts:
    def __init__(self, conn: Connection, snapshot_id: uuid.UUID, thresholds: Thresholds):
        self.conn, self.s, self.t = conn, snapshot_id, thresholds
        snapshot = conn.execute(sa.text("select source_instance from marts.snapshot where snapshot_id = :s"), {"s": snapshot_id}).first()
        if snapshot is None:
            raise ValueError(f"snapshot {snapshot_id} has no marts; run marts first")
        self.source_instance = snapshot.source_instance
        self.company_currency = {r["company_id"]: r["currency_code"] for r in _rows(conn, "select company_id, currency_code from marts.dim_company where snapshot_id = :s", s=snapshot_id)}
        self.reconciled = {
            (r["company_id"], r["period"]): r["status"] == "RECONCILED"
            for r in _rows(conn, "select company_id, period, status from marts.reconciliation_result where snapshot_id = :s and check_id = 'REVENUE_POSTED'", s=snapshot_id)
        }
        self.products = {r["product_id"]: r for r in _rows(conn, "select * from marts.dim_product where snapshot_id = :s", s=snapshot_id)}
        self.partners = {r["partner_id"]: r for r in _rows(conn, "select * from marts.dim_partner where snapshot_id = :s", s=snapshot_id)}
        self.pricelists = {r["pricelist_id"]: r for r in _rows(conn, "select * from marts.dim_pricelist where snapshot_id = :s", s=snapshot_id)}
        self.items: dict[int, list[PricelistItem]] = defaultdict(list)
        for r in _rows(conn, "select * from marts.dim_pricelist_item where snapshot_id = :s", s=snapshot_id):
            self.items[r["pricelist_id"]].append(PricelistItem(
                r["item_id"], r["pricelist_id"], r["applied_on"], r["product_template_id"], r["product_id"], r["category_id"],
                r["min_quantity"], r["compute_price"], r["fixed_price"], r["percent_price"], r["currency_code"], r["date_start"], r["date_end"]))
        self.invoices: dict[int, list[InvoiceRef]] = defaultdict(list)
        self.invoice_ids_by_line: dict[int, set[int]] = defaultdict(set)
        for r in _rows(conn, """
            select b.sale_line_id, b.allocation_weight, i.invoice_line_id, i.invoice_id, i.invoice_name, i.move_type,
                   to_char(i.accounting_date, 'YYYY-MM') as period, i.subtotal_signed, i.revenue_company_ccy, i.product_id
            from marts.bridge_sale_invoice_line b
            join marts.fact_invoice_line i on i.snapshot_id = b.snapshot_id and i.invoice_line_id = b.invoice_line_id
            where b.snapshot_id = :s order by i.accounting_date, i.invoice_line_id""", s=snapshot_id):
            self.invoices[r["sale_line_id"]].append(InvoiceRef(r["invoice_id"], r["invoice_name"], r["move_type"], r["period"],
                                                               r["subtotal_signed"], r["revenue_company_ccy"], r["allocation_weight"]))
            self.invoice_ids_by_line[r["sale_line_id"]].add(r["invoice_id"])
        self.allocations: dict[int, list[Allocation]] = defaultdict(list)
        for r in _rows(conn, "select * from marts.fact_cost_allocation where snapshot_id = :s and sale_line_id is not null order by delivery_move_id, allocation_no", s=snapshot_id):
            self.allocations[r["sale_line_id"]].append(Allocation(r["delivery_move_id"], r["receipt_move_id"], r["quantity"], r["unit_cost"],
                                                                  r["amount"], r["status"], r["reason"]))
        self.delivered_units: dict[int, Decimal] = defaultdict(Decimal)
        for r in _rows(conn, "select sale_line_id, sum(qty_product_uom) as units from marts.fact_stock_move where snapshot_id = :s"
                             " and direction = 'outgoing' and state = 'done' and sale_line_id is not null group by 1", s=snapshot_id):
            self.delivered_units[r["sale_line_id"]] = r["units"]
        self.lines_raw = _rows(conn, "select * from marts.fact_sales_order_line where snapshot_id = :s order by order_date, sale_line_id", s=snapshot_id)
        # Freight invoice lines that carry no order link, keyed by invoice: attributed to the order invoiced on the same document.
        self.unlinked_freight_by_invoice: dict[int, list[dict[str, Any]]] = defaultdict(list)
        self.unlinked_lines = _rows(conn, """
            select i.*, p.default_code, to_char(i.accounting_date, 'YYYY-MM') as period
            from marts.fact_invoice_line i
            left join marts.dim_product p on p.snapshot_id = i.snapshot_id and p.product_id = i.product_id
            where i.snapshot_id = :s and not exists (select 1 from marts.bridge_sale_invoice_line b
                                                     where b.snapshot_id = i.snapshot_id and b.invoice_line_id = i.invoice_line_id)
            order by i.accounting_date, i.invoice_line_id""", s=snapshot_id)
        for r in self.unlinked_lines:
            if r["default_code"] in thresholds.freight_product_codes:
                self.unlinked_freight_by_invoice[r["invoice_id"]].append(r)
        self.history: dict[tuple[int, str], list[tuple[date, int, Decimal]]] = defaultdict(list)
        for r in self.lines_raw:
            if r["order_state"] == "sale" and r["product_id"] is not None and r["qty_ordered"] and r["qty_ordered_product_uom"]:
                per_unit = r["price_unit"] * r["qty_ordered"] / r["qty_ordered_product_uom"]
                company = per_unit / r["fx_rate"] if r["fx_rate"] else per_unit
                self.history[(r["company_id"], str(r["product_id"]))].append((r["order_date"], r["sale_line_id"], company))

    def period_reconciled(self, company_id: int, period: str | None) -> bool:
        return True if period is None else self.reconciled.get((company_id, period), False)

    def line(self, r: dict[str, Any]) -> LineFacts:
        product = self.products.get(r["product_id"], {})
        partner = self.partners.get(r["customer_id"], {})
        invoices = tuple(self.invoices.get(r["sale_line_id"], []))
        first_period = min((i.period for i in invoices if i.move_type == "out_invoice"), default=None)
        return LineFacts(
            sale_line_id=r["sale_line_id"], sale_order_id=r["sale_order_id"], order_name=r["order_name"], order_state=r["order_state"],
            order_date=r["order_date"], company_id=r["company_id"], customer_id=r["customer_id"], customer_ref=partner.get("ref"),
            product_id=r["product_id"], product_code=product.get("default_code"), product_name=product.get("name"),
            product_type=product.get("product_type", "unknown"), is_storable=product.get("is_storable"),
            is_freight=(product.get("default_code") in self.t.freight_product_codes), currency_code=r["currency_code"],
            company_currency=self.company_currency.get(r["company_id"], "EUR"), fx_rate=r["fx_rate"], qty_ordered=r["qty_ordered"],
            qty_product_uom=r["qty_ordered_product_uom"], price_unit=r["price_unit"], discount_pct=r["discount_pct"], subtotal=r["subtotal"],
            qty_delivered=r["qty_delivered"], qty_invoiced=r["qty_invoiced"], invoices=invoices, pricelist_id=r["pricelist_id"],
            customer_pricelist_id=partner.get("pricelist_id"), list_price=product.get("list_price"),
            period_reconciled=self.period_reconciled(r["company_id"], first_period),
        )

    def history_for(self, line: LineFacts) -> list[Decimal]:
        start = _month_before(f"{line.order_date.year}-{line.order_date.month:02d}", self.t.historical_months)
        first = date(int(start[:4]), int(start[5:7]), 1)
        return [price for (day, lid, price) in self.history.get((line.company_id, str(line.product_id)), [])
                if lid != line.sale_line_id and first <= day < line.order_date]

    def baseline(self, line: LineFacts, ref: ReferenceData) -> Baseline:
        product = self.products.get(line.product_id, {})
        customer_list = self.pricelists.get(line.customer_pricelist_id or -1)
        order_list = self.pricelists.get(line.pricelist_id or -1)
        return resolve_baseline(
            line,
            contract=ref.contract_price_for(line.customer_ref, line.product_code, line.order_date, line.qty_product_uom or line.qty_ordered),
            customer_items=self.items.get(line.customer_pricelist_id or -1, []),
            customer_pricelist_currency=customer_list["currency_code"] if customer_list else None,
            order_items=self.items.get(line.pricelist_id or -1, []),
            order_pricelist_currency=order_list["currency_code"] if order_list else None,
            template_id=product.get("template_id"), category_id=product.get("category_id"),
            history_company_ccy=self.history_for(line), thresholds=self.t,
        )

    def cost(self, line: LineFacts, ref: ReferenceData) -> CostFacts:
        return CostFacts(tuple(self.allocations.get(line.sale_line_id, [])), self.delivered_units.get(line.sale_line_id, Decimal(0)),
                         ref.cost_reference_for(line.product_code, line.order_date))

    def order(self, sale_order_id: int, lines: list[LineFacts]) -> OrderFacts:
        head = lines[0]
        goods = tuple(ln for ln in lines if not ln.is_freight)
        freight = tuple(ln for ln in lines if ln.is_freight)
        invoiced = Decimal(0)
        refs: list[dict[str, Any]] = []
        for fl in freight:
            for inv in fl.invoices:
                weight = inv.allocation_weight if inv.allocation_weight is not None else Decimal(1)
                invoiced += inv.subtotal_signed * weight
                refs.append({"invoice": inv.invoice_name, "invoice_id": inv.invoice_id, "subtotal_signed": decimal_text(inv.subtotal_signed), "link": "order line"})
        seen = {r["invoice_id"] for r in refs}
        for gl in goods:
            for invoice_id in self.invoice_ids_by_line.get(gl.sale_line_id, set()):
                for r in self.unlinked_freight_by_invoice.get(invoice_id, []):
                    if r["invoice_line_id"] not in seen:
                        seen.add(r["invoice_line_id"])
                        invoiced += r["subtotal_signed"]
                        refs.append({"invoice": r["invoice_name"], "invoice_id": r["invoice_id"], "subtotal_signed": decimal_text(r["subtotal_signed"]),
                                     "link": "same invoice, no order line"})
        return OrderFacts(sale_order_id, head.order_name, head.order_state, head.order_date, head.company_id, head.customer_id, head.customer_ref,
                          head.currency_code, head.fx_rate, goods, freight, invoiced, tuple(refs),
                          period_reconciled=all(ln.period_reconciled for ln in goods) if goods else True)


# --------------------------------------------------------------------------- running the rules
def evaluate_snapshot(conn: Connection, snapshot_id: uuid.UUID, thresholds: Thresholds | None = None) -> EngineRun:
    thresholds = thresholds or load_thresholds()
    facts = _Facts(conn, snapshot_id, thresholds)
    run = EngineRun(snapshot_id, facts.source_instance, thresholds)
    references: dict[int, ReferenceData] = {}

    def ref_for(company_id: int) -> ReferenceData:
        if company_id not in references:
            references[company_id] = read_reference(conn, facts.source_instance, company_id)
            if run.reference_load is None and references[company_id].load:
                run.reference_load = {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in references[company_id].load.items()}
        return references[company_id]

    by_order: dict[int, list[LineFacts]] = defaultdict(list)
    for raw in facts.lines_raw:
        line = facts.line(raw)
        by_order[line.sale_order_id].append(line)
        ref = ref_for(line.company_id)
        segment = ref.segment_of(line.customer_ref, line.order_date)
        applicable, expired = ref.policies_for(line.customer_ref, segment, line.order_date)
        derogation = ref.derogation_for(line.order_name, line.order_date)
        results = [
            rules.evaluate_discount_cap(line, segment=segment, applicable=applicable, expired=expired, derogation=derogation, thresholds=thresholds),
            rules.evaluate_price_baseline(line, facts.baseline(line, ref), thresholds=thresholds),
            rules.evaluate_cost_variance(line, facts.cost(line, ref), thresholds=thresholds),
        ]
        for result in results:
            run.evaluations.append(Evaluation("sale_order_line", line.sale_line_id, f"{line.order_name} / {line.product_code or line.sale_line_id}",
                                              line.company_id, line.customer_id, line.product_id, line.sale_order_id, line.order_date, line.period,
                                              line.company_currency, f"sale_order_line:{line.sale_line_id}", result))
    for sale_order_id, lines in by_order.items():
        order = facts.order(sale_order_id, lines)
        ref = ref_for(order.company_id)
        result = rules.evaluate_freight(order, ref.freight_contract_for(order.customer_ref, order.order_date), thresholds=thresholds)
        head = lines[0]
        run.evaluations.append(Evaluation("sale_order", sale_order_id, order.order_name, order.company_id, order.customer_id, None, sale_order_id,
                                          order.order_date, order.period, head.company_currency, f"sale_order:{sale_order_id}", result))
    for r in facts.unlinked_lines:
        line = UnlinkedInvoiceLine(r["invoice_line_id"], r["invoice_id"], r["invoice_name"], r["move_type"], r["company_id"], r["customer_id"],
                                   r["product_id"], r["default_code"], r["period"], r["accounting_date"], r["revenue_company_ccy"],
                                   facts.period_reconciled(r["company_id"], r["period"]))
        result = rules.evaluate_unlinked_invoice_line(line, thresholds=thresholds)
        run.evaluations.append(Evaluation("invoice_line", line.invoice_line_id, f"{line.invoice_name} / {line.product_code or line.invoice_line_id}",
                                          line.company_id, line.customer_id, line.product_id, None, line.accounting_date, line.period,
                                          facts.company_currency.get(line.company_id, "EUR"), None, result))
    return run


# --------------------------------------------------------------------------- storing
def store_run(conn: Connection, run: EngineRun, *, actor: str = "service:margin-engine") -> None:
    s = run.snapshot_id
    conn.execute(sa.text("delete from marts.fact_margin_rule_evaluation where snapshot_id = :s"), {"s": s})
    rows = []
    for e in run.evaluations:
        r = e.result
        rows.append({
            "s": s, "rule": r.rule_id, "rv": r.rule_version, "st": e.subject_type, "sid": e.subject_id, "sref": e.subject_ref, "co": e.company_id,
            "cu": e.customer_id, "pr": e.product_id, "so": e.sale_order_id, "od": e.order_date, "pe": e.period, "out": r.outcome, "cl": r.classification,
            "ca": r.cause, "et": r.exposure_type, "cp": r.component, "ex": r.expected_amount, "ac": r.actual_amount, "ad": r.adverse_exposure,
            "po": r.potential_exposure, "es": r.exposure_stage, "cc": e.currency_code, "sev": r.severity, "conf": r.confidence, "ctl": r.controllability,
            "mat": r.material, "rev": r.requires_human_review, "og": e.overlap_group, "ev": canonical_json({**r.evidence, "reason": r.reason}),
            "f": r.formula, "tv": run.thresholds.stamp,
        })
    if rows:
        conn.execute(sa.text("""
            insert into marts.fact_margin_rule_evaluation (snapshot_id, rule_id, rule_version, subject_type, subject_id, subject_ref, company_id,
                customer_id, product_id, sale_order_id, order_date, period, outcome, classification, cause, exposure_type, component,
                expected_amount, actual_amount, adverse_exposure, potential_exposure, exposure_stage, currency_code, severity, confidence,
                controllability, material, requires_human_review, overlap_group, evidence, formula, thresholds_version)
            values (:s, :rule, :rv, :st, :sid, :sref, :co, :cu, :pr, :so, :od, :pe, :out, :cl, :ca, :et, :cp, :ex, :ac, :ad, :po, :es, :cc,
                :sev, :conf, :ctl, :mat, :rev, :og, cast(:ev as jsonb), :f, :tv)"""), rows)
    _upsert_cases(conn, run)
    _ensure_recommendations(conn, run)
    run.periods = _store_periods(conn, run)
    run.impacts = measure_impacts(conn, s, run.source_instance, freight_codes=run.thresholds.freight_product_codes)
    append_event(conn, actor=actor, action="margin.exceptions_computed", object_type="snapshot", object_id=str(s), run_id=str(s),
                 payload={**run.summary(), "reference_load": run.reference_load})


def _upsert_cases(conn: Connection, run: EngineRun) -> None:
    s, instance = run.snapshot_id, run.source_instance
    current_keys: set[str] = set()
    for e in run.evaluations:
        r = e.result
        if not r.creates_case:
            continue
        key = f"{r.rule_id}:{e.subject_type}:{e.subject_id}"
        current_keys.add(key)
        existing = conn.execute(sa.text("select case_id from decision.exception_case where source_instance = :i and exception_key = :k"),
                                {"i": instance, "k": key}).first()
        if existing is None:
            seq = conn.execute(sa.text("select nextval('decision.exception_case_ref_seq')")).scalar_one()
            conn.execute(sa.text("""
                insert into decision.exception_case (case_id, case_ref, source_instance, company_id, exception_key, rule_id, subject_type, subject_id,
                    subject_ref, first_snapshot_id, last_snapshot_id, classification, cause, severity, adverse_exposure, potential_exposure)
                values (:c, :ref, :i, :co, :k, :rule, :st, :sid, :sref, :s, :s, :cl, :ca, :sev, :ad, :po)"""),
                {"c": uuid.uuid4(), "ref": f"MC-{seq:06d}", "i": instance, "co": e.company_id, "k": key, "rule": r.rule_id, "st": e.subject_type,
                 "sid": e.subject_id, "sref": e.subject_ref, "s": s, "cl": r.classification, "ca": r.cause, "sev": r.severity,
                 "ad": r.adverse_exposure, "po": r.potential_exposure})
            run.cases_created += 1
        else:
            conn.execute(sa.text("""
                update decision.exception_case set last_snapshot_id = :s, last_seen_at = now(), classification = :cl, cause = :ca, severity = :sev,
                    adverse_exposure = :ad, potential_exposure = :po, resolved_snapshot_id = null, resolved_note = null,
                    status = case when status = 'NO_LONGER_RAISED' then 'OPEN' else status end
                where case_id = :c"""),
                {"s": s, "cl": r.classification, "ca": r.cause, "sev": r.severity, "ad": r.adverse_exposure, "po": r.potential_exposure,
                 "c": existing.case_id})
            run.cases_updated += 1
    # A case whose exception the newest snapshot of the instance no longer raises is closed with the reason recorded:
    # the evaluation now classifies differently (source corrected, or a rule or threshold changed), or the subject is gone.
    latest = conn.execute(sa.text("select max(batch_seq) from marts.snapshot where source_instance = :i"), {"i": instance}).scalar()
    this_seq = conn.execute(sa.text("select batch_seq from marts.snapshot where snapshot_id = :s"), {"s": s}).scalar()
    if latest is not None and this_seq == latest:
        stale = conn.execute(sa.text("""
            select case_id, rule_id, subject_type, subject_id from decision.exception_case
            where source_instance = :i and status not in ('CLOSED', 'NO_LONGER_RAISED') and last_snapshot_id <> :s
              and exception_key <> all(:keys)"""), {"s": s, "i": instance, "keys": sorted(current_keys) or [""]}).mappings().all()
        current = {(e.result.rule_id, e.subject_type, e.subject_id): e.result for e in run.evaluations}
        for case in stale:
            now = current.get((case["rule_id"], case["subject_type"], case["subject_id"]))
            note = (f"subject absent from snapshot {s}" if now is None else
                    f"{now.outcome} / {now.classification} ({now.cause}) in snapshot {s}, rule v{now.rule_version}, thresholds {run.thresholds.stamp}")
            conn.execute(sa.text("update decision.exception_case set status = 'NO_LONGER_RAISED', resolved_snapshot_id = :s, resolved_note = :n"
                                 " where case_id = :c"), {"s": s, "n": note, "c": case["case_id"]})
        run.cases_resolved = len(stale)


def _ensure_recommendations(conn: Connection, run: EngineRun) -> None:
    """Every open case carries one pending recommendation built from its latest evaluation."""
    for e in run.evaluations:
        r = e.result
        if not r.creates_case:
            continue
        case = conn.execute(sa.text("select * from decision.exception_case where source_instance = :i and exception_key = :k"),
                            {"i": run.source_instance, "k": f"{r.rule_id}:{e.subject_type}:{e.subject_id}"}).mappings().first()
        if case is None:
            continue
        evaluation = {"cause": r.cause, "classification": r.classification, "adverse_exposure": r.adverse_exposure,
                      "potential_exposure": r.potential_exposure, "exposure_stage": r.exposure_stage, "rule_id": r.rule_id,
                      "rule_version": r.rule_version, "subject_type": e.subject_type, "subject_id": e.subject_id}
        outcome = ensure_recommendation(conn, dict(case), evaluation, snapshot_id=run.snapshot_id, thresholds_version=run.thresholds.stamp)
        run.recommendations[outcome] = run.recommendations.get(outcome, 0) + 1


def _store_periods(conn: Connection, run: EngineRun) -> int:
    s = run.snapshot_id
    conn.execute(sa.text("delete from marts.fact_margin_period where snapshot_id = :s"), {"s": s})
    revenue = _rows(conn, "select company_id, to_char(accounting_date, 'YYYY-MM') as period, sum(revenue_company_ccy) as revenue, count(*) as lines"
                          " from marts.fact_invoice_line where snapshot_id = :s group by 1, 2", s=s)
    cogs = {(r["company_id"], r["period"]): r["cogs"] for r in _rows(
        conn, "select company_id, to_char(accounting_date, 'YYYY-MM') as period, sum(balance) as cogs from marts.fact_posted_cogs_line"
              " where snapshot_id = :s group by 1, 2", s=s)}
    recon = {(r["company_id"], r["period"], r["check_id"]): r["status"] for r in _rows(
        conn, "select company_id, period, check_id, status from marts.reconciliation_result where snapshot_id = :s", s=s)}
    leak: dict[tuple[int, str], dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    counts: dict[tuple[int, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for e in run.evaluations:
        r = e.result
        key = (e.company_id, e.period)
        if r.classification in LEAKAGE_CLASSES and r.adverse_exposure:
            leak[key][r.exposure_type or "other"] += r.adverse_exposure
            leak[key]["addressable"] += kpis.total_addressable_leakage([(r.adverse_exposure, r.controllability)])
            leak[key]["recoverable"] += kpis.recoverable_from_customer([(r.adverse_exposure, r.component or "")])
        if r.rule_id == "INVOICE_WITHOUT_SALE_LINK" and r.potential_exposure:
            leak[key]["untraceable"] += r.potential_exposure
        if r.creates_case:
            counts[key]["material" if r.material else "review"] += 1
    split = {(r["company_id"], r["period"]): r for r in _rows(
        conn, "select i.company_id, to_char(i.accounting_date, 'YYYY-MM') as period,"
              " sum(case when p.product_type = 'service' then i.revenue_company_ccy else 0 end) as services,"
              " sum(case when p.product_type = 'service' then 0 else i.revenue_company_ccy end) as goods"
              " from marts.fact_invoice_line i left join marts.dim_product p on p.snapshot_id = i.snapshot_id and p.product_id = i.product_id"
              " where i.snapshot_id = :s group by 1, 2", s=s)}
    rows = []
    for r in revenue:
        key = (r["company_id"], r["period"])
        rev_status = recon.get((*key, "REVENUE_POSTED"), "UNAVAILABLE")
        cogs_status = recon.get((*key, "COGS_POSTED"), "UNAVAILABLE")
        cogs_value = cogs.get(key)
        basis, status = kpis.margin_basis(rev_status, cogs_status, cogs_value)
        gm = None if basis == "UNAVAILABLE" else kpis.gross_margin(r["revenue"], cogs_value)
        gm_pct = kpis.gross_margin_pct(gm, r["revenue"])
        lk = leak[key]
        rows.append({
            "s": s, "co": key[0], "pe": key[1], "rev": r["revenue"], "rg": split.get(key, {}).get("goods", Decimal(0)),
            "rs": split.get(key, {}).get("services", Decimal(0)), "cogs": None if basis == "UNAVAILABLE" else cogs_value, "gm": gm, "gmp": gm_pct,
            "basis": basis, "status": status, "rr": rev_status, "cr": cogs_status, "dl": lk["discount"], "pl": lk["price"], "fl": lk["freight"],
            "cl": lk["cost"], "tl": lk["addressable"], "rc": lk["recoverable"], "ut": lk["untraceable"], "em": counts[key]["material"],
            "er": counts[key]["review"], "il": r["lines"],
        })
    if rows:
        conn.execute(sa.text("""
            insert into marts.fact_margin_period (snapshot_id, company_id, period, revenue, revenue_goods, revenue_services, cogs, gross_margin,
                gross_margin_pct, margin_basis, margin_status, revenue_reconciliation, cogs_reconciliation, discount_leakage, price_leakage,
                freight_leakage, cost_leakage, total_addressable_leakage, recoverable_from_customer, untraceable_revenue, exceptions_material,
                exceptions_review, invoice_lines)
            values (:s, :co, :pe, :rev, :rg, :rs, :cogs, :gm, :gmp, :basis, :status, :rr, :cr, :dl, :pl, :fl, :cl, :tl, :rc, :ut, :em, :er, :il)"""), rows)
    return len(rows)


def run_engine(engine: Engine, snapshot_id: uuid.UUID, thresholds: Thresholds | None = None) -> EngineRun:
    with engine.begin() as conn:
        run = evaluate_snapshot(conn, snapshot_id, thresholds)
        store_run(conn, run)
    return run


def dump_evaluation(e: Evaluation) -> dict[str, Any]:
    r = e.result
    return json.loads(canonical_json({
        "rule_id": r.rule_id, "rule_version": r.rule_version, "subject_type": e.subject_type, "subject_id": e.subject_id, "subject_ref": e.subject_ref,
        "period": e.period, "outcome": r.outcome, "classification": r.classification, "cause": r.cause, "exposure_type": r.exposure_type,
        "component": r.component, "expected_amount": r.expected_amount, "actual_amount": r.actual_amount, "adverse_exposure": r.adverse_exposure,
        "potential_exposure": r.potential_exposure, "exposure_stage": r.exposure_stage, "severity": r.severity, "confidence": r.confidence,
        "controllability": r.controllability, "material": r.material, "requires_human_review": r.requires_human_review, "reason": r.reason,
    }))
