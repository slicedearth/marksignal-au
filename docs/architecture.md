# Architecture

## Purpose

MarkSignal AU turns a large weekly relational export into a small, evidence-linked static
site for selected organisations. The runtime boundary is intentionally simple: data work
happens during a scheduled build and the public site serves files only.

```text
temporary IP RAPID ZIP
          |
          v
bounded streaming CSV adapter
          |
          v
exact watchlist alias resolver
          |
          v
normalised current trade mark state
          |
          +----> immutable observed-change events
          |
          +----> versioned deterministic signals
          |
          v
restricted durable state
          |
          v
temporary JSON, CSV, Parquet, RSS, and Astro pages
          |
          v
GitHub Pages
```

## Components

`src/marksignal/ip_rapid.py` verifies archive shape and streams the documented source
tables. It selects watched organisation applicants before retaining application,
description, classification, and event records.

`src/marksignal/resolver.py` loads YAML watchlists and resolves only exact normalised
aliases. Its similarity method produces review candidates but never changes identity.

`src/marksignal/diff.py` compares the previous and incoming state. New and changed records
produce immutable events. Records missing from one weekly subset are not deleted because a
temporary source omission is not evidence of withdrawal.

`src/marksignal/signals.py` calculates four reason types from ordered filing history. Every
reason stores points, an explanation, and machine-readable evidence under a named algorithm
version.

`src/marksignal/pipeline.py` writes durable state to a separately configured data root and
generates evidence files, downloads, and site data atomically in the build root. Astro renders
the result to static HTML. The signal feed uses 50-item static pages with sticky navigation,
page-local filters, and page-specific CSV export. A same-origin browser enhancement fetches one
bounded static page, validates its route and page metadata, and atomically replaces the main
region. Numbered-page requests bypass stored browser documents, while a four-page in-memory cache
supports repeat navigation within the current session. The enhancement preserves the selected
pagination control's viewport position and browser history.
Complete generated downloads remain available for dataset-wide work. The pipeline verifies
manifest hashes before it trusts durable state for a rebuild, update, or public status record.

## Data boundaries

The official ZIP stays in runner temporary storage and is never committed. Durable production
state, observations, signals, and manifests are committed to restricted versioned storage.
Published data is limited to matched organisation filings and calculated evidence. Source
hashes refer to the accepted input and selected records. The public repository's committed
starter dataset is fictional.

The project has no production database. In the restricted state checkout,
`data/state/trademarks.json` is the current selected state, while
`data/events/changes.json` is append-only in normal operation. Generated downloads are rebuilt
from those validated models inside the deployment runner and do not enter public Git history.

## Failure behaviour

Publication stops when the archive has unsafe paths, duplicate or unexpected members, missing or
duplicate columns, excessive download or expanded size, excessive table rows, oversized cells,
an excessive selected set, excessive global or per-record descriptions and events, ambiguous
applicant matches, or too many selected-row validation errors. Durable JSON and generated
publication volumes are bounded separately. The privacy scan supports a
non-writing audit, a strict stop on any match, and scheduled bounded quarantine. Quarantine
removes affected records from both incoming and previously retained state. The complete update stops when
matches exceed both three records and one percent of selected records. Validation and privacy
reports store bounded codes and marker types without rejected source values. Tests use local
fixtures and never contact a live service.

Generated official-record URLs are allowlisted offline before any request. The weekly update
then checks low, middle, and high record numbers with sequential `HEAD` requests, no redirects,
and no response body. A `404` or `410` confirms a broken destination and stops publication.
Access controls, redirects, rate limits, network errors, and server errors remain indeterminate
so an external outage cannot erase or block otherwise verified state.

## Deployment boundary

CI validates Python and Astro independently. The update workflow fetches and processes the
weekly archive, runs the full verification suite, commits durable data to restricted state, and writes
only a non-identifying status record publicly. The Pages workflow receives only read-only state
access and creates the public artifact. The update workflow introduces the separate write key
only after a data update passes verification. The built site contains no credential and cannot
mutate repository state.
