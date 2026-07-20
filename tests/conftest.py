from __future__ import annotations

from datetime import UTC, datetime

import pytest

from marksignal.models import Trademark, TrademarkClass


@pytest.fixture
def observed_at() -> datetime:
    return datetime(2026, 7, 20, tzinfo=UTC)


def make_trademark(
    number: str,
    *,
    applicant_id: str = "northstar-labs",
    applicant_name: str = "Northstar Labs Pty Ltd",
    mark_text: str | None = "NORTHSTAR NEBULA",
    filing_date: str | None = "2026-01-01",
    status: str = "filed",
    classes: list[int] | None = None,
    observed_at: datetime | None = None,
) -> Trademark:
    timestamp = observed_at or datetime(2026, 7, 20, tzinfo=UTC)
    return Trademark(
        trademark_number=number,
        applicant_id=applicant_id,
        applicant_name=applicant_name,
        observed_applicant_name=applicant_name,
        mark_text=mark_text,
        mark_types=["word_mark_phrase"],
        filing_date=filing_date,
        priority_date=filing_date,
        current_status=status,
        classes=[TrademarkClass(class_number=value) for value in classes or [42]],
        source_hash=(number.zfill(64)[-64:]).replace("9", "a"),
        source_dataset_url="https://data.gov.au/data/dataset/iprapid",
        official_record_url=(f"https://search.ipaustralia.gov.au/trademarks/search/view/{number}"),
        first_seen_at=timestamp,
        last_seen_at=timestamp,
    )
