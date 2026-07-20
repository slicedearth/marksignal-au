"""Command-line interface for fixture builds and IP RAPID updates."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marksignal.fixtures import read_fixture
from marksignal.ip_rapid import (
    IP_RAPID_DATASET_URL,
    IP_RAPID_DOWNLOAD_URL,
    read_ip_rapid,
    validation_failure_summary,
)
from marksignal.pipeline import process_snapshot, publish_status, rebuild_site
from marksignal.privacy import audit_trademarks
from marksignal.resolver import ApplicantResolver, load_watchlists
from marksignal.source_links import SourceLinkError, check_dashboard_source_links


def _path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="marksignal",
        description="Surface reproducible signals from watched Australian trade mark filings.",
    )
    parser.add_argument("--root", type=_path, default=Path.cwd(), help="repository root")
    parser.add_argument(
        "--watchlists",
        type=_path,
        help="watchlist directory; defaults to <root>/watchlists",
    )
    parser.add_argument(
        "--data-root",
        type=_path,
        help="durable state root; defaults to the repository root",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    fixture = subparsers.add_parser("ingest-fixture", help="build from a synthetic JSON fixture")
    fixture.add_argument("path", type=_path)

    rapid = subparsers.add_parser("ingest-iprapid", help="stream a downloaded IP RAPID ZIP")
    rapid.add_argument("path", type=_path)
    rapid.add_argument("--retrieved-at", type=_timestamp)
    rapid.add_argument(
        "--privacy-mode",
        choices=("strict", "quarantine"),
        default="strict",
    )

    audit = subparsers.add_parser(
        "audit-iprapid",
        help="report aggregate privacy matches without writing state",
    )
    audit.add_argument("path", type=_path)
    audit.add_argument("--retrieved-at", type=_timestamp)

    subparsers.add_parser("validate-watchlists", help="validate all YAML watchlists")
    subparsers.add_parser("rebuild-site", help="rebuild site assets from local state")
    subparsers.add_parser(
        "check-source-links",
        help="validate official-record URLs and check a three-record availability sample",
    )
    status = subparsers.add_parser(
        "publish-status",
        help="write a non-identifying public status record from durable state",
    )
    status.add_argument("--data-revision", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root: Path = args.root.resolve()
    data_root: Path = args.data_root or root
    watchlist_path = args.watchlists or root / "watchlists"
    watchlists = load_watchlists(watchlist_path)
    resolver = ApplicantResolver(watchlists)

    if args.command == "validate-watchlists":
        print(json.dumps({"organisations": resolver.organisation_count}, sort_keys=True))
        return 0
    if args.command == "rebuild-site":
        dashboard = rebuild_site(root, resolver=resolver, data_root=data_root)
        print(json.dumps(dashboard["stats"], sort_keys=True))
        return 0
    if args.command == "check-source-links":
        report = check_dashboard_source_links(root / "site/src/data/dashboard.json")
        if report.broken:
            raise SourceLinkError(
                f"official-record sample contains {report.broken} confirmed missing link(s)"
            )
        print(json.dumps(report.public_summary(), sort_keys=True))
        return 0
    if args.command == "publish-status":
        status = publish_status(
            root,
            data_root=data_root,
            data_revision=args.data_revision,
        )
        print(status.model_dump_json())
        return 0
    if args.command == "audit-iprapid":
        retrieved_at = args.retrieved_at or datetime.now(UTC)
        snapshot = read_ip_rapid(
            args.path,
            resolver=resolver,
            retrieved_at=retrieved_at,
        )
        audit_result = audit_trademarks(snapshot.trademarks)
        print(
            json.dumps(
                {
                    **audit_result.public_summary(),
                    **validation_failure_summary(snapshot.validation_failures),
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "ingest-fixture":
        snapshot, retrieved_at = read_fixture(args.path, resolver=resolver)
        result = process_snapshot(
            snapshot,
            resolver=resolver,
            root=root,
            data_root=data_root,
            retrieved_at=retrieved_at,
            source_url=IP_RAPID_DATASET_URL,
            is_demo=True,
        )
    else:
        retrieved_at = args.retrieved_at or datetime.now(UTC)
        snapshot = read_ip_rapid(
            args.path,
            resolver=resolver,
            retrieved_at=retrieved_at,
        )
        result = process_snapshot(
            snapshot,
            resolver=resolver,
            root=root,
            data_root=data_root,
            retrieved_at=retrieved_at,
            source_url=IP_RAPID_DOWNLOAD_URL,
            is_demo=False,
            privacy_mode=args.privacy_mode,
        )
    print(result.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
