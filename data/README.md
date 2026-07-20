# Public data boundary

The files committed under this directory contain only the fictional demonstration dataset.
They exercise the full state, event, manifest, Parquet, and site generation paths without
creating real findings about an organisation.

Production durable state uses the same layout in a separate restricted state store:

- `state/trademarks.json` and `state/trademarks.parquet` hold current selected records.
- `events/changes.json` holds immutable first-observed and material-change events.
- `events/signals.json` holds the current versioned signal calculations.
- `manifests/source-manifest.json` records source, schema, quality, and output checksums.
- `manifests/privacy-report.json` records aggregate coverage and bounded restricted quarantine
  metadata without matched source values.

The full IP RAPID archive belongs in temporary storage and must not be committed. Generated
records exclude addresses, personal contact details, agents, and private-person applicants.
Selected text also passes a high-confidence contact, identifier, phone-number, and
street-address scan before publication. Matching records are withheld in scheduled runs, and
an unusual volume stops the complete update.

Production JSON, CSV, Parquet, RSS, and evidence files are generated in the deployment runner.
They are included in the public static site but do not enter public Git history. The public
repository retains only counts, retrieval timing, and a state revision pointer after a
production update.
