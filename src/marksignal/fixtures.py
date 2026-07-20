"""Synthetic fixture adapter used for tests and the initial static demonstration."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from marksignal.ip_rapid import IP_RAPID_DATASET_URL, IngestedSnapshot
from marksignal.models import Trademark, TrademarkClass, TrademarkEvent
from marksignal.normalise import stable_hash
from marksignal.resolver import ApplicantResolver


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("fixture retrieved_at must include a timezone")
    return parsed


def read_fixture(
    path: Path,
    *,
    resolver: ApplicantResolver,
) -> tuple[IngestedSnapshot, datetime]:
    """Validate a privacy-safe synthetic fixture through production models."""

    content = path.read_bytes()
    payload = json.loads(content)
    if not isinstance(payload, dict) or not isinstance(payload.get("trademarks"), list):
        raise ValueError("fixture must contain a trademarks array")
    if payload.get("fixture_type") != "synthetic_demo":
        raise ValueError("fixture_type must be synthetic_demo")
    retrieved_at = _timestamp(str(payload["retrieved_at"]))
    trademarks: list[Trademark] = []
    for raw in payload["trademarks"]:
        if not isinstance(raw, dict):
            raise ValueError("fixture trade marks must be objects")
        applicant_id = str(raw["applicant_id"])
        applicant = resolver.applicants.get(applicant_id)
        if applicant is None:
            raise ValueError(f"fixture references unknown applicant {applicant_id!r}")
        events = [
            TrademarkEvent(
                event_id=stable_hash(event),
                event_type=str(event["event_type"]),
                event_category=str(event["event_category"]),
                effective_date=event.get("effective_date"),
                declared_date=event.get("declared_date"),
                is_standing=bool(event["is_standing"]),
            )
            for event in raw.get("events", [])
        ]
        source_payload: dict[str, Any] = {
            key: value
            for key, value in raw.items()
            if key not in {"source_hash", "first_seen_at", "last_seen_at"}
        }
        trademarks.append(
            Trademark(
                trademark_number=str(raw["trademark_number"]),
                applicant_id=applicant_id,
                applicant_name=applicant.display_name,
                observed_applicant_name=str(
                    raw.get("observed_applicant_name", applicant.display_name)
                ),
                mark_text=raw.get("mark_text"),
                mark_types=list(raw.get("mark_types", ["word_mark_phrase"])),
                filing_date=raw.get("filing_date"),
                priority_date=raw.get("priority_date"),
                current_status=str(raw["current_status"]),
                classes=[
                    TrademarkClass(class_number=int(class_number))
                    for class_number in raw.get("classes", [])
                ],
                events=events,
                source_hash=stable_hash(source_payload),
                source_dataset_url=IP_RAPID_DATASET_URL,
                official_record_url=None,
                first_seen_at=retrieved_at,
                last_seen_at=retrieved_at,
                is_demo=True,
            )
        )
    field_names = sorted(
        {str(key) for raw in payload["trademarks"] if isinstance(raw, dict) for key in raw}
    )
    return (
        IngestedSnapshot(
            trademarks=trademarks,
            source_sha256=hashlib.sha256(content).hexdigest(),
            schema_fingerprint=stable_hash(field_names),
            source_rows_read={"synthetic_fixture": len(trademarks)},
            validation_failures=[],
        ),
        retrieved_at,
    )
