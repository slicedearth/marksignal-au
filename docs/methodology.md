# Methodology

## Research question

MarkSignal AU asks whether a watched organisation has a public filing pattern worth closer
review. It does not infer why the filing was made or whether a product will launch.

## Selection

Organisations are deliberately curated in public `watchlists/*.yml`. Each entry has a stable ID,
display name, category, and explicit aliases. The pipeline considers current applicant rows
whose party type is `Organisation`. It excludes individuals, agents, addresses, and contact
details.

Every retained source text field, including status, mark type, and event wording, passes a
high-confidence scan for email addresses, labelled ABNs or ACNs, Australian phone numbers, and
street addresses. Retained before-and-after change values are checked again before publication.
Audit mode reports aggregate matches
without writing state. Strict mode stops on any match. Scheduled quarantine mode withholds
matching records and stops the complete update when matches exceed both three records and one
percent of selected records. Error and privacy records retain bounded codes, identifiers, field
names, marker types, and source hashes without copying rejected source values.

## Normalisation and identity

Applicant names are Unicode-normalised, uppercased, stripped of punctuation differences,
and standardised for limited forms such as `PROPRIETARY LIMITED`, `PTY. LTD.`, and
`LIMITED`. Legal suffixes remain part of the comparison. Only an exact normalised alias can
resolve an applicant.

Character trigram similarity is used for related mark wording and optional alias review. It
never merges applicants. Ambiguous aliases stop watchlist loading, and a source application
that maps to more than one watched organisation is skipped with a validation record.

## Signal reasons

Signals are calculated from filing-date order for one resolved applicant:

| Reason | Points | Rule |
| --- | ---: | --- |
| New class | 25 | A current Nice class has not appeared in an earlier observed filing |
| Filing cluster | 25 | The mark has at least two related filings within seven days |
| Long filing gap | 20 | The preceding observed filing is at least 365 days earlier |
| Novel tokens | 20 | Meaningful mark tokens have not appeared in earlier observed filings |

Related marks require character trigram cosine similarity of at least `0.62`. Common tokens
such as `THE`, `AUSTRALIA`, and `AUSTRALIAN` do not contribute to novelty. The maximum score
is 90. The score is only a transparent ordering aid and is not a probability or risk rating.

The first observed filing for an applicant is historical context and does not receive a
novelty signal because the selected data contains no earlier comparison point.

## Change observations

The pipeline compares source hashes and records first observation, status, current Nice
classes, mark wording, and resolved applicant changes. Each event retains before and after
hashes. Reprocessing identical selected data is idempotent.

An absent record is retained rather than marked withdrawn. Withdrawal or lapse must be
supported by a published status or event, not inferred from one missing snapshot.

## Evidence and corrections

Each filing page separates source facts from calculated signal reasons and links to the
official Australian Trade Mark Search record when one can be constructed. Downloadable
evidence includes the normalised filing, reasons, observed changes, retrieval timestamps,
and source hashes.

Incorrect matches and calculation problems can be reported through GitHub issues. Accepted
corrections should update the watchlist or deterministic rule and include regression tests.

Durable production records and manifests are stored in restricted versioned storage. Public
site files are generated inside a deployment runner and are not committed to public Git
history. This limits unnecessary historical persistence but does not make a filing displayed
by the public site private.

Quarantined records and their existing change observations are removed from incoming and
previously retained state for that build. Generated evidence directories are rebuilt from the
accepted record set. The public dataset reports only the aggregate quarantine count, so a
privacy match cannot leave an older public copy visible after it is detected.

## Limitations

- A filing can be defensive, speculative, abandoned, refused, or unrelated to an active
  commercial plan.
- Watchlists are selective and do not represent all Australian organisations.
- Exact alias matching favours precision and may miss unlisted subsidiaries or name forms.
- Privacy quarantine can temporarily hide a small number of otherwise relevant organisation
  filings until the source text or selection rule is reviewed.
- Filing dates show public record timing, not internal company decision dates.
- Nice classes are broad administrative categories and do not prove market entry.
- Similar wording does not establish common ownership, copying, or infringement.
- The weekly dataset can lag source-system changes.
