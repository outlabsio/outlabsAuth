# JWT Tokens

> **Handbook · Reference** — how access and refresh tokens behave.  
> Part of the [OutlabsAuth Handbook](./README.md). Mount login routes:
> [Routers & Prefixes](./02-Routers-and-Prefixes.md). Sessions:
> [Sessions & Audit](./05-Sessions-and-Audit.md).

---

## How OutlabsAuth uses JWTs

Login (and accept-invite, magic-link verify, access-code verify, …) returns two
tokens:

| Token | Typical lifetime | Role |
|-------|------------------|------|
| **Access** | ~15 minutes | `Authorization: Bearer …` on API calls |
| **Refresh** | ~30 days | Exchange for a new access token; powers session inventory when stored |

Defaults are configurable. Prefer short access tokens; revoke refresh rows (or
blacklist access JWTs with Redis) when you need immediate cut-off.

Refresh tokens must **not** be accepted as access credentials (SEC-1).

### Typical claims

**Access:** `sub` (user id), `exp`, `iat`, `type: "access"`, `aud`, `jti`  
**Refresh:** same shape with `type: "refresh"` and a longer `exp`

`aud` (audience) reduces accidental cross-app token reuse. `jti` supports
blacklist / uniqueness.

---

## Token flow

```
POST /auth/login  →  access_token + refresh_token
       │
       ▼
API calls with Bearer access_token
       │
       ▼ (near expiry)
POST /auth/refresh { refresh_token }  →  new access (+ optional rotated refresh)
       │
       ▼
POST /auth/logout  (revokes refresh when store_refresh_tokens is on)
```

Exact paths depend on your mount prefix (`/auth`, `/v1/auth`, `/iam/auth`, …).

---

## Configuration knobs

Set on the preset / `AuthConfig` (names may vary slightly by version — check
`outlabs_auth/core/config.py`):

| Setting | Typical default | Purpose |
|---------|-----------------|---------|
| `secret_key` | required | HS256 signing (≥ 32 chars) |
| `access_token_expire_minutes` | `15` | Access token TTL |
| `refresh_token_expire_days` | `30` | Refresh token TTL |
| `store_refresh_tokens` | `True` | Persist refresh rows → revoke + [sessions](./05-Sessions-and-Audit.md) |
| `enable_token_blacklist` | `False` | Immediate access-token kill switch (needs Redis) |
| `token_blacklist_failure_mode` | `fail_closed` | Behavior if blacklist Redis is down |

Production: long random `secret_key`, HTTPS, prefer httpOnly cookies for refresh
in browser apps (host-owned cookie transport).

---

## Validation and auth deps

Host routes use `auth.deps.authenticated()` / `require_permission(...)`. The
library verifies signature, `exp`, `type`, and audience, then loads the user
and applies status / lockout rules ([User Status](./48-User-Status-System.md)).

---

## Revocation

| Goal | Mechanism |
|------|-----------|
| End one device / login | Delete that refresh row (session APIs) |
| End all sessions for a user | Delete all refresh rows for the user |
| Kill a still-valid access JWT early | Redis blacklist (`enable_token_blacklist`) |
| Password change / suspend / ban | Revoke refresh tokens in the same flow |

Without blacklist, access tokens remain valid until `exp`.

---

## Custom claims

Prefer putting product claims in **your** tokens or session store. If you extend
OutlabsAuth JWT payloads, keep `sub` / `type` / `aud` / `jti` intact and
document any audience changes for every consumer.

---

## Related

- [Sessions & Audit](./05-Sessions-and-Audit.md)
- [Configuration](./03-Configuration.md)
- [User Status](./48-User-Status-System.md)
- [Getting Started](./01-Getting-Started.md)
