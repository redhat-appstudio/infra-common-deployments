# Crossplane Config promotions

Crossplane Config is manifest-only. Its base currently contains a ServiceAccount,
ClusterRole and ClusterRoleBindings, with no image or Helm subscriptions.
The `crossplane-config` Warehouse watches only
`components/crossplane-config/base` in the deployment repository. Changes to ring
snapshots do not trigger another candidate.

## Rings and gates

| Ring | Freight source | PR merge | Checks |
|---|---|---|---|
| 0 | Warehouse | Automatic | GitHub checks and `ci/prow/appstudio-operator-overlay-e2e-tests` |
| 1 | Ring 0 | Automatic | GitHub checks; Argo CD readiness for `crossplane-config-kflux-stg-es01` |
| 2 | Ring 1, after 48h soak | Manual | GitHub checks; Argo CD readiness for `crossplane-config-kflux-prd-es01` |

The development ApplicationSet deploys Ring 0 to clusters selected by
`appstudio.redhat.com/eaas-cluster=true`. Its targets are dynamic, so Ring 0 uses
the shared Git/CI gate rather than a hardcoded Argo readiness cluster list.
Staging and production target the EaaS clusters above, as configured in their
ApplicationSets. Prow is explicitly disabled for Rings 1 and 2.

Production auto-promotion opens the proposal; a person must merge its PR before
Argo CD auto-sync deploys it. The 48-hour upstream soak matches existing Vanguard
production policy. Kargo measures time while Freight is current upstream;
frequent newer promotions can delay eligibility.

Tenant Kanary checks are not applied to these EaaS targets. Argo CD readiness
checks synchronization and health, not whether the granted RBAC permissions are
functionally correct. The required Ring 0 Prow suite is not a dedicated Crossplane
RBAC test. It does not deploy Crossplane Config: a passing result proves only
the Operator regression gate passed. Ring 0 has no independent Crossplane
deployment check; Crossplane-specific Argo readiness starts at Ring 1.

## What preparation does

The Stage clones current `main` into `./src` and the selected Freight's Git commit
into `./freight`. Preparation replaces the target ring's `base-snapshot` with the
base from `./freight`, including removal of files deleted in the source.

All three rings use that same immutable Git source, rather than copying a
previous ring that may already contain newer changes. Outer Kustomizations and
cluster-specific overlays remain unchanged. No image versions are discovered or
modified. Changes outside the watched base require a separate reviewed rollout.

The shared tasks handle PR publication, exact-head CI, merge confirmation and
readiness. Their existing limits still apply, including the exact Argo revision
requirement when `main` advances. See the
[shared workflow guide](../../../../kargo-shared-promotion-tasks/README.md).
