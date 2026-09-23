# Operate Kargo

[Production overview](../README.md) · [Onboarding](onboarding.md) · [Verification](verifications.md)

## Configuration sources

Read current chart/image versions and controller settings from the
[production generator](../deployment/kargo-helm-generator.yaml) and
[staging generator](../../internal-staging/deployment/kargo-helm-generator.yaml).
Both are full installations with Route/OAuth integration; staging is a separate
test control plane. Project policies live in each project's `base/`.

The [Kargo ApplicationSet](../../../../argo-cd-apps/base/internal/kargo/appset.yaml)
and the shard ApplicationSets under `argo-cd-apps/overlays/` select the deployed
paths. Moving documentation or source folders does not change resource identity,
namespace, runtime permissions or rollout policy.

## Cross-cluster connections

Production hosts the project state. Shards use a host kubeconfig to access that
state while executing against their configured Argo CD namespace.

| Stage shard | Controller location | Argo CD namespace | Generator |
|---|---|---|---|
| `infra-common-deployments-staging` | Staging | `argocd-local` | [generator](../../../kargo-shard/internal-staging/infra-common-deployments/deployment/kargo-shard-helm-generator.yaml) |
| `infra-deployments-staging` | Staging | `argocd-infra-deployments` | [generator](../../../kargo-shard/internal-staging/infra-deployments/deployment/kargo-shard-helm-generator.yaml) |
| `infra-deployments-production` | Production | `argocd-infra-deployments` | [generator](../../../kargo-shard/internal-production/infra-deployments/deployment/kargo-shard-helm-generator.yaml) |

These are controller-only installs. The host runs the API and manages Kargo
resources. The production shard namespace is
`kargo-shard-infra-deployments-production`, distinct from the staging shard's
`kargo-shard-infra-deployments` lease namespace on the host.

The shard generators reference `production-kargo-kubeconfig` through
`kubeconfigSecrets.kargo`. Its ExternalSecret uses the existing
`staging/devprod/kargo-shard-kubeconfig` Vault path, including for the production
shard. Host-side [shard RBAC](../platform/shard-rbac/) grants the existing
`kargo-shard-staging` identity controller, project/shared-namespace and lease
access. Check the actual bindings before changing connectivity.

Verification requires the [production RolloutManager](../../../argo-rollouts/internal-production/rollout-manager.yaml)
and its CRDs. Relevant controllers use the configured Rollouts integration and
`controllerInstanceID: kargo`; inspect the generator and controller RBAC when
AnalysisRuns are not being created or reconciled.

## Credentials and access

[platform/credentials](../platform/credentials/) deploys ExternalSecrets once in
`kargo-shared-resources`. Their templates distinguish Git credentials from generic
API/verification credentials and explicitly select replication. Shared promotion
API calls use `sharedSecret('konflux-kargo-git-operations')`; readiness tasks use
the configured project-local reader secret. These lookup scopes are different.
Project-specific credentials, including those for `kargo-infra-common`, retain
their existing locations and access model.

ExternalSecrets use the [AppSRE Vault ClusterSecretStore](../../../cluster-secret-store/base/appsre-stonesoup-vault-secret-store.yaml).
Inspect its namespace conditions and ExternalSecret status when synchronization
fails. Rotate credentials in the existing source system and confirm consumers
receive the update; a documentation/layout change does not authorize expanding
replication or replacing identities. Keep tokens, kubeconfigs and private keys
out of Git and diagnostic output.

## Upgrade Kargo

Kargo is itself a promoted [component in kargo-infra-common](../projects/kargo-infra-common/kargo/).
Its Warehouse selects chart and image artifacts and enforces its configured
compatibility criteria. The component's Ring 1 task updates the staging Helm
generator; Ring 2 updates the production generator through the project's current
promotion policy. Read the [staging Stage](../projects/kargo-infra-common/base/staging-stage.yaml),
[production Stage](../projects/kargo-infra-common/base/production-stage.yaml) and
[project policy](../projects/kargo-infra-common/base/project-config.yaml) before an upgrade.

The current [Ring 2 preparation task](../projects/kargo-infra-common/kargo/promotiontasks/kargo-promote-ring-2.yaml)
updates the production control plane and all three shard generators together.
Keep shard chart/image versions compatible with the host during rollout, and
review all of those updates as well as the staging full installation.

## Local validation

Run from the repository root, with the project's required toolchain:

```sh
kustomize build --enable-helm components/kargo/internal-staging/
kustomize build --enable-helm components/kargo/internal-production/
kustomize build --enable-helm components/kargo-shard/internal-staging/infra-common-deployments/
kustomize build --enable-helm components/kargo-shard/internal-staging/infra-deployments/
kustomize build --enable-helm components/kargo-shard/internal-production/infra-deployments/
kustomize build components/kargo/internal-production/projects/kargo-infra-common/
kustomize build components/kargo/internal-production/projects/kargo-konflux-vanguard/
```

Render any other affected project too. Repository change validation also includes
all four `argo-cd-apps/overlays/` environments (`internal-staging`,
`internal-production`, `external-staging`, `external-production`) and applicable
YAML checks. Kube-linter excludes Kargo and shard Helm output; that exclusion is
not runtime validation. A build does not evaluate Kargo expressions, exercise
GitHub CI/merge handling or establish deployment readiness.

For a directory-only move, compare rendered resource identities and specifications
before and after. Keep namespaces, labels, resource names, replication annotations,
RBAC and Stage policy unchanged.

## Troubleshooting

| Symptom | Inspect |
|---|---|
| Shard cannot reach the host | Host kubeconfig ExternalSecret status, endpoint and host-side shard RBAC |
| No verification AnalysisRun | Stage verification references, template namespace, Rollouts CRDs/integration, controller instance ID and `kargo-controller-rollouts` binding |
| Wrong Applications or readiness timeout | `spec.shard`, shard Argo namespace, component prefix, complete cluster list and reader-secret access; shared readiness checks the exact confirmed revision |
| Clone, push or PR failures | Git credential selection and ExternalSecret status; repository/branch permissions |
| CI polling fails or waits | Required selectors, checked SHA, GitHub authentication/rate limits and the API credential used by that task |
| Production PR waits for a person | Stage `mergeMode`; automatic promotion and automatic merge are separate policies |
| Freight does not advance | Source Stage verification, configured soak eligibility and project promotion policy |
| Pending promotions accumulate | [Promotion cleaner](../platform/promotion-cleaner/README.md) configuration and logs; distinguish Pending from active work before intervention |
| Manifests do not appear | Argo CD ApplicationSet paths and application reconciliation errors |

Use the failed Promotion step and its explicit outputs to locate the failure.
For analysis-specific diagnosis, see [verification troubleshooting](verifications.md#debugging).
