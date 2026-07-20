"""Bounded streaming adapter for the public IP RAPID archive."""

from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from marksignal.models import Applicant, Trademark, TrademarkClass, TrademarkEvent
from marksignal.normalise import stable_hash
from marksignal.resolver import ApplicantResolver
from marksignal.source_models import (
    SourceApplication,
    SourceClassification,
    SourceDescription,
    SourceEvent,
    SourcePartyActivity,
)

IP_RAPID_DATASET_URL = "https://data.gov.au/data/dataset/iprapid"
IP_RAPID_DOWNLOAD_URL = (
    "https://data.gov.au/data/dataset/423000b8-5735-4447-bcb9-792644bcd7ea/"
    "resource/c79b3af6-3720-44ac-9e39-6a68f5635924/download/iprapid.zip"
)
SOURCE_LICENSE: Literal["https://creativecommons.org/licenses/by/4.0/"] = (
    "https://creativecommons.org/licenses/by/4.0/"
)
SOURCE_PUBLISHER: Literal["IP Australia"] = "IP Australia"
EXPECTED_MEMBERS = {
    "application.csv",
    "application_classification.csv",
    "application_description.csv",
    "application_events.csv",
    "application_links.csv",
    "party_activity.csv",
}
REQUIRED_COLUMNS = {
    "application.csv": {
        "ip_right_type",
        "application_number",
        "ip_right_sub_type",
        "status",
        "application_date",
        "earliest_filed_date",
        "priority_date",
    },
    "party_activity.csv": {
        "ip_right_type",
        "application_number",
        "party_role_category",
        "party_type",
        "party_name",
        "is_current",
    },
    "application_description.csv": {
        "ip_right_type",
        "application_number",
        "description_type",
        "description_value",
    },
    "application_classification.csv": {
        "ip_right_type",
        "application_number",
        "is_current",
        "classification_system",
        "classification",
    },
    "application_events.csv": {
        "ip_right_type",
        "application_number",
        "is_standing",
        "event_type",
        "event_category",
        "event_effective_date",
        "event_declared_date",
    },
    "application_links.csv": {
        "ip_right_type",
        "application_number",
    },
}
MAX_ARCHIVE_BYTES = 2_500_000_000
MAX_UNCOMPRESSED_BYTES = 20_000_000_000
MAX_CELL_CHARACTERS = 20_000
MAX_VALIDATION_FAILURES = 200
MAX_ROWS_PER_MEMBER = 100_000_000
MAX_SELECTED_APPLICATIONS = 250_000
MAX_SELECTED_PARTY_ROWS = 100_000
MAX_SELECTED_DESCRIPTION_ROWS = 100_000
MAX_SELECTED_EVENT_ROWS = 250_000
MAX_DESCRIPTIONS_PER_APPLICATION = 500
MAX_EVENTS_PER_APPLICATION = 2_000
_CLASS_RE = re.compile(r"^0*([1-9]|[1-3][0-9]|4[0-5])$")


class SourceArchiveError(RuntimeError):
    """Raised when an archive is unsafe, incomplete, or structurally incompatible."""


@dataclass(frozen=True)
class IngestedSnapshot:
    trademarks: list[Trademark]
    source_sha256: str
    schema_fingerprint: str
    source_rows_read: dict[str, int]
    validation_failures: list[str]


@dataclass(frozen=True)
class _ResolvedParty:
    applicant: Applicant
    observed_name: str


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_archive(path: Path) -> zipfile.ZipFile:
    if not path.is_file():
        raise SourceArchiveError(f"source archive does not exist: {path}")
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise SourceArchiveError("source archive exceeds the 2.5 GB compressed limit")
    archive = zipfile.ZipFile(path)
    members = archive.infolist()
    names = [member.filename for member in members]
    if len(names) != len(set(names)):
        archive.close()
        raise SourceArchiveError("source archive contains duplicate member names")
    if set(names) != EXPECTED_MEMBERS:
        archive.close()
        missing = sorted(EXPECTED_MEMBERS - set(names))
        unexpected = sorted(set(names) - EXPECTED_MEMBERS)
        raise SourceArchiveError(
            f"source archive member mismatch; missing={missing}, unexpected={unexpected}"
        )
    total_size = sum(member.file_size for member in members)
    if total_size > MAX_UNCOMPRESSED_BYTES:
        archive.close()
        raise SourceArchiveError("source archive exceeds the 20 GB expanded limit")
    if any("/" in name or "\\" in name or name.startswith(".") for name in names):
        archive.close()
        raise SourceArchiveError("source archive contains an unsafe member path")
    return archive


def _reader(
    archive: zipfile.ZipFile,
    member: str,
) -> tuple[csv.DictReader[str], io.TextIOWrapper]:
    stream = io.TextIOWrapper(archive.open(member), encoding="utf-8-sig", newline="")
    reader = csv.DictReader(stream)
    fieldnames = reader.fieldnames or []
    if any(not fieldname.strip() for fieldname in fieldnames) or len(fieldnames) != len(
        set(fieldnames)
    ):
        stream.close()
        raise SourceArchiveError(f"{member} contains blank or duplicate columns")
    missing = REQUIRED_COLUMNS[member] - set(fieldnames)
    if missing:
        stream.close()
        raise SourceArchiveError(f"{member} is missing columns: {sorted(missing)}")
    return reader, stream


def _bounded_rows(
    reader: csv.DictReader[str],
    *,
    member: str,
) -> Iterator[dict[str, str]]:
    for row_number, row in enumerate(reader, start=1):
        if row_number > MAX_ROWS_PER_MEMBER:
            raise SourceArchiveError(
                f"{member} exceeds the {MAX_ROWS_PER_MEMBER:,} row safety limit"
            )
        if any(len(str(value or "")) > MAX_CELL_CHARACTERS for value in row.values()):
            raise SourceArchiveError("source row contains a cell over 20,000 characters")
        yield row


def _failure(failures: list[str], member: str, row_number: int, code: str) -> None:
    if len(failures) < MAX_VALIDATION_FAILURES:
        failures.append(f"{member} row {row_number}: {code}")


def _schema_fingerprint(archive: zipfile.ZipFile) -> str:
    schemas: dict[str, list[str]] = {}
    for member in sorted(EXPECTED_MEMBERS):
        reader, stream = _reader(archive, member)
        try:
            schemas[member] = list(reader.fieldnames or [])
        finally:
            stream.close()
    return stable_hash(schemas)


def _parse_class(value: str) -> int | None:
    match = _CLASS_RE.fullmatch(value.strip())
    return int(match.group(1)) if match else None


def _source_event(row: SourceEvent) -> TrademarkEvent:
    payload = {
        "event_type": row.event_type,
        "event_category": row.event_category,
        "effective_date": row.event_effective_date,
        "declared_date": row.event_declared_date,
        "is_standing": row.is_standing,
    }
    return TrademarkEvent(
        event_id=stable_hash(payload),
        event_type=row.event_type,
        event_category=row.event_category,
        effective_date=row.event_effective_date,
        declared_date=row.event_declared_date,
        is_standing=row.is_standing,
    )


def read_ip_rapid(
    path: Path,
    *,
    resolver: ApplicantResolver,
    retrieved_at: datetime,
) -> IngestedSnapshot:
    """Stream the official relational export and retain watched organisations only."""

    archive = _safe_archive(path)
    try:
        source_sha256 = _file_sha256(path)
        failures: list[str] = []
        rows_read = {member.removesuffix(".csv"): 0 for member in EXPECTED_MEMBERS}
        schema_fingerprint = _schema_fingerprint(archive)
        resolved_by_number: dict[str, list[_ResolvedParty]] = defaultdict(list)
        selected_party_rows = 0

        reader, stream = _reader(archive, "party_activity.csv")
        try:
            for row_number, raw in enumerate(
                _bounded_rows(reader, member="party_activity.csv"), start=2
            ):
                rows_read["party_activity"] += 1
                if (
                    str(raw.get("ip_right_type", "")).casefold() != "trade_mark"
                    or str(raw.get("party_role_category", "")).casefold() != "applicant"
                    or str(raw.get("party_type", "")).casefold() != "organisation"
                ):
                    continue
                try:
                    resolved = resolver.resolve(str(raw.get("party_name", "")))
                    if resolved is None:
                        continue
                    selected_party_rows += 1
                    if selected_party_rows > MAX_SELECTED_PARTY_ROWS:
                        raise SourceArchiveError(
                            "selected applicant rows exceed the global safety limit"
                        )
                    party_row = SourcePartyActivity.model_validate(raw)
                    if not party_row.is_current:
                        continue
                    applicant, _ = resolved
                    candidate = _ResolvedParty(applicant, party_row.party_name)
                    if candidate not in resolved_by_number[party_row.application_number]:
                        resolved_by_number[party_row.application_number].append(candidate)
                except (ValidationError, ValueError):
                    _failure(failures, "party_activity.csv", row_number, "selected_row_invalid")
        finally:
            stream.close()

        ambiguous = {
            number
            for number, parties in resolved_by_number.items()
            if len({party.applicant.applicant_id for party in parties}) != 1
        }
        for ambiguous_number in sorted(ambiguous):
            _failure(
                failures,
                "party_activity.csv",
                0,
                "ambiguous_watchlist_match",
            )
            resolved_by_number.pop(ambiguous_number)
        selected_numbers = set(resolved_by_number)
        if len(selected_numbers) > MAX_SELECTED_APPLICATIONS:
            raise SourceArchiveError(
                "watchlist selection exceeds the "
                f"{MAX_SELECTED_APPLICATIONS:,} application safety limit"
            )

        applications: dict[str, SourceApplication] = {}
        duplicate_applications: set[str] = set()
        reader, stream = _reader(archive, "application.csv")
        try:
            for row_number, raw in enumerate(
                _bounded_rows(reader, member="application.csv"), start=2
            ):
                rows_read["application"] += 1
                application_number = raw.get("application_number")
                if (
                    application_number not in selected_numbers
                    or application_number in duplicate_applications
                ):
                    continue
                try:
                    application_row = SourceApplication.model_validate(raw)
                    if application_row.ip_right_type == "trade_mark":
                        if application_row.application_number in applications:
                            applications.pop(application_row.application_number)
                            duplicate_applications.add(application_row.application_number)
                            _failure(
                                failures,
                                "application.csv",
                                row_number,
                                "duplicate_selected_application",
                            )
                        else:
                            applications[application_row.application_number] = application_row
                except (ValidationError, ValueError):
                    _failure(failures, "application.csv", row_number, "selected_row_invalid")
        finally:
            stream.close()

        descriptions: dict[str, dict[str, SourceDescription]] = defaultdict(dict)
        selected_description_rows = 0
        reader, stream = _reader(archive, "application_description.csv")
        try:
            for row_number, raw in enumerate(
                _bounded_rows(reader, member="application_description.csv"), start=2
            ):
                rows_read["application_description"] += 1
                if raw.get("application_number") not in applications:
                    continue
                selected_description_rows += 1
                if selected_description_rows > MAX_SELECTED_DESCRIPTION_ROWS:
                    raise SourceArchiveError(
                        "selected description rows exceed the global safety limit"
                    )
                try:
                    description_row = SourceDescription.model_validate(raw)
                    if description_row.ip_right_type == "trade_mark":
                        description_key = stable_hash(description_row.model_dump(mode="json"))
                        application_descriptions = descriptions[
                            description_row.application_number
                        ]
                        if description_key not in application_descriptions:
                            if (
                                len(application_descriptions)
                                >= MAX_DESCRIPTIONS_PER_APPLICATION
                            ):
                                raise SourceArchiveError(
                                    "selected application exceeds the description safety limit"
                                )
                            application_descriptions[description_key] = description_row
                except (ValidationError, ValueError):
                    _failure(
                        failures,
                        "application_description.csv",
                        row_number,
                        "selected_row_invalid",
                    )
        finally:
            stream.close()

        classes: dict[str, set[int]] = defaultdict(set)
        reader, stream = _reader(archive, "application_classification.csv")
        try:
            for row_number, raw in enumerate(
                _bounded_rows(reader, member="application_classification.csv"), start=2
            ):
                rows_read["application_classification"] += 1
                if raw.get("application_number") not in applications:
                    continue
                try:
                    classification_row = SourceClassification.model_validate(raw)
                    class_number = _parse_class(classification_row.classification)
                    if (
                        classification_row.ip_right_type == "trade_mark"
                        and classification_row.is_current
                        and classification_row.classification_system.casefold() == "nice"
                        and class_number is not None
                    ):
                        classes[classification_row.application_number].add(class_number)
                except (ValidationError, ValueError):
                    _failure(
                        failures,
                        "application_classification.csv",
                        row_number,
                        "selected_row_invalid",
                    )
        finally:
            stream.close()

        events: dict[str, dict[str, TrademarkEvent]] = defaultdict(dict)
        selected_event_rows = 0
        reader, stream = _reader(archive, "application_events.csv")
        try:
            for row_number, raw in enumerate(
                _bounded_rows(reader, member="application_events.csv"), start=2
            ):
                rows_read["application_events"] += 1
                if raw.get("application_number") not in applications:
                    continue
                selected_event_rows += 1
                if selected_event_rows > MAX_SELECTED_EVENT_ROWS:
                    raise SourceArchiveError(
                        "selected event rows exceed the global safety limit"
                    )
                try:
                    event_row = SourceEvent.model_validate(raw)
                    if event_row.ip_right_type == "trade_mark":
                        event = _source_event(event_row)
                        application_events = events[event_row.application_number]
                        if event.event_id not in application_events:
                            if len(application_events) >= MAX_EVENTS_PER_APPLICATION:
                                raise SourceArchiveError(
                                    "selected application exceeds the event safety limit"
                                )
                            application_events[event.event_id] = event
                except (ValidationError, ValueError):
                    _failure(
                        failures,
                        "application_events.csv",
                        row_number,
                        "selected_row_invalid",
                    )
        finally:
            stream.close()

        trademarks: list[Trademark] = []
        for number, application in sorted(applications.items()):
            parties = resolved_by_number[number]
            party = sorted(parties, key=lambda item: item.observed_name)[0]
            source_descriptions = sorted(
                descriptions[number].values(),
                key=lambda item: (item.description_type, item.description_value),
            )
            phrases = sorted(
                {
                    item.description_value
                    for item in source_descriptions
                    if item.description_type == "trade_mark_word_mark_phrase"
                    and item.description_value
                }
            )
            image_words = sorted(
                {
                    item.description_value
                    for item in source_descriptions
                    if item.description_type == "trade_mark_image_words" and item.description_value
                }
            )
            mark_text = " | ".join(phrases or image_words) or None
            mark_types = sorted(
                {
                    item.description_type.removeprefix("trade_mark_")
                    for item in source_descriptions
                    if item.description_type.startswith("trade_mark_")
                }
            )
            trademark_classes = [
                TrademarkClass(class_number=class_number)
                for class_number in sorted(classes[number])
            ]
            trademark_events = sorted(
                events[number].values(),
                key=lambda item: (
                    item.declared_date
                    or item.effective_date
                    or application.application_date
                    or date.min,
                    item.event_id,
                ),
            )
            source_payload: dict[str, Any] = {
                "application": application.model_dump(mode="json"),
                "applicant_id": party.applicant.applicant_id,
                "observed_applicant_name": party.observed_name,
                "descriptions": [item.model_dump(mode="json") for item in source_descriptions],
                "classes": sorted(classes[number]),
                "events": [item.model_dump(mode="json") for item in trademark_events],
            }
            try:
                trademark = Trademark(
                    trademark_number=number,
                    applicant_id=party.applicant.applicant_id,
                    applicant_name=party.applicant.display_name,
                    observed_applicant_name=party.observed_name,
                    mark_text=mark_text,
                    mark_types=mark_types,
                    filing_date=application.application_date,
                    priority_date=application.priority_date,
                    current_status=application.status,
                    classes=trademark_classes,
                    events=trademark_events,
                    source_hash=stable_hash(source_payload),
                    source_dataset_url=IP_RAPID_DATASET_URL,
                    official_record_url=(
                        f"https://search.ipaustralia.gov.au/trademarks/search/view/{number}"
                    ),
                    first_seen_at=retrieved_at,
                    last_seen_at=retrieved_at,
                )
            except (ValidationError, ValueError):
                _failure(failures, "joined_record", 0, "selected_record_invalid")
                continue
            trademarks.append(trademark)
    finally:
        archive.close()

    return IngestedSnapshot(
        trademarks=trademarks,
        source_sha256=source_sha256,
        schema_fingerprint=schema_fingerprint,
        source_rows_read=dict(sorted(rows_read.items())),
        validation_failures=failures,
    )
