# kargo-release-common

Kargo project for automated promotion of release-team components deployed
from `infra-common-deployments`. Part of the per-team `kargo-<team>-common`
naming scheme for infra-common-deployments projects.

## Components

- [`internal-services`](components/internal-services/) — promotes the
  `components/internal-services/shared-resources/` snapshot into each
  environment's `shared-resources-ref/` directory
  ([KFLUXINFRA-5021](https://redhat.atlassian.net/browse/KFLUXINFRA-5021)).

## Promotion flow

1. A change merges to `main` under `components/internal-services/shared-resources/`.
2. The `internal-services` Warehouse produces new freight.
3. Ring 1 (`ring-1-internal-services`, shard `infra-common-deployments-staging`)
   auto-promotes: opens a PR syncing `internal-staging/shared-resources-ref`
   via the shared promotion tasks, automatically merged once CI passes, then
   the staging ArgoCD application is verified as synced and healthy.
4. Ring 2 (`ring-2-internal-services`) auto-promotes verified staging freight:
   opens a PR syncing `internal-production/shared-resources-ref`. The PR is
   merged manually (`mergeMode: manual`); the promotion then verifies the
   production ArgoCD application.

Both rings use the shared promotion tasks from
`components/kargo/internal-production/shared/promotion-tasks/`
(publish-promotion-pr, verify-promotion-ci, merge-promotion-pr,
verify-argocd-deployment) with `environment` and `githubRepo:
infra-common-deployments`.

## Secrets

Git credentials are the platform-managed `kargo-promotion-credentials`
(cloned into project namespaces by Kargo). The staging ArgoCD reader token is
the platform-managed `argocd-app-reader-token-common-staging` Secret
replicated into the project namespace (see `platform/credentials/`). The
production ArgoCD reader token is the project-local `argocd-app-reader`
ServiceAccount token.

## Access

Promoters are members of the `konflux-release` group (see the
`kargo-release-common-promoter` ServiceAccount claims). Project resource
administration is granted to `konflux-devprod` and `konflux-release`.
