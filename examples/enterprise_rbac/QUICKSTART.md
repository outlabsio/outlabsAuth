# Quick Start — EnterpriseRBAC Example

Standalone consumer app that mounts OutlabsAuth EnterpriseRBAC plus a sample
leads domain.

## Run

```bash
cd examples/enterprise_rbac
uv sync

# Optional: validate a local wheel instead of the published package
# uv pip install --reinstall ../../dist/outlabs_auth-<version>-py3-none-any.whl

uv run outlabs-auth migrate
uv run python reset_test_env.py
uv run uvicorn main:app --reload --port 8004
open http://localhost:8004/docs
```

## Login

Use accounts from `reset_test_env.py`. Password for active users: `Testpass1!`

| Email | Role |
|-------|------|
| `admin@acme.com` | Superuser |
| `org-admin@acme.com` | ACME org admin |
| `agent@sf.acme.com` | SF residential agent |
| `summit-admin@summit.com` | Second-root admin |

Full persona table: [README.md § Demo Credentials](./README.md#demo-credentials).

## Try

- `GET /v1/leads` — results differ by membership scope
- `GET /v1/entities` — ACME / Summit hierarchy
- `GET /v1/entities/suggestions` — entity type suggestions
- `POST /v1/auth/login` — obtain JWT, then Authorize in Swagger

## Optional: OutlabsAuth UI

See [README.md § Connect Admin UI](./README.md#connect-admin-ui) or
[`docs/AUTH_UI.md`](../../docs/AUTH_UI.md).

## More

- Full example docs: [README.md](./README.md)
- Release smoke: `uv run python scripts/run_enterprise_example_smoke.py` (repo root)
