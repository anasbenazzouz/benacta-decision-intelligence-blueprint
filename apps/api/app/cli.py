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
    return pipeline.run_pipeline(settings, steps=("ingest", "marts", "plans", "reconcile"))


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
    audit = commands.add_parser("verify-audit", help="verify the audit hash chain")
    audit.add_argument("--export", action="store_true", help="also export the journal as JSONL")
    audit.set_defaults(func=_verify_audit)
    commands.add_parser("seed-odoo-dry-run", help="plan the Odoo sandbox seed; writes nothing").set_defaults(
        func=_seed_odoo_dry_run
    )
    commands.add_parser("seed-odoo", help="seed the Odoo sandbox; refused unless the write guard passes").set_defaults(
        func=_seed_odoo
    )
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
