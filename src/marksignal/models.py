"""Validated, privacy-minimised models used throughout MarkSignal AU."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    """Base model that rejects source or pipeline schema drift."""

    model_config = ConfigDict(extra="forbid")


class WatchlistOrganisation(StrictModel):
    """One deliberately curated organisation and its exact aliases."""

    id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    display_name: str = Field(min_length=1, max_length=300)
    aliases: list[str] = Field(min_length=1, max_length=50)

    @field_validator("aliases")
    @classmethod
    def unique_aliases(cls, value: list[str]) -> list[str]:
        cleaned = [" ".join(alias.split()) for alias in value]
        if any(not alias for alias in cleaned):
            raise ValueError("aliases cannot be blank")
        if len({alias.casefold() for alias in cleaned}) != len(cleaned):
            raise ValueError("aliases must be unique within an organisation")
        return cleaned


class Watchlist(StrictModel):
    """Versioned YAML watchlist contract."""

    schema_version: Literal[1]
    category: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    organisations: list[WatchlistOrganisation] = Field(min_length=1, max_length=250)


class ApplicantAlias(StrictModel):
    """A traceable applicant alias used by exact entity resolution."""

    applicant_id: str
    alias: str = Field(min_length=1, max_length=300)
    normalised_alias: str = Field(min_length=1, max_length=300)
    alias_source: Literal["watchlist", "ip_rapid"]
    match_method: Literal["exact_normalised"]


class Applicant(StrictModel):
    """A watched organisation after deterministic resolution."""

    applicant_id: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    display_name: str = Field(min_length=1, max_length=300)
    categories: list[str] = Field(min_length=1, max_length=20)
    observed_names: list[str] = Field(default_factory=list, max_length=50)


class TrademarkClass(StrictModel):
    """A current Nice class observed for a trade mark."""

    class_number: int = Field(ge=1, le=45)
    goods_services_text: str | None = Field(default=None, max_length=20_000)


class TrademarkEvent(StrictModel):
    """One event from the IP RAPID application-events table."""

    event_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    event_type: str = Field(min_length=1, max_length=200)
    event_category: str = Field(min_length=1, max_length=200)
    effective_date: date | None = None
    declared_date: date | None = None
    is_standing: bool


class Trademark(StrictModel):
    """A source-linked trade mark selected through a watchlist."""

    trademark_number: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9.-]{0,31}$")
    applicant_id: str
    applicant_name: str = Field(min_length=1, max_length=300)
    observed_applicant_name: str = Field(min_length=1, max_length=300)
    mark_text: str | None = Field(default=None, max_length=5_000)
    mark_types: list[str] = Field(default_factory=list, max_length=20)
    filing_date: date | None = None
    priority_date: date | None = None
    current_status: str = Field(min_length=1, max_length=100)
    classes: list[TrademarkClass] = Field(default_factory=list, max_length=45)
    events: list[TrademarkEvent] = Field(default_factory=list, max_length=2_000)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_dataset_url: str = Field(pattern=r"^https://data\.gov\.au/")
    official_record_url: str | None = Field(
        default=None,
        pattern=r"^https://search\.ipaustralia\.gov\.au/trademarks/search/view/",
    )
    first_seen_at: datetime
    last_seen_at: datetime
    is_demo: bool = False

    @field_validator("classes")
    @classmethod
    def unique_classes(cls, value: list[TrademarkClass]) -> list[TrademarkClass]:
        numbers = [item.class_number for item in value]
        if len(numbers) != len(set(numbers)):
            raise ValueError("trade mark classes must be unique")
        return sorted(value, key=lambda item: item.class_number)


SignalType = Literal["new_class", "filing_cluster", "long_filing_gap", "novel_tokens"]
SignalEvidenceValue = str | int | float | list[str] | list[int]


class SignalReason(StrictModel):
    """A displayed component of the deterministic signal score."""

    type: SignalType
    points: int = Field(gt=0, le=25)
    explanation: str = Field(min_length=1, max_length=500)
    evidence: dict[str, SignalEvidenceValue] = Field(default_factory=dict)


class FilingSignal(StrictModel):
    """A filing and the complete reason breakdown for surfacing it."""

    signal_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    trademark_number: str
    applicant_id: str
    detected_at: datetime
    score: int = Field(ge=0, le=90)
    maximum_score: Literal[90] = 90
    algorithm_version: Literal["1.0.0"] = "1.0.0"
    reasons: list[SignalReason] = Field(min_length=1, max_length=4)


ChangeType = Literal[
    "first_observed",
    "status_changed",
    "classes_changed",
    "mark_text_changed",
    "applicant_changed",
]


class ObservedChange(StrictModel):
    """An immutable difference between two observed snapshots."""

    change_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    trademark_number: str
    change_type: ChangeType
    detected_at: datetime
    old_value: str | None
    new_value: str | None
    before_source_hash: str | None
    after_source_hash: str


class SourceManifest(StrictModel):
    """Provenance, quality, and output metadata for one accepted snapshot."""

    parser_version: str
    signal_algorithm_version: str
    retrieved_at: datetime
    source_url: str
    source_publisher: Literal["IP Australia"]
    source_license: Literal["https://creativecommons.org/licenses/by/4.0/"]
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    schema_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    is_demo: bool
    watchlist_organisations: int = Field(ge=1)
    source_rows_read: dict[str, int]
    matched_trade_marks: int = Field(ge=0)
    emitted_signals: int = Field(ge=0)
    changes_added: int = Field(ge=0)
    privacy_quarantined: int = Field(default=0, ge=0)
    privacy_marker_counts: dict[str, int] = Field(default_factory=dict)
    validation_failures: list[str] = Field(default_factory=list, max_length=200)
    state_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    signals_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    changes_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PipelineResult(StrictModel):
    """Small summary returned by the CLI and tests."""

    matched_trade_marks: int
    emitted_signals: int
    changes_added: int
    changes_total: int
    manifest_path: str
    privacy_quarantined: int = 0
    unchanged_source: bool = False


class PublicUpdateStatus(StrictModel):
    """Non-identifying pointer from the public repository to restricted state."""

    schema_version: Literal[1] = 1
    data_revision: str = Field(pattern=r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
    retrieved_at: datetime
    source_publisher: Literal["IP Australia"]
    source_rows_read: int = Field(ge=0)
    watchlist_organisations: int = Field(ge=1)
    matched_trade_marks: int = Field(ge=0)
    emitted_signals: int = Field(ge=0)
    privacy_quarantined: int = Field(ge=0)
    validation_failure_count: int = Field(ge=0)
