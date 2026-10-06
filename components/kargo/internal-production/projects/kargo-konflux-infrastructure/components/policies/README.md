# Policies promotions

Policies is a manifest-based Konflux Kyverno policy component, not a controller
image. One Warehouse, `policies`, records one Git revision from
`infra-deployments/components/policies/base`. Each Freight carries that revision
through the ring sequence; the policy manifests are copied from the immutable
Freight checkout into each ring's `base/base-snapshot`.

## Rings

| Ring | Environment | Merge policy | Soak | Argo CD readiness |
|---|---|---|---|---|
| 0 | development | Automatic after GitHub checks and Prow | — | No fixed development target list |
| 1 | staging | Automatic after GitHub checks | — | `lightwell-dev`, `stone-stage-p01`, `stone-stg-rh01` |
| 2 | production | Manual | — | `kflux-fedora-01`, `kflux-lw-p01`, `kflux-ocp-p01`, `kflux-osp-p01`, `kflux-prd-rh03`, `kflux-rhel-p01`, `stone-prod-p01` |
| 3 | production | Manual | 48h | `stone-prd-rh01`, `stone-prod-p02` |
| 4 | production | Manual | 72h | `kflux-prd-rh02` |

Soak: ring-3 `48h0m0s`, ring-4 `72h0m0s` on the Freight source (ring-0/1/2 none). Each
Stage still requires verified Freight from its predecessor. Ring 0 requires
`ci/prow/appstudio-operator-overlay-e2e-tests`; Prow is skipped in later rings.
Auto-promotion creates production proposals (Rings 2-4); it does not approve
their merge. Rings 3-4 soak (48h / 72h) before promoting onward. Readiness and
kanary cover each ring's full cluster set. Ring-1's `stone-stage-p01` and
`stone-stg-rh01` currently render only `kueue-config` (missing `../base`) — a
misconfiguration being fixed separately; they stay in the ring-1 set, not dropped.

## What changes

Preparation replaces only the target ring's `base/base-snapshot`, removing stale
files and copying the selected Freight's `components/policies/base`. It does not
touch ring-local overlays (`konflux-rbac/`, `kueue/`, `cost-management/`,
`patches`, cluster directories) or any `kustomization.yaml`. The shared
publication, CI, merge and readiness tasks handle the rest.

See the [shared workflow guide](../../../../shared/promotion-tasks/README.md).
