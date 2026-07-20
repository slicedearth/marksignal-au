# ADR 0003: Use displayed deterministic signal reasons

Status: accepted

## Context

A single opaque importance rating would hide the assumptions behind a result and encourage
unsupported interpretations of corporate intent.

## Decision

Publish four versioned reason types with fixed points, plain-language explanations, and
machine-readable evidence. Sum those points only as a feed-ordering aid. Keep source facts
and calculated observations visibly separate.

## Consequences

Researchers can reproduce, challenge, or ignore each component. Rule changes require a new
algorithm version and regression tests. The score must never be described as probability,
risk, misconduct, or a launch prediction.

