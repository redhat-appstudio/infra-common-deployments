# Onboard a component

[Production overview](../README.md) · [Operations](operations.md) · [Verification](verifications.md)

## Ring naming conventions

All Kargo resources follow a strict naming scheme. Monitoring dashboards, alerts, promotion cleaners and automation scripts depend on these patterns — deviating silently breaks observability and tooling.

### Stage names

```
ring-{N}-{component}
```

`N` is the ring number, `component` is the kebab-case component name matching the Warehouse origin. Examples: `ring-0-konflux-operator`, `ring-2-etcd-shield`.

### Ring numbering and environment mapping

| Ring | Environment | Shard | Color | Purpose |
|---|---|---|---|---|
| ring-0 | development | *(none — main controller)* | blue | Direct from Warehouse. Runs full CI including Prow. |
| ring-1 | staging | infra-deployments-staging | yellow | Staging clusters. Kanary verification + conformance tests. |
| ring-2 | production | infra-deployments-production | orange | First production ring. |
| ring-3 | production | infra-deployments-production | red | Second production ring (wider blast radius). |
| ring-4 | production | infra-deployments-production | purple | Final production ring (full fleet). |

Not every component uses all five rings. A component with two clusters may only have ring-0 through ring-2.

### Labels and annotations

Every Stage must carry:

```yaml
labels:
  konflux-environment: development | staging | production
annotations:
  kargo.akuity.io/color: blue | yellow | orange | red | purple
```

These are used by the Kargo UI, monitoring dashboards and promotion policies.

### Other resource names

| Resource | Pattern | Example |
|---|---|---|
| Warehouse | `{component}` | `konflux-operator` |
| PromotionTask (prepare) | `{component}-promote-ring-{N}` | `konflux-operator-promote-ring-1` |
| PR branch | `{project}/{component}/ring-{N}` | `kargo-konflux-core/konflux-operator/ring-0` |
| ArgoCD Application | `{component}-{cluster}` | `konflux-operator-stone-stage-p01` |

### Monitoring dependency

The `konflux-environment` label and the `ring-{N}-{component}` stage name pattern are used by:
- Grafana dashboards to filter promotion metrics by environment
- Prometheus ServiceMonitor label selectors
- Promotion cleaner to identify and group pending promotions
- Alerting rules to route ring-specific incidents

Renaming a stage or changing its labels without updating dashboards and alerts will cause silent monitoring gaps.

## Choose the deployment repository first

- **infra-common-deployments:** follow the existing
  [kargo-infra-common guide](../projects/kargo-infra-common/README.md) and its
  [Kargo component](../projects/kargo-infra-common/kargo/). This project has
  project-specific stages and tasks. The repository's
  [onboarding skill](../../../../skills/kargo-onboard.md) is scoped to the
  `kargo-infra-common` workflow.
- **infra-deployments:** choose the appropriate domain project from the
  [project directory](../README.md#projects), then follow the shared workflow below.
  Shared publication/CI/merge tasks currently target this repository and `main`.

Do not copy historical [project examples](../../examples/project/) as a new
production workflow. Use a live implementation with the same source model.

## Pick a maintained reference

| Source model or requirement | Implementation |
|---|---|
| Image SHA and matching remote manifests | [Notification Controller](../projects/kargo-konflux-vanguard/components/notification-controller/) |
| Git base plus chart | [Artifact Registry Proxy](../projects/kargo-konflux-vanguard/components/artifact-registry-proxy/) |
| Immutable public Git base plus private configuration ref | [Repository Validator](../projects/kargo-konflux-infrastructure/components/repository-validator/) |
| Controller image plus companion-image availability check | [Multi-platform Controller](../projects/kargo-konflux-infrastructure/components/multi-platform-controller/) |
| Mandatory Prow and Stage verification | [Konflux Operator](../projects/kargo-konflux-core/components/konflux-operator/) |
| Small complete shared-workflow example | [Playground Ring 1](../projects/kargo-production-playground/components/dummy-deployment/stages/ring-1-stage.yaml) |

These are implementation references, not universal policy defaults. Confirm the
actual deployment paths, active cluster overlays and rendered Application names
before selecting readiness targets. Empty overlays are not deployed workloads.

## Define the component's contract

Record the source repositories/images/charts, paths that discovery watches,
files preparation may change, target rings and clusters, Prow/check selectors,
merge policy, verification and soak settings. Preserve an existing component's
policy unless a separate behavior change is intended.

A Warehouse can contain multiple subscriptions in one Freight bundle. Separate
Warehouses represent independent origins; choose deliberately rather than
splitting every subscription automatically. A bundle of independently selected
Git commits is not an atomic cross-repository release.

For manifest copying, use the selected Freight's immutable Git commit in a
separate checkout. The destination checkout may start at current deployment
`main`; copying its moving base or a previous ring would lose the selected
release boundary. Preserve ring-specific configuration outside the intended edits.

## Implement preparation and connect the Stage

Keep the component under `projects/<project>/components/<component>/` with its
Kustomization, Warehouse definition, preparation task and `stages/`. Follow the
existing project's filenames; a larger component may have multiple task files.

The [shared task README](../shared/promotion-tasks/README.md) defines the full
input/output contract. A current shared-workflow Stage connects:

1. Clone the deployment repository and any immutable source checkout.
2. Run component preparation. Validate the Freight and expected file layout;
   publish `prepared: 'yes'` only after every required edit succeeds.
3. Call `publish-promotion-pr` with preparation outputs and the cloned base SHA.
4. Call `verify-promotion-ci` with publication outputs and explicit CI policy.
5. Call `merge-promotion-pr` with checked/published SHAs and explicit merge mode.
6. Where required, call `verify-argocd-deployment` with the confirmed merge SHA,
   exact Application prefix, full readiness target list and reader-secret name.
7. Configure post-promotion `spec.verification` separately when required.

Forward task results through the expanded alias, for example
`outputs['promote::result']?.prepared ?? ''`; within a task use `task.outputs`.
Missing required outputs must not manufacture successful completion. Preserve
shared no-op handling: unchanged content can skip a PR, but configured deployment
readiness still runs against the confirmed revision.

Kargo evaluates expressions and may convert string-shaped values to other types.
For example, forward the string Prow switch as:

```yaml
- name: skipProwChecks
  value: ${{ quote(vars.skipProwChecks) }}
```

Use an explicit Prow policy and a nonempty required selector when enabled. Do not
assume an image-only component never needs Prow. Keep preparation values and
forwarded collections compatible with the shared task's declared inputs.

## Wire the project and its policy

Add the component to the project's `kustomization.yaml`, and its Stage files to
`stages/kustomization.yaml`. Check `base/project-config.yaml` for the corresponding
promotion policies. The domain projects already include
`../../shared/promotion-tasks` and `../../shared/verifications`.

`autoPromotionEnabled` controls whether Kargo starts an eligible promotion.
`mergeMode: manual` means the shared workflow waits for a human to merge the PR;
an automatically started production promotion can still require manual merge.
These are distinct controls. Soak settings belong to each Stage's Freight source;
there is no single duration or fixed number of rings for all components.

Use the configured shard and credential references for the target environment.
Central credentials are deployed by [platform/credentials](../platform/credentials/),
not by adding another secrets Component to a project. Review existing access and
replication before requesting credentials; never put credential values in YAML,
PR descriptions or verification arguments.

Document component-specific policy and exceptions in its README and use existing
[ownership](../../OWNERS). For an origin migration, plan legacy Promotion/PR
handoff and Freight history explicitly; renaming a Warehouse is not a directory move.

## Validate before wider use

Render the affected project, check resource names/namespaces and all task and
verification references, and follow the repository's required overlay checks in
[operations](operations.md#local-validation). A successful Kustomize build does
not execute Kargo expressions or prove promotion correctness.

Exercise preparation against representative deployment fixtures and evaluate
expressions with the target Kargo behavior. Cover missing/malformed inputs,
failed prerequisites, expected edits, configuration preservation and no-op
outputs. Confirm readiness lists against deployment evidence and CI selectors
against the required checks. Use the playground or an agreed controlled rollout
for execution validation; do not silently change live promotion policy to test it.
