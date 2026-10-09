# Trust-manager promotions

Trust-manager belongs to the production `kargo-konflux-vanguard` project.
Its Warehouse discovers the public `trust-manager` chart from
`https://charts.jetstack.io` every two hours. The initial `^0.19.0` constraint
allows stable patches of the deployed minor; review this constraint before
adopting another minor. Upstream chart versions may have a `v` prefix.

Each promotion clones infra-deployments `main` and updates only `version` in
`components/trust-manager/rings/<ring>/base/trust-manager-helm-generator.yaml`.
The chart supplies the images. Existing Helm values, namespace, release name,
and cluster overlays remain in infra-deployments. There is no Git subscription
or base snapshot to copy.

## Gates

The stages follow Vanguard's project-controller flow, using the shared publish,
CI, merge, and ArgoCD readiness tasks and the `team/konflux-vanguard` PR label.

| Ring | Source soak | Merge | Verification |
| --- | --- | --- | --- |
| 0 | None | Automatic after CI | GitHub checks and `ci/prow/konflux-ring-deployments-conformance-tests` |
| 1 | None | Automatic after CI | GitHub checks, staging ArgoCD readiness, staging Kanary |
| 2 | 48 hours | Manual PR merge | GitHub checks, production ArgoCD readiness, production Kanary |
| 3 | 48 hours | Manual PR merge | GitHub checks, production ArgoCD readiness, production Kanary |
| 4 | 72 hours | Manual PR merge | GitHub checks, production ArgoCD readiness, production Kanary |

All five stages enable automatic promotion. Production PRs still require manual
merging. Rings 1–4 skip Prow because the conformance job excludes those paths.

ArgoCD readiness checks use:
- Ring 1: stone-stage-p01, stone-stg-rh01.
- Ring 2: kflux-fedora-01, kflux-lw-p01, kflux-ocp-p01, kflux-osp-p01,
  kflux-prd-rh03, kflux-rhel-p01, stone-prod-p01.
- Ring 3: stone-prd-rh01, stone-prod-p02.
- Ring 4: kflux-prd-rh02.

The Ring 1 base also feeds lightwell-dev and kflux-stg-p02; these are not
readiness or Kanary targets in this flow. Lightwell-dev remains excluded from
production Kargo verification, consistent with the other Vanguard components.
Kanary checks cover the same representative clusters as project-controller;
the Stage manifests contain the exact lists.

## Operations

The first discovery can start Ring 0 automatically and may produce a change
from `0.19.0` to the equivalent published `v0.19.0` spelling. No chart is
deployed merely by adding these Kargo resources; deployments follow the
promotion PRs in infra-deployments.

Use the existing shared infra-deployments Git credentials, ArgoCD reader
secrets, and Kanary templates. No Konflux CI source credentials are needed to
discover this public chart. Runtime promotion and application health must be
confirmed after reconciliation.

When changing a ring's cluster membership, update both the corresponding
infra-deployments overlays and this component's readiness/verification lists.
To stop new automatic promotions, disable this component's five
`autoPromotionEnabled` policies; review already-running promotions separately.
