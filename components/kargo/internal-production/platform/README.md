# Platform resources

These resources are included once by the [production entry point](../kustomization.yaml).
This directory groups files; it is not a Kustomize entry point and imposes no namespace.

| Directory | Responsibility | Runtime scope |
|---|---|---|
| [credentials](credentials/) | ExternalSecret definitions for common credentials | `kargo-shared-resources`; selected generated Secrets are replicated to projects |
| [shard-rbac](shard-rbac/) | Shard identities, access and cross-namespace RoleBindings | Explicit namespaces and cluster-scoped RBAC |
| [promotion-cleaner](promotion-cleaner/) | Maintenance of pending promotion queues | Runs in `kargo`; configured project access is explicit |

The Helm installation stays in [deployment](../deployment/). Kargo's self-promotion
tasks refer to that path directly.

Ownership follows [Kargo OWNERS](../../OWNERS). A file move must not change resource
names, namespace placement, RBAC subjects or credential distribution. Changes to
those contracts require a separate behavioral review.
