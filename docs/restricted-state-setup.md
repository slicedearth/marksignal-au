# Restricted state setup

The public repository deploys its fictional demonstration dataset without any secret.
Production history uses a separate access-controlled state store so selected filings,
immutable observations, manifests, and evidence do not accumulate in public Git history.

## Required state store

Create a restricted Git repository with a default branch and a small README. The scheduled
workflow creates and maintains its `data/` directory. Keep its identifier out of public files.

## Repository-scoped deploy key

1. Generate a dedicated SSH key pair for MarkSignal AU.
2. Add the public key to the restricted state repository as a deploy key with write access.
3. Add the private key to the public repository Actions secrets as
   `RESTRICTED_STATE_DEPLOY_KEY`.
4. Add the state repository's `owner/name` identifier as the masked Actions secret
   `RESTRICTED_STATE_REPOSITORY`.
5. Do not reuse a personal SSH key or a key with access to another repository.

The public Pages workflow uses the same scoped key for read-only checkout during a build.
GitHub holds the secret; it is never added to site files or workflow output.

## First production run

Run the `Update trade mark data` workflow manually with `audit`. It downloads the official
archive into runner temporary storage, reports aggregate privacy-match coverage, and writes no
state. Review that count, then run the workflow with `strict`. Strict mode stops on any match;
a successful run writes durable selected state to restricted storage, verifies an isolated
production build, and commits only non-identifying counts and a state revision pointer to the
public repository.

Scheduled runs use `quarantine`. Matching records are withheld from the current public build
and restricted selected state. The complete update stops if matches exceed both three records
and one percent of selected records. The restricted privacy report contains application numbers,
source hashes, affected fields, and marker types, but never the matched source text.

A later public-repository push rebuilds from restricted state when the secrets are available. If
the secret is not configured, Pages deliberately falls back to the fictional demonstration
dataset.

## Public boundary

The deployed production site remains public. Its filing pages and downloads can be copied by
visitors and search engines. Restricted storage reduces unnecessary Git-history
persistence and protects operational manifests; it does not make published findings private.

If the deployed findings must also be restricted, do not use GitHub Pages. Use an access
layer or keep the project in demonstration-only mode.
