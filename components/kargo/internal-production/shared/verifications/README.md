# Shared verifications

Kustomize Component that provides shared Argo Rollouts AnalysisTemplates to all
Kargo projects. These templates run post-promotion verification to confirm
components are healthy before advancing to the next ring.

## Templates

| Template | File | Environment | Endpoint | Secret |
| -------- | ---- | ----------- | -------------- | ------ |
| `kanary-staging` | `kanary-staging.yaml` | Staging | `observatorium-mst.api.stage.openshift.com` | `kargo-rhobs-staging` |
| `kanary-production` | `kanary-production.yaml` | Production | `observatorium-mst.api.openshift.com` | `kargo-rhobs-production` |
| `caching-proxy-regression-staging` | `caching-proxy-regression/` | Staging | Target cluster API | `vanguard-proxy-verification-sa` |

Both query the `kanary_up` metric from RHOBS (Observatorium) via PromQL to verify
that the Kanary sidecar reports all target clusters as healthy after promotion.

The [conformance verification](konflux-conformance-tests/) also includes its
AnalysisTemplate and a ConfigMap containing PipelineRun template data. Including
this Component supplies definitions; it does not launch tests until a Stage uses them.

The [caching proxy regression](caching-proxy-regression/) tests the deployed
proxy endpoint and tenant CA contract. Its initial Vanguard Warehouse watches
both proxy manifests and the selected staging cluster-config file.

## Dependencies

- `kargo-rhobs-staging` secret — RHOBS staging OAuth2 client credentials
- `kargo-rhobs-production` secret — RHOBS production OAuth2 client credentials
- `vanguard-proxy-verification-sa` secret — target-cluster launcher tokens

These secrets must exist in each project namespace. Their ExternalSecrets are
provisioned once under [platform credentials](../../platform/credentials/) and
selected generated Secrets are replicated to projects.

## Stage usage

```yaml
spec:
  verification:
    analysisTemplates:
      - name: kanary-staging   # or kanary-production for production rings (ring-2/3/4)
    args:
      - name: clusters
        value: stone-stg-rh01|stone-stage-p01
      - name: expected-cluster-count
        value: "2"
```

## What belongs here

- AnalysisTemplates shared across multiple Kargo projects
- Generic verification templates parameterized via args

## What does NOT belong here

- Verifications that cannot be reused across multiple projects
- Templates used by only one project

## Usage

In a project's top-level `kustomization.yaml`:

```yaml
components:
  - ../../shared/verifications
```
