# Custom Kargo Verifications

Kargo uses Argo Rollouts **AnalysisTemplates** for post-promotion verification.
After a stage's promotion steps complete, Kargo runs the referenced templates and
only marks the stage healthy (allowing the next ring to soak or be promoted) if all
metrics pass.

---

## How verification works in Kargo

```
Promotion completes
      │
      ▼
AnalysisRun created (per template in spec.verification)
      │
      ├── metric: kanary-up  ──► query RHOBS ──► success/failure
      └── metric: kanary-error ─► query RHOBS ──► success/failure
      │
      ▼
All metrics pass? ──YES──► Stage marked Healthy
                  ──NO───► Stage fails, no downstream promotion
```

Templates are scoped to the project namespace. Each project receives copies from
`kargo-shared-verifications` (via Kustomize Component) so they land in the correct namespace automatically.

---

## Shared templates (available in all projects)

| Template | When to use |
|----------|-------------|
| `kanary-staging` | Ring-1 (staging clusters) |
| `kanary-production` | Rings 2–4 (production clusters) |

Both query the Kanary sidecar metric from RHOBS (Observatorium). See
[`kargo-shared-verifications/README.md`](../kargo-shared-verifications/README.md).

---

## Creating a custom AnalysisTemplate

Use a custom template when:
- The shared Kanary templates don't cover your component's health signals
- You need component-specific metrics (error rate, latency, custom business metric)
- You want to query a different Prometheus endpoint

### Template anatomy

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AnalysisTemplate
metadata:
  name: verify-<component>-<environment>
spec:
  args:
    # Parameterize anything that varies between stages
    - name: clusters
    - name: expected-cluster-count
    - name: namespace
      value: my-component-namespace   # default, overridable per stage

    # OAuth2 credentials (pull from a secret)
    - name: oauth-client-id
      valueFrom:
        secretKeyRef:
          name: my-component-metrics-secret
          key: client_id
    - name: oauth-client-secret
      valueFrom:
        secretKeyRef:
          name: my-component-metrics-secret
          key: client_secret

  metrics:
    - name: my-metric
      initialDelay: 10m          # wait before first query (let deployment settle)
      interval: 10m              # re-query interval
      consecutiveSuccessLimit: 1 # how many consecutive passes to declare success
      failureLimit: 1            # how many failures before giving up
      provider:
        prometheus:
          address: https://my-prometheus-endpoint/api/metrics/v1/my-tenant
          authentication:
            oauth2:
              clientId: '{{args.oauth-client-id}}'
              clientSecret: '{{args.oauth-client-secret}}'
              scopes:
                - profile
              tokenUrl: https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token
          query: |
            count(
              my_metric{namespace="{{args.namespace}}", cluster=~"{{args.clusters}}"}
              > 0
            )
          timeout: 40
      successCondition: len(result) > 0 && result[0] == {{args.expected-cluster-count}}
```

### Referencing from a stage

```yaml
spec:
  verification:
    analysisTemplates:
      - name: verify-<component>-staging
    args:
      - name: clusters
        value: stone-stg-rh01|stone-stage-p01
      - name: expected-cluster-count
        value: "2"
      - name: namespace
        value: my-component-namespace
```

---

## Where to put the template

### Component-specific (used by one component only)

Place it in the component directory and reference it from `kustomization.yaml`:

```
projects/<project>/components/<component>/
  verify-<component>-staging.yaml
  kustomization.yaml   ← add it to resources:
```

```yaml
# kustomization.yaml
resources:
  - <component>-wh.yaml
  - promotiontask.yaml
  - verify-<component>-staging.yaml
  - stages
```

### Shared across all projects

Add to `kargo-shared-verifications/` and list in its `kustomization.yaml`:

```yaml
# kargo-shared-verifications/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1alpha1
kind: Component
resources:
  - kanary-staging.yaml
  - kanary-production.yaml
  - verify-<new-template>.yaml   # add here
```

Only add shared templates if they apply to **all** projects. See
[`kargo-shared-verifications/README.md`](../kargo-shared-verifications/README.md)
for the boundary.

---

## Secrets for custom verifications

If your template needs credentials (OAuth2, API keys), create an ExternalSecret in
the project namespace.

**Component-specific secret** — add to the component directory:
```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: my-component-metrics-secret
spec:
  refreshInterval: 15m
  secretStoreRef:
    kind: ClusterSecretStore
    name: appsre-stonesoup-vault
  dataFrom:
    - extract:
        key: production/devprod/my-component-metrics
  target:
    name: my-component-metrics-secret
    creationPolicy: Owner
    deletionPolicy: Delete
```

**Shared secret** — add to `kargo-shared-secrets/` if used by multiple projects.
See [`kargo-shared-secrets/README.md`](../kargo-shared-secrets/README.md).

---

## Tuning verification timing

| Field | Purpose | Typical value |
|-------|---------|---------------|
| `initialDelay` | Wait before first query — give the deployment time to roll out | `10m` staging, `40m` production |
| `interval` | How often to re-query after the first check | `10m`–`40m` |
| `consecutiveSuccessLimit` | How many passes in a row to call it healthy | `1` (single pass is usually enough) |
| `failureLimit` | Failures allowed before declaring the analysis failed | `1` |

For production rings where rollout is slow across many clusters, use longer
`initialDelay` (e.g. `40m`) to avoid false negatives on the first query.

---

## Multi-metric templates

You can have multiple metrics in one template — **all must pass** for the
AnalysisRun to succeed:

```yaml
metrics:
  - name: error-rate-ok
    successCondition: result[0] < 0.01
    provider:
      prometheus:
        query: |
          rate(my_errors_total[5m])

  - name: latency-ok
    successCondition: result[0] < 0.5
    provider:
      prometheus:
        query: |
          histogram_quantile(0.99, rate(my_request_duration_seconds_bucket[5m]))
```

---

## Debugging a failed AnalysisRun

```sh
# list analysis runs for a stage
kubectl get analysisruns -n <project-namespace>

# describe to see metric results and error messages
kubectl describe analysisrun <run-name> -n <project-namespace>
```

Common failures:
- **OAuth2 token fetch fails** — check the secret name and vault key in ExternalSecret
- **Query returns 0 results** — metric labels may not match; inspect the RHOBS query manually
- **initialDelay too short** — pods still starting when first query fires; increase delay
