# Configure verification

[Production overview](../README.md) · [Onboarding](onboarding.md) · [Operations](operations.md)

Kargo uses Argo Rollouts AnalysisTemplates for a Stage's configured
post-promotion verification. Kargo creates an AnalysisRun from the referenced
templates; its result contributes to Freight verification in that Stage.
Downstream eligibility also depends on the downstream Stage's sources, approvals
and soak settings. Deployment health, analysis success and elapsed soak are
separate checks.

## Available definitions

All six projects include [shared/verifications](../shared/verifications/kustomization.yaml)
as a Kustomize Component. The templates are created in each project's namespace;
a Stage only runs those it explicitly references. Multiple referenced templates
contribute to an AnalysisRun, not one independent run per template.

| Definition | Purpose |
|---|---|
| [kanary-staging](../shared/verifications/kanary-staging.yaml) | Queries staging RHOBS for the configured Kanary clusters and types |
| [kanary-production](../shared/verifications/kanary-production.yaml) | Queries production RHOBS for the configured Kanary clusters and types |
| [Konflux conformance](../shared/verifications/konflux-conformance-tests/README.md) | Existing remote conformance execution and its credential dependencies |

Kanary's active metric is `kanary-up`; commented metric examples do not execute.
Read the live templates for timing and thresholds. The staging template takes
repeated measurements, rather than declaring success after one healthy sample.
Kanary targets describe available test signals and can differ from the complete
Application list checked by promotion readiness. See the
[Operator Ring 1 Stage](../projects/kargo-konflux-core/components/konflux-operator/stages/ring-1-stage.yaml)
for a maintained example combining verification with promotion steps.

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

### Reusable across projects

Add to `shared/verifications/` and list in its `kustomization.yaml`:

```yaml
# shared/verifications/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1alpha1
kind: Component
resources:
  - kanary-staging.yaml
  - kanary-production.yaml
  - konflux-conformance-tests
  - verify-<new-template>.yaml   # add here
```

Adding a resource to this Component makes it available in every importing
project; it does not opt any Stage into execution. Review its dependencies and
namespace scope first. Keep a template used by one component with that component.

---

## Secrets for custom verifications

If your template needs credentials (OAuth2, API keys), first check for an
existing authorized project-local reference. For a new component-specific
credential, the example below shows an ExternalSecret in the project namespace;
its Vault path is a placeholder and requires the appropriate store access.

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

**Existing shared credentials** are deployed once from
[platform/credentials](../platform/credentials/kustomization.yaml) into
`kargo-shared-resources`. RHOBS and conformance definitions carry replication
annotations so their consumers can resolve project-local secret references.
Reuse the intended existing reference where applicable. A new shared credential
requires an explicit decision about consumers and replication; including an
AnalysisTemplate does not itself grant secret access. Do not add the central
credentials Kustomization as a per-project Component.

---

## Tuning verification timing

| Field | Meaning to review |
|---|---|
| `initialDelay` | Delay before the first measurement |
| `interval` | Time between measurements |
| `count` | Configured number of measurements, where specified |
| `consecutiveSuccessLimit` | Consecutive successes needed where this mode is configured |
| `failureLimit` | Allowed failed measurements before the analysis fails |

The example above illustrates fields, not a production timing recommendation.
Copy neither its timing nor another component's targets without checking rollout
duration and signal coverage. Read both success and failure conditions, including
what empty query results mean. Verification duration is distinct from a Stage's
`requiredSoakTime`.

---

## Multi-metric templates

A template can contain multiple gating metrics. Each must satisfy its configured
completion criteria for successful analysis. These query fragments omit common
provider/authentication settings; they are not complete templates:

```yaml
metrics:
  - name: error-rate-ok
    successCondition: len(result) > 0 && result[0] < 0.01
    provider:
      prometheus:
        query: |
          rate(my_errors_total[5m])

  - name: latency-ok
    successCondition: len(result) > 0 && result[0] < 0.5
    provider:
      prometheus:
        query: |
          histogram_quantile(0.99, rate(my_request_duration_seconds_bucket[5m]))
```

---

## Debugging

```sh
# list analysis runs in the project; identify the run referenced by the Stage
kubectl get analysisruns -n <project-namespace>

# describe to see metric results and error messages
kubectl describe analysisrun <run-name> -n <project-namespace>
```

Common failures:
- **OAuth2 token fetch fails** — check the secret name and vault key in ExternalSecret
- **Query returns 0 results** — metric labels may not match; inspect the RHOBS query manually
- **Early failures** — compare rollout timing with the query and measurement schedule before changing thresholds
- **No AnalysisRun** — inspect template references, Rollouts integration and RBAC as described in [operations](operations.md#cross-cluster-connections)
