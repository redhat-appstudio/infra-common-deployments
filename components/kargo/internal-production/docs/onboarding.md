# Onboarding a New Component to Kargo

This guide describes how to add a new infrastructure component to an existing
Kargo project so that it is promoted automatically through deployment rings.

## Prerequisites

Before starting, ensure the following conditions are met:

1. **Ring-based directory structure exists in infra-deployments.** The
   component must already have a `-rd` directory (e.g.,
   `components/my-component-rd/`) in the
   [infra-deployments](https://github.com/redhat-appstudio/infra-deployments)
   repository with the standard ring layout (`base/`, `rings/ring-0/`,
   `rings/ring-1/`, etc.).

2. **ArgoCD ApplicationSet is deployed.** The component must have an
   ApplicationSet in the `rd-staging` overlay that generates ArgoCD
   Applications for the target staging clusters.

3. **Target Kargo project exists.** Identify the Kargo project where the
   component belongs:
   - `kargo-infra-deployments` — general infra-deployments components
   - `kargo-konflux-core` — core Konflux operator components
   - `kargo-konflux-infrastructure` — infrastructure services (etcd-shield,
     authentication, repository-validator)
   - `kargo-konflux-vanguard` — early-adopter components
     (artifact-registry-proxy, container-image-proxy, notification-controller)

4. **Shared components are included.** The target project's
   `kustomization.yaml` must reference the shared Kustomize Components:
   ```yaml
   components:
     - ../../kargo-shared-secrets
     - ../../kargo-shared-promotion-tasks
     - ../../kargo-shared-verifications
   ```

## Step 1: Create the Component Directory

Create the following directory structure under the target project:

```
projects/<project>/components/<component>/
├── kustomization.yaml
├── warehouse.yaml
├── promotiontask.yaml
└── stages/
    ├── kustomization.yaml
    ├── ring-0.yaml
    └── ring-1.yaml
```

### `kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - warehouse.yaml
  - promotiontask.yaml
  - stages
```

## Step 2: Define the Warehouse

The Warehouse defines what artifact sources Kargo monitors. Choose the
pattern that matches the component's deployment model.

### Pattern A: Container Image (Quay)

Use when the component is built as a container image and tagged with commit
SHAs.

```yaml
apiVersion: kargo.akuity.io/v1alpha1
kind: Warehouse
metadata:
  name: <component>
spec:
  freightCreationPolicy: Automatic
  interval: 30m0s
  subscriptions:
    - image:
        repoURL: quay.io/konflux-ci/<image-name>
        imageSelectionStrategy: NewestBuild
        discoveryLimit: 5
        allowTagsRegexes:
          - ^[0-9a-f]{40}$
```

### Pattern B: Git Manifest Changes

Use when the component's base manifests (Tier 1) change in the
`infra-deployments` repository and must be copied into ring-specific
`base-snapshot/` directories.

```yaml
apiVersion: kargo.akuity.io/v1alpha1
kind: Warehouse
metadata:
  name: <component>-manifest-wh
spec:
  freightCreationPolicy: Automatic
  interval: 2h0m0s
  subscriptions:
    - git:
        repoURL: https://github.com/redhat-appstudio/infra-deployments.git
        commitSelectionStrategy: NewestFromBranch
        branch: main
        includePaths:
          - 'components/<component>-rd/base'
```

### Pattern C: Private Git Repository

Use when the component references manifests from a private repository.
Requires a git credential secret with `kargo.akuity.io/cred-type: git` label
in the project namespace.

```yaml
apiVersion: kargo.akuity.io/v1alpha1
kind: Warehouse
metadata:
  name: <component>-git-wh
spec:
  freightCreationPolicy: Automatic
  interval: 2h0m0s
  subscriptions:
    - git:
        repoURL: https://github.com/<org>/<private-repo>.git
        commitSelectionStrategy: NewestFromBranch
        branch: main
        discoveryLimit: 5
        includePaths:
          - 'components/<component>'
```

**Note:** A component may have multiple Warehouses (e.g., one for images and
one for manifests). Each Warehouse produces Freight independently.

## Step 3: Define the Promotion Task

The PromotionTask contains only the component-specific update logic. The
shared `git-workflow-infra-deployments` task handles the git commit, push, PR
creation, CI wait, merge, and ArgoCD sync verification.

### Pattern A: Image Tag and External Repository Reference

```yaml
apiVersion: kargo.akuity.io/v1alpha1
kind: PromotionTask
metadata:
  name: promote-<component>
spec:
  vars:
    - name: srcPath
    - name: targetRing
  steps:
    - uses: yaml-update
      as: update-ref
      config:
        path: ${{ vars.srcPath }}/components/<component>-rd/rings/${{ vars.targetRing }}/base/kustomization.yaml
        updates:
          - key: images.0.newTag
            value: ${{ imageFrom("quay.io/konflux-ci/<image>").Tag }}
          - key: resources.0
            value: https://github.com/<org>/<repo>/config/default?ref=${{ imageFrom("quay.io/konflux-ci/<image>").Tag }}
```

### Pattern B: Base-Snapshot Copy (Manifest Promotion)

```yaml
apiVersion: kargo.akuity.io/v1alpha1
kind: PromotionTask
metadata:
  name: promote-<component>-manifests
spec:
  vars:
    - name: srcPath
    - name: component
      value: <component>-rd
    - name: prevRing
    - name: targetRing
  steps:
    - uses: delete
      as: delete-old-base-snapshot
      if: ${{ ctx.targetFreight.origin.name == "<component>-manifest-wh" }}
      config:
        path: ${{ vars.srcPath }}/components/${{ vars.component }}/rings/${{ vars.targetRing }}/base/base-snapshot
    - uses: copy
      as: copy-from-tier-1
      if: ${{ ctx.targetFreight.origin.name == "<component>-manifest-wh" && vars.prevRing == "base" }}
      config:
        inPath: ${{ vars.srcPath }}/components/${{ vars.component }}/base
        outPath: ${{ vars.srcPath }}/components/${{ vars.component }}/rings/${{ vars.targetRing }}/base/base-snapshot
    - uses: copy
      as: copy-from-previous-ring
      if: ${{ ctx.targetFreight.origin.name == "<component>-manifest-wh" && vars.prevRing != "base" }}
      config:
        inPath: ${{ vars.srcPath }}/components/${{ vars.component }}/rings/${{ vars.prevRing }}/base/base-snapshot
        outPath: ${{ vars.srcPath }}/components/${{ vars.component }}/rings/${{ vars.targetRing }}/base/base-snapshot
```

## Step 4: Define the Stages

Each stage defines a ring in the promotion pipeline. Every stage follows the
same three-step pattern:

1. `git-clone` — Clone the infra-deployments repository.
2. Component-specific promote task — Apply the component's update logic.
3. `git-workflow-infra-deployments` — Commit, push, open PR, wait for CI,
   merge, and verify ArgoCD sync.

### Ring-0 Stage (Passthrough or Development)

If the component is not deployed to a development environment, use a
passthrough stage:

```yaml
apiVersion: kargo.akuity.io/v1alpha1
kind: Stage
metadata:
  name: ring-0-<component>
  labels:
    konflux-environment: development
  annotations:
    kargo.akuity.io/color: blue
spec:
  requestedFreight:
    - origin:
        kind: Warehouse
        name: <component>
      sources:
        direct: true
  promotionTemplate:
    spec:
      steps:
        - uses: compose-output
          as: passthrough
          config:
            status: skipped
```

If the component IS deployed to development, use the full three-step pattern
with `prevRing: base`.

### Ring-1 Stage (Staging)

```yaml
apiVersion: kargo.akuity.io/v1alpha1
kind: Stage
metadata:
  name: ring-1-<component>
  labels:
    konflux-environment: staging
  annotations:
    kargo.akuity.io/color: yellow
spec:
  shard: infra-deployments-staging
  requestedFreight:
    - origin:
        kind: Warehouse
        name: <component>
      sources:
        stages:
          - ring-0-<component>
  verification:
    analysisTemplates:
      - name: kanary-staging
    args:
      - name: clusters
        value: stone-stg-rh01|stone-stage-p01
      - name: expected-cluster-count
        value: "2"
  promotionTemplate:
    spec:
      vars:
        - name: srcPath
          value: ./src
        - name: component
          value: <component>
        - name: targetRing
          value: ring-1
        - name: prevRing
          value: ring-0
      steps:
        - uses: git-clone
          as: clone
          config:
            repoURL: https://github.com/redhat-appstudio/infra-deployments.git
            checkout:
              - branch: main
                path: ${{ vars.srcPath }}
        - task:
            name: promote-<component>
          as: promote
          vars:
            - name: srcPath
              value: ${{ vars.srcPath }}
            - name: targetRing
              value: ${{ vars.targetRing }}
        - task:
            name: git-workflow-infra-deployments
          as: git-workflow
          vars:
            - name: srcPath
              value: ${{ vars.srcPath }}
            - name: component
              value: ${{ vars.component }}
            - name: targetRing
              value: ${{ vars.targetRing }}
            - name: skipProwChecks
              value: "true"
            - name: clusters
              value: "stone-stg-rh01|stone-stage-p01"
```

### `stages/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ring-0.yaml
  - ring-1.yaml
```

## Step 5: Register the Component in the Project

Add the component to the project's `kustomization.yaml`:

```yaml
resources:
  - base
  - components/<component>
```

Add auto-promotion policies to `base/project-config.yaml`:

```yaml
spec:
  promotionPolicies:
    - stage: ring-0-<component>
      autoPromotionEnabled: true
    - stage: ring-1-<component>
      autoPromotionEnabled: true
```

## Step 6: Validate

Run the Kustomize build and verify that the output includes the expected
Warehouse, PromotionTask, and Stage resources:

```bash
kustomize build components/kargo/internal-production/projects/<project>/
```

Verify that the component's resources appear in the output:

```bash
kustomize build components/kargo/internal-production/projects/<project>/ | \
  grep -E 'kind: (Warehouse|PromotionTask|Stage)' -A1 | \
  grep 'name:' | grep '<component>'
```

## Shared Resources Reference

The following shared Kustomize Components are available to all projects.
Do not duplicate their contents in project directories.

| Shared Component | What It Provides | Documentation |
| --- | --- | --- |
| `kargo-shared-secrets` | Vault-synced ExternalSecrets (GitHub PAT, ArgoCD tokens, RHOBS credentials, conformance SA tokens) | [README](../kargo-shared-secrets/README.md) |
| `kargo-shared-promotion-tasks` | Reusable PromotionTasks (`wait-for-ci`, `wait-for-infra-deployments-argocd-sync`, `git-workflow-infra-deployments`) | [README](../kargo-shared-promotion-tasks/README.md) |
| `kargo-shared-verifications` | Post-promotion AnalysisTemplates (kanary smoke tests, conformance e2e tests) | [README](../kargo-shared-verifications/README.md) |
