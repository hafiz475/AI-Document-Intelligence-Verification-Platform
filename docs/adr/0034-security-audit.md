# ADR 0034: Actor-aware audit metadata

Extend immutable project audit events with actor, target, request, and trace identifiers.
Record safe administrative/workflow metadata only; never document text, credentials,
cookies, tokens, or provider internals.
