# Konflux Kite Kargo project

`kargo-konflux-kite` promotes `infra-deployments/components/konflux-kite` through
Rings 0–4 using the shared publish, CI, merge and Argo readiness tasks.

## Release inputs

| Subscription | Selection | Promotion target |
|---|---|---|
| `infra-deployments` Git | Latest `main` commit changing `components/konflux-kite/base` | Immutable ring `base/base-snapshot` |
| `quay.io/konflux-ci/kite-prod` | `NewestBuild`, full 40-character lowercase SHA tags | Kite API container |
| `quay.io/konflux-ci/kite-init` | `NewestBuild`, full 40-character lowercase SHA tags | Database migration init container |

Both images are built from [konflux-ci/kite](https://github.com/konflux-ci/kite).
The push pipelines build them separately for each `main` push. Published tag sets
are not identical, so preparation requires both selected image tags to be the
same full source SHA. A mismatch fails before any checkout edits or PR creation;
wait for a matching release pair, or select Freight containing both matching
artifacts. Kargo's independent `NewestBuild` discovery does not itself correlate
these repositories. Do not bypass the pair check to advance an incomplete build.

Preparation writes explicit `name`, `newName` and `newTag` entries for both
images. It copies only the shared base from the selected immutable Git Freight.
Ring-local database configuration, ExternalSecret paths, certificates, Routes,
and cluster overrides remain in place. Development configuration is never
copied from Ring 0 into another ring. This prevents carrying development database
and authorization settings into staging or production.

## Promotion and verification

Every ring enables automatic promotion initiation and automatic PR merging after
its required CI checks. There are no `requiredSoakTime` settings. Ring 0 requires
`^ci/prow/konflux-ring-deployments-conformance-tests$` and remains CI-only.
Rings 1–4 skip Prow, retain the other shared CI gates, and verify Argo readiness
at the merged revision before starting Kanary verification.

Each Kanary analysis uses `container-single-arch`, with a 40-minute initial delay,
40-minute interval, 36 measurements and seven-failure limit: approximately 24
hours per promotion. Subsequent rings source verified Freight from the preceding
ring. These platform Kanary signals are not a Kite-specific functional test.

| Ring | Source | Argo readiness clusters | Kanary clusters |
|---|---|---|---|
| 0 | Warehouse directly | None; CI only | None |
| 1 | Ring 0 | `kflux-hub-stg-01`, `kflux-stg-p02`, `stone-stage-p01`, `stone-stg-rh01` | `stone-stage-p01`, `stone-stg-rh01` (2) |
| 2 | Ring 1 | `kflux-fedora-01`, `kflux-ocp-p01`, `kflux-osp-p01`, `kflux-prd-rh03`, `kflux-rhel-p01`, `stone-prod-p01` | Same six clusters (6) |
| 3 | Ring 2 | `stone-prd-rh01`, `stone-prod-p02` | Same two clusters (2) |
| 4 | Ring 3 | `kflux-prd-rh02` | `kflux-prd-rh02` (1) |

Cluster assignments were checked against infra-deployments commit
[`3910309c017d73ee54ab95294ed1a6d622dc6af7`](https://github.com/redhat-appstudio/infra-deployments/tree/3910309c017d73ee54ab95294ed1a6d622dc6af7/components/konflux-kite),
including rendered staging and production ApplicationSets with their shared
cluster-list patches. This is configured inventory, not a live deployment check.

- `lightwell-dev` is explicitly excluded by the Kite staging ApplicationSet and
  is not a verification target.
- `kflux-lw-p01` is a deployed Ring 2 target in that inventory, but is deliberately
  excluded from both Kargo verification lists per the existing rollout requirement.
  Its overlay receives the shared Ring 2 update; its health does not gate onward
  promotion. This is an explicit coverage gap, not an assertion that Kite is absent.
- `kflux-hub-stg-01` and `kflux-stg-p02` have Kite overlays but are not listed in
  the [Kanary workload ApplicationSet](https://github.com/redhat-appstudio/infra-deployments/blob/3910309c017d73ee54ab95294ed1a6d622dc6af7/argo-cd-apps/base/member/infra-deployments/monitoring-workload-kanary/monitoring-workload-kanary.yaml).
  They are covered by Argo readiness only. Adding nonexistent Kanary targets would
  block verification on missing measurements.

## Ownership and access

The `konflux-ui` group is taken from Kite's infra-deployments component-maintainer
binding. It maps to the project's promoter service account and built-in
`kargo-promoter` Role. It is not bound to project-admin, Secret-read permissions,
or the extra mutation Role used by `kargo-manager`.

Component reviewers mirror `components/konflux-kite/OWNERS` at the inventory
commit. They may approve documentation; platform owners remain required for
executable promotion manifests, project policy and access changes. Shared
Git/verification credentials follow the existing platform setup. The project
includes the Argo application-reader account and the shard and promotion-cleaner
bindings needed by the shared workflow.

## Validation and rollback

Render this project, the project aggregate and all four root environment overlays.
Exercise preparation against an immutable infra-deployments snapshot: all ring
and cluster overlays must render both selected image tags, and files outside the
shared snapshots and two image overrides must remain unchanged. Verify mismatched
or absent image artifacts fail before preparation can return `prepared: yes`.

Live GitHub credentials, Prow, Argo and Kanary must be confirmed during the first
promotion. No live cluster access was available during onboarding. Reverting
this onboarding PR removes its GitOps configuration; it does not roll back
already-merged deployment PRs or database migrations. The Project uses
`kargo.akuity.io/keep-namespace: "true"` to retain its history on removal.
