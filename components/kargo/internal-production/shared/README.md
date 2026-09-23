# Shared project definitions

These directories are Kustomize Components. Each project explicitly includes them
to create resources in its own namespace:

```yaml
components:
  - ../../shared/promotion-tasks
  - ../../shared/verifications
```

- [Promotion tasks](promotion-tasks/) provide the reusable publication, CI, merge
  and readiness workflow. Component-specific preparation remains in each project.
- [Verifications](verifications/) provide AnalysisTemplates and supporting
  conformance template data. A Stage chooses which verification to run.

There is deliberately no aggregate `shared/kustomization.yaml`: deploying these
resources once centrally would not supply their project-local instances.
Credentials are provisioned separately under [platform/credentials](../platform/credentials/).
Ownership follows [Kargo OWNERS](../../OWNERS).
