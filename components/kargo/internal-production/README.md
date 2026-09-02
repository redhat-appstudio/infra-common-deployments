# Kargo Internal Production

Kargo progressive delivery for Konflux infrastructure. Components promote through ring-0 (dev) → ring-1 (staging) → ring-2+ (production) automatically.

## Directory Structure

| Directory | Description | When to Modify |
| --- | --- | --- |
| `projects/` | Kargo project definitions. Each subdirectory maps to a Kargo namespace containing Warehouses, Stages, and PromotionTasks for a set of components. | When onboarding a new component or modifying an existing promotion pipeline. |
| `kargo-shared-promotion-tasks/` | Kustomize Component providing reusable PromotionTasks shared by all projects. Includes `wait-for-ci`, `wait-for-infra-deployments-argocd-sync`, and `git-workflow-infra-deployments`. | When modifying the shared git workflow or CI check logic. See [README](kargo-shared-promotion-tasks/README.md). |
| `kargo-shared-secrets/` | Kustomize Component providing Vault-synced ExternalSecrets shared by all projects. Includes GitHub PAT, ArgoCD reader tokens, RHOBS credentials, and conformance test credentials. | When adding or rotating a shared Vault secret. See [README](kargo-shared-secrets/README.md). |
| `kargo-shared-verifications/` | Kustomize Component providing AnalysisTemplates for post-promotion verification. Includes kanary smoke tests and conformance e2e tests. | When adding or modifying verification checks. See [README](kargo-shared-verifications/README.md). |
| `deployment/` | Kargo Helm chart, values, and controller deployment configuration. | When upgrading the Kargo version or modifying controller settings. |
| `shard-rbac/` | RBAC definitions for Kargo shard controllers running on member clusters. | When adding a new shard controller or adjusting its permissions. |
| `docs/` | Operational documentation for component onboarding and maintenance. | Reference only; update when processes change. |

## Quick Start

### Onboard a new component

Follow the step-by-step guide in [docs/onboarding.md](docs/onboarding.md).

### Understand what shared resources are available

Each shared component directory contains a README documenting every resource
it provides, including configuration variables, secret references, and usage
examples:

- [Shared Secrets Reference](kargo-shared-secrets/README.md)
- [Shared Promotion Tasks Reference](kargo-shared-promotion-tasks/README.md)
- [Shared Verifications Reference](kargo-shared-verifications/README.md)

### Add a component to an existing project

1. Identify the target project under `projects/` (for example,
   `kargo-infra-deployments` or `kargo-konflux-infrastructure`).
2. Create a component directory at
   `projects/<project>/components/<component>/` containing `warehouse.yaml`,
   `promotiontask.yaml`, and a `stages/` subdirectory.
3. Register the component in the project `kustomization.yaml` and add
   auto-promotion policies to `base/project-config.yaml`.
4. Validate the output:
   ```bash
   kustomize build components/kargo/internal-production/projects/<project>/
   ```

### Available Kargo Projects

| Project | Namespace | Components |
| --- | --- | --- |
| `kargo-infra-deployments` | `kargo-infra-deployments` | dummy-deployment (and future infra-deployments components) |
| `kargo-konflux-core` | `kargo-konflux-core` | konflux-operator |
| `kargo-konflux-infrastructure` | `kargo-konflux-infrastructure` | authentication, etcd-shield |
| `kargo-konflux-vanguard` | `kargo-konflux-vanguard` | artifact-registry-proxy, container-image-proxy, notification-controller |

### Troubleshooting Common Promotion Failures

| Symptom | Cause | Resolution |
| --- | --- | --- |
| `outputs['push'].commit` is nil | The component-specific promote task failed before the `git-push` step executed. | Inspect the promote task step logs in the Kargo UI. Common causes include malformed kustomization paths or missing files in the target ring directory. |
| `HTTP (403)` in `wait-for-sync` | The ArgoCD reader token secret is missing, has no data, or lacks the `kargo.akuity.io/cred-type: generic` label. | Verify the secret exists in the project namespace and contains a valid `token` key. |
| `cannot call nil` in `wait-for-sync` | The ArgoCD API returned a response with a nil `items` field, typically because the token could not authenticate. | Confirm that the token secret references the correct Vault path and that the ExternalSecret has synced successfully. |
| `filter == []` in `wait-for-sync` | No ArgoCD Applications matched the component and cluster pattern. | Verify that the ArgoCD ApplicationSet has generated Applications for the expected clusters and that the `component` variable matches the Application name prefix. |
