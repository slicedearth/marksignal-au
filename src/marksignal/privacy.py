"""High-confidence privacy checks for selected public trade mark fields."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Literal

from marksignal.models import Trademark

PrivacyMode = Literal["strict", "quarantine"]
QUARANTINE_ABSOLUTE_TOLERANCE = 3
QUARANTINE_FRACTION_TOLERANCE = 0.01

PATTERNS = {
    "email address": re.compile(
        r"(?i)(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])"
    ),
    "labelled business identifier": re.compile(
        r"(?i)\b(?:ABN|ACN|Australian Business Number)\s*[:#-]?\s*"
        r"(?:\d[ -]?){8,11}\b"
    ),
    "Australian phone number": re.compile(
        r"(?<!\d)(?:\+?61[ -]?[2-478]|0[2-478])(?:[ -]?\d){8}(?!\d)"
    ),
    "street address": re.compile(
        r"(?i)\b\d{1,5}\s+[A-Z][A-Z0-9'. -]{1,60}\s+"
        r"(?:STREET|ST|ROAD|RD|AVENUE|AVE|DRIVE|DR|COURT|CT|LANE|LN|PLACE|PL)\b"
    ),
}


@dataclass(frozen=True, slots=True)
class PrivacyFinding:
    """Field and marker type without retaining the matched source value."""

    field_name: str
    marker: str


@dataclass(frozen=True, slots=True)
class QuarantinedTrademark:
    """A private review pointer without the matched source text."""

    trademark_number: str
    source_hash: str
    fields: tuple[str, ...]
    markers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PrivacyAudit:
    """Partitioned publication set and aggregate privacy coverage."""

    accepted: tuple[Trademark, ...]
    quarantined: tuple[QuarantinedTrademark, ...]
    selected_count: int
    marker_counts: dict[str, int]
    field_counts: dict[str, int]

    @property
    def quarantined_count(self) -> int:
        return len(self.quarantined)

    @property
    def quarantined_fraction(self) -> float:
        if self.selected_count == 0:
            return 0.0
        return self.quarantined_count / self.selected_count

    @property
    def threshold_exceeded(self) -> bool:
        return (
            self.quarantined_count > QUARANTINE_ABSOLUTE_TOLERANCE
            and self.quarantined_fraction > QUARANTINE_FRACTION_TOLERANCE
        )

    def public_summary(self) -> dict[str, object]:
        """Return aggregate counts suitable for logs and public status."""

        return {
            "selected_count": self.selected_count,
            "accepted_count": len(self.accepted),
            "quarantined_count": self.quarantined_count,
            "quarantined_fraction": round(self.quarantined_fraction, 6),
            "marker_counts": self.marker_counts,
            "field_counts": self.field_counts,
            "threshold_exceeded": self.threshold_exceeded,
            "absolute_tolerance": QUARANTINE_ABSOLUTE_TOLERANCE,
            "fraction_tolerance": QUARANTINE_FRACTION_TOLERANCE,
        }


def privacy_findings(trademark: Trademark) -> tuple[PrivacyFinding, ...]:
    """Find contact or address markers in fields retained for publication."""

    fields: dict[str, str | None] = {
        "applicant_name": trademark.applicant_name,
        "observed_applicant_name": trademark.observed_applicant_name,
        "mark_text": trademark.mark_text,
        **{
            f"class_{item.class_number}_goods_services": item.goods_services_text
            for item in trademark.classes
        },
    }
    findings: list[PrivacyFinding] = []
    for field_name, value in fields.items():
        if not value:
            continue
        for marker, pattern in PATTERNS.items():
            if pattern.search(value):
                findings.append(PrivacyFinding(field_name=field_name, marker=marker))
    return tuple(findings)


def audit_trademarks(trademarks: list[Trademark]) -> PrivacyAudit:
    """Partition selected records without retaining matched source values."""

    accepted: list[Trademark] = []
    quarantined: list[QuarantinedTrademark] = []
    marker_counts: Counter[str] = Counter()
    field_counts: Counter[str] = Counter()
    for trademark in trademarks:
        findings = privacy_findings(trademark)
        if not findings:
            accepted.append(trademark)
            continue
        fields = tuple(sorted({finding.field_name for finding in findings}))
        markers = tuple(sorted({finding.marker for finding in findings}))
        marker_counts.update(markers)
        field_counts.update(fields)
        quarantined.append(
            QuarantinedTrademark(
                trademark_number=trademark.trademark_number,
                source_hash=trademark.source_hash,
                fields=fields,
                markers=markers,
            )
        )
    return PrivacyAudit(
        accepted=tuple(accepted),
        quarantined=tuple(quarantined),
        selected_count=len(trademarks),
        marker_counts=dict(sorted(marker_counts.items())),
        field_counts=dict(sorted(field_counts.items())),
    )
