# Shared Promotion Tasks

## Overview

This directory is a Kustomize Component that provides reusable PromotionTasks to all Kargo projects. PromotionTasks encapsulate multi-step workflows that are identical across components, eliminating duplication and centralizing maintenance.

## Usage

Projects include this component in their `kustomization.yaml`:

```yaml
components:
  - ../../kargo-shared-promotion-tasks
```

**Important:** Do not create project-level copies of these tasks. If a task needs to be customized for a specific project, file an issue to discuss whether the customization should be added as a variable to the shared task or handled differently.

## Included Tasks

### `wait-for-ci`

Polls the GitHub API until all required CI checks pass for a given commit. Operates in two phases:

1. **GitHub Check Runs** (GitHub Actions workflows): Polls the
   `/repos/{owner}/{repo}/commits/{sha}/check-runs` endpoint until all
   matching check runs report a conclusion of `success`, `neutral`, or
   `skipped`.
2. **Prow Status Checks** (optional): Polls the
   `/repos/{owner}/{repo}/commits/{sha}/status` endpoint until all matching
   status contexts (excluding `tide`) report `success`. This phase can be
   skipped entirely by setting `skipProwChecks` to `"true"`.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `commitSHA` | Yes | (none) | The git commit SHA to monitor for CI results. |
| `repoOwner` | No | `redhat-appstudio` | The GitHub organization that owns the repository. |
| `repoName` | No | `infra-deployments` | The GitHub repository name. |
| `requiredCheckRuns` | No | `.*` | A regular expression filter applied to check-run names. Only matching runs are evaluated. |
| `requiredProwChecks` | No | `.*` | A regular expression filter applied to Prow status context names. Only matching contexts are evaluated. |
| `skipProwChecks` | No | `"false"` | Set to `"true"` to skip the Prow status check phase entirely. |

**Retry behavior:** Each phase retries for up to 2 hours 30 minutes with a 30-second poll interval.

**Authentication:** Uses the `kargo-promotion-credentials` shared secret (`github_pat` key) for GitHub API authentication.

---

### `wait-for-infra-deployments-argocd-sync`

Polls the ArgoCD Kubernetes API until all ArgoCD Applications matching a component and cluster name pattern are Synced, Healthy, and report the expected commit revision.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `commitSHA` | Yes | (none) | The expected git revision that Applications must be synced to. |
| `component` | Yes | (none) | The component name prefix used to match ArgoCD Application names (pattern: `^{component}-({clusters})$`). |
| `clusters` | Yes | (none) | A pipe-delimited regex of cluster names (e.g., `stone-stg-rh01\|stone-stage-p01`). |
| `appsNamespace` | No | `argocd-infra-deployments` | The Kubernetes namespace where ArgoCD Application resources reside. |
| `tokenSecret` | Yes | (none) | The name of the Kubernetes Secret containing a `token` key for ArgoCD API bearer authentication. |

**Immediate failure conditions:**

| Condition | Behavior |
| --- | --- |
| HTTP 401, 403, or 404 | The task fails immediately without retrying. |
| HTTP 200 with no matching Applications (`filter == []`) | The task fails immediately, indicating the component is not deployed. |
| HTTP 200 with any matching Application in `Degraded` health or `Failed`/`Error` operation phase | The task fails immediately. |

**Retry behavior:** 15-minute timeout with an error threshold of 3.

**Authentication:** Uses the secret specified by `tokenSecret` (bearer token injected into the `Authorization` header).

---

### `git-workflow-infra-deployments`

Encapsulates the entire git-based promotion workflow that is common to every stage: committing changes, pushing a branch, opening a pull request, waiting for CI, finding and merging the PR, and optionally waiting for ArgoCD to sync.

This task is designed to be invoked after a component-specific PromotionTask has already modified files in the working directory. It replaces approximately 80 lines of repeated YAML that previously appeared in every stage definition.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `srcPath` | Yes | (none) | The local git working directory path (must already contain cloned and modified files). |
| `component` | Yes | (none) | The component name, used to construct the branch name (`{project}/{component}/{targetRing}`) and PR title. |
| `targetRing` | Yes | (none) | The target ring name (e.g., `ring-0`, `ring-1`), used in branch naming and PR labels. |
| `skipProwChecks` | No | `"true"` | Whether to skip Prow CI checks during the `wait-for-ci` sub-task. |
| `clusters` | No | `""` | Cluster regex for the ArgoCD sync wait step. When empty, the sync step is skipped. |
| `tokenSecret` | No | `argocd-app-reader-token-staging` | The Secret name for ArgoCD API authentication during sync verification. |
| `waitForSync` | No | `"true"` | Set to `"false"` to skip the ArgoCD sync verification step entirely (useful for ring-0 stages that have no ArgoCD Applications). |
| `githubPatSecret` | No | `kargo-promotion-credentials` | The Secret name containing the `github_pat` key for GitHub API authentication. |

**Internal steps executed in order:**

1. `git-commit` — Commits all changes in `srcPath`. 2. `git-push` — Force-pushes to a branch named `{project}/{component}/{targetRing}`. 3. `git-open-pr` — Opens a pull request (continues on error if PR already exists). 4. `wait-for-ci` — Waits for CI checks to pass (delegates to the `wait-for-ci` shared task). 5. `find-pr` — Finds the open PR by branch name via the GitHub API. 6. `git-merge-pr` — Squash-merges the PR and waits for the merge to complete. 7. `wait-for-infra-deployments-argocd-sync` — Optionally waits for ArgoCD Applications to sync (delegates to the shared sync task).

**Example usage in a Stage:**

```yaml
promotionTemplate:
  spec:
    vars:
      - name: srcPath
        value: ./src
      - name: component
        value: my-component
      - name: targetRing
        value: ring-1
    steps:
      # Step 1: Clone the repository
      - uses: git-clone
        as: clone
        config:
          repoURL: https://github.com/redhat-appstudio/infra-deployments.git
          checkout:
            - branch: main
              path: ${{ vars.srcPath }}

      # Step 2: Apply component-specific changes (unique per component)
      - task:
          name: promote-my-component
        as: promote
        vars:
          - name: srcPath
            value: ${{ vars.srcPath }}

      # Step 3: Shared git workflow (identical for all components)
      - task:
          name: git-workflow-infra-deployments
        as: git-workflow
        vars:
          - name: srcPath
            value: ${{ vars.srcPath }}
          - name: component
            value: ${{ vars.component }}
          - name: targetRing
            value: ${{ vars.targetRing }}
          - name: skipProwChecks
            value: "true"
          - name: clusters
            value: "stone-stg-rh01|stone-stage-p01"
```

## Adding a New Shared Promotion Task

1. Create a new PromotionTask YAML file in this directory. 2. Add the filename to the `resources` list in `kustomization.yaml`. 3. Validate that the task builds correctly in at least one project:
   ```bash
   kustomize build components/kargo/internal-production/projects/<project>/
   ```
4. Document the task's variables, behavior, and usage in this README.

## Anti-Patterns

- **Do not copy shared tasks into project directories.** If the shared task
  does not support a required variable, add the variable to the shared task
  definition with a sensible default rather than forking the task.
- **Do not inline the git workflow steps in stage definitions.** Always
  delegate to `git-workflow-infra-deployments` to ensure consistency and
  reduce maintenance burden.
