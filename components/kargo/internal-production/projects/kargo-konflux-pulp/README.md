# kargo-konflux-pulp

Kargo project for Pulp access controller promotions in
`redhat-appstudio/infra-deployments`. The Project and namespace are both named
`kargo-konflux-pulp`. This configuration is hosted by the production Kargo control
plane; its first deployment target is staging.

## Sources and preparation

The `pulp-access-controller` Warehouse watches the component's `base/` directory
on infra-deployments `main` and the public image repository
`quay.io/redhat-user-workloads/pulp-access-controller-tenant/pulp-access-controller-ca9ff`.
Image discovery selects stable `v1.x.y` tags with SemVer, constrained to
`>=1.3.1 <2.0.0`. This starts at the currently deployed release and excludes
PR builds, signatures, prereleases, and future major versions. Discovery runs
every two hours. The Git revision and image are independently selected sources
in one Freight bundle, not an atomic release from a single source repository.

Preparation clones current deployment `main` and the immutable Git revision
selected by Freight into separate directories. It replaces only the target
ring's `base/base-snapshot` from that immutable checkout, then updates the
controller image in the ring's `base/kustomization.yaml`. Guards reject an
unexpected component, repository, image, ring, or destination layout before
editing. Removed base files are removed from the snapshot. Ring-specific
`pulp-secrets-es.yaml`, other resources, and cluster overlays remain intact.

## Promotion policy

Ring 0 is intentionally empty in infra-deployments, so Ring 1 receives Freight
directly. All four stages enable automatic promotion. Staging PRs merge after
CI passes; production PRs require a human to merge them.

| Ring | Source | Required source soak | Merge | ArgoCD readiness targets |
| --- | --- | --- | --- | --- |
| 1 | Warehouse | None | Automatic after CI | kflux-hub-stg-01, kflux-stg-p02, stone-stage-p01, stone-stg-rh01 |
| 2 | Ring 1 | 48 hours | Manual | kflux-fedora-01, kflux-lw-p01, kflux-ocp-p01, kflux-osp-p01, kflux-prd-rh03, kflux-rhel-p01, stone-prod-p01 |
| 3 | Ring 2 | 48 hours | Manual | stone-prd-rh01, stone-prod-p02 |
| 4 | Ring 3 | 72 hours | Manual | kflux-prd-rh02 |

Each stage uses shared publication, CI, merge, and ArgoCD readiness tasks.
Prow is skipped for ring-only promotion changes, matching the existing Ring 1–4
workflows. Base changes enter through normal infra-deployments review and CI.
Readiness requires the `app.kubernetes.io/part-of: pulp-access-controller`
Application label already present in both deployment ApplicationSets.

Kanary uses the existing representative fleet checks: stone-stg-rh01 and
stone-stage-p01 for Ring 1, stone-prod-p01 and kflux-prd-rh03 for Ring 2,
stone-prd-rh01 for Ring 3, and kflux-prd-rh02 for Ring 4. These are fleet health
checks, not Pulp-specific functional tests. ArgoCD checks cover the listed Pulp cluster overlays, including staging
clusters outside the Kanary sample.

## Access and operations

The project reuses shared Git and Kanary credentials and the replicated staging
ArgoCD reader token. Its production ArgoCD reader uses the existing shared
ClusterRole. Project RBAC follows the maintained domain-project pattern,
including the `konflux-pulp` OIDC group for promoter access and existing
DevProd/infra administration. Confirm that group is supplied by the identity
provider when testing team access. Staging-shard access and promotion-cleaner
registration are included.

After reconciliation, confirm image discovery, credential replication, team
access, and the first Ring 1 promotion. Local rendering cannot prove live
credentials, Kargo execution, or Pulp functionality. An initial Freight may
start staging promotion automatically; production deployment still requires
manual PR merge. Disable the four `autoPromotionEnabled` policies to stop new
automatic promotions and review already-running promotions separately.
