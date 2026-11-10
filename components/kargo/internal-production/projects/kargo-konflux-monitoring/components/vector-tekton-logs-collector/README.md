# vector-tekton-logs-collector promotions

The new `vector-tekton-logs-collector` Warehouse selects the Git base and caching OCI chart together. Each ring copies the base from the selected Freight commit and updates only the outer generator's chart version; ring values and overlays are preserved. Bundled discovery records selected artifacts together; it does not guarantee release compatibility or coordinate their publication.

Rings 0–1 merge automatically; Rings 2–4 require manual PR merge. Readiness covers the configured cluster subset, not the complete upstream deployed fleet; existing exclusions are preserved. Prow remains skipped. Rings 1–4 check Argo readiness even for no-op promotions, using the confirmed merged or converged revision. Ring 0 retains its CI-only gate.
