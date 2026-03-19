# User Audit Log Strategy

**Date**: 2026-03-18
**Last Updated**: 2026-03-19
**Status**: Implemented current-state guidance
**Owners**: API team

## Purpose

This document describes the current user-centric history contract in the
runtime.

The default admin history experience is built around:

- durable, queryable `user_audit_events`
- append-only `entity_membership_history`
- security telemetry in `login_history`

It is not built around a generic `audit_service`, and it is not primarily
gated by `enable_audit_log`.

## Current History Surfaces

### `user_audit_events`

Primary user-centric lifecycle timeline.

Current event families include:

- profile updates
- email changes
- password changes
- status changes
- retained delete and restore
- invite create, resend, and accept
- direct-role assignment and revocation
- successful login and failed login
- password reset request and completion
- mirrored entity membership lifecycle events

### `entity_membership_history`

Append-only membership lifecycle history for entity access.

Current event families include:

- created
- updated
- suspended
- reactivated
- revoked
- entity_archived

### `login_history`

Authentication-attempt telemetry and security metadata. This is useful for
security analysis, but it is not the primary admin-facing history model.

### `user_activities` / `activity_metrics`

Analytics-oriented activity rollups. These are not a durable audit surface.

## Timeline Scope

The default user-history timeline intentionally includes high-signal lifecycle
events and excludes noisy session internals.

Included:

- lifecycle and identity changes
- access-grant changes
- authentication success/failure
- password and invite recovery flows

Intentionally excluded from the default timeline:

- logout events
- token refresh events
- per-request keepalive/session-noise events

If a raw session timeline is needed later, it should be added as a separate
view instead of polluting the default admin history surface.

## Event Envelope

Current `user_audit_events` columns:

- `id`
- `occurred_at`
- `event_category`
- `event_type`
- `event_source`
- `actor_user_id`
- `subject_user_id`
- `subject_email_snapshot`
- `root_entity_id`
- `entity_id`
- `role_id`
- `request_id`
- `ip_address`
- `user_agent`
- `reason`
- `before`
- `after`
- `metadata`

Current categories:

- `profile`
- `credential`
- `status`
- `membership`
- `role`
- `invitation`
- `authentication`

Rendering contract:

- history is snapshot-first
- `before`/`after` must remain readable without requiring a live join
- optional live links are a convenience, not a rendering dependency

## Service Ownership

Durable audit writes originate in domain services, not routers.

Current ownership boundaries:

- `UserService`: profile/email/password/status/delete/restore/invite lifecycle
- `AuthService`: login, password reset, invite acceptance, token issuance for non-password auth flows
- `MembershipService`: membership history plus mirrored membership audit events
- `RoleService`: direct-role lifecycle events

Routers may pass actor/request metadata, but they should stay thin and should
not become the source of audit semantics.

## User Deletion Contract

User deletion is retained delete in the current runtime:

- set `status = deleted`
- populate `deleted_at`
- revoke active entity memberships
- revoke exceptional direct roles
- revoke refresh tokens in place
- revoke user-owned API keys in place
- keep the user row for continuity of identity and history

Additional rules:

- deleted users cannot authenticate
- deleted-user emails remain reserved for create and invite flows
- restore is identity-only
- restore does not automatically restore memberships, direct roles, refresh
  tokens, or API keys

Hard purge is intentionally separate from the default admin delete flow.

## API Surfaces

Current admin-facing read surfaces:

- `GET /v1/users/{user_id}/audit-events`
- `GET /v1/users/{user_id}/membership-history`

These endpoints provide pagination and filtering without requiring callers to
query internal tables directly.

## Operational Guidance

Current documentation and implementation should assume:

- core lifecycle history is part of the product contract
- `user_audit_events` and `entity_membership_history` are the primary history
  stores
- `enable_audit_log` is not the switch that enables current admin history
- a generic `auth.audit_service` is not part of the live runtime contract

If a broader facade is introduced later, it should compose explicit services
instead of hiding them behind a catch-all subsystem.

## Remaining Follow-Up

The main remaining work around user-centric history is expansion of product
scope, not basic audit infrastructure. The current notable follow-ups are:

- deciding whether a separate raw session/security-history view is needed
- deciding whether future compliance/export requirements need a composed facade
  over the existing explicit history services
- revisiting retention-sensitive FK strategy if hard purge is introduced later
