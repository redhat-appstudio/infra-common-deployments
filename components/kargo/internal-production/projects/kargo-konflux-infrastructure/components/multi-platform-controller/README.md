# Multi-platform controller promotions

One Warehouse tracks two sources: `components/multi-platform-controller/base`
from infra-deployments Git and the SHA-tagged controller image from Quay.
The controller SHA sets **both image tags and both upstream manifest refs**.
The OTP image is not selected independently: preparation waits up to two hours
for that exact tag to appear in its public Quay repository before changing Git.

This follows the existing deployment contract: controller and OTP are built from
the same source revision. The availability check does not prove compatibility
between arbitrary versions or verify image provenance. Both image repositories
must keep SHA tags immutable; OTP's digest is not independently recorded in Freight.

## Rings and approval

| Ring | Merge policy | Upstream soak | Argo CD targets |
|---|---|---|---|
| 0 | Automatic after GitHub checks and Prow | None | No fixed Argo CD target list; Prow is required |
| 1 | Automatic after GitHub checks | None | `stone-stage-p01`, `stone-stg-rh01`, `lightwell-dev` |
| 2 | Manual | 24h | `kflux-lw-p01`, `kflux-fedora-01`, `kflux-ocp-p01`, `kflux-osp-p01`, `kflux-prd-rh03`, `kflux-rhel-p01`, `stone-prod-p01` |
| 3 | Manual | 48h | `stone-prd-rh01`, `stone-prod-p02` |
| 4 | Manual | 72h | `kflux-prd-rh02` |

Ring 0 receives Freight directly. Each later ring takes verified Freight from
its predecessor. Auto-promotion is enabled for every ring; production creates a
proposal and waits for a human to merge it. The Prow gate is
`ci/prow/appstudio-operator-overlay-e2e-tests`, whose trigger includes this
component's Ring 0. It is an integration gate, not an MPC-specific test suite.
Prow is skipped explicitly in Rings 1-4.

Readiness checks every configured Application after merge in Rings 1-4. Targets
match the rendered staging/production ApplicationSets and existing ring paths;
this onboarding does not add clusters. The infrastructure Kanary templates add
sampled verification: Ring 1 checks `stone-stage-p01` and `stone-stg-rh01`, Ring 2
checks `stone-prod-p01`, `kflux-fedora-01` and `kflux-prd-rh03`, Ring 3 checks
`stone-prd-rh01`, and Ring 4 checks `kflux-prd-rh02`.

## What a promotion changes

Each ring prepares the selected Freight against current `main`:

1. Verify that the OTP image with the controller's SHA exists. Missing tags,
   rate limits and server errors wait; invalid requests or denied access fail.
2. Replace only `base/base-snapshot` with the shared monitoring/RBAC base from
   the Freight's immutable Git checkout, including removal of deleted files.
3. Set controller and OTP image tags and the `deploy/operator` and `deploy/otp`
   manifest refs to the selected controller SHA.
4. Use shared tasks for PR publication, CI, merge and Argo CD readiness.

Image match names remain `multi-platform-controller` and
`multi-platform-otp-server`. Host charts, host values, credentials, resource
patches and logcollector configuration stay in their existing ring/cluster
locations and are not copied between rings. Their changes need separate reviewed
rollouts. PR descriptions show previous and proposed image tags and manifest refs.

## Operational limits

- A Git/image bundle is a candidate, not a coordinated release transaction.
  Ring 0 and staging validate the combination before production approval.
- The OTP check uses the public Quay API, not the shared GitHub PAT. It polls
  every two minutes only while waiting, with a two-hour limit per promotion.
- A permanently missing OTP tag blocks promotion. Inspect the companion build
  or choose another Freight; do not bypass the check.
- Soak follows the infrastructure peer policy. It counts time while Freight is
  current in its upstream Stage; frequent replacements can delay eligibility.
- Shared readiness requires the captured merge revision. A newer `main` revision
  can cause a timeout even when the component is healthy.

See the [shared workflow guide](../../../../shared/promotion-tasks/README.md)
for task contracts and troubleshooting.
