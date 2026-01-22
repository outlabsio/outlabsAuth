# Repository Guidelines

## Project Structure & Module Organization
- `outlabs_auth/`: core library code (services, routers, models, schemas, auth, middleware).
- `outlabs_auth/migrations/`: Alembic migrations for SQL schema changes.
- `tests/`: unit and integration tests; see `tests/README.md` for workflows.
- `auth-ui/`: Nuxt-based admin UI (Bun toolchain).
- `examples/` and `scripts/`: runnable demos and smoke scripts.
- `observability/` and `docker-compose.yml`: metrics/logging stack and local dependencies.
- `docs/` and `docs-library/`: design docs, guides, and API references.

## Build, Test, and Development Commands
- `uv run start.py`: interactive launcher for API/UI/observability services.
- `uv run uvicorn main:app --reload`: run the API server locally.
- `uv run pytest`: run the full test suite.
- `uv run pytest tests/unit/`: unit tests only.
- `uv run pytest tests/integration/`: integration tests (often require DB/Redis).
- `cd auth-ui && bun install && bun run dev`: run the admin UI.
- `cd auth-ui && bun run build`: build the admin UI.
- `docker compose up -d`: start local dependencies (Postgres/Redis/observability stack).

## Coding Style & Naming Conventions
- Python: 4-space indentation, type hints preferred; format with `black` and sort imports with `isort`.
- Static checks: `flake8` and `mypy` are configured in `pyproject.toml`.
- Tests: files named `test_*.py`, pytest markers like `@pytest.mark.unit` and `@pytest.mark.integration` are used.
- Frontend: keep existing Nuxt/TypeScript patterns; follow file-local conventions.

## Testing Guidelines
- Frameworks: `pytest` + `pytest-asyncio`.
- Prefer `uv run pytest ...` so Python 3.12+ matches `pyproject.toml`.
- Use focused runs during development, e.g. `uv run pytest tests/unit/services/test_permission_scope.py`.

## Commit & Pull Request Guidelines
- Commit style in history uses short, imperative summaries (e.g., “Fix…”, “Update…”).
- PRs should include a clear description, test evidence, and screenshots for UI changes (see `auth-ui/`).

## Security & Configuration Tips
- Configure secrets and DB URLs via environment variables; see `auth-ui/.env.example` and docs.
- When adding permissions/roles, keep names in `resource:action` format.
