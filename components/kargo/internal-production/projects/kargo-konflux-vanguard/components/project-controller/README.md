# Project Controller promotions

Project Controller belongs to `kargo-konflux-vanguard` and inherits the project's
[OWNERS](../../OWNERS). Every promotion PR receives `team/konflux-vanguard`,
`component/project-controller`, its ring label, and `automated-promotion`.

## What creates Freight

The Warehouse checks every two hours for:

- 40-character SHA image tags in `quay.io/konflux-ci/project-controller`.
- Commits on `infra-deployments/main` that change `components/project-controller/base`.

Each Freight records both the image and the deployment repository commit. The
image tag selects the matching upstream `project-controller/config/default`
manifest ref. The deployment commit supplies the shared RBAC `base-snapshot`.
These are separate source revisions; the repository subscriptions do not create
an atomic cross-repository release.

## Ring policy

| Ring | Merge policy | Deployment readiness | Soak in previous Stage |
|---|---|---|---|
| 0 | Automatic after GitHub checks and the Operator overlay Prow suite | Development deployment uses the updated ring base; no Argo readiness gate | None |
| 1 | Automatic after GitHub checks | All three staging Applications, then the existing Kanary verification | None |
| 2 | Manual after GitHub checks | Seven production Applications, then Kanary on two clusters | 48h |
| 3 | Manual after GitHub checks | Two production Applications, then Kanary on one cluster | 48h |
| 4 | Manual after GitHub checks | One production Application, then Kanary on that cluster | 72h |

Automatic promotion is enabled for all five Stages. For production this starts
a proposal; a reviewer still has to merge the PR. Prow is required in Ring 0 and
explicitly skipped in later rings, following the existing Vanguard workflow.
Soak measures eligibility in the previous Stage, not the image publication age.

Application targets were checked against infra-deployments commit
[`562b33c4b35b9e2af320778679e37082597acf47`](https://github.com/redhat-appstudio/infra-deployments/tree/562b33c4b35b9e2af320778679e37082597acf47/components/project-controller/rings):

- Ring 1: `stone-stage-p01`, `stone-stg-rh01`, `lightwell-dev`.
- Ring 2: `kflux-lw-p01`, `kflux-fedora-01`, `kflux-ocp-p01`, `kflux-osp-p01`,
  `kflux-prd-rh03`, `kflux-rhel-p01`, `stone-prod-p01`.
- Ring 3: `stone-prd-rh01`, `stone-prod-p02`.
- Ring 4: `kflux-prd-rh02`.

Applications use `project-controller-<cluster>` names and the
`app.kubernetes.io/part-of: project-controller` label. All three staging overlays
include the component base. Kanary covers only `stone-stg-rh01` and
`stone-stage-p01`, matching the existing staging monitoring configuration;
`lightwell-dev` is still required to pass Argo readiness. Production retains
the existing Vanguard Kanary targets: `stone-prod-p01` and `kflux-prd-rh03`
in Ring 2, `stone-prd-rh01` in Ring 3, and `kflux-prd-rh02` in Ring 4.

## What a promotion changes

Preparation validates the Freight origin, SHA values, ring, image alias and
resource layout before editing. It then:

1. Copies `components/project-controller/base` from the Freight's immutable Git
   checkout into the target ring's `base/base-snapshot`.
2. Updates the `konflux-project-controller` image alias to the selected SHA tag.
3. Updates the upstream manifest URL to that same image SHA, locating the URL by
   prefix rather than assuming an array position.

Other resources, ring-specific settings and cluster overlays stay in place.
Preparation exposes success only after all edits finish. The shared tasks then
publish the PR, check its exact commit, confirm its merge, and check the health
and sync status of every configured Application. The primary readiness path
also requires the accepted revision in each Application's current revision or
sync history. If that path times out, the shared ancestry fallback checks all
Applications' health and sync status but verifies ancestry for only the first
matched Application. This inherited fallback does not prove revision ancestry
for every target. An unchanged tree skips PR creation but still runs these
readiness checks in Rings 1-4.

SHA tags must remain immutable and identify available upstream Git commits.
The Warehouse watches shared base changes; it does not separately discover
cluster-overlay edits as Freight. Existing project credentials and staging /
production shards are reused.

To change the rollout policy, edit the relevant Stage's `mergeMode`,
`requestedFreight.sources.requiredSoakTime`, readiness targets or verification.
Keep the target list aligned with the deployment ApplicationSets. Project-wide
automatic starts are configured in `base/project-config.yaml`.

See the [shared promotion workflow](../../../../shared/promotion-tasks/README.md)
for CI, no-op, merge and readiness behavior.
