# Migrating a Component to the Environment Deployment Standard Structure

## Table of Contents

- [Summary](#summary)
- [Prerequisites](#prerequisites)
- [Best Practices](#best-practices)
- [Process](#process)
  - [Part 1: Staging Migration](#part-1-staging-migration)
  - [Part 2: Old Staging Deletion](#part-2-old-staging-deletion)
  - [Part 3: Migration to Production](#part-3-migration-to-production)
  - [Part 4: Old Production Deletion](#part-4-old-production-deletion)
  - [Part 5: Old Component Removal](#part-5-old-component-removal)

## Summary

This document details the requirements and full process for migrating a component to use the new standard component structure, and thus onboarding to environment deployments on the Konflux common clusters. This process aims to minimize, and most likely eliminate, any down-time for the component throughout this migration.

## Prerequisites

- Basic knowledge of Kustomize and Git

## Best Practices

1. Always follow the [directory structure documentation] when migrating a component, regardless of its legacy organization.

   - Put resources shared by all environments in `shared-resources/` and environment-specific changes in `<ENVIRONMENT>/` (`internal-staging/`, `external-staging/`, `internal-production/` or `external-production/`). Use `features/` for optional Kustomize components.
   - Pay particular attention to the guide's [File Conventions](directory-layout.md#5-file-conventions): name resource files `<resource-name>-<type-abbreviation>.yaml` as described in [File Naming](directory-layout.md#51-file-naming), keep one resource per file, and place patches in `patches/` with names ending in `-patch.yaml`. Upstream manifests consumed as-is may be exceptions to these file conventions.

2. Keep component maintainers involved in the review of each migration PR. Coordinate concurrent changes with them, and ask for their help during the migration when needed to verify that the component still works as intended.

3. Before filing each migration PR, apply these checks where relevant:

   - Search `hack/` and `.github/workflows/` for the component name and references to its legacy and temporary (`-ed`) paths. Update affected tests, scripts, and workflows so path changes do not break them.
   - When the rendered resources should remain unchanged, compare the Kustomize builds of the legacy and temporary component directories while both exist, for every environment the component is deployed to. For example, for the staging environments:

     ```sh
     diff <(kustomize build components/<COMPONENT_NAME>/internal-staging) \
          <(kustomize build components/<COMPONENT_NAME>-ed/internal-staging)
     ```

     Investigate any difference before filing the PR; if a change is intentional, explain it in the PR.
   - Run `kustomize build` on all four overlays (`argo-cd-apps/overlays/internal-staging/`, `external-staging/`, `internal-production/` and `external-production/`), as required by this repository's AGENTS.md.

## Process

### Part 1: Staging Migration

1. Fork and clone the [infra-common-deployments] repository and create a new branch.
2. Create a copy of the component folder `components/<COMPONENT_NAME>/` and call it `components/<COMPONENT_NAME>-ed/`.

   *The component folder is the `sourceRoot` of the component's original ApplicationSet. It is usually `components/<COMPONENT_NAME>/`, but not always: for example the `monitoring-workload-grafana` ApplicationSet uses `components/monitoring/grafana/`, so its copy is `components/monitoring/grafana-ed/`.*

3. Reorganize the component structure under the new folder created in the previous step to follow the [directory structure documentation]. Create just `components/<COMPONENT_NAME>-ed/shared-resources/` and the staging environment folders `components/<COMPONENT_NAME>-ed/internal-staging/` (plus `components/<COMPONENT_NAME>-ed/external-staging/` if the component is deployed to the external staging cluster) for now.

   *`shared-resources/` must contain all the resources the component's environments share, whether or not the legacy structure had a `base/`. If it has one, move it there; if it does not, extract whatever is common to all of the legacy environment folders (production included, even though production is migrated in [Part 3](#part-3-migration-to-production)).*

4. Copy the `components/<COMPONENT_NAME>-ed/shared-resources/` folder into each of the staging environment folders and name it `shared-resources-ref`. Ensure each environment's `kustomization.yaml` file (e.g. `components/<COMPONENT_NAME>-ed/internal-staging/kustomization.yaml`) has a resource entry for it.
5. Configure the staging environment folders appropriately using the [directory structure documentation].
6. Create a folder called `argo-cd-apps/overlays/ed-staging/<GROUP>/<COMPONENT_NAME>/` and add the following files. `<GROUP>` is `all-clusters`, `internal` or `external`, matching the folder under `argo-cd-apps/base/` that holds the component's original ApplicationSet (step 8):

`<COMPONENT_NAME>-appset.yaml`
```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: <COMPONENT_NAME>-ed # The original ApplicationSet's name + '-ed'
spec:
  generators:
    - clusters:
        values:
          sourceRoot: components/<COMPONENT_NAME>-ed # The original appset's sourceRoot + '-ed' (the component folder from step 2), e.g. components/monitoring/grafana-ed
          environment: "" # Populated by each overlay's environment-patch.yaml, e.g. internal-staging | external-staging
          # clusterName: "" # (optional) IF the original appset has this value, copy it
  template:
    metadata:
      name: <COMPONENT_NAME>-ed-{{nameNormalized}}
      labels:
        app.kubernetes.io/part-of: <COMPONENT_NAME> # The component's original name, without '-ed'
    spec:
      project: default
      source:
        path: '{{values.sourceRoot}}/{{values.environment}}'
        repoURL: https://github.com/redhat-appstudio/infra-common-deployments.git
        targetRevision: main
      destination:
        namespace: <ORIGINAL_NAMESPACE> # (optional) IF the component has this field in its original appset
        name: in-cluster # Copy the destination of the component's original appset (`name: in-cluster` in almost all of them; IF it has `server: '{{server}}'` instead, copy that, e.g. smee)
      syncPolicy:
        # automated:
        #   prune: true
        #   selfHeal: true
        syncOptions: # Copy syncOptions from the original appset
        - CreateNamespace=true
        retry: # Copy retry from the original appset (the values vary, e.g. limit: -1 or limit: 50)
          limit: -1
          backoff:
            duration: 10s
            factor: 2
            maxDuration: 3m

```

`kustomization.yaml`
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
- <COMPONENT_NAME>-appset.yaml

```

> *Be sure to fill in all templated information (phrases surrounded by <>)*

> *The old ApplicationSet and its Applications run on the same ArgoCD instance as these new ones, and neither can share a name with them (identical ApplicationSet names do not even build), so the new ApplicationSet and its Applications carry the `-ed` suffix until [Part 5](#part-5-old-component-removal) removes it.*

> *Until [Part 2](#part-2-old-staging-deletion) deletes the old ApplicationSet, its Applications and the new `-ed` ones describe the same live resources. The old ones no longer auto-sync: do not sync them manually, and expect ArgoCD to possibly flag the shared resources on both once step 11 is done.*

7. Add '<COMPONENT_NAME>' to the `resources` field of the `argo-cd-apps/overlays/ed-staging/<GROUP>/kustomization.yaml` file.

8. Remove the automated sync of the component's original ApplicationSet in the staging overlays. In each staging overlay the component is deployed to (`argo-cd-apps/overlays/internal-staging/` and/or `argo-cd-apps/overlays/external-staging/`), create `<COMPONENT_NAME>-remove-auto-sync-patch.yaml`:

   ```yaml
   apiVersion: argoproj.io/v1alpha1
   kind: ApplicationSet
   metadata:
     name: <COMPONENT_NAME>
   spec:
     template:
       spec:
         syncPolicy:
           automated: null
   ```

   and add the following `patches` entry to that overlay's `kustomization.yaml` file:

   ```yaml
     # Remove automated sync from <COMPONENT_NAME> for staging migration; this AppSet is
     # shared with production, so the base syncPolicy is left untouched
     - path: <COMPONENT_NAME>-remove-auto-sync-patch.yaml
       target:
         kind: ApplicationSet
         version: v1alpha1
         name: <COMPONENT_NAME>
   ```

   *The original ApplicationSet file should be located in a folder of the same name as the component underneath `argo-cd-apps/base/all-clusters/`, `argo-cd-apps/base/internal/` or `argo-cd-apps/base/external/`. Its file name varies (e.g. `appset.yaml` or `<COMPONENT_NAME>.yaml`), so check the legacy each time. If the component is deployed to a single environment, it may be a file directly in that environment's `argo-cd-apps/overlays/<ENVIRONMENT>/` folder instead.*

9. Commit these changes, publish the branch, and create a PR with the following name: '(onboarding) Migrate staging <COMPONENT_NAME> AppSet to environment deployments'.
10. Once the previously mentioned PR is merged, navigate to the [kflux-c-stg-i01 ArgoCD instance] (and the [kflux-c-stg-e01 ArgoCD instance] if the component is deployed to the external staging cluster) and search for '<COMPONENT_NAME>-ed'.
11. For each of the staging applications, click on the 'SYNC' button in the top left corner, then the 'SYNCHRONIZE' button in the top right corner. Verify the application is healthy and synced.

### Part 2: Old Staging Deletion

1. Create a new branch in the same repository.
2. Ensure any references to the old ApplicationSet in the `argo-cd-apps/overlays/internal-staging/` and `argo-cd-apps/overlays/external-staging/` folders are deleted: the `<COMPONENT_NAME>-remove-auto-sync-patch.yaml` file and `patches` entry added in step 8 of [Part 1](#part-1-staging-migration) and, if the old ApplicationSet is a file in the overlay itself, that file and its `resources` entry.
3. Add a delete patch for the component to the `argo-cd-apps/overlays/internal-staging/delete-applications.yaml` and `argo-cd-apps/overlays/external-staging/delete-applications.yaml` files, as applicable.

   ```yaml
   ---
   apiVersion: argoproj.io/v1alpha1
   kind: ApplicationSet
   metadata:
     name: <COMPONENT_NAME>
   $patch: delete
   ```

   *Skip this step if the original ApplicationSet is a file in the overlay itself; deleting that file and its `resources` entry in the previous step is enough.*

4. Commit these changes and publish the branch.
5. Navigate to the [internal staging common cluster OCP console](https://console-openshift-console.apps.rosa.kflux-c-stg-i01.qfla.p3.openshiftapps.com/dashboards) and select the 'argocd-local' namespace.
6. Select Home->Search from the dropdown menu on the left side and search for 'ApplicationSet' resources.
7. Click on the <COMPONENT_NAME> ApplicationSet and then the YAML tab.
8. Add the following underneath the `spec` field:

   ```yaml
   syncPolicy:
     preserveResourcesOnDeletion: true
   ```
9. Click the `Save` button and ensure the changes were made.
10. Select Home->Search from the dropdown menu on the left side and search for 'Application' resources.
11. For all <COMPONENT_NAME> resources, verify the YAML has no `resources-finalizer.argocd.argoproj.io` under the `metadata.finalizers` field.

    > **Warning:** Do not skip this check, and do not create the PR in step 13 until it passes. If an old Application still carries the `resources-finalizer.argocd.argoproj.io` finalizer, deleting the old ApplicationSet deletes the live resources that Application tracks, which are the same resources the new `-ed` applications now run. If a finalizer is present, go back to steps 8-9 and confirm the change was saved. Take extra care with components that deploy an ArgoCD instance themselves (`argocd-internal-appsre`, `argocd-external-appsre`): losing their resources would take down the ArgoCD that hosts other applications.

12. If the component is deployed to the external staging cluster, repeat steps 5-11 on the [external staging common cluster OCP console](https://console-openshift-console.apps.rosa.kflux-c-stg-e01.3zdg.p3.openshiftapps.com/).
13. Create a PR with the published branch named: '(onboarding) Remove old staging <COMPONENT_NAME> AppSet'.
14. Once the previously mentioned PR is merged, navigate to the [kflux-c-stg-i01 ArgoCD instance] (and the [kflux-c-stg-e01 ArgoCD instance] if applicable) and search for '<COMPONENT_NAME>-ed'. For each of the staging applications, trigger a manual sync and verify that the application is healthy and synced.
15. On the same ArgoCD instance(s), verify that the old <COMPONENT_NAME> app(s) (the ones without the `-ed` in their name) are gone.

### Part 3: Migration to Production

1. Create a new branch in the same repository.
2. Add `internal-production/` (and `external-production/` if the component is deployed to the external production cluster) folders to the `components/<COMPONENT_NAME>-ed/` folder and organize them appropriately using the [directory structure documentation].
3. Copy the `components/<COMPONENT_NAME>-ed/shared-resources/` folder into each of the production environment folders and name it `shared-resources-ref/`. Ensure each environment's `kustomization.yaml` file has a resource entry for 'shared-resources-ref'.
4. Create a folder called `argo-cd-apps/overlays/ed-production/<GROUP>/<COMPONENT_NAME>/` and add the following files (`<GROUP>` as in step 6 of [Part 1](#part-1-staging-migration)):

`<COMPONENT_NAME>-appset.yaml`
```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: <COMPONENT_NAME>-ed # The original ApplicationSet's name + '-ed'
spec:
  generators:
    - clusters:
        values:
          sourceRoot: components/<COMPONENT_NAME>-ed # The original appset's sourceRoot + '-ed' (the component folder from step 2), e.g. components/monitoring/grafana-ed
          environment: "" # Populated by each overlay's environment-patch.yaml, e.g. internal-production | external-production
          # clusterName: "" # (optional) IF the original appset has this value, copy it
  template:
    metadata:
      name: <COMPONENT_NAME>-ed-{{nameNormalized}}
      labels:
        app.kubernetes.io/part-of: <COMPONENT_NAME> # The component's original name, without '-ed'
    spec:
      project: default
      source:
        path: '{{values.sourceRoot}}/{{values.environment}}'
        repoURL: https://github.com/redhat-appstudio/infra-common-deployments.git
        targetRevision: main
      destination:
        namespace: <ORIGINAL_NAMESPACE> # (optional) IF the component has this field in its original appset
        name: in-cluster # Copy the destination of the component's original appset (`name: in-cluster` in almost all of them; IF it has `server: '{{server}}'` instead, copy that, e.g. smee)
      syncPolicy:
        # automated:
        #   prune: true
        #   selfHeal: true
        syncOptions: # Copy syncOptions from the original appset
        - CreateNamespace=true
        retry: # Copy retry from the original appset (the values vary, e.g. limit: -1 or limit: 50)
          limit: -1
          backoff:
            duration: 10s
            factor: 2
            maxDuration: 3m

```

`kustomization.yaml`
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
- <COMPONENT_NAME>-appset.yaml

```

> *Be sure to fill in all templated information (phrases surrounded by <>)*

5. Add '<COMPONENT_NAME>' to the `argo-cd-apps/overlays/ed-production/<GROUP>/kustomization.yaml` file's `resources` field.

6. Remove the automated sync of the component's original ApplicationSet in the production overlays, the same way as in step 8 of [Part 1](#part-1-staging-migration), in `argo-cd-apps/overlays/internal-production/` and/or `argo-cd-apps/overlays/external-production/`, as applicable.
7. Commit these changes, publish the branch, and create a PR with the following name: '(onboarding) Migrate production <COMPONENT_NAME> AppSet to environment deployments'.
8. Once the previously mentioned PR is merged, navigate to the [kflux-c-prd-i01 ArgoCD instance] (and the [kflux-c-prd-e01 ArgoCD instance] if the component is deployed to the external production cluster) and search for '<COMPONENT_NAME>-ed'. For each of the production applications, trigger a manual sync and verify that the application is healthy and synced.

### Part 4: Old Production Deletion

1. Create a new branch in the same repository.
2. Ensure any references to the old ApplicationSet in the `argo-cd-apps/overlays/internal-production/` and `argo-cd-apps/overlays/external-production/` folders are deleted: the `<COMPONENT_NAME>-remove-auto-sync-patch.yaml` file and `patches` entry added in step 6 of [Part 3](#part-3-migration-to-production) and, if the old ApplicationSet is a file in the overlay itself, that file and its `resources` entry.
3. Add a delete patch for the component to the `argo-cd-apps/overlays/internal-production/delete-applications.yaml` and `argo-cd-apps/overlays/external-production/delete-applications.yaml` files, as applicable.

   ```yaml
   ---
   apiVersion: argoproj.io/v1alpha1
   kind: ApplicationSet
   metadata:
     name: <COMPONENT_NAME>
   $patch: delete

   ```

   *Skip this step if the original ApplicationSet is a file in the overlay itself; deleting that file and its `resources` entry in the previous step is enough.*

4. Commit these changes and publish the branch.


5. Navigate to the [internal production common cluster OCP console](https://console-openshift-console.apps.rosa.kflux-c-prd-i01.7hyu.p3.openshiftapps.com/dashboards) and select the 'argocd-local' namespace.
6. Select Home->Search from the dropdown menu on the left side and search for 'ApplicationSet' resources.
7. Click on the <COMPONENT_NAME> ApplicationSet and then the YAML tab.
8. Add the following underneath the `spec` field:

   ```yaml
   syncPolicy:
     preserveResourcesOnDeletion: true
   ```
9. Click the `Save` button and ensure the changes were made.
10. Select Home->Search from the dropdown menu on the left side and search for 'Application' resources.
11. For all <COMPONENT_NAME> resources, verify the YAML has no `resources-finalizer.argocd.argoproj.io` under the `metadata.finalizers` field.

    > **Warning:** Do not skip this check, and do not create the PR in step 13 until it passes. If an old Application still carries the `resources-finalizer.argocd.argoproj.io` finalizer, deleting the old ApplicationSet deletes the live resources that Application tracks, which are the same resources the new `-ed` applications now run. If a finalizer is present, go back to steps 8-9 and confirm the change was saved. Take extra care with components that deploy an ArgoCD instance themselves (`argocd-internal-appsre`, `argocd-external-appsre`): losing their resources would take down the ArgoCD that hosts other applications.

12. If the component is deployed to the external production cluster, repeat steps 5-11 on the [external production common cluster OCP console](https://console-openshift-console.apps.rosa.kflux-c-prd-e01.yo5u.p3.openshiftapps.com/).
13. Create a PR with published branch called: '(onboarding) Remove old production <COMPONENT_NAME> AppSet'.
14. Once the previously mentioned PR is merged, navigate to the [kflux-c-prd-i01 ArgoCD instance] (and the [kflux-c-prd-e01 ArgoCD instance] if applicable) and search for '<COMPONENT_NAME>-ed'. For each of the production applications, trigger a manual sync and verify that the application is healthy and synced.
15. On the same ArgoCD instance(s), verify that the old <COMPONENT_NAME> app(s) (the ones without the `-ed` in their name) are gone.

### Part 5: Old Component Removal

1. Create one more new branch in the same repository.
2. Delete the old ApplicationSet component folder found in step 8 of [Part 1](#part-1-staging-migration).
3. Remove the component entry from the Kustomize file in the parent folder of the folder from the previous step.
4. Ensure ANY references to the old ApplicationSet in the `argo-cd-apps/overlays/internal-staging/`, `argo-cd-apps/overlays/external-staging/`, `argo-cd-apps/overlays/internal-production/` and `argo-cd-apps/overlays/external-production/` folders are deleted, including the delete patches added in [Part 2](#part-2-old-staging-deletion) and [Part 4](#part-4-old-production-deletion).
5. Uncomment the following lines in the component's ApplicationSet files under the `argo-cd-apps/overlays/ed-staging/<GROUP>/<COMPONENT_NAME>/` and `argo-cd-apps/overlays/ed-production/<GROUP>/<COMPONENT_NAME>/` folders.

   ```yaml
   # automated:
   #   prune: true
   #   selfHeal: true
   ```
6. Delete the `components/<COMPONENT_NAME>` folder and rename the `components/<COMPONENT_NAME>-ed/` folder -> `components/<COMPONENT_NAME>/`.
7. Change all instances of `<COMPONENT_NAME>-ed` in the `argo-cd-apps/overlays/ed-staging/` and `argo-cd-apps/overlays/ed-production/` folders to `<COMPONENT_NAME>`.
8. Commit these changes, publish the branch, and create a PR with the following name: '(onboarding) Remove old <COMPONENT_NAME> component'.
9. Once the previously mentioned PR is merged, navigate to the [kflux-c-stg-i01 ArgoCD instance] (and the [kflux-c-stg-e01 ArgoCD instance] if applicable) and search for <COMPONENT_NAME>. Verify that all of the applications are healthy and synced.
10. Navigate to the [kflux-c-prd-i01 ArgoCD instance] (and the [kflux-c-prd-e01 ArgoCD instance] if applicable) and search for <COMPONENT_NAME>. Verify that all of the applications are healthy and synced.

[infra-common-deployments]: https://github.com/redhat-appstudio/infra-common-deployments
[kflux-c-stg-i01 ArgoCD instance]: https://argocd-server-argocd-local.apps.rosa.kflux-c-stg-i01.qfla.p3.openshiftapps.com/applications?proj=&sync=&autoSync=&health=&namespace=&targetRevision=&repo=&cluster=&labels=&annotations=&operation=
[kflux-c-stg-e01 ArgoCD instance]: https://argocd-server-argocd-local.apps.rosa.kflux-c-stg-e01.3zdg.p3.openshiftapps.com/applications?proj=&sync=&autoSync=&health=&namespace=&targetRevision=&repo=&cluster=&labels=&annotations=&operation=
[kflux-c-prd-i01 ArgoCD instance]: https://argocd-server-argocd-local.apps.rosa.kflux-c-prd-i01.7hyu.p3.openshiftapps.com/applications?proj=&sync=&autoSync=&health=&namespace=&targetRevision=&repo=&cluster=&labels=&annotations=&operation=
[kflux-c-prd-e01 ArgoCD instance]: https://argocd-server-argocd-local.apps.rosa.kflux-c-prd-e01.yo5u.p3.openshiftapps.com/applications?proj=&sync=&autoSync=&health=&namespace=&targetRevision=&repo=&cluster=&labels=&annotations=&operation=
[directory structure documentation]: directory-layout.md
