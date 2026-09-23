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
  projects/                      # Six existing projects and their components
  docs/                          # Onboarding, operations, verifications
```

The [root Kustomization](kustomization.yaml) deploys `deployment/`, `projects/`
and the three platform directories. [Credentials](platform/credentials/kustomization.yaml)
are deployed once in `kargo-shared-resources`; individual definitions determine
shared access and replication. This is not a Component to include per project.

The two `shared/` directories are Kustomize Components, included by project
Kustomizations so their resources receive the project's namespace. Five projects
include promotion tasks; all six include verifications. Inclusion makes a task
or template available; each Stage explicitly selects what it uses. See the
[shared workflow contract](shared/promotion-tasks/README.md).

## Projects

| Project | Current scope |
|---|---|
| [kargo-infra-common](projects/kargo-infra-common/) | Promotes this repository, including Kargo itself; uses its own workflow tasks |
| [kargo-production-playground](projects/kargo-production-playground/) | Dummy deployment for exercising the shared workflow |
| [kargo-konflux-core](projects/kargo-konflux-core/) | Konflux Operator |
| [kargo-konflux-infrastructure](projects/kargo-konflux-infrastructure/) | Infrastructure components, including repository validator and multi-platform controller |
| [kargo-konflux-monitoring](projects/kargo-konflux-monitoring/) | Reserved project; shared definitions only, no components currently |
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
