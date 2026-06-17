---
name: kargo-onboard
description: >
  Use when onboarding a new component to Kargo automated promotion in
  kargo-infra-common — creating warehouses, promotion tasks, and patching
  stage files
---

# Kargo Component Onboarding

Scaffold a new component into the `kargo-infra-common` Kargo promotion
pipeline.

## Skill Invocation Policy

This skill is **user-invoked only**. It must be run locally by a human operator using Claude Code on their machine — it is not available to Fullsend or any other automated agent framework.

- **Who**: Human users (SREs, component leads) running Claude Code locally.
- **Not**: Fullsend, CI pipelines, bots, or any headless/automated agent runner.
- **Why**: Kargo onboarding decisions require human judgment, context, and accountability. Automated agents lack the cross-team context needed to make sound promotion pipeline trade-offs. Every change to these configs should have a human author who can defend the decision in review.

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

Read the reference implementation before generating each file.

### 1. Warehouse — `<component>/warehouse.yaml`

Reference: `components/kargo/internal-production/projects/kargo-infra-common/kargo/warehouse.yaml`

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

Reference: `components/kargo/internal-production/projects/kargo-infra-common/kargo/promotiontasks/kargo-promote-ring-1.yaml`

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

Read then edit `components/kargo/internal-production/projects/kargo-infra-common/kustomization.yaml`:
- Add `- <component>` to the `resources` list (before `commonAnnotations`)

### 7. Staging stage

Read then edit `components/kargo/internal-production/projects/kargo-infra-common/base/stage-ring-1-staging.yaml`:
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

Read then edit `components/kargo/internal-production/projects/kargo-infra-common/base/stage-ring-2-production.yaml`:
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

After generating all files and patching stages, run these checks:

1. **Kustomize build** — must exit 0:
   ```sh
   kustomize build components/kargo/internal-production/projects/kargo-infra-common/
   ```
2. **Warehouse subscriptions** — verify the built output contains a Warehouse
   whose `subscriptions` list matches the images/charts the user provided.
3. **PromotionTask paths** — confirm each task's `config.path` points to the
   correct environment directory (`internal-staging` for ring-1,
   `internal-production` for ring-2).
4. **Stage patching** — confirm `requestedFreight` in both stages references
   the new Warehouse by name, and `steps` includes the new promotion task
   before `git-commit`.
5. **No orphan resources** — every YAML file is listed in a `kustomization.yaml`.

If the build fails, diagnose and fix before reporting success.

## Summary

After completion, tell the user:
- Which files were created
- Which existing files were patched (and what was added)
- Whether `kustomize build` passed
- Remind them to also create the component's deployment config in the
  target environment directory (e.g., `components/<component>/internal-staging/`)
  if it doesn't already exist — that's where the promotion task will write to
