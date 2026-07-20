"""State management, immutable changes, and static publication."""

from __future__ import annotations

import csv
import hashlib
import html
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

from marksignal import __version__
from marksignal.diff import compare_trademarks
from marksignal.ip_rapid import (
    IP_RAPID_DATASET_URL,
    SOURCE_LICENSE,
    SOURCE_PUBLISHER,
    IngestedSnapshot,
)
from marksignal.models import (
    FilingSignal,
    ObservedChange,
    PipelineResult,
    PublicUpdateStatus,
    SourceManifest,
    Trademark,
)
from marksignal.normalise import stable_hash
from marksignal.privacy import (
    PrivacyAudit,
    PrivacyMode,
    audit_trademarks,
    change_privacy_findings,
    privacy_findings,
)
from marksignal.resolver import ApplicantResolver
from marksignal.signals import ALGORITHM_VERSION, detect_signals

DISCLAIMER = (
    "A trade mark filing is not confirmation that a product or service will launch. "
    "Applications may be defensive, speculative, abandoned, refused, or unrelated to "
    "current commercial plans. Signals are reproducible research leads, not legal or "
    "commercial conclusions."
)
ADAPTATION_NOTICE = (
    "Selected, minimised, normalised, and analysed by MarkSignal AU from IP RAPID data."
)
MAX_VALIDATION_FAILURES = 50
MAX_JSON_BYTES = 100_000_000
MAX_PUBLISHED_TRADEMARKS = 25_000
MAX_PUBLISHED_SIGNALS = 25_000
MAX_PUBLISHED_CHANGES = 250_000


class DataQualityError(RuntimeError):
    """Raised when an input cannot be published safely."""


def _audit_privacy(trademarks: list[Trademark]) -> None:
    for trademark in trademarks:
        findings = privacy_findings(trademark)
        if findings:
            fields = ", ".join(sorted({finding.field_name for finding in findings}))
            raise DataQualityError(
                f"privacy scan found contact, identifier, or address markers in {fields}; "
                "publication stopped"
            )


def _audit_change_privacy(changes: list[ObservedChange]) -> None:
    for change in changes:
        findings = change_privacy_findings(change)
        if findings:
            fields = ", ".join(sorted({finding.field_name for finding in findings}))
            raise DataQualityError(
                f"privacy scan found contact, identifier, or address markers in {fields}; "
                "publication stopped"
            )


def _privacy_report(audit: PrivacyAudit, *, retrieved_at: datetime) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "retrieved_at": retrieved_at.isoformat(),
        **audit.public_summary(),
        "records": [
            {
                "trademark_number": item.trademark_number,
                "source_hash": item.source_hash,
                "fields": item.fields,
                "markers": item.markers,
            }
            for item in audit.quarantined
        ],
    }


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            default=lambda item: item.isoformat(),
        ).encode("utf-8")
        + b"\n"
    )


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> bytes:
    content = _json_bytes(value)
    _atomic_write(path, content)
    return content


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    if path.stat().st_size > MAX_JSON_BYTES:
        raise DataQualityError(f"JSON input exceeds the {MAX_JSON_BYTES:,} byte safety limit")
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_durable_state(root: Path, manifest: SourceManifest) -> None:
    expected_hashes = {
        root / "data/state/trademarks.json": manifest.state_sha256,
        root / "data/events/signals.json": manifest.signals_sha256,
        root / "data/events/changes.json": manifest.changes_sha256,
    }
    for path, expected_hash in expected_hashes.items():
        if not path.is_file():
            raise DataQualityError(f"durable state file is missing: {path.name}")
        if path.stat().st_size > MAX_JSON_BYTES:
            raise DataQualityError(f"durable state file exceeds the safety limit: {path.name}")
        actual_hash = _file_sha256(path)
        if actual_hash != expected_hash:
            raise DataQualityError(f"durable state hash mismatch: {path.name}")


def _load_trademarks(path: Path) -> list[Trademark]:
    return [Trademark.model_validate(item) for item in _load_json(path, [])]


def _load_changes(path: Path) -> list[ObservedChange]:
    return [ObservedChange.model_validate(item) for item in _load_json(path, [])]


def _material_fingerprint(trademarks: list[Trademark]) -> str:
    return stable_hash(
        [
            {"trademark_number": item.trademark_number, "source_hash": item.source_hash}
            for item in sorted(trademarks, key=lambda record: record.trademark_number)
        ]
    )


def _merge_snapshot(
    previous: list[Trademark],
    incoming: list[Trademark],
) -> tuple[list[Trademark], list[ObservedChange]]:
    previous_by_number = {item.trademark_number: item for item in previous}
    merged = dict(previous_by_number)
    changes: list[ObservedChange] = []
    for item in incoming:
        before = previous_by_number.get(item.trademark_number)
        if before is not None:
            item = item.model_copy(
                update={
                    "first_seen_at": before.first_seen_at,
                    "last_seen_at": (
                        before.last_seen_at
                        if before.source_hash == item.source_hash
                        else item.last_seen_at
                    ),
                }
            )
        changes.extend(compare_trademarks(before, item))
        merged[item.trademark_number] = item
    return sorted(merged.values(), key=lambda item: item.trademark_number), changes


def _csv_safe(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r", "\n")):
        return f"'{value}"
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_safe(row.get(key)) for key in fieldnames})
    temporary.replace(path)


def _write_parquet(path: Path, rows: list[dict[str, Any]], schema: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame = pl.DataFrame(rows, schema=schema) if rows else pl.DataFrame(schema=schema)
    frame.write_parquet(temporary, compression="zstd")
    temporary.replace(path)


def _signal_for_site(signal: FilingSignal, trademark: Trademark) -> dict[str, Any]:
    payload = signal.model_dump(mode="json")
    payload.update(
        {
            "mark_text": trademark.mark_text or "No word element published",
            "applicant_name": trademark.applicant_name,
            "filing_date": trademark.filing_date.isoformat() if trademark.filing_date else None,
            "status": trademark.current_status,
            "classes": [item.class_number for item in trademark.classes],
            "official_record_url": trademark.official_record_url,
            "evidence_path": f"evidence/{trademark.trademark_number}.json",
        }
    )
    return payload


def _validate_publication_bounds(
    trademarks: list[Trademark],
    signals: list[FilingSignal],
    changes: list[ObservedChange],
) -> None:
    limits = {
        "trade marks": (len(trademarks), MAX_PUBLISHED_TRADEMARKS),
        "signals": (len(signals), MAX_PUBLISHED_SIGNALS),
        "changes": (len(changes), MAX_PUBLISHED_CHANGES),
    }
    for label, (count, limit) in limits.items():
        if count > limit:
            raise DataQualityError(
                f"publication contains too many {label}: {count:,} exceeds {limit:,}"
            )


def _change_summary(change: ObservedChange) -> str:
    labels = {
        "first_observed": "First observed in the selected public dataset.",
        "status_changed": f"Status changed from {change.old_value} to {change.new_value}.",
        "classes_changed": (
            f"Current Nice classes changed from {change.old_value} to {change.new_value}."
        ),
        "mark_text_changed": "Published mark wording changed.",
        "applicant_changed": "The matched watched applicant name changed.",
    }
    return labels[change.change_type]


def _rss_item(item: dict[str, Any]) -> str:
    published = datetime.fromisoformat(item["detected_at"].replace("Z", "+00:00"))
    descriptions = "; ".join(reason["explanation"] for reason in item["reasons"])
    return (
        "<item>"
        f"<title>{html.escape(item['mark_text'])} | {html.escape(item['applicant_name'])}</title>"
        f"<link>https://slicedearth.github.io/marksignal-au/trademarks/"
        f"{item['trademark_number']}/</link>"
        f'<guid isPermaLink="false">{item["signal_id"]}</guid>'
        f"<pubDate>{published.strftime('%a, %d %b %Y %H:%M:%S GMT')}</pubDate>"
        f"<description>{html.escape(descriptions)}</description>"
        "</item>"
    )


def build_site_data(
    trademarks: list[Trademark],
    signals: list[FilingSignal],
    changes: list[ObservedChange],
    *,
    resolver: ApplicantResolver,
    root: Path,
    generated_at: datetime,
    is_demo: bool,
    privacy_quarantined: int = 0,
) -> dict[str, Any]:
    """Generate compact site data, evidence files, feeds, and tabular downloads."""

    _validate_publication_bounds(trademarks, signals, changes)
    _audit_privacy(trademarks)

    trademark_lookup = {item.trademark_number: item for item in trademarks}
    public_signals = [
        signal for signal in signals if signal.trademark_number in trademark_lookup
    ]
    public_changes = [
        change for change in changes if change.trademark_number in trademark_lookup
    ]
    _audit_change_privacy(public_changes)
    site_signals = [
        _signal_for_site(signal, trademark_lookup[signal.trademark_number])
        for signal in public_signals
    ]
    changes_by_number: dict[str, list[ObservedChange]] = defaultdict(list)
    for change in public_changes:
        changes_by_number[change.trademark_number].append(change)

    applicant_summaries: list[dict[str, Any]] = []
    for applicant_id, applicant in resolver.applicants.items():
        applicant_marks = [item for item in trademarks if item.applicant_id == applicant_id]
        applicant_signals = [
            item for item in public_signals if item.applicant_id == applicant_id
        ]
        if not applicant_marks:
            continue
        class_counts = Counter(
            item.class_number for mark in applicant_marks for item in mark.classes
        )
        applicant_summaries.append(
            {
                "applicant_id": applicant_id,
                "display_name": applicant.display_name,
                "categories": applicant.categories,
                "filings": len(applicant_marks),
                "signals": len(applicant_signals),
                "classes": [
                    {"class_number": class_number, "filings": count}
                    for class_number, count in sorted(class_counts.items())
                ],
                "latest_filing_date": max(
                    (item.filing_date for item in applicant_marks if item.filing_date),
                    default=None,
                ),
                "trademark_numbers": [
                    item.trademark_number
                    for item in sorted(
                        applicant_marks,
                        key=lambda record: (
                            record.filing_date is not None,
                            record.filing_date,
                            record.trademark_number,
                        ),
                        reverse=True,
                    )
                ],
            }
        )
    applicant_summaries.sort(key=lambda item: (-item["signals"], item["display_name"]))

    class_counts = Counter(item.class_number for mark in trademarks for item in mark.classes)
    reason_counts = Counter(
        reason.type for signal in public_signals for reason in signal.reasons
    )
    dashboard = {
        "project": "MarkSignal AU",
        "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
        "is_demo": is_demo,
        "source": {
            "name": "IP RAPID",
            "publisher": SOURCE_PUBLISHER,
            "url": IP_RAPID_DATASET_URL,
            "license": SOURCE_LICENSE,
            "adaptation_notice": ADAPTATION_NOTICE,
        },
        "disclaimer": DISCLAIMER,
        "stats": {
            "watched_organisations": resolver.organisation_count,
            "matched_organisations": len(applicant_summaries),
            "trade_marks": len(trademarks),
            "signals": len(public_signals),
            "observed_changes": len(public_changes),
            "classes": len(class_counts),
            "privacy_quarantined": privacy_quarantined,
        },
        "reason_counts": dict(sorted(reason_counts.items())),
        "class_counts": [
            {"class_number": class_number, "filings": count}
            for class_number, count in sorted(
                class_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ],
        "signals": site_signals,
        "applicants": applicant_summaries,
        "trademarks": [item.model_dump(mode="json") for item in trademarks],
        "changes": [
            {**item.model_dump(mode="json"), "summary": _change_summary(item)}
            for item in sorted(
                public_changes,
                key=lambda change: (change.detected_at, change.change_id),
                reverse=True,
            )
        ],
    }
    _write_json(root / "site/src/data/dashboard.json", dashboard)
    _write_json(root / "site/public/data/signals.json", site_signals)
    _write_json(
        root / "site/public/data/trademarks.json",
        [item.model_dump(mode="json") for item in trademarks],
    )
    _write_json(
        root / "site/public/data/changes.json",
        [item.model_dump(mode="json") for item in public_changes],
    )

    evidence_root = root / "site/public/evidence"
    evidence_root.mkdir(parents=True, exist_ok=True)
    for stale_evidence in evidence_root.glob("*.json"):
        stale_evidence.unlink()
    for trademark in trademarks:
        evidence_signals = [
            item.model_dump(mode="json")
            for item in public_signals
            if item.trademark_number == trademark.trademark_number
        ]
        _write_json(
            evidence_root / f"{trademark.trademark_number}.json",
            {
                "trademark": trademark.model_dump(mode="json"),
                "signals": evidence_signals,
                "changes": [
                    item.model_dump(mode="json")
                    for item in changes_by_number[trademark.trademark_number]
                ],
                "source": dashboard["source"],
                "disclaimer": DISCLAIMER,
            },
        )

    signal_rows = [
        {
            "signal_id": item.signal_id,
            "trademark_number": item.trademark_number,
            "applicant_id": item.applicant_id,
            "detected_at": item.detected_at.isoformat(),
            "score": item.score,
            "algorithm_version": item.algorithm_version,
            "reason_types": ",".join(reason.type for reason in item.reasons),
            "reasons_json": json.dumps(
                [reason.model_dump(mode="json") for reason in item.reasons],
                separators=(",", ":"),
            ),
        }
        for item in public_signals
    ]
    signal_fields = [
        "signal_id",
        "trademark_number",
        "applicant_id",
        "detected_at",
        "score",
        "algorithm_version",
        "reason_types",
        "reasons_json",
    ]
    _write_csv(root / "site/public/data/signals.csv", signal_rows, signal_fields)
    _write_parquet(
        root / "site/public/data/signals.parquet",
        signal_rows,
        {
            "signal_id": pl.String,
            "trademark_number": pl.String,
            "applicant_id": pl.String,
            "detected_at": pl.String,
            "score": pl.Int64,
            "algorithm_version": pl.String,
            "reason_types": pl.String,
            "reasons_json": pl.String,
        },
    )

    feed_items = "".join(_rss_item(item) for item in site_signals[:50])
    rss = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>'
        "<title>MarkSignal AU filing signals</title>"
        "<link>https://slicedearth.github.io/marksignal-au/</link>"
        "<description>Evidence-linked signals from selected Australian trade mark "
        "filings.</description>"
        f"{feed_items}</channel></rss>\n"
    )
    _atomic_write(root / "site/public/feed.xml", rss.encode("utf-8"))
    return dashboard


def process_snapshot(
    snapshot: IngestedSnapshot,
    *,
    resolver: ApplicantResolver,
    root: Path,
    data_root: Path | None = None,
    retrieved_at: datetime,
    source_url: str,
    is_demo: bool,
    privacy_mode: PrivacyMode = "strict",
) -> PipelineResult:
    """Accept a source snapshot, append changes, and publish static outputs."""

    privacy_audit = audit_trademarks(snapshot.trademarks)
    if privacy_audit.quarantined_count and privacy_mode == "strict":
        raise DataQualityError(
            f"privacy scan quarantined {privacy_audit.quarantined_count} selected record(s); "
            "strict publication stopped"
        )
    if privacy_mode == "quarantine" and privacy_audit.threshold_exceeded:
        raise DataQualityError(
            f"privacy quarantine threshold exceeded: {privacy_audit.quarantined_count} of "
            f"{privacy_audit.selected_count} selected records"
        )
    incoming = list(privacy_audit.accepted)
    if len(snapshot.validation_failures) > MAX_VALIDATION_FAILURES:
        raise DataQualityError(
            f"source has {len(snapshot.validation_failures)} validation failures; maximum is "
            f"{MAX_VALIDATION_FAILURES}"
        )
    durable_root = data_root or root
    state_path = durable_root / "data/state/trademarks.json"
    changes_path = durable_root / "data/events/changes.json"
    manifest_path = durable_root / "data/manifests/source-manifest.json"
    previous_manifest = _load_json(manifest_path, {})
    previous_manifest_model: SourceManifest | None = None
    if previous_manifest:
        previous_manifest_model = SourceManifest.model_validate(previous_manifest)
        _verify_durable_state(durable_root, previous_manifest_model)
    previous = _load_trademarks(state_path)
    quarantined_numbers = {item.trademark_number for item in privacy_audit.quarantined}
    previous = [
        trademark
        for trademark in previous
        if trademark.trademark_number not in quarantined_numbers
    ]
    _audit_privacy(previous)
    existing_changes = _load_changes(changes_path)
    previous_numbers = {item.trademark_number for item in previous}
    filtered_existing_changes = [
        change
        for change in existing_changes
        if change.trademark_number in previous_numbers
    ]
    history_was_filtered = len(filtered_existing_changes) != len(existing_changes)
    incoming_fingerprint = _material_fingerprint(incoming)
    previous_fingerprint = _material_fingerprint(previous)
    if (
        incoming_fingerprint == previous_fingerprint
        and not history_was_filtered
        and previous_manifest.get("signal_algorithm_version") == ALGORITHM_VERSION
        and previous_manifest.get("privacy_quarantined", 0)
        == privacy_audit.quarantined_count
    ):
        existing_signals = [
            FilingSignal.model_validate(item)
            for item in _load_json(durable_root / "data/events/signals.json", [])
        ]
        if previous_manifest_model is None:
            raise DataQualityError("durable state manifest is missing")
        existing_manifest = previous_manifest_model
        build_site_data(
            previous,
            existing_signals,
            existing_changes,
            resolver=resolver,
            root=root,
            generated_at=existing_manifest.retrieved_at,
            is_demo=existing_manifest.is_demo,
            privacy_quarantined=existing_manifest.privacy_quarantined,
        )
        return PipelineResult(
            matched_trade_marks=len(previous),
            emitted_signals=len(existing_signals),
            changes_added=0,
            changes_total=len(existing_changes),
            manifest_path=str(manifest_path),
            privacy_quarantined=privacy_audit.quarantined_count,
            unchanged_source=True,
        )

    trademarks, added_changes = _merge_snapshot(previous, incoming)
    accepted_numbers = {item.trademark_number for item in trademarks}
    existing_changes = [
        change
        for change in filtered_existing_changes
        if change.trademark_number in accepted_numbers
    ]
    seen_change_ids = {item.change_id for item in existing_changes}
    new_changes = [item for item in added_changes if item.change_id not in seen_change_ids]
    changes = sorted(
        [
            *existing_changes,
            *(item for item in new_changes if item.trademark_number in accepted_numbers),
        ],
        key=lambda item: (item.detected_at, item.change_id),
    )
    _audit_change_privacy(changes)
    signals = detect_signals(trademarks)
    _validate_publication_bounds(trademarks, signals, changes)

    state_payload = [item.model_dump(mode="json") for item in trademarks]
    signal_payload = [item.model_dump(mode="json") for item in signals]
    change_payload = [item.model_dump(mode="json") for item in changes]
    state_content = _json_bytes(state_payload)
    signals_content = _json_bytes(signal_payload)
    changes_content = _json_bytes(change_payload)

    manifest = SourceManifest(
        parser_version=__version__,
        signal_algorithm_version=ALGORITHM_VERSION,
        retrieved_at=retrieved_at,
        source_url=source_url,
        source_publisher=SOURCE_PUBLISHER,
        source_license=SOURCE_LICENSE,
        source_sha256=snapshot.source_sha256,
        schema_fingerprint=snapshot.schema_fingerprint,
        is_demo=is_demo,
        watchlist_organisations=resolver.organisation_count,
        source_rows_read=snapshot.source_rows_read,
        matched_trade_marks=len(trademarks),
        emitted_signals=len(signals),
        changes_added=len(new_changes),
        privacy_quarantined=privacy_audit.quarantined_count,
        privacy_marker_counts=privacy_audit.marker_counts,
        validation_failures=snapshot.validation_failures,
        state_sha256=_sha256(state_content),
        signals_sha256=_sha256(signals_content),
        changes_sha256=_sha256(changes_content),
    )

    _atomic_write(state_path, state_content)
    _atomic_write(durable_root / "data/events/signals.json", signals_content)
    _atomic_write(changes_path, changes_content)
    _write_json(manifest_path, manifest.model_dump(mode="json"))
    _write_json(
        durable_root / "data/manifests/privacy-report.json",
        _privacy_report(privacy_audit, retrieved_at=retrieved_at),
    )
    _write_parquet(
        durable_root / "data/state/trademarks.parquet",
        [
            {
                "trademark_number": item.trademark_number,
                "applicant_id": item.applicant_id,
                "applicant_name": item.applicant_name,
                "mark_text": item.mark_text,
                "filing_date": item.filing_date.isoformat() if item.filing_date else None,
                "priority_date": item.priority_date.isoformat() if item.priority_date else None,
                "current_status": item.current_status,
                "classes": ",".join(str(value.class_number) for value in item.classes),
                "source_hash": item.source_hash,
            }
            for item in trademarks
        ],
        {
            "trademark_number": pl.String,
            "applicant_id": pl.String,
            "applicant_name": pl.String,
            "mark_text": pl.String,
            "filing_date": pl.String,
            "priority_date": pl.String,
            "current_status": pl.String,
            "classes": pl.String,
            "source_hash": pl.String,
        },
    )
    build_site_data(
        trademarks,
        signals,
        changes,
        resolver=resolver,
        root=root,
        generated_at=retrieved_at,
        is_demo=is_demo,
        privacy_quarantined=privacy_audit.quarantined_count,
    )
    return PipelineResult(
        matched_trade_marks=len(trademarks),
        emitted_signals=len(signals),
        changes_added=len(new_changes),
        changes_total=len(changes),
        manifest_path=str(manifest_path),
        privacy_quarantined=privacy_audit.quarantined_count,
    )


def rebuild_site(
    root: Path,
    *,
    resolver: ApplicantResolver,
    data_root: Path | None = None,
) -> dict[str, Any]:
    """Rebuild site assets from validated local state."""

    durable_root = data_root or root
    manifest = SourceManifest.model_validate(
        _load_json(durable_root / "data/manifests/source-manifest.json", {})
    )
    _verify_durable_state(durable_root, manifest)
    trademarks = _load_trademarks(durable_root / "data/state/trademarks.json")
    signals = [
        FilingSignal.model_validate(item)
        for item in _load_json(durable_root / "data/events/signals.json", [])
    ]
    changes = _load_changes(durable_root / "data/events/changes.json")
    return build_site_data(
        trademarks,
        signals,
        changes,
        resolver=resolver,
        root=root,
        generated_at=manifest.retrieved_at,
        is_demo=manifest.is_demo,
        privacy_quarantined=manifest.privacy_quarantined,
    )


def publish_status(root: Path, *, data_root: Path, data_revision: str) -> PublicUpdateStatus:
    """Publish counts and provenance timing without source-record content."""

    manifest = SourceManifest.model_validate(
        _load_json(data_root / "data/manifests/source-manifest.json", {})
    )
    _verify_durable_state(data_root, manifest)
    status = PublicUpdateStatus(
        data_revision=data_revision,
        retrieved_at=manifest.retrieved_at,
        source_publisher=manifest.source_publisher,
        source_rows_read=sum(manifest.source_rows_read.values()),
        watchlist_organisations=manifest.watchlist_organisations,
        matched_trade_marks=manifest.matched_trade_marks,
        emitted_signals=manifest.emitted_signals,
        privacy_quarantined=manifest.privacy_quarantined,
        validation_failure_count=len(manifest.validation_failures),
    )
    _write_json(root / "site/src/data/update-status.json", status.model_dump(mode="json"))
    return status
