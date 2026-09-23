# Kargo

Kargo promotes selected Git revisions, images and charts through deployment rings.
A **Warehouse** discovers artifacts, **Freight** records a selected bundle, and a
**Stage** defines how that bundle is promoted and verified. Promotion workflows
change deployment Git through pull requests; Argo CD reconciles the result.

## Start here

- [Production directory and ownership](internal-production/README.md)
- [Onboard a component](internal-production/docs/onboarding.md)
- [Operate and upgrade Kargo](internal-production/docs/operations.md)
- [Configure verification](internal-production/docs/verifications.md)
- [Existing Kargo owners](OWNERS)

## Topology

| Piece | Location | Purpose |
|---|---|---|
| Production control plane | [internal-production](internal-production/) | Hosts the six production Kargo projects and their promotion state |
| Staging control plane | [internal-staging](internal-staging/) | Separate full installation for testing and Kargo's own staging rollout |
| Staging shards | [kargo-shard/internal-staging](../kargo-shard/internal-staging/) | Execute production-hosted Stages against staging Argo CD |
| Production shard | [kargo-shard/internal-production](../kargo-shard/internal-production/) | Executes Stages targeting production `argocd-infra-deployments` |
| Argo Rollouts | [argo-rollouts/internal-production](../argo-rollouts/internal-production/) | Supplies AnalysisTemplate/AnalysisRun CRDs and verification reconciliation |

The Stage's `spec.shard` selects its controller. Each configured shard targets one
Argo CD namespace; the staging Kargo control plane is distinct from a staging
shard connected to the production host. See the [connection map](internal-production/docs/operations.md#cross-cluster-connections).

## Repository boundaries

`base/` contains common Route/OAuth and RBAC configuration. Each environment's
`deployment/` contains its Helm generator. Production additionally separates
platform resources, reusable workflow definitions and project-owned components.
The [Kargo ApplicationSet](../../argo-cd-apps/base/internal/kargo/appset.yaml)
deploys these environment overlays.

[Historical project examples](examples/project/) are reference material outside
the deployment tree. For new work, use the maintained implementations linked in
[onboarding](internal-production/docs/onboarding.md).
