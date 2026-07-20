# ADR 0001: Use a static build

Status: accepted

## Context

The application needs scheduled data processing, evidence downloads, searchable pages, and
low ongoing cost. It does not need accounts or request-time calculations.

## Decision

Run ingestion and signal detection in GitHub Actions, commit compact selected outputs, and
deploy an Astro static site to GitHub Pages.

## Consequences

The public surface has no application server or database. Updates follow the source and
workflow schedule rather than appearing in real time. Arbitrary private watchlists and
notifications are outside the initial scope.

