# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project is in alpha (pre-1.0); breaking changes are allowed between alpha releases.

## [Unreleased]

### Added

- **`outlabs-auth doctor` — read-only preflight diagnostics.** New CLI command that runs five safe, read-only checks against the target database and schema: connectivity, target schema existence, Alembic version table presence, revision matches the packaged head, and core auth tables present. Supports `--format text` (default, with `[OK]` / `[FAIL]` / `[--]` markers and `->` remediation hints) and `--format json` (machine-readable payload with `healthy`, `schema`, and a `checks[]` array). Exit codes: `0` healthy, `1` one or more checks failed, `2` `DATABASE_URL` not set. Short-circuits cleanly on prerequisite failures (skipped checks are reported, not silently dropped) and redacts passwords from any URL printed to stdout or embedded in JSON output. Covered by 18 new tests in `tests/unit/test_cli_doctor.py`, wired into the release-gate workflow.

## [0.1.0a18] - 2026-04-22

Async/perf pass across the auth data plane. Full test suite (745 tests) green.

### Performance

- **Login: Argon2id offload + flush batching.** `login` now runs Argon2id verify (~20 ms per call) on `asyncio.to_thread` and batches the last-login flush into the commit. Login p95 under concurrent load dropped roughly 40x on the local baseline. Argon2 parameters retuned to OWASP 2023 minimums.
- **`AccessScopeService.resolve_for_user`: 3 queries → 1.** Root, direct-membership, and closure-table lookups collapsed into a single CTE + LEFT JOIN via `_resolve_user_scope_inputs`. Saves 1 round trip on the hydrated-user path, 2 when `user=None`.
- **API-key `_check_ip`: 2 queries → 1.** `COUNT` + `SELECT` pair replaced with a single `SELECT ip_address`. Empty list → allow-all; otherwise membership is checked in memory.
- **Policy engine `matches` operator: compiled regex cache.** ABAC `matches` conditions now go through `functools.lru_cache(maxsize=1024)` via a module-level `_compile_regex` helper. Invalid patterns still fail closed.
- **Snapshot auth check: `asyncio.gather` for multi-permission routes.** `_try_api_key_auth_snapshot` parallelizes when a route declares multiple required permissions. Safe because the path is pure CPU + Redis — no `AsyncSession` work.

### Fixed

- **Fire-and-forget background tasks now have an error path.** `ActivityTracker.track_activity_detached()` and `NotificationService.emit()` retain their `asyncio.create_task` handles in an instance-level set and attach a `done_callback` that logs exceptions structurally. Callers in `services/auth.py` and `dependencies/__init__.py` use the detached helper so no background task escapes observability.
- Simple example contract: dropped a stale `integration_principals` assertion that fired after the fixture stopped seeding them.

### Intentionally reverted after measurement

Three thread-offload refactors were implemented, measured, and reverted in this pass because `asyncio.to_thread` has ~35 μs of scheduling overhead and the target ops cost well under that threshold:

- Fernet encrypt/decrypt for OAuth token encryption (~8–12 μs sync).
- API-key SHA-256 hash on the verify path (~0.4 μs sync).
- JWT HS256 encode/decode in service tokens and `utils/jwt.py` (~13 μs / ~19 μs sync).

See [docs/NEXT_PASS_BACKLOG.md](docs/NEXT_PASS_BACKLOG.md) → "Measurement rule" for the cost table and the rule of thumb: **only offload sync CPU when the op costs >> 100 μs.**

## [0.1.0a17] - 2026-04-21

Route-level perf slice (2026-04-12 pass). See [docs/NEXT_PASS_BACKLOG.md](docs/NEXT_PASS_BACKLOG.md) → "Release-Ready Auth Perf Slice" for the full list. High-level wins:

- `/v1/users/me`: 2 queries → 1 (`root_entity` eager-loaded on JWT-authenticated user resolution).
- `/v1/roles/entity/{entity_id}`: entity type + ancestor chain resolved in a single query.
- Lean permission-resolution path for the common non-ABAC, non-context-aware-role case: `check_permission(...)` 14 → 8 queries, `get_user_permissions(...)` 13 → 7 queries.
- Removed route-level N+1s on `/v1/users/{id}/permissions` (batched role permission loading) and `/v1/entities/{id}/members` (`get_entity_members_with_users(...)`).
- API-key permission projection + batched response shaping for the non-ABAC case; personal `authorize_api_key(...)` drops from ~22 queries unanchored / ~27 anchored into that faster path, and the self-service and admin inventory routes benefit in turn.
- Lazy access-scope member projection: `resolve_for_auth_result(..., include_member_user_ids=False)` skips the extra member-user lookup when callers only need entity/root scope; descendant expansion is reused rather than re-expanded.
- Checked-in query-budget regression coverage for `/v1/users/me`, `/v1/roles/entity/{entity_id}`, enterprise permission hot paths, `/v1/users/{id}/permissions`, `/v1/entities/{id}/members`, non-superuser `/v1/roles/`, and the personal / system API-key authorization and inventory surfaces.

[0.1.0a18]: https://github.com/outlabsio/outlabsAuth/compare/v0.1.0a17...v0.1.0a18
[0.1.0a17]: https://github.com/outlabsio/outlabsAuth/compare/v0.1.0a16...v0.1.0a17
