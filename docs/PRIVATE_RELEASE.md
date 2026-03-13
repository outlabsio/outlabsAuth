# Private Release Workflow

This package is intended for private distribution across internal projects.

## Release Checklist

1. Set the new release version:
   - `uv run python scripts/release_version.py set X.Y.ZaN`
   - Use `X.Y.Z` for a stable release, `X.Y.ZaN` for alpha, `X.Y.ZbN` for beta, and `X.Y.ZrcN` for release candidates.
2. Run the release validation commands locally:
   - `uv run python scripts/release_version.py check`
   - `uv run --extra test python -m pytest tests/unit/test_release_packaging.py tests/unit/test_bootstrap.py -q`
   - `TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth_test uv run --extra test python -m pytest tests/integration/test_packaged_cli_migrations.py -q`
   - `uv build --no-sources`
   - `cd auth-ui && bun ci && bun run build`
3. Push the branch and wait for the `Release Readiness` GitHub Actions workflow to pass.
4. Verify the wheel contains:
   - `outlabs_auth/alembic.ini`
   - `outlabs_auth/migrations/`
5. Validate the packaged bootstrap flow explicitly:
   - `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth_test OUTLABS_AUTH_SCHEMA=release_smoke uv run python -m outlabs_auth.cli migrate`
   - `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth_test OUTLABS_AUTH_SCHEMA=release_smoke uv run python -m outlabs_auth.cli seed-system`
   - `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth_test OUTLABS_AUTH_SCHEMA=release_smoke uv run python -m outlabs_auth.cli bootstrap-admin --email admin@example.com --password 'ChangeMe123!'`
6. Tag the release:
   - `git tag vX.Y.ZaN`
   - `git push origin vX.Y.ZaN`

## Library-Owned Schema Lifecycle

OutlabsAuth owns its schema lifecycle. Host applications should not vendor or merge
the auth migrations into their own Alembic history.

Use this sequence for a fresh install in a consuming application:

1. `migrate`
   - Applies the auth schema migrations into `OUTLABS_AUTH_SCHEMA` and records state in `outlabs_auth_alembic_version`.
2. `seed-system`
   - Seeds the library-owned permission catalog and default system config records.
3. `bootstrap-admin`
   - Creates the first superuser exactly once; rerunning with the same email is idempotent.

Environment variables:

- `DATABASE_URL`: target PostgreSQL database URL
- `OUTLABS_AUTH_SCHEMA`: optional schema name for auth tables; defaults to `public` when unset
- `OUTLABS_AUTH_BOOTSTRAP_EMAIL`: optional default email for `bootstrap-admin`
- `OUTLABS_AUTH_BOOTSTRAP_PASSWORD`: optional default password for `bootstrap-admin`

The bundled `outlabs_auth/alembic.ini` intentionally ships with a placeholder URL.
Installed consumers must provide `DATABASE_URL`; there is no real fallback database target.

## Publish To A Private Index

Add the private index to `pyproject.toml` in consuming projects:

```toml
[project]
dependencies = ["outlabs-auth>=X.Y.ZaN,<X.(Y+1)"]  # Example: >=0.1.0a1,<0.2

[tool.uv.sources]
outlabs-auth = { index = "outlabs-private" }

[[tool.uv.index]]
name = "outlabs-private"
url = "https://<your-registry>/simple/"
publish-url = "https://<your-registry>/"
explicit = true
```

Authenticate and publish:

```bash
uv auth login <your-registry-host>
uv build --no-sources
uv publish --index outlabs-private
```

## Consume Via Private Git

If you are not ready to operate a private index yet, pin a Git tag instead:

```toml
[project]
dependencies = ["outlabs-auth"]

[tool.uv.sources]
outlabs-auth = { git = "ssh://git@github.com/<org>/outlabsAuth.git", tag = "vX.Y.ZaN" }
```

This is acceptable for the first few projects, but a private index is the better
long-term option because it decouples installability from Git checkout shape and
gives you conventional version resolution.
