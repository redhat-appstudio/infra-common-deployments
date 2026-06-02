# infra-common-deployments

GitOps repository for shared infrastructure components across Konflux
common clusters using ArgoCD (app-of-apps pattern) and Kustomize.

## Quick Commands

| Action         | Command                                                 |
|----------------|---------------------------------------------------------|
| Build overlay  | `kustomize build argo-cd-apps/overlays/<env>/`          |
| Lint YAML      | `yamllint .`                                            |
| Chainsaw tests | `chainsaw test --config .chainsaw.yaml <test-dir>`      |

Kube-lint (requires building kustomize output first):

```sh
mkdir -p kustomizedfiles
kustomize build argo-cd-apps/overlays/<env>/ -o kustomizedfiles/<env>.yaml
kube-linter lint --config .kube-linter.yaml kustomizedfiles/
```

Dry-run apply:

```sh
kustomize build <path> | kubectl apply --dry-run=client -f -
```

## Project Layout

- `argo-cd-apps/base/{all-clusters,external,internal}/` — ApplicationSet
  definitions scoped by cluster type.
- `argo-cd-apps/overlays/` — four environments: `internal-staging`,
  `internal-production`, `external-staging`, `external-production`.
- `components/<name>/` — Kustomize components with `base/`, per-env overlays,
  and optional `k-components/` for shared patches (Component kind `v1alpha1`).
- `.yamllint.yaml` — relaxed profile, ignores Helm charts/templates.
- `.kube-linter.yaml` — excludes probe port checks.

## Key Conventions

- App-of-apps pattern: root ArgoCD Application manages ApplicationSets.
- Kubernetes resource files named after their Kind.
- Always `kustomize build` all four overlays before submitting changes.
- yamllint ignores `**/charts/` and `**/templates/` (Helm content).
- All changes via PR; OWNERS approval required.

## Testing

- Chainsaw tests validate Kyverno policies in `components/kyverno/` and
  `components/policies/`. Tests live in `.chainsaw-test/` directories.
- CI creates a Kind cluster, installs Kyverno, then runs chainsaw.
- kube-linter scans all kustomized output for Kubernetes best practices.
- yamllint validates all YAML files (relaxed profile, Helm excluded).

## CI Pipeline (GitHub Actions)

- `yamllint` — lints all YAML on PRs and pushes to main.
- `kube-linter` — builds kustomize overlays, scans with kube-linter,
  uploads SARIF to GitHub Security tab.
- `chainsaw-tests` — Kyverno policy tests in Kind. Only triggers on
  kyverno/policy file changes.
- `dep-triage` — auto-triages Renovate/Konflux bot dependency PRs.
- `auto-merge` — merges approved dependency PRs when all checks pass.

## Gotchas

- kube-linter excludes `kargo/` and `konflux-devlake/` (Helm-based).
- Chainsaw tests require Kyverno fully rolled out (300s timeout).
- Environment patches target ApplicationSets by group/version/kind —
  changing ApplicationSet structure may silently break patches.
