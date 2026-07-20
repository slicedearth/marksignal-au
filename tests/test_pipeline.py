from __future__ import annotations

import hashlib
import json
from pathlib import Path

import polars as pl
import pytest

from marksignal.fixtures import read_fixture
from marksignal.ip_rapid import IP_RAPID_DATASET_URL
from marksignal.pipeline import DataQualityError, process_snapshot, publish_status, rebuild_site
from marksignal.privacy import audit_trademarks
from marksignal.resolver import ApplicantResolver, load_watchlists


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fixture_pipeline_is_idempotent_and_publishes_all_formats(tmp_path: Path) -> None:
    resolver = ApplicantResolver(load_watchlists(Path("watchlists")))
    snapshot, retrieved_at = read_fixture(
        Path("tests/fixtures/synthetic-trademarks.json"),
        resolver=resolver,
    )
    first = process_snapshot(
        snapshot,
        resolver=resolver,
        root=tmp_path,
        retrieved_at=retrieved_at,
        source_url=IP_RAPID_DATASET_URL,
        is_demo=True,
    )
    state = tmp_path / "data/state/trademarks.json"
    first_digest = _digest(state)
    second = process_snapshot(
        snapshot,
        resolver=resolver,
        root=tmp_path,
        retrieved_at=retrieved_at,
        source_url=IP_RAPID_DATASET_URL,
        is_demo=True,
    )
    assert first.matched_trade_marks == 8
    assert first.emitted_signals >= 4
    assert first.changes_added == 8
    assert second.unchanged_source is True
    assert second.changes_added == 0
    assert _digest(state) == first_digest

    dashboard = json.loads((tmp_path / "site/src/data/dashboard.json").read_text())
    assert dashboard["is_demo"] is True
    assert dashboard["stats"]["trade_marks"] == 8
    assert dashboard["disclaimer"].startswith("A trade mark filing is not confirmation")
    assert (tmp_path / "site/public/data/signals.csv").is_file()
    assert (tmp_path / "site/public/data/signals.parquet").is_file()
    assert (tmp_path / "site/public/feed.xml").is_file()
    assert pl.read_parquet(tmp_path / "data/state/trademarks.parquet").height == 8
    assert pl.read_parquet(tmp_path / "site/public/data/signals.parquet").height >= 4


def test_rebuild_uses_manifest_timestamp(tmp_path: Path) -> None:
    resolver = ApplicantResolver(load_watchlists(Path("watchlists")))
    snapshot, retrieved_at = read_fixture(
        Path("tests/fixtures/synthetic-trademarks.json"),
        resolver=resolver,
    )
    process_snapshot(
        snapshot,
        resolver=resolver,
        root=tmp_path,
        retrieved_at=retrieved_at,
        source_url=IP_RAPID_DATASET_URL,
        is_demo=True,
    )
    dashboard = rebuild_site(tmp_path, resolver=resolver)
    assert dashboard["generated_at"] == "2026-07-20T00:00:00Z"


def test_restricted_data_root_keeps_durable_state_separate(tmp_path: Path) -> None:
    public_root = tmp_path / "public"
    restricted_root = tmp_path / "restricted"
    resolver = ApplicantResolver(load_watchlists(Path("watchlists")))
    snapshot, retrieved_at = read_fixture(
        Path("tests/fixtures/synthetic-trademarks.json"),
        resolver=resolver,
    )
    process_snapshot(
        snapshot,
        resolver=resolver,
        root=public_root,
        data_root=restricted_root,
        retrieved_at=retrieved_at,
        source_url=IP_RAPID_DATASET_URL,
        is_demo=True,
    )
    assert (restricted_root / "data/state/trademarks.json").is_file()
    assert not (public_root / "data/state/trademarks.json").exists()
    assert (public_root / "site/src/data/dashboard.json").is_file()

    status = publish_status(
        public_root,
        data_root=restricted_root,
        data_revision="a" * 40,
    )
    assert status.matched_trade_marks == 8
    public_status = (public_root / "site/src/data/update-status.json").read_text()
    assert "NORTHSTAR" not in public_status
    assert '"data_revision": "aaaaaaaa' in public_status


def test_privacy_markers_stop_publication(tmp_path: Path) -> None:
    resolver = ApplicantResolver(load_watchlists(Path("watchlists")))
    snapshot, retrieved_at = read_fixture(
        Path("tests/fixtures/synthetic-trademarks.json"),
        resolver=resolver,
    )
    unsafe = snapshot.trademarks[0].model_copy(update={"mark_text": "CALL 02 1234 5678"})
    unsafe_snapshot = snapshot.__class__(
        trademarks=[unsafe, *snapshot.trademarks[1:]],
        source_sha256=snapshot.source_sha256,
        schema_fingerprint=snapshot.schema_fingerprint,
        source_rows_read=snapshot.source_rows_read,
        validation_failures=snapshot.validation_failures,
    )
    with pytest.raises(DataQualityError, match="privacy scan"):
        process_snapshot(
            unsafe_snapshot,
            resolver=resolver,
            root=tmp_path,
            retrieved_at=retrieved_at,
            source_url=IP_RAPID_DATASET_URL,
            is_demo=True,
        )
    assert not (tmp_path / "data/state/trademarks.json").exists()


def test_bounded_privacy_quarantine_withholds_one_record(tmp_path: Path) -> None:
    resolver = ApplicantResolver(load_watchlists(Path("watchlists")))
    snapshot, retrieved_at = read_fixture(
        Path("tests/fixtures/synthetic-trademarks.json"),
        resolver=resolver,
    )
    process_snapshot(
        snapshot,
        resolver=resolver,
        root=tmp_path,
        retrieved_at=retrieved_at,
        source_url=IP_RAPID_DATASET_URL,
        is_demo=True,
    )
    unsafe = snapshot.trademarks[0].model_copy(update={"mark_text": "CALL 02 1234 5678"})
    unsafe_snapshot = snapshot.__class__(
        trademarks=[unsafe, *snapshot.trademarks[1:]],
        source_sha256=snapshot.source_sha256,
        schema_fingerprint=snapshot.schema_fingerprint,
        source_rows_read=snapshot.source_rows_read,
        validation_failures=snapshot.validation_failures,
    )
    result = process_snapshot(
        unsafe_snapshot,
        resolver=resolver,
        root=tmp_path,
        retrieved_at=retrieved_at,
        source_url=IP_RAPID_DATASET_URL,
        is_demo=True,
        privacy_mode="quarantine",
    )
    state = json.loads((tmp_path / "data/state/trademarks.json").read_text())
    report = json.loads((tmp_path / "data/manifests/privacy-report.json").read_text())
    dashboard = json.loads((tmp_path / "site/src/data/dashboard.json").read_text())
    public_changes = json.loads((tmp_path / "site/public/data/changes.json").read_text())
    durable_changes = json.loads((tmp_path / "data/events/changes.json").read_text())
    evidence_path = tmp_path / "site/public/evidence" / f"{unsafe.trademark_number}.json"
    assert len(state) == 7
    assert unsafe.trademark_number not in {item["trademark_number"] for item in state}
    assert unsafe.trademark_number not in {
        item["trademark_number"] for item in public_changes
    }
    assert unsafe.trademark_number not in {
        item["trademark_number"] for item in durable_changes
    }
    assert not evidence_path.exists()
    assert result.privacy_quarantined == 1
    assert report["quarantined_count"] == 1
    assert report["records"][0]["trademark_number"] == unsafe.trademark_number
    assert "02 1234 5678" not in json.dumps(report)
    assert dashboard["stats"]["privacy_quarantined"] == 1
    assert dashboard["stats"]["observed_changes"] == 7


def test_privacy_quarantine_spike_stops_publication(tmp_path: Path) -> None:
    resolver = ApplicantResolver(load_watchlists(Path("watchlists")))
    snapshot, retrieved_at = read_fixture(
        Path("tests/fixtures/synthetic-trademarks.json"),
        resolver=resolver,
    )
    unsafe = [
        item.model_copy(update={"mark_text": f"CALL 02 1234 567{index}"})
        if index < 4
        else item
        for index, item in enumerate(snapshot.trademarks)
    ]
    unsafe_snapshot = snapshot.__class__(
        trademarks=unsafe,
        source_sha256=snapshot.source_sha256,
        schema_fingerprint=snapshot.schema_fingerprint,
        source_rows_read=snapshot.source_rows_read,
        validation_failures=snapshot.validation_failures,
    )
    audit = audit_trademarks(unsafe)
    assert audit.threshold_exceeded is True
    assert "02 1234" not in json.dumps(audit.public_summary())
    with pytest.raises(DataQualityError, match="threshold exceeded"):
        process_snapshot(
            unsafe_snapshot,
            resolver=resolver,
            root=tmp_path,
            retrieved_at=retrieved_at,
            source_url=IP_RAPID_DATASET_URL,
            is_demo=True,
            privacy_mode="quarantine",
        )
    assert not (tmp_path / "data/state/trademarks.json").exists()


def test_rebuild_stops_when_retained_change_history_contains_contact_data(
    tmp_path: Path,
) -> None:
    resolver = ApplicantResolver(load_watchlists(Path("watchlists")))
    snapshot, retrieved_at = read_fixture(
        Path("tests/fixtures/synthetic-trademarks.json"),
        resolver=resolver,
    )
    process_snapshot(
        snapshot,
        resolver=resolver,
        root=tmp_path,
        retrieved_at=retrieved_at,
        source_url=IP_RAPID_DATASET_URL,
        is_demo=True,
    )
    changes_path = tmp_path / "data/events/changes.json"
    changes = json.loads(changes_path.read_text())
    changes[0]["new_value"] = "Contact owner@example.com"
    changes_path.write_text(json.dumps(changes), encoding="utf-8")

    with pytest.raises(DataQualityError, match="change_new_value"):
        rebuild_site(tmp_path, resolver=resolver)
