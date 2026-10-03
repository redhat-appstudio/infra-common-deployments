# cluster-secret-store-rh promotions

## What to change

Edit `components/cluster-secret-store-rh/base/` in
[infra-deployments](https://github.com/redhat-appstudio/infra-deployments/tree/main/components/cluster-secret-store-rh/base)
and merge the source PR. The Git-only Warehouse checks `main` every two hours,
watching only that path, and creates Freight containing the selected Git commit.
There are no image or chart subscriptions.

Each promotion copies that immutable commit's base into
`components/cluster-secret-store-rh/rings/ring-N/base/base-snapshot/`.
It replaces the snapshot so deleted source files are removed too. Preparation
checks the Warehouse, repository, component, allowed ring, commit SHA and target
snapshot reference before changing files.

The RHEL-specific SecretStore, ExternalSecret and trusted CA resources, and
Ring 3 Insights stores and condition patches, stay outside the snapshot and
are not replaced by promotion.
Changes outside the watched base path remain separately reviewed configuration
changes; they do not create Freight or propagate through this pipeline.

## Rings and review

This component is production-only. Rings 0 and 1 are empty and have no
Stages. Ring 2 receives Freight directly; there is no staging qualification
for this Warehouse. Review its first production proposal accordingly.

| Ring | Freight source | Argo CD readiness targets | Kanary sample |
|---|---|---|---|
| 2 | Warehouse | kflux-lw-p01, kflux-fedora-01, kflux-ocp-p01, kflux-osp-p01, kflux-prd-rh03, kflux-rhel-p01, stone-prod-p01 | stone-prod-p01, kflux-fedora-01, kflux-prd-rh03 |
| 3 | Verified ring 2 | stone-prd-rh01, stone-prod-p02 | stone-prd-rh01 |
| 4 | Verified ring 3 | kflux-prd-rh02 | kflux-prd-rh02 |

Kargo automatically starts eligible promotions and proposes PRs. **Every ring
requires manual PR merge.** GitHub checks run through the shared CI task; Prow
is explicitly skipped, following the existing manifest workflow for rings 1–4.
There is no additional `requiredSoakTime`; the shared Kanary timing still applies.

After merge, Argo CD auto-sync reconciles the snapshot. Readiness checks every
listed Application using the `cluster-secret-store-rh-<cluster>` name, the promoted
revision, sync status and health. Staging uses `argocd-app-reader-token-staging`;
production uses `argocd-app-reader-token`. Post-promotion Kanary verification
samples the listed existing infrastructure targets before Freight can proceed.
Kanary is a general cluster signal, not a direct Vault access check. Its live
metric availability has not been checked as part of this onboarding.

## Operating the pipeline

Find `cluster-secret-store-rh` in the `kargo-konflux-infrastructure` project. Review the
source commit and snapshot diff in each generated PR, then merge after checks
pass. If a promotion is unchanged, the shared no-op path still checks deployment
readiness. Investigate failed CI, Argo CD or Kanary checks before advancing the
same Freight to the next ring; avoid manually approving unverified Freight.

To pause proposals, set the relevant Stage's `autoPromotionEnabled` policy to
`false` and handle any already queued or running Promotions separately. To undo
a deployed change, revert the affected snapshot PR in `infra-deployments`.
Removing this onboarding stops future automation but does not roll back deployed
manifests or merge/close existing promotion PRs.

See the [shared workflow guide](../../../../shared/promotion-tasks/README.md).
