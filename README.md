# MarkSignal AU

**Early corporate signals in public Australian trade mark filings.**

MarkSignal AU monitors organisations defined in version-controlled watchlists and surfaces
reproducible filing patterns such as first-observed Nice classes, related filing clusters,
long filing gaps, and new mark-name tokens.

[View the dashboard](https://slicedearth.github.io/marksignal-au/) ·
[Read the methodology](docs/methodology.md) ·
[Inspect the data dictionary](docs/data-dictionary.md) ·
[Review the data boundary](docs/privacy-and-data-boundary.md) ·
[Read the threat model](docs/threat-model.md) ·
[Review legal and licensing notes](docs/legal-and-licensing.md)

## What it shows

- a filterable feed with a complete reason and point breakdown
- applicant timelines, current classes, filing frequency, and related marks
- source-linked trade mark detail pages and immutable observation events
- downloadable JSON, CSV, Parquet, and RSS outputs
- retrieval manifests, source hashes, schema fingerprints, and quality stops
- YAML watchlists with exact, reviewable applicant aliases

A trade mark filing is not confirmation that a product or service will launch. Applications
may be defensive, speculative, abandoned, refused, or unrelated to current commercial
plans. MarkSignal presents research leads, not legal or commercial conclusions.

> The committed dashboard dataset uses clearly labelled fictional organisations and trade
> marks. It demonstrates the complete pipeline without attaching synthetic findings to real
> companies. Production records are generated from restricted deployment state during
> deployment and do not enter public Git history.

## How it works

```text
IP RAPID weekly archive
          |
          v
stream six documented CSV tables and select watched organisations
          |
          v
normalise names, dates, classes, descriptions, events, and source evidence
          |
          v
exact alias resolution and character n-gram filing comparison
          |
          v
append observation events and calculate explainable signal reasons
          |
          v
write durable state and manifests to restricted storage
          |
          v
generate temporary JSON, CSV, Parquet, RSS, applicant, and filing pages
          |
          v
GitHub Actions and GitHub Pages
```

The signal feed is divided into 50-item static pages with controls above and below the results.
Pagination replaces the generated main region in place, keeps the selected control visually
anchored, and updates browser history without a document reload. The static links remain usable
when scripting or a same-origin page request is unavailable. Filters and filtered CSV downloads
operate on the current page, while complete generated downloads remain available for
dataset-wide analysis. This keeps every signal browsable without allowing one HTML page or
browser document to grow with the full history.

The archive adapter rejects unexpected members, unsafe paths, missing documented columns,
oversized downloads, expanded archives, tables, cells, selected sets, per-record descriptions,
per-record events, and excessive validation failures. It reads rows as streams and retains only
matched organisation records. Durable state hashes are verified before rebuilding or publishing.
Every generated official-record URL must match the exact Australian Trade Mark Search host and
path. The weekly update checks only three deterministic record numbers with sequential `HEAD` requests,
does not follow redirects, and does not download record pages. Confirmed `404` or `410` responses
stop publication, while access controls and transient failures are reported as indeterminate.
Addresses, personal contact details, agent records, and
private-person applicants are not published. A high-confidence privacy scan checks every
retained source text field and change value for contact, business-identifier, phone-number, and
street-address markers. Manual runs
can audit without writing state or fail on any match. Scheduled runs quarantine a bounded set
and stop when matches exceed both three records and one percent of selected records. Validation
and privacy reports contain error codes and marker types rather than rejected source values.

## Signal model

The score is a transparent sort aid with four independently displayed components:

| Reason | Points | Condition |
| --- | ---: | --- |
| New class | 25 | First observed Nice class for an applicant with prior filings |
| Filing cluster | 25 | At least three related marks filed within seven days |
| Long filing gap | 20 | At least 365 days since the previous observed filing |
| Novel tokens | 20 | Meaningful mark-name tokens not seen in prior filings |

The maximum score is 90. It is not a probability, risk score, prediction, or assessment of
conduct. Character trigram cosine similarity is recorded under algorithm version `1.0.0`.
Similarity can group filings for one resolved applicant but can never merge applicants.

## Local development

Requirements: Python 3.12+, Node.js 24.15 LTS or Node.js 26+, and npm 12.0.1+.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/marksignal ingest-fixture tests/fixtures/synthetic-trademarks.json

cd site
npm ci
npm run dev
```

Run the checks:

```bash
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/pytest --cov=marksignal --cov-report=term-missing
.venv/bin/pip-audit
cd site && npm test && npm run check && npm run build && npm run check:security && npm audit
```

Process a downloaded official archive:

```bash
.venv/bin/marksignal audit-iprapid /path/to/iprapid.zip

.venv/bin/marksignal \
  --data-root /path/to/restricted-state \
  ingest-iprapid /path/to/iprapid.zip --privacy-mode strict
```

Use `strict` for the first reviewed production run. Scheduled updates use `quarantine`, which
withholds a bounded set of affected records and stops the complete update if the match volume
is unusual.

The current archive is about 1.3 GB compressed. It is intentionally not committed. The
scheduled workflow downloads it into temporary runner storage, writes durable selected state
to restricted deployment storage, and supports manual dispatch. Production site assets are
generated inside the deployment runner and are not committed publicly.

## Entity resolution boundary

Applicant matching is conservative by design:

1. Normalise Unicode, punctuation, whitespace, and limited legal-form variants.
2. Match only exact aliases declared in `watchlists/production/*.yml`.
3. Keep legal suffixes such as `PTY LTD` and `LTD` rather than stripping them.
4. Expose fuzzy candidates for review only.
5. Fail closed when one alias maps to multiple organisations.

No applicant is merged solely because two names look similar.

## Repository layout

```text
src/marksignal/          source models, resolver, signals, changes, and publication
tests/                   behavioural tests and fictional fixtures
watchlists/              separated production and demonstration aliases
data/state/              current selected trade mark state
data/events/             immutable changes and generated filing signals
data/manifests/          source, quality, schema, and checksum evidence
site/                    static Astro dashboard and generated downloads
docs/                    architecture, methodology, ethics, and data definitions
.github/workflows/       CI, weekly updates, and Pages deployment
```

The paths under `data/` and the generated site files committed here contain only the fictional
demonstration dataset. Production state uses the same layout in a restricted checkout.
The only production record written publicly is `site/src/data/update-status.json`, which
contains counts, including the number of quarantined records, retrieval timing, and the
corresponding state revision without applicant, mark, application, class, event, or
source-error content.

## Automation and cost

The project uses standard GitHub-hosted Actions and GitHub Pages. It has no production
server, database, account system, paid data service, or request-time processing. Expected
recurring hosting cost is **$0** for a public repository using the included configuration.

Production history requires a restricted versioned state store plus separate repository-scoped
read and write deploy keys. Their state-store identifier is held in Actions secrets rather than
public files. Without that configuration, Pages safely deploys the fictional dataset. See
[restricted state setup](docs/restricted-state-setup.md).

## Primary sources and attribution

- [IP RAPID dataset](https://data.gov.au/data/dataset/iprapid)
- [IP RAPID data dictionary](https://data.gov.au/data/dataset/423000b8-5735-4447-bcb9-792644bcd7ea/resource/f4750acd-decc-4b7b-99c9-4ed1c3c43441/download/ip-rapid-data-dictionary.pdf)
- [Australian Trade Mark Search](https://search.ipaustralia.gov.au/trademarks/)
- [IP Australia API information](https://www.ipaustralia.gov.au/tools-and-research/professional-resources/apis)

IP RAPID is published by IP Australia under the
[Creative Commons Attribution 4.0 International licence](https://creativecommons.org/licenses/by/4.0/).
MarkSignal selects, minimises, normalises, and analyses that material. The source-derived
records remain under their source licence. The [MIT Licence](LICENSE) applies to original
software and project documentation only. See [NOTICE](NOTICE) and the
[legal and licensing notes](docs/legal-and-licensing.md) for the full boundary.
