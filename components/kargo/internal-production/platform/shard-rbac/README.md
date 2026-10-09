# Shard heartbeats

All three remote shards connect to the production Kargo control plane:

| Controller | Workload namespace |
|---|---|
| `infra-common-deployments-staging` | `kargo-shard-infra-common-deployments` |
| `infra-deployments-staging` | `kargo-shard-infra-deployments` |
| `infra-deployments-production` | `kargo-shard-infra-deployments-production` |

Their workloads run in separate namespaces, but the production Kargo API reads
controller heartbeats from `kargo`. Each shard's Helm values therefore set
`global.kargoNamespace: kargo`. A Stage's `spec.shard` selects its controller;
the heartbeat namespace is configured on the controller, not on the Stage.

The existing `kargo-shard-staging` ServiceAccount is the identity used by all
three shards' `production-kargo-kubeconfig`. The heartbeat RoleBinding grants
that identity permission to create Leases in `kargo` and to get, update, and
delete only the three `kargo-controller-<controller-name>` heartbeat Leases.
Creation cannot be restricted by resource name using Kubernetes RBAC. Delete
is needed for heartbeat cleanup on controller shutdown.

## Rollout

Sync the production Kargo platform RBAC before syncing the shard Applications.
Each shard's ConfigMap change rolls out its controller. If a shard rolls out
before RBAC is available, heartbeat writes fail and retry until the Role and
RoleBinding are applied.

After rollout, check that each heartbeat Lease in `kargo` has a recent
`spec.renewTime` and each controller is reported alive in the UI. This check
requires Lease read permissions; a Ready pod alone does not prove that its
heartbeat is visible to the API.

The previous Lease permissions in the shard namespaces remain available for
rollback. Revert the shard namespace settings before removing the new
heartbeat RBAC.
