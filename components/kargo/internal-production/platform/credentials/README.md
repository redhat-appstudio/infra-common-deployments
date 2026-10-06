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
| `konflux-kargo-git-operations` | Generic credential read with `sharedSecret()` by GitHub HTTP steps; no replication annotation |
| `kargo-konflux-ci-credentials` | Git credential discovery for konflux-ci repositories, using the URL regex stored in Vault; no replication annotation |
| `argocd-app-reader-token-staging` | Replicated to projects; readiness reads it with `secret()` |
| `kargo-rhobs-staging`, `kargo-rhobs-production` | Replicated to projects for Kanary AnalysisTemplates |
| `konflux-conformance-sa` | Replicated to projects for the conformance launcher |
| `konflux-conformance-tests-credentials` | Replicated to projects for conformance tests |

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
