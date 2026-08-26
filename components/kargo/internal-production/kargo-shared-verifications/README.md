# kargo-shared-verifications

Kustomize Component that provides shared Argo Rollouts AnalysisTemplates to all
Kargo projects. These templates run post-promotion verification to confirm
components are healthy before advancing to the next ring.

## Templates

| Template | File | Environment | RHOBS Endpoint | Secret |
| -------- | ---- | ----------- | -------------- | ------ |
| `kanary-staging` | `kanary-staging.yaml` | Staging | `observatorium-mst.api.stage.openshift.com` | `kargo-rhobs-staging` |
| `kanary-production` | `kanary-production.yaml` | Production | `observatorium-mst.api.openshift.com` | `kargo-rhobs-production` |

Both query the `kanary_up` metric from RHOBS (Observatorium) via PromQL to verify
that the Kanary sidecar reports all target clusters as healthy after promotion.

## Dependencies

- `kargo-rhobs-staging` secret — RHOBS staging OAuth2 client credentials
- `kargo-rhobs-production` secret — RHOBS production OAuth2 client credentials

These secrets must exist in each project namespace. They should be added to
`kargo-shared-secrets` when these verifications are used across all projects.

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

- AnalysisTemplates shared across **all** Kargo projects
- Generic verification templates parameterized via args

## What does NOT belong here

- Component-specific verifications
- Templates used by only one project

## Usage

In a project's top-level `kustomization.yaml`:

```yaml
components:
  - ../../kargo-shared-verifications
```
