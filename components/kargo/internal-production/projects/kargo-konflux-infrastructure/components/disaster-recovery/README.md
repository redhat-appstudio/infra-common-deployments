# Disaster recovery promotions

The `disaster-recovery` Warehouse and stages belong to
`kargo-konflux-infrastructure`. They promote the manifests in
`components/tenants-backup-restore-test` in infra-deployments. The Kargo
component name follows the ArgoCD Application name and
`app.kubernetes.io/part-of: disaster-recovery` label.

## Source and promotion scope

The Warehouse watches changes to `components/tenants-backup-restore-test/base`
on infra-deployments `main` every two hours. The selected Git commit is checked
out separately from the current target branch. The preparation task replaces
only the target ring's `base/base-snapshot` with this immutable source,
including source deletions.

Pinned task image updates arrive through Git changes to the base manifests.
There is no separate image or Helm chart subscription. Ring-specific CronJob,
triggers, networking, RBAC, and cluster overlays stay outside the snapshot;
changes to those files require normal infra-deployments PRs.

## Ring gates

| Stage | Source | Merge | Gates |
| --- | --- | --- | --- |
| ring-0-disaster-recovery | Warehouse | Automatic after CI | GitHub checks and `ci/prow/konflux-ring-deployments-conformance-tests` |
| ring-1-disaster-recovery | Verified Ring 0 Freight | Automatic after CI | GitHub checks, ArgoCD readiness, staging Kanary |

Ring 1 runs on the `infra-deployments-staging` shard. Its readiness check
targets `disaster-recovery-stone-stg-rh01`; Kanary checks only
`stone-stg-rh01` with an expected cluster count of one. This matches the
current staging ApplicationSet's explicit cluster selector. Other Ring 1
directories exist, but the ApplicationSet does not select them.

Both stages enable automatic promotion, with no additional soak requirement,
following the infrastructure project's existing Ring 0 and Ring 1 pattern.
No Rings 2–4 are configured because this component has no production ring
deployments.

## Operations

The initial discovery can immediately start promotions, including a no-op when
the selected base already matches a ring snapshot. Deployment follows merged
promotion PRs through ArgoCD.

The existing staging scheduler will run the promoted backup/restore tasks.
This pipeline does not itself start a disaster-recovery PipelineRun. ArgoCD
readiness and Kanary do not prove that a backup/restore exercise succeeded;
that remains visible through the existing scheduled pipeline results.

If the ApplicationSet's cluster selection changes, update both the readiness
and Kanary cluster lists here. To stop new promotions, disable this component's
two auto-promotion policies and review any already-running promotions.
Reverting the onboarding configuration does not revert merged snapshot PRs;
revert those separately in infra-deployments when needed.
