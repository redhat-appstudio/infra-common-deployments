
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

## Dashboard structure

Team dashboards are maintained in per environment overlays (`internal-staging/dashboards/`, `external-staging/dashboards/`). Each environment references its own dashboard source independently. The `base/dashboards/` directory contains shared dashboard definitions referenced by the overlays.
