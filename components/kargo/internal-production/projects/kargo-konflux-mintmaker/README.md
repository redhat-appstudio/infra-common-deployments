# Konflux MintMaker

Project and namespace: `kargo-konflux-mintmaker`. Warehouse: `mintmaker`.
This project promotes MintMaker in
[`infra-deployments/components/mintmaker`](https://github.com/redhat-appstudio/infra-deployments/tree/main/components/mintmaker)
through Rings 0–4 using the [shared promotion workflow](../../shared/promotion-tasks/README.md).

## Release inputs

One Warehouse creates Freight containing five independently discovered inputs:

| Input | Selection | Promotion use |
|---|---|---|
| `redhat-appstudio/infra-deployments` Git | Newest `main` commit changing `components/mintmaker/base` | Immutable shared base snapshot |
| `quay.io/konflux-ci/mintmaker` | `NewestBuild`, full 40-character lowercase Git SHA tags | Controller tag and both controller manifest source refs |
| `quay.io/konflux-ci/mintmaker-renovate-image` | `NewestBuild`, full Git SHA tags | Renovate image tag in both pod annotations |
| `quay.io/konflux-ci/mintmaker-schedule-calculator` | `NewestBuild`, full Git SHA tags | Schedule-calculator CronJob image tag |
| `quay.io/openshift/origin-cli` | `SemVer`, stable `4.21` / `4.21.x` tags only | CLI image tag in MintMaker CronJobs |

Discovery runs every two hours. The public `quay.io/konflux-ci` repositories are
release destinations; `quay.io/redhat-user-workloads/konflux-mintmaker-tenant`
repositories are producer build outputs and are deliberately not subscribed.
The MintMaker SHA-tag filter excludes `latest`, short SHA aliases, digest aliases and
attestation/signature/SBOM artifacts. Do not enable `cacheByTag` on an assumption
that tags cannot be moved.

The three MintMaker images come from **three different source repositories**. Their SHA tags
must not be forced to match. This Freight is a combination of releases, not an
atomic cross-repository release; Ring 0 CI and subsequent verification gate the
combination. Warehouse discovery can find versions newer than the existing deployment pins
immediately; only Ring 0 starts promotions automatically.

Preparation writes all four images using **`name`, `newName`, and `newTag`**
with their independently selected release tags from Freight, using
[`kustomize-set-image`](https://docs.kargo.io/user-guide/reference-docs/promotion-steps/kustomize-set-image).
It replaces any existing digest pin on these four entries; unrelated image overrides remain unchanged.
For example, the controller entry keeps this structure:

```yaml
- name: quay.io/konflux-ci/mintmaker
  newName: quay.io/konflux-ci/mintmaker
  newTag: <controller SHA tag>
```

The controller's SHA tag, not the Git-base commit or another image's SHA, sets
both remote resources:

```text
https://github.com/konflux-ci/mintmaker/config/default?ref=<controller SHA>
https://github.com/konflux-ci/mintmaker/config/renovate?ref=<controller SHA>
```

See the producer's
[release workflow](https://github.com/konflux-ci/mintmaker/blob/81900c4d36ba18c32ff2e7a4e5de3644b1ca8504/docs/automated-release-workflow.md)
for the source/image relationship. Its older staging/production directory names
predate the ring layout. A deliberately separate Renovate manifest rollback is
replaced by the controller-aligned ref on the next promotion.

## Bounded preparation

The working checkout starts at deployment `main` for the PR base. A separate
checkout uses `commitFrom(repoURL).ID` for the selected shared base. For the target
ring only, preparation:

1. Validates origin, repository, ring, the three MintMaker SHA tags, the CLI
   release tag and layout.
2. Requires exactly one entry for each MintMaker image, both remote resource URLs, and the
   two Deployment annotation paths in `kustomizeconfig.yaml`. An origin-cli
   override may be absent or occur once; redirected or duplicate entries fail.
3. Replaces only `base/base-snapshot/` from the selected Git commit's
   `components/mintmaker/base/`.
4. Updates the four named images and the two controller manifest refs. Adds
   the origin-cli override when the ring previously inherited its image from
   the base snapshot. Ring 3 also updates the CLI transformer in
   `stone-prod-p02`, where two tenant CronJobs are added above the base.
5. For Ring 3, clears temporary render output, builds the updated `stone-prod-p02`
   overlay and requires both tenant CronJobs to contain exactly one `origin-cli`
   container using the selected tag. A failed build, missing/malformed job or
   mismatched image blocks preparation. Rendered output stays outside the PR checkout.
6. Emits `prepared: 'yes'` only after every required step succeeds.

The Renovate image is passed to the controller through the
`mintmaker.appstudio.redhat.com/renovate-image` pod annotation and the
`RENOVATE_IMAGE` Downward API environment variable. The newer
`mintmaker.konflux-ci.dev/renovate-image` annotation is also transformed. Keeping
the custom image transformer is essential: updating a normal container field
would not configure Renovate TaskRuns.

Ring-specific files remain intact: resource limits, profiling/blackbox settings,
Kite configuration, quotas, trusted CA mounts, secret references, tenant
CronJobs and schedules. Ring 0's origin-cli override now follows the selected
CLI release tag, and Rings 1–4 receive the same explicit override. Renovate's
previous `latest` alias becomes the selected release tag.

The origin-cli subscription shares the same Freight and ring gates as the
three MintMaker releases. Its SemVer constraint stays below 4.22, and its tag
filter excludes prereleases, `latest`, SHA tags and artifact tags. It does not
use `cacheByTag`, because the `4.21` tag can be republished. A moved tag can
produce new Freight without changing the generated `newTag`; tag-only
configuration does not pin the discovered digest or guarantee a new rollout.
Changing the supported CLI minor requires updating both the Warehouse filter
and the promotion validation together.

The shared base snapshot carries CLI job definitions and Redis configuration.
Ring 1's blackbox image stays ring-local. Controller-generated Tekton steps also
use OSV database, UBI, leaktk and optional Renovate log analyzer images. Those
runtime image references are controlled by upstream code/configuration, outside
these Kustomize image entries. This project does not claim to pin every image
used by generated PipelineRuns or add subscriptions that cannot affect them.

## Ring policy and verification

| Stage | Source | Soak on predecessor | PR merge | Gate |
|---|---|---|---|---|
| `ring-0-mintmaker` | Warehouse | — | Automatic | Required ring-deployments conformance Prow check |
| `ring-1-mintmaker` | Verified Ring 0 | — | Automatic | Staging Argo readiness + shared staging Kanary |
| `ring-2-mintmaker` | Verified Ring 1 | 48 hours | Manual | Production Argo readiness + shared production Kanary |
| `ring-3-mintmaker` | Verified Ring 2 | 48 hours | Manual | Production Argo readiness + shared production Kanary |
| `ring-4-mintmaker` | Verified Ring 3 | 72 hours | Manual | Production Argo readiness + shared production Kanary |

Only Ring 0 allows automatic promotion initiation. Rings 0 and 1 merge their
promotion PRs automatically after the required checks pass. Ring 1 still
requires manual promotion initiation; Rings 2–4 require both manual initiation
and a human PR merge. Existing verification and soak requirements still apply. Ring 0 requires
`^ci/prow/konflux-ring-deployments-conformance-tests$`; nonzero rings follow the
existing component policy of skipping Prow while retaining the shared GitHub
CI checks. The historical MintMaker overlay-update Tekton pipeline refers to
removed directories and is not used as a gate.

Ring 0 targets dynamic development member clusters and follows the existing
CI-only Kargo development-stage pattern. Its Applications lack the production
readiness label, so it has no fabricated named-cluster readiness check.
Rings 1–4 use `mintmaker-<cluster>` Applications with
`app.kubernetes.io/part-of=mintmaker`:

| Ring | Argo readiness targets | Kanary targets |
|---|---|---|
| 1 | `stone-stage-p01`, `stone-stg-rh01` | `stone-stage-p01`, `stone-stg-rh01` |
| 2 | `kflux-fedora-01`, `kflux-ocp-p01`, `kflux-osp-p01`, `kflux-prd-rh03`, `kflux-rhel-p01`, `stone-prod-p01` | `kflux-fedora-01`, `kflux-ocp-p01`, `kflux-osp-p01`, `kflux-prd-rh03`, `kflux-rhel-p01`, `stone-prod-p01` |
| 3 | `stone-prd-rh01`, `stone-prod-p02` | `stone-prd-rh01`, `stone-prod-p02` |
| 4 | `kflux-prd-rh02` | `kflux-prd-rh02` |

`lightwell-dev` and `kflux-lw-p01` are excluded from verification by explicit
project policy. Do not reintroduce them when refreshing deployment inventories.
This does not change their deployment configuration. Unmapped clusters with empty overlays
are not verification targets. Ring 1 uses the two requested staging clusters.
Ring 2 verifies all six production targets listed above in both checks, with
Kanary expected-cluster-count set to 6. Ring 3 checks both `stone-prd-rh01` and
`stone-prod-p02` in Argo readiness and Kanary, including the cluster whose tenant
CronJobs are updated during CLI promotion. The shared Argo task checks health
and the merged revision, with its existing history/ancestry fallback.
Kanary expects every cluster in its own list.

The Ring 2 inventory was rechecked at infra-deployments commit
[`1ce741f8f4a2`](https://github.com/redhat-appstudio/infra-deployments/commit/1ce741f8f4a24f944bf5bc384631cc3e9099ff73).
Rendering `argo-cd-apps/overlays/rd-production` combines the
[MintMaker ApplicationSet](https://github.com/redhat-appstudio/infra-deployments/blob/1ce741f8f4a24f944bf5bc384631cc3e9099ff73/argo-cd-apps/overlays/rd-production/mintmaker/mintmaker-appset.yaml)
with the [production cluster assignments](https://github.com/redhat-appstudio/infra-deployments/blob/1ce741f8f4a24f944bf5bc384631cc3e9099ff73/argo-cd-apps/k-components/deploy-to-production-tenant-clusters/tenant-clusters-list-patch.yaml).
All seven assigned Ring 2 clusters have nonempty
[MintMaker overlays](https://github.com/redhat-appstudio/infra-deployments/tree/1ce741f8f4a24f944bf5bc384631cc3e9099ff73/components/mintmaker/rings/ring-2).
This includes `kflux-rhel-p01`, `kflux-osp-p01` and `kflux-prd-rh03`, which are
covered by both checks. The only configured Ring 2 deployment excluded from
verification is `kflux-lw-p01`, by the explicit policy above; it is not absent
from the deployment inventory. This is a configuration inventory check, not a
live cluster-health measurement.

Kanary is a sampled fleet-health signal, **not a MintMaker dependency-update
functional test**. Shared default sampling is retained. MintMaker jobs generally
run every four hours; Ring 3's main dependency-update job runs only at 00:00 and
04:00 UTC. Readiness and a successful Kanary sample do not demonstrate a
completed MintMaker work cycle. Before the first production merge, operators
should inspect actual dependency-update, Renovate and scheduler outcomes from
the staging release. No new live metrics or credentials are assumed here.

## Platform integration and validation

The project includes shared tasks and verification templates, uses centrally
managed Git/staging-reader/RHOBS credentials, and provisions its production Argo
reader. Shard access and promotion-cleaner configuration include the namespace.
Existing `konflux-devprod`/`konflux-infra` administration is retained. The
`konflux-mintmaker-team` OIDC group maps to `kargo-konflux-mintmaker-promoter`, bound
to Kargo's built-in project `kargo-promoter` Role. The same RoleBinding covers
direct Kubernetes group access, scoped to `kargo-konflux-mintmaker`. The team can
view project state and initiate the existing Stage promotion workflows; it
cannot read Secrets or modify RBAC, Stage definitions, PromotionTasks,
AnalysisTemplates or promotion policies. The team has neither `kargo-admin`
nor `kargo-promoter-extras`; the latter permits Stage patches and would reopen
an indirect credential-access path. Manual Freight approval and abort actions
requiring additional privileges remain with platform operators.

Platform approvers from `components/kargo/OWNERS` own this project's RBAC,
ProjectConfig, resource entrypoints and credential-consuming workflow YAML.
MintMaker maintainers review component changes and can approve component
documentation. They cannot approve changes to their own access or executable
promotion definitions without a platform approver.

Shared verification credentials remain available to the platform-controlled
controllers and workflows. They are not moved or replicated differently by
this project. Restricting only direct Secret reads would be insufficient if
the team could edit a Stage or PromotionTask that calls `secret()` or
`sharedSecret()`; runtime permissions and file ownership both enforce that
boundary. Full namespace administration must not be granted to this team while
platform credentials are available to project workflows.

Render the project, shard RBAC, cleaner and all four repository root overlays.
Rendering does not prove live credential access, image compatibility or
successful cluster rollout.

Rollback the onboarding by reverting its repository change. Reverting Kargo
configuration does not undo already merged infra-deployments promotion PRs;
revert those separately when restoring a deployed version.
