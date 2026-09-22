# Notification Controller promotions

The unchanged image Warehouse selects 40-character SHA tags from
`quay.io/konflux-ci/notification-service`. Ring 0 remains a compose-output
passthrough: it does not deploy or run CI.

Ring 1 clones deployment Git main, prepares the selected image tag and matching
remote Kustomize commit, then uses the shared publication, exact-head GitHub CI,
automatic merge and Argo readiness tasks. Prow is explicitly skipped. Preparation
checks the Freight origin, ring, SHA tag and expected configuration entries before
mutation, and publishes its result only after success. PR descriptions show the
previous and proposed Git configuration.

The deployment path is `components/notification-controller/rings/ring-1/base`,
correcting the old task's obsolete `notification-controller-rd` path. The rendered
staging ApplicationSet also uses `notification-controller` as its Application
prefix. At infra-deployments revision `a747fe082fd8e67edd5efa40706385b81d3c53e9`,
`stone-stg-rh01` and `stone-stage-p01` consume this base. The additional mapped
`lightwell-dev` overlay is empty and is not a deployment readiness target.

Readiness requires both deployed Applications to be healthy and synchronized to
the confirmed revision, including no-op promotions. Freight metadata `noOpRing1`
remains `yes` or `no`. The existing two-cluster Kanary verification is unchanged.

SHA tags must remain immutable, and the image tag must identify an available
notification-service Git commit. Remote Kustomize fetching depends on GitHub
availability; pinning the top-level ref does not freeze any transitive mutable
dependencies. Main supplies ring-specific configuration, so the Freight pins the
image and remote source, not the entire deployment repository. Prow is not a
notification-specific validation gate. Exact-revision readiness can time out if
main advances before Argo observes the accepted revision.

See the [shared workflow guide](../../../../kargo-shared-promotion-tasks/README.md)
for branch ownership, merge and CI limitations.
