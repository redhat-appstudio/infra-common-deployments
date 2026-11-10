# Production Kargo

This overlay hosts promotion projects for both `infra-common-deployments` and
`infra-deployments`. Start with [onboarding](docs/onboarding.md) for a new
component, [operations](docs/operations.md) for platform changes, or
[verifications](docs/verifications.md) for post-promotion checks.

## Directory and deployment scope

```text
internal-production/
  deployment/                    # Production control-plane Helm generator
  platform/
    credentials/                 # Central ExternalSecrets
    shard-rbac/                  # Host-side shard access and reader RBAC
    promotion-cleaner/           # Promotion queue maintenance
  shared/
    promotion-tasks/             # Reusable project-scoped PromotionTasks
    verifications/               # Reusable project-scoped AnalysisTemplates
  projects/                      # Seven existing projects and their components
  docs/                          # Onboarding, operations, verifications
```

The [root Kustomization](kustomization.yaml) deploys `deployment/`, `projects/`
and the three platform directories. [Credentials](platform/credentials/kustomization.yaml)
are deployed once in `kargo-shared-resources`; individual definitions determine
shared access and replication. This is not a Component to include per project.

The two `shared/` directories are Kustomize Components, included by project
Kustomizations so their resources receive the project's namespace. Six projects
include promotion tasks; all seven include verifications. Inclusion makes a task
or template available; each Stage explicitly selects what it uses. See the
[shared workflow contract](shared/promotion-tasks/README.md).

## Projects

| Project | Current scope |
|---|---|
| [kargo-infra-common](projects/kargo-infra-common/) | Promotes this repository, including Kargo itself; uses its own workflow tasks |
| [kargo-production-playground](projects/kargo-production-playground/) | Dummy deployment for exercising the shared workflow |
| [kargo-konflux-core](projects/kargo-konflux-core/) | Konflux Operator |
| [kargo-konflux-infrastructure](projects/kargo-konflux-infrastructure/) | Infrastructure components, including repository validator and multi-platform controller |
| [kargo-konflux-kubearchive](projects/kargo-konflux-kubearchive/) | Vector Kubearchive log collector |
| [kargo-konflux-monitoring](projects/kargo-konflux-monitoring/) | Reserved project; shared definitions only, no components currently |
| [kargo-konflux-pulp](projects/kargo-konflux-pulp/) | Pulp access controller |
| [kargo-konflux-mintmaker](projects/kargo-konflux-mintmaker/) | MintMaker controller, Renovate, schedule calculator and OpenShift CLI |
| [kargo-konflux-vanguard](projects/kargo-konflux-vanguard/) | Proxy, notification, crossplane and related components |

[projects/kustomization.yaml](projects/kustomization.yaml) is the deployed project
index. Domain projects keep namespace, Project, promotion policies and RBAC in
`base/`, and component Warehouses, preparation tasks and Stages in
`components/<component>/`. `kargo-infra-common` retains its existing component
folders directly under its project; follow its [own guide](projects/kargo-infra-common/README.md).

## Ownership and policy

Use the existing [Kargo OWNERS](../OWNERS) and applicable project ownership,
including [Vanguard OWNERS](projects/kargo-konflux-vanguard/OWNERS). Directory
organization does not change approval rights or credential access.

A Stage owns its Freight sources, CI requirements, merge mode, readiness targets,
verification and soak policy. A component task owns the deployment-file changes.
Shared tasks provide publication, CI, merge and readiness mechanics. Project
`base/project-config.yaml` controls automatic promotion eligibility separately
from a Stage's PR merge policy. Read the component's current Stage and README
rather than assuming every project uses the same rings or gates.

## MintMaker and Pulp project rename

`konflux-mintmaker` and `konflux-pulp` become `kargo-konflux-mintmaker` and
`kargo-konflux-pulp`, including their namespace, ProjectConfig, project-local
RBAC, production Argo reader binding, shard access and promotion-cleaner
registration. The OIDC groups remain `konflux-mintmaker-team` and `konflux-pulp`.
Shared credentials already replicate to all Kargo projects; the new project
namespaces receive their own credentials and service-account tokens.

A Kubernetes namespace cannot be renamed in place. This creates fresh projects;
Freight, verification history and Promotions are not transferred automatically.
Before merging the rename, finish or abort active promotions in the old projects
and resolve their open infra-deployments PRs. Promotion branch names include the
project name, so old PRs will not be adopted by the new projects. Save any runtime
history needed for audit or rollback before the old definitions are pruned.

After synchronization, verify both new projects, their group access, credential
availability and shard reconciliation. Warehouses rediscover Freight. MintMaker
All MintMaker Rings 0–4 start promotions automatically when Freight meets
their predecessor verification and soak requirements.
Rings 0 and 1 merge promotion PRs automatically after required checks pass;
Rings 2–4 require manual merge. Re-establish verification in ring order rather than treating old
project history as verification in the new project. Pulp retains its existing
promotion policies. Do not run overlapping promotions from old and new projects.

The former Namespace manifests are retained in
[`projects/retained-project-namespaces.yaml`](projects/retained-project-namespaces.yaml)
to prevent namespace deletion during this change. Old project workflow resources
are removed from desired state, and their shard and cleaner bindings are removed.
Retaining namespaces does not prevent garbage collection of resources owned by
pruned Stages or other workflow objects. Removing the former namespaces, any
remaining runtime objects and credentials is a separate explicit cleanup after
verification and backup; this PR does not delete those namespaces.

Rollback: stop promotions in the new projects, then restore the old project
configuration from Git. Retain the new namespaces as well before removing their
project definitions if their runtime state is needed. Kargo configuration
rollback does not revert infra-deployments PRs that have already merged.
