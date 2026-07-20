from __future__ import annotations

import pytest

from marksignal.similarity import character_ngrams, mark_similarity


def test_similarity_is_symmetric_and_bounded() -> None:
    left = mark_similarity("NORTHSTAR NEBULA PAY", "NORTHSTAR NEBULA WALLET")
    right = mark_similarity("NORTHSTAR NEBULA WALLET", "NORTHSTAR NEBULA PAY")
    assert left == pytest.approx(right)
    assert 0.62 <= left <= 1
    assert mark_similarity("NORTHSTAR NEBULA", "PAPER KITE") < 0.2


def test_empty_marks_do_not_cluster() -> None:
    assert mark_similarity(None, "EXAMPLE") == 0
    assert not character_ngrams(None)
    with pytest.raises(ValueError, match="between 2 and 5"):
        character_ngrams("EXAMPLE", size=1)
