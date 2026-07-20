# Data dictionary

## Published trade mark state

| Field | Meaning |
| --- | --- |
| `trademark_number` | IP Australia application number used as the record key |
| `applicant_id` | Stable watchlist identifier after exact alias resolution |
| `applicant_name` | Curated display name for the watched organisation |
| `observed_applicant_name` | Organisation name present in the selected source row |
| `mark_text` | Published word-mark phrase, or published image words when no phrase exists |
| `mark_types` | Description types observed for the application |
| `filing_date` | Source application date, when present |
| `priority_date` | Source priority date, when present |
| `current_status` | Current source status at retrieval time |
| `classes` | Current Nice classification numbers from 1 to 45 |
| `events` | Published application events, including standing state and available dates |
| `source_hash` | SHA-256 of the selected normalised source payload |
| `official_record_url` | Primary-record link in Australian Trade Mark Search |
| `first_seen_at` | First accepted observation time in this dataset |
| `last_seen_at` | Most recent accepted material observation time |
| `is_demo` | Whether the record is part of the fictional starter dataset |

## Filing signals

| Field | Meaning |
| --- | --- |
| `signal_id` | Stable SHA-256 identifier for the filing, algorithm version, and reasons |
| `trademark_number` | Filing receiving the signal |
| `applicant_id` | Resolved watched organisation |
| `detected_at` | Accepted observation time for the selected record |
| `score` | Sum of displayed reason points, from 0 to 90 |
| `maximum_score` | Published maximum score, currently 90 |
| `algorithm_version` | Rule and threshold version, currently `1.0.0` |
| `reasons` | Complete list of typed explanations, points, and evidence values |

Signal reason types are `new_class`, `filing_cluster`, `long_filing_gap`, and
`novel_tokens`.

## Observed changes

| Field | Meaning |
| --- | --- |
| `change_id` | Stable SHA-256 identifier for the complete difference |
| `change_type` | First observation or a material field change |
| `old_value` | Previous normalised value, when one exists |
| `new_value` | Incoming normalised value |
| `before_source_hash` | Selected record hash before the difference |
| `after_source_hash` | Selected record hash after the difference |
| `detected_at` | Time the incoming snapshot was accepted |

## Source manifest

The restricted manifest records parser and signal versions, retrieval time, publisher, licence,
download hash, source schema fingerprint, rows scanned by table, selected record count,
signal count, appended change count, privacy-quarantine count and marker counts, validation
failures, and output hashes.

Validation failures are stored as table name, row number, and a bounded error code. Rejected
source values are not retained in the manifest.

`data/manifests/privacy-report.json` remains restricted. It records aggregate coverage and, for
each quarantined record, the application number, source hash, affected field names, and marker
types. It never copies the matched source value.

## Public update status

The public repository may contain `site/src/data/update-status.json`. It includes retrieval
time, publisher, aggregate rows scanned, watchlist count, matched filing count, signal count,
privacy-quarantine count, validation-failure count, and the corresponding state revision. It
contains no applicant, mark, application, class, event, description, privacy marker, or
rejected source value.

## Source table mapping

| IP RAPID table | Selected use |
| --- | --- |
| `party_activity.csv` | Current organisation applicants and their published names |
| `application.csv` | Application number, subtype, status, and key dates |
| `application_description.csv` | Word-mark phrases, image words, and observed mark types |
| `application_classification.csv` | Current Nice classes |
| `application_events.csv` | Event type, category, dates, and standing state |
| `application_links.csv` | Schema-presence check only in version 0.1.0 |

Source columns outside this mapping are not published or inferred.
