# Shared credentials

This directory is a **Kustomization**, included once by the
[production entry point](../../kustomization.yaml). It creates ExternalSecrets in
`kargo-shared-resources` using the `appsre-stonesoup-vault` ClusterSecretStore.
Do not include it under a project's `components:` list.

External Secrets reads the configured Vault entries and creates the target Secrets.
The generated Secret's credential label and replication annotation determine how
Kargo consumers receive it:

| Target Secret | Access pattern |
|---|---|
| `kargo-promotion-credentials` | Git credential discovery in the shared resources namespace; no replication annotation |
| `kargo-konflux-ci-credentials` | Git credential discovery for konflux-ci repositories, using the URL regex stored in Vault; no replication annotation |
| `argocd-app-reader-token-staging` | Replicated to projects; readiness reads it with `secret()` |
| `argocd-app-reader-token-common-staging` | Replicated to projects; infra-common readiness reads it with `secret()` |
| `kargo-rhobs-staging`, `kargo-rhobs-production` | Replicated to projects for Kanary AnalysisTemplates |
| `konflux-conformance-tests-credentials` | Replicated to projects; contains cluster SA tokens and the conformance GitHub PAT |

`konflux-conformance-tests-credentials` imports Vault entries matching
`stonesoup/production/devprod/konflux-conformance-*`. This includes
`konflux-conformance-tests-credentials`, whose JSON value is stored under the
same key in the combined Secret. The launcher reads its `github_pat` field
from `/credentials/konflux-conformance-tests-credentials`; no separate
Kubernetes Secret is needed. Keep this source entry in Vault.

Replication is configured on `spec.target.template.metadata.annotations` with
`kargo.akuity.io/replicate-to: "*"`. It applies to generated Secrets, not copies
of these ExternalSecrets in each project. Secret names, labels, Vault references
and replication scope are operational contracts; review changes separately from
folder organization.

Production callers may use `argocd-app-reader-token`, which is defined in
project RBAC resources such as [Vanguard reader access](../../projects/kargo-konflux-vanguard/base/rbac/argocd-app-reader.yaml),
not by this directory. Check the selected shard and project namespace when
diagnosing readiness credentials.

See [shared verifications](../../shared/verifications/) and
[shared promotion tasks](../../shared/promotion-tasks/) for consumers.
Platform ownership follows [Kargo OWNERS](../../../OWNERS). Coordinate Vault rotation
with the owners of the source credential; never commit credential values here.

## konflux-ci repository credentials

`kargo-konflux-ci-credentials` follows the same configuration as
`kargo-promotion-credentials`, importing the complete Vault entry at
`production/devprod/konflux-ci-kargo-bot` every 15 minutes.

Store the App fields (`githubAppID`, `githubAppInstallationID`,
`githubAppPrivateKey`) and repository matching fields (`repoURL`,
`repoURLIsRegex`) in that entry. Use the konflux-ci installation and a regex
matching the intended konflux-ci repository URLs, including `.git` URLs.
The App installation must include each repository Kargo will access.

Kyverno's resolver selects this credential automatically with
`repoCredentials('https://github.com/konflux-ci/kyverno.git', 'git').Password`.
Kargo manages the installation token. Wait for the ExternalSecret to report
`Ready` in `kargo-shared-resources` before retrying a promotion.

`repoCredentials()` requires Kargo v1.12 or a backport; see the
[release notes](https://docs.kargo.io/release-notes/v1.12.0). The repository pins
v1.11.3, so confirm runtime support before deploying the resolver change.

## redhat-appstudio repository credentials

`kargo-promotion-credentials` is the shared GitHub App credential for HTTPS
repository URLs under `redhat-appstudio`. The ExternalSecret imports the complete
entry from `stonesoup/production/devprod/konflux-redhat-appstudio-bot`.
Vault owns the App credentials and repository matching configuration
(`repoURL` and `repoURLIsRegex`); manifests do not override these fields.
Any legacy PAT still present in Vault is imported but is not read by promotion
HTTP steps.
The project-local `kargo-infra-common-secrets` is removed so it cannot override
shared credential discovery.

Promotion HTTP steps use `repoCredentials(repositoryURL, 'git').Password` to
resolve an installation token for the repository queried by that step. The
conformance PipelineRun still consumes its separate GitHub PAT; it is not a
Kargo promotion expression and is outside this migration.

Before merging or syncing this migration:

1. Store the replacement App private key as PEM (not base64) in the shared Vault
   entry. Keep the App and installation IDs as strings.
2. Confirm the installation includes every repository to be accessed. Matching
   an organization URL does not grant GitHub access to additional repositories.
3. Grant and approve Checks read and Commit statuses read for authenticated CI
   polling across private repositories, alongside Contents write and Pull
   requests write. Public read access alone is not validation of those grants.
4. Confirm the shared ExternalSecret is Ready before removing project-local
   credentials, then exercise CI, PR publication, and merge in a test promotion.

Kargo v1.12.4 is pinned in the production deployment and supports
`repoCredentials()`. Live Kargo promotion execution remains a rollout check.

## Production Git credential sources

Production Kargo uses only these two shared Git credentials:

| Secret | Vault key |
|---|---|
| `kargo-promotion-credentials` | `production/devprod/konflux-redhat-appstudio-bot` |
| `kargo-konflux-ci-credentials` | `production/devprod/konflux-ci-kargo-bot` |

Both import complete Vault entries, including repository matching configuration.
The project-local production credential is removed in favor of shared discovery.
Staging credential configuration is outside this migration. Generic credentials,
cluster access tokens, and signing keys are separate from this Git credential
inventory.
