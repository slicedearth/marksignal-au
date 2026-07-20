# ADR 0002: Resolve only exact curated aliases

Status: accepted

## Context

Applicant names vary in punctuation and legal-form spelling. Incorrectly merging two legal
entities would contaminate timelines, classes, and every downstream signal.

## Decision

Normalise limited formatting differences, retain legal suffixes, and resolve only exact
aliases declared in version-controlled watchlists. Use similarity only to produce candidates
for human review. Reject aliases that map to more than one organisation.

## Consequences

Precision is favoured over recall. Unlisted subsidiaries and spelling variants can be
missed, but every accepted match is reviewable and deterministic.

