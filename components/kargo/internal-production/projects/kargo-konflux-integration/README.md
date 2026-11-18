# Konflux Integration Kargo project

`kargo-konflux-integration` promotes `image-rbac-proxy` through the existing
infra-deployments Rings 0–4. The project is managed by the production Kargo
control plane. Ring 0 is the integration gate on `infra-deployments/main`, not a
cluster cohort. Ring 1 uses the staging shard; Rings 2–4 use the production shard.

## Release inputs and Ring 0 images

One Warehouse creates Freight containing three subscriptions:

| Input | Selection | Use |
| --- | --- | --- |
| `redhat-appstudio/infra-deployments.git` | `main`, changes under `components/image-rbac-proxy/base` | Copy the selected commit's shared base into the target ring's `base/base-snapshot` |
| `quay.io/konflux-ci/image-rbac-proxy` | NewestBuild, full 40-character source-SHA tags | Set the proxy `newTag` and upstream deployment manifest `ref` to the same SHA |
| `quay.io/kubearchive/memcached` | SemVer, stable tags `>=1.6.39 <3.0.0` | Update the existing `memcached` image override **only in Ring 0** |

The Git subscription intentionally excludes `rings/`, so promotion commits do
not trigger new Freight. The upstream `konflux-ci/image-rbac-proxy` manifest
revision comes from the selected proxy image tag, rather than independently
following that repository's latest commit before an image has been published.

Ring 0 consumes `deploy/development/base?ref=<proxy-image-tag>`; Rings 1–4 consume
`deploy/base?ref=<proxy-image-tag>`. Both image subscriptions are independent:
the proxy uses source-SHA tags and Memcached uses version tags, with no shared
SHA requirement. Proxy image tags remain tags, not digest overrides.

Ring 0 currently overrides the upstream `memcached` image to
`quay.io/kubearchive/memcached`. Rings 1–4 deliberately retain the Memcached
image defined by the pinned upstream manifests. A Memcached-only Freight change
can therefore be a no-op in later rings; it does not introduce a Quay override
there. Dex also remains selected by the upstream manifest ref, and the OAuth
Job's task-runner image remains ring-local. Neither gets an additional image
subscription in this project.

Preparation validates the Freight and manifest layout, updates the shared base,
proxy tag and matching remote ref, and updates Memcached only for Ring 0. It then
renders the target ring base and requires the proxy Deployment to consume the
selected proxy image (and the selected Memcached image in Ring 0) before emitting
`prepared: yes`. A missing upstream revision, missing container, or ineffective
image override stops preparation before a PR is published. OAuth jobs, external
secrets, cluster patches, certificates and environment-specific resource paths
are preserved.

## Promotion policy and checks

| Ring | Start promotion | Promotion PR merge | Verification |
| --- | --- | --- | --- |
| 0 | Automatic | Automatic after CI | Required Prow ring-deployment conformance check and shared GitHub checks |
| 1 | Automatic after Ring 0 | Automatic after CI | Argo revision readiness, then nominal 24-hour single-arch Kanary analysis |
| 2 | Manual after Ring 1 verification | Manual after CI | Argo revision readiness, then nominal 24-hour single-arch Kanary analysis |
| 3 | Manual after Ring 2 verification | Manual after CI | Argo revision readiness, then nominal 24-hour single-arch Kanary analysis |
| 4 | Manual after Ring 3 verification | Manual after CI | Argo revision readiness, then nominal 24-hour single-arch Kanary analysis |

No additional soak-time configuration is used. Rings 1–4 use 36 measurements
with an initial 40-minute delay, 40-minute intervals and failure limit 7, matching
the existing component convention. The shared CI task handles Codecov/Fullsend
exclusions and Prow timeouts. This project does not alter those shared tasks.
The shared Kanary template checks `kanary_up`; this onboarding does not change
its existing error-signal semantics. Missing metrics cannot satisfy its success
condition. Configuration validation does not establish live Kanary health.

## Cluster coverage

Inventory checked at infra-deployments commit
[`fbaa5f55b447b11019793f235e8017d075db7aab`](https://github.com/redhat-appstudio/infra-deployments/commit/fbaa5f55b447b11019793f235e8017d075db7aab),
including rendered `rd-staging` and `rd-production` ApplicationSets and the
staging cluster-registration labels in infra-common-deployments commit
`4b9989878`. The staging selector excludes spoke clusters and includes the hub.

| Ring | Argo readiness targets | Kanary targets | Expected Kanary count |
| --- | --- | --- | --- |
| 0 | None; main-branch integration only | None | — |
| 1 | `stone-stage-p01`, `stone-stg-rh01`, `kflux-stg-p02`, `kflux-hub-stg-01` | `stone-stage-p01`, `stone-stg-rh01`, `kflux-stg-p02` | 3 |
| 2 | `kflux-fedora-01`, `kflux-ocp-p01`, `kflux-osp-p01`, `kflux-prd-rh03`, `kflux-rhel-p01`, `stone-prod-p01` | Same | 6 |
| 3 | `stone-prd-rh01`, `stone-prod-p02` | Same | 2 |
| 4 | `kflux-prd-rh02` | Same | 1 |

`kflux-hub-stg-01` receives the component and is covered by Argo readiness, but
is not assigned a Kanary probe overlay in the checked Kanary ApplicationSet.
The staging tenant targets supply the available Kanary checks. This is not a
claim of hub-specific synthetic coverage.

`lightwell-dev` and `kflux-lw-p01` remain excluded from verification, as explicitly
requested for Kargo projects. The inventory above still lists their deployment
overlays; exclusion does **not** mean they no longer deploy this component.
Changes to their shared ring base can still reach them through Argo CD.

## Access and ownership

The existing component group `konflux-image-rbac-proxy` is mapped to a Kargo
promoter ServiceAccount and role binding. It does not receive project-admin or
Secret-read permissions from this project. Platform operators retain the
existing infrastructure administration roles.

The project-level OWNERS file retains platform approvers for RBAC and promotion
policy. Maintainers from infra-deployments `components/image-rbac-proxy/OWNERS`
are delegated only under `components/image-rbac-proxy/` in this project.

Shared credential replication, promotion/merge tasks and verification templates
are reused. The project is registered with shard RBAC and the promotion cleaner;
no new Vault entries or credential values are added.
