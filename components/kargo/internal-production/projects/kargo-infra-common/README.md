# Onboarding a Component to Kargo Promotion

This guide explains how to add a new component to the `kargo-infra-common`
automated promotion pipeline. Kargo watches container registries and Helm chart
repositories for new versions, then opens PRs to promote those versions through
staging and production.

## How Promotion Works

```
Warehouse                        Stage: staging              Stage: production
(watches registries)  ──freight──>  (auto-promotes)  ──soak──>  (manual approval)
                                       │                            │
                                  PromotionTask               PromotionTask
                                  updates staging              updates production
                                  config files                 config files
                                       │                            │
                                  Opens PR to main            Opens PR to main
                                  Waits for merge             Waits for merge
```

**Key concepts:**

- **Warehouse** — watches image registries / Helm repos and creates "freight"
  (a versioned bundle of artifacts) when new versions appear.
- **Stage** — represents an environment (staging, production). Each stage
  consumes freight and runs a promotion template.
- **PromotionTask** — the reusable logic that updates files in this GitOps
  repo. Each component has its own task.
- **Freight origin guard** — each PromotionTask uses
  `if: ${{ ctx.targetFreight.origin.name == "<warehouse>" }}` so it only
  executes when its own warehouse produces new freight.

## Directory Layout

```
kargo-infra-common/
├── base/                              # shared project resources
│   ├── namespace.yaml                 # namespace with kargo.akuity.io/project label
│   ├── project.yaml                   # Kargo Project
│   ├── project-config.yaml            # promotion policies (auto/manual per stage)
│   ├── rbac/                          # RBAC for the konflux-devprod group
│   ├── external-secrets/              # git credentials from Vault
│   ├── stage-ring-1-staging.yaml      # staging stage (calls all component tasks)
│   └── stage-ring-2-production.yaml   # production stage (calls component tasks)
│
├── kargo/                             # kargo component
│   ├── kustomization.yaml
│   ├── warehouse.yaml                 # watches kargo + dex images, kargo helm chart
│   └── promotiontasks/
│       ├── kargo-promote-ring-1.yaml  # updates staging config
│       └── kargo-promote-ring-2.yaml  # updates production config
│
├── <your-component>/                  # add your component here
│   ├── kustomization.yaml
│   ├── warehouse.yaml
│   └── promotiontasks/
│       └── <component>-promote-ring-1.yaml  # at minimum, staging
│
└── kustomization.yaml                 # references: base, kargo, <your-component>
```

Each component owns its **warehouse** (what to watch) and **promotion tasks**
(what to update). The **stages** in `base/` are shared — they call every
component's promotion task in sequence within a single promotion, which
preserves soak time gating between staging and production.

## Step-by-Step: Onboard a New Component

### 1. Create Your Component Directory

```
kargo-infra-common/<component>/
├── kustomization.yaml
├── warehouse.yaml
└── promotiontasks/
    ├── kustomization.yaml
    └── <component>-promote-ring-1.yaml
```

### 2. Define Your Warehouse

The warehouse tells Kargo what artifacts to watch. It polls every 5 minutes
and creates freight when new versions appear.

```yaml
# <component>/warehouse.yaml
---
apiVersion: kargo.akuity.io/v1alpha1
kind: Warehouse
metadata:
  name: <component>
spec:
  freightCreationPolicy: Automatic
  interval: 5m0s
  subscriptions:
    # Helm chart (if your component deploys via Helm)
    - chart:
        repoURL: https://charts.example.com
        name: <chart-name>
        semverConstraint: ^1.0.0
        discoveryLimit: 5
    # Container images
    - image:
        repoURL: quay.io/konflux-ci/<image>
        imageSelectionStrategy: NewestBuild
        discoveryLimit: 5
        allowTags: ^[0-9a-f]{40}$      # SHA tags
    # Add more images as needed
```

**`allowTags`** — regex filter for image tags. Common patterns:
- `^[0-9a-f]{40}$` — full 40-char git SHA
- `^1\.10-[0-9a-f]{7}$` — semver prefix + short SHA
- `^v[0-9]+\.[0-9]+\.[0-9]+$` — semver tags

**`imageSelectionStrategy`** — use `NewestBuild` for SHA-tagged images,
`SemVer` for semver-tagged images.

### 3. Create Your Promotion Task

The promotion task defines which files to update and how. It uses
`yaml-update` to patch specific keys in your component's config files.

```yaml
# <component>/promotiontasks/<component>-promote-ring-1.yaml
---
apiVersion: kargo.akuity.io/v1alpha1
kind: PromotionTask
metadata:
  name: <component>-promote-ring-1
spec:
  vars:
    - name: srcPath
  steps:
    - uses: yaml-update
      as: update-<component>
      if: ${{ ctx.targetFreight.origin.name == "<component>" }}
      config:
        path: ${{ vars.srcPath }}/components/<component>/internal-staging/<target-file>
        updates:
          - key: <yaml.key.to.update>
            value: ${{ imageFrom("quay.io/konflux-ci/<image>").Tag }}
```

**What goes in `updates`** depends on how your component is deployed:

| Deployment Method | Target File | Key to Update |
|---|---|---|
| HelmChartInflationGenerator | `kargo-helm-generator.yaml` | `valuesInline.image.tag` |
| Kustomize `helmCharts:` | `helm-values.yaml` | `<image-key>.tag` |
| Kustomize `images:` | `kustomization.yaml` | `images.0.newTag` |
| Helm chart version | generator or kustomization | `version` (use `chartFrom()`) |
| Git resource ref | `kustomization.yaml` | `resources.<index>` |

**Expression functions:**
- `imageFrom("quay.io/repo").Tag` — resolves image tag from freight
- `chartFrom("oci://registry/chart").Version` — resolves chart version from freight

**If your component also deploys to production**, create `<component>-promote-ring-2.yaml`
with the same structure but pointing to the production config path
(`internal-production/` instead of `internal-staging/`).

### 4. Wire Up the Kustomizations

```yaml
# <component>/kustomization.yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - warehouse.yaml
  - promotiontasks
```

```yaml
# <component>/promotiontasks/kustomization.yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - <component>-promote-ring-1.yaml
  # - <component>-promote-ring-2.yaml  # if you have production
```

### 5. Register Your Component in the Top-Level Kustomization

```yaml
# kustomization.yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: kargo-infra-common
resources:
  - base
  - kargo
  - <component>          # <-- add this line
commonAnnotations:
  argocd.argoproj.io/sync-options: SkipDryRunOnMissingResource=true
```

### 6. Add Your Warehouse as a Freight Origin in the Stage

Edit `base/stage-ring-1-staging.yaml` — add your warehouse under
`requestedFreight`:

```yaml
spec:
  requestedFreight:
    - origin:
        kind: Warehouse
        name: kargo
      sources:
        direct: true
    - origin:                    # <-- add this block
        kind: Warehouse
        name: <component>
      sources:
        direct: true
```

Then add your promotion task call in the `steps` section, after the existing
task calls:

```yaml
      steps:
        - uses: git-clone
          ...
        # --- kargo ---
        - task:
            name: kargo-promote-ring-1
          as: kargo-promote
          vars:
            - name: srcPath
              value: ./src
        # --- <component> ---          # <-- add this block
        - task:
            name: <component>-promote-ring-1
          as: <component>-promote
          vars:
            - name: srcPath
              value: ./src
        - uses: git-commit
          ...
```

If your component also promotes to production, make the same changes in
`base/stage-ring-2-production.yaml`.

### 7. Update the Project Config (if needed)

The project config in `base/project-config.yaml` controls auto-promotion.
The current stages already have policies defined — you only need to edit this
if you add new stages:

```yaml
spec:
  promotionPolicies:
    - stage: ring-1-staging
      autoPromotionEnabled: true       # staging auto-promotes
    - stage: ring-2-production
      autoPromotionEnabled: false      # production requires manual approval
```

### 8. Validate

```sh
# build the kargo-infra-common project
kustomize build components/kargo/internal-production/projects/kargo-infra-common/

# build the full overlays
kustomize build --enable-helm components/kargo/internal-staging/
kustomize build --enable-helm components/kargo/internal-production/

# apply to a local kind cluster for testing (if available)
kustomize build components/kargo/internal-production/projects/kargo-infra-common/ \
  | kubectl apply -f -
```

## Environments

This repo supports four environments across two cluster types:

| Environment | Cluster Type | Kargo Stage | ArgoCD Source Path |
|---|---|---|---|
| `internal-staging` | Internal | `ring-1-staging` | `components/<name>/internal-staging` |
| `internal-production` | Internal | `ring-2-production` | `components/<name>/internal-production` |
| `external-staging` | External | `ring-1-staging` | `components/<name>/external-staging` |
| `external-production` | External | `ring-2-production` | `components/<name>/external-production` |

ArgoCD ApplicationSets use `{{values.environment}}` which is patched per
overlay to the correct environment name. Your component needs a directory
matching each environment it deploys to (e.g., `internal-staging/`,
`internal-production/`).

If your component deploys to **external** clusters, your promotion task must
also update the external config files.

## Example: Kargo Component (Reference)

The `kargo/` directory is the reference implementation:

**Warehouse** — watches the Kargo Helm chart (OCI), Kargo image, and Dex image:

```yaml
subscriptions:
  - chart:
      repoURL: oci://ghcr.io/akuity/kargo-charts/kargo
      semverConstraint: ^1.10.0
  - image:
      repoURL: quay.io/konflux-ci/kargo
      allowTags: ^1\.10-[0-9a-f]{7}$
  - image:
      repoURL: quay.io/konflux-ci/dex
      allowTags: ^[0-9a-f]{40}$
```

**Promotion Task** — updates the Helm generator with chart version + image tags:

```yaml
steps:
  - uses: yaml-update
    as: update-kargo
    if: ${{ ctx.targetFreight.origin.name == "kargo" }}
    config:
      path: ${{ vars.srcPath }}/components/kargo/internal-staging/deployment/kargo-helm-generator.yaml
      updates:
        - key: version
          value: ${{ chartFrom("oci://ghcr.io/akuity/kargo-charts/kargo").Version }}
        - key: valuesInline.image.tag
          value: ${{ imageFrom("quay.io/konflux-ci/kargo").Tag }}
        - key: valuesInline.api.oidc.dex.image.tag
          value: ${{ imageFrom("quay.io/konflux-ci/dex").Tag }}
```

## Checklist

Before opening your PR:

- [ ] Warehouse created with correct image repos, tag filters, and chart refs
- [ ] PromotionTask created with `if` guard on `ctx.targetFreight.origin.name`
- [ ] PromotionTask `path` points to the correct target file in your component
- [ ] Kustomizations wired up (`<component>/kustomization.yaml` and `promotiontasks/kustomization.yaml`)
- [ ] Top-level `kustomization.yaml` includes your component
- [ ] Stage YAML updated with your freight origin and task call
- [ ] `kustomize build` passes for all overlays
- [ ] Tested on a local kind cluster (if available)
