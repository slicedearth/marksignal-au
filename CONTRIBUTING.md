# Contributing to MarkSignal AU

Contributions that improve source accuracy, reproducibility, accessibility, or clearly
documented watchlists are welcome.

## Before opening a change

1. Open an issue for source-schema changes, new signal types, or entity merges.
2. Use fictional organisations and trade marks in tests and screenshots.
3. Keep applicant aliases exact and reviewable. Similar names are not sufficient evidence
   that two applicants are the same organisation.
4. Do not add addresses, personal email addresses, agent details, or private-person records.
5. Keep every signal deterministic and include the displayed evidence behind it.

## Local checks

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/pytest --cov=marksignal --cov-report=term-missing
.venv/bin/pip-audit

cd site
npm ci
npm run check
npm audit --audit-level=high
npm run build
```

Run `marksignal validate-watchlists` after changing YAML files. Browser-check the home,
applicant, trade mark, methodology, and data pages at desktop and mobile widths when a
change affects the site.

## Watchlist changes

A watchlist pull request should explain why the organisation is in scope and link to a
reliable source for every alias. An alias should be a documented name variant, not a fuzzy
guess. Keep one stable organisation ID when the same organisation appears in more than one
category.

## Reporting corrections

Use a GitHub issue to report a wrong match, missing attribution, calculation problem, or
outdated record. Include the trade mark number and the relevant primary-record link. Do not
include private contact details in the report.

