# Configure Kargo promotions

This guide is the short map for changing Kargo in this repository. Use it to
find the right project and file first; the linked guides cover the detailed
steps and exceptions. These manifests are GitOps source: make changes in a PR
and let Argo CD apply them.

## The promotion flow

```text
Warehouse discovers artifacts
        ↓
Freight records the selected release
        ↓
Stage chooses its source, target and promotion policy
        ↓
PromotionTask updates deployment configuration
        ↓
Shared tasks publish a PR, check CI, merge, and check Argo CD
        ↓
Stage verification and soak policy decide whether Freight can advance
```

A **Warehouse** watches Git, image, or chart sources. A **Stage** is one
promotion point, often a ring. A **PromotionTask** prepares the deployment-file
changes. A **Promotion** is one execution of that Stage's steps. Freight carries
the selected artifact versions between stages.

## Choose the project

Choose the project that owns the deployment GitOps repository or operational
domain you are changing. The production project list and current ownership are
in the [production overview](internal-production/README.md#projects).

| If you are changing… | Start here |
|---|---|
| Shared infrastructure deployments | [kargo-konflux-infrastructure](internal-production/projects/kargo-konflux-infrastructure/) |
| Vanguard deployments | [kargo-konflux-vanguard](internal-production/projects/kargo-konflux-vanguard/) |
| Konflux Operator | [kargo-konflux-core](internal-production/projects/kargo-konflux-core/) |
| This repository, including Kargo itself | [kargo-infra-common](internal-production/projects/kargo-infra-common/README.md) |
| A controlled production-workflow example | [kargo-production-playground](internal-production/projects/kargo-production-playground/) |

`kargo-infra-common` has its own promotion workflow and directory layout. The
other domain projects generally use `components/<component>/` with a Warehouse,
preparation task, and Stage files. The staging control plane is a separate Kargo
installation; it is not the same thing as a Stage targeting staging clusters.
See the [topology](README.md#topology) before changing a control plane or shard.

## Where configuration lives

| Change | Configure it here |
|---|---|
| Project namespace, access and automatic promotion eligibility | `projects/<project>/base/` (`Project`, `ProjectConfig`, RBAC) |
| Artifact repositories, image or chart selection, Freight discovery | `projects/<project>/components/<component>/warehouse.yaml` |
| Ring/source progression, shard, merge policy, CI policy, readiness targets, soak and verification | `projects/<project>/components/<component>/stages/` |
| Files changed for a release | The component's `PromotionTask` |
| Reusable PR, CI, merge and deployment-readiness mechanics | `internal-production/shared/promotion-tasks/` |
| Analysis templates and post-promotion checks | `internal-production/shared/verifications/` or a component's own directory |
| Shared credentials and their replication | `internal-production/platform/credentials/` |
| Shard identity and host/project permissions | `internal-production/platform/shard-rbac/` and `components/kargo-shard/` |

Each project Kustomization must include its resources. Domain projects that call
shared tasks must include the shared promotion-task Kustomize Component; adding a
task definition alone does not make a Stage call it.

## Set the Stage policy deliberately

The Stage is the source of truth for the promotion policy. Keep these choices
visible in its YAML:

- `requestedFreight`: the Warehouse and permitted prior Stage(s).
- `shard`: which Kargo shard runs the Promotion and which Argo CD connection it
  uses.
- `promotionTemplate`: the preparation and shared task sequence, ring variables,
  and merge/CI policy.
- `verification`: AnalysisTemplates and their arguments.
- Freight source soak settings: how long a release must remain eligible before
  advancing, when configured.

`mergeMode: manual` means a person merges the promotion PR. It does not turn off
automatic promotion. ProjectConfig controls automatic promotion eligibility;
these are separate settings. Likewise, ring numbers describe a common rollout
shape, not a requirement that every component use every ring. Confirm the
component's actual Stages and targets before copying a policy.

Production readiness tasks also need the correct Argo CD Application names,
namespace, and reader-token Secret for the Stage's target. Use the existing
credential references; never put secret values in Git. See [operations and
credential guidance](internal-production/docs/operations.md#credentials-and-access).

## Add or change a component

1. Choose the project and deployment repository.
2. Pick the closest maintained [source-model example](internal-production/docs/onboarding.md#pick-a-maintained-reference).
3. Configure the Warehouse subscriptions and the component task's exact target
   files. When copying upstream manifests, use the Freight's immutable commit.
4. Add or update the Stages and keep ring-specific gates and targets explicit.
5. Update every affected Kustomization and the project index; check whether the
   project includes shared tasks or verifications.
6. Render the affected project and follow the [local validation
   instructions](internal-production/docs/operations.md#local-validation).

The full [component onboarding guide](internal-production/docs/onboarding.md)
covers source models, task contracts, ring conventions, and validation. For
`kargo-infra-common`, use its [project-specific onboarding guide](internal-production/projects/kargo-infra-common/README.md).

## Find operational guidance

- [Failed promotion and deployment troubleshooting](internal-production/docs/operations.md#troubleshooting)
- [Shared task inputs, outputs, guarantees, and limits](internal-production/shared/promotion-tasks/README.md)
- [Verification setup and AnalysisRun debugging](internal-production/docs/verifications.md)
- [Kargo and shard topology, credentials, upgrades, and local builds](internal-production/docs/operations.md)
- [Project owners](OWNERS)

The docs explain the checked-in configuration. Kustomize rendering does not
evaluate Kargo expressions or prove a live GitHub, merge, Argo CD, or verification
flow; use a controlled promotion to validate behavior changes.
