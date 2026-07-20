from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from marksignal.source_links import (
    SourceLinkError,
    check_source_links,
    dashboard_source_links,
    sample_source_links,
)

OFFICIAL_FIRST = "https://search.ipaustralia.gov.au/trademarks/search/view/1000001"
OFFICIAL_MIDDLE = "https://search.ipaustralia.gov.au/trademarks/search/view/2000002"
OFFICIAL_LAST = "https://search.ipaustralia.gov.au/trademarks/search/view/3000003"


class UnreadableStream(httpx.SyncByteStream):
    """Fail the test if the checker attempts to consume a response body."""

    def __iter__(self):  # type: ignore[no-untyped-def]
        raise AssertionError("source-link checker read a response body")


def test_dashboard_source_links_are_deduplicated_sorted_and_allowlisted(
    tmp_path: Path,
) -> None:
    path = tmp_path / "dashboard.json"
    path.write_text(
        json.dumps(
            {
                "signals": [
                    {"official_record_url": OFFICIAL_LAST},
                    {"official_record_url": OFFICIAL_FIRST},
                ],
                "trademarks": [
                    {"official_record_url": OFFICIAL_LAST},
                    {"official_record_url": None},
                ],
            }
        ),
        encoding="utf-8",
    )

    assert dashboard_source_links(path) == [OFFICIAL_FIRST, OFFICIAL_LAST]


def test_dashboard_source_links_reject_unapproved_or_excessive_sets(tmp_path: Path) -> None:
    path = tmp_path / "dashboard.json"
    path.write_text(
        json.dumps({"official_record_url": "https://example.com/record/1000001"}),
        encoding="utf-8",
    )
    with pytest.raises(SourceLinkError, match="unapproved"):
        dashboard_source_links(path)

    path.write_text(
        json.dumps(
            {
                "signals": [
                    {"official_record_url": OFFICIAL_FIRST},
                    {"official_record_url": OFFICIAL_LAST},
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(SourceLinkError, match="safety limit"):
        dashboard_source_links(path, maximum=1)


def test_sample_source_links_is_deterministic_and_capped() -> None:
    urls = [
        f"https://search.ipaustralia.gov.au/trademarks/search/view/{number}"
        for number in range(1000001, 1000011)
    ]

    assert sample_source_links(urls) == [urls[0], urls[4], urls[-1]]
    assert sample_source_links(urls, maximum=1) == [urls[-1]]
    with pytest.raises(ValueError, match="between 1 and 3"):
        sample_source_links(urls, maximum=4)


def test_source_link_outcomes_use_head_without_redirects_or_response_bodies() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if str(request.url) == OFFICIAL_FIRST:
            return httpx.Response(200, stream=UnreadableStream())
        if str(request.url) == OFFICIAL_MIDDLE:
            return httpx.Response(404)
        return httpx.Response(302, headers={"Location": "https://example.com/redirect"})

    report = check_source_links(
        [OFFICIAL_FIRST, OFFICIAL_MIDDLE, OFFICIAL_LAST],
        published_links=5_466,
        transport=httpx.MockTransport(handler),
    )

    assert [request.method for request in requests] == ["HEAD", "HEAD", "HEAD"]
    assert [result.outcome for result in report.results] == [
        "reachable",
        "broken",
        "indeterminate",
    ]
    assert report.public_summary() == {
        "published_links": 5_466,
        "checked": 3,
        "reachable": 1,
        "broken": 1,
        "indeterminate": 1,
    }


def test_source_link_check_bounds_requests_and_rejects_unapproved_urls() -> None:
    with pytest.raises(SourceLinkError, match="live source-link limit"):
        check_source_links([OFFICIAL_FIRST] * 4)

    with pytest.raises(SourceLinkError, match="unapproved"):
        check_source_links(["https://example.com/record/1000001"])
