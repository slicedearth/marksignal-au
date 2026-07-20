# Threat model

## Scope and assets

This model covers the public source repository, the scheduled ingestion workflow, the
restricted state store, the generated Pages artifact, and visitors downloading or
filtering public evidence.

Protected assets are:

- the restricted state deploy key
- integrity and provenance of selected filing state
- confidentiality of durable production history and manifests
- absence of unnecessary personal or contact data from publication
- availability of a valid static build
- clear separation between source facts and calculated observations

The selected production findings are not confidential once deployed. The public site and its
downloads are intentionally readable without authentication.

## Trust boundaries

- IP RAPID archives and every contained CSV value are untrusted.
- Watchlists are reviewed repository input and can change publication scope.
- The restricted state store is durable operational state, not an authoritative source.
- GitHub Actions can read the scoped deploy key during approved workflows.
- Astro templates receive validated generated data and publish a static artifact.
- External source links leave the project origin and lead to independently operated systems.

## Threats and controls

| Threat | Controls |
| --- | --- |
| ZIP path traversal or archive bomb | No extraction, exact member allowlist, safe-path checks, compressed and expanded size limits, bounded cells |
| Source schema drift | Required-column checks, archive member checks, strict selected models, schema fingerprint, fail-closed publication |
| Script or markup injection | Astro text escaping, no raw HTML rendering, restrictive static content policy |
| Output path traversal | Bounded application-number pattern without path separators, stable generated directories |
| Spreadsheet formula execution | Formula-triggering CSV cells receive a leading apostrophe |
| Unnecessary personal-data publication | Organisation-only exact aliases, field minimisation, contact and address privacy scan, fictional public fixtures |
| Rejected values leaking through diagnostics | Bounded table, row, and error codes without rejected source text |
| Incorrect applicant merge | Exact normalised aliases only, alias collision failure, ambiguous source match skipped, similarity used only for review |
| Forged or unexplained signal | Deterministic versioned rules, complete reason records, source and output hashes, regression tests |
| Corrupt update replacing history | Atomic writes, immutable change IDs, duplicate suppression, missing records do not delete prior state |
| Credential exposure | State identifier and repository-scoped key in Actions secrets, no pull-request trigger on state workflows, no credential in builds, logs, or public status |
| Public Git persistence | Real durable state stays in restricted storage; public Git retains fictional data and aggregate status only |
| Dependency or workflow compromise | Lockfile, pinned workflow actions, weekly updates, Python and npm audits, narrow job permissions |
| Resource exhaustion | Streaming CSV reads, selected-record retention, archive and field bounds, job timeout, serialized updates |
| Referrer leakage | External links use `noreferrer`; the document applies a referrer policy |

## Residual risks

- A deployed finding can be indexed, copied, archived, or redistributed by third parties.
- High-confidence pattern checks can miss unusual personal data or stop on a benign numeric
  mark. A failure requires manual review.
- A valid exact alias can become outdated after a restructure or name transfer.
- IP Australia can correct records after publication, so primary-source verification remains
  necessary.
- Compromise of the public default branch or a repository administrator could alter workflows
  that receive the deploy key.
- GitHub Pages does not let the project set all desired security response headers.
- Availability depends on GitHub and the official dataset host.

## Operational response

Rotate the deploy key after suspected exposure. Pause the scheduled workflow when source
licensing, schema, or publisher identity changes. Remove an unnecessary filing from the next
artifact and document the correction. Use private vulnerability reporting for sensitive
reports rather than placing details in a public issue.
