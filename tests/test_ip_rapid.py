from __future__ import annotations

import csv
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from marksignal.ip_rapid import (
    EXPECTED_MEMBERS,
    SourceArchiveError,
    read_ip_rapid,
    validation_failure_summary,
)
from marksignal.resolver import ApplicantResolver, load_watchlists

HEADERS = {
    "application.csv": [
        "ip_right_type",
        "application_number",
        "ip_right_sub_type",
        "status",
        "application_date",
        "earliest_filed_date",
        "priority_date",
    ],
    "party_activity.csv": [
        "ip_right_type",
        "application_number",
        "party_role_category",
        "party_type",
        "party_name",
        "is_current",
    ],
    "application_description.csv": [
        "ip_right_type",
        "application_number",
        "description_type",
        "description_value",
    ],
    "application_classification.csv": [
        "ip_right_type",
        "application_number",
        "is_current",
        "classification_system",
        "classification",
    ],
    "application_events.csv": [
        "ip_right_type",
        "application_number",
        "is_standing",
        "event_type",
        "event_category",
        "event_effective_date",
        "event_declared_date",
    ],
    "application_links.csv": ["ip_right_type", "application_number"],
}


def _csv_bytes(name: str, rows: list[list[str]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(HEADERS[name])
    writer.writerows(rows)
    return output.getvalue().encode()


def build_archive(
    path: Path,
    *,
    include_all: bool = True,
    include_invalid_watched_row: bool = False,
    selected_application_number: str = "1234567",
    duplicate_header_member: str | None = None,
) -> None:
    rows = {
        "party_activity.csv": [
            [
                "trade_mark",
                "1234567",
                "applicant",
                "Organisation",
                "Northstar Labs Pty. Limited",
                "TRUE",
            ],
            ["trade_mark", "7654321", "applicant", "Individual", "Private Person", "TRUE"],
            ["trade_mark", "7654323", "applicant", "Organisation", "---", "TRUE"],
            ["trade_mark", "7654322", "agent", "Organisation", "Unrelated Agent", "INVALID"],
        ],
        "application.csv": [
            [
                "trade_mark",
                "1234567",
                "trade_mark",
                "filed",
                "2026-07-01",
                "2026-07-01",
                "2026-07-01",
            ],
        ],
        "application_description.csv": [
            ["trade_mark", "1234567", "trade_mark_word_mark_phrase", "NORTHSTAR NEBULA PAY"],
            ["trade_mark", "1234567", "trade_mark_word", ""],
        ],
        "application_classification.csv": [
            ["trade_mark", "1234567", "TRUE", "Nice", "9"],
            ["trade_mark", "1234567", "TRUE", "Nice", "42"],
            ["trade_mark", "1234567", "FALSE", "Nice", "35"],
        ],
        "application_events.csv": [
            ["trade_mark", "1234567", "TRUE", "filed", "filing", "2026-07-01", "2026-07-01"],
            [
                "trade_mark",
                "1234567",
                "FALSE",
                "filed_historical",
                "filing_historical",
                "2026-06-30",
                "2026-06-30",
            ],
        ],
        "application_links.csv": [],
    }
    if include_invalid_watched_row:
        rows["party_activity.csv"].append(
            [
                "trade_mark",
                "1234568",
                "applicant",
                "Organisation",
                "Northstar Labs Pty Ltd",
                "INVALID",
            ]
        )
    if selected_application_number != "1234567":
        for table_rows in rows.values():
            for row in table_rows:
                if len(row) > 1 and row[1] == "1234567":
                    row[1] = selected_application_number
    names = EXPECTED_MEMBERS if include_all else EXPECTED_MEMBERS - {"application_links.csv"}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(names):
            content = _csv_bytes(name, rows[name])
            if name == duplicate_header_member:
                text = content.decode()
                first_line, remainder = text.split("\r\n", 1)
                content = f"{first_line},{HEADERS[name][-1]}\r\n{remainder}".encode()
            archive.writestr(name, content)


def test_streaming_adapter_selects_minimal_watched_records(tmp_path: Path) -> None:
    path = tmp_path / "iprapid.zip"
    build_archive(path)
    resolver = ApplicantResolver(load_watchlists(Path("watchlists")))
    snapshot = read_ip_rapid(
        path,
        resolver=resolver,
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
    )
    assert len(snapshot.trademarks) == 1
    trademark = snapshot.trademarks[0]
    assert trademark.trademark_number == "1234567"
    assert trademark.applicant_id == "northstar-labs"
    assert [item.class_number for item in trademark.classes] == [9, 42]
    assert [item.is_standing for item in trademark.events] == [False, True]
    assert trademark.official_record_url.endswith("/1234567")  # type: ignore[union-attr]
    serialised = trademark.model_dump_json()
    assert "Private Person" not in serialised
    assert "address" not in serialised.casefold()
    assert snapshot.validation_failures == []


def test_archive_member_drift_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "iprapid.zip"
    build_archive(path, include_all=False)
    resolver = ApplicantResolver(load_watchlists(Path("watchlists")))
    with pytest.raises(SourceArchiveError, match="member mismatch"):
        read_ip_rapid(
            path,
            resolver=resolver,
            retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        )


def test_duplicate_source_columns_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "iprapid.zip"
    build_archive(path, duplicate_header_member="application.csv")
    resolver = ApplicantResolver(load_watchlists(Path("watchlists")))
    with pytest.raises(SourceArchiveError, match="duplicate columns"):
        read_ip_rapid(
            path,
            resolver=resolver,
            retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        )


def test_archive_validation_precedes_full_file_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "iprapid.zip"
    path.write_bytes(b"invalid")

    def reject_archive(_: Path) -> zipfile.ZipFile:
        raise SourceArchiveError("unsafe archive")

    def unexpected_hash(_: Path) -> str:
        pytest.fail("unsafe archive was hashed before validation")

    monkeypatch.setattr("marksignal.ip_rapid._safe_archive", reject_archive)
    monkeypatch.setattr("marksignal.ip_rapid._file_sha256", unexpected_hash)
    resolver = ApplicantResolver(load_watchlists(Path("watchlists")))
    with pytest.raises(SourceArchiveError, match="unsafe archive"):
        read_ip_rapid(
            path,
            resolver=resolver,
            retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        )


def test_validation_failure_does_not_retain_rejected_source_value(tmp_path: Path) -> None:
    path = tmp_path / "iprapid.zip"
    build_archive(path, include_invalid_watched_row=True)
    resolver = ApplicantResolver(load_watchlists(Path("watchlists")))
    snapshot = read_ip_rapid(
        path,
        resolver=resolver,
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
    )
    assert snapshot.validation_failures == [
        "party_activity.csv row 6: selected_row_invalid"
    ]
    assert "Northstar" not in " ".join(snapshot.validation_failures)
    assert "INVALID" not in " ".join(snapshot.validation_failures)
    assert validation_failure_summary(snapshot.validation_failures) == {
        "retained_validation_failure_count": 1,
        "validation_failure_codes": {"selected_row_invalid": 1},
        "validation_failure_tables": {"party_activity.csv": 1},
    }


def test_joined_record_failure_does_not_log_rejected_source_value(tmp_path: Path) -> None:
    path = tmp_path / "iprapid.zip"
    build_archive(path, selected_application_number="bad/value")
    resolver = ApplicantResolver(load_watchlists(Path("watchlists")))
    snapshot = read_ip_rapid(
        path,
        resolver=resolver,
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
    )
    assert snapshot.trademarks == []
    assert snapshot.validation_failures == [
        "joined_record row 0: selected_record_invalid"
    ]
    assert "bad/value" not in " ".join(snapshot.validation_failures)


def test_source_table_row_limit_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "iprapid.zip"
    build_archive(path)
    monkeypatch.setattr("marksignal.ip_rapid.MAX_ROWS_PER_MEMBER", 1)
    resolver = ApplicantResolver(load_watchlists(Path("watchlists")))
    with pytest.raises(SourceArchiveError, match="row safety limit"):
        read_ip_rapid(
            path,
            resolver=resolver,
            retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        )


def test_selected_application_limit_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "iprapid.zip"
    build_archive(path)
    monkeypatch.setattr("marksignal.ip_rapid.MAX_SELECTED_APPLICATIONS", 0)
    resolver = ApplicantResolver(load_watchlists(Path("watchlists")))
    with pytest.raises(SourceArchiveError, match="application safety limit"):
        read_ip_rapid(
            path,
            resolver=resolver,
            retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        )


@pytest.mark.parametrize(
    "constant_name",
    [
        "MAX_SELECTED_PARTY_ROWS",
        "MAX_SELECTED_DESCRIPTION_ROWS",
        "MAX_SELECTED_EVENT_ROWS",
    ],
)
def test_selected_global_child_row_limits_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    constant_name: str,
) -> None:
    path = tmp_path / "iprapid.zip"
    build_archive(path)
    monkeypatch.setattr(f"marksignal.ip_rapid.{constant_name}", 0)
    resolver = ApplicantResolver(load_watchlists(Path("watchlists")))
    with pytest.raises(SourceArchiveError, match="global safety limit"):
        read_ip_rapid(
            path,
            resolver=resolver,
            retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        )


@pytest.mark.parametrize(
    ("constant_name", "message"),
    [
        ("MAX_DESCRIPTIONS_PER_APPLICATION", "description safety limit"),
        ("MAX_EVENTS_PER_APPLICATION", "event safety limit"),
    ],
)
def test_selected_child_row_limits_fail_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    constant_name: str,
    message: str,
) -> None:
    path = tmp_path / "iprapid.zip"
    build_archive(path)
    monkeypatch.setattr(f"marksignal.ip_rapid.{constant_name}", 1)
    resolver = ApplicantResolver(load_watchlists(Path("watchlists")))
    with pytest.raises(SourceArchiveError, match=message):
        read_ip_rapid(
            path,
            resolver=resolver,
            retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        )
