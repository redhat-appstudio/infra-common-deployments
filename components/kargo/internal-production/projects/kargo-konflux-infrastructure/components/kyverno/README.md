# Kyverno Promotions

One Warehouse tracks the SHA-tagged kyverno image from Quay. The kyverno SHA sets **all image tags**. The other 4 images (kyverno-init, kyverno-background, kyverno-cleanup, and kyverno-cli) are not selected independently: the promotion tasks wait up to two hours
for that exact tag to appear in the public Quay repository before making changes with Git.


| **Note**: Because Kyverno has its image tags at the cluster level instead of the ring level, the creation of a new cluster will require the hosting ring's PromotionTask to be updated with steps for the new cluster. See the [template PromotionTask](./template-pt.yaml) for details.

## Rings and Approvals

| Ring | Merge policy | Upstream soak | Argo CD targets |
|---|---|---|---|
| 0 | Automatic after GitHub checks and Prow | None | No fixed Argo CD target list; Prow is required |
| 1 | Automatic after GitHub checks | None | `stone-stage-p01`, `stone-stg-rh01`, `lightwell-dev` |
| 2 | Manual | 24h | `kflux-lw-p01`, `kflux-fedora-01`, `kflux-ocp-p01`, `kflux-osp-p01`, `kflux-prd-rh03`, `kflux-rhel-p01`, `stone-prod-p01` |
| 3 | Manual | 48h | `stone-prd-rh01`, `stone-prod-p02` |
| 4 | Manual | 72h | `kflux-prd-rh02` |

Ring 0 receives Freight directly. Each later ring takes verified Freight from its predecessor Auto-promotion is enabled for every ring; production creates a pull request and waits for a human to merge it. The Prow gate is `ci/prow/appstudio-operator-overlay-e2e-tests`, whose trigger includes this component's ring 0. It is an integration gate, not a kyverno-specific test suite. Prow is skipped explicitly in rings 1-4.

Readiness checks occur on every configured Application after merge in rings 1-4. Targets match the rendered staging/production ApplicationSets and existing ring paths; this onboarding does not add clusters. The infrastructure Kanary templates add sampled verification: ring 1 checks `stone-stage-p01` and `stone-stg-rh01`; ring 2 checks `stone-prod-p01`, `kflux-fedora-01` and `kflux-prd-rh03`; ring 3 checks `stone-prd-rh01`; and ring 4 checks `kflux-prd-rh02`.

## What a Promotion Changes

Each ring prepares the selected Freight against current `main`:

1. Verify that each of the 4 other image repositories has an image with the same SHA tag as the kyverno image.
2. Verify that each cluster's Kustomize file already has the necessary 5 kyverno image entries.
3. Set all 5 kyverno images (in each cluster's Kustomize file) to the selected image SHA.
4. Use shared tasks for PR publication, CI, merge and Argo CD readiness. PR descriptions will show previous and proposed image tags.

Helm values and the Helm generator stay in their existing cluster locations and are not copied across rings. Changes to those resources need separate reviewed rollouts and are not managed by Kargo.

## Operational limits

- A kyverno image is a candidate, not a coordinated release transaction across all image repos. Ring 0 and staging validate the combination before production approval.
- The other image checks uses the public Quay API, not the shared GitHub PAT. It polls every two minutes only while waiting, with a two-hour limit per promotion.
- A permanently missing image tag blocks promotion. Inspect the companion builds or choose another Freight; do not bypass the check.
- Soak follows the infrastructure peer policy. It counts time while Freight is current in its upstream Stage; frequent replacements can delay eligibility.

See the [shared workflow guide](../../../../shared/promotion-tasks/README.md)
for task contracts and troubleshooting.
