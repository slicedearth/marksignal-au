from __future__ import annotations

from datetime import UTC, datetime

import pytest

from marksignal.models import ObservedChange, Trademark, TrademarkEvent
from marksignal.privacy import change_privacy_findings, privacy_findings


def _event() -> TrademarkEvent:
    return TrademarkEvent(
        event_id="a" * 64,
        event_type="Application accepted",
        event_category="Status",
        is_standing=True,
    )


def _trademark() -> Trademark:
    observed_at = datetime(2026, 7, 20, tzinfo=UTC)
    return Trademark(
        trademark_number="9000001",
        applicant_id="northstar-labs",
        applicant_name="Northstar Labs Pty Ltd",
        observed_applicant_name="Northstar Labs Pty Ltd",
        mark_text="NORTHSTAR",
        mark_types=["word_mark_phrase"],
        current_status="Registered",
        events=[_event()],
        source_hash="b" * 64,
        source_dataset_url="https://data.gov.au/data/dataset/iprapid",
        first_seen_at=observed_at,
        last_seen_at=observed_at,
        is_demo=True,
    )


@pytest.mark.parametrize(
    "record",
    [
        _trademark().model_copy(update={"current_status": "Contact owner@example.com"}),
        _trademark().model_copy(update={"mark_types": ["Contact owner@example.com"]}),
        _trademark().model_copy(
            update={
                "events": [
                    _event().model_copy(update={"event_type": "Contact owner@example.com"})
                ]
            }
        ),
        _trademark().model_copy(
            update={
                "events": [
                    _event().model_copy(update={"event_category": "Contact owner@example.com"})
                ]
            }
        ),
    ],
)
def test_every_retained_source_text_group_is_scanned(record: Trademark) -> None:
    findings = privacy_findings(record)
    assert {finding.marker for finding in findings} == {"email address"}


def test_change_values_are_scanned_before_publication() -> None:
    observed_at = datetime(2026, 7, 20, tzinfo=UTC)
    change = ObservedChange(
        change_id="c" * 64,
        trademark_number="9000001",
        change_type="status_changed",
        detected_at=observed_at,
        old_value="Registered",
        new_value="Contact owner@example.com",
        before_source_hash="d" * 64,
        after_source_hash="e" * 64,
    )
    findings = change_privacy_findings(change)
    assert {finding.field_name for finding in findings} == {"change_new_value"}
