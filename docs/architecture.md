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
the result to static HTML.

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

Publication stops when the archive has unsafe paths, duplicate or unexpected members,
missing required columns, excessive size, oversized cells, ambiguous applicant matches, or
too many selected-row validation errors. The privacy scan supports a non-writing audit, a
strict stop on any match, and scheduled bounded quarantine. Quarantine removes affected
records from both incoming and previously retained state. The complete update stops when
matches exceed both three records and one percent of selected records. Validation and privacy
reports store bounded codes and marker types without rejected source values. Tests use local
fixtures and never contact a live service.

## Deployment boundary

CI validates Python and Astro independently. The update workflow fetches and processes the
weekly archive, runs the full verification suite, commits durable data to restricted state, and writes
only a non-identifying status record publicly. The Pages workflow reads restricted state through
separate repository-scoped read and write deploy keys and creates the public artifact. The Pages
generator receives read-only state access, while the write key is introduced only after a data
update passes verification. The built site contains no credential and cannot mutate repository
state.
