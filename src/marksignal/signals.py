"""Explainable filing signal detection."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from marksignal.models import FilingSignal, SignalReason, Trademark
from marksignal.normalise import mark_tokens, stable_hash
from marksignal.similarity import mark_similarity

ALGORITHM_VERSION = "1.0.0"
CLUSTER_WINDOW_DAYS = 7
CLUSTER_SIMILARITY = 0.62
LONG_GAP_DAYS = 365


def _dated(trademarks: list[Trademark]) -> list[Trademark]:
    return sorted(
        (trademark for trademark in trademarks if trademark.filing_date is not None),
        key=lambda trademark: (trademark.filing_date, trademark.trademark_number),
    )


def detect_signals(trademarks: list[Trademark]) -> list[FilingSignal]:
    """Calculate all displayed reasons from filing history."""

    by_applicant: dict[str, list[Trademark]] = defaultdict(list)
    for trademark in trademarks:
        by_applicant[trademark.applicant_id].append(trademark)

    signals: list[FilingSignal] = []
    for applicant_id in sorted(by_applicant):
        filings = _dated(by_applicant[applicant_id])
        for index, current in enumerate(filings):
            if current.filing_date is None:
                continue
            history = filings[:index]
            reasons: list[SignalReason] = []

            prior_classes = {item.class_number for previous in history for item in previous.classes}
            current_classes = {item.class_number for item in current.classes}
            new_classes = sorted(current_classes - prior_classes) if history else []
            if new_classes:
                reasons.append(
                    SignalReason(
                        type="new_class",
                        points=25,
                        explanation=(
                            "First observed filing by this applicant in Nice "
                            f"class{'es' if len(new_classes) != 1 else ''} "
                            f"{', '.join(str(item) for item in new_classes)}."
                        ),
                        evidence={"new_classes": new_classes},
                    )
                )

            related = [
                candidate
                for candidate in filings
                if candidate.trademark_number != current.trademark_number
                and candidate.filing_date is not None
                and abs((candidate.filing_date - current.filing_date).days) <= CLUSTER_WINDOW_DAYS
                and mark_similarity(candidate.mark_text, current.mark_text) >= CLUSTER_SIMILARITY
            ]
            if len(related) >= 2:
                members = sorted(
                    [current.trademark_number, *(item.trademark_number for item in related)]
                )
                reasons.append(
                    SignalReason(
                        type="filing_cluster",
                        points=25,
                        explanation=(
                            f"Part of a {len(members)}-mark related filing cluster within "
                            f"{CLUSTER_WINDOW_DAYS} days."
                        ),
                        evidence={"member_trademark_numbers": members},
                    )
                )

            previous_dated = history[-1] if history else None
            if previous_dated is not None and previous_dated.filing_date is not None:
                gap_days = (current.filing_date - previous_dated.filing_date).days
                if gap_days >= LONG_GAP_DAYS:
                    reasons.append(
                        SignalReason(
                            type="long_filing_gap",
                            points=20,
                            explanation=f"First observed filing in {gap_days:,} days.",
                            evidence={"gap_days": gap_days},
                        )
                    )

            previous_tokens = {token for item in history for token in mark_tokens(item.mark_text)}
            new_tokens = sorted(mark_tokens(current.mark_text) - previous_tokens)
            if history and new_tokens:
                displayed = new_tokens[:5]
                reasons.append(
                    SignalReason(
                        type="novel_tokens",
                        points=20,
                        explanation=(
                            "Mark wording contains previously unobserved token"
                            f"{'s' if len(displayed) != 1 else ''}: {', '.join(displayed)}."
                        ),
                        evidence={"novel_tokens": displayed},
                    )
                )

            if not reasons:
                continue
            reason_payload = [reason.model_dump(mode="json") for reason in reasons]
            signals.append(
                FilingSignal(
                    signal_id=stable_hash(
                        {
                            "trademark_number": current.trademark_number,
                            "algorithm_version": ALGORITHM_VERSION,
                            "reasons": reason_payload,
                        }
                    ),
                    trademark_number=current.trademark_number,
                    applicant_id=applicant_id,
                    detected_at=current.last_seen_at,
                    score=sum(reason.points for reason in reasons),
                    reasons=reasons,
                )
            )
    filing_dates = {
        trademark.trademark_number: trademark.filing_date for trademark in trademarks
    }
    return sorted(
        signals,
        key=lambda signal: (
            filing_dates.get(signal.trademark_number) or date.min,
            signal.detected_at,
            signal.signal_id,
        ),
        reverse=True,
    )
