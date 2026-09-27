# MORTAL Service Contract

The Skill is the workflow entry. The Rust MCP service is the controlled action boundary.

## Required Service Shape

- Bind to `127.0.0.1` by default.
- Expose Streamable HTTP MCP at `/mcp`.
- Expose a non-MCP health endpoint at `/health`.
- Route tools through explicit company configuration.
- Keep arbitrary shell, SQL, deletion, remote-host, payment, and credential operations out of the MCP surface.

## Company Routing

Each company entry has:

- `id`: stable lowercase identifier.
- `name`: display name.
- `tools`: bounded tool records with purpose, adapter, and read-only flag.

Adapters are declarative. They describe an allowed implementation path; they are not executable instructions by themselves.
