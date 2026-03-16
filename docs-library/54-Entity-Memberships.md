# 54. Entity Memberships

This document describes how EnterpriseRBAC models entity memberships, how lifecycle state affects access, and which API endpoints manage that state.

## Overview

An entity membership connects:

- one user
- one entity
- zero or more scoped roles

Memberships are the primary way EnterpriseRBAC grants entity-scoped access. A user can belong to multiple entities, and each membership can have its own lifecycle window and status.

## Lifecycle Model

Each membership stores:

- `status`
- `valid_from`
- `valid_until`
- `joined_at`
- `joined_by_id`
- `revoked_at`
- `revoked_by_id`
- `revocation_reason`

### Status Semantics

Memberships use the shared `MembershipStatus` enum:

- `active`: membership may grant permissions if it is inside its validity window
- `suspended`: membership is preserved but does not grant permissions
- `revoked`: membership was removed and does not grant permissions
- `expired`: computed effective state when `valid_until` has passed
- `pending`: computed effective state when `valid_from` is in the future
- `rejected`: reserved for future approval flows

Important distinction:

- `status` is the stored lifecycle state
- `effective_status` is the runtime state after validity windows are applied

Example:

- stored `status=active`
- `valid_until` is yesterday
- runtime `effective_status=expired`

## API Endpoints

Base path: `/v1/memberships`

### Get Current User Memberships

`GET /v1/memberships/me`

Query params:

- `include_inactive=false` by default

Returns the authenticated user's memberships for context switching and UI state.

### Add Member

`POST /v1/memberships/`

Required permission:

- `membership:create` or tree-equivalent enforcement through entity context

Request body:

```json
{
  "user_id": "uuid",
  "entity_id": "uuid",
  "role_ids": ["uuid"],
  "status": "active",
  "valid_from": "2026-03-16T09:00:00Z",
  "valid_until": "2026-03-23T09:00:00Z",
  "reason": "Optional lifecycle note"
}
```

Notes:

- create supports `active` and `suspended`
- `valid_from` and `valid_until` are optional
- roles are validated against the entity context before assignment

### Get Entity Members

`GET /v1/memberships/entity/{entity_id}`

Query params:

- `page`
- `limit`
- `include_inactive=false`

Returns memberships for one entity.

### Get Entity Members With User Details

`GET /v1/memberships/entity/{entity_id}/details`

Query params:

- `page`
- `limit`
- `include_inactive=false`

Returns memberships plus user summaries, role summaries, and lifecycle fields.

### Get User Memberships

`GET /v1/memberships/user/{user_id}`

Query params:

- `page`
- `limit`
- `include_inactive=false`

This is the main endpoint for user detail screens and access reviews.

### Update Member Access

`PATCH /v1/memberships/{entity_id}/{user_id}`

Required permission:

- `membership:update` or tree-equivalent enforcement through entity context

Request body fields are all optional. The endpoint updates only fields that are present.

```json
{
  "role_ids": ["uuid", "uuid"],
  "status": "suspended",
  "valid_from": "2026-03-16T09:00:00Z",
  "valid_until": "2026-03-30T12:00:00Z",
  "reason": "Temporary leave"
}
```

Supported state changes:

- replace the role set
- suspend a membership
- reactivate a suspended or revoked membership
- set or clear validity windows
- update the lifecycle reason

Notes:

- PATCH supports `active` and `suspended`
- use `DELETE` to revoke a membership
- sending `null` clears optional fields like `valid_until` or `reason`

### Remove Member

`DELETE /v1/memberships/{entity_id}/{user_id}`

Required permission:

- `membership:delete` or tree-equivalent enforcement through entity context

This is a soft revoke:

- stored `status` becomes `revoked`
- `revoked_at` is set
- `revoked_by_id` is recorded when available
- audit history is preserved

Use `PATCH` with `status=active` to reactivate the membership later if needed.

## Response Shape

Membership endpoints return lifecycle-aware responses:

```json
{
  "id": "uuid",
  "entity_id": "uuid",
  "user_id": "uuid",
  "role_ids": ["uuid"],
  "status": "active",
  "effective_status": "expired",
  "joined_at": "2026-03-16T09:00:00Z",
  "joined_by_id": "uuid",
  "valid_from": "2026-03-16T09:00:00Z",
  "valid_until": "2026-03-23T09:00:00Z",
  "revoked_at": null,
  "revoked_by_id": null,
  "revocation_reason": null,
  "is_currently_valid": false,
  "can_grant_permissions": false
}
```

## Permission Resolution

A membership grants permissions only when both conditions are true:

- `status == active`
- the current time is inside the validity window

That means:

- suspended memberships never grant permissions
- revoked memberships never grant permissions
- active memberships outside their time window also do not grant permissions

## Current Limitation

Membership-level timing is supported.

Per-role timing inside a membership is not currently supported. Scoped roles inside one membership share the same membership lifecycle window.

## Testing Status

Current automated coverage for this lifecycle contract exists in:

- `tests/integration/test_membership_lifecycle_api.py`

That coverage verifies:

- create with lifecycle fields
- update with lifecycle fields and multiple roles
- inactive membership filtering
- soft revoke plus reactivation

Important note:

- this is still feature-focused coverage, not the full admin user-details contract exercised end-to-end with the adjacent user-management routes
- comprehensive cross-surface integration coverage should still be added in the future for:
  - user detail reads
  - direct role memberships
  - membership lifecycle updates from the same record page flow
