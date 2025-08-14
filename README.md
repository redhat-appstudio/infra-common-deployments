# Infra Common Clusters

A GitOps repository for managing shared infrastructure components across multiple Konflux clusters using ArgoCD and Kustomize.

## Overview

This repository provides reusable infrastructure components and ArgoCD application definitions for deploying common services that aren't associated with a single Konflux cluster. It follows a GitOps approach where infrastructure changes are managed through Git and automatically deployed by ArgoCD.

## Repository Structure

```
infra-common-clusters/
├── argo-cd-apps/              # ArgoCD Application definitions
│   ├── app-of-app-sets/       # App-of-Apps pattern for ApplicationSets
│   └── overlays/              # Environment-specific app configurations
├── components/                # Reusable Kustomize components
└── README.md
```

### Components

| Component | Purpose | Environments |
|-----------|---------|--------------|
| **internal-services** | Service access controls and RBAC | internal environments |
| **smee** | Webhook forwarding service | external environments |

### Environment Matrix

| Environment | Purpose | Cluster Short Name |
|-------------|---------|----------------|
| **int-stage** | Internal Red Hat staging resources | `kflux-c-stg-i01` |
| **ext-stage** | External/public staging resources | `kflux-c-stg-e01` |
| **int-prod** | Internal Red Hat production resources | `kflux-c-prd-i01` |
| **ext-prod** | External/public production resources | `kflux-c-prd-e01` |

## Architecture

### GitOps Flow

```mermaid
graph LR
    A{{infra-common-clusters}} 
    
    A --> B1
    A --> C1  
    A --> D1
    A --> E1
    
    subgraph StagingInternal[kflux-c-stg-i01]
        B1>ArgoCD]
        B2[internal-services]
        B1 --> B2
    end
    
    subgraph StagingExternal[kflux-c-stg-e01]
        C1>ArgoCD]
        C2[smee]
        C1 --> C2
    end
    
    subgraph ProductionInternal[kflux-c-prd-i01]
        D1>ArgoCD]
        D2[internal-services]
        D1 --> D2
    end
    
    subgraph ProductionExternal[kflux-c-prd-e01]
        E1>ArgoCD]
        E2[smee]
        E1 --> E2
    end
```

### App-of-Apps Pattern

This repository uses the **App-of-Apps pattern** where:
1. A root ArgoCD Application (`all-application-sets`) manages ApplicationSets
2. ApplicationSets automatically discover and deploy components
3. Components are deployed using Kustomize overlays per environment

## Deployment Guide

### Prerequisites

- OpenShift cluster with appropriate permissions
- ArgoCD installed and accessible
- Git repository access

### Bootstrap Process

#### 1. Deploy App-of-Apps

```bash
# Deploy the App-of-Apps for a cluster to let ArgoCD manage everything
kubectl apply -k argo-cd-apps/overlays/int-prod/
```

#### 2. Verify Deployment

```bash
# Check ArgoCD applications
kubectl get applications -n argocd

# Access ArgoCD UI
kubectl port-forward svc/argocd-server -n argocd 8080:80
# Open https://localhost:8080
```

### Environment-Specific Deployments

Each environment has its own overlay configuration:

```bash
# Staging Internal
kubectl apply -k argo-cd-apps/overlays/internal/staging/

# Staging External  
kubectl apply -k argo-cd-apps/overlays/external/staging/

# Production Internal
kubectl apply -k argo-cd-apps/overlays/internal/production/

# Production External
kubectl apply -k argo-cd-apps/overlays/external/production/
```

## Component Development

### Adding a New Component

1. **Create base component directory**:
   ```bash
   mkdir -p components/my-component/base
   cd components/my-component/base
   ```

2. **Create Kustomize base**:
   ```yaml
   # kustomization.yaml
   apiVersion: kustomize.config.k8s.io/v1beta1
   kind: Kustomization
   
   resources:
   - deployment.yaml
   - service.yaml
   
   namespace: my-component
   ```

   *Note: Be sure to name Kubernetes resource files after their Kubernetes kind*

3. **Add environment overlay(s)**:
   ```bash
   mkdir components/my-component/int-stage
   mkdir components/my-component/int-prod
   ```

4. **Create overlay kustomization(s)**:
   ```yaml
   # components/my-component/int-stage/kustomization.yaml
   apiVersion: kustomize.config.k8s.io/v1beta1
   kind: Kustomization
   
   namespace: my-component-staging
   
   resources:
   - ../base
   
   patchesStrategicMerge:
   - staging-patches.yaml
   ```

5. **Create a base ApplicationSet overlay**:

   *Note: If your component is only on either internal or external clusters, put the ApplicationSet in the environments base folder.*

   ```yaml
   # argo-cd-apps/overlays/internal/base/my-component/appset.yaml
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
   # arcgo-cd-apps/overlays/internal/base/my-component/kustomization.yaml
   apiVersion: kustomize.config.k8s.io/v1beta1
   kind: Kustomization
   resources:
   - appset.yaml
   ```

6. **Add component to base overlay**:

   *Note: If your component is only on either internal or external clusters, add the component to the environment's base overlay*

   ```yaml
   # argo-cd-apps/overlays/internal/base/kustomization.yaml
   apiVersion: kustomize.config.k8s.io/v1beta1
   kind: Kustomization
   resources:
   - internal-services
   - my-component
   ```

7. **Update other environment overlays if need be**:
   ```yaml
   # argo-cd-apps/overlays/internal/staging/kustomization.yaml
   apiVersion: kustomize.config.k8s.io/v1beta1
   kind: Kustomization
   resources:
   - ../base
   patches:
   - path: cluster-name-patch.yaml 
      target:
         group: argoproj.io
         version: v1alpha1
         kind: Application
   - path: environment-patch.yaml 
      target:
         group: argoproj.io
         version: v1alpha1
         kind: Application
   - path: special-patch.yaml 
      target:
         group: argoproj.io
         version: v1alpha1
         kind: Application
         name: my-component
   ```

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

## References

- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [Kustomize Documentation](https://kustomize.io/)
- [OpenShift GitOps](https://docs.openshift.com/container-platform/latest/cicd/gitops/understanding-openshift-gitops.html)
- [Konflux Documentation](https://konflux-ci.dev/)

