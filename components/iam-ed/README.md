# IAM

The Identity Access Management (IAM) component contains manifests for **identity and access management** on Konflux **common clusters**, defining OpenShift **ClusterRoles** and **ClusterRoleBindings** for Konflux Rover/LDAP groups.

## What gets deployed

### RBAC roles and bindings

| Manifest | Kind | Purpose |
| --- | --- | --- |
| `konflux-admins.yaml` | `ClusterRole` / `ClusterRoleBinding`  | Elevated permissions on the management cluster (OpenShift platform, Tekton, Argo CD, JVM build service, etc.) |
| `dev-can-sync.yaml` | `ClusterRole` / `ClusterRoleBinding` | View and sync Argo CD `Application`s; view projects, clusters, and repositories |
| `component-maintainers.yaml` | `ClusterRole` | OLM `installplans`, pipeline `ServiceAccount` patch, Tekton `PipelineRun` cleanup, Tekton Results, port-forward |
| `everyone-can-view.yaml` + patch | `ClusterRole` / `ClusterRoleBinding`| Shared view access for cluster version, compute, and cluster monitoring |

`everyone-can-view-patch.yaml` centralizes the list of Konflux Rover groups that receive the “everyone can view” bindings so the same group list is not duplicated across multiple bindings.

## Related components

- [rover-group-sync](../rover-group-sync/README.md)
- [authentication](https://github.com/redhat-appstudio/infra-deployments/tree/main/components/authentication)
- [k8s-groups component](https://github.com/redhat-appstudio/internal-infra-deployments/tree/main/components/k8s-groups)
