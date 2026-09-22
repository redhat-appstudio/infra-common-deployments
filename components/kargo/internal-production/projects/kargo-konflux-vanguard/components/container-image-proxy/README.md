# container-image-proxy promotions

The new `container-image-proxy` Warehouse selects the Git base and caching OCI chart together.
It retains the existing discovery interval, chart constraint and discovery limit.
Each ring copies the base from the selected Freight commit and updates only the
outer generator's chart version; ring values and overlays are preserved.
Bundled discovery records selected artifacts together; it does not guarantee
release compatibility or coordinate their publication.

Rings 0–1 merge automatically; Rings 2–4 require manual PR merge. Existing
48h/48h/72h upstream soaks, Kanary verification and readiness targets are retained.
Readiness covers the configured cluster subset, not the complete upstream
deployed fleet; existing exclusions are preserved. Prow remains skipped.
Rings 1–4 check Argo readiness even for no-op promotions,
using the confirmed merged or converged revision. Ring 0 retains its CI-only gate.

## Rollout and rollback

Before merge, pause auto-promotion for the affected Stages and prevent manual
submissions. Drain old-origin queued/running Promotions and verification. Keep
the pause through GitOps application; validate the new bundle before resuming.
Draining alone races further old-Freight promotions, and changing requested
origins can reject newly submitted old-origin Promotions. The new bundle origin
restarts qualification; independently qualified old Freight does not qualify it.

This migration removes the two legacy Warehouse definitions. The combined
Warehouse is the only discovery source and creates Freight automatically.

To roll back, pause submissions and drain new-origin Promotions/verification,
restore the old two-origin Stage/task definitions and recreate both legacy
Warehouses with their original `Automatic` policy. Recheck Freight availability
and qualification before resuming; do not mix old tasks with bundled Freight.
