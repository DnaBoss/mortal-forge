---
name: debug-not-working
description: Diagnose reports like "not working", "not updated", "still the same", or "no effect" when local verification appears green. Use in any project to reproduce the user's actual state, identify the single cause that explains all symptoms, and avoid arguing from narrow evidence.
---

# debug-not-working

Use this skill when the user says the result did not take effect, especially when your own checks look normal.

## Rule

Assume your verification has a blind spot until the user's symptoms are explained.

## Procedure

1. Split the user's report into separate symptoms. Do not merge them into one vague failure.
2. Start with the symptom that your current theory explains least well.
3. List at least three possible causes, including the possibility that your own implementation or verification is wrong.
4. Reproduce under the user's state when practical:
   - existing cookies and login state
   - localStorage, sessionStorage, IndexedDB, cache, and service worker
   - relevant environment variables, data rows, feature flags, tenant, role, or region
   - the same browser, device class, account, or deployment target
5. Prefer one cause that explains all symptoms. If the cause explains only part of the report, keep investigating.
6. When presenting evidence, state both what it proves and what it does not prove.
7. Leave a user-checkable artifact when possible, such as a version endpoint, screen URL, visible marker, log excerpt, or exact reproduction path.

## Common Trap

Server-side evidence often proves only that new bytes exist somewhere. It does not prove that the user's browser, session, cache, tenant, role, region, or persisted local state is using those bytes.
