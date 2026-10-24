# Infra Common Clusters

A GitOps repository for managing shared infrastructure components across multiple Konflux common clusters using ArgoCD and Kustomize.

## Overview

This repository provides reusable infrastructure components and ArgoCD application definitions for deploying common services across different cluster types (internal/external) and environments (staging/production). It follows a GitOps approach where infrastructure changes are managed through Git and automatically deployed by ArgoCD.

## Repository Structure

```
infra-common-deployments/
├── argo-cd-apps/                           # ArgoCD Application definitions
│   ├── base/
│   │   ├── all-clusters/                   # Components deployed to ALL clusters
│   │   ├── external/                       # Components only for external clusters
│   │   └── internal/                       # Components only for internal clusters
│   └── overlays/                           # Environment-specific configurations
│       ├── external-production/            # External production cluster config
│       ├── external-staging/               # External staging cluster config
│       ├── internal-production/            # Internal production cluster config
│       └── internal-staging/               # Internal staging cluster config
├── components/                             # Reusable Kustomize components
│   ├── <component-name>/                   # <component-name> component
│   │   └── k-components/                   # Reusable <component-name> components (if any)
|   ...
└── README.md
```


| Environment | Purpose | Cluster Short Name |
|-------------|---------|----------------|
| **internal-staging** | Internal Red Hat staging resources | `kflux-c-stg-i01` |
| **internal-production** | Internal Red Hat production resources | `kflux-c-prd-i01` |
| **external-staging** | External/public staging resources | `kflux-c-stg-e01` |
| **external-production** | External/public production resources | `kflux-c-prd-e01` |

## Architecture

### GitOps Flow

```mermaid
graph LR
    A[infra-common-deployments]

    A --> B1
    A --> C1
    A --> D1 
    A --> E1

    subgraph StagingInternal[kflux-c-stg-i01]
        B1>Local Argo CD]
        B2["local component (e.g. internal-services)"]
        B1 --> B2
    
        B3>Ring Deployments Argo CD]
        B4>Tenants Config Argo CD]
    end

    F["Staging Tenant Clusters"]
    B3 --> F
    B4 --> F

    subgraph StagingExternal[kflux-c-stg-e01]
        C1>Local Argo CD]
        C2["local component (e.g. smee)"]
        C1 --> C2
    end

    subgraph ProductionInternal[kflux-c-prd-i01]
        D1>ArgoCD]
        D2["local component (e.g. internal services)"]
        D1 --> D2

        D3>Ring Deployments Argo CD]
        D4>Tenants Config Argo CD]
    end

    G["Production Tenant Clusters"]
    D3 --> G
    D4 --> G

    subgraph ProductionExternal[kflux-c-prd-e01]
        E1>Local Argo CD]
        E2["local component (e.g. smee)"]
        E1 --> E2
    end
```

### App-of-Apps Pattern

This repository uses the **App-of-Apps pattern** where:

1. A root ArgoCD Application (`all-application-sets`) manages ApplicationSets
2. ApplicationSets automatically discover and deploy components
3. Components are deployed using Kustomize overlays per environment

### Environment Overlay Structure

Each overlay includes:

- **Base all-clusters**: IAM + External Secrets Operator
- **Environment-specific base**: Additional components for that cluster type
- **Environment patches**: Configuration overrides for staging/production

## Reusable Components (k-components)

This repository uses Kustomize Components to eliminate duplication between environments. These components are located in `k-components/` directories within each component folder. 

Benefits include:

- **DRY Principle**: Eliminates code duplication between environments
- **Maintainability**: Changes only need to be made in one place
- **Consistency**: Ensures identical behavior across environments
- **Reusability**: Components can be easily used in new environments

## Component Development

### Adding a New Component

1. **Create base component directory**:

   ```bash
   mkdir -p components/my-component/base
   cd components/my-component/base
   ```

2. **Add resources shared across all clusters**:

   ```yaml
    ├── my-component/
    │   ├── base/
    │   │   ├── database-es.yaml
    │   │   ├── kustomize.yaml
    │   │   └── my-component-svc.yaml
    |   ...
   ```

   *Note: Be sure to name Kubernetes resource files after their Kubernetes kind*

3. **Add environment overlay(s) for each overlay to be deployed to**:

   ```bash
   mkdir components/my-component/<(internal | external)-(staging | production)>
   ```

4. **Add overlay-specific resources/patches to each overlay**:

   ```yaml
    ├── my-component/
    │   ├── base/
    │   │   ├── database-es.yaml
    │   │   ├── kustomize.yaml
    │   │   └── my-component-svc.yaml
    │   ├── internal-staging/
    │   │   ├── external-secret-path-patch.yaml
    │   │   ├── kustomize.yaml
    │   │   └── int-staging-cm.yaml
    |   ...
   ```

*Note: Be sure to reference the `base` folder as a resource in the Kustomize file of each overlay*

5. **Create a base ApplicationSet overlay**:

   *Note: If your component is only on either internal or external clusters, put the ApplicationSet in the proper folder.*

   ```yaml
   # argo-cd-apps/base/internal/base/my-component/appset.yaml
   apiVersion: argoproj.io/v1alpha1
   kind: ApplicationSet
   metadata:
   name: my-component
   spec:
   generators:
      - clusters:
         values:
            sourceRoot: components/my-component
            environment: base
            clusterName: ""
   template:
      metadata:
         name: my-component-{{values.clusterName}}
      spec:
         project: default
         source:
         path: '{{values.sourceRoot}}/{{values.environment}}'
         repoURL: https://github.com/redhat-appstudio/infra-common-deployments.git
         targetRevision: main
      destination:
        namespace: my-component-namespace
        server: '{{server}}'
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
        syncOptions:
          - CreateNamespace=true
        retry:
          limit: -1
          backoff:
            duration: 10s
            factor: 2
            maxDuration: 3m
   ```

   ```yaml
   # argo-cd-apps/base/internal/base/my-component/kustomization.yaml
   apiVersion: kustomize.config.k8s.io/v1beta1
   kind: Kustomization
   resources:
   - appset.yaml
   ```

6. **Add component to both staging overlay Kustomize files**:

   *Note: If your component is only on either internal or external clusters, add the component to only that staging environment's file*

   ```yaml
   # argo-cd-apps/overlays/internal-staging/kustomization.yaml
   apiVersion: kustomize.config.k8s.io/v1beta1
   kind: Kustomization
   resources:
   - internal-services
   # Testing on only staging first
   - my-component
   ```
   
7. **Add component to base Kustomize file (all-clusters, internal, or external) and remove the component entry from staging overlay Kustomize file(s)**:

   *Note: Only do this once the cmponent has been fully tested on staging*

   ```yaml
   # argo-cd-apps/overlays/internal-staging/kustomization.yaml
   apiVersion: kustomize.config.k8s.io/v1beta1
   kind: Kustomization
   resources:
   - internal-services

   # argo-cd-apps/base/internal/kustomization.yaml
   apiVersion: kustomize.config.k8s.io/v1beta1
   kind: Kustomization
   resources:
   - internal-services
   - my-component
   ```

### Creating Reusable Components (k-components)

When you have identical patches or configurations across multiple environments, consider creating a k-component:

1. **Create k-components directory**:
   ```bash
   mkdir -p components/my-component/k-components/my-config
   ```

2. **Create component kustomization**:
   ```yaml
   # components/my-component/k-components/my-config/kustomization.yaml
   apiVersion: kustomize.config.k8s.io/v1alpha1
   kind: Component
   patches:
     - path: my-config-patch.yaml
       target:
         name: my-resource
         kind: MyResource
   ```

3. **Create the patch file**:
   ```yaml
   # components/my-component/k-components/my-config/my-config-patch.yaml
   apiVersion: my-api/v1
   kind: MyResource
   metadata:
     name: my-resource
   spec:
     # Your configuration here
   ```

4. **Reference in environment kustomizations**:
   ```yaml
   # components/my-component/external-production/kustomization.yaml
   apiVersion: kustomize.config.k8s.io/v1beta1
   kind: Kustomization
   resources:
     - ../base
   components:
     - ../k-components/my-config
   ```

5. **Remove duplicate patch files** from individual environment directories

## Testing and Validation

### Prerequisites

- `kustomize` CLI tool installed
- Access to the repository
- Understanding of the target environment

### Local Testing with Kustomize

#### 1. Test Individual Overlays

```bash
# Test external production overlay
kustomize build argo-cd-apps/overlays/external-production/

# Test external staging overlay
kustomize build argo-cd-apps/overlays/external-staging/

# Test internal production overlay
kustomize build argo-cd-apps/overlays/internal-production/

# Test internal staging overlay
kustomize build argo-cd-apps/overlays/internal-staging/
```

#### 2. Testing Specific Components

```bash
# Build just the component
kustomize build components/my-componentr/base/

# Build with just a specific overlay
kustomize build components/my-component/internal-production/
```

### Validation Checklist

When testing, verify that:

- [ ] **All overlays build successfully** without errors
- [ ] **Environment patches are applied** correctly
- [ ] **Component resources are included** as expected in the overlay
- [ ] **No duplicate resources** are generated
- [ ] **Namespace assignments** are correct
- [ ] **Resource references** are valid

## Troubleshooting

### Common Issues

#### 1. Kustomize Build Errors

- **Problem**: `replace operation does not apply: doc is missing path`
- **Solution**: Check that ApplicationSet structures match the expected paths for environment patches

#### 2. Missing Components

- **Problem**: Expected components not appearing in build output
- **Solution**: Verify kustomization.yaml files include all required resources

#### 3. Environment Patch Failures

- **Problem**: Environment not being set correctly
- **Solution**: Ensure ApplicationSet generators have the correct structure for patches

#### 4. k-component Issues

- **Problem**: Component not being applied
- **Solution**: Verify the component is referenced in the kustomization.yaml and the target specification matches the resource

- **Problem**: Duplicate patches after creating k-component
- **Solution**: Remove the original patch files from environment directories after creating the k-component

### Debug Commands

```bash
# Show kustomize build plan
kustomize build --dry-run argo-cd-apps/overlays/external-production/

# Validate YAML syntax
kustomize build argo-cd-apps/overlays/external-production/ | kubectl apply --dry-run=client -f -

# Check specific component
kustomize build components/external-secrets-operator/base/ --dry-run
```

## Development Workflow

### Modifying Existing Components

1. **Make changes** in component directory
2. **Test locally** with kustomize build
3. **Verify environment overlays** still work
4. **Test in staging** before production

## Best Practices

- **Always test locally** with `kustomize build` before committing
- **Use consistent naming** conventions across components
- **Keep environment-specific configs** in overlays, not bases
- **Document component dependencies** and requirements
- **Test all overlays** when making changes to base components

## Contributing

1. **Fork** the repository
2. **Create** a new branch (`git checkout -b feature/my-component`)
3. **Test** changes in staging environment
4. **Submit** a merge request with:
   - Component documentation
   - Environment-specific configurations
   - Test validation results

### Review Checklist

- [ ] Component follows established patterns
- [ ] Environment overlays are complete
- [ ] Documentation is updated
- [ ] Security considerations addressed
- [ ] Monitoring configured
- [ ] Tested in staging environment

## Support

For issues or questions:

1. Check the troubleshooting section above
2. Review the component-specific documentation
3. Test with kustomize build locally
4. Check ArgoCD logs for deployment issues

## References

- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [Kustomize Documentation](https://kustomize.io/)
- [OpenShift GitOps](https://docs.openshift.com/container-platform/latest/cicd/gitops/understanding-openshift-gitops.html)
- [Konflux Documentation](https://konflux-ci.dev/)
