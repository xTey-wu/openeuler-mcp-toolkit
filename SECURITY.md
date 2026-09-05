# Security policy

## Supported version

The latest revision of the default branch is supported while the project is experimental.

## Data boundary

This server is read-only, but read access can still expose sensitive data to an MCP client or its configured model provider.

- Configure `OPENEULER_MCP_ALLOWED_ROOTS` with the smallest necessary directories.
- Never authorize directories containing secrets, private keys, browser profiles or credentials.
- Do not run the Server as root unless a controlled experiment genuinely requires it.
- Keep the stdio transport local; it does not provide remote authentication.
- The project never requires an API key and no key should be committed to this repository.
- All registered tools publish read-only/non-destructive annotations and reject unknown input fields.
- Client models must refuse delete/kill requests; the Server independently enforces safety by exposing no such capability.

## Reporting a vulnerability

Do not open a public issue containing sensitive details. Use GitHub's private security advisory feature for the repository and include the affected version, reproduction steps and expected impact.
