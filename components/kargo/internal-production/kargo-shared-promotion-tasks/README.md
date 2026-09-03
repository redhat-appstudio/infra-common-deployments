# kargo-shared-promotion-tasks

Kustomize Component that provides shared PromotionTasks to all Kargo projects.
Included via `components:` in each project's `kustomization.yaml`.

## Tasks

| Task | Purpose |
| ---- | ------- |
| `github-ci-gate` | Polls GitHub API until all CI checks (Actions + Prow) pass for a commit. Gates ring advancement on green CI. |
| `wait-for-infra-deployments-argocd-sync` | Verifies ArgoCD Applications have synced a specific commit and are healthy on target clusters. |

Both tasks only apply to components using Ring Deployments via the
`redhat-appstudio/infra-deployments` repository.

## Dependencies

- `kargo-promotion-credentials` secret (from `kargo-shared-secrets`) — GitHub PAT for API calls
- `argocd-app-reader-token-staging` secret (from `kargo-shared-secrets`) — ArgoCD bearer token

## What belongs here

- PromotionTasks shared across **all** Kargo projects
- Tasks that are generic and parameterized via vars (not component-specific)

## What does NOT belong here

- Component-specific promotion tasks (put them in the component's own directory)
- Tasks used by only one project

## Usage

In a project's top-level `kustomization.yaml`:

```yaml
components:
  - ../../kargo-shared-promotion-tasks
```
