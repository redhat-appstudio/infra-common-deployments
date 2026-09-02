# Shared Verifications

## Overview

This directory is a Kustomize Component that provides AnalysisTemplates for post-promotion verification. After a Promotion successfully deploys Freight to a Stage, Kargo creates an AnalysisRun from the templates referenced in the Stage's `spec.verification` block. All referenced templates run in parallel.

Verification results determine whether Freight is marked as `VerifiedIn` for the Stage, which gates its availability for promotion to downstream rings.

## Usage

Projects include this component in their `kustomization.yaml`:

```yaml
components:
  - ../../kargo-shared-verifications
```

**Important:** Do not create project-level copies of these AnalysisTemplates. Duplicating them causes resource name conflicts during Kustomize builds and makes it impossible to apply fixes in a single location.

## Included AnalysisTemplates

### `kanary-staging`

Validates that kanary smoke test probes are healthy across all expected staging clusters by querying the `kanary_up` Prometheus metric from the staging RHOBS Observatorium instance.

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `clusters` | Yes | (none) | A pipe-delimited regex of cluster names to check (e.g., `stone-stg-rh01\|stone-stage-p01`). |
| `expected-cluster-count` | Yes | (none) | The number of clusters that must report a healthy kanary probe for the check to pass. |
| `namespace` | No | `konflux-otel` | The Kubernetes namespace where kanary probes are deployed on each cluster. |
| `types` | No | `container-single-arch` | A regex filter for kanary probe types to include in the query. |

| Timing Property | Value |
| --- | --- |
| Initial delay | 40 minutes |
| Poll interval | 40 minutes |
| Consecutive successes required | 1 |
| Maximum failures allowed | 1 |

**Authentication:** OAuth2 using `client_id` and `client_secret` from the `kargo-rhobs-staging` shared secret. Token endpoint: `https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token`.

**Prometheus query:**
```promql
count(
  min by (tested_cluster) (
    kanary_up{namespace="<namespace>", type=~"<types>", tested_cluster=~"<clusters>"}
  ) == 1
)
```

The query returns the count of clusters where all kanary probes report `kanary_up == 1`. The success condition checks that this count equals `expected-cluster-count`.

---

### `kanary-production`

Identical to `kanary-staging` but queries the production RHOBS Observatorium instance.

| Property | Staging | Production |
| --- | --- | --- |
| Prometheus address | `https://observatorium-mst.api.stage.openshift.com/api/metrics/v1/rhtap` | `https://observatorium-mst.api.openshift.com/api/metrics/v1/rhtap` |
| OAuth2 credentials secret | `kargo-rhobs-staging` | `kargo-rhobs-production` |

All arguments and timing properties are the same as `kanary-staging`.

---

### `konflux-conformance-tests-stone-stage-p01`

Runs the Konflux conformance end-to-end test suite against the `stone-stage-p01` staging cluster. The test creates a PipelineRun on the target cluster that clones the `konflux-ci/konflux-ci` repository, compiles the Ginkgo test binary, and executes the conformance test scenarios.

**Execution flow:**

1. A Job is created using the `quay.io/konflux-ci/task-runner:3.1.2` image. 2. The Job reads the service account token for `stone-stage-p01` from the
   `konflux-conformance-sa` shared secret.
3. The Job reads the GitHub PAT from the
   `konflux-conformance-tests-credentials` shared secret.
4. The Job constructs a kubeconfig for the target cluster and creates a
   PipelineRun from the `conformance-pipelinerun-template` ConfigMap.
5. The Job polls the PipelineRun status until it completes or times out. 6. A `Succeeded` PipelineRun results in a passing metric; any other outcome
   fails the verification.

**Required secrets:**

| Secret Name | Source | Purpose |
| --- | --- | --- |
| `konflux-conformance-sa` | `kargo-shared-secrets` | Per-cluster service account tokens for authenticating to staging clusters. |
| `konflux-conformance-tests-credentials` | `kargo-shared-secrets` | GitHub PAT for cloning the test repository during PipelineRun execution. |

**Required ConfigMap:**

| ConfigMap Name | Source | Purpose |
| --- | --- | --- |
| `conformance-pipelinerun-template` | `kargo-shared-verifications/konflux-conformance-tests/` | YAML template for the PipelineRun that executes the conformance tests. |

| Timing Property | Value |
| --- | --- |
| Initial delay | 2 minutes |
| Maximum failures allowed | 0 (any failure fails the verification) |
| Job timeout | 3600 seconds (1 hour) |

## Referencing Verifications in a Stage

Add the desired templates to the Stage's `spec.verification` block:

```yaml
spec:
  verification:
    analysisTemplates:
      - name: kanary-staging
      - name: konflux-conformance-tests-stone-stage-p01
    args:
      - name: clusters
        value: stone-stg-rh01|stone-stage-p01
      - name: expected-cluster-count
        value: "2"
```

All listed templates run in parallel as part of a single AnalysisRun. The Freight is marked as verified only when every template's metrics pass.

**Note:** The `args` block is shared across all templates in the same verification block. Ensure that argument names do not collide between templates, or use template-specific arguments with distinct names.

## Adding a New Verification Template

1. Create the AnalysisTemplate YAML file in this directory (or in a
   subdirectory if it requires supporting resources such as ConfigMaps).
2. Add the filename or subdirectory to the `resources` list in
   `kustomization.yaml`.
3. Reference the template by name in the target Stage's
   `spec.verification.analysisTemplates` list.
4. Validate the build:
   ```bash
   kustomize build components/kargo/internal-production/projects/<project>/
   ```
5. Document the template's arguments, timing properties, required secrets,
   and behavior in this README.

## Anti-Patterns

- **Do not duplicate shared templates in project directories.** This causes
  Kustomize build failures due to duplicate resource names and prevents
  centralized updates.
- **Do not set `failureLimit` to a high value to make a template
  "optional."** If a verification should not block promotion, remove it from
  the Stage's verification block rather than silencing its failures.
