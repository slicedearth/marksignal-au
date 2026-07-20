# Restricted state setup

The public repository deploys its fictional demonstration dataset without any secret.
Production history uses a separate access-controlled state store so selected filings,
immutable observations, manifests, and evidence do not accumulate in public Git history.

## Required state store

Create a restricted Git repository with a default branch and a small README. The scheduled
workflow creates and maintains its `data/` directory. Keep its identifier out of public files.

## Repository-scoped deploy keys

Use two dedicated SSH key pairs that are valid only for the restricted state store:

1. Add the first public key as a read-only deploy key.
2. Store its private key in the public repository secret `RESTRICTED_STATE_READ_KEY`.
3. Add the second public key as a deploy key with write access.
4. Store its private key in the public repository secret `RESTRICTED_STATE_DEPLOY_KEY`.
5. Store the state repository's `owner/name` identifier as the masked secret
   `RESTRICTED_STATE_REPOSITORY`.
6. Do not reuse either key as a personal key or a credential for another repository.

Data-processing and Pages-generation jobs use the read-only key with persisted Git credentials
disabled. Dependencies are installed before state checkout. The update job introduces the write
key only after the selected state, privacy boundary, tests, dependency audits, and isolated site
build have passed. Public status publication happens in a separate job that cannot read the
restricted state or its keys.

## First production run

Run the `Update trade mark data` workflow manually with `audit`. It downloads the official
archive into runner temporary storage, reports aggregate privacy-match coverage, receives no
state credential, and has read-only public-repository permissions. Review that count, then run
the workflow with `strict`. Strict mode stops on any match; a successful run writes durable
selected state to restricted storage, verifies an isolated production build, and commits only
non-identifying counts and a state revision pointer to the public repository.

Scheduled runs use `quarantine`. Matching records are withheld from the current public build
and restricted selected state. The complete update stops if matches exceed both three records
and one percent of selected records. The restricted privacy report contains application numbers,
source hashes, affected fields, and marker types, but never the matched source text.

A later public-repository push rebuilds from restricted state when the read-only secret is
available. If the secret is not configured, Pages deliberately falls back to the fictional
demonstration dataset.

An empty state store is also treated as uninitialized. Pages continues to publish the fictional
demonstration dataset until the first verified data update creates a manifest. Once a manifest
exists, missing or corrupt state fails the deployment instead of silently falling back.

## Public boundary

The deployed production site remains public. Its filing pages and downloads can be copied by
visitors and search engines. Restricted storage reduces unnecessary Git-history persistence and
protects operational manifests; it does not make published findings private.

If the deployed findings must also be restricted, do not use GitHub Pages. Use an access layer
or keep the project in demonstration-only mode.
