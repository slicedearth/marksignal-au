"""Bounded availability checks for published official-record links."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx

LinkOutcome = Literal["reachable", "broken", "indeterminate"]

OFFICIAL_RECORD_PATTERN = re.compile(
    r"^https://search\.ipaustralia\.gov\.au/trademarks/search/view/\d{1,12}$"
)
MAX_PUBLISHED_LINKS = 25_000
MAX_LIVE_CHECKS = 3


class SourceLinkError(RuntimeError):
    """Raised when generated source-link data cannot be checked safely."""


@dataclass(frozen=True, slots=True)
class SourceLinkResult:
    """Availability outcome for one approved destination."""

    url: str
    outcome: LinkOutcome
    status_code: int | None = None
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class SourceLinkReport:
    """Aggregate result for a small deterministic availability sample."""

    published_links: int
    results: tuple[SourceLinkResult, ...]

    @property
    def checked(self) -> int:
        return len(self.results)

    @property
    def reachable(self) -> int:
        return sum(result.outcome == "reachable" for result in self.results)

    @property
    def broken(self) -> int:
        return sum(result.outcome == "broken" for result in self.results)

    @property
    def indeterminate(self) -> int:
        return sum(result.outcome == "indeterminate" for result in self.results)

    def public_summary(self) -> dict[str, int]:
        """Return only non-identifying counts suitable for public logs."""

        return {
            "published_links": self.published_links,
            "checked": self.checked,
            "reachable": self.reachable,
            "broken": self.broken,
            "indeterminate": self.indeterminate,
        }


def _collect_official_record_links(value: Any, links: set[str]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "official_record_url":
                if nested is None:
                    continue
                if not isinstance(nested, str):
                    raise SourceLinkError("official_record_url must be a string or null")
                links.add(nested)
            else:
                _collect_official_record_links(nested, links)
    elif isinstance(value, list):
        for nested in value:
            _collect_official_record_links(nested, links)


def dashboard_source_links(
    path: Path,
    *,
    maximum: int = MAX_PUBLISHED_LINKS,
) -> list[str]:
    """Read, deduplicate, allowlist, and bound generated official-record URLs."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SourceLinkError(f"cannot read generated dashboard: {type(exc).__name__}") from exc

    links: set[str] = set()
    _collect_official_record_links(payload, links)
    if not links:
        raise SourceLinkError("generated dashboard contains no official-record links")
    if len(links) > maximum:
        raise SourceLinkError(
            f"generated dashboard contains {len(links)} official-record links; "
            f"safety limit is {maximum}"
        )
    if any(OFFICIAL_RECORD_PATTERN.fullmatch(url) is None for url in links):
        raise SourceLinkError("generated dashboard contains an unapproved official-record URL")
    return sorted(links, key=lambda url: int(url.rsplit("/", 1)[-1]))


def sample_source_links(
    urls: list[str],
    *,
    maximum: int = MAX_LIVE_CHECKS,
) -> list[str]:
    """Choose deterministic low, middle, and high record numbers without over-requesting."""

    if not 1 <= maximum <= MAX_LIVE_CHECKS:
        raise ValueError(f"maximum must be between 1 and {MAX_LIVE_CHECKS}")
    if len(urls) <= maximum:
        return urls
    if maximum == 1:
        return [urls[-1]]

    positions = {
        round(index * (len(urls) - 1) / (maximum - 1))
        for index in range(maximum)
    }
    return [urls[index] for index in sorted(positions)]


def check_source_links(
    urls: list[str],
    *,
    published_links: int | None = None,
    timeout: float = 10.0,
    transport: httpx.BaseTransport | None = None,
) -> SourceLinkReport:
    """Send at most three sequential HEAD requests without following redirects."""

    if not urls:
        raise SourceLinkError("no official-record links were supplied")
    if len(urls) > MAX_LIVE_CHECKS:
        raise SourceLinkError(f"live source-link limit is {MAX_LIVE_CHECKS}")
    if any(OFFICIAL_RECORD_PATTERN.fullmatch(url) is None for url in urls):
        raise SourceLinkError("live check contains an unapproved official-record URL")

    results: list[SourceLinkResult] = []
    with httpx.Client(
        follow_redirects=False,
        timeout=httpx.Timeout(timeout),
        headers={
            "Accept": "text/html",
            "User-Agent": "MarkSignal-AU-LinkCheck/0.1",
        },
        limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        transport=transport,
    ) as client:
        for url in urls:
            try:
                with client.stream("HEAD", url) as response:
                    status_code = response.status_code
            except httpx.HTTPError as exc:
                results.append(
                    SourceLinkResult(
                        url=url,
                        outcome="indeterminate",
                        detail=type(exc).__name__,
                    )
                )
                continue

            if 200 <= status_code < 300:
                outcome: LinkOutcome = "reachable"
            elif status_code in {404, 410}:
                outcome = "broken"
            else:
                outcome = "indeterminate"
            results.append(
                SourceLinkResult(
                    url=url,
                    outcome=outcome,
                    status_code=status_code,
                )
            )

    return SourceLinkReport(
        published_links=published_links if published_links is not None else len(urls),
        results=tuple(results),
    )


def check_dashboard_source_links(path: Path) -> SourceLinkReport:
    """Validate every generated URL and availability-check a three-record sample."""

    links = dashboard_source_links(path)
    return check_source_links(
        sample_source_links(links),
        published_links=len(links),
    )
