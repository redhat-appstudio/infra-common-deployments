---
name: pr-workflow
description: >
  Use when opening, monitoring, or iterating on a pull request in
  infra-common-deployments, including PR body template, CI interpretation,
  staging-first requirements, commit conventions, and environment-specific
  validation.
---

# PR Workflow

Full lifecycle reference for pull requests in infra-common-deployments.

## Overview

infra-common-deployments is a GitOps monorepo deploying shared infrastructure components via Kustomize and ArgoCD across four environments: `internal-staging`, `external-staging`, `internal-production`, `external-production`. PRs always target the upstream repository (`redhat-appstudio/infra-common-deployments`), never the fork.

## When to Use

- About to open a PR or write a PR description
- Preparing a production change and unsure about staging-first requirements
- Promoting a change from staging to production

## Branch Setup

If a dedicated branch already exists for this work, use it. Otherwise, create a branch from the latest main.

First, find which remote points to `redhat-appstudio/infra-common-deployments`:

```bash
git remote -v | grep redhat-appstudio/infra-common-deployments
```

Then fetch and branch from it:

```bash
git fetch <remote>
git checkout -b <branch-name> <remote>/main --no-track
```

Never branch from an old or diverged main.

## PR Body Template

Every PR follows this structure:

```markdown
## What

<concise list of what changed>

Environments affected: <list environments>

[KFLUXINFRA-1234](https://redhat.atlassian.net/browse/KFLUXINFRA-1234)

## Why

<motivation — why this change is needed>

## Validation

- `kustomize build` passes for all affected overlays
- <staging PR link, test results, other evidence>

## Risk Assessment

**Risk Level:** Low / Medium / High / Critical
**What could go wrong:** <describe what breaks if this change is incorrect>
**Rollback:** Revert PR / <specific rollback steps>
<explanation of risk and blast radius>
```

**Rules:**
- **What** — Concise change list, affected environments, Jira link at the bottom. Don't explain why here.
- **Why** — Motivation only. Keep it brief.
- **Validation** — Proof, not explanation. kustomize build results, staging links.
- **Risk Assessment** — Required for production PRs. May be omitted for staging.

## Commit Conventions

Prefix every commit with the Jira key when applicable:

```
KFLUXINFRA-1234: short description of the change
```

Always use `-s` flag (DCO sign-off).

Trailers (at end of commit message body). Use the actual agent/tool identity:
- Interactive sessions (human + agent): `Assisted-by:` trailer
- Agentic workflow (autonomous): `Authored-by:` trailer

## Pre-Push Validation

Run `kustomize build` on each affected directory containing a `kustomization.yaml`:

```bash
kustomize build argo-cd-apps/overlays/<env>/
```

Mention the results in the Validation section of the PR body.

## Staging-First Promotion

Changes must go to **staging first**, then production. This is a team convention — no CI check enforces it.

**Flow:**
1. Create a PR with staging changes (`internal-staging` and/or `external-staging`)
2. Get it merged and validated in staging
3. Create a separate PR for production (`internal-production` and/or `external-production`)
4. Reference the staging PR in the production PR's Validation section

**Hotfix exception:** If the change is a critical production hotfix, you may go directly to production. Document why staging was skipped in the PR body.

Each environment overlay is **self-contained** — never create shared base layers between staging and production.

## Production PR Requirements

- **Risk Assessment** section is mandatory (level, what could go wrong, rollback plan, blast radius).
- Reference the staging PR or evidence in the Validation section.
- When applying to both internal and external production, confirm with the human whether to split into separate PRs or apply together.

## Key CI Checks

| Check | Triggers On | What It Does |
|-------|-------------|--------------|
| **yamllint** (GHA + Prow) | All PRs | YAML formatting validation |
| **kube-linter** | All PRs | Kubernetes manifest best-practice scans |
| **chainsaw-tests** | `kyverno/**`, `policies/**` | Kyverno policy integration tests |
| **agents-md-lint** | `AGENTS.md` changes | Validates AGENTS.md under 300 lines |
| **pr-assigner** | PR opened/updated | Auto-assigns reviewers |

See `skills/ci-troubleshooting.md` for debugging failed checks.

## Interactive Sessions

In interactive sessions (human + agent), always confirm with the human before pushing and opening the PR. Show them the commit message, PR title, and PR body for approval first. Never push or create a PR without explicit approval.

Always use the `-s` flag (DCO sign-off) on all commits.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Skipping staging and going straight to production | Create staging PR first, then production |
| Forgetting Risk Assessment on a production PR | Add the section — reviewers will block without it |
| Not running `kustomize build` before pushing | Run it on all affected overlays, mention in Validation |
| Putting explanation in Validation instead of proof | Validation = evidence (build output, staging links). Why = explanation. |
| Branching from a stale main | Always fetch and reset from upstream before branching |
| Creating PR against fork instead of upstream | Use `gh pr create --repo redhat-appstudio/infra-common-deployments` |
