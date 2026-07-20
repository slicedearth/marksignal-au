# Security policy

## Supported version

Security fixes are applied to the current default branch.

## Reporting a vulnerability

Use GitHub private vulnerability reporting when it is enabled for this repository. If it is
not available, open an issue asking for a private contact channel without publishing exploit
details or personal information.

Include the affected component, reproduction conditions, expected impact, and any suggested
mitigation. Reports concerning unsafe archive handling, formula injection, script injection,
dependency compromise, workflow permissions, or accidental personal-data publication are
particularly useful.

## Security boundaries

- The public site is static and has no accounts, cookies, database, or request-time API.
- Source archives, CSV cells, watchlists, URLs, and displayed strings are untrusted input.
- Archive processing is bounded and rejects unsafe paths, unexpected members, excessive download
  or expanded size, oversized tables, cells, selected sets, per-record descriptions, per-record
  events, aggregate selected child rows, duplicate columns, missing required columns, and
  excessive validation errors. Archive structure is checked before the full source file is hashed.
- Site templates escape source text. CSV output prefixes formula-triggering values. Browser code
  and styles are same-origin files, and the build rejects inline script, inline style, or an
  `unsafe-inline` content-policy exception.
- Enhanced pagination accepts only the site root and numeric signal-page paths on the current
  origin. It rejects redirects, non-HTML responses, mismatched page metadata, and responses over
  two megabytes. Scripts are removed from the parsed replacement before the main region is
  imported. The previous page remains visible until a complete replacement has been validated.
- The content policy permits browser connections only to the same origin for enhanced pagination.
  There are no third-party browser requests, analytics requests, credentials, or request-time
  data APIs.
- Static signal pages contain at most 50 result cards. Page-local filtering and export avoid an
  unbounded browser document while complete downloads remain separately available.
- Every generated official-record URL is validated against one exact HTTPS host and path pattern.
  A weekly availability sample is capped at three sequential `HEAD` requests, does not follow
  redirects, and never reads response bodies. Only confirmed missing responses block publication.
- Scheduled audit and data-processing jobs use read-only public-repository permissions. A
  separate publisher job receives public write permission only after verification.
- The project deliberately excludes private-person applicants and unnecessary contact data.
- A high-confidence privacy scan checks every retained source text field and change value for
  email, business-identifier, Australian phone-number, or street-address markers. Strict runs
  block any match. Scheduled runs quarantine a bounded set and block an unusual volume.
- Validation records use bounded error codes and do not retain rejected source values.
- Restricted privacy reports retain only record identifiers, source hashes, affected field names,
  and marker types. They do not copy the matched source text.
- Durable production state and manifests stay in restricted versioned storage. Public Git
  history retains only fictional records and non-identifying update counts.
- Manifest hashes for state, signals, and changes are verified before rebuilds or status
  publication. Durable JSON and generated-publication volumes also have explicit size limits.

The application is an informational research tool. It does not provide legal advice and
does not determine infringement, ownership, commercial intent, or misconduct.

Restricted-state deploy keys must be unique to this project and granted access only to the
restricted state store. `RESTRICTED_STATE_READ_KEY` is read-only and is used for data processing
and Pages generation. `RESTRICTED_STATE_DEPLOY_KEY` has write access and is introduced only after
the generated state passes verification. The state identifier is stored as
`RESTRICTED_STATE_REPOSITORY`, not in public files. Neither key may be reused as a personal key
or broader account credential. Public
site artifacts contain source-derived findings by design, so the storage split limits Git
history rather than making deployed findings confidential.

GitHub Pages controls response headers. The project supplies a restrictive content policy
and referrer policy in the static document, but header-level enforcement would require a
different static host.
