# ArgoCD Repository Secrets

The ArgoCD Repository Secrets component consists of ExternalSecrets that allow the common Konflux clusters to deploy resources from any private repository in the [redhat-appstudio GitHub organization](https://github.com/redhat-appstudio).


## Secrets and Configurations (Vault)

External Secrets sync from Vault (via `appsre-stonesoup-vault`) into Kubernetes `Secret`s. Paths are under `<environment>/infrastructure/github-argocd/<cluster_name>`. See the [Argo CD docs](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/#repositories) for more information on configuring repositories for ArgoCD.
