# Repository Guidelines

## Project Structure & Module Organization
- `outlabs_auth/`: core library code (services, routers, models, schemas, auth, middleware).
- `outlabs_auth/migrations/`: Alembic migrations for SQL schema changes.
- `tests/`: unit and integration tests; see `tests/README.md` for workflows.
- Admin UI now lives in the sibling repository `../OutlabsAuthUI`.
- `examples/` and `scripts/`: runnable demos and smoke scripts.
- `observability/` and `docker-compose.yml`: metrics/logging stack and local dependencies.
- `docs/`: maintainer design specs, audits, release process
- `docs-library/`: implementer handbook (user-facing guides; future docs-site source)

## Build, Test, and Development Commands
- `uv run start.py`: interactive launcher for API/observability services.
- `uv run uvicorn main:app --reload`: run the API server locally.
- `uv run pytest`: run the full test suite.
- `uv run pytest tests/unit/`: unit tests only.
- `uv run pytest tests/integration/`: integration tests (often require DB/Redis).
- `uv run ruff check .`: run lint checks.
- `uv run black --check .`: verify formatting.
- `cd ../OutlabsAuthUI && bun install && cp public/app-config.template.json public/app-config.json && bun run dev`: run the external admin console (Nuxt) on `http://localhost:3000`; the template targets the EnterpriseRBAC example on `:8004`.
- `cd ../OutlabsAuthUI && bun run generate`: build the console's static artifact (`.output/public`). Its release gate is `bun run release:check --enterprise http://localhost:8004 --simple http://localhost:8003`, run against this repo's seeded examples.
- `docker compose up -d`: start local dependencies (Postgres/Redis/observability stack).

## Coding Style & Naming Conventions
- Python: 4-space indentation, type hints preferred; format with `black`.
- Static checks: `ruff` and `mypy` are configured in `pyproject.toml`.
- Tests: files named `test_*.py`, pytest markers like `@pytest.mark.unit` and `@pytest.mark.integration` are used.
- Frontend: admin UI lives in sibling `../OutlabsAuthUI` (Nuxt 4 + Nuxt UI 4, Vue/TypeScript, Pinia + Pinia Colada, Zod; Playwright E2E is its acceptance gate); follow that repo’s `AGENTS.md`.

## Testing Guidelines
- Frameworks: `pytest` + `pytest-asyncio`.
- Prefer `uv run pytest ...` so Python 3.12+ matches `pyproject.toml`.
- Use focused runs during development, e.g. `uv run pytest tests/unit/services/test_permission_scope.py`.

## Commit & Pull Request Guidelines
- Commit style in history uses short, imperative summaries (e.g., “Fix…”, “Update…”).
- PRs should include a clear description and test evidence. UI changes belong in `../OutlabsAuthUI` and ship there with a Playwright spec; backend changes that alter routes, schemas or example seeds should note the console impact.

## Security & Configuration Tips
- The console holds no secrets or database URLs: it reads a public runtime `app-config.json` (untracked `public/app-config.json` in development, staged per deployment by its deploy preflight; `NUXT_PUBLIC_*` env is honoured only by `bun run dev`). Only its deploy credentials (`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`) live in its untracked `.env.deploy`.
- When adding permissions/roles, keep names in `resource:action` format.
