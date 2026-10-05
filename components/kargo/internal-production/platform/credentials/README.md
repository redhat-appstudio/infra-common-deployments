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
| `kyverno-source-credentials` | Git credential for `konflux-ci/kyverno`; source HTTP steps use `repoCredentials()`; limited to `kargo-konflux-infrastructure` |
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

## Kyverno source repository credential

Kyverno source resolution reads the internal `konflux-ci/kyverno` repository.
It uses the existing `konflux-kargo-bot` App (ID `3794764`), with the
**konflux-ci installation `168199985`**. The `redhat-appstudio` installation
`134364184` continues to serve deployment repository operations.

The `kyverno-source-credentials` ExternalSecret reads only `githubAppID` and
`githubAppPrivateKey` from the existing Vault entry
`production/devprod/konflux-redhat-appstudio-bot`. It sets the konflux-ci
installation ID and matches the exact repository URL
`https://github.com/konflux-ci/kyverno.git`. The existing promotion credential
and its redhat-appstudio installation remain unchanged.

The resolver uses
`repoCredentials('https://github.com/konflux-ci/kyverno.git', 'git').Password`
for both GitHub API requests. Kargo manages the App installation token;
External Secrets refreshes the underlying App fields from Vault every 15
minutes. There is no separate generated-token Secret or token generator.

The `kargo.akuity.io/github-token-scopes` annotation restricts this shared Git
credential to `kyverno` in the `kargo-konflux-infrastructure` Project. Tokens
retain the App installation's permissions; this configuration does not
independently reduce those permissions to read-only. The credential is not
replicated and is not exposed as a shared generic Secret.

Deployment requires Kargo v1.12 or a build with `repoCredentials()` backported
to promotion expressions; see the [v1.12 release notes](https://docs.kargo.io/release-notes/v1.12.0).
The repository currently pins v1.11.3. Upgrade or confirm the backport in the
deployed build before merging or deploying this resolver change. YAML linting
and Kustomize rendering cannot establish runtime function support.

Before retrying a promotion after sync:

1. Confirm the App's konflux-ci installation still includes `kyverno`.
2. Confirm the deployed Kargo build supports `repoCredentials()`.
3. Wait for the `kyverno-source-credentials` ExternalSecret to report `Ready`
   in `kargo-shared-resources`.
4. Retry the affected Kyverno promotion. All rings call the same resolver.

For missing credentials, inspect the ExternalSecret's status and events,
the exact repository URL, and the Project scope annotation. For HTTP 401,
check the App key and installation ID. For HTTP 403/404, check the App
installation's repository access. Do not print Secret values.
