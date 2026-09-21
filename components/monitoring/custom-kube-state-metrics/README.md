# Custom Kube State Metrics

Deploys a dedicated `kube-state-metrics` instance for exposing Prometheus metrics
from Kargo custom resources as part of SPRE-6674.

Uses `--custom-resource-state-only=true` to avoid duplicating platform metrics.

## Kargo Metrics

The current configuration exposes custom metrics from:

- `Stage`
  - Stage health status
  - Latest promotion phase
  - Latest promotion start timestamp
  - Latest promotion finish timestamp
- `Warehouse`
  - Warehouse condition status

The Stage metrics use `status.lastPromotion` rather than individual Promotion
resources to provide stable labels and avoid creating time series for uniquely
named Promotion objects.

## Configuration

Custom resource metrics are defined in:

`base/custom-resource-state-config.yaml`

RBAC permissions for the monitored Kargo resources are defined in:

`base/rbac.yaml`

## Validation

Validate the internal staging component:

    kustomize build components/monitoring/custom-kube-state-metrics/internal-staging

Validate the complete internal staging Argo CD overlay:

    kustomize build argo-cd-apps/overlays/internal-staging

## References

- https://github.com/kubernetes/kube-state-metrics/blob/main/docs/customresourcestate-metrics.md
