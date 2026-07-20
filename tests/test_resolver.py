from __future__ import annotations

from pathlib import Path

import pytest

from marksignal.models import Watchlist, WatchlistOrganisation
from marksignal.resolver import ApplicantResolver, WatchlistError, load_watchlists


def test_watchlists_load_and_exact_alias_resolves() -> None:
    resolver = ApplicantResolver(load_watchlists(Path("watchlists")))
    match = resolver.resolve("Northstar Labs Pty. Limited")
    assert match is not None
    applicant, alias = match
    assert applicant.applicant_id == "northstar-labs"
    assert alias.match_method == "exact_normalised"
    assert resolver.resolve("Northstar Laboratory Pty Ltd") is None


def test_production_watchlists_exclude_demonstration_organisations() -> None:
    resolver = ApplicantResolver(load_watchlists(Path("watchlists/production")))

    assert resolver.organisation_count == 12
    assert resolver.resolve("Northstar Labs Pty Ltd") is None


def test_similarity_candidates_do_not_resolve() -> None:
    resolver = ApplicantResolver(load_watchlists(Path("watchlists")))
    assert resolver.resolve("Northstar Lab Pty Ltd") is None
    assert resolver.suggest("Northstar Lab Pty Ltd", threshold=0.6)[0][0] == "northstar-labs"


def test_alias_collision_fails_closed() -> None:
    watchlist = Watchlist(
        schema_version=1,
        category="test",
        organisations=[
            WatchlistOrganisation(
                id="one", display_name="Example Limited", aliases=["Example Ltd"]
            ),
            WatchlistOrganisation(
                id="two", display_name="Example Ltd", aliases=["Example Limited"]
            ),
        ],
    )
    with pytest.raises(WatchlistError, match="multiple organisations"):
        ApplicantResolver([watchlist])
