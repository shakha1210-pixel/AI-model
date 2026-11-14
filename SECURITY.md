# Security Policy

Apeiron handles user-supplied AI provider credentials and may execute agent
operations in future releases. Security issues should be reported privately.

## Reporting a vulnerability

Use GitHub's **Report a vulnerability** feature on this repository, if
available, to contact maintainers privately. Include affected commits, impact,
reproduction steps, and suggested mitigation.

Never include real API keys, passwords, personal data, or production secrets in
public issues, screenshots, or logs. Revoke and rotate any credential that may
have been exposed.

## Credential handling

- Provider API keys are write-only and encrypted at rest with
  `PROVIDER_CREDENTIALS_ENCRYPTION_KEY` using Fernet.
- Keep the encryption key outside source control and back it up securely.
  Losing the key makes stored provider credentials unrecoverable.
- Do not place provider keys in browser storage, frontend bundles, logs, or
  API responses.
- Every provider connection is scoped to its authenticated owner.
- The connection test endpoint performs a short model request and may incur
  provider usage charges.

## Custom provider endpoints

- Custom endpoints must use HTTPS and must not contain URL credentials,
  query strings, or fragments.
- Local, private, loopback, link-local, reserved, and metadata-service
  destinations are rejected after DNS resolution.
- DNS can change between validation and connection. Production deployments
  must also enforce outbound network/egress restrictions; application-level
  URL validation alone is not a complete DNS-rebinding defense.

## Agent execution

Agent tools and generated code must not run with unrestricted host access.
Production execution requires a real isolated sandbox with resource and
network limits, plus explicit permission checks and approval for side effects.
