"""Plan import: staging -> validation -> error report -> DRAFT version.

The same path serves CSV files, an optional spreadsheet adapter and generated seeds. An import never creates a
submitted, approved or locked version, and an empty cell stays NULL: it is never read as zero.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from app.audit.log import append_event
from app.planning.domain import (
    ALL_CATEGORIES,
    COST_MEASURES,
    CSV_COLUMNS,
    MEASURES,
    REVENUE_CATEGORY,
    REVENUE_MEASURES,
    VERSION_HEADER_COLUMNS,
    Actor,
    ImportResult,
    Role,
    Scenario,
    ValidationIssue,
    VersionType,
)

COST_TOLERANCE = Decimal("0.01")


@dataclass(frozen=True)
class ImportContext:
    company_id: int
    source_instance: str
    known_projects: dict[str, str]  # project_code -> business unit
    expected_totals: dict[str, Decimal] | None = None  # optional control totals by measure


@dataclass
class StagedRow:
    row_number: int
    values: dict[str, Any]


def parse_csv(content: bytes) -> list[dict[str, str]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in CSV_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"missing columns: {', '.join(missing)}")
    return [dict(row) for row in reader]


def _text(raw: dict[str, Any], name: str) -> str:
    value = raw.get(name)
    return "" if value is None else str(value).strip()


def _period(value: str) -> date | None:
    try:
        if len(value) == 7:
            return date.fromisoformat(value + "-01")
        parsed = date.fromisoformat(value)
        return parsed if parsed.day == 1 else None
    except ValueError:
        return None


def _decimal(value: str) -> Decimal:
    """Accept 1234.56 or 1234,56 (decimal comma). Thousands separators are rejected rather than guessed."""
    compact = value.replace(" ", "").replace(" ", "")
    if "," in compact and "." not in compact:
        compact = compact.replace(",", ".")
    return Decimal(compact)


def validate(rows: list[dict[str, Any]], ctx: ImportContext, actor: Actor) -> tuple[list[StagedRow], list[ValidationIssue], dict[str, Decimal]]:
    issues: list[ValidationIssue] = []
    staged: list[StagedRow] = []
    if not rows:
        return [], [ValidationIssue(0, "EMPTY_FILE", "the file contains no data rows")], {}

    if not actor.can(Role.PROJECT_CONTROLLER):
        issues.append(ValidationIssue(0, "NOT_AUTHORISED", "importing plans requires the project_controller role"))

    headers = {tuple(_text(r, c) for c in VERSION_HEADER_COLUMNS) for r in rows}
    if len(headers) > 1:
        issues.append(ValidationIssue(0, "MIXED_VERSIONS", "one file must describe exactly one version (same project, type, scenario, label, cutoff, currency)"))
    header = dict(zip(VERSION_HEADER_COLUMNS, next(iter(headers)), strict=True))

    if header["version_type"] not in VersionType.__members__:
        issues.append(ValidationIssue(0, "INVALID_VERSION_TYPE", f"version_type must be one of {', '.join(VersionType)}", "version_type"))
    if header["scenario"] not in Scenario.__members__:
        issues.append(ValidationIssue(0, "INVALID_SCENARIO", f"scenario must be one of {', '.join(Scenario)}", "scenario"))
    if not header["label"]:
        issues.append(ValidationIssue(0, "MISSING_VALUE", "label is required", "label"))
    if len(header["currency"]) != 3 or not header["currency"].isalpha() or not header["currency"].isupper():
        issues.append(ValidationIssue(0, "INVALID_CURRENCY", "currency must be an ISO 4217 code such as EUR", "currency"))
    cutoff = None
    if header["cutoff_date"]:
        try:
            cutoff = date.fromisoformat(header["cutoff_date"])
        except ValueError:
            issues.append(ValidationIssue(0, "INVALID_DATE", "cutoff_date must be YYYY-MM-DD", "cutoff_date"))
    if header["version_type"] == VersionType.FORECAST and cutoff is None:
        issues.append(ValidationIssue(0, "MISSING_VALUE", "cutoff_date is required for a FORECAST", "cutoff_date"))

    project = header["project_code"]
    if project not in ctx.known_projects:
        issues.append(ValidationIssue(0, "UNKNOWN_PROJECT", f"project {project or '(empty)'} does not exist in the snapshot", "project_code"))
    elif not actor.can_access_project(ctx.company_id, project):
        issues.append(ValidationIssue(0, "NOT_AUTHORISED", f"{actor.user_id} may not plan project {project}", "project_code"))

    seen: set[tuple] = set()
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for number, raw in enumerate(rows, start=2):  # row 1 is the header line
        row: dict[str, Any] = {}
        for name in ("business_unit", "work_package", "cost_category", "resource_or_role"):
            row[name] = _text(raw, name)
        for name in ("business_unit", "work_package", "cost_category"):
            if not row[name]:
                issues.append(ValidationIssue(number, "MISSING_VALUE", f"{name} is required", name))
        if row["cost_category"] and row["cost_category"] not in ALL_CATEGORIES:
            issues.append(ValidationIssue(number, "INVALID_CATEGORY", f"cost_category must be one of {', '.join(ALL_CATEGORIES)}", "cost_category"))
        if project in ctx.known_projects and row["business_unit"] and row["business_unit"] != ctx.known_projects[project]:
            issues.append(ValidationIssue(number, "BUSINESS_UNIT_MISMATCH", f"project {project} belongs to {ctx.known_projects[project]}", "business_unit"))

        period = _period(_text(raw, "period"))
        if period is None:
            issues.append(ValidationIssue(number, "INVALID_PERIOD", "period must be YYYY-MM or the first day of a month", "period"))
        elif header["version_type"] == VersionType.FORECAST and cutoff and period <= date(cutoff.year, cutoff.month, 1):
            issues.append(ValidationIssue(number, "PERIOD_NOT_AFTER_CUTOFF", "a forecast only plans periods after its cutoff month", "period"))
        row["period"] = period

        present: dict[str, Decimal | None] = {}
        for measure in MEASURES:
            text = _text(raw, measure)
            if text == "":
                present[measure] = None  # empty stays empty, never zero
                continue
            try:
                present[measure] = _decimal(text)
            except InvalidOperation:
                issues.append(ValidationIssue(number, "INVALID_NUMBER", f"{measure} is not a number", measure))
                present[measure] = None
        row.update(present)

        category = row["cost_category"]
        if category == REVENUE_CATEGORY:
            if any(present[m] is not None for m in COST_MEASURES):
                issues.append(ValidationIssue(number, "MEASURE_NOT_ALLOWED", "REVENUE rows carry revenue, billing or cash only", None))
            if all(present[m] is None for m in REVENUE_MEASURES):
                issues.append(ValidationIssue(number, "NO_MEASURE", "a REVENUE row needs at least one revenue, billing or cash value", None))
        elif category in ALL_CATEGORIES:
            if any(present[m] is not None for m in REVENUE_MEASURES):
                issues.append(ValidationIssue(number, "MEASURE_NOT_ALLOWED", "cost rows carry hours, rate and cost only", None))
            if all(present[m] is None for m in COST_MEASURES):
                issues.append(ValidationIssue(number, "NO_MEASURE", "a cost row needs hours or cost", None))
            for measure in ("planned_hours", "planned_rate"):
                if present[measure] is not None and present[measure] < 0:
                    issues.append(ValidationIssue(number, "NEGATIVE_VALUE", f"{measure} cannot be negative", measure))
            hours, rate, cost = present["planned_hours"], present["planned_rate"], present["planned_cost"]
            if hours is not None and rate is not None and cost is not None and abs(hours * rate - cost) > COST_TOLERANCE:
                issues.append(ValidationIssue(number, "COST_NOT_HOURS_TIMES_RATE", f"planned_cost {cost} differs from hours x rate {hours * rate}", "planned_cost"))
            if category == "LABOUR" and not row["resource_or_role"]:
                issues.append(ValidationIssue(number, "MISSING_VALUE", "LABOUR rows need a resource or role", "resource_or_role"))

        key = (row["work_package"], category, row["resource_or_role"], period)
        if key in seen:
            issues.append(ValidationIssue(number, "DUPLICATE_ROW", "same work package, category, resource and period appear twice", None))
        seen.add(key)
        for measure, value in present.items():
            if value is not None:
                totals[measure] += value
        staged.append(StagedRow(number, row))

    if ctx.expected_totals:
        for measure, expected in ctx.expected_totals.items():
            if totals.get(measure, Decimal(0)) != expected:
                issues.append(ValidationIssue(0, "CONTROL_TOTAL_MISMATCH", f"{measure} total {totals.get(measure, Decimal(0))} differs from control total {expected}", measure))
    for row in staged:
        row.values["_header"] = header
        row.values["_cutoff"] = cutoff
    return staged, issues, dict(totals)


def import_plan(
    conn: Connection,
    rows: list[dict[str, Any]],
    ctx: ImportContext,
    actor: Actor,
    *,
    source: str,
    file_name: str | None = None,
    raw_bytes: bytes | None = None,
) -> ImportResult:
    """Validate and, only when clean, create a DRAFT version in the caller's transaction."""
    import_id = uuid.uuid4()
    digest_source = raw_bytes if raw_bytes is not None else repr(rows).encode("utf-8")
    file_hash = hashlib.sha256(digest_source).hexdigest()
    staged, issues, totals = validate(rows, ctx, actor)
    status = "REJECTED" if issues else "VALIDATED"
    version_id = uuid.uuid4() if not issues else None

    conn.execute(
        sa.text(
            "insert into planning.import_batch (import_id, source, file_name, file_hash, author, status, row_count,"
            " error_count, totals) values (:i, :s, :f, :h, :a, :st, :rc, :ec, cast(:t as jsonb))"
        ),
        {"i": import_id, "s": source, "f": file_name, "h": file_hash, "a": actor.user_id, "st": status,
         "rc": len(rows), "ec": len(issues), "t": _json_totals(totals)},
    )
    if issues:
        conn.execute(
            sa.text(
                "insert into planning.import_error (import_id, row_number, field, code, message)"
                " values (:i, :r, :f, :c, :m) on conflict do nothing"
            ),
            [{"i": import_id, "r": e.row_number, "f": e.field or "", "c": e.code, "m": e.message} for e in issues],
        )
    else:
        header = staged[0].values["_header"]
        conn.execute(
            sa.text(
                "insert into planning.plan_version (version_id, company_id, source_instance, project_code, version_type,"
                " scenario, label, cutoff_date, currency, status, author, source, import_id)"
                " values (:v, :c, :si, :p, :vt, :sc, :l, :cut, :cur, 'DRAFT', :a, :src, :i)"
            ),
            {"v": version_id, "c": ctx.company_id, "si": ctx.source_instance, "p": header["project_code"],
             "vt": header["version_type"], "sc": header["scenario"], "l": header["label"],
             "cut": staged[0].values["_cutoff"], "cur": header["currency"], "a": actor.user_id, "src": source, "i": import_id},
        )
        conn.execute(
            sa.text(
                "insert into planning.plan_line (version_id, business_unit, work_package, cost_category, resource_or_role,"
                " period, currency, planned_hours, planned_rate, planned_cost, planned_revenue, planned_billing,"
                " planned_cash_collection) values (:v, :bu, :wp, :cc, :rr, :p, :cur, :h, :r, :c, :rev, :bill, :cash)"
            ),
            [{"v": version_id, "bu": r.values["business_unit"], "wp": r.values["work_package"],
              "cc": r.values["cost_category"], "rr": r.values["resource_or_role"], "p": r.values["period"],
              "cur": header["currency"], "h": r.values["planned_hours"], "r": r.values["planned_rate"],
              "c": r.values["planned_cost"], "rev": r.values["planned_revenue"], "bill": r.values["planned_billing"],
              "cash": r.values["planned_cash_collection"]} for r in staged],
        )
        conn.execute(sa.text("update planning.import_batch set version_id = :v where import_id = :i"), {"v": version_id, "i": import_id})

    append_event(
        conn, actor=actor.user_id, action="planning.import_" + status.lower(), object_type="plan_import",
        object_id=str(import_id),
        payload={"file_hash": file_hash, "rows": len(rows), "errors": len(issues), "version_id": str(version_id) if version_id else None,
                 "source": source},
    )
    return ImportResult(str(import_id), status, str(version_id) if version_id else None, issues,
                        {k: str(v) for k, v in totals.items()})


def _json_totals(totals: dict[str, Decimal]) -> str:
    return json.dumps({k: str(v) for k, v in totals.items()})
