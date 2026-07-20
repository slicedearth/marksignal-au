from __future__ import annotations

import pytest
from conftest import make_trademark
from pydantic import ValidationError

from marksignal.models import Trademark, TrademarkClass, WatchlistOrganisation


def test_nice_classes_are_bounded() -> None:
    assert TrademarkClass(class_number=45).class_number == 45
    with pytest.raises(ValidationError):
        TrademarkClass(class_number=46)


def test_watchlist_aliases_reject_duplicates() -> None:
    with pytest.raises(ValidationError, match="unique"):
        WatchlistOrganisation(
            id="example",
            display_name="Example Pty Ltd",
            aliases=["Example Ltd", "example ltd"],
        )


def test_trademark_number_cannot_create_an_output_path() -> None:
    payload = make_trademark("1001").model_dump()
    payload["trademark_number"] = "1001/../../unexpected"
    with pytest.raises(ValidationError, match="trademark_number"):
        Trademark.model_validate(payload)
