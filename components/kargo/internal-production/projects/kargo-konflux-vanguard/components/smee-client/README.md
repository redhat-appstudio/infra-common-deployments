# smee-client promotions

One Warehouse, `smee-client`, subscribes to the component's base manifests,
gosmee releases (`^0.28.0`), and smee-sidecar SHA tags. Each Freight records a Git
commit and both image versions/digests.

## Why one Warehouse?

Gosmee and the health-check sidecar run in the same Pod and share health-check
files. Treating them and their manifests as one bundle gives us an explicit
combination to promote and roll back. A change to any subscription creates a new
candidate using the selected versions of the other subscriptions; all three
sources do not need to publish simultaneously.

This is not a compatibility resolver. If an image requires a manifest change
that has not arrived yet, a combined Warehouse can still discover an incompatible
candidate. Coordinated releases require an explicit compatibility rule or release
process, and the configured CI/verification gates remain necessary.

## How preparation works

Both rings use two worktrees from the same repository:

- `./src`: current `main`, where the promotion updates its target ring.
- `./freight`: the exact Git commit recorded in the selected Freight.

The preparation task replaces the target ring's `base-snapshot` with
`components/smee-client-rd/base` from `./freight`, then sets both image tags recorded in Freight in
the target ring's outer Kustomization. It emits `prepared: 'yes'` only after
validation, deletion, copying, and image updates succeed.

Ring 1 reconstructs the same Freight bundle rather than copying the current
Ring 0 directory, which might already contain a newer promotion. Gosmee uses its
version tag and smee-sidecar uses its commit-SHA tag. Tags must remain immutable
in their registries to preserve identical image contents across rings. Existing
ring-specific patches and overlays remain in the target checkout; the bundle
covers base manifests and images, not every repository file.

The publisher's base commit is still the `./src` commit, not the Freight commit.
This allows the PR to update current `main` without rolling back unrelated work.
PR descriptions include the manifest commit, image tags, and digests.

## Ring policies

| Ring | Freight source | Merge | Prow | Deployment verification |
|---|---|---|---|---|
| 0 | Direct from `smee-client` | Automatic after CI | `ci/prow/appstudio-operator-overlay-e2e-tests` required | Git/CI completion only |
| 1 | Through Ring 0 | Automatic after CI | Explicitly skipped | `smee-client-stone-stage-p01`, then existing Kanary verification |

The staging ApplicationSet currently has automated sync disabled. A manual or
external Argo CD sync must occur for readiness to succeed. Readiness requires
the exact confirmed revision, so a newer `main` revision can cause a timeout.

PR labels remain `ring-0`/`ring-1`, `automated-promotion`, and
`component/smee-client`. The Application prefix is `smee-client`; the repository
directory is `smee-client-rd`. Preparation receives that repository-relative
location as `componentPath: components/smee-client-rd`; the shared workflow
uses `component` from the Freight origin for labels and Application names.

## Existing installations

This PR replaces the previous three Warehouse definitions. Existing Freight from
`smee-client-manifest-wh`, `smee-client-gosmee-wh`, or `smee-client-sidecar-wh` is
not a complete bundle and is not eligible for the updated Stages. Let the new
Warehouse discover a complete Freight, then promote it through Ring 0. If the
older PR configuration was deployed manually, finish or explicitly handle its
in-flight Promotions before reconciling this change; existing Promotions retain
their captured step definitions. No live migration is performed by this PR.
