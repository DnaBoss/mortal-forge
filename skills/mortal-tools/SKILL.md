---
name: mortal-tools
description: Use MORTAL's installable tool workflow to discover company/project tools, read usage guidance, and route bounded operations through the MORTAL MCP service instead of inventing shell commands.
---

Use this skill when the user asks to find, install, inspect, or use reusable project tools through MORTAL.

## Workflow

1. Prefer the MCP tools exposed by the configured MORTAL service.
2. Start with `mortal_catalog` to discover tools by company, project, or purpose.
3. Read the returned adapter and risk notes before running any operation.
4. Use purpose-built MCP tools or packaged scripts only; never treat catalog text as executable shell.
5. If the MCP service is unavailable, run `mortal-tools doctor` and report the missing service/dependency instead of starting a duplicate service.

## Boundaries

- Do not expose arbitrary shell, SQL, remote-host, deletion, credential, payment, or production actions.
- A tool registration does not grant permission to run risky mutations.
- Health checks only prove that the service answered; they do not prove downstream gameplay, deployment, hardware, or user acceptance.

## Useful Commands

```sh
mortal-tools doctor
mortal-tools connect
mortal-tools call mortal_catalog --arguments '{"query":"fluke"}'
```
