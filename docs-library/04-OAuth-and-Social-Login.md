# OAuth and Social Login

Add Google (or another provider) so users can sign in with an existing account.
Email/password keeps working without any of this — OAuth is opt-in by mounting
routers, not a constructor flag.

Runnable wiring: `examples/enterprise_rbac/main.py` (Google invite-only +
associate). Deeper design notes for maintainers:
[`docs/AUTH_EXTENSIONS.md`](../docs/AUTH_EXTENSIONS.md).

## How it fits

- Local `User` rows stay the account of record
- Each linked provider is a `SocialAccount` row (`user_id`, `provider`,
  `provider_user_id`, …)
- Users can link several providers; unlinking is a row delete

## Enable and mount

OAuth is **not** a constructor flag. You mount a router per provider:

```python
from outlabs_auth.oauth.providers import get_google_client  # or GitHub / Facebook helpers
from outlabs_auth.routers import get_oauth_router, get_oauth_associate_router

google = get_google_client(
    client_id=os.environ["GOOGLE_CLIENT_ID"],
    client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
)

app.include_router(
    get_oauth_router(
        google,
        auth,
        state_secret=os.environ["SECRET_KEY"],  # or a dedicated OAuth state secret
        prefix="/v1/oauth/google",
        redirect_url="https://api.example.com/v1/oauth/google/callback",
        success_redirect_url="https://app.example.com/auth/oauth/callback",
        error_redirect_url="https://app.example.com/auth/login",
        associate_by_email=True,
        is_verified_by_default=True,
        require_existing_user=True,  # invite-only: reject unknown emails
        cookie_secure=True,
    )
)

# Optional: link an extra provider while already signed in
app.include_router(
    get_oauth_associate_router(
        google,
        auth,
        state_secret=os.environ["SECRET_KEY"],
        prefix="/v1/oauth-associate/google",
        redirect_url="https://api.example.com/v1/oauth-associate/google/callback",
        success_redirect_url="https://app.example.com/app/account",
        cookie_secure=True,
    )
)
```

Both factories are exported from `outlabs_auth.routers` since `0.1.0a25`
(the module paths `outlabs_auth.routers.oauth` and
`outlabs_auth.routers.oauth_associate` still work).

Register the callback URLs with the provider console exactly as mounted.

### Multi-frontend OAuth

When your mount serves several frontends, `/authorize` accepts a registered
frontend profile key (`?app=portal`). The signed + persisted state binds that
profile and a per-flow nonce — concurrent same-provider flows from different
frontends coexist — and the callback lands on the bound profile's registered
`oauth_success` / `oauth_error` routes. Construction-time
`success_redirect_url` / `error_redirect_url` remain the single-profile
degenerate case. See [Multi-Frontend Support](../docs/MULTI_FRONTEND_SUPPORT.md).

## Important flags

| Flag | Meaning |
|------|---------|
| `require_existing_user=True` | Invite-only OAuth; unknown emails are rejected (also forced when the host sets `enable_registration=False`) |
| `associate_by_email=True` | Link provider identity to an existing local user with the same email — only for providers whose email verification you trust |
| `is_verified_by_default` | Whether to treat the provider email as verified at link time |
| `state_secret` | Required; signs OAuth state |

## Self-service social accounts

With `get_users_router` mounted (e.g. `/v1/users`):

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/v1/users/me/social-accounts` | List linked providers |
| `DELETE` | `/v1/users/me/social-accounts/{account_id}` | Unlink (blocked if it would remove the last auth method) |

Associate flow (authenticated link) uses `get_oauth_associate_router`, not these
list/unlink routes.

When the associate router knows a landing URL (the state-bound frontend
profile's `oauth_associate_success` route, else `error_redirect_url`, else
`success_redirect_url`), the callback always returns to the SPA: success adds
`?linked=<provider>`, failure adds `?link_error=<code>&provider=<provider>` with
`code` one of `cancelled`, `provider`, `invalid_state`, `already_linked`,
`provider_conflict` or `auth`. Without any landing URL the callback keeps
answering JSON (API clients).

## Provider token storage (optional)

By default provider access/refresh tokens are **not** stored. To persist them for
calling the provider API later:

```python
auth = EnterpriseRBAC(
    ...,
    store_oauth_provider_tokens=True,
    oauth_token_encryption_key=os.environ["OAUTH_TOKEN_ENCRYPTION_KEY"],  # Fernet
)
```

Enabling storage without an encryption key fails at construction.

## Security checklist

- Prefer `require_existing_user=True` unless you intentionally allow social signup
- Only set `associate_by_email=True` when you trust provider email verification
- Use HTTPS + `cookie_secure=True` in production
- Keep `state_secret` high-entropy and stable across instances
- OutlabsAuth UI offers OAuth sign-in (`/auth/oauth/callback`) and account linking
  (under `/app/account`) when its `authUi.oauthProviders` lists the provider and the users
  and OAuth associate routers are mounted; the console and API must be same-site because
  the OAuth state cookie is `SameSite=Lax`. Customer-facing sign-in still lives in your
  product frontend

## Related

- [02-Routers-and-Prefixes.md](./02-Routers-and-Prefixes.md)
- [05-Sessions-and-Audit.md](./05-Sessions-and-Audit.md)
- [Multi-Frontend Support](../docs/MULTI_FRONTEND_SUPPORT.md)
- [`docs/AUTH_UI.md`](../docs/AUTH_UI.md)
