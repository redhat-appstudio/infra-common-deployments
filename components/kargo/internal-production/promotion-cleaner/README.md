# Promotion Cleaner

CronJob that prevents promotion queue buildup in Kargo projects by
aborting stale Pending promotions while respecting warehouse boundaries.

## Problem

Kargo Warehouses discover new freight every ~2 hours. Each freight
auto-promotes through the ring pipeline. If a promotion takes longer
than 2 hours (waiting for CI, ArgoCD sync, etc.), new promotions
queue behind it. Kargo processes promotions sequentially and does NOT
cancel or supersede pending promotions when newer ones arrive.

Without cleanup, a stage can accumulate many stale Pending promotions
that will each run to completion — even though each one is outdated
by the time it starts.

## How It Works

The cleaner runs every 10 minutes and performs three steps per
configured project:

### Step 1 — Build a freight-origin lookup

```
kubectl get freight → { freight-name: warehouse-name }
```

Each freight originates from a specific Warehouse. The cleaner builds
a lookup table mapping freight names to their origin warehouse.

### Step 2 — Group pending promotions by (stage, warehouse)

```
Pending promotions → enrich with warehouse origin → group by (stage + origin)
```

This is the key design decision. A stage like `ring-0-etcd-shield`
can have pending promotions from TWO different warehouses:

- `etcd-shield-manifest-wh` (git manifest changes)
- `etcd-shield-image-wh` (container image updates)

These are **independent promotion queues**. A new manifest freight
should NOT cancel a pending image freight, and vice versa. The cleaner
groups by `stage/warehouse` and within each group keeps only the
**newest** promotion.

**Example:**

```
Pending promotions for ring-0-etcd-shield:
  promo-1  freight=abc  origin=etcd-shield-manifest-wh  created=10:00
  promo-2  freight=def  origin=etcd-shield-manifest-wh  created=10:30
  promo-3  freight=ghi  origin=etcd-shield-image-wh     created=10:15

After grouping by (stage, origin):
  Group "ring-0-etcd-shield/etcd-shield-manifest-wh":
    promo-1 (10:00) ← ABORT (stale)
    promo-2 (10:30) ← KEEP (newest)

  Group "ring-0-etcd-shield/etcd-shield-image-wh":
    promo-3 (10:15) ← KEEP (only one, nothing to abort)

Result: promo-1 aborted, promo-2 and promo-3 kept.
```

### Step 3 — Abort stale promotions safely

For each stale promotion identified:

1. **Re-check phase** — the promotion may have advanced from Pending
   to Running between Step 2 and now. Only Pending promotions are
   aborted. Running promotions are left to finish.

2. **resourceVersion precondition** — the patch includes the
   resourceVersion captured in Step 2. If the promotion was modified
   between the list and patch operations, the Kubernetes API server
   rejects the patch with a conflict error, preventing accidental
   abort of a promotion that just started running.

3. **Error counting** — failed patches are logged and counted
   separately from successful aborts. The job exits non-zero if any
   errors occurred, making failures visible in CronJob history.

## Configuration

Projects are listed in `config.yaml` (one per line):

```yaml
data:
  projects: |
    kargo-konflux-core
```

**When adding a new project**, you must also add two RoleBindings
in `rolebindings.yaml`:

1. **Kubernetes RBAC** — bind ClusterRole `kargo-promotion-cleaner`
   (grants get/list/patch on Promotions and get/list on Freight)
2. **Kargo RBAC** — bind Role `kargo-promoter` (required by Kargo's
   admission webhook to permit promotion updates)

Without both bindings, the cleaner cannot operate in that namespace.

## Components

| File                  | Purpose                                               |
| --------------------- | ----------------------------------------------------- |
| `config.yaml`         | ConfigMap listing projects to clean                   |
| `cronjob.yaml`        | CronJob definition (runs every 10m)                   |
| `serviceaccount.yaml` | ServiceAccount for the CronJob                        |
| `clusterrole.yaml`    | ClusterRole: promotions (get/list/patch), freight (get/list) |
| `rolebindings.yaml`   | Per-project RoleBindings (K8s RBAC + Kargo promoter)  |

## How Kargo Abort Works

Setting the annotation `kargo.akuity.io/abort=terminate` on a
Promotion resource tells the Kargo controller to transition it to
the `Aborted` phase. Only non-terminal promotions (Pending, Running)
can be aborted. Terminal promotions (Succeeded, Failed, Errored) are
silently ignored.

## Tuning

| Parameter               | Default             | Description                       |
| ----------------------- | ------------------- | --------------------------------- |
| `schedule`              | `*/10 * * * *`      | How often to check (every 10 min) |
| `activeDeadlineSeconds` | `300`               | Max job runtime (5 min)           |
| Image                   | `task-runner:3.1.2` | Pinned image with kubectl + jq    |
