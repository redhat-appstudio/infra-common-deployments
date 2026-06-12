---
name: kargo-onboard
description: Scaffold a new component into the kargo-infra-common Kargo promotion pipeline
---

You are onboarding a new component to the Kargo automated promotion pipeline
in the `kargo-infra-common` project.

## Before you start

Read these files to understand the conventions and reference implementation:

1. `components/kargo/internal-production/projects/kargo-infra-common/README.md` — the onboarding guide
2. `components/kargo/internal-production/projects/kargo-infra-common/kargo/warehouse.yaml` — reference warehouse
3. `components/kargo/internal-production/projects/kargo-infra-common/kargo/promotiontasks/kargo-promote-ring-1.yaml` — reference promotion task
4. `components/kargo/internal-production/projects/kargo-infra-common/base/stage-ring-1-staging.yaml` — staging stage to patch
5. `components/kargo/internal-production/projects/kargo-infra-common/base/stage-ring-2-production.yaml` — production stage to patch
6. `components/kargo/internal-production/projects/kargo-infra-common/kustomization.yaml` — top-level kustomization to patch

## Gather component details

Ask the user for these details. Use AskUserQuestion to collect them
interactively. If the user provided some details in their initial message,
only ask for what's missing.

Required:
- **Component name** — lowercase kebab-case identifier (e.g., `devlake`, `smee`)
- **Container image repos** — one or more image URLs to watch (e.g., `quay.io/konflux-ci/devlake-mcp`)
  - For each image: tag regex pattern (`allowTags`) and selection strategy (`NewestBuild` or `SemVer`)

Optional:
- **Helm chart repo** — OCI or HTTPS chart URL + semver constraint (e.g., `oci://ghcr.io/charts/myapp`, `^1.0.0`)
- **Deployment method** — how the component is deployed. Options:
  - `HelmChartInflationGenerator` — updates a `kargo-helm-generator.yaml` file
  - `kustomize-helmCharts` — updates values in a Helm values file referenced by kustomization
  - `kustomize-images` — updates `images.N.newTag` in `kustomization.yaml`
  - `git-resource-ref` — updates a git resource ref in `kustomization.yaml`
- **Target config file** — the file path that the promotion task should update,
  relative to `components/<component>/<environment>/` (e.g., `deployment/kargo-helm-generator.yaml`, `kustomization.yaml`)
- **YAML keys to update** — which keys to set for each image/chart subscription
- **Promote to production** — whether to create ring-2 (production) promotion task in addition to ring-1 (staging). Default: yes.

## Generate files

All files go under:
`components/kargo/internal-production/projects/kargo-infra-common/<component>/`

### 1. Warehouse — `<component>/warehouse.yaml`

```yaml
---
apiVersion: kargo.akuity.io/v1alpha1
kind: Warehouse
metadata:
  name: <component>
spec:
  freightCreationPolicy: Automatic
  interval: 5m0s
  subscriptions:
    # Add chart subscription if Helm chart provided
    # Add image subscriptions for each container image
```

### 2. Promotion task (staging) — `<component>/promotiontasks/<component>-promote-ring-1.yaml`

```yaml
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
          # Add updates for each image/chart key
```

### 3. Promotion task (production) — `<component>/promotiontasks/<component>-promote-ring-2.yaml`

Same as ring-1 but with `internal-production` in the path instead of `internal-staging`.
Only create this if the user wants production promotion.

### 4. Promotiontasks kustomization — `<component>/promotiontasks/kustomization.yaml`

```yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - <component>-promote-ring-1.yaml
  # - <component>-promote-ring-2.yaml  # if production
```

### 5. Component kustomization — `<component>/kustomization.yaml`

```yaml
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - warehouse.yaml
  - promotiontasks
```

## Patch existing files

IMPORTANT: These patches are ADDITIVE ONLY. Never remove or modify existing
entries. Only append new items to existing arrays.

### 6. Top-level kustomization

Edit `components/kargo/internal-production/projects/kargo-infra-common/kustomization.yaml`:
- Add `- <component>` to the `resources` list (before `commonAnnotations`)

### 7. Staging stage

Edit `components/kargo/internal-production/projects/kargo-infra-common/base/stage-ring-1-staging.yaml`:
- Add a new freight origin entry to `spec.requestedFreight`:
  ```yaml
  - origin:
      kind: Warehouse
      name: <component>
    sources:
      direct: true
  ```
- Add the promotion task call in `spec.promotionTemplate.spec.steps`,
  BEFORE the `git-commit` step:
  ```yaml
  - task:
      name: <component>-promote-ring-1
    as: <component>-promote
    vars:
      - name: srcPath
        value: ./src
  ```

### 8. Production stage (if applicable)

Edit `components/kargo/internal-production/projects/kargo-infra-common/base/stage-ring-2-production.yaml`:
- Add a new freight origin entry to `spec.requestedFreight`:
  ```yaml
  - origin:
      kind: Warehouse
      name: <component>
    sources:
      stages:
        - ring-1-staging
  ```
  Note: production sources freight from the staging stage (not `direct: true`).
- Add the promotion task call in steps, BEFORE `git-commit`:
  ```yaml
  - task:
      name: <component>-promote-ring-2
    as: <component>-promote
    vars:
      - name: srcPath
        value: ./src
  ```

## Validate

After generating all files and patching stages, run:

```sh
kustomize build components/kargo/internal-production/projects/kargo-infra-common/
```

If the build fails, diagnose and fix the issue. Common problems:
- Missing kustomization.yaml in a new directory
- Incorrect resource path references
- YAML indentation errors

## Summary

After completion, tell the user:
- Which files were created
- Which existing files were patched (and what was added)
- Whether `kustomize build` passed
- Remind them to also create the component's deployment config in the
  target environment directory (e.g., `components/<component>/internal-staging/`)
  if it doesn't already exist — that's where the promotion task will write to
