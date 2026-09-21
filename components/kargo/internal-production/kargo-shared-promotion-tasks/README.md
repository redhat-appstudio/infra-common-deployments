# Shared Kargo promotion tasks

Kargo promotes a selected release by changing Git configuration, opening a pull
request, checking CI, merging, and checking the deployment. A release is called
**Freight**; a deployment step such as Ring 0 or Ring 1 is called a **Stage**.

The playground and Konflux Operator use the shared tasks described here. Other
components keep their existing workflows until they are migrated.

## How it works

```text
Stage
  1. Clone the deployment repository
  2. Prepare the component's image, chart or manifest changes
  3. Publish a pull request
  4. Wait for the configured CI checks
  5. Merge automatically, or wait for a human to merge
  6. Check the configured Argo CD Applications, when required
  7. Run the Stage's configured verification, when present
```

**The Stage owns policy:** which Freight to use, which ring to update, whether
Prow is required, how the PR is merged, and which clusters to check.

**The component task owns the change:** updating image tags, chart versions or
manifests. It edits the same checkout that the publication task commits.

**The shared tasks own the repeated work:** publication, CI, merge and deployment
readiness. Kargo tasks cannot call other tasks, so the Stage connects them.
These tasks currently target `redhat-appstudio/infra-deployments`, branch `main`.

## Current policies

| Component | Ring | Merge | Prow | Argo CD readiness |
|---|---|---|---|---|
| Playground | 0 | Automatic | Disabled | None; Git-only promotion |
| Playground | 1 | Automatic | Disabled | `stone-stg-rh01`, `stone-stage-p01` |
| Konflux Operator | 0 | Automatic | Required | None; Git-only promotion |
| Konflux Operator | 1 | Automatic | Disabled | `stone-stage-p01` |
| Konflux Operator | 2 | Automatic | Disabled | `kflux-lw-p01` |

Operator Ring 0 requires `^ci/prow/appstudio-operator-overlay-e2e-tests$`.
Operator Ring 1 also runs Kanary and conformance verification on
`stone-stage-p01`, with single-arch and multi-arch signals. Those verification
checks have a different scope from its two-cluster deployment readiness check.

Operator Ring 2 already used automatic merging. Its previous PR description said
manual approval; the new description matches the actual executable policy.
Changing to human merging requires an explicit `mergeMode: manual` choice.

## Start here when adding a component

Use the [playground Ring 1 Stage](../projects/kargo-production-playground/components/dummy-deployment/stages/ring-1-stage.yaml)
as a complete example. For mandatory Prow, see the
[Operator Ring 0 Stage](../projects/kargo-konflux-core/components/konflux-operator/stages/ring-0-stage.yaml).

1. Keep the component's Freight sources, shard and verification settings in its Stage.
2. Clone the repository, then run a component preparation task against that checkout.
3. Return `prepared: "yes"` only after all required edits succeed.
4. Call publication, CI and merge in that order, forwarding their explicit result outputs.
5. Set `mergeMode` and `skipProwChecks` explicitly. When Prow is enabled, supply its required suite.
6. Add one readiness call for the component and its cluster list when the ring needs deployment verification.
7. Render the affected project, validate its expressions, and exercise the workflow before wider adoption.

Image updates must use the selected Freight. Manifest-copy components must use an
immutable source revision; copying from the current `main` can deploy different
content from the release selected for promotion.

A component may pass its own variables, such as `prevRing`, to its preparation
task. The Operator does not use `prevRing`: it writes the selected image tag and
manifest ref directly into each target ring's invariant kustomization.

### Choosing Prow

Use string values: `skipProwChecks: "false"` requires Prow; `"true"` disables it.
When forwarding the Stage variable into a task, use:

```yaml
- name: skipProwChecks
  value: ${{ quote(vars.skipProwChecks) }}
```

`quote()` prevents Kargo from converting the string into a boolean.
`requiredCheckRuns` defaults to `.*`. An enabled Prow gate requires a nonempty
`requiredProwChecks` regex. Each selector must match at least one check. A regex
with alternatives does not prove that every alternative exists; prefer a reliable
aggregate suite when every constituent test is required.

### Choosing readiness targets

One call checks the whole configured group:

```yaml
- task:
    name: verify-argocd-deployment
  as: verify-deployment
  vars:
    - name: mergeConfirmed
      value: ${{ outputs['merge::result']?.mergeConfirmed ?? '' }}
    - name: commitSHA
      value: ${{ outputs['merge::result']?.mergeCommitSHA ?? '' }}
    - name: component
      value: ${{ vars.component }}
    - name: clusters
      value: stone-stg-rh01|stone-stage-p01
```

Cluster names are literal, unique, pipe-separated values: no regex, spaces or
empty entries. The supported group size is 1–15 clusters. Expected Application
names are `<component>-<cluster>`. The naming contract is:

```text
Freight origin (Warehouse name) = component = Argo CD Application prefix
```

Declare `component` once in the Stage as `${{ ctx.targetFreight.origin.name }}`
and forward `${{ vars.component }}` to publication and readiness. This is the
Warehouse name, not the generated Freight ID or alias. A mismatched Application
name cannot pass readiness. Repository directory names may differ; keep those
paths in the component preparation task.

The default reader secret is `argocd-app-reader-token-staging`. Production callers
must pass their appropriate `tokenSecret`; Operator Ring 2 uses
`argocd-app-reader-token`. The default Application namespace is
`argocd-infra-deployments`.

## Task contracts

Every task publishes its completion fields in a step named `result`.

| Task | Required inputs | Result fields |
|---|---|---|
| [publish-promotion-pr](publish-promotion-pr.yaml) | `srcPath`, `component`, `targetRing`, `prepared`, `baseCommitSHA`, `mergeMode`, `skipProwChecks` | `published`, `promotionAsNoOp`, `baseCommitSHA`, `headCommitSHA`, `prNumber`, `prURL` |
| [verify-promotion-ci](verify-promotion-ci.yaml) | `published`, `commitSHA`, `promotionAsNoOp`, `skipProwChecks`; `requiredProwChecks` when enabled | `passed`, `checkedSHA`, `promotionAsNoOp` |
| [merge-promotion-pr](merge-promotion-pr.yaml) | `passed`, `checkedSHA`, `headCommitSHA`, `baseCommitSHA`, `prNumber`, `promotionAsNoOp`, `mergeMode` | `mergeConfirmed`, `mergeCommitSHA`, `promotionAsNoOp` |
| [verify-argocd-deployment](verify-argocd-deployment.yaml) | `mergeConfirmed`, `commitSHA`, `component`, `clusters` | `deploymentVerified`, `commitSHA`, `appDetails` |

Keep these rules when extending or generating configuration:

- Success flags use the string `"yes"`. No-op uses `"yes"` or `"no"`; merge mode uses `auto` or `manual`.
- Pass the clone's commit as publication's `baseCommitSHA`; pass the published head to CI and the checked SHA to merge.
- Inside a task, use `status('local-step')` and `task.outputs['local-step']`.
- Across tasks, use `outputs['task-alias::result']?.field ?? ''`. Cross-task `status()` lookups do not work.
- Missing success outputs must fail the next task's validation. A failed task is never a no-op.
- An intermediate output map is not proof of completion. Read the final `result` fields.
- Optional empty defaults use `${{ '' }}` or `${{ [] }}`. A literal empty default is treated as missing during Kargo task expansion.

## What the checks guarantee

**Publication:** each Promotion gets its own branch, with force-push disabled.
Native Kargo steps push and open the PR. If PR creation is skipped because the
change may already exist, two HTTP reads verify exact Git-tree equality before
accepting it as a no-op. The branch must remain owned exclusively by its Promotion.

**CI and merge:** required checks must pass for the published head SHA. Automatic
mode uses native `git-merge-pr`; manual mode uses native `git-wait-for-pr`. HTTP
checks verify the PR's head, base branch and resulting merge SHA. Missing or
pending CI results wait; failed results block completion. Responses exceeding
100 checks/statuses are rejected rather than approving a partial result set.

**Readiness:** every configured Application must appear in the same complete
response and be Healthy, Synced, at the expected revision, and not deleting or
running an operation. Reconciliation must be newer than the fixed readiness-start
boundary. Operation history, when present, must be successful and older than that
reconciliation. An Application without operation history can pass.

**No-op:** no Git changes means no new PR or CI run. Rings with readiness still
verify the captured target revision. Existing `noOpRing0/1/2` Freight annotations
are retained, but later tasks use fresh publication outputs instead of cached
Freight metadata.

Operator migration intentionally adopts these stricter checks and unique branches.
It preserves sources, ring targets and policies, but is not behavior-identical to
the legacy flow: no-ops now undergo readiness and every configured target is required.

## Promotion PR descriptions

Preparation tasks may return `prSummary`, `prChanges`, and `prCompareURL` alongside
`prepared`. Each change row has `kind`, `previous`, `proposed`, and `path`.
The Stage forwards them to the publisher; they are optional.

The publisher shows configuration changes, merge/Prow policy and promotion IDs.
Previous values come from Git, not the running deployment. Comparison links are
only produced for recognized manifest repositories with old and new 40-character
hexadecimal refs; they are not proof of image provenance. No extra GitHub calls
are made just to build the description. A reused PR may keep its original body.

## Limits and troubleshooting

| Symptom or concern | Meaning / action |
|---|---|
| Readiness response exceeds 2 MiB | The HTTP request lists the namespace; cluster filtering happens locally. Kargo rejects oversized responses. Labels are not required, and this size limit remains unresolved. |
| Readiness times out while Applications look healthy | Check exact revision, reconciliation timestamp, active operation and every expected name. A later `main` commit can prevent exact-revision matching even if component content is unchanged. |
| Timeout message lacks per-Application detail | `appDetails` is produced only on successful HTTP completion. Inspect Applications directly for a failed or pending check. |
| Missing Application | The entire group waits; an incomplete or paginated response cannot approve readiness. |
| GitHub rate limiting | HTTP CI/identity calls still use a shared PAT. Native Git steps use configured Kargo credentials. Task reuse alone does not reduce request volume. |
| Merge fails on a transient API error | Native Kargo v1.11.3 merge errors can be terminal. A retry budget does not make every provider failure retryable. |
| Branch changes during merge | Native merge lacks an atomic expected-head precondition. The final identity check can detect a mismatch but cannot undo an already completed merge. |
| Restarting a Promotion | Exercise restart/retry behavior after publication before broad adoption; do not manually push to its branch. |

CI polling defaults to two minutes, with up to 2h30m per phase. Automatic merge and
PR identity checks use two-minute polling and two-hour budgets; the manual merge
waiter uses five-minute polling and a seven-day budget. Readiness has a 45-minute
retry budget. These are not strict wall-clock deadlines.

HTTP rate-limit responses remain pending; polling does not follow exact
`Retry-After` times or implement a global limiter. Seventy concurrent CI waiters at
two-minute intervals can issue about 2,100 requests/hour for one active phase.
Measure credential usage, namespace response size and branch retention before
scaling to more components. Readiness uses the local Kubernetes API and consumes
no GitHub quota; it does not request an Argo CD sync.

## Validation and rollback

Render the playground and `kargo-konflux-core` projects and all four root overlays
with `kustomize build`, then lint changed YAML. Rendering alone does not prove
runtime expressions or GitHub/Argo CD integration. Temporary expression checks are
used during development; no test files are included in this PR.

Live end-to-end validation remains required, including the Operator production
ring. Existing in-flight Promotions retain their generated steps; inspect a new
Promotion when validating changed Stage configuration.

To roll back, restore the migrated Stage and preparation files first. Remove the
new shared tasks only after no callers reference them. Legacy CI/readiness tasks
remain available for components that have not migrated.

## Directory setup and legacy tasks

This directory is a Kustomize Component. Include it in a project's
`kustomization.yaml` to make its shared PromotionTasks available:

```yaml
components:
  - ../../kargo-shared-promotion-tasks
```

Keep component-specific preparation tasks in their component directories. Shared
tasks belong here when they can be reused across projects through explicit inputs.

These legacy tasks remain available for components that have not migrated:

| Task | Purpose |
|---|---|
| `github-ci-gate` | Wait for configured GitHub Actions and Prow checks. |
| `wait-for-infra-deployments-argocd-sync` | Check the expected Argo CD revision and Application health. |

Native Git operations require configured Kargo Git credentials. HTTP GitHub calls
use `konflux-kargo-git-operations` from the shared resources namespace. Argo CD
readiness uses the appropriate Kubernetes API reader token, such as
`argocd-app-reader-token-staging`; production callers select their reader explicitly.
See the shared secret configuration and each task's variables for deployment details.
