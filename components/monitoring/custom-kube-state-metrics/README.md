# Custom Kube State Metrics

Deploys a dedicated `kube-state-metrics` instance in the common cluster for
exposing Prometheus metrics from custom resources.

Uses `--custom-resource-state-only=true` to avoid duplicating platform metrics.

This component provides the base custom kube-state-metrics deployment.
Custom resource metrics will be added and validated separately.

## Configuration

Custom resource metrics are configured in:

`base/custom-resource-state-config.yaml`

RBAC permissions required by custom resource collectors are defined in:

`base/rbac.yaml`

## Validation

Validate the internal staging component:

    kustomize build components/monitoring/custom-kube-state-metrics/internal-staging

Validate the complete internal staging Argo CD overlay:

    kustomize build argo-cd-apps/overlays/internal-staging

## References

- https://github.com/kubernetes/kube-state-metrics/blob/main/docs/customresourcestate-metrics.md
