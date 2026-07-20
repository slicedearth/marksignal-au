from __future__ import annotations

from datetime import UTC, datetime

from conftest import make_trademark

from marksignal.diff import compare_trademarks


def test_first_observation_and_material_changes() -> None:
    before = make_trademark("1001", status="filed", classes=[9], mark_text="NEBULA PAY")
    after = make_trademark(
        "1001",
        status="accepted",
        classes=[9, 36],
        mark_text="Nebula Wallet",
        observed_at=datetime(2026, 7, 21, tzinfo=UTC),
    ).model_copy(update={"source_hash": "b" * 64})
    assert compare_trademarks(None, before)[0].change_type == "first_observed"
    changes = compare_trademarks(before, after)
    assert {item.change_type for item in changes} == {
        "status_changed",
        "classes_changed",
        "mark_text_changed",
    }


def test_formatting_only_mark_change_is_ignored() -> None:
    before = make_trademark("1001", mark_text="NEBULA   PAY")
    after = make_trademark("1001", mark_text="nebula pay").model_copy(
        update={"source_hash": "b" * 64}
    )
    assert compare_trademarks(before, after) == []
