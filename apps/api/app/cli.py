"""`benacta` command line. Only commands that are implemented are registered."""

from __future__ import annotations

import argparse
import sys

from app.config import REPO_ROOT, get_settings


def _doctor(_: argparse.Namespace) -> int:
    from app.ops import doctor

    return doctor.main(get_settings())


def _discover_odoo(_: argparse.Namespace) -> int:
    from app.ops import discover_odoo

    snapshot, report = discover_odoo.run(get_settings())
    print(f"Wrote {snapshot.relative_to(REPO_ROOT)} and {report.relative_to(REPO_ROOT)}")
    return 0


def _migrate(_: argparse.Namespace) -> int:
    from app.ops import pipeline

    print(f"analytics database at revision {pipeline.run_migrations(get_settings())}")
    return 0


def _pipeline(*steps: str):
    def run(args: argparse.Namespace) -> int:
        from app.ops import pipeline

        return pipeline.run_pipeline(get_settings(), steps=steps)

    return run


def _seed_fixtures(_: argparse.Namespace) -> int:
    from app.config import Mode
    from app.ops import pipeline

    settings = get_settings().model_copy(update={"benacta_mode": Mode.FIXTURE})
    pipeline.run_migrations(settings)
    return pipeline.run_pipeline(settings, steps=("ingest", "marts", "plans", "reconcile", "reference", "exceptions", "documents"))


def _margin_overview(args: argparse.Namespace) -> int:
    from app.ops import margin_ops

    return margin_ops.run_overview(get_settings(), args.period)


def _margin_exceptions(args: argparse.Namespace) -> int:
    from app.ops import margin_ops

    return margin_ops.run_queue(get_settings(), args.period, args.classification, args.limit)


def _margin_case(args: argparse.Namespace) -> int:
    from app.ops import margin_ops

    return margin_ops.run_case(get_settings(), args.case)


def _margin_decide(args: argparse.Namespace) -> int:
    from app.ops import margin_ops

    return margin_ops.run_decide(get_settings(), args.case, args.decision, args.actor, args.role, reason=args.reason, comment=args.comment,
                                 assigned_to=args.assign_to, defer_until=args.defer_until, expected_version=args.expected_version)


def _margin_act(args: argparse.Namespace) -> int:
    from app.ops import margin_ops

    return margin_ops.run_act(get_settings(), args.case, args.actor, args.role, confirm=args.confirm)


def _margin_impact(_: argparse.Namespace) -> int:
    from app.ops import margin_ops

    return margin_ops.run_impact(get_settings())


def _margin_investigate(args: argparse.Namespace) -> int:
    from app.ops import margin_ops

    return margin_ops.run_investigate(get_settings(), args.case, use_llm=args.llm)


def _margin_audit(args: argparse.Namespace) -> int:
    from app.ops import margin_ops

    return margin_ops.run_audit(get_settings(), args.case)


def _reconciliation_report(args: argparse.Namespace) -> int:
    from app.ops import margin_ops

    return margin_ops.run_reconciliation_report(get_settings(), args.period)


def _portfolio(args: argparse.Namespace) -> int:
    from app.ops import controlling_ops

    return controlling_ops.run_portfolio(get_settings(), args.cutoff, args.business_unit)


def _psr(args: argparse.Namespace) -> int:
    from app.ops import controlling_ops

    return controlling_ops.run_psr(get_settings(), args.project, args.cutoff, args.save)


def _investigate(args: argparse.Namespace) -> int:
    from app.ops import controlling_ops

    return controlling_ops.run_investigation(get_settings(), args.project, args.cutoff, args.save)


def _verify_audit(args: argparse.Namespace) -> int:
    from app.ops import pipeline

    return pipeline.run_verify_audit(get_settings(), export=args.export)


def _seed_odoo_dry_run(_: argparse.Namespace) -> int:
    from app.ops import seed_odoo

    return seed_odoo.dry_run(get_settings())


def _seed_odoo(_: argparse.Namespace) -> int:
    from app.ops import seed_odoo

    return seed_odoo.seed(get_settings())


def _odoo_configure(args: argparse.Namespace) -> int:
    from app.ops import odoo_configure

    return odoo_configure.run(get_settings(), confirm=args.confirm)


def _seed_odoo_projects(args: argparse.Namespace) -> int:
    from app.ops import seed_projects

    return seed_projects.run(get_settings(), confirm=args.confirm)


def _local_db_stop(_: argparse.Namespace) -> int:
    from app.db.engine import LOCAL_PGDATA, stop_local_server

    print("embedded database stopped" if stop_local_server() else f"no embedded database running in {LOCAL_PGDATA}")
    return 0


def _serve(args: argparse.Namespace) -> int:
    import uvicorn

    # Local development adapter: loopback only, never a production server.
    uvicorn.run("app.main:app", host="127.0.0.1", port=args.port, reload=False)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="benacta")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="check configuration and live connections").set_defaults(func=_doctor)
    commands.add_parser("discover-odoo", help="read-only discovery of the configured Odoo").set_defaults(
        func=_discover_odoo
    )
    commands.add_parser("migrate", help="upgrade the verified analytics database").set_defaults(func=_migrate)
    commands.add_parser(
        "seed-fixtures", help="fixture mode: migrate, ingest the demo dataset, build marts, reconcile"
    ).set_defaults(func=_seed_fixtures)
    commands.add_parser("ingest", help="ingest from the configured source").set_defaults(func=_pipeline("ingest"))
    commands.add_parser("marts", help="build marts for the latest snapshot").set_defaults(func=_pipeline("marts"))
    commands.add_parser("reconcile", help="reconcile the latest snapshot").set_defaults(func=_pipeline("reconcile"))
    commands.add_parser(
        "load-policies", help="load governed commercial terms (fixture terms, or data/policies/margin_policy_register.yml)"
    ).set_defaults(func=_pipeline("reference"))
    commands.add_parser("exceptions", help="run the margin rules on the latest snapshot").set_defaults(
        func=_pipeline("exceptions")
    )
    overview = commands.add_parser("margin-overview", help="gross margin, leakage and drivers for a period")
    overview.add_argument("--period", help="YYYY-MM; defaults to the latest period with posted revenue")
    overview.set_defaults(func=_margin_overview)
    queue = commands.add_parser("margin-exceptions", help="ranked exception queue")
    queue.add_argument("--period")
    queue.add_argument("--classification", choices=["CONFIRMED_LEAKAGE", "PROBABLE_LEAKAGE", "DATA_QUALITY_ISSUE", "INSUFFICIENT_EVIDENCE"])
    queue.add_argument("--limit", type=int, default=50)
    queue.set_defaults(func=_margin_exceptions)
    case = commands.add_parser("margin-case", help="one exception with its evidence, drill-down and lineage")
    case.add_argument("case", help="case reference, e.g. MC-000001")
    case.set_defaults(func=_margin_case)
    decide = commands.add_parser("margin-decide", help="record a human decision on a case (pilot identity: --actor and --role)")
    decide.add_argument("case")
    decide.add_argument("--decision", required=True, choices=["APPROVE", "REJECT", "REQUEST_EVIDENCE", "ASSIGN", "DEFER", "COMMENT", "REOPEN", "CLOSE"])
    decide.add_argument("--actor", required=True, help="user identifier, e.g. FIN-01")
    decide.add_argument("--role", action="append", default=[], help="analyst, project_controller, finance_approver, admin (repeatable)")
    decide.add_argument("--reason", help="required for REJECT, DEFER, REQUEST_EVIDENCE, REOPEN")
    decide.add_argument("--comment")
    decide.add_argument("--assign-to")
    decide.add_argument("--defer-until", help="YYYY-MM-DD")
    decide.add_argument("--expected-version", type=int, help="the case version the decision was taken on; a stale version is refused")
    decide.set_defaults(func=_margin_decide)
    act = commands.add_parser("margin-act", help="create the approved review activity in Odoo (sandbox, guarded); dry run without --confirm")
    act.add_argument("case")
    act.add_argument("--actor", required=True)
    act.add_argument("--role", action="append", default=[])
    act.add_argument("--confirm", action="store_true")
    act.set_defaults(func=_margin_act)
    commands.add_parser("index-documents", help="register the governed document corpus (data/documents/margin)").set_defaults(
        func=_pipeline("documents")
    )
    investigate_case = commands.add_parser("margin-investigate", help="investigate a case: deterministic by default, --llm uses the configured model")
    investigate_case.add_argument("case")
    investigate_case.add_argument("--llm", action="store_true", help="draft with LLM_PROVIDER/LLM_MODEL/LLM_API_KEY; falls back when refused")
    investigate_case.set_defaults(func=_margin_investigate)
    commands.add_parser("margin-impact", help="estimated against realised recovery per approved case").set_defaults(func=_margin_impact)
    audit_case = commands.add_parser("margin-audit", help="everything that happened to a case, with audit events")
    audit_case.add_argument("case")
    audit_case.set_defaults(func=_margin_audit)
    report = commands.add_parser("reconciliation-report", help="closed-period reconciliation report")
    report.add_argument("--period")
    report.set_defaults(func=_reconciliation_report)
    audit = commands.add_parser("verify-audit", help="verify the audit hash chain")
    audit.add_argument("--export", action="store_true", help="also export the journal as JSONL")
    audit.set_defaults(func=_verify_audit)
    commands.add_parser("seed-odoo-dry-run", help="plan the Odoo sandbox seed; writes nothing").set_defaults(
        func=_seed_odoo_dry_run
    )
    commands.add_parser("seed-odoo", help="seed the Odoo sandbox; refused unless the write guard passes").set_defaults(
        func=_seed_odoo
    )
    configure = commands.add_parser(
        "odoo-configure", help="install authorised modules, currencies and extension fields; dry run without --confirm"
    )
    configure.add_argument("--confirm", action="store_true")
    configure.set_defaults(func=_odoo_configure)
    projects_seed = commands.add_parser(
        "seed-odoo-projects", help="write the synthetic project company into Odoo; dry run without --confirm"
    )
    projects_seed.add_argument("--confirm", action="store_true")
    projects_seed.set_defaults(func=_seed_odoo_projects)
    commands.add_parser("local-db-stop", help="stop the embedded fixture database (data kept)").set_defaults(
        func=_local_db_stop
    )
    portfolio = commands.add_parser("portfolio", help="portfolio overview at a cutoff")
    portfolio.add_argument("--cutoff", help="YYYY-MM-DD; defaults to the fixture anchor in fixture mode")
    portfolio.add_argument("--business-unit")
    portfolio.set_defaults(func=_portfolio)
    psr = commands.add_parser("psr", help="build a project status report draft")
    psr.add_argument("--project", required=True)
    psr.add_argument("--cutoff")
    psr.add_argument("--save", action="store_true", help="store the draft (publication needs a different approver)")
    psr.set_defaults(func=_psr)
    investigate = commands.add_parser("investigate", help="why is the margin at completion of a project decreasing")
    investigate.add_argument("--project", required=True)
    investigate.add_argument("--cutoff")
    investigate.add_argument("--save", action="store_true", help="store the report and its proposals pending review")
    investigate.set_defaults(func=_investigate)
    serve = commands.add_parser("serve", help="run the API on 127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.set_defaults(func=_serve)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
