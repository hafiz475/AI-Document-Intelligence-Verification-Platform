# ADR 0033: OpenTelemetry and protected metrics

Propagate W3C trace context from API through Dramatiq and instrument bounded operations.
Expose low-cardinality Prometheus metrics only behind a configured token/network
boundary; OTLP export is optional and no dashboard is claimed by default.
