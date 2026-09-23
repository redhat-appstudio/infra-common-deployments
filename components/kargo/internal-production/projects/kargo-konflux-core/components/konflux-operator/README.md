# Operator manifest readiness POC

Ring 1 (`stone-stage-p01`) tries manifest equivalence when Argo CD has synchronized
a different repository commit than the promotion. Ring 0, Ring 2 and other
components retain their current behavior.

## Why

Two PRs can merge before Argo CD reconciles. If the second PR changes an unrelated
component, requiring the first PR's exact repository SHA can time out even though
the Operator configuration was applied.

## How it works

1. Read the specific Operator Application through the Kubernetes API. Require a
   fresh reconciliation, `Synced`, `Healthy`, no active operation or deletion, and
   the expected single Kustomize source, cluster-overlay path and cluster API
   destination (the same endpoint used by staging conformance tests).
2. If its revision equals the promotion's confirmed merge SHA, use that proof.
3. Otherwise, clone both immutable revisions using native Kargo Git credentials
   and render the **entire** `ring-1/stone-stage-p01` overlay at each revision.
4. Compare the complete rendered YAML with native local Git steps. Both image and
   non-image changes are covered. Git ignore rules cannot hide the render file.
5. Re-read Argo CD and require the same Application UID, destination, revision and
   readiness conditions. Only then emit `deploymentVerified: yes`.

The baseline/comparison commits exist only in disposable local checkouts. Nothing
is pushed. The existing promotion checkout is not modified. There are no added
GitHub PAT calls; native cloning and remote Kustomize resources still use network
access. The exact-revision path avoids cloning and rendering altogether.

## Boundaries before wider rollout

- This is desired-manifest equivalence plus Argo CD's sync/health report, not an
  independent audit of every live resource or Operator-generated workload.
- Remote render dependencies must be immutable. The Operator manifest source is
  pinned by commit; new mutable dependencies need review before using this POC.
- Argo CD and Kargo renderer versions/build options must be checked in staging.
  The POC rejects per-Application Kustomize/Helm/plugin overrides, multiple
  sources and per-Application ignore rules. Global Argo customization remains a
  live-validation prerequisite.
- Different YAML, render failures or a changed observed revision never pass.
  A different revision during comparison fails closed; retry the promotion to
  take a new snapshot. This POC does not loop the entire comparison automatically.
- The initial readiness poll is bounded at 45 minutes. A freshly reconciled but
  older/different configuration can fail the comparison sooner; it is never
  accepted merely because it is healthy. There is no timed healthy fallback.
- Byte comparison is deliberately strict. Harmless ordering differences can
  reject equivalence, but cannot create a false match.

## Validation before merging

Use this draft in staging first: confirm renderer parity, then merge an unrelated
PR before reconciliation and check for `identical-rendered-manifests` in task
outputs. Confirm an Operator manifest change fails even when the image is the
same. No production-ring rollout is part of this POC.

Rollback: point Ring 1 back to `verify-argocd-deployment` with its previous
component, cluster and token inputs, or revert this PR.
