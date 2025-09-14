<!-- Updated to best practices on 2025-09-14. -->
# Roadmap

<!-- BEGIN GENERATED: ROADMAP:MAIN -->

This roadmap outlines where {{PROJECT_NAME}} is headed. It is a living
document; propose changes via issues or PRs.

## Vision

Simple, reliable recipient blocking for Postfix with a database-backed store
and a clean web/API interface.

## Now

- Stabilize DB2 support and startup resiliency
- Improve e2e coverage for both backends

## Next

- Authentication for the API/UI (e.g., OAuth/OIDC)
- Metrics and health endpoints for operations

## Later

- Multi-tenant support and RBAC
- Pluggable storage backends (e.g., MySQL, SQLite for dev)

## Non-Goals

- Acting as a general-purpose MTA; Postfix stays the MTA
- Managing outbound mail policies beyond recipient blocking

## Proposing Changes

Open an issue tagged `roadmap` describing the problem, proposed solution,
alternatives, and impact.

<!-- END GENERATED: ROADMAP:MAIN -->

