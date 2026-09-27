# MORTAL MCP

Read `.agents/skills/mortal-mcp/SKILL.md` before operating tools.
Use Traditional Chinese for user reports. Keep this service local to 127.0.0.1.
Adapters call existing project scripts; never duplicate business or ledger logic.
No arbitrary shell, SQL, file deletion or remote-host tool. Fixed commands only.
Mutations share a host lock, are bounded, and leave evidence. No automatic retries.
Do not change or restart game processes as part of MCP deployment or smoke testing.
