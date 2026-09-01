# Konflux Conformance Tests

Post-promotion verification that runs the Konflux conformance test suite
against staging clusters after Kargo promotes a component.

## Architecture

```
Kargo Cluster                          Target Staging Cluster
┌──────────────────────┐               ┌──────────────────────────────┐
│  Stage verification  │               │  konflux-managed-tests       │
│  ──────────────────  │               │  ────────────────────────    │
│  AnalysisRun         │               │                              │
│   └─ Launcher Job    │──── creates ──│─▶ PipelineRun               │
│       (task-runner)  │    via K8s API │    └─ conformance-test-     │
│                      │               │       runner SA              │
│  Credentials:        │               │       └─ go test             │
│   konflux-conformance│               │          ./tests/            │
│   -sa (Vault secret) │               │          conformance/...     │
└──────────────────────┘               └──────────────────────────────┘
```

### Flow

1. Kargo promotes a component to ring-1 (staging)
2. After ArgoCD sync, the Stage triggers an AnalysisRun
3. The AnalysisRun creates a **Launcher Job** on the Kargo cluster
4. The Launcher Job:
   - Reads the bot SA token from the `konflux-conformance-sa` secret
   - Builds a kubeconfig targeting the staging cluster
   - Creates a **PipelineRun** on the staging cluster from the template
   - Polls until the PipelineRun succeeds or fails
5. The PipelineRun on the staging cluster:
   - Runs as `conformance-test-runner` SA
   - Clones `github.com/konflux-ci/konflux-ci`
   - Compiles and runs `go test ./tests/conformance/...`
6. Launcher exits 0 (pass) or 1 (fail) → Kargo marks freight as verified or not

## Files

| File | Purpose |
|------|---------|
| `konflux-conformance-tests-<cluster>.yaml` | Per-cluster AnalysisTemplate with hardcoded cluster URL and name |
| `conformance-pipelinerun-template.yaml` | ConfigMap with the Tekton PipelineRun YAML template |

## Adding a new cluster

1. Copy an existing `konflux-conformance-tests-<cluster>.yaml`
2. Rename to `konflux-conformance-tests-<new-cluster>.yaml`
3. Update inside the file:
   - `metadata.name` → `konflux-conformance-tests-<new-cluster>`
   - `CLUSTER_URL` → the new cluster's API server URL
   - `CLUSTER_NAME` → `<new-cluster>`
4. Add to `kustomization.yaml`
5. Reference in the Stage verification:
   ```yaml
   verification:
     analysisTemplates:
       - name: konflux-conformance-tests-<new-cluster>
   ```

## Secrets

The Launcher Job mounts the `konflux-conformance-sa` secret (synced from
Vault via ExternalSecret). Inside, each cluster has its own key:

- `konflux-conformance-<cluster-name>` — JSON with `token` field (bot SA token)
- `konflux-conformance-tests-credentials` — JSON with `github_pat` field

These are populated by PushSecret on the staging clusters
(`infra-deployments/konflux-verifications-rd`).

## Images

- **Launcher**: `quay.io/konflux-ci/task-runner` — has `oc`, `kubectl`, `jq`, `yq`
- **Test runner**: `registry.access.redhat.com/ubi10/go-toolset` — Go 1.26,
  compiles conformance tests at runtime

## Debugging

Check the Launcher Job logs:
```bash
kubectl logs -n <kargo-project-ns> -l batch.kubernetes.io/job-name=<analysis-run-job>
```

Check the PipelineRun on the staging cluster:
```bash
kubectl get pipelinerun -n konflux-managed-tests -l tekton.dev/pipelineRun=conformance-<cluster>-*
```
