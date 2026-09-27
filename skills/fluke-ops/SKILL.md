---
name: fluke-ops
description: Operate Fluke-related local preview and validation workflows through MORTAL MCP with bounded locks, evidence, and no duplicated game or ledger logic.
---

Use this skill only for Fluke local preview, validation, and evidence workflows that are explicitly exposed by the MORTAL MCP service.

## Workflow

1. Call `mortal_catalog` with `{"query":"fluke"}` or read `mortal://skills/fluke-ops` if the host exposes resources.
2. Prefer read-only status first. Health is not gameplay acceptance.
3. For validations, run only the named scenario exposed by the MCP service and report the evidence path.
4. For preview restarts or other mutations, require explicit user authorization in the current task and keep the host lock.
5. On failure or timeout, inspect retained logs and actual process state before any retry.

## Boundaries

- Do not start Godot, Gateway, DB, or local AI inference unless the chosen MCP tool explicitly owns that operation and the user authorized it.
- Do not duplicate Fluke business, game, or ledger logic inside this skill.
- Do not apply PLAY tools to real-money or production systems.
