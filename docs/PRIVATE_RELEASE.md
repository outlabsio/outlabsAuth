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

1. Make sure `CHANGELOG.md` has an `## [Unreleased]` section covering everything since the last
   release. It must include a **Database migrations** subsection: list any new Alembic revisions and
   how they are applied (`auto_migrate=True` or `outlabs-auth bootstrap`), or state "None"; spell out
   operational upgrade steps (new config flags, required role grants, breaking behavior). The release
   gate fails if the released version has no `CHANGELOG.md` section.
2. Set the new release version:
   - `uv run python scripts/release_version.py set X.Y.ZaN`
   - Use `X.Y.Z` for stable, `X.Y.ZaN` for alpha, `X.Y.ZbN` for beta, and `X.Y.ZrcN` for release candidates.
   - This also promotes `## [Unreleased]` to `## [X.Y.ZaN] - <today>` in `CHANGELOG.md`.
3. Verify release metadata:
   - `uv run python scripts/release_version.py check`
4. Run packaging and bootstrap tests:
   - `uv run --extra test python -m pytest tests/unit/test_release_packaging.py tests/unit/test_bootstrap.py -q`
   - `TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/outlabs_auth_test uv run --extra test python -m pytest tests/integration/test_packaged_cli_migrations.py -q`
5. Run the full test suite and the API integration suite (see
   [API Integration Validation](#api-integration-validation) below). The
   `Release Readiness` workflow runs both automatically (`full-suite` and
   `api-integration` jobs with ephemeral Postgres + Redis services) on every
   PR and on `main`/tags — run locally to iterate faster than CI:
   - `TEST_REDIS_URL=redis://localhost:56379/15 uv run pytest -q`
   - `uv run python scripts/run_enterprise_example_smoke.py`
6. If the release contains new Alembic revisions, wait for the required
   [`seeded-upgrade-rehearsal`](#database-upgrade-rehearsal) CI job. It
   reconstructs the preceding release's schema shape in a disposable Postgres
   container, seeds affected auth records, upgrades to the current head, checks
   the transformed data and schema, then verifies a second upgrade is a no-op.
   This is the standard release rehearsal; it does not require a consumer
   application's database or credentials.
7. Build distributions locally:
   - `uv build --no-sources`
8. Push the branch and wait for the `Release Readiness` workflow to pass.
9. Merge to `main`.
10. Create and push the version tag:
    - `git tag vX.Y.ZaN`
    - `git push origin vX.Y.ZaN`
11. Confirm the `Publish PyPI` workflow completes and the release appears on PyPI.

## API Integration Validation

The unit/integration pytest suite exercises services in-process. The API
integration suite drives the **running** EnterpriseRBAC example over HTTP
against seeded multi-root scenario data, asserting the behavior an operator
cares about before shipping.

One command does everything (seed → boot uvicorn → admin/ABAC smoke →
45-check assertion suite → teardown; non-zero exit on any failure):

```bash
uv run python scripts/run_enterprise_example_smoke.py
# Environment (optional): DATABASE_URL, REDIS_URL, SECRET_KEY, HOST, PORT
```

It runs two layers, which can also be run individually against an
already-running instance (including a staging host):

- `scripts/smoke_enterprise_api.py` — admin + ABAC flow runner: entity
  create/move/archive as admin, plus a role-level ABAC condition created via
  the API and verified to allow/deny two holders of the same role.
- `examples/enterprise_rbac/api_integration_check.py [--base-url ...]` — the
  assertion suite (45 checks): persona logins across two org roots,
  entity-scoped grants, sibling-team / cross-root isolation via a
  membership-only user, **tree-permission inheritance** down the hierarchy
  (and non-leakage to sibling branches), cache-served verdict stability with
  latencies, and the **next-request visibility arcs** — role grant/revoke,
  role-permission add/remove, membership suspend/reactivate, entity archive,
  API-key revoke, and refresh-token logout must all take effect on the very
  next request even with Redis caching enabled.

Both layers create only throwaway data (unique-suffixed users, roles, leads,
one archived entity) on top of the seed; `reset_test_env.py` restores the
known state. Gotchas encoded in the scripts so they aren't relearned:
everything must run with `--project <repo root>` so the *current* library is
exercised (the example's own `.venv` may pin an older build), seeded
credentials are `Testpass1!`, the seeded `agent` role is a protected system
role (don't mutate shared seed data — create throwaway roles), and
`sf_residential` auto-assigns a default role to new members (use
`sf_commercial` when a membership must grant *only* what the test attaches).

## Database Upgrade Rehearsal

For releases that ship Alembic revisions, the `seeded-upgrade-rehearsal` CI job
is required. It uses the repository's disposable Postgres container and does
the following:

- creates the preceding release's schema shape;
- inserts affected user, refresh-token, and API-key rows;
- upgrades through the new revisions and verifies row counts, refresh-token
  family backfill, indexes, and the new receipt table; and
- reruns the upgrade to prove idempotency.

The `api-integration` and `simple-example-integration` jobs separately seed,
start, and exercise the EnterpriseRBAC and SimpleRBAC FastAPI examples over
HTTP. A consuming application may still choose to rehearse its own deployment,
but it is not a prerequisite for publishing this library release.

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
