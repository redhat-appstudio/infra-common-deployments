# Repository validator promotions

Repository validator is a manifest-based admission policy, not a controller
image. One Warehouse, `repository-validator`, records two Git revisions:

- Public policy manifests from `infra-deployments/components/repository-validator/base`.
- Private configuration from `internal-infra-deployments/components/repository-validator`.

Each Freight carries both revisions through the same ring sequence. The public
policy is copied from its immutable Freight checkout; configuration stays in the
private repository and is referenced by commit SHA.

## Rings

| Ring | Configuration | Merge policy | Argo CD readiness |
|---|---|---|---|
| 0 | Existing local wildcard ConfigMap | Automatic after GitHub checks and Prow | No fixed development target list |
| 1 | Private `staging` config | Automatic after GitHub checks | `stone-stage-p01` |
| 2 | Private `production` config | Manual | `kflux-lw-p01`, `kflux-ocp-p01`, `kflux-osp-p01`, `kflux-rhel-p01`, `stone-prod-p01` |
| 3 | Private `production` config | Manual | `stone-prod-p02` |

There are **no soak delays** (`requiredSoakTime`) in any Stage. Each Stage still
requires verified Freight from its predecessor, and keeps its CI, merge,
readiness and Kanary gates. Auto-promotion creates production proposals; it does
not approve their merge.

The staging and production Applications enable Argo CD auto-sync with pruning
and self-healing. After merge, Argo CD reconciles the change; the readiness task
observes that sync and does not initiate it.

Ring 0 requires `ci/prow/appstudio-operator-overlay-e2e-tests`; its trigger includes
this component's Ring 0 paths. Prow is explicitly skipped in later rings. Ring 0
keeps the development allow-all configuration and does not test the private
allowlists. Staging exercises the staging config; reviewers must review the
production config in the private repository before merging its promotion.

Staging Kanary checks `stone-stage-p01`; production Kanary samples
`stone-prod-p01` in Ring 2 and `stone-prod-p02` in Ring 3. These are configured
Kanary targets, not proof of live metric availability or policy-specific tests.
The shared staging analysis retains its existing monitoring duration; removing
soak delays does not skip verification.

`lightwell-dev` has an empty overlay and is excluded from readiness.
`stone-stg-rh01` is not a deployment target. Ring 4 is intentionally empty, so no
Ring 4 Stage is created. Readiness uses the Application prefix
`repository-validator`, matching the public Git directory name.

## What changes

Preparation replaces only the target ring's `base/base-snapshot`, removing stale
files, and updates its environment-appropriate private configuration ref. It does
not copy a moving previous-ring directory, change cluster overlays, or copy
private allowlist contents into the public repository or PR description.

The shared publication, CI, merge and readiness tasks handle the rest. Existing
branch names and GitHub labels are retained. PR descriptions show the public
policy source and the previous/proposed configuration revision.

## Migration and operation

This replaces `repository-validator-manifest-wh` and
`repository-validator-git-wh` with one combined Warehouse and adds Rings 2–3.
Historical Freight from the old Warehouses is not automatically converted or
qualified for the new Warehouse. New Freight starts at Ring 0.

Finish or abort in-flight legacy promotions before applying the migration:
existing Promotion objects retain their old steps and use the same PR branches.
Review any existing open promotion PRs before proceeding. Kargo needs Git access
to both source repositories; Argo CD already needs access to the private refs.

A combined Warehouse selects a candidate pair, not an atomic cross-repository
release. Production remains manually reviewed. Shared readiness's exact-revision
check can time out if `main` advances before Argo CD observes the captured merge.

See the [shared workflow guide](../../../../kargo-shared-promotion-tasks/README.md).
