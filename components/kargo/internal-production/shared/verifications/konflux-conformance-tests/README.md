# Konflux Conformance Tests

Post-promotion verification that runs the Konflux conformance test suite
against staging clusters after Kargo promotes a component.

<!-- mdformat-toc start --slug=github --no-anchors --maxlevel=3 --minlevel=2 -->

- [Architecture](#architecture)
- [Files](#files)
- [Configuration reference](#configuration-reference)
  - [Launcher Job (AnalysisTemplate)](#launcher-job-analysistemplate)
  - [PipelineRun (test step)](#pipelinerun-test-step)
  - [Secrets](#secrets)
- [Kargo integration](#kargo-integration)
- [Running locally](#running-locally)
  - [Prerequisites](#prerequisites)
  - [Step-by-step](#step-by-step)
- [Adding a new cluster](#adding-a-new-cluster)
- [Extending the tests](#extending-the-tests)
- [Troubleshooting](#troubleshooting)

<!-- mdformat-toc end -->

## Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│ Kargo Cluster (production)                                         │
│                                                                    │
│  Stage: ring-1-konflux-operator                                    │
│  ├── promotionTemplate                                             │
│  │   └── PR → CI → merge → verify-argocd-deployment               │
│  │                                                                 │
│  └── spec.verification  (runs after promotionTemplate completes)   │
│      ├── kanary-staging                    [parallel]              │
│      └── konflux-conformance-tests         [parallel]              │
│                │                                                   │
│                ▼                                                   │
│      Launcher Job  (quay.io/konflux-ci/task-runner)                │
│      ├── reads konflux-conformance-sa (ExternalSecret ← Vault)    │
│      ├── builds kubeconfig for target cluster                      │
│      └── creates PipelineRun, polls status, exits 0/1             │
│                                                                    │
│      all metrics pass → Kargo marks freight verified               │
└──────────────────────────────┬─────────────────────────────────────┘
                               │  kubectl create / poll status
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│ Target Staging Cluster                                             │
│                                                                    │
│  ns: konflux-managed-tests                                         │
│  └── PipelineRun                                                   │
│      ├── SA: conformance-test-runner                               │
│      └── step: tests                                               │
│          image: quay.io/konflux-ci/conformance-tests               │
│          └── /usr/local/bin/conformance.test                       │
│              -ginkgo.vv -test.timeout 45m -test.count 1            │
│                       │ creates resources                          │
│                       ▼                                            │
│  ns: konflux-conformance-tests                                     │
│  └── Applications, Components, PipelineRuns                        │
│      (created and cleaned up per test run)                         │
└────────────────────────────────────────────────────────────────────┘
```

### Flow

1. Kargo promotes a component to ring-1 (staging)
2. After promotion succeeds, Kargo creates an **AnalysisRun** as a verification gate
4. The AnalysisRun creates a **Launcher Job** on the Kargo cluster
5. The Launcher Job:
   - Reads the `konflux-bot-0` SA token from the `konflux-conformance-sa` secret
   - Builds a kubeconfig targeting the staging cluster
   - Substitutes placeholders in the PipelineRun template ConfigMap
   - Creates a **PipelineRun** on the staging cluster that builds and tests a real Konflux application end-to-end
   - Polls until the PipelineRun succeeds or fails (every `POLL_INTERVAL` seconds)
6. The PipelineRun on the staging cluster:
   - Runs as `conformance-test-runner` SA in `konflux-managed-tests`
   - Uses image `quay.io/konflux-ci/conformance-tests` — pre-compiled Ginkgo binary with `oc`/`kubectl` bundled
   - Entrypoint `/usr/local/bin/conformance.test` runs the suite with `-ginkgo.vv -test.timeout 45m -test.count 1`
7. Launcher exits 0 (pass) or 1 (fail); when the AnalysisRun passes, Kargo marks freight verified for that Stage

## Files

| File | Purpose |
|------|---------|
| `konflux-conformance-tests-stone-stage-p01.yaml` | AnalysisTemplate for `stone-stage-p01` — hardcoded cluster URL and credentials reference |
| `conformance-pipelinerun-template.yaml` | ConfigMap containing the Tekton PipelineRun template; Launcher substitutes `__PLACEHOLDER__` values at run time |
| `kustomization.yaml` | Lists both resources above |

## Configuration reference

### Launcher Job (AnalysisTemplate)

These env vars are set directly in the AnalysisTemplate for each cluster file:

| Variable | Example value | Description |
|----------|---------------|-------------|
| `CLUSTER_URL` | `https://api.stone-stage-p01.hpmt.p1.openshiftapps.com:6443` | API server URL of the target staging cluster |
| `CLUSTER_NAME` | `stone-stage-p01` | Short name; used to look up the credential key in the `konflux-conformance-sa` secret and as the `CLUSTER_NAME` in log output |
| `RUNNER_NAMESPACE` | `konflux-managed-tests` | Namespace on the staging cluster where the PipelineRun is created and the `conformance-test-runner` SA lives |
| `APP_NAMESPACE` | `konflux-conformance-tests` | Namespace on the staging cluster where test Applications/Components are created |
| `POLL_INTERVAL` | `30` | Seconds between PipelineRun status polls |

The Launcher also reads these **template placeholders** from the ConfigMap and substitutes at run time:

| Placeholder | Source |
|-------------|--------|
| `__RUN_ID__` | Generated: `conformance-<CLUSTER_NAME>-<4-hex-chars>` |
| `__RUNNER_NS__` | `RUNNER_NAMESPACE` env var |
| `__APP_NS__` | `APP_NAMESPACE` env var |
| `__GITHUB_TOKEN__` | `github_pat` field from the `konflux-conformance-tests-credentials` key in the secret |

### PipelineRun (test step)

These env vars are passed to the `quay.io/konflux-ci/conformance-tests` container
and consumed by the pre-compiled Ginkgo binary:

| Variable | Value | Description |
|----------|-------|-------------|
| `E2E_APPLICATIONS_NAMESPACE` | `__APP_NS__` → substituted at launch | Tenant namespace where test Applications/Components are created |
| `E2E_MANAGED_NAMESPACE` | `__RUNNER_NS__` → substituted at launch | Managed/release namespace |
| `MY_GITHUB_ORG` | `konflux-ci` | GitHub org owning the test repos |
| `E2E_REPO` | `testrepo-private` | Private test repo used in PaC build flows |
| `E2E_ITS_REPO` | `testrepo` | Public integration test repo |
| `TEST_ENVIRONMENT` | `upstream` | Tells the suite to target upstream Konflux (not OpenShift-specific paths) |
| `GITHUB_TOKEN` | `__GITHUB_TOKEN__` → substituted at launch | GitHub PAT for managing PRs in test repos |
| `CUSTOM_DOCKER_BUILD_OCI_TA_MIN_PIPELINE_BUNDLE` | Optional — if unset, the binary uses the value baked in at image build time from the operator manifest at the same commit | Override the pipeline bundle digest for docker-build-oci-ta-min |

### Secrets

All credentials come from a single Kubernetes Secret named `konflux-conformance-sa`
(synced from AppSRE Vault via ExternalSecret). Each cluster has its own JSON-encoded key
inside that secret:

| Secret key | JSON field | Purpose |
|------------|------------|---------|
| `konflux-conformance-<cluster-name>` | `token` | Token for `konflux-bot-0` SA on the target cluster — used by the Launcher to create the PipelineRun |
| `konflux-conformance-tests-credentials` | `github_pat` | GitHub PAT for cloning private repos and opening PRs |

> **Vault:** the `konflux-bot-0` token is minted manually via `oc create token`
> on each staging cluster and stored in AppSRE Vault as key
> `konflux-conformance-<cluster-name>` (JSON `{"token": "..."}`) in the path
> used by the ExternalSecret. It is then synced into the `konflux-conformance-sa`
> Secret on the Kargo cluster. Do not commit credential values to git.

#### Tenant prerequisites on the staging cluster

The namespaces, SAs, and RBAC on each staging cluster are managed by ArgoCD
syncing `infra-deployments/components/konflux-verifications-rd/`. Do not
create these manually. The component deploys:

- Namespace `konflux-managed-tests` — PipelineRun executor namespace
- Namespace `konflux-conformance-tests` — test Application/Component namespace
- ServiceAccount `konflux-bot-0` in `konflux-managed-tests` — the Launcher authenticates as this SA to create PipelineRuns; its token is pushed to Vault via PushSecret
- ServiceAccount `conformance-test-runner` in `konflux-managed-tests` — PipelineRun runs as this SA; it holds `konflux-admin-user-actions` in both namespaces plus extra RBAC for pods/jobs/roles

## Kargo integration

Conformance tests run as one of two verification metrics on a Stage. In
`kargo-konflux-core`, `ring-1-konflux-operator` uses both `kanary-staging`
(RHOBS Kanary signal) and the conformance template together:

```yaml
spec:
  verification:
    analysisTemplates:
      - name: kanary-staging
      - name: konflux-conformance-tests-stone-stage-p01
    args:
      - name: clusters
        value: stone-stage-p01
      - name: expected-cluster-count
        value: "1"
      - name: types
        value: container-single-arch|container-multi-arch
```

Both metrics run in parallel inside the same AnalysisRun. Kargo marks freight
verified only when **all** metrics pass.

Verification fires after the full `promotionTemplate` completes — the Stage
runs PR open → CI wait → merge → `verify-argocd-deployment` (waits for ArgoCD
sync), and only then creates the AnalysisRun. If any metric's Launcher Job
exits non-zero, Kargo marks the freight unverified and blocks further promotion.

The AnalysisTemplates land in the Kargo project namespace via ArgoCD: the
`shared/verifications` Kustomize component is included in the project
`kustomization.yaml`, and `base/rbac/analysis-template-rbac.yaml` grants
ArgoCD's application controller permission to create/update `AnalysisTemplate`
resources in that namespace.

## Running locally

Local runs skip the Launcher Job entirely — pull the pre-built image and run it
directly against a staging cluster.

### Prerequisites

- `kubectl` or `oc` pointing at a staging cluster where:
  - Namespace `konflux-managed-tests` exists
  - Namespace `konflux-conformance-tests` exists (or any tenant namespace)
  - ServiceAccount `conformance-test-runner` exists in `konflux-managed-tests` with appropriate RBAC
- A GitHub PAT with repo/PR permissions on `konflux-ci/testrepo` and `konflux-ci/testrepo-private`
- `KUBECONFIG` set to a kubeconfig that authenticates as (or can impersonate) an appropriately scoped user
- `podman` or `docker` available locally, or use `kubectl run` to execute on-cluster

### Step-by-step

```bash
# Pull the image (use the digest/tag matching your deployed operator version)
IMAGE=quay.io/konflux-ci/conformance-tests:latest

# Run the pre-compiled binary via podman
podman run --rm \
  -e KUBECONFIG=/etc/creds/kubeconfig \
  -e GITHUB_TOKEN=<your-github-pat> \
  -e MY_GITHUB_ORG=konflux-ci \
  -e E2E_REPO=testrepo-private \
  -e E2E_ITS_REPO=testrepo \
  -e TEST_ENVIRONMENT=upstream \
  -e E2E_APPLICATIONS_NAMESPACE=konflux-conformance-tests \
  -e E2E_MANAGED_NAMESPACE=konflux-managed-tests \
  -v "${KUBECONFIG}:/etc/creds/kubeconfig:ro,z" \
  "${IMAGE}" \
  -ginkgo.vv -test.timeout 45m -test.count 1
```

Alternatively, run on-cluster (same pattern the Launcher uses — useful when
the test workload needs to reach cluster-internal services):

```bash
IMAGE=quay.io/konflux-ci/conformance-tests:latest

kubectl create secret generic conformance-local-creds \
  --namespace=konflux-managed-tests \
  --from-file=kubeconfig="${KUBECONFIG}" \
  --from-literal=GITHUB_TOKEN=<your-github-pat>

kubectl run conformance-local \
  --namespace=konflux-managed-tests \
  --image="${IMAGE}" \
  --restart=Never \
  --env=KUBECONFIG=/etc/creds/kubeconfig \
  --env=GITHUB_TOKEN_FROM_SECRET=ignored \   # overridden via --overrides if needed
  -- -ginkgo.vv -test.timeout 45m -test.count 1

kubectl logs -f conformance-local --namespace=konflux-managed-tests
kubectl delete pod conformance-local --namespace=konflux-managed-tests
kubectl delete secret conformance-local-creds --namespace=konflux-managed-tests
```

## Adding a new cluster

### 1. Deploy tenant resources on the staging cluster

Add a directory under
[`infra-deployments/components/konflux-verifications-rd/rings/ring-1/`](https://github.com/redhat-appstudio/infra-deployments/tree/main/components/konflux-verifications-rd/rings/ring-1)
for the new cluster:

```bash
mkdir -p components/konflux-verifications-rd/rings/ring-1/<new-cluster>
cat > components/konflux-verifications-rd/rings/<ring-number>/<new-cluster>/kustomization.yaml <<EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ../base
EOF
```

This deploys (via ArgoCD sync) the `konflux-managed-tests` and
`konflux-conformance-tests` namespaces, the `konflux-bot-0` and
`conformance-test-runner` SAs, and all required RBAC to the new cluster.

### 2. Create and store the Vault token

Once ArgoCD has synced the new cluster's resources:

```bash
# Mint a token for the bot SA on the target cluster
oc create token konflux-bot-0 \
  --namespace=konflux-managed-tests \
  --duration=8760h          # 1 year; adjust per policy
```

Store the token in AppSRE Vault under the key:

```
konflux-conformance-<new-cluster>
```

The value must be a JSON object with a `token` field:

```json
{"token": "<token-from-oc-create-token>"}
```

The ExternalSecret on the Kargo cluster will sync it into the
`konflux-conformance-sa` Secret automatically.

### 3. Add the AnalysisTemplate in this repo

```bash
cp konflux-conformance-tests-stone-stage-p01.yaml \
   konflux-conformance-tests-<new-cluster>.yaml
```

Update inside the new file:
- `metadata.name` → `konflux-conformance-tests-<new-cluster>`
- `CLUSTER_URL` env var → new cluster's API server URL
- `CLUSTER_NAME` env var → `<new-cluster>`

Add to `kustomization.yaml`:

```yaml
resources:
  - konflux-conformance-tests-<new-cluster>.yaml
```

### 4. Wire into the Stage verification

```yaml
verification:
  analysisTemplates:
    - name: kanary-staging
    - name: konflux-conformance-tests-<new-cluster>
  args:
    - name: clusters
      value: stone-stage-p01|<new-cluster>
    - name: expected-cluster-count
      value: "2"
    - name: types
      value: container-single-arch|container-multi-arch
```

## Extending the tests

Test source lives in `github.com/konflux-ci/konflux-ci` at
`test/go-tests/tests/conformance/`. The suite is Ginkgo-based.

To add tests for a new component:

1. Open a PR in `konflux-ci/konflux-ci`.
2. Add a new `_test.go` file (or extend an existing spec file) in `test/go-tests/tests/conformance/`.
3. Follow Ginkgo conventions used in the package: `Describe`/`It`/`Eventually`, `DeferCleanup` for resource teardown.
4. Use `E2E_APPLICATIONS_NAMESPACE` / `E2E_MANAGED_NAMESPACE` for namespace targeting — do not hardcode namespace names.
5. Test locally against a staging cluster (see [Running locally](#running-locally)) before submitting.
6. The next conformance test run in Kargo will pick up the new tests automatically once the PR merges to `main` and the conformance-tests image is rebuilt and promoted by Renovate.

> **No manifest change required here** unless you need a new env var in the
> PipelineRun. In that case, add it to `conformance-pipelinerun-template.yaml`.

## Troubleshooting

### Launcher Job logs

```bash
# Find the Job name from the AnalysisRun
kubectl get analysisrun -n <kargo-project-ns>

# Tail Launcher logs
kubectl logs -n <kargo-project-ns> \
  -l batch.kubernetes.io/job-name=<analysis-run-job> --tail=100
```

### PipelineRun on the staging cluster

```bash
# List recent conformance PipelineRuns
kubectl get pipelinerun -n konflux-managed-tests \
  -l app.kubernetes.io/part-of=kargo-conformance

# Get logs for a specific run
kubectl logs -n konflux-managed-tests \
  -l tekton.dev/pipelineRun=conformance-<cluster>-<suffix> --all-containers
```

### Common failures

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Launcher exits immediately with `jq: error` | Credential key missing in `konflux-conformance-sa` secret | Verify Vault has `konflux-conformance-<cluster>` key; check ExternalSecret sync status |
| Launcher exits with `Unauthorized` on `kubectl create` | `konflux-bot-0` token expired or wrong cluster URL | Remint token via `oc create token konflux-bot-0 -n konflux-managed-tests` on the target cluster, push to Vault; verify `CLUSTER_URL` matches actual API endpoint |
| PipelineRun never created | `konflux-bot-0` lacks `builder-bot-actions` in `konflux-managed-tests`, or `RUNNER_NAMESPACE` doesn't exist | Check `infra-deployments/components/konflux-verifications-rd/` deployed to the cluster; verify RBAC for `konflux-bot-0` |
| PipelineRun stuck in `Running` past 25 min | Flaky test or cluster overload | Check test-step logs for hung `Eventually` blocks; re-trigger AnalysisRun once |
| Tests fail inside container with `dial tcp: connection refused` | Test cluster unreachable from within the PipelineRun step | Check network policy / routing from `konflux-managed-tests` pod CIDR |
| Tests fail on `github.com/konflux-ci/testrepo-private: 404` | `GITHUB_TOKEN` lacks access to private repo | Rotate PAT in Vault; ensure token has `repo` scope on `konflux-ci` org |
| AnalysisRun never created by Kargo | Shard `controller.rollouts.integrationEnabled` not set, or ControllerInstanceID mismatch | See `components/kargo/README.md` → Shards section |

### Re-triggering a failed verification

Kargo does not automatically re-run a failed AnalysisRun. To retry:

1. Delete the failed AnalysisRun from the Kargo project namespace.
2. Kargo will create a fresh AnalysisRun on the next reconcile, or trigger one
   manually via the Kargo UI / CLI:
   ```bash
   kargo promote --project <project> --freight <freight-id> --stage <stage>
   ```
