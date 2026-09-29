"""Command line entry point.

    iris-ingest list
    iris-ingest run fixture-nrw-csv --out out/
    iris-ingest run fixture-nrw-csv --database-url postgresql://...
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from iris_ingest.adapters import load_all
from iris_ingest.core import (
    ConfigurationError,
    JsonlSink,
    PostgisSink,
    get_adapter,
    registered_adapters,
    run,
)


def _parse_ts(value: str) -> datetime:
    ts = datetime.fromisoformat(value)
    if ts.tzinfo is None:
        raise argparse.ArgumentTypeError("--fetched-at needs a timezone, e.g. ...Z")
    return ts


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="iris-ingest")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="show registered source adapters")

    r = sub.add_parser("run", help="run one adapter into staging")
    r.add_argument("source_id")
    r.add_argument("--input", help="override the adapter's default input path")
    r.add_argument("--out", default="out", help="output dir for JSONL (default: out)")
    r.add_argument("--database-url", help="stage into PostGIS instead of JSONL")
    r.add_argument(
        "--fetched-at",
        type=_parse_ts,
        help="fix fetched_at for reproducible output (ISO 8601 with tz)",
    )
    r.add_argument(
        "--fail-on-reject",
        action="store_true",
        help="exit with status 2 if any record was rejected",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_all()

    if args.command == "list":
        for source_id, cls in sorted(registered_adapters().items()):
            print(f"{source_id}\t{cls.__module__}.{cls.__name__}")
        return 0

    try:
        adapter_cls = get_adapter(args.source_id)
        adapter = adapter_cls(args.input) if args.input else adapter_cls()
        sink = PostgisSink(args.database_url) if args.database_url else JsonlSink(args.out)
        report = run(adapter, sink, fetched_at=args.fetched_at)
    except ConfigurationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(report.summary())
    for key, reasons in report.reject_reasons.items():
        print(f"  rejected {key}: {'; '.join(reasons)}")
    if not args.database_url:
        print(f"output: {args.out}/accepted.jsonl, {args.out}/rejected.jsonl")

    return 2 if args.fail_on_reject and report.rejected else 0


if __name__ == "__main__":
    raise SystemExit(main())
