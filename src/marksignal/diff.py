"""Immutable snapshot change detection."""

from __future__ import annotations

from marksignal.models import ChangeType, ObservedChange, Trademark
from marksignal.normalise import normalise_mark_text, stable_hash


def _classes(trademark: Trademark) -> str:
    return ",".join(str(item.class_number) for item in trademark.classes)


def _event(
    current: Trademark,
    *,
    change_type: ChangeType,
    old_value: str | None,
    new_value: str | None,
    before_hash: str | None,
) -> ObservedChange:
    payload = {
        "trademark_number": current.trademark_number,
        "change_type": change_type,
        "detected_at": current.last_seen_at.isoformat(),
        "old_value": old_value,
        "new_value": new_value,
        "before_source_hash": before_hash,
        "after_source_hash": current.source_hash,
    }
    return ObservedChange(
        change_id=stable_hash(payload),
        trademark_number=current.trademark_number,
        change_type=change_type,
        detected_at=current.last_seen_at,
        old_value=old_value,
        new_value=new_value,
        before_source_hash=before_hash,
        after_source_hash=current.source_hash,
    )


def compare_trademarks(previous: Trademark | None, current: Trademark) -> list[ObservedChange]:
    """Compare material displayed fields while ignoring source-only churn."""

    if previous is None:
        return [
            _event(
                current,
                change_type="first_observed",
                old_value=None,
                new_value=current.current_status,
                before_hash=None,
            )
        ]

    comparisons: list[tuple[ChangeType, str | None, str | None]] = [
        ("status_changed", previous.current_status, current.current_status),
        ("classes_changed", _classes(previous), _classes(current)),
        (
            "mark_text_changed",
            normalise_mark_text(previous.mark_text),
            normalise_mark_text(current.mark_text),
        ),
        ("applicant_changed", previous.applicant_name, current.applicant_name),
    ]
    return [
        _event(
            current,
            change_type=change_type,
            old_value=old_value,
            new_value=new_value,
            before_hash=previous.source_hash,
        )
        for change_type, old_value, new_value in comparisons
        if old_value != new_value
    ]
