# Adding a New Component to a Kargo Project

This guide walks through adding a component to one of the per-domain Kargo projects.

## Projects and their domains

| Project | Domain |
|---------|--------|
| `kargo-konflux-core` | Operator and core platform components |
| `kargo-konflux-infrastructure` | Infrastructure-layer components (authentication, etcd-shield) |
| `kargo-konflux-monitoring` | Observability and monitoring components |
| `kargo-konflux-vanguard` | Proxy and caching components |

Pick the project that matches your component's domain.

---

## Directory structure

Each component lives under `projects/<project>/components/<component>/`:

```
projects/<project>/components/<component>/
  kustomization.yaml        # lists warehouses.yaml, promotiontask, stages dir
  warehouses.yaml           # all Warehouse resources for this component (one file, multi-doc)
  promotiontask.yaml        # the PromotionTask for this component
  stages/
    kustomization.yaml      # lists all ring stage files
    ring-0.yaml             # development ring (optional — not all components have one)
    ring-1.yaml             # staging ring
    ring-2.yaml             # production ring, 24h soak
    ring-3.yaml             # production ring, 48h soak
    ring-4.yaml             # production ring, 72h soak
```

---

## Step 1 — Create the Warehouses

All Warehouses for a component live in a single `warehouses.yaml` file (multi-document YAML).
Each Warehouse tracks one freight source independently — Kargo treats them separately and
stages can subscribe to one or both.

**Example: component with a git manifest source and a container image source:**
```yaml
---
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
          - components/<component>/base
---
apiVersion: kargo.akuity.io/v1alpha1
kind: Warehouse
metadata:
  name: <component>-image-wh
spec:
  freightCreationPolicy: Automatic
  interval: 2h0m0s
  subscriptions:
    - image:
        repoURL: quay.io/konflux-ci/<component>
        imageSelectionStrategy: NewestBuild
        discoveryLimit: 5
        allowTagsRegexes:
          - ^[0-9a-f]{40}$
```

**Example: component with a git manifest source and a Helm chart source:**
```yaml
---
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
          - components/<component>/base
---
apiVersion: kargo.akuity.io/v1alpha1
kind: Warehouse
metadata:
  name: <component>-chart-wh
spec:
  freightCreationPolicy: Automatic
  interval: 2h0m0s
  subscriptions:
    - chart:
        repoURL: oci://quay.io/org/chart-repo
        semverConstraint: ^1.0.0
        discoveryLimit: 5
```

**Example: manifest-only component (single Warehouse):**
```yaml
---
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
          - components/<component>/base
```

---

## Step 2 — Create the PromotionTask

The PromotionTask defines *how* to promote — what files to copy, update, or delete in `infra-deployments`.

For a **manifest-only component** (copies base snapshot between rings):
```yaml
apiVersion: kargo.akuity.io/v1alpha1
kind: PromotionTask
metadata:
  name: promote-<component>-manifests
spec:
  vars:
    - name: srcPath
    - name: component
    - name: prevRing
    - name: targetRing
  steps:
    - uses: delete
      as: delete-old-base-snapshot-folder
      if: ${{ ctx.targetFreight.origin.name == "<component>-manifest-wh" }}
      config:
        path: ${{ vars.srcPath }}/components/${{ vars.component }}/rings/${{ vars.targetRing }}/base/base-snapshot

    - uses: copy
      as: copy-tier-1-folder
      if: ${{ ctx.targetFreight.origin.name == "<component>-manifest-wh" && vars.prevRing == "base" }}
      config:
        inPath: ${{ vars.srcPath }}/components/${{ vars.component }}/base
        outPath: ${{ vars.srcPath }}/components/${{ vars.component }}/rings/${{ vars.targetRing }}/base/base-snapshot

    - uses: copy
      as: copy-prev-ring-base-snapshot-folder
      if: ${{ ctx.targetFreight.origin.name == "<component>-manifest-wh" && vars.prevRing != "base" }}
      config:
        inPath: ${{ vars.srcPath }}/components/${{ vars.component }}/rings/${{ vars.prevRing }}/base/base-snapshot
        outPath: ${{ vars.srcPath }}/components/${{ vars.component }}/rings/${{ vars.targetRing }}/base/base-snapshot
```

For an **image-based component** (updates the image tag in a kustomization):
```yaml
  steps:
    - uses: kustomize-set-image
      as: update-image
      if: ${{ ctx.targetFreight.origin.name == "<component>-image-wh" }}
      config:
        path: ${{ vars.srcPath }}/components/${{ vars.component }}/rings/${{ vars.targetRing }}/base
        images:
          - image: quay.io/konflux-ci/<component>
            tag: ${{ imageFrom("quay.io/konflux-ci/<component>").Tag }}
```

---

## Step 3 — Create the Stages

### Ring-0 (development) — optional

Ring-0 takes freight directly from the Warehouse (no prior stage required) and
auto-merges without manual approval. Suitable for development/overlay clusters.

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
        name: <component>-manifest-wh
      sources:
        direct: true
  promotionTemplate:
    spec:
      vars:
        - name: srcPath
          value: ./src
        - name: repoURL
          value: https://github.com/redhat-appstudio/infra-deployments.git
        - name: component
          value: <component>
        - name: targetRing
          value: ring-0
        - name: prevRing
          value: base
      steps:
        - uses: git-clone
          as: clone
          config:
            repoURL: ${{ vars.repoURL }}
            checkout:
              - branch: main
                path: ${{ vars.srcPath }}
        - task:
            name: promote-<component>-manifests
          as: promote-<component>
          vars:
            - name: srcPath
              value: ${{ vars.srcPath }}
            - name: component
              value: ${{ vars.component }}
            - name: prevRing
              value: ${{ vars.prevRing }}
            - name: targetRing
              value: ${{ vars.targetRing }}
        - uses: git-commit
          as: commit
          config:
            path: ${{ vars.srcPath }}
            message: |
              chore(${{ ctx.stage }}): promote ${{ vars.component }} to ${{ vars.targetRing }}
        - uses: git-push
          as: push
          config:
            path: ${{ vars.srcPath }}
            targetBranch: ${{ ctx.project }}/${{ vars.component }}/${{ vars.targetRing }}
            force: true
        - uses: git-open-pr
          as: open-pr
          continueOnError: true
          config:
            repoURL: ${{ vars.repoURL }}
            sourceBranch: ${{ ctx.project }}/${{ vars.component }}/${{ vars.targetRing }}
            targetBranch: main
            title: "chore(${{ ctx.stage }}): promote ${{ vars.component }} to ${{ vars.targetRing }}"
            description: |
              ### ${{ ctx.stage }}

              | | |
              |---|---|
              | **Component** | `${{ vars.component }}` |
              | **Project** | `${{ ctx.project }}` |
              | **Freight** | `${{ ctx.targetFreight.alias }}` |

              Auto-merged after CI passes.

              > Branch is force-pushed each promotion cycle. Do not commit directly.
            labels:
              - ring-0
              - automated-promotion
              - component/${{ vars.component }}
        - task:
            name: wait-for-ci
          as: wait-for-ci
          vars:
            - name: commitSHA
              value: ${{ outputs['push'].commit }}
            - name: skipProwChecks
              value: "true"   # set to "false" and add requiredProwChecks if Prow runs on this component
        - uses: http
          as: find-pr
          retry:
            timeout: 5m0s
            errorThreshold: 10
          config:
            method: GET
            url: https://api.github.com/repos/redhat-appstudio/infra-deployments/pulls?head=redhat-appstudio:${{ ctx.project }}/${{ vars.component }}/${{ vars.targetRing }}&state=open
            headers:
              - name: Authorization
                value: Bearer ${{ secret('kargo-promotion-credentials').github_pat }}
              - name: Accept
                value: application/vnd.github+json
            outputs:
              - name: prNumber
                fromExpression: response.body[0].number
            successExpression: response.status == 200 && len(response.body) > 0
            timeout: 30s
        - uses: git-merge-pr
          as: merge-pr
          retry:
            timeout: 2h0m0s
          config:
            repoURL: ${{ vars.repoURL }}
            prNumber: ${{ outputs['find-pr'].prNumber }}
            mergeMethod: squash
            wait: true
```

### Ring-1 (staging) — required

Ring-1 sources from ring-0 (or direct from Warehouse if no ring-0). Auto-merges
after CI passes. Runs post-promotion verification via Kanary.

Key differences from ring-0:
- `shard: infra-deployments-staging`
- `sources.stages: [ring-0-<component>]` (or `direct: true` if no ring-0)
- `verification` block with `kanary-staging`
- Adds `wait-for-infra-deployments-argocd-sync` task after merge

```yaml
spec:
  shard: infra-deployments-staging
  requestedFreight:
    - origin:
        kind: Warehouse
        name: <component>-manifest-wh
      sources:
        stages:
          - ring-0-<component>   # or direct: true if no ring-0
  verification:
    analysisTemplates:
      - name: kanary-staging
    args:
      - name: clusters
        value: stone-stg-rh01|stone-stage-p01
      - name: expected-cluster-count
        value: "2"
```

### Rings 2–4 (production) — required for any component reaching production

Production rings are **mandatory** for components that promote beyond staging.
Skipping or shortening soak times is not permitted — they are a hard gate that
blocks the next ring from receiving freight until the soak duration has elapsed.

Rings 2–4 also require **manual PR approval** (use `git-wait-for-pr` instead of
`git-merge-pr`).

| Ring | Soak | Clusters | Verification |
|------|------|----------|-------------|
| ring-2 | **24h** from ring-1 | stone-prod-p01, kflux-fedora-01, kflux-prd-rh03 | `kanary-production` |
| ring-3 | **48h** from ring-2 | stone-prd-rh01 | `kanary-production` |
| ring-4 | **72h** from ring-3 | kflux-prd-rh02 | `kanary-production` |

The `requiredSoakTime` field on each freight source enforces this — Kargo will not
allow promotion to the next ring until the freight has been healthy in the current
ring for the full soak period. Do not remove or reduce these values.

Replace `git-merge-pr` with:
```yaml
        - uses: git-wait-for-pr
          as: wait-for-pr
          retry:
            timeout: 168h0m0s
          config:
            repoURL: ${{ vars.repoURL }}
            prNumber: ${{ outputs['find-pr'].prNumber }}
        - uses: http
          as: verify-merged
          config:
            method: GET
            url: https://api.github.com/repos/redhat-appstudio/infra-deployments/pulls/${{ outputs['find-pr'].prNumber }}
            headers:
              - name: Authorization
                value: Bearer ${{ secret('kargo-promotion-credentials').github_pat }}
              - name: Accept
                value: application/vnd.github+json
            successExpression: response.status == 200 && response.body.merged == true
            failureExpression: response.status == 200 && response.body.state == 'closed' && response.body.merged == false
            timeout: 30s
```

---

## Step 4 — Wire up the project

### `components/<component>/kustomization.yaml`
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - warehouses.yaml
  - promotiontask.yaml
  - stages
```

### `stages/kustomization.yaml`
```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - ring-0.yaml   # omit if no ring-0
  - ring-1.yaml
  - ring-2.yaml   # omit if no production rings
  - ring-3.yaml
  - ring-4.yaml
```

### `projects/<project>/kustomization.yaml` — add the component
```yaml
resources:
  - base
  - components/<existing-component>
  - components/<component>          # add this line
```

### `projects/<project>/base/project-config.yaml` — add promotion policies
```yaml
spec:
  promotionPolicies:
    - stage: ring-0-<component>
      autoPromotionEnabled: true
    - stage: ring-1-<component>
      autoPromotionEnabled: true
    - stage: ring-2-<component>     # false = manual gate for production
      autoPromotionEnabled: false
```

---

## Step 5 — Verify

```sh
kustomize build components/kargo/internal-production/projects/<project>/
```

No errors = ready to PR.

---

## Prow checks

Components with Prow CI (e.g. `appstudio-e2e-tests`) should set:
```yaml
- task:
    name: wait-for-ci
  vars:
    - name: requiredProwChecks
      value: "^ci/prow/appstudio-e2e-tests$"
    - name: skipProwChecks
      value: "false"
```

Components without Prow (image-only or operator updates) set `skipProwChecks: "true"`.

---

## Stage colors by environment

| Ring | Environment label | Color |
|------|------------------|-------|
| ring-0 | `development` | `blue` |
| ring-1 | `staging` | `yellow` |
| ring-2 | `production` | `orange` |
| ring-3 | `production` | `red` |
| ring-4 | `production` | `purple` |
