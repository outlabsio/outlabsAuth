# Maintainer Release Guide

This repository now publishes `outlabs-auth` as a public alpha package on PyPI.

## One-Time PyPI Setup

1. Create or claim the `outlabs-auth` project on PyPI.
2. In PyPI, configure a trusted publisher for:
   - owner: `outlabsio`
   - repository: `outlabsAuth`
   - workflow: `publish-pypi.yml`
   - environment: `pypi`
3. In GitHub repository settings, create the `pypi` environment used by the publish workflow.

Trusted publishing is the default path. No long-lived PyPI token is required for GitHub Actions once the publisher is configured.

## Release Checklist

1. Set the new release version:
   - `uv run python scripts/release_version.py set X.Y.ZaN`
   - Use `X.Y.Z` for stable, `X.Y.ZaN` for alpha, `X.Y.ZbN` for beta, and `X.Y.ZrcN` for release candidates.
2. Verify release metadata:
   - `uv run python scripts/release_version.py check`
3. Run packaging and bootstrap tests:
   - `uv run --extra test python -m pytest tests/unit/test_release_packaging.py tests/unit/test_bootstrap.py -q`
   - `TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth_test uv run --extra test python -m pytest tests/integration/test_packaged_cli_migrations.py -q`
4. Build distributions locally:
   - `uv build --no-sources`
5. Push the branch and wait for the `Release Readiness` workflow to pass.
6. Merge to `main`.
7. Create and push the version tag:
   - `git tag vX.Y.ZaN`
   - `git push origin vX.Y.ZaN`
8. Confirm the `Publish PyPI` workflow completes and the release appears on PyPI.

## GitHub Actions Publish Flow

The public release workflow lives in [`.github/workflows/publish-pypi.yml`](/Users/macbookm3/Documents/projects/outlabsAuth/.github/workflows/publish-pypi.yml).

- `Release Readiness` remains the branch/tag validation gate.
- `Publish PyPI` runs on `v*` tags.
- The publish job uses `pypa/gh-action-pypi-publish@release/v1` with GitHub OIDC trusted publishing.

## Local Fallback Publish

If GitHub Actions is unavailable, publish manually after building distributions:

```bash
uv build --no-sources
uvx twine upload dist/*
```

For the fallback path, create a PyPI API token on pypi.org and supply it to Twine using its standard environment variables or prompt flow.
