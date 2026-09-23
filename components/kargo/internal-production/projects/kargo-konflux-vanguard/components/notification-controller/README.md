# Notification Controller promotions

The unchanged image Warehouse selects 40-character SHA tags from
`quay.io/konflux-ci/notification-service`. Ring 0 remains a compose-output
passthrough: it does not deploy or run CI.

Rings 1–4 clone deployment Git main, prepare the selected image tag and matching
remote Kustomize commit, then use the shared publication, exact-head GitHub CI,
merge and Argo readiness tasks. Ring 1 merges automatically; production requires
manual PR merge. Prow is explicitly skipped. Preparation
checks the Freight origin, ring, SHA tag and expected configuration entries before
mutation, and publishes its result only after success. PR descriptions show the
previous and proposed Git configuration.

The deployment path is `components/notification-controller/rings/ring-1/base`,
correcting the old task's obsolete `notification-controller-rd` path. The rendered
staging ApplicationSet also uses `notification-controller` as its Application
prefix. At the checked infra-deployments revision `5012cf12f`,
`stone-stg-rh01` and `stone-stage-p01` consume this base. The additional mapped
`lightwell-dev` overlay is empty and is not a deployment readiness target.

Readiness requires every configured Application in the ring to be healthy and synchronized to
the confirmed revision, including no-op promotions. Freight metadata `noOpRing1`
remains `yes` or `no`. The existing two-cluster Kanary verification is unchanged.

SHA tags must remain immutable, and the image tag must identify an available
notification-service Git commit. Remote Kustomize fetching depends on GitHub
availability; pinning the top-level ref does not freeze any transitive mutable
dependencies. Main supplies ring-specific configuration, so the Freight pins the
image and remote source, not the entire deployment repository. Prow is not a
notification-specific validation gate. Exact-revision readiness can time out if
main advances before Argo observes the accepted revision.

See the [shared workflow guide](../../../../kargo-shared-promotion-tasks/README.md)
for branch ownership, merge and CI limitations.

## Production rings

| Ring | Targets | Required soak in previous ring |
|---|---|---|
| 2 | `kflux-lw-p01`, `kflux-fedora-01`, `kflux-ocp-p01`, `kflux-osp-p01`, `kflux-prd-rh03`, `kflux-rhel-p01`, `stone-prod-p01` | 48h |
| 3 | `stone-prd-rh01`, `stone-prod-p02` | 48h |
| 4 | `kflux-prd-rh02` | 72h |

These gates follow the existing Vanguard proxy stages. Freight must satisfy Kargo's
soak eligibility in the previous Stage; time since image publication alone does
not qualify it. Frequent replacement of current Freight can delay eligibility.

Production stages use the production shard and Argo CD reader token. Automatic
promotion opens proposals; a reviewer must merge each production PR. Argo CD
auto-sync is enabled upstream, and readiness checks every target after merge.
Staging keeps its two-cluster Kanary verification; production uses Argo CD
readiness without adding a new Kanary policy.

The preparation task updates only the image tag and matching remote manifest
ref. SNS secrets, region/filter patches and production memory settings remain
ring-specific. The Warehouse continues to track only the image: local configuration
changes in infra-deployments are not independently discovered as Freight.
