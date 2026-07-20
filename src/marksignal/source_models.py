"""Typed mappings for documented IP RAPID CSV fields."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from marksignal.normalise import clean_text, parse_bool, parse_date


class SourceRow(BaseModel):
    """Base for a selected subset of a wider documented source row."""

    model_config = ConfigDict(extra="ignore")


class SourceApplication(SourceRow):
    ip_right_type: str
    application_number: str = Field(min_length=1, max_length=32)
    ip_right_sub_type: str
    status: str = Field(min_length=1, max_length=100)
    application_date: date | None = None
    earliest_filed_date: date | None = None
    priority_date: date | None = None

    @field_validator("application_date", "earliest_filed_date", "priority_date", mode="before")
    @classmethod
    def source_dates(cls, value: object) -> date | None:
        return parse_date(value)


class SourcePartyActivity(SourceRow):
    ip_right_type: str
    application_number: str = Field(min_length=1, max_length=32)
    party_role_category: str
    party_type: str
    party_name: str = Field(min_length=1, max_length=300)
    is_current: bool

    @field_validator("is_current", mode="before")
    @classmethod
    def source_boolean(cls, value: object) -> bool:
        return parse_bool(value)

    @field_validator("party_name", mode="before")
    @classmethod
    def source_name(cls, value: object) -> str:
        cleaned = clean_text(str(value), maximum=300)
        if cleaned is None:
            raise ValueError("party_name cannot be blank")
        return cleaned


class SourceDescription(SourceRow):
    ip_right_type: str
    application_number: str = Field(min_length=1, max_length=32)
    description_type: str = Field(min_length=1, max_length=100)
    description_value: str = Field(default="", max_length=5_000)

    @field_validator("description_value", mode="before")
    @classmethod
    def source_description(cls, value: object) -> str:
        return clean_text(str(value or ""), maximum=5_000) or ""


class SourceClassification(SourceRow):
    ip_right_type: str
    application_number: str = Field(min_length=1, max_length=32)
    is_current: bool
    classification_system: str
    classification: str = Field(min_length=1, max_length=100)

    @field_validator("is_current", mode="before")
    @classmethod
    def source_boolean(cls, value: object) -> bool:
        return parse_bool(value)


class SourceEvent(SourceRow):
    ip_right_type: str
    application_number: str = Field(min_length=1, max_length=32)
    is_standing: bool
    event_type: str = Field(min_length=1, max_length=200)
    event_category: str = Field(min_length=1, max_length=200)
    event_effective_date: date | None = None
    event_declared_date: date | None = None

    @field_validator("is_standing", mode="before")
    @classmethod
    def source_boolean(cls, value: object) -> bool:
        return parse_bool(value)

    @field_validator("event_effective_date", "event_declared_date", mode="before")
    @classmethod
    def source_dates(cls, value: object) -> date | None:
        return parse_date(value)
