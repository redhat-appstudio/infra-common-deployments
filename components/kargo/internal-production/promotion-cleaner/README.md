# Promotion Cleaner

CronJob that prevents promotion queue buildup in Kargo projects.

## Problem

When a Warehouse produces freight every 2h, each freight auto-promotes
to ring-0/ring-1. If a promotion takes longer than 2h (waiting for CI,
ArgoCD sync, etc.), new promotions queue up behind it. By the time the
running promotion finishes, multiple pending promotions are waiting —
each one stale because newer freight has already arrived.

Kargo processes promotions sequentially and does not cancel or supersede
pending promotions when newer ones arrive.

## Solution

A CronJob runs every 10 minutes and, for each configured project:

1. Lists all **Pending** promotions
2. Groups them by Stage
3. Keeps only the **newest** pending promotion per Stage
4. Re-checks each target's phase before patching (race guard)
5. Aborts older pending promotions via the
   `kargo.akuity.io/abort=terminate` annotation with resourceVersion
   precondition

This ensures only the latest freight gets promoted, skipping
intermediate versions that were already superseded.

## Configuration

Projects are listed in `config.yaml`:

```yaml
data:
  projects: |
    kargo-konflux-core
```

Add or remove project names (one per line) to control which projects
are cleaned. Only Pending promotions in listed projects are affected.
Running promotions are never aborted.

**Important:** When adding a new project, you must also add
RoleBindings for that project in `rolebindings.yaml` — both the
Kubernetes RBAC binding (ClusterRole `kargo-promotion-cleaner`) and
the Kargo RBAC binding (Role `kargo-promoter`). Without both, the
cleaner cannot patch promotions in that namespace.

## Components

| File                    | Purpose                                                       |
| ----------------------- | ------------------------------------------------------------- |
| `config.yaml`           | ConfigMap listing projects to clean                           |
| `cronjob.yaml`          | CronJob definition (runs every 10m)                           |
| `serviceaccount.yaml`   | ServiceAccount for the CronJob                                |
| `clusterrole.yaml`      | ClusterRole granting get/list/patch on Promotions             |
| `rolebindings.yaml`     | Per-project RoleBindings (K8s RBAC + Kargo promoter role)     |

## RBAC

The cleaner uses two layers of RBAC per project:

1. **Kubernetes RBAC** — ClusterRole `kargo-promotion-cleaner` bound
   via RoleBinding in each project namespace. Grants get/list/patch
   on `kargo.akuity.io/promotions`.

2. **Kargo RBAC** — Role `kargo-promoter` (created by Kargo per
   project) bound via RoleBinding in each project namespace. Required
   by Kargo's admission webhook to permit promotion updates.

The cleaner does NOT have cluster-wide access. It can only operate in
namespaces where both RoleBindings exist.

## How Abort Works

Kargo supports aborting promotions by setting the annotation
`kargo.akuity.io/abort=terminate` on the Promotion resource. The
controller detects this annotation and transitions the Promotion to
the `Aborted` phase. Only non-terminal promotions (Pending, Running)
can be aborted. Terminal promotions (Succeeded, Failed, Errored) are
ignored.

## Safety Guards

- **Phase re-check:** Before patching, the cleaner re-reads the
  promotion's current phase. Only Pending promotions are aborted.
  If a promotion advanced to Running, it is left to finish.
- **resourceVersion precondition:** The patch includes the
  resourceVersion from the initial list. If the resource was modified
  between list and patch, the API server rejects the patch.
- **Error counting:** Failed list or patch operations are counted
  separately. The job exits non-zero if any errors occurred.

## Observability

The CronJob logs every action:

```text
[cleaner] aborting stale pending promotion: kargo-konflux-core/ring-0-konflux-operator.01m22m7t.d44180a (rv=12345)
[cleaner] skipping kargo-konflux-core/slow-promo-3 (phase changed to Running)
[cleaner] done. aborted=2 errors=0
```

Job history is retained (3 successful, 3 failed) for debugging.

## Tuning

| Parameter                | Default           | Description                          |
| ------------------------ | ----------------- | ------------------------------------ |
| `schedule`               | `*/10 * * * *`    | How often to check (every 10 min)    |
| `activeDeadlineSeconds`  | `300`             | Max job runtime (5 min)              |
| Image                    | `task-runner:3.1.2`| Pinned image with kubectl + jq      |
