from __future__ import annotations

import pytest

from marksignal.normalise import (
    mark_tokens,
    normalise_applicant_name,
    normalise_mark_text,
    parse_bool,
    parse_date,
)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Example Pty. Limited", "EXAMPLE PTY LTD"),
        ("Example Proprietary Ltd", "EXAMPLE PTY LTD"),
        ("Example & Sons Limited", "EXAMPLE AND SONS LTD"),
        ("  Example\tLtd  ", "EXAMPLE LTD"),
    ],
)
def test_normalise_applicant_legal_forms(source: str, expected: str) -> None:
    assert normalise_applicant_name(source) == expected


def test_normalisation_does_not_strip_distinguishing_legal_form() -> None:
    assert normalise_applicant_name("Example Holdings Pty Ltd") != normalise_applicant_name(
        "Example Pty Ltd"
    )
    assert normalise_applicant_name("Example Pty Ltd") != normalise_applicant_name("Example Ltd")


def test_mark_tokens_drop_only_documented_generic_words() -> None:
    assert normalise_mark_text("  Nébula & Pay  ") == "NEBULA PAY"
    assert mark_tokens("The Nebula Pay Australia") == {"NEBULA", "PAY"}


def test_source_scalar_parsers_are_explicit() -> None:
    assert parse_bool("TRUE") is True
    assert parse_bool("0") is False
    assert parse_date("20/07/2026").isoformat() == "2026-07-20"  # type: ignore[union-attr]
    with pytest.raises(ValueError, match="unrecognised"):
        parse_bool("perhaps")
    with pytest.raises(ValueError, match="unrecognised"):
        parse_date("July 20")
