# cert-manager-trusted-ca promotions

## Source and preparation

Edit `components/cert-manager-trusted-ca/base/` in
[infra-deployments](https://github.com/redhat-appstudio/infra-deployments/tree/main/components/cert-manager-trusted-ca/base).
The Git-only Warehouse watches that path on `main` every two hours. Ring paths
are excluded to avoid discovering Kargo's own snapshot promotions. There are
no image or chart subscriptions: this component defines the trust-manager
`Bundle` named `trusted-ca`, not the cert-manager or trust-manager operators.

Preparation replaces the target ring's `base/base-snapshot/` with the base from the
selected immutable Git revision. Deleted source files are removed too. It checks
the Warehouse, component, repository, ring, commit SHA and snapshot reference,
and requires a successful Kustomize render before reporting `prepared: yes`.
Ring-local configuration remains outside the copied snapshot.

The `rh-internal-ca` source ConfigMap is supplied separately by the private
internal-infra-deployments repository. This pipeline does not copy certificates
or change that dependency. The trust-manager controller and its CRD must already
be installed. The Bundle distributes the combined default and RH internal CAs
to `trusted-ca` ConfigMaps across namespaces; changes affect workload trust.

## Coverage and policy

Inventory was checked at infra-deployments commit
[`6cf5ed127187b0ee022cfbfe0319a8ea136f06d3`](https://github.com/redhat-appstudio/infra-deployments/commit/6cf5ed127187b0ee022cfbfe0319a8ea136f06d3),
including the rendered staging and production ApplicationSets.

| Ring | Kargo scope | Argo readiness targets | Kanary targets |
| --- | --- | --- | --- |
| 0 | None: empty, not deployed to development | None | None |
| 1 | Git Warehouse → snapshot promotion | `kflux-stg-p02`, `kflux-hub-stg-01` | `kflux-stg-p02`, expected count 1 |
| 2 | Verified Ring 1 Freight → snapshot promotion | `kflux-lw-p01` | `kflux-lw-p01`, expected count 1 |
| 3–4 | No deployment overlays | None | None |

Both rings follow the existing infrastructure manifest policy: eligible Freight
automatically starts a promotion and opens a PR; **PR merge is manual**. The
shared CI task runs GitHub checks with Prow skipped, as in sibling manifest
pipelines. After merge, the staging shard checks both Ring 1 Applications using
`argocd-app-reader-token-staging`. The production shard checks Ring 2 using
`argocd-app-reader-token`. Both use sync, health and revision checks.

The ApplicationSet must label generated Applications with
`app.kubernetes.io/part-of: cert-manager-trusted-ca` before enabling this pipeline;
the shared readiness task filters on that label. Prerequisites:
[Ring 1 labels #15694](https://github.com/redhat-appstudio/infra-deployments/pull/15694)
and [Ring 2 labels #15695](https://github.com/redhat-appstudio/infra-deployments/pull/15695).
Without these labels, readiness fails
closed because the expected Applications are missing from the query.

Post-promotion verification uses `kanary-staging` / `kanary-production`
with `container-single-arch`
and the shared timing defaults. There is no additional soak time. The staging
hub has no assigned Kanary probe overlay, so it receives Argo readiness checks
only. Kanary is a general workload signal, not a direct certificate-chain test.
Live metrics and promotions were not exercised during onboarding.

`kflux-lw-p01` is explicitly included for this component, as an approved
exception to its exclusion from other Kargo pipelines. Ring 2 consumes verified
Ring 1 Freight and checks this cluster with both Argo readiness and Kanary.

## Operation and rollback

Review the proposed snapshot changes and CI results before merging. A no-op
promotion still goes through the shared deployment-readiness path. Investigate
failed readiness or Kanary verification before approving Freight manually.

To pause new proposals, disable the relevant ring's `autoPromotionEnabled` policy and
handle queued Promotions separately. Revert the affected infra-deployments
snapshot PR to roll back a deployed change. Removing the Kargo configuration
alone does not undo a deployed Bundle or changes to generated CA ConfigMaps.
