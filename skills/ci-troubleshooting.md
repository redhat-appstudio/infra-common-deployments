---
name: ci-troubleshooting
description: >
  Use when a CI check fails on a PR in infra-common-deployments and you need to
  understand what failed, how to read the logs, and how to fix it.
---

# CI Troubleshooting

## Overview

How to investigate and fix CI failures on infra-common-deployments PRs. This repo uses GitHub Actions and Prow for CI — there are no E2E tests and `/retest` does not apply here.

## When to Use

- A CI check failed on your PR
- You need to understand what a CI comment or status means
- You want to re-run a failed check

## Prerequisites

Verify `gh` CLI is installed and authenticated:

```bash
gh auth status
```

## Reading CI Logs

### GitHub Actions checks

```bash
gh pr checks <PR-number> --repo redhat-appstudio/infra-common-deployments
```

To investigate a failed check:

```bash
gh run view <run-id> --repo redhat-appstudio/infra-common-deployments
gh run view <run-id> --repo redhat-appstudio/infra-common-deployments --log-failed
```

### Prow checks

Prow runs `yamllint` separately. Find Prow statuses and their log URLs:

```bash
gh api repos/redhat-appstudio/infra-common-deployments/commits/<sha>/statuses \
  --jq '.[] | select(.context | startswith("ci/prow")) | "\(.context) — \(.state) — \(.target_url)"'
```

The `target_url` is the Prow log viewer page. Open it in a browser or fetch it to read logs. That page also contains a "Prow Job YAML" link with the prowjob UUID — use it to inspect the full ProwJob resource:

```
https://prow.ci.openshift.org/prowjob?prowjob=<prowjob-uuid>
```

This shows the ProwJob spec, cluster assignment, timeouts, and final status — useful for debugging infrastructure issues (pod scheduling, timeout config, secret mounts).

## CI Checks Reference

| Check | Source | Triggers On | What It Does |
|-------|--------|-------------|--------------|
| **yamllint** | GitHub Actions | All PRs, pushes to main | YAML formatting validation |
| **yamllint** | Prow (`ci/prow/yamllint`) | All PRs | Same validation, separate system |
| **kube-linter** | GitHub Actions | All PRs, pushes to main | Kubernetes manifest best-practice scans |
| **chainsaw-tests** | GitHub Actions | `components/kyverno/**`, `components/policies/**` | Kyverno policy integration tests in Kind |
| **agents-md-lint** | GitHub Actions | `AGENTS.md` changes | Validates AGENTS.md stays under 300 lines |
| **pr-assigner** | GitHub Actions | PR opened/updated | Auto-assigns reviewers from CODEOWNERS |
| **tide** | Prow | All PRs | Merge automation — manages merge queue |

## Common Failures

### yamllint

YAML formatting errors (trailing whitespace, wrong indentation, missing newline at end of file). The CI logs show the exact file and line. Fix those directly, or run `yamllint .` locally to reproduce.

Both GitHub Actions and Prow run yamllint — both must pass.

### kube-linter

Scans kustomized Kubernetes manifests for security and best practice violations. Check the logs for specific rule violations.

To reproduce locally:

```bash
mkdir -p kustomizedfiles
kustomize build argo-cd-apps/overlays/<env>/ -o kustomizedfiles/<env>.yaml
kube-linter lint --config .kube-linter.yaml kustomizedfiles/
```

**Note:** kube-linter excludes `kargo/` and `konflux-devlake/` (Helm-based components).

### chainsaw-tests

Path-triggered on `components/kyverno/**` and `components/policies/**` changes. Runs Kyverno policy tests in a Kind cluster.

Often flaky due to infrastructure issues (Kyverno rollout timeout, Kind cluster provisioning). If logs show no relevant errors and the PR looks correct, re-run the failed job:

```bash
# Find the run ID from pr checks
gh pr checks <PR-number> --repo redhat-appstudio/infra-common-deployments
# Re-run just the failed jobs
gh run rerun <run-id> --repo redhat-appstudio/infra-common-deployments --failed
```

To run locally:

```bash
# Set up Kind cluster with Kyverno (300s timeout for rollout)
hack/chainsaw/chainsaw-prepare.sh
# Run specific tests
chainsaw test --config .chainsaw.yaml <test-dir>
```

### agents-md-lint

Fails if AGENTS.md exceeds 300 lines. Trim content or move details into skills files.

### tide (Prow)

Tide manages the merge queue. A pending `tide` status is normal — it means the PR is waiting for approval or required checks. Not a failure unless it stays stuck after all checks pass and approvals are in place.
