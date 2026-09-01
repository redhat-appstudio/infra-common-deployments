# Conformance E2E Analysis Templates

Post-promotion verification for Kargo stages. After a promotion succeeds,
Kargo runs these AnalysisTemplates to verify the target cluster is healthy
before proceeding to the next ring.

## Architecture

```
Kargo Cluster                          Target Cluster (e.g. stone-stage-p01)
┌──────────────────────┐               ┌───────────────────────────────────┐
│  AnalysisRun         │               │                                   │
│  └─ Launcher Job     │               │  konflux-managed-tests (runner)   │
│     (ubi-minimal)    │               │  ├─ conformance-test-runner SA    │
│                      │  kubectl      │  └─ PipelineRun                  │
│     1. Read vault    │──create──────▶│     └─ go test ./conformance/... │
│        credentials   │               │                                   │
│     2. Create PLR    │               │  konflux-conformance-tests (apps) │
│     3. Poll status   │               │  ├─ Application                   │
│                      │               │  ├─ Component                     │
│                      │               │  ├─ IntegrationTestScenario       │
│                      │               │  └─ PipelineRun (build)           │
└──────────────────────┘               └───────────────────────────────────┘
```

## Files

| File | Kind | Purpose |
|------|------|---------|
| `conformance-konflux-e2e.yaml` | AnalysisTemplate | Launcher Job that creates and monitors a PipelineRun on the target cluster |
| `conformance-pipelinerun-template.yaml` | ConfigMap | PipelineRun manifest template with placeholders replaced at runtime |

## Namespaces

| Namespace | Role |
|-----------|------|
| `konflux-managed-tests` | PipelineRun execution namespace. The `conformance-test-runner` SA lives here. Also used as `E2E_MANAGED_NAMESPACE` for managed resources (build pipelines, image repos). |
| `konflux-conformance-tests` | Application namespace. Test applications, components, snapshots, and integration test scenarios are created here (`E2E_APPLICATIONS_NAMESPACE`). |

## Service Accounts

| SA | Namespace | Permissions | Purpose |
|----|-----------|-------------|---------|
| `konflux-bot-0` | `konflux-managed-tests` | `konflux-builder-bot-actions` | Launcher authenticates as this SA to create PipelineRuns |
| `conformance-test-runner` | `konflux-managed-tests` | `konflux-admin-user-actions` (both ns) + extra RBAC | Runs the actual conformance tests inside the PipelineRun |

## Secrets

Stored in Vault, synced via ExternalSecret to the Kargo cluster:

| Secret Key | Content |
|------------|---------|
| `konflux-conformance-<cluster-name>` | `{"token": "<konflux-bot-0 SA token>"}` |
| `konflux-conformance-tests-credentials` | `{"github_pat": "<GitHub PAT>"}` |

## Template Placeholders

The launcher replaces these in the ConfigMap template before creating the PipelineRun:

| Placeholder | Source | Example |
|-------------|--------|---------|
| `__RUN_ID__` | Generated at runtime | `conformance-stone-stage-p01-a3f1bc09` |
| `__RUNNER_NS__` | `RUNNER_NAMESPACE` env | `konflux-managed-tests` |
| `__APP_NS__` | `APP_NAMESPACE` env | `konflux-conformance-tests` |
| `__GITHUB_TOKEN__` | Vault secret | `ghp_...` |

## RBAC Requirements (infra-deployments)

The following RBAC must exist on each target cluster (managed by
`infra-deployments/components/konflux-verifications-rd/`):

- `conformance-test-runner` SA in `konflux-managed-tests`
- `konflux-admin-user-actions` RoleBinding in both namespaces
- `conformance-test-runner-extra` Role+RoleBinding in both namespaces
  (grants `pods/delete`, `batch/jobs` CRUD, `rbac.authorization.k8s.io/roles+rolebindings` CRUD)

## Adding to Other Kargo Projects

To enable conformance verification in another project, add the
`analysis-templates` directory with these two files to the project's
`base/` directory and reference it from `kustomization.yaml`.
