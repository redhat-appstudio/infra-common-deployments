# Custom Kube State Metrics

Deploys a dedicated `kube-state-metrics` instance in the common cluster for
exposing Prometheus metrics from custom resources.

Uses `--custom-resource-state-only=true` to avoid duplicating platform metrics.

This component provides the common custom kube-state-metrics deployment:
the Deployment, Service and ServiceMonitor live in `shared-resources/`,
which is copied into each environment's `shared-resources-ref/`.
Custom resource metrics are configured and validated separately per environment.

## Configuration

Environment-specific custom resource metrics are configured in:

`<environment>/custom-resource-state-config.yaml`

RBAC permissions required by custom resource collectors are defined in:

`<environment>/rbac/custom-kube-state-metrics-cr.yaml`

For example, the internal staging configuration is located in:

- `internal-staging/custom-resource-state-config.yaml`
- `internal-staging/rbac/custom-kube-state-metrics-cr.yaml`

A custom resource metric can be added using the following template:

```yaml
spec:
  resources:
    - groupVersionKind:
        group: <api-group>
        version: <api-version>
        kind: <resource-kind>
      metrics:
        - name: <metric-name>
          help: <metric-description>
          each:
            type: Gauge
            gauge:
              path: [status, <field>]
```

The corresponding RBAC permissions for the custom resource must also be added
to the environment-specific `rbac/custom-kube-state-metrics-cr.yaml`.

## Validation

Validate the internal staging component:

    kustomize build components/monitoring/custom-kube-state-metrics/internal-staging

Validate the complete internal staging Argo CD overlay:

    kustomize build argo-cd-apps/overlays/internal-staging

### Custom metric validation

Custom resource metrics should be tested individually before being added to an
environment configuration. This helps ensure that an invalid metric definition
does not affect the custom kube-state-metrics deployment.

Metric-specific configuration and validation will be handled separately as part
of the corresponding monitoring work.

## References

- https://github.com/kubernetes/kube-state-metrics/blob/main/docs/customresourcestate-metrics.md
