---
name: start-work
description: Start non-trivial work safely: read local rules, inspect existing work and ownership, choose bounded execution, and preserve evidence.
---

# start-work

Use before work that changes a repository, system, or service. The user's instruction and project rules take priority.

## Start

1. Read applicable project instructions and the shared [engineering policy](../cash-rule/references/engineering-policy.md). For sustained or multi-step work, use the canonical [cash-rule lifecycle](../cash-rule/SKILL.md); do not copy its state machine or checkpoint rules here.
2. Record the first available timestamp and check usage availability. Use `minimal` telemetry by default; see cash-rule [reporting](../cash-rule/references/reporting.md).
3. Inspect the current directory, branch, uncommitted changes, running owner/process, current artifacts and duplicate work. Preserve unrelated changes and continue existing ownership when appropriate.
4. Choose the smallest safe work area. Use the current worktree for small work tied to its state; isolate independent or conflicting changes. Do not create a parallel implementation when an owner already exists.
5. Keep a compact plan for multi-step work. The plan covers outcome, dependencies and whole-task acceptance; detail only the next one or two steps.

## Execution choice

Use deterministic tools for facts they can establish. Reuse existing scripts before writing new code; follow the shared `~/tools/` catalog rule in the cross-project context. When a model is needed, choose by expected total cost and risk using [model-dispatch](../cash-rule/references/model-dispatch.md), not a fixed local-first rule.

Decide whether bounded independent review or specialist work will materially reduce risk. Use a reviewer for materially risky changes; parallel implementation only when ownership and integration boundaries are explicit. If the runtime lacks delegation, do the review sequentially and say so.

## Finish

Validate the actual acceptance path at a depth proportionate to risk. Report what changed, the evidence checked, what remains unverified, and any required human action. Do not imply tests, review, deployment, or background execution occurred unless it did. For multi-round work, keep the current LOOP as a state summary and append history using the canonical checkpoint schema.
