# Private Release Workflow

This package is intended for private distribution across internal projects.

## Release Checklist

1. Set the new release version:
   - `uv run python scripts/release_version.py set X.Y.ZaN`
   - Use `X.Y.Z` for a stable release, `X.Y.ZaN` for alpha, `X.Y.ZbN` for beta, and `X.Y.ZrcN` for release candidates.
2. Run the release validation commands locally:
   - `uv run python scripts/release_version.py check`
   - `uv run --extra test python -m pytest tests/unit/test_release_packaging.py -q`
   - `uv build --no-sources`
   - `cd auth-ui && bun ci && bun run build`
3. Push the branch and wait for the `Release Readiness` GitHub Actions workflow to pass.
4. Verify the wheel contains:
   - `outlabs_auth/alembic.ini`
   - `outlabs_auth/migrations/`
5. Tag the release:
   - `git tag vX.Y.ZaN`
   - `git push origin vX.Y.ZaN`

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
