# OpenShift Pipelines promotions

The `pipeline-service` Warehouse and Ring 0–4 stages belong to
`kargo-konflux-core`. They promote the reviewed
`components/pipeline-service/base` in infra-deployments, following that
component's update procedure.

## Release inputs

Update the OLM catalog image digest, Subscription channel, and any associated
TektonConfig or base manifests together in an infra-deployments base PR.
The Warehouse watches that base on `main` every two hours. It does not discover
arbitrary catalog tags: the catalog repository includes multiple release
streams, and a catalog image alone does not establish package/channel
compatibility.

Each promotion clones current target `main` and the immutable Freight commit
separately. The preparation task replaces only
`rings/<ring>/base/base-snapshot` from the selected commit's base, including
deletions. Every ring uses that same Freight source, never a moving previous
ring directory. Ring and cluster overlays remain outside the snapshot.

The generated PR summarizes the selected source commit, catalog image,
Subscription channel, and `TektonConfig.spec.result.disabled` before/after.
This is a complete base promotion, including Results, Chains, logging, RBAC
and configuration changes; it is not limited to the operator catalog image.

## No deploy.yaml generation

Current pipeline-service uses native Kustomize sources and ring snapshots.
There are no `deploy.yaml` files or `resources/` generation inputs in its
component tree. ArgoCD renders the selected ring/cluster overlay directly.
The older `hack/generate-deploy-config.sh` flow remains in bootstrap templates
but is not used by this promotion.

Merge the [companion infra-deployments CI repair](https://github.com/redhat-appstudio/infra-deployments/pull/14921)
before enabling these stages.
The old `verify-pipelines-configs.yaml` workflow references removed
`staging/`, `production/`, and `production/sync-rings.sh` paths. The repaired
workflow must render the source and ring/cluster entry points independently;
it must not synchronize snapshots across rings.

## Promotion gates

| Ring | Source soak | Merge | Verification |
| --- | --- | --- | --- |
| 0 | None | Automatic after CI | GitHub checks and `ci/prow/konflux-ring-deployments-conformance-tests` |
| 1 | None | Automatic after CI | GitHub checks, staging ArgoCD readiness and Kanary |
| 2 | None | Manual PR merge | GitHub checks, production ArgoCD readiness and Kanary |
| 3 | 48 hours | Manual PR merge | GitHub checks, production ArgoCD readiness and Kanary |
| 4 | 72 hours | Manual PR merge | GitHub checks, production ArgoCD readiness and Kanary |

Automatic stage promotion is disabled for Rings 0–4 until the companion CI
repair and the separately reviewed initial production migration have merged.
Enable the five policies in a follow-up after verifying those prerequisites.
Once enabled, Rings 0–1 automatically merge after their checks; Rings 2–4
still require manual PR merges. Prow is skipped for Rings 1–4, matching the
conformance job's path filters; GitHub checks remain required.

ArgoCD readiness uses the `pipeline-service` application prefix and label:
- Ring 1: stone-stage-p01, stone-stg-rh01.
- Ring 2: kflux-fedora-01, kflux-lw-p01, kflux-ocp-p01, kflux-osp-p01,
  kflux-prd-rh03, kflux-rhel-p01, stone-prod-p01.
- Ring 3: stone-prd-rh01, stone-prod-p02.
- Ring 4: kflux-prd-rh02.

Ring 1 also deploys to lightwell-dev and kflux-stg-p02 through its ApplicationSet.
These are not readiness/Kanary targets here, matching the existing infrastructure
gate coverage. Lightwell-dev remains excluded from production Kargo verification.
Kanary uses the same representative clusters and counts as the policies component.

## Initial production migration

At infra-deployments commit `f160e99f069b65a36d6e643be1b403cc62d640b6`,
source base and Rings 0–1 share the same snapshot. Production Rings 2–4 still
contain standalone Tekton Results resources and set `result.disabled: true`.
Promoting the current base removes those resources and enables operator-managed
Results. Review resource ownership, pruning and database configuration together
before merging production promotion PRs.

The Ring 2 `kflux-lw-p01` overlay still strategically patches standalone
Results Deployments. It does not render with the current source base because
those Deployment targets disappear. Before activating this onboarding, merge a
separate component-owner reviewed Ring 2 migration PR that updates the snapshot
and its matching cluster patches together. The existing Ring 1 `kflux-stg-p02`
overlay shows the TektonConfig DB port and CA patch pattern; preserve Lightwell's
production database secret settings. Do not remove its working standalone patches
ahead of the snapshot transition. The companion CI validation must reject an
incompatible overlay.

The same migration must update Fedora's `tekton-results-database` and
`tekton-results-s3` ExternalSecret patch selectors from `tekton-results` to
`openshift-pipelines`. Otherwise they silently stop applying and leave the
source defaults, despite a successful render. Reconcile Lightwell's PaC
trusted-CA patch as well: it replaces whole TektonConfig objects that now carry
source OTEL and resource settings. Component owners must verify the resulting
cluster-specific database, object-storage, CA and operator configuration.

Do not add that migration by editing a Kargo-generated PR: the shared workflow
validates the originally published head SHA, and a new promotion force-pushes the
stable branch, potentially overwriting owner edits. After the separate migration
is merged into deployment `main`, start a fresh promotion. The selected source
base must include every desired snapshot change because preparation replaces the
snapshot completely. Keep the onboarding PR in draft until the CI prerequisite
and initial production migration plan have been resolved.

This onboarding does not execute the Results migration or change those deployment
manifests. ArgoCD readiness checks Applications; successful readiness is not proof
that every operator-managed component or data migration is healthy.

## Operations

Initial discovery may immediately start Ring 0, including a no-op when the
snapshot already matches. New base changes flow through the configured gates.
The component's update procedure permits owner patches on generated PRs, but
the current shared Kargo workflow does not support adopting those changed heads.
Land coordinated overlay/snapshot migrations separately before promotion, as
described above; do not bypass the shared merge identity checks.

Disable these five auto-promotion policies to stop new automatic promotions
and review already-running Promotions separately. Reverting onboarding does
not undo merged infra-deployments snapshot PRs. Review OLM and Results migration
rollback compatibility before reverting deployment content.
