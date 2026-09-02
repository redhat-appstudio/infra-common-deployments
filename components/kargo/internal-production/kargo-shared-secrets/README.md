# Shared Secrets

## Overview

This directory is a Kustomize Component that provides Vault-synced ExternalSecrets to all Kargo projects. Each ExternalSecret pulls credentials from HashiCorp Vault via the `appsre-stonesoup-vault` ClusterSecretStore and creates a Kubernetes Secret in the project namespace.

## Usage

Projects include this component in their `kustomization.yaml`:

```yaml
components:
  - ../../kargo-shared-secrets
```

The Kustomize `namespace:` directive in each project ensures that every ExternalSecret and resulting Secret is created in the correct project namespace automatically.

**Important:** Do not create project-level copies of these ExternalSecrets. Duplicating them leads to naming conflicts and makes secret rotation error-prone. If a project needs a secret that is not shared, add it to the project's own `base/external-secrets/` directory instead.

## Included Secrets

### `kargo-promotion-credentials`

Provides the GitHub Personal Access Token used by promotion steps to create and merge pull requests against the `infra-deployments` repository.

| Property | Value |
| --- | --- |
| ExternalSecret name | `kargo-promotion-credentials` |
| Vault path | `production/devprod/infra-deployments-bot` |
| Secret keys | `github_pat` |
| Kargo label | `kargo.akuity.io/cred-type: git` |
| Refresh interval | 15 minutes |
| Consumed by | `git-open-pr`, `find-pr`, and `git-merge-pr` steps in the shared `git-workflow-infra-deployments` PromotionTask |

### `argocd-app-reader-token-staging`

Provides a bearer token for querying the ArgoCD Kubernetes API to verify that Applications have synced to the expected commit after a promotion merges.

| Property | Value |
| --- | --- |
| ExternalSecret name | `argocd-app-reader-token-staging` |
| Vault path | `staging/devprod/kargo-infra-deployments-argocd-app-reader-staging` |
| Secret keys | `token` |
| Kargo label | `kargo.akuity.io/cred-type: generic` |
| Refresh interval | 15 minutes |
| Consumed by | `wait-for-infra-deployments-argocd-sync` PromotionTask |

### `kargo-rhobs-staging`

Provides OAuth2 client credentials for authenticating to the staging RHOBS Observatorium instance when querying Prometheus metrics during kanary verification.

| Property | Value |
| --- | --- |
| ExternalSecret name | `kargo-rhobs-staging` |
| Vault path | `staging/devprod/kargo-rhobs-staging` |
| Secret keys | `client_id`, `client_secret` |
| Refresh interval | 15 minutes |
| Consumed by | `kanary-staging` AnalysisTemplate (via `valueFrom.secretKeyRef`) |

### `kargo-rhobs-production`

Provides OAuth2 client credentials for authenticating to the production RHOBS Observatorium instance.

| Property | Value |
| --- | --- |
| ExternalSecret name | `kargo-rhobs-production` |
| Vault path | `production/devprod/kargo-rhobs-production` |
| Secret keys | `client_id`, `client_secret` |
| Refresh interval | 15 minutes |
| Consumed by | `kanary-production` AnalysisTemplate (via `valueFrom.secretKeyRef`) |

### `konflux-conformance-sa`

Provides service account tokens for all staging clusters, used by conformance test AnalysisTemplates to authenticate when launching PipelineRuns on target clusters. Uses the ESO `find` directive with a regexp to auto-discover all Vault keys matching the naming convention, so new clusters are picked up without configuration changes.

| Property | Value |
| --- | --- |
| ExternalSecret name | `konflux-conformance-sa` |
| Vault path pattern | `production/devprod/konflux-conformance-*` (auto-discovered) |
| Secret keys | One key per cluster (e.g., `konflux-conformance-stone-stage-p01`) containing a JSON object with a `token` field |
| Kargo label | `kargo.akuity.io/cred-type: generic` |
| Refresh interval | 10 minutes |
| Consumed by | `konflux-conformance-tests-stone-stage-p01` AnalysisTemplate |

## Adding a New Shared Secret

1. Create a new ExternalSecret YAML file in this directory. 2. Add the filename to the `resources` list in `kustomization.yaml`. 3. Verify that the Vault path exists and the `appsre-stonesoup-vault`
   ClusterSecretStore has read access to it.
4. Validate the build:
   ```bash
   kustomize build components/kargo/internal-production/projects/<any-project>/
   ```
5. After merging, confirm that the ExternalSecret reaches `Ready` status in
   each project namespace.

## Anti-Patterns

- **Do not duplicate shared secrets in project directories.** If a project
  references `kargo-shared-secrets` as a component and also defines the same
  ExternalSecret locally, the build will fail with a duplicate resource error.
- **Do not hardcode secret names in stages.** Use the shared task variables
  (e.g., `githubPatSecret`, `tokenSecret`) to reference secrets by name so
  that secret rotation requires changes in only one place.
