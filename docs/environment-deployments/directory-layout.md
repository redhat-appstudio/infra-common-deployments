# Canonical Directory Layout — Environment-Based Multi-Cluster Deployments

> **Warning**
> Environment deployments are still under active development. This documentation may change as the implementation evolves.

The standard directory structure every component in infra-common-deployments must follow.

## Table of Contents

1. [Why This Exists](#1-why-this-exists)
2. [How It Works: Kargo + ArgoCD](#2-how-it-works-kargo--argocd)
3. [The Canonical Layout](#3-the-canonical-layout)
4. [Tier Definitions](#4-tier-definitions)
   - 4.1 [Tier 1 — Shared Resources](#41-tier-1--shared-resources)
   - 4.2 [Tier 2 — Environment](#42-tier-2--environment)
   - 4.3 [Tier 3 — Features](#43-tier-3--features)
5. [File Conventions](#5-file-conventions)
   - 5.1 [File Naming](#51-file-naming)
   - 5.2 [One Resource Per File](#52-one-resource-per-file)
   - 5.3 [Patches Directory](#53-patches-directory)
6. [Validation](#6-validation)

---

## 1. Why This Exists

### The Problem

infra-common-deployments deploys the same components across multiple common clusters — internal and external, staging and production. Without a controlled rollout mechanism, changes merged to `main` land on all clusters simultaneously (each cluster's ArgoCD follows `main` with automated sync). A bad configuration change can break production within minutes of merging. There is no safe, gradual rollout path.

### The Solution: Environment-Based Progressive Delivery

We adopt an **environment-based progressive delivery model** — the infra-common-deployments equivalent of the [ring-based model](https://github.com/redhat-appstudio/infra-deployments/blob/main/docs/ring-deployments/directory-layout.md) used in infra-deployments, with no rings. Changes roll out through a sequence of environments, starting from staging and advancing toward production:

| Environment | Purpose | What Happens Here |
|-------------|---------|-------------------|
| **internal-staging** | Staging (internal) | First deployment of the change. Verified with ArgoCD sync health and metrics. |
| **external-staging** | Staging (external) | Same as internal-staging, for external-facing components. |
| **internal-production** | Production (internal) | Production rollout, after manual approval and soak. |
| **external-production** | Production (external) | Same as internal-production, for external-facing components. |

A Kargo **Stage** owns two environments: the `staging` Stage writes `internal-staging/` and, for components that deploy externally, `external-staging/` in a single Promotion; the `production` Stage does the same for `internal-production/` and `external-production/`. Environments inside a Stage are never promoted one at a time.

A change must pass verification in staging before it is promoted to production. Between stages, a **soak time** is enforced — a mandatory waiting period after verification passes, allowing the change to run in the current environment long enough to surface issues that tests alone cannot catch. If verification fails, promotion stops — production is never exposed to a change that broke staging.

Most components in this repository are deployed to internal clusters only. Those have `internal-staging/` and `internal-production/` and nothing else.

### Current Environment/Cluster Layout

| Environment | Cluster | Stage |
|-------------|---------|-------|
| `internal-staging` | `kflux-c-stg-i01` | Staging |
| `external-staging` | `kflux-c-stg-e01` | Staging — external-facing components only |
| `internal-production` | `kflux-c-prd-i01` | Production |
| `external-production` | `kflux-c-prd-e01` | Production — external-facing components only |

## 2. How It Works: Kargo + ArgoCD

**ArgoCD** syncs the Git repository to each common cluster. Each cluster has its own ArgoCD instance that manages the Applications for components deployed to it. ApplicationSets live under `argo-cd-apps/base/{all-clusters,internal,external}/`. The overlay for a cluster in `argo-cd-apps/overlays/` sets the `environment` value (`internal-staging`, `external-staging`, `internal-production`, or `external-production`), so the rendered source path is `components/{component}/{environment}` — the environment directory.

**[Kargo](https://kargo.io)** is the promotion engine that layers on top of ArgoCD. Without Kargo, ArgoCD alone would deploy changes to every cluster the moment they merge — there would be no controlled, environment-by-environment rollout. Kargo watches for new component versions — container image tags, upstream Git commits, Helm charts, or commits in infra-common-deployments itself (e.g. resources authored directly in the repo that need environment-by-environment rollout) — and promotes them environment-by-environment by updating the Git repo. Kargo serializes promotions within each Stage — it queues them and processes one at a time, with verification blocking subsequent promotions. This ensures each change is individually verified before the next one lands.

**Why this matters for directory structure:** Kargo writes to one of two computable paths per environment; given a component name and an environment, the path is either `components/{component}/{environment}/kustomization.yaml` for image and Helm chart-based changes or `components/{component}/{environment}/shared-resources-ref/` for manifest-based changes. Each component has its own [PromotionTask](architecture.md#7-definitions) per environment, but the canonical layout means all PromotionTasks follow the same pattern — the path is computable from `{component}` and `{environment}`, keeping PromotionTask definitions simple and consistent.

**How promotion works:** Kargo does not commit directly to `main`. Instead, it pushes to a branch and opens a PR. Staging promotions auto-merge. Production promotions require approval or are configured for automated merge only when the PR contains Kargo's verified commit. Every promotion remains a reviewable PR. This mirrors the promotion policy described in the [architecture](architecture.md).

---

## 3. The Canonical Layout

One structure. Every component. No exceptions. Given a component name and an environment, the path to any `kustomization.yaml` is computable without looking it up.

```
components/{component-name}/
│
├── shared-resources/                  # TIER 1
│   ├── kustomization.yaml
│   ├── allow-argocd-to-manage-cr.yaml
│   └── monitoring/
│       ├── controller-sm.yaml
│       └── slo-alerts-pr.yaml
│
├── features/                          # TIER 3 (library — not a layer; referenced via components:)
│   ├── rh-certs/
│   │   └── kustomization.yaml
│   ├── debug/
│   │   └── kustomization.yaml
│   └── high-availability/
│       └── kustomization.yaml
│
├── internal-staging/                  # TIER 2 — environment
│   ├── kustomization.yaml             # ← Kargo writes here (image tags, Git SHAs, Helm charts; references `shared-resources-ref`)
│   ├── shared-resources-ref/          # ← Kargo writes here (a 'snapshot' in time of the Tier 1 `shared-resources/` folder)
│   ├── external-secrets/              # ← environment-authored: Kargo ignores
│   │   └── pipelines-as-code-es.yaml
│   └── patches/                       # ← environment patches: Kargo ignores
│       └── resource-limits-patch.yaml
│
├── external-staging/                  # TIER 2 — environment (external components only)
│   ├── kustomization.yaml
│   ├── shared-resources-ref/
│   └── patches/
│       └── resource-limits-patch.yaml
│
├── internal-production/               # TIER 2 — environment
│   ├── kustomization.yaml
│   ├── shared-resources-ref/
│   ├── external-secrets/
│   │   └── pipelines-as-code-es.yaml
│   └── patches/
│       └── resource-limits-patch.yaml
│
├── external-production/               # TIER 2 — environment (external components only)
│   ├── kustomization.yaml
│   ├── shared-resources-ref/
│   └── patches/
│       └── resource-limits-patch.yaml
│
├── OWNERS
└── README.md
```

> **Minimum Viable Layout — Internal-Only Component**
>
> Components deployed only to internal clusters still follow the canonical structure — just with one environment directory per environment they deploy to:
>
> ```
> components/{internal-only-tool}/
> ├── shared-resources/                 # TIER 1
> │   └── kustomization.yaml
> ├── internal-staging/                 # TIER 2
> │   ├── kustomization.yaml
> │   └── shared-resources-ref/
> ├── internal-production/              # TIER 2
> │   ├── kustomization.yaml
> │   └── shared-resources-ref/
> └── OWNERS
> ```
>
> Don't create empty environment directories for environments the component doesn't deploy to.

**Where Kargo Writes**

Kargo **solely** writes to Tier 2: `components/{component}/{environment}/` — the image tags, Helm chart versions, upstream `?ref=` values in `kustomization.yaml`, and the `shared-resources-ref/` folder. The path is computable from `{component}` and `{environment}`, enabling a single generic [PromotionTask](architecture.md#7-definitions).

**Where does my change go?** Two questions:

1. **What type of change is it?**
   - **Helm chart or image-based?** → **Kargo takes care of this automatically**. Kargo automatically detects when a new Helm chart or image is available based on the sources it has configured. The component's [PromotionTask](architecture.md#7-definitions) is defined to make the appropriate changes to the Tier 2 Kustomize files (e.g. external repo reference updates, overwrites to the `newTag` image field etc.) and then automatically open a PR with those changes.
   - **Manifest-based change?** → **Move on to question 2**
2. **Does it differ across environments?**
   - **Yes** → **Tier 2**. This covers **environment-authored configs** like ExternalSecret vault paths or feature flags — authored independently in each environment because the values differ (e.g., staging vault path ≠ production vault path). Changes should occur in the environment folder `components/{component}/{environment}/` because they apply only to that environment.
   - **No, it applies to every environment** → **Tier 1**. This covers all changes not covered by the previous answer. They are promoted environment by environment (staging → production) via `shared-resources-ref/` (see below).

---

## 4. Tier Definitions

Every component follows the same three tiers. Tiers can be minimal but must exist. No skipping tiers, no alternative layouts. Consistency over cleverness.

### Tier Overview

| Tier | Path | Description | Changed By | Promotion Tactic |
|------|------|-------------|------------|------------------|
| **Tier 1** shared-resources/ | `components/{component}/shared-resources/` | Resources shared by every environment | Component team — manual PR | environment-by-environment |
| **Tier 2** environment | `components/{component}/{environment}/` | Environment-specific overlay plus the `shared-resources-ref/` snapshot of Tier 1 | images, Helm Charts, external repos — Kargo; everything else — manual PR | images, Helm Charts, external repos — environment-by-environment; everything else — None |
| **Tier 3** features | `components/{component}/features/{name}/` | Opt-in capabilities (certs, debug, HA). Referenced via `components:` in any tier's Kustomize file. | Component team — manual PR | None |

> **Note:** each environment directory is self-contained: it holds the environment's Kustomize entry point, its `shared-resources-ref/` snapshot, and any environment-specific resources or patches. ArgoCD points at the environment directory.

### 4.1 Tier 1 — Shared Resources

**The Foundation — one common base for staging and production.**

`shared-resources/` is the single source of truth for every environment, staging and production alike. It is authored once; each environment receives it through its own `shared-resources-ref/` copy. That copy is what lets a `shared-resources/` change be promoted staging → production as one unit instead of landing on every cluster at merge time — the content is common, the *timing* is per stage.

Resources that have a base definition shared by all environments belong here: Deployments, Namespaces, RBAC, monitoring resources. If a resource only belongs in a specific subset of environments or has significant differences across environments, it should **NOT** exist here.

> **Promoting shared-resources changes through environments (`shared-resources-ref/`)**
>
> When Tier 1 (`shared-resources/`) changes occur, they still follow an environment-by-environment rollout; Kargo promotes them via `shared-resources-ref/` — a copy of Tier 1's `shared-resources/` folder in each environment directory — which is copied from the component's `shared-resources/` folder in the repo at the SHA commit indicated in the freight so changes never skip environments and are never deployed to more than one environment at a time. This also allows back-to-back manifest-based changes to occur while one change has still not made it through all environments.

```yaml
# components/example-component/shared-resources/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
- allow-argocd-to-manage-cr.yaml           # ArgoCD sync permission
- monitoring.yaml                          # ServiceMonitors, alerts
- rbac/                                    # Platform-level RBACs
- build-pipeline-config/build-pipeline-config.yaml

commonAnnotations:
  argocd.argoproj.io/sync-options: SkipDryRunOnMissingResource=true
```

Rules:

- **Must exist** for every component, even if it contains a single resource.
- **Environment-agnostic resources only.** Only resources without significant structural changes between environments should exist here.
- **Never contains** `images:`, `namespace:`, environment URLs, or environment-specific secrets.
- **Changed by** the component team via manual PR.

### 4.2 Tier 2 — Environment

**The Environment Layer — Where ArgoCD Points.**

This is the environment's deployment root. ArgoCD ApplicationSets point at Tier 2 — one directory per environment. Tier 2 holds two types of content with different lifecycles:

1. **Promoted content** — component versions (image tags, upstream refs) in `kustomization.yaml` and the `shared-resources-ref/` folder containing a snapshot of the foundational resource manifests currently being promoted.
2. **Environment-authored config** — configuration that differs between environments (e.g. ExternalSecret vault paths, environment-specific feature flags, or resource baselines). These are authored independently in each environment's Tier 2 because the values are environment-specific — Kargo does not promote them.

Tier 2 pulls in Tier 1 via `shared-resources-ref`, pins the component version (however the component manages that), and sets the namespace. **This is the only tier Kargo writes to.**

**Directory convention** — separate promoted from environment-authored content visually:

```
internal-staging/
├── kustomization.yaml              # images, upstream refs — Kargo writes here (promoted)
├── shared-resources-ref/           # foundational resources from Tier 1 - Kargo writes here (promoted)
├── external-secrets/               # environment-authored — Kargo ignores, authored per environment
│   └── pipelines-as-code-es.yaml
└── patches/                        # environment patches - Kargo ignores, authored per environment
    └── resource-limits-patch.yaml
```

Promoted resources (image refs and `shared-resources-ref`) and environment-authored resources (ExternalSecrets, feature flags) both live in Tier 2 but in their own subdirectories for clarity.

```yaml
# components/example-component/internal-staging/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
- shared-resources-ref                # ← Tier 1 reference: Kargo copies from the component's shared-resources/ at the freight's commit
- external-secrets/                   # ← environment-authored: Kargo ignores
- https://github.com/konflux-ci/example/config/default?ref=04a4744 # ← promoted: upstream ref

namespace: example-component

images:                               # ← promoted: Kargo writes HERE
- name: quay.io/konflux-ci/example
  newName: quay.io/konflux-ci/example
  newTag: 04a4744321a7fb747f796da783d51fc322aef598

components:
- ../features/rh-certs                # ← Tier 3 opt-in

patches:
- path: patches/resource-limits-patch.yaml
```

Rules:

- **Each environment has exactly one version.** Image tags, Helm chart versions, Git refs — whatever the component pins, every cluster receiving that environment directory gets that version. Versions differ only between environment directories.
- **Upstream resource refs** (`?ref=SHA`) live here. The upstream ref pulls in all component resources — Deployments, RBACs, Services, CRDs — so they are promoted environment-by-environment with the component version.
- **Environment-authored config lives here too.** ExternalSecret vault paths, feature flags, resource baselines — if it differs between environments, it's Tier 2. Place environment-authored resources in their own subdirectory (e.g. `external-secrets/`). These are authored independently in each environment (not promoted by Kargo).
- **Kargo promotes** image tags, upstream `?ref=SHA`, Helm chart versions, Git commits in infra-common-deployments itself (via [Git Warehouse subscriptions](https://docs.kargo.io/user-guide/how-to-guides/working-with-warehouses#git-repository-subscriptions)), and any manifests in the `shared-resources-ref/` folder (AKA a copy of Tier 1).
- **Path formula:** `components/{component}/{environment}/kustomization.yaml` — always.

> **Helm-Based Components**
>
> For components deployed via Helm charts, the `HelmChartInflationGenerator` and its `valuesInline` live in Tier 2 alongside `kustomization.yaml`. Kargo promotes Helm components by updating the generator file — writing the chart `version` and image tags inside `valuesInline`:
>
> ```
> internal-staging/
> ├── kustomization.yaml                  # generators: [kargo-helm-generator.yaml]
> └── kargo-helm-generator.yaml           # ← Kargo writes version + valuesInline.image.tag here
> ```
>
> ```yaml
> # kargo-helm-generator.yaml — Kargo updates version and image tags
> apiVersion: builtin
> kind: HelmChartInflationGenerator
> metadata:
>   name: kargo
> name: kargo
> repo: oci://ghcr.io/akuity/kargo-charts
> version: 1.10.7                         # ← Kargo writes chart version
> namespace: kargo
> releaseName: kargo
> valuesInline:
>   image:
>     repository: quay.io/konflux-ci/kargo
>     tag: 1.10-2cd30bc                   # ← Kargo writes image tag
> ```
>
> The PromotionTask uses `yaml-update` steps to write these fields. Environment-authored Helm values (environment-specific endpoints, OIDC config) are part of the same file — they stay in Tier 2 and are authored independently per environment, just like ExternalSecrets.

> **Adding or Removing an Environment**
>
> - **Adding** an environment for a component requires two steps: (1) create the directory with a `kustomization.yaml` referencing `shared-resources-ref` (seed `shared-resources-ref/` from Tier 1), and (2) make sure the component's ApplicationSet is rendered in that environment's overlay. Without step 2, the directory exists but ArgoCD won't create an Application for it.
> - **Removing** one reverses the process: remove the ArgoCD Application (or update the ApplicationSet), verify no active workloads remain, then delete the directory.

### 4.3 Tier 3 — Features

**Opt-In Capabilities.**

Kustomize Components for optional cross-cutting concerns. Any tier (1 or 2) can opt in by adding a `components:` reference. Use for capabilities that not every environment needs — RH certificates, debug mode, high-availability patches, profiling. Features are never mandatory.

**Why not in `shared-resources/`?** Resources in Tier 1 apply to every environment unconditionally. Features exist separately because not all environments need them — `debug/` belongs only in staging, `high-availability/` only in production, `rh-certs/` only on Red Hat-hosted clusters. Keeping them in `features/` lets each environment opt in selectively without forcing the capability on environments where it is unnecessary or harmful.

```yaml
# components/example-component/features/rh-certs/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1alpha1
kind: Component                                                    # ← Kustomize Component, not Kustomization

patches:
- path: add-rh-certs-patch.yaml
  target:
    name: example-controller-manager
    kind: Deployment

configMapGenerator:
- name: trusted-ca
  options:
    labels:
      config.openshift.io/inject-trusted-cabundle: "true"

namespace: example-component
```

Rules:

- **Kind is `Component`**, not `Kustomization`. Referenced via `components:`, not `resources:`.
- **Any environment can opt in:** staging can enable `rh-certs` while production doesn't.
- **Changed by** the component team via manual PR.

> **Reference Direction — Always Upward**
>
> References always go upward: Tier 2 → Tier 1 (`shared-resources-ref/`). ArgoCD ApplicationSets point at Tier 2 — the environment directory. Each environment directory assembles the full stack by pulling its parent.

---

## 5. File Conventions

### 5.1 File Naming

Every resource file is named `{resource-name}-{type-abbreviation}.yaml`. The resource name comes first, followed by a short abbreviation of the Kubernetes resource type. This makes `ls` output self-documenting — you know what each file contains without opening it.

| Resource Kind | Abbreviation | Example Filename |
|--------------|-------------|-----------------|
| ServiceAccount | `sa` | `konflux-ui-sa.yaml` |
| Role | `role` | `pod-logs-reader-role.yaml` |
| ClusterRole | `cr` | `test-runner-cr.yaml` |
| RoleBinding | `rb` | `pipeline-runner-rb.yaml` |
| ClusterRoleBinding | `crb` | `argocd-manager-crb.yaml` |
| ConfigMap | `cm` | `build-pipeline-config-cm.yaml` |
| Service | `svc` | `webhook-svc.yaml` |
| Deployment | `deploy` | `controller-deploy.yaml` |
| Namespace | `ns` | `example-ns.yaml` |
| ExternalSecret | `es` | `pipelines-as-code-es.yaml` |
| ServiceMonitor | `sm` | `controller-sm.yaml` |
| PrometheusRule | `pr` | `slo-alerts-pr.yaml` |

For custom resources without a standard abbreviation, use a short descriptive suffix: `release-plan-admission-rpa.yaml`, `build-pipeline-selector-bps.yaml`. When no sensible abbreviation exists, the full kind in lowercase is acceptable: `pac-repository.yaml`.

### 5.2 One Resource Per File

Each Kubernetes resource lives in its own YAML file. No multi-document files (`---` separators), no bundled manifests. This makes diffs atomic — a PR that modifies a RoleBinding only touches the RoleBinding file.

Correct — one resource per file:

```
shared-resources/
├── kustomization.yaml
├── build-service-ns.yaml                # Namespace
├── allow-argocd-to-manage-cr.yaml       # ClusterRole
├── pipeline-runner-rb.yaml              # RoleBinding
├── controller-sm.yaml                   # ServiceMonitor
└── external-secrets/                    # subdirectory for related group
    ├── kustomization.yaml
    ├── pipelines-as-code-es.yaml
    └── snyk-token-es.yaml
```

Wrong — multiple resources in one file:

```
shared-resources/
├── kustomization.yaml
└── resources.yaml                       # 4 resources with --- separators
```

- **Exception:** CRDs or upstream manifests pulled via `?ref=SHA` are not split — they are consumed as-is from upstream.
- **Subdirectories** for related groups (e.g. `external-secrets/`, `rbac/`, `monitoring/`) are encouraged when a tier has more than ~6 resource files.

### 5.3 Patches Directory

Strategic merge patches and JSON patches live in a `patches/` subdirectory, not mixed in with resource files. This separates *what gets deployed* (resources) from *what gets modified* (patches). When scanning a directory, you immediately know which files create resources and which modify them.

```
internal-staging/
├── kustomization.yaml
└── patches/
    ├── resource-limits-patch.yaml         # CPU/memory overrides
    ├── replica-count-patch.yaml           # Environment-specific replica count
    └── env-config-patch.yaml              # Environment-specific env vars
```

Reference in kustomization.yaml:

```yaml
patches:
- path: patches/resource-limits-patch.yaml
  target:
    kind: Deployment
    name: controller-manager
- path: patches/replica-count-patch.yaml
  target:
    kind: Deployment
```

Rules:

- **Patch files end with `-patch.yaml`** — distinguishes them from resource files at a glance.
- **One patch per concern.** Don't bundle resource limits and replica counts in the same patch file.
- **Inline patches** (the `patch: |-` form in kustomization.yaml) are acceptable for single-line changes. Move to a file in `patches/` when the patch exceeds ~5 lines.
- **When a directory has only one patch**, the `patches/` subdirectory is still preferred for consistency, but a single patch file at the directory root (e.g. `resources_patch.yaml`) is tolerated.

> **Legacy Naming**
>
> Existing files like `resources_patch.yaml` at the directory root predate this convention. New components must follow the `patches/` directory pattern. Existing components should migrate when next modified — don't create PRs solely to rename files.

---

## 6. Validation

Before submitting a PR, verify that every tier builds successfully. Run `kustomize build` on the environment directory (Tier 2) — this exercises the full chain (Tier 2 → Tier 1 + Tier 3 features):

```bash
# Build an environment directory (Tier 2) — the path ArgoCD points at
kustomize build --enable-helm components/{component}/{environment}/

# Build the component's shared resources (Tier 1) — sanity check
kustomize build components/{component}/shared-resources/
```

If any of these fail, the layout is broken. Common errors:

- **`resource not found`** — a `resources:` entry references a file or directory that doesn't exist.
- **`no such file or directory`** — a `patches:` path is wrong, or a `shared-resources-ref` reference points to the wrong level.
- **`namespace mismatch`** — a Component sets a different `namespace:` than its parent kustomization.
- **`multiple matches`** — a `target:` selector in a patch matches more than one resource. Narrow it with `name:` or `group:`.

For rollback and hotfix procedures, see [Rollback and Reliability](architecture.md#37-rollback-and-reliability) in the architecture doc.
