# Authentication with secrets stored in Vault

## GitHub App Authentication

The active ExternalSecret (`konflux-devprod-poc-gh-app.yaml`) creates a Kubernetes Secret that Kargo uses for GitHub App authentication.  
This is the recommended approach for GitHub as it is not tied to a specific GitHub user.

### How it works

1. The PEM-encoded GitHub App private key is stored in Vault at
   `staging/devprod/kargo-secrets-stage` under the key `githubAppPrivateKey`.
2. The ExternalSecret fetches the private key from Vault via the shared
   `appsre-stonesoup-vault` ClusterSecretStore.
3. Non-sensitive configuration fields (`githubAppClientID`,
   `githubAppInstallationID`, `repoURL`) are defined in the ExternalSecret's
   target template and stored in Git.
4. The resulting Kubernetes Secret is labeled `kargo.akuity.io/cred-type: git`
   so Kargo automatically discovers it when accessing matching repositories.

### Kargo docs reference

https://docs.kargo.io/user-guide/security/managing-secrets#github-app-authentication

## Personal Access Token Authentication

The commented-out ExternalSecret in `konflux-devprod-poc-secrets.yaml` shows a PAT-based approach.  
It used `dataFrom` to extract all keys from the same Vault path and created a Secret with `username`/`password` fields.

**Note**: PATs are tied to individual GitHub users and carry broader permissions.
