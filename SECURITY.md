# Security policy

AssureAI accepts security reports through the repository's private security-advisory
channel. Do not include customer documents, credentials, access tokens, or exploit data
in a public issue.

## Implemented controls

- OIDC JWT validation checks issuer, audience, signature, expiry, and subject using the
  provider JWKS. The local development adapter signs short-lived HttpOnly sessions and
  is labelled as non-production identity.
- OWNER, EDITOR, and VIEWER memberships are checked server-side before every
  project-scoped route. A valid identifier never grants cross-project access.
- Credentialed CORS uses an explicit allowlist. Request/body/header limits, fixed-window
  rate limits, safe error envelopes, request IDs, CSP, frame denial, MIME sniffing
  denial, and referrer/permissions policies are applied centrally.
- Document objects are private, generated under project/document prefixes, and never
  returned as public URLs. Azure Blob and Key Vault adapters use managed identity.
- Audit metadata excludes secrets, authorization headers, cookies, and document text.
  Metrics require a configured token and are disabled from public discovery otherwise.

## Demo limitations

The public single-VM demo may use development authentication, local private storage,
raw HTTP, container PostgreSQL/Redis, disabled malware scanning, and no OTLP exporter.
These are not claims of production OIDC, HTTPS, Azure Blob, Key Vault, managed data
services, malware scanning, high availability, dashboards, or alerting. Use the
production migration runbook before processing sensitive documents.

Rotate the session secret and all infrastructure credentials after suspected exposure.
Do not place secrets in Git, container images, frontend variables, logs, or database
configuration records.
