# Dependency policy

MarkSignal AU keeps the production surface small and uses lockfiles for the static site.

## Python

Runtime dependencies are limited to validated models, YAML watchlists, and Parquet output.
Development dependencies provide linting, strict typing, tests, coverage, and vulnerability
auditing. Versions use compatible upper bounds and are reviewed through Dependabot.

## JavaScript

Astro generates static pages. There is no client framework and no request-time server. The
package lock is committed, install scripts are explicitly controlled in `package.json`, and
CI uses `npm ci` plus a high-severity audit.

## GitHub Actions

Actions are pinned to immutable commit hashes. Dependabot checks those pins weekly. Workflow
permissions are declared per workflow and the data update serialises concurrent refreshes.
One repository-scoped deploy key gives the workflows access only to the restricted state
store. Its identifier is supplied through a masked Actions secret.

## Review expectations

A dependency change should pass the full Python and site suites, preserve the static build,
and avoid adding an external production service. A new runtime dependency needs a clear
maintenance, security, and zero-cost justification.
