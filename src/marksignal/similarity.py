"""Reproducible character n-gram similarity for related word marks."""

from __future__ import annotations

import math
from collections import Counter

from marksignal.normalise import normalise_mark_text


def character_ngrams(value: str | None, *, size: int = 3) -> Counter[str]:
    """Return counted, boundary-padded character n-grams."""

    if size < 2 or size > 5:
        raise ValueError("n-gram size must be between 2 and 5")
    normalised = normalise_mark_text(value)
    if normalised is None:
        return Counter()
    padded = f"{' ' * (size - 1)}{normalised}{' ' * (size - 1)}"
    return Counter(padded[index : index + size] for index in range(len(padded) - size + 1))


def mark_similarity(left: str | None, right: str | None, *, size: int = 3) -> float:
    """Calculate cosine similarity between two character n-gram vectors."""

    left_counts = character_ngrams(left, size=size)
    right_counts = character_ngrams(right, size=size)
    if not left_counts or not right_counts:
        return 0.0
    dot_product = sum(count * right_counts.get(gram, 0) for gram, count in left_counts.items())
    left_norm = math.sqrt(sum(count * count for count in left_counts.values()))
    right_norm = math.sqrt(sum(count * count for count in right_counts.values()))
    return dot_product / (left_norm * right_norm)
