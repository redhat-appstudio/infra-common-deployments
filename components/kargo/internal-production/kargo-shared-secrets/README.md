# kargo-shared-secrets

Kustomize Component that provides shared ExternalSecrets to all Kargo projects.
Included via `components:` in each project's `kustomization.yaml`. The project's
`namespace:` field ensures each secret is created in the correct project namespace.

## Structure

```
kargo-shared-secrets/
  kargo-promotion-credentials.yaml          # Git + PAT for Kargo promotion workflows
  argocd-app-reader-token-staging.yaml      # ArgoCD staging app reader token
  konflux-verifications-credentials/        # Konflux conformance test credentials
    konflux-e2e-external-secrets.yaml
    konflux-conformance-tests-credentials-external-secret.yaml
```

## Secrets

| Secret | Vault Key | Purpose |
|--------|-----------|---------|
| `kargo-promotion-credentials` | `production/devprod/infra-deployments-bot` | GitHub PAT used by promotion tasks (wait-for-ci, PR creation/merge). Git cred-type. |
| `argocd-app-reader-token-staging` | `staging/devprod/kargo-infra-deployments-argocd-app-reader-staging` | Bearer token to query ArgoCD staging Applications API during ring promotions. |
| `konflux-conformance-sa` | `production/devprod/konflux-conformance-*` (pattern match) | SA tokens per staging cluster for running Konflux conformance tests. |
| `konflux-conformance-tests-credentials` | `production/devprod/konflux-conformance-tests-credentials` | Credentials for the Konflux conformance test suite (github.com/konflux-ci/konflux-ci). |

## What belongs here

- Secrets shared across **all** Kargo projects (not component-specific)
- ExternalSecrets pulling from Vault via the `appsre-stonesoup-vault` ClusterSecretStore
- Credentials used by shared promotion tasks or verification pipelines

## What does NOT belong here

- Component-specific secrets (put them in the component's own directory)
- Secrets used by only one project (put them in that project's `base/`)
- Non-secret resources (RBAC, promotion tasks, stages, etc.)

## Usage

In a project's top-level `kustomization.yaml`:

```yaml
components:
  - ../../kargo-shared-secrets
```
