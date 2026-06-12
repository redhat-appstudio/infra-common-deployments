---
name: brainstorming-workflow
description: >
  Use when in an interactive session and the user requests a new feature, significant
  change, or migration in infra-common-deployments. Provides a structured process
  choice before any changes are made. Skip when dispatched with a complete task.
---

# Brainstorming Workflow

Discipline for interactive sessions involving new features, overlay restructuring, component additions, or other significant changes.

## Context Detection

- **Interactive session** (human in CLI/IDE): follow this workflow.
- **Dispatched with a complete task** (sub-agent, automation, explicit spec): skip entirely and execute.

## First Message

**Always ask this question first**, even when the request sounds urgent. It's a quick check that keeps things on track. Your first message must contain **exactly this question and nothing else** — no clarifying questions, no context gathering, no implementation details.

> I can approach this a few ways:
>
> A) Jump straight to making changes
> B) Discuss approaches first, then make changes
> C) Full design process — explore approaches, write up a plan, then execute
>
> Which works for you?

That's it. One question. Wait for the answer before asking anything else.

**After asking**, if the human replies with "just do it", gives a direct instruction, or otherwise signals urgency, treat as **A**. But ask first — don't skip the question based on tone or urgency cues in the initial request.

## Path A — Jump to Changes

Proceed directly. All existing conventions still apply (pr-workflow, kustomize build validation). No additional ceremony.

## Path B — Discuss Approaches

1. **Understand the problem**: what is being changed, why, and any constraints.
2. **Propose 2-3 approaches** with trade-offs (blast radius, complexity, number of PRs, staging-first implications).
3. **Lead with a recommendation** and explain why.
4. Let the human choose, then execute.

Examples where this helps:
- Deciding whether a component change needs staging-first or qualifies as a hotfix
- Planning how to restructure component overlays across internal/external clusters
- Choosing between adding a new ApplicationSet vs. extending an existing one
- Evaluating whether a kustomize component (`k-components/`) makes sense vs. duplicating patches

Ask one question at a time. Prefer multiple choice over open-ended questions.

## Path C — Full Design Process

Everything in Path B, plus:

1. **Write up the plan** — what changes in which files, which environments, how many PRs.
2. **Break into ordered steps** with dependencies (e.g., staging PR first, then production PR).
3. Get human approval before executing.

## Key Principles

- **One question at a time.** Never pile up multiple questions in one message.
- **Prefer multiple choice.** Easier for the human to decide quickly.
- **Human decides the process, not the agent.** Respect the chosen path.
- **"Just do it" means just do it.** Don't add process the human didn't ask for.
