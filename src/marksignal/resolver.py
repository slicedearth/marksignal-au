"""Watchlist loading and conservative applicant entity resolution."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import yaml

from marksignal.models import Applicant, ApplicantAlias, Watchlist
from marksignal.normalise import normalise_applicant_name
from marksignal.similarity import mark_similarity


class WatchlistError(ValueError):
    """Raised when watchlists are invalid or ambiguous."""


class ApplicantResolver:
    """Resolve only exact normalised aliases and expose fuzzy candidates separately."""

    def __init__(self, watchlists: list[Watchlist]) -> None:
        categories: dict[str, set[str]] = defaultdict(set)
        display_names: dict[str, str] = {}
        alias_lookup: dict[str, tuple[str, str]] = {}

        for watchlist in watchlists:
            for organisation in watchlist.organisations:
                categories[organisation.id].add(watchlist.category)
                existing_name = display_names.setdefault(organisation.id, organisation.display_name)
                if existing_name != organisation.display_name:
                    raise WatchlistError(
                        f"organisation {organisation.id!r} has conflicting display names"
                    )
                for alias in [organisation.display_name, *organisation.aliases]:
                    normalised = normalise_applicant_name(alias)
                    existing = alias_lookup.get(normalised)
                    if existing is not None and existing[0] != organisation.id:
                        raise WatchlistError(
                            f"normalised alias {normalised!r} maps to multiple organisations"
                        )
                    alias_lookup[normalised] = (organisation.id, alias)

        self._aliases = alias_lookup
        self.applicants = {
            applicant_id: Applicant(
                applicant_id=applicant_id,
                display_name=display_name,
                categories=sorted(categories[applicant_id]),
            )
            for applicant_id, display_name in sorted(display_names.items())
        }

    @property
    def organisation_count(self) -> int:
        return len(self.applicants)

    def resolve(self, source_name: str) -> tuple[Applicant, ApplicantAlias] | None:
        """Resolve a source name through an exact normalised alias."""

        normalised = normalise_applicant_name(source_name)
        match = self._aliases.get(normalised)
        if match is None:
            return None
        applicant_id, _ = match
        return self.applicants[applicant_id], ApplicantAlias(
            applicant_id=applicant_id,
            alias=source_name,
            normalised_alias=normalised,
            alias_source="ip_rapid",
            match_method="exact_normalised",
        )

    def suggest(self, source_name: str, *, threshold: float = 0.82) -> list[tuple[str, float]]:
        """Return review candidates without changing entity resolution."""

        normalised = normalise_applicant_name(source_name)
        candidates: dict[str, float] = {}
        for alias, (applicant_id, _) in self._aliases.items():
            score = mark_similarity(normalised, alias)
            if score >= threshold:
                candidates[applicant_id] = max(candidates.get(applicant_id, 0.0), score)
        return sorted(candidates.items(), key=lambda item: (-item[1], item[0]))


def load_watchlists(path: Path) -> list[Watchlist]:
    """Load every YAML watchlist below a directory in stable order."""

    if not path.is_dir():
        raise WatchlistError(f"watchlist directory does not exist: {path}")
    files = sorted([*path.glob("*.yml"), *path.glob("*.yaml")])
    if not files:
        raise WatchlistError(f"no YAML watchlists found in {path}")
    watchlists: list[Watchlist] = []
    for file_path in files:
        payload = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        try:
            watchlists.append(Watchlist.model_validate(payload))
        except (TypeError, ValueError) as exc:
            raise WatchlistError(f"invalid watchlist {file_path}: {exc}") from exc
    ApplicantResolver(watchlists)
    return watchlists
