# Shared promotion workflow

Both playground Stages use the shared workflow: Ring 0 composes publication, CI
and merge; Ring 1 additionally checks Argo CD readiness. Component
preparation stays outside these tasks: clone the target repository, then invoke
the component task to update images, chart versions or manifests. The publication
task commits those changes in the same working directory.

```text
clone target -> component preparation -> publish -> CI -> merge -> Argo CD readiness
                                                                        -> Stage verification
```

Kargo tasks cannot invoke other tasks. The Stage is the composition layer; each
shared task owns one responsibility. Existing `github-ci-gate` and
`wait-for-infra-deployments-argocd-sync` callers are unchanged. The new workflow tasks are opt-in while both playground rings validate the migration.

## Task contracts

| Task | Required inputs | Successful `result` outputs |
|---|---|---|
| `publish-promotion-pr` | `srcPath`, `component`, `targetRing`, `prepared`, `baseCommitSHA`, `mergeMode`, `skipProwChecks` | `published`, `promotionAsNoOp`, `baseCommitSHA`, `headCommitSHA`, `prNumber`, `prURL` |
| `verify-promotion-ci` | `published`, `commitSHA`, `promotionAsNoOp`, `skipProwChecks`; `requiredProwChecks` when Prow is enabled | `passed`, `checkedSHA`, `promotionAsNoOp` |
| `merge-promotion-pr` | `passed`, `checkedSHA`, `headCommitSHA`, `baseCommitSHA`, `prNumber`, `promotionAsNoOp`, `mergeMode` | `mergeConfirmed`, `mergeCommitSHA`, `promotionAsNoOp` |
| `verify-argocd-deployment` | `mergeConfirmed`, `commitSHA`, `component`, `clusters` | `deploymentVerified`, `commitSHA`, `appDetails` |

Success flags are strings (`"yes"`), not booleans. No-op is `"yes"` or `"no"`;
`skipProwChecks` is `"true"` or `"false"`; `mergeMode` is `auto` or `manual`.
Missing prerequisite outputs become empty inputs and fail validation before
network operations. A failed task must never be translated into a no-op.

Inside a task, use `status('local-step')` and `task.outputs['local-step']`.
Between tasks, use explicit result outputs such as
`outputs['ci::result']?.passed ?? ''`. Do not use cross-task `status()` lookups.
Do not treat the existence of a task output map as proof of completion: intermediate
compose-output steps can populate that map before the task finishes.

The component preparation task emits `prepared: "yes"` only after its mutation
succeeds. Multi-step component tasks must guard their final result with the success
of every required mutation. The playground task demonstrates the single-step case.

## Promotion PR descriptions

The publisher owns one shared layout: summary, previous/proposed configuration
rows, an optional manifest comparison link, merge/check policy and collapsed
traceability details. It never claims CI passed at creation time.

Component preparation can return optional `prSummary`, `prChanges`, and
`prCompareURL` alongside `prepared`. Each change row contains `kind`, `previous`,
`proposed`, and `path`. The Stage forwards those fields to publication; other
components can omit them and get a generic summary plus the Files changed fallback.
Optional defaults use expressions returning an empty string/list so task expansion
does not make them required. Markdown table cells escape pipes, backticks and
line breaks.

Both playground tasks use native `yaml-parse` before `yaml-update` to capture the
previous image tag and manifest source. Those values describe the cloned target
Git configuration, not the live cluster. A comparison link is emitted only when
the previous manifest URL points to the configured source repository with a
40-character hexadecimal ref and the proposed ref has the same format. The link
compares configured manifest refs; it does not prove image build provenance or
fetch an application changelog. Other ref formats simply omit the link.

This adds local YAML parsing and composition, not GitHub API requests. Native
`git-open-pr` receives the formatted body through its existing call. Existing PRs
adopted by the native step may retain their original description; no extra update
API is added solely to refresh text.

## Stage policy

Each playground Stage declares `mergeMode` and `skipProwChecks` once and passes
those values to the relevant tasks. Both preserve automatic merge and explicitly
skip Prow, matching their existing policies. Ring 0 updates the development overlay
and ends after confirmed merge; Ring 1 updates staging and retains Argo CD readiness,
Kanary and conformance verification. Freight annotations remain `noOpRing0` and
`noOpRing1` respectively.
For Ring 0 with mandatory Prow, use `skipProwChecks: "false"` and pass an anchored
`requiredProwChecks` regex identifying the required suite to `verify-promotion-ci`.

`requiredCheckRuns` defaults to `.*`; `requiredProwChecks` defaults to an expression returning an empty string, which is
rejected when Prow is enabled. A literal empty default is not optional in Kargo.
The Stage forwards the string Prow policy with `quote(vars.skipProwChecks)` because
Kargo reparses unquoted expression results such as `true` into booleans. Every enabled selector must match
at least one result. Pending or absent checks wait; failed checks stop the gate.
Responses truncated beyond 100 results fail closed rather than silently ignoring
checks. Regex alternatives do not assert that every alternative exists: use one
reliable aggregate suite when all constituent checks must be required.

Publication uses one branch per Promotion (`<project>/promotions/<promotion>`),
with force-push disabled. Native `git-open-pr` supplies the PR identity directly;
there is no separate search for an arbitrary open PR. The workflow is specific to
the infra-deployments repository and its main branch.

Automatic mode uses native `git-merge-pr` with squash merging. Manual mode uses
native `git-wait-for-pr` and never requests a merge. Both require passing CI for
the exact published head SHA. HTTP identity checks verify the tested head, main
base branch and resulting merge SHA. Native merge has no atomic expected-head
precondition: another writer can change a branch between inspection and merge.
The branch must be owned exclusively by the Promotion. The final identity check
can detect a mismatch but cannot undo a merge that already happened.

## No-op and readiness

A skipped commit means the desired component content is already in the cloned
main revision. Publication returns `published: "yes"` to indicate the publication
phase completed, even though no branch or PR was created. CI emits a passing no-op
result without making GitHub requests, and merge returns the cloned base revision
without merging. `mergeConfirmed` means the workflow has an accepted target
revision; it does not mean a PR was merged in the no-op case.

If native PR creation is skipped after another writer converges main to the
promoted content, publication reads main's commit and tree, then compares that tree
with the immutable pushed commit's tree. Only exact whole-repository tree equality
produces a concurrent no-op, targeting the observed main revision. A mismatch
fails safely; a skipped PR alone is never evidence of success. This recovery uses
two bounded HTTP reads through the shared PAT.

Each Stage preserves its existing `noOpRing0` or `noOpRing1` Freight annotation. This annotation
is informational; the task output carries the fresh decision for subsequent steps.

Ring 1 readiness always runs, including no-ops. Ring 0 preserves its existing
Git-only development flow. One `verify-argocd-deployment` invocation checks the
whole component/ring group, using `component` and pipe-separated literal `clusters`.
For example, `component: dummy-deployment` and
`clusters: stone-stg-rh01|stone-stage-p01` require both corresponding Applications.
Empty, duplicate, whitespace and regex entries are rejected. The task does not
infer component names from repository directories.

All expected Applications must be present in the same complete API response and:

- not marked for deletion;
- Synced and Healthy at the exact target revision;
- free of an active operation; operation history, when present, must be successful;
- reconciled at or after the fixed readiness-start timestamp, and after the
  completed operation when one exists.

Extra Applications are ignored. A missing target waits instead of allowing a
partially deployed group through. All targets share one 45-minute timeout.
A healthy Application without operation history can pass. Health remains the
controller's reported observation, not a guarantee workloads cannot change later.

The Stage passes `component` and a pipe-separated list of 1–15 literal cluster
names. One HTTP request per poll lists Applications from the local Kubernetes API;
the task selects exact `<component>-<cluster>` names from that response. No labels
or ApplicationSet changes are required. This uses the existing Kubernetes reader
token, not an Argo CD server API token or GitHub credentials.

The response includes the namespace's Applications, not only the requested ring.
Kargo's 2 MiB response limit therefore remains a scaling limitation: an oversized
response errors and cannot pass readiness. Pagination is rejected rather than
accepting an incomplete group. The cluster list filters verification locally; it
does not reduce the server response size.

Authorization and endpoint errors fail immediately. Missing Applications and
unhealthy states wait for convergence. `tokenSecret` defaults to
`argocd-app-reader-token-staging`, and `appsNamespace` defaults to
`argocd-infra-deployments`. The task reads the shard's local Kubernetes API and
does not initiate Argo CD sync operations or consume GitHub API quota.

Exact revision matching is deliberately conservative. In a busy monorepo Argo CD
may advance to a later commit before this gate observes the target revision,
causing a timeout even when the component content is correct. History membership
or Git ancestry alone is insufficient because a later commit can revert the
component. Relaxing this requires proving current component content matches the
promoted content, not simply accepting any descendant commit.

A timeout can still have a generic controller message; `appDetails` is emitted
only after a successful HTTP step. Inspect the listed Applications when diagnosing
a timeout. These tasks do not promise persistent per-poll diagnostics.

## Request volume and retries

| Operation | Polling / retry budget |
|---|---|
| Actions and Prow | `ciPollInterval` defaults to 2 minutes; up to 2h30m per phase |
| Native automatic merge | 2-minute polling; up to 2h |
| Native manual merge waiter | 5-minute polling; up to 168h |
| PR identity checks | 2-minute polling; up to 2h |
| Concurrent no-op verification | Two HTTP reads when needed; 2-minute polling and up to 2h per step |
| Argo CD readiness | 45-minute budget for the complete cluster group; Kubernetes API, not GitHub |

HTTP 403 responses indicating primary/secondary rate limits, and HTTP 429,
remain pending rather than terminating CI or identity checks. Other authorization
errors remain terminal. Kargo uses the configured fixed polling interval here;
this does not implement exact `Retry-After` or reset-time scheduling. HTTP steps
still use the shared PAT, not the native GitHub App credential.

Native `git-merge-pr` in Kargo v1.11.3 treats provider errors as terminal, including
some transient errors. Its retry budget covers pending merge readiness, not every
network failure. Correcting that requires upstream runner support; these tasks do
not hide that failure or start readiness without a confirmed target revision.

Task reuse reduces duplicated configuration, not API calls by itself. Seventy
concurrent CI waiters at two-minute intervals are approximately 2,100 requests per
hour for one active polling phase, before other requests. Four active rings per
component can multiply this to 8,400. Budget against the actual GitHub credential
shared by workloads, monitor rate limits and stagger promotions before broad
rollout. Poll intervals are not a global rate limiter.

Restart behavior after a successful push must be validated before broad rollout:
the promotion-specific branch is retained and force-push is disabled. Branch
retention and abandoned manual PR cleanup are separate operational policies; the
pending-promotion cleaner does not delete either.

## Adopting another component

1. Keep cloning and component changes in the Stage/component task. Use the same
   `srcPath` for preparation and publication.
2. Emit `prepared` only after all required component changes succeed.
3. Pass the clone's main commit as `baseCommitSHA` and wire explicit result outputs
   through publication, CI, merge and readiness as in the playground Stage.
4. Choose Prow and merge policy explicitly. Preserve component-specific Stage
   verification and Freight source policy.
5. Invoke readiness once with the component prefix, complete literal cluster list
   and correct reader token. No Application labels are required.

For image-only updates, resolve the image from the selected Freight. For manifests,
do not copy source files from mutable main: clone the selected Freight's immutable
Git commit into a separate source directory and copy into the target checkout.
When copying an upstream ring's rendered snapshot, use its recorded deployment
revision; the original source Freight commit may predate that snapshot. Prove
this mapping before migrating manifest-copy components.

This PR migrates both playground image-based flows (Ring 0 and Ring 1). Next candidates must
cover image-only, manifest-copy, chart/image plus manifest, and manual-production
flows independently. Stage size depends on its sources and policies; explicit
output wiring is retained even when it costs extra YAML lines.

## Validation and rollback

Validate the playground project and all four root overlays with `kustomize build`,
then lint the changed YAML. Rendering does not validate runtime expressions or
prove GitHub/Argo CD integration. Validate the composed tasks on the deployed Kargo
version before extending beyond the playground. No test files are added to this PR.

Rollback the playground caller and component completion output, then remove the
new tasks after confirming no caller references them. Existing legacy CI/readiness
tasks remain available throughout migration.
