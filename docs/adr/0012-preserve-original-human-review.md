# ADR 0012: Preserve original values during human review

- Status: Accepted
- Date: 2026-11-07

## Context

Reviewers must verify, correct, or reject extracted values without destroying what the
provider originally returned. Authentication is not implemented yet.

## Decision

Raw and normalized AI values are immutable after a run completes. A correction is
stored in a separate corrected-value column with its reason and timestamp. Verification
and rejection likewise record a decision and optional/required reason. Reviewed fields
cannot be reviewed a second time in Milestone 2.

Every decision creates an audit event. Reviewer remains null until real authentication
exists; the application does not invent a user identity.

## Consequences

The original output and decision trail remain inspectable. Re-review, approval chains,
and authenticated attribution are deferred.
