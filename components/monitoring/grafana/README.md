
## Installing and configuring Grafana on common clusters

We use Grafana Operator to create all needed services and routes 

Note: The steps below should be handled by Argo CD

- Create the `appstudio-grafana` namespace on each cluster, if it does not exist yet:

    ```
    $ oc create namespace appstudio-grafana
    ```

- Build and apply from the per environment overlay:

    ```
    $ kustomize build components/monitoring/grafana/internal-staging | oc apply -f -
    ```

    Replace `internal-staging` with the appropriate environment overlay.

## Structure

Shared resources (operator, app, patches, RBAC, common dashboards) live in `base/`. Each environment overlay (`external-production`, `external-staging`, `internal-production`, `internal-staging`) contains only a `kustomization.yaml` that references `../base` and optionally includes k-components.

## Dashboard structure

Common dashboards (dora-metrics, generic-dashboards, perfscale) are in `base/dashboards/`. Internal-only dashboards (kueue, kyverno, pipeline-service) are in `k-components/internal-dashboards/dashboards/` and are included by the `internal-*` overlays via a Kustomize Component.
