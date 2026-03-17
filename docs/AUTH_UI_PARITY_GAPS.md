# Auth UI Parity Gaps

This document tracks the remaining known gaps between the agnostic OutlabsAuth admin UI in `auth-ui/` and the backend contract exposed by `outlabs_auth`.

## Current Status

The following surfaces were verified and brought into backend parity in the March 13, 2026 pass:

- Users CRUD and detail views
- Roles CRUD and permission assignment
- Permissions CRUD
- Entities and memberships
- API keys, including rotation
- User settings/profile/security surfaces
- Dashboard summary signals
- ABAC condition-group and condition management for roles and permissions

Supporting verification:

- `uv run pytest tests/unit/test_auth_ui_contract.py -q`
- `uv run pytest tests/integration/test_abac_endpoints.py -q`
- `cd auth-ui && bun run build`

Recent backend additions that now support the frontend user-details surface:

- membership lifecycle fields and lifecycle-aware update/remove flows under `/v1/memberships/...`
- direct account role membership metadata via `GET /v1/users/{id}/role-memberships`

Coverage note:

- targeted regression coverage exists for these additions in:
  - `tests/integration/test_membership_lifecycle_api.py`
  - `tests/integration/test_role_assignment.py` (`role-memberships` cases)
- comprehensive admin user-details contract coverage now exists in:
  - `tests/integration/test_admin_user_details_contract.py`

That suite covers the full record-page lifecycle together:

- profile update
- status change and suspension window handling
- resend invite
- admin password reset
- delete user
- direct role assign/read/revoke with lifecycle metadata
- entity membership create/update/remove/reactivate with lifecycle windows

Until that broader suite exists, treat this surface as implemented but not fully hardened by comprehensive integration coverage.

## Remaining Gap

### OAuth and Social Account Parity

This is the only remaining functional parity gap identified in the current pass.

#### What exists in the backend

The backend already supports provider-specific OAuth login and authenticated account-linking flows:

- `outlabs_auth/routers/oauth.py`
- `outlabs_auth/routers/oauth_associate.py`

#### What is still missing for the agnostic UI

The UI cannot safely render OAuth/social login or linked-account management yet because it lacks a stable runtime discovery contract.

Current blockers:

- `GET /auth/config` only reports preset, feature flags, and available permissions.
- There is no backend endpoint that tells the UI which OAuth providers are actually configured for the current host app.
- There is no backend endpoint for listing the current user's linked social accounts.
- There is no backend endpoint for unlinking a linked social account.

Because of that, the UI intentionally does not yet expose:

- provider login buttons on the login screen
- provider-linking controls in settings/security
- linked social account status cards
- unlink/revoke provider actions

## Recommended Backend Contract

To close the remaining parity gap cleanly, add library-level runtime endpoints instead of host-specific UI workarounds.

Recommended additions:

1. Add provider discovery to `GET /auth/config` or a dedicated `GET /auth/providers` endpoint.
2. Return only providers that are actually mounted/configured by the host application.
3. Include enough metadata for an agnostic UI to render buttons and initiate flows.
4. Add `GET /users/me/social-accounts` to list linked providers for the current user.
5. Add `DELETE /users/me/social-accounts/{provider}` to unlink a provider from the current user.

Minimum provider discovery payload:

```json
{
  "providers": [
    {
      "name": "google",
      "display_name": "Google",
      "login_path": "/auth/google/authorize",
      "associate_path": "/auth/google/authorize",
      "enabled": true
    }
  ]
}
```

The exact shape can change, but the key requirement is that the UI must not infer configured providers from docs, environment variables, or hardcoded assumptions.

## Non-Gaps

These came up during the audit but are not remaining parity gaps:

- The dashboard no longer shows a fake recent-activity feed. It now renders real user/config-backed signals because the backend does not expose an activity feed endpoint.
- The ABAC editor no longer requires a frontend workaround for ungrouping. The backend now accepts explicit `null` updates for `condition_group_id` and descriptions.
- The settings pages no longer expose fake 2FA, session management, or destructive account controls that the backend does not support.

## Next Step

The next parity task should start in the library, not the UI:

1. Add OAuth provider discovery and social-account management endpoints.
2. Extend the auth config/types to expose that contract.
3. Wire the login and settings/security UI to those endpoints.
4. Add parity regression tests covering provider discovery and linked-account rendering.
