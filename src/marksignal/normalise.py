"""Deterministic text and identifier normalisation."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from typing import Any

_SPACE_RE = re.compile(r"\s+")
_NON_NAME_RE = re.compile(r"[^A-Z0-9]+")
_TOKEN_RE = re.compile(r"[A-Z0-9]+")
_NOVELTY_STOP_WORDS = {
    "A",
    "AN",
    "AND",
    "AU",
    "AUSTRALIA",
    "AUSTRALIAN",
    "FOR",
    "OF",
    "THE",
}


def clean_text(value: str | None, *, maximum: int = 5_000) -> str | None:
    """Normalise Unicode and whitespace while preserving source wording."""

    if value is None:
        return None
    cleaned = _SPACE_RE.sub(" ", unicodedata.normalize("NFKC", str(value))).strip()
    if not cleaned:
        return None
    if len(cleaned) > maximum:
        raise ValueError(f"text exceeds {maximum} characters")
    return cleaned


def normalise_applicant_name(value: str) -> str:
    """Standardise conservative legal-form variants without removing suffixes."""

    cleaned = clean_text(value, maximum=300)
    if cleaned is None:
        raise ValueError("applicant name cannot be blank")
    upper = unicodedata.normalize("NFKD", cleaned).encode("ascii", "ignore").decode("ascii")
    upper = upper.upper().replace("&", " AND ")
    tokens = _NON_NAME_RE.sub(" ", upper).split()

    result: list[str] = []
    index = 0
    while index < len(tokens):
        pair = tuple(tokens[index : index + 2])
        if pair in {
            ("PROPRIETARY", "LIMITED"),
            ("PROPRIETARY", "LTD"),
            ("PTY", "LIMITED"),
            ("PTY", "LTD"),
        }:
            result.extend(("PTY", "LTD"))
            index += 2
            continue
        token = tokens[index]
        result.append("LTD" if token == "LIMITED" else token)
        index += 1
    if not result:
        raise ValueError("applicant name has no searchable characters")
    return " ".join(result)


def normalise_mark_text(value: str | None) -> str | None:
    """Return a comparison form for a word mark or image words."""

    cleaned = clean_text(value)
    if cleaned is None:
        return None
    ascii_text = unicodedata.normalize("NFKD", cleaned).encode("ascii", "ignore").decode("ascii")
    return " ".join(_TOKEN_RE.findall(ascii_text.upper())) or None


def mark_tokens(value: str | None) -> set[str]:
    """Select meaningful deterministic tokens for novelty comparisons."""

    normalised = normalise_mark_text(value)
    if normalised is None:
        return set()
    return {
        token
        for token in normalised.split()
        if len(token) >= 2 and token not in _NOVELTY_STOP_WORDS
    }


def parse_bool(value: Any) -> bool:
    """Parse the boolean forms used in IP RAPID CSV exports."""

    if isinstance(value, bool):
        return value
    normalised = str(value).strip().casefold()
    if normalised in {"true", "t", "1", "yes", "y"}:
        return True
    if normalised in {"false", "f", "0", "no", "n", ""}:
        return False
    raise ValueError(f"unrecognised boolean value: {value!r}")


def parse_date(value: Any) -> date | None:
    """Parse an ISO or day-first source date without guessing other formats."""

    if value is None or not str(value).strip():
        return None
    text = str(value).strip()
    for format_string in (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%fZ",
    ):
        try:
            return datetime.strptime(text, format_string).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date value: {text!r}")


def canonical_json(value: Any) -> bytes:
    """Serialise a value for stable hashing and output comparison."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=lambda item: item.isoformat(),
    ).encode("utf-8")


def stable_hash(value: Any) -> str:
    """Return a SHA-256 digest for canonical JSON data."""

    return hashlib.sha256(canonical_json(value)).hexdigest()
