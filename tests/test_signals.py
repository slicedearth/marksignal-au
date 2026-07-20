from __future__ import annotations

from datetime import UTC, datetime

from conftest import make_trademark

from marksignal.signals import detect_signals


def test_signal_reasons_are_explainable_and_deterministic() -> None:
    timestamp = datetime(2026, 7, 20, tzinfo=UTC)
    filings = [
        make_trademark(
            "1001",
            mark_text="NORTHSTAR NEBULA",
            filing_date="2022-01-10",
            classes=[42],
            observed_at=timestamp,
        ),
        make_trademark(
            "1002",
            mark_text="NORTHSTAR NEBULA PAY",
            filing_date="2026-06-09",
            classes=[36, 42],
            observed_at=timestamp,
        ),
        make_trademark(
            "1003",
            mark_text="NORTHSTAR NEBULA WALLET",
            filing_date="2026-06-12",
            classes=[9, 36, 42],
            observed_at=timestamp,
        ),
        make_trademark(
            "1004",
            mark_text="NORTHSTAR NEBULA BUSINESS",
            filing_date="2026-06-15",
            classes=[35, 36, 42],
            observed_at=timestamp,
        ),
    ]
    first = detect_signals(filings)
    second = detect_signals(list(reversed(filings)))
    assert [item.model_dump() for item in first] == [item.model_dump() for item in second]
    assert [item.trademark_number for item in first] == ["1004", "1003", "1002"]
    signal = next(item for item in first if item.trademark_number == "1002")
    reason_types = {reason.type for reason in signal.reasons}
    assert {"new_class", "filing_cluster", "long_filing_gap", "novel_tokens"} <= reason_types
    assert signal.score == 90
    assert sum(reason.points for reason in signal.reasons) == signal.score


def test_first_or_undated_filing_does_not_invent_history() -> None:
    filings = [
        make_trademark("1001", filing_date=None),
        make_trademark("1002", filing_date="2026-01-01"),
    ]
    assert detect_signals(filings) == []
