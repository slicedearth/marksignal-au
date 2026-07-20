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
- Archive processing is bounded and rejects unsafe paths, unexpected members, excessive
  expanded size, oversized cells, missing required columns, and excessive validation errors.
- Site templates escape source text. CSV output prefixes formula-triggering values.
- Scheduled workflows use only the permissions required by their jobs.
- The project deliberately excludes private-person applicants and unnecessary contact data.
- A high-confidence privacy scan detects selected text containing email, business-identifier,
  Australian phone-number, or street-address markers. Strict runs block any match. Scheduled
  runs quarantine a bounded set and block an unusual volume.
- Validation records use bounded error codes and do not retain rejected source values.
- Restricted privacy reports retain only record identifiers, source hashes, affected field names,
  and marker types. They do not copy the matched source text.
- Durable production state and manifests stay in restricted versioned storage. Public Git
  history retains only fictional records and non-identifying update counts.

The application is an informational research tool. It does not provide legal advice and
does not determine infringement, ownership, commercial intent, or misconduct.

The restricted-state deploy key must be unique to this project, stored only as the
`RESTRICTED_STATE_DEPLOY_KEY` Actions secret, and granted access only to the restricted state
store. Its identifier is stored as `RESTRICTED_STATE_REPOSITORY`, not in public files. The key
must not be reused as a personal key or broader account credential. Public
site artifacts contain source-derived findings by design, so the storage split limits Git
history rather than making deployed findings confidential.

GitHub Pages controls response headers. The project supplies a restrictive content policy
and referrer policy in the static document, but header-level enforcement would require a
different static host.
