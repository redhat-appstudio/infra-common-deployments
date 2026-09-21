# External Secrets Operator promotions

One Warehouse, `external-secrets-operator`, records the base manifests and
vendored Helm chart from Git together with a SHA-tagged image from
`quay.io/konflux-ci/external-secrets-operator`. No Helm subscription is needed:
the chart is checked into `components/external-secrets-operator/base`.

## Promotion flow

| Ring | Source | PR merge | Upstream soak | Argo CD targets |
|---|---|---|---|---|
| 1 | Warehouse | Automatic after CI | None | `stone-stage-p01`, `stone-stg-rh01`, `kflux-stg-es01` |
| 2 | Verified Ring 1 | Manual | 24h | `kflux-fedora-01`, `kflux-ocp-p01`, `kflux-osp-p01`, `kflux-prd-es01`, `kflux-prd-rh03`, `kflux-rhel-p01`, `stone-prod-p01`, `kflux-lw-p01` |
| 3 | Verified Ring 2 | Manual | 48h | `stone-prd-rh01`, `stone-prod-p02` |
| 4 | Verified Ring 3 | Manual | 72h | `kflux-prd-rh02` |

These targets come from the rendered ESO staging/production ApplicationSets.
Ring 0 is an empty placeholder with no development ApplicationSet, so promotion
starts at Ring 1. `lightwell-dev` is empty and is not a deployment target.
GitHub checks are required. Prow is explicitly skipped: this component has no
active Ring 0 deployment, and the Operator overlay Prow suite targets Ring 0.

Production auto-promotion creates the proposal; it does not merge it. Every ring
waits for all its Argo CD Applications to be healthy and synchronized after the
confirmed merge. Argo CD auto-sync is enabled in the source ApplicationSets.

The existing infrastructure Kanary checks add sampled verification: staging
checks `stone-stage-p01` and `stone-stg-rh01`; production checks Ring 2's
`stone-prod-p01`, `kflux-fedora-01`, `kflux-prd-rh03`, Ring 3's `stone-prd-rh01`, and
Ring 4's `kflux-prd-rh02`. This is not ESO-specific testing or full fleet Kanary
coverage; Argo CD readiness checks every target listed above.

## What changes in Git

Each promotion clones current `main` into `./src` and the selected Freight's Git
commit into `./freight`. Preparation replaces only the target ring's
`base/base-snapshot` from the Freight checkout, then sets the outer Kustomization's
image override. This pins manager, webhook and cert-controller to the same selected
Quay image. Ring-specific values and cluster overlays are preserved.

Every ring reconstructs the same Freight bundle; it never copies a moving
previous-ring snapshot. Shared tasks handle PR publication, CI, merging and
readiness. PR descriptions show chart/image changes and the source Git commit.

At onboarding, Ring 1 already uses a Quay SHA tag, while production uses the
chart's GHCR image. The first production promotion therefore changes the image
repository as well as its tag; review that transition before merging.

## Limits

- A combined Warehouse records a candidate; it does not prove chart/image
  compatibility. Git and image releases may arrive independently. Validate the
  selected combination in staging before approving production.
- SHA tags must remain immutable in Quay to preserve image content across rings.
- Soak follows the infrastructure peer policy. Kargo measures time while Freight
  is current in the upstream Stage; frequent newer promotions can delay eligibility.
- Ring-specific `values.yaml` changes are outside the Warehouse's watched base
  directory and require their own reviewed rollout.
- Shared readiness requires the exact merge revision; later commits on `main`
  can cause a timeout even when the component is healthy.

See the [shared workflow guide](../../../../kargo-shared-promotion-tasks/README.md)
for task contracts, CI policy and troubleshooting.
