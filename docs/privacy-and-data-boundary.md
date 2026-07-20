# Privacy and data boundary

## Short answer

MarkSignal AU does not require secrets, private filings, user accounts, analyst notes, or
private-person applicant records in the public repository. The public repository contains
source code, curated organisation watchlists, fictional fixtures, fictional generated data,
and non-identifying production update counts.

Real selected records originate in a public government dataset. They can still contain
unnecessary personal or contact information, so public-source status is not treated as an
automatic publication approval.

## Production data flow

1. GitHub Actions downloads the full official archive into temporary runner storage.
2. The adapter retains only current organisation applicants that exactly match a curated
   alias.
3. Addresses, contacts, agents, opponents, and private-person applicants are never selected.
4. A privacy scan checks every retained source text field and before-and-after change value for
   high-confidence contact, identifier, phone-number, or street-address markers. Audit mode
   writes nothing. Strict mode stops on any match.
   Scheduled quarantine mode withholds matching records and stops the complete update when
   matches exceed both three records and one percent of selected records.
5. A restricted privacy report records aggregate counts plus affected application numbers, source
   hashes, field names, and marker types without copying matched source values.
6. Durable selected state, observations, signals, and manifests are committed to restricted
   versioned storage.
7. Public site files are generated in the deployment runner and uploaded as a Pages artifact.
8. The public code repository receives only counts, including the number of quarantined
   records, retrieval timing, and a state revision pointer.

The deployed site remains public. Its visible filings and downloads can be copied or indexed.
The split prevents unnecessary permanent public Git history; it is not access control for the
published research output.

## Data that remains public

- public organisation watchlist names and aliases
- selected public trade mark application numbers
- public mark wording, filing dates, status, current Nice classes, and relevant events
- deterministic signal reasons and scores
- official record links and selected-record hashes

The first item is committed in the public repository. The remaining items appear only in the
production deployment artifact and the restricted state store.

## Data that is excluded

- private-person applicants
- addresses, postcodes, phone numbers, email addresses, and agent details
- source rows for unmatched organisations
- selected records quarantined by the high-confidence privacy scan, including their observations
- the full IP RAPID archive
- workflow credentials and deploy keys
- analyst notes, accounts, user searches, and behavioural tracking
- rejected source values in validation reports

## Alternatives considered

| Model | Privacy and security | Trade-off |
| --- | --- | --- |
| Public Git history | Simple, but every selected version persists in clones and forks | Not used for production state |
| Restricted state plus public artifact | Limits Git-history persistence while preserving a shared scheduled dashboard | Chosen; deployed findings remain public |
| Browser-local state | Keeps each researcher's watchlist and notes on their device | No shared scheduled history or consistent public feed |
| Demonstration-only site | Publishes no real findings | Safest option when restricted state is not configured |
| Access-controlled static host | Can restrict the deployed findings as well as durable state | Adds hosting and identity management outside the zero-cost Pages design |

GitHub caches, workflow logs, release assets, and large-file storage are not treated as privacy
controls. They are not substitutes for restricted storage or an access-controlled host.

## Operational checks

- Use separate repository-scoped read and write deploy keys. Rotate either key if exposure is
  suspected.
- Enable private vulnerability reporting before production publication.
- Review watchlist aliases as public research scope, not private analyst configuration.
- Run the first production archive in audit mode, inspect only aggregate counts, then use a
  strict run before enabling the scheduled quarantine policy.
- Treat a privacy threshold failure as a source or parser change requiring manual review,
  never as text to republish.
- Review restricted quarantine entries by application number and source field without placing the
  matched text in issues, logs, or the public repository.
- Review source licence, schema, and publication terms when the upstream source changes.
- Remove a record from the next deployment when continued publication is no longer necessary.
