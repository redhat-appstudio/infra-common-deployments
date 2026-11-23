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

| Ring | Freight source | Argo readiness targets | PR merge |
| --- | --- | --- | --- |
| 0 | None: empty, not deployed to development | None | None |
| 1 | Git Warehouse | `kflux-stg-p02`, `kflux-hub-stg-01` | Manual |
| 2 | Successfully promoted Ring 1 Freight | `kflux-lw-p01` | Automatic after required approval and checks |
| 3–4 | No deployment overlays; not onboarded | None | None |

Eligible Freight automatically starts a promotion and opens a PR in both rings.
Ring 1 requires manual PR merge. Ring 2 uses the shared automatic merge task,
with an explicit GitHub `reviewDecision == APPROVED` check for the tested head
before requesting a merge. This is necessary because the Kargo App has a branch
rule bypass. Pending or changes-requested reviews wait; API errors, a closed PR
or a changed head fail the check. The wait is limited to seven days. An already
merged PR is observed without requesting another merge; no-op promotions have
no PR to approve. The shared CI task
runs GitHub checks with Prow skipped, as in sibling manifest pipelines.

After merge, the staging shard checks both Ring 1 Applications using
`argocd-app-reader-token-staging`. The production shard checks Ring 2 using
`argocd-app-reader-token`. Both use sync, health and revision checks before
promotion succeeds.

The ApplicationSet must label generated Applications with
`app.kubernetes.io/part-of: cert-manager-trusted-ca` before enabling this pipeline;
the shared readiness task filters on that label. Prerequisites:
[Ring 1 labels #15694](https://github.com/redhat-appstudio/infra-deployments/pull/15694)
and [Ring 2 labels #15695](https://github.com/redhat-appstudio/infra-deployments/pull/15695).
Without these labels, readiness fails
closed because the expected Applications are missing from the query.

This component has no Kanary AnalysisRun or additional soak time in either
ring. Successful Ring 1 promotion, including Argo readiness, makes Freight
eligible for Ring 2. Argo health is not a direct certificate-chain test.
Live promotions were not exercised during onboarding.

`kflux-lw-p01` is explicitly included for this component, as an approved
exception to its exclusion from other Kargo pipelines. Rings 3–4 must be added
only after infra-deployments defines their overlays and target clusters.

## Operation and rollback

Review the proposed snapshot changes and CI results before merging. A no-op
promotion still goes through the shared deployment-readiness path. Investigate
failed CI or Argo readiness before approving Freight manually.

To pause new proposals, disable the relevant ring's `autoPromotionEnabled` policy and
handle queued Promotions separately. Revert the affected infra-deployments
snapshot PR to roll back a deployed change. Removing the Kargo configuration
alone does not undo a deployed Bundle or changes to generated CA ConfigMaps.
