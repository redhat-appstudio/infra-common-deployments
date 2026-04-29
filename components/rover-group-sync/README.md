# Rover Group Sync

The Rover Group Sync component consists of a scheduled job that ensures `Group` YAML manifest files in a `groups/<environment>/` directory of a Git repository are kept up to date with Konflux's [Rover][rover] LDAP groups. The component runs `oc adm groups sync` (LDAP only), then commits and pushes to the configured branch and Git repository when there are changes to the groups.

The container image and entrypoint script are maintained in the [infrastructure](https://github.com/redhat-appstudio/infrastructure) repository under `maintenance/rover-group-sync`.

[rover]: https://rover.redhat.com/

## Layout

`Secret`s spawned from `ExternalSecret`s in the `external-secrets/` directory are mounted into a `CronJob` along with a `ConfigMap` generated using the file(s) in the `config/` directory. The `CronJob` runs in the associated `Namspace` using the associated `ServiceAccount`.

## Default Behavior

**Schedule:** every 15 minutes
**Concurrency:** `Forbid` (no overlapping runs).
**Volume Mounts:** named to satisfy the expected default environment variable paths
**Environment:** defaults to a staging environment with `ENVIRONMENT` being set to 'staging'

## Secrets and Configurations (Vault)

External Secrets sync from Vault (via `appsre-stonesoup-vault`) into Kubernetes `Secret`s. Paths are under `staging/infrastructure/group-sync/`. Currently, all Vault secrets that need to be mounted have keys and mount paths that line up with the expected default environment variable paths in the script (see [Environment Variables](#environment-variables) below). If a Secret's keys change, the new value **must** be passed in via the appropriate env variable.

The LDAP sync config template in `base/config/ldap-sync-config.yaml` has placeholders to prevent secret credentials from being committed to the repository; the script injects the bind DN, password, and CA path at runtime using environment variables ties to Kubernetes `Secret`s.

| Resource Name | Resource Type | Typical Use | Expected Keys|
|---------------|---------------|-------------|--------------|
| `ldap-creds` | `Secret` | LDAP bind credentials | none |
| `git-repo-creds` | `Secret` | Credentials for the Git repo | `url` and `ssh_private` keys|
| `mtls-ca-validators` | `Secret` | Permissions for LDAP TLS | `ca.crt` |
| `rover-group-sync-config` | `ConfigMap` | Template LDAP config for `oc adm groups sync` | ldap-sync-config.yaml |

## Environment Variables

| env Name | Purpose | Required | Default Value | Source |
|----------|---------|----------|---------------|--------|
| `SYNC_CONFIG_SOURCE` | Path to LDAP config template | No | `config/ldap-sync-config.yaml` | `rover-group-sync` ConfigMap |
| `LDAP_CA_PATH` | Path to LDAP CA certificate | No | `secrets/ca.crt` | `ldap-creds` Secret |
| `GIT_PRIVATE_SSH_PATH` | Path to Git repo's private SSH key | No | `secrets/git-repo/ssh_private` | `git-repo-creds` Secret |
| `LDAP_DN` | LDAP credential injection value | Yes | N/A | `ldap-creds` Secret |
| `LDAP_PASSWORD` | LDAP credential injection value | Yes | N/A | `ldap-creds` Secret |
| `GIT_REPO_URL` | Git repository URL | Yes | N/A | `git-repo-creds` Secret |
| `GIT_BRANCH` | Git repository branch | No | "main" | CronJob env |
| `ENVIRONMENT` | The type of environment hosting the component | No | "staging" | Cronjob env |

## Local checks

Run a one-off job on the cluster (same pod template as the CronJob):

```bash
oc create job "rover-group-sync-manual-$(date +%s)" \
  --from=cronjob/rover-group-sync \
  -n rover-group-sync
```
