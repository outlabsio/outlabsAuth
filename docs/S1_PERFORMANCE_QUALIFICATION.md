# S1 local performance qualification

**Date:** 2026-10-11. **Candidate runtime:** `eaa5ff3`, compared with archived
`a6305fe`. Both include the eight S1 corrections; this comparison isolates the
migration/recovery slice. No deployed consumer or production latency SLO is qualified.

## Post-review warm-path requalification

Runtime `90de105` was requalified on 2026-10-11 with 100 requests after 20
warmups, real Redis, both presets, and concurrency 1 and 10. Each sample now
resets request memoization on entry/exit, as the host middleware does. The first
repetition incorrectly reused synthetic request memos and suppressed anchored-key
cache publication (15 SQL/request); that run is rejected. Correcting the harness
restores all ten paths to zero SQL and zero failures without a runtime change.
Every successful warmup is required; failed warmups cannot be ignored.

| Scenario | Serial p95 | Concurrency 10 p95 |
| --- | ---: | ---: |
| `simple_service_token_permission` | 0.04ms | 0.06ms |
| `simple_user_api_key_global` | 2.90ms | 6.52ms |
| `simple_user_api_key_dependency_global` | 2.55ms | 2.79ms |
| `simple_seeded_service_token_permission` | 0.05ms | 0.05ms |
| `enterprise_service_token_permission` | 0.10ms | 0.05ms |
| `enterprise_personal_api_key_unanchored` | 1.30ms | 6.39ms |
| `enterprise_personal_api_key_dependency_unanchored` | 1.37ms | 2.74ms |
| `enterprise_personal_api_key_anchored_tree` | 3.12ms | 4.13ms |
| `enterprise_system_api_key_global` | 2.35ms | 3.02ms |
| `enterprise_system_api_key_entity_tree` | 4.34ms | 3.82ms |

All paths meet the existing 10ms local review ceiling. These are loopback fixture
observations under concurrent suite work, not a production latency/capacity SLO.
The earlier comparison tables below remain historical runtime `eaa5ff3` evidence.

## Numeric regression gates

The permanent SQL gates in `test_s1_coldpath_budgets.py` use real PostgreSQL and
Redis, fresh request scopes/sessions and a detached ordinary user. They exercise
one active role plus zero or 250 future ACTIVE scheduled roles carrying the same
permission. The conditioned case stores a real `time.hour < 24` role condition.
Cold iterations advance the shared version to prevent a cached verdict or condition
flag from hiding the load; warmed conditioned iterations must still evaluate policy.

| Path | SQL maximum per operation | Local p95 review ceiling |
| --- | ---: | ---: |
| Ordinary RBAC cold, no future bindings | 3 | 20ms |
| Conditioned cold, no future bindings | 8 | 20ms |
| Ordinary RBAC warmed, either cardinality | 0 | 2ms |
| Conditioned warmed, no future bindings | 6 | 10ms |
| Cold or conditioned warmed, 250 future bindings | 3 / 8 / 6 respectively | 75ms |

SQL caps are automated regression assertions. Latency ceilings are local review
thresholds for this fixture/host, with headroom for allocation/GC and loopback I/O;
they are not timing assertions in pytest or maintainer-approved production budgets.
An overrun requires investigation and a recorded disposition. Future S2 staff-grant
budgets remain a separate design gate; no staff evaluator runtime is benchmarked here.

## Measured cold and warmed paths

100 serial samples per path after two warmups; timings include session creation,
request reset, condition work and the cold Redis version bump. Candidate and
baseline run sequentially against separate schemas in the same owned Postgres 16
and Redis 7 fixture. The source full suite was also running against a different
database/Redis DB on the same host; treat wall-time differences as local noisy
observations, not statistically established performance improvements/regressions.
Both runs use the repository's Python 3.12.8 environment and locked dependencies.

| Conditions / future bindings | Cold SQL | Candidate cold p50 / p95 | Baseline cold p95 | Warm SQL | Candidate warm p50 / p95 | Baseline warm p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| No / 0 | 3 | 2.94 / 4.51ms | 4.87ms | 0 | 0.21 / 0.27ms | 0.76ms |
| No / 250 | 3 | 12.12 / 44.96ms | 41.99ms | 0 | 0.31 / 0.45ms | 0.35ms |
| Yes / 0 | 8 | 5.27 / 7.97ms | 5.53ms | 6 | 4.32 / 5.69ms | 5.19ms |
| Yes / 250 | 8 | 12.76 / 45.99ms | 45.67ms | 6 | 11.90 / 46.26ms | 42.45ms |

Every path meets the local ceiling and has the same SQL count as the comparison
baseline. The high-cardinality cost is graph-row materialization and policy/lease
work, not additional round trips. Retaining scheduled bindings is required for
correct activation deadlines; filtering them out to improve this number would
reintroduce stale-denial bugs. Conditioned final decisions remain conservatively
uncached. These fixtures prove a bounded statement count and measured 250-role cost,
not bounded rows or latency for arbitrarily large customer graphs.

The existing warmed aggregate/allow/deny checks also pass at zero SQL. In the
20-sample candidate run their p95 values were 0.28/0.60/0.59ms. Existing uncached
Simple/Enterprise permission, HTTP and API-key query caps remain authoritative;
the full suite checks them without widening their assertions.

## Warm API-key and service-token paths

`scripts/benchmark_auth_paths.py` now supplies its required unique Redis namespace
and raises only its disposable schema's synthetic key limits to 1,000,000/minute.
The limiter and usage work remain enabled; a legitimate 60/minute rejection is not
counted as a latency sample for successful authorization. No consumer config or
rate limit changes. Both source revisions use this identical harness correction.

100 serial requests after five warmups, cache mode, no usage commit, default zero
local snapshot TTL. All ten scenarios have **zero SQL**, available real Redis and
zero failures. The local p95 ceiling is **10ms**; all candidate samples meet it.

| Scenario | Candidate p50 / p95 | Baseline p95 |
| --- | ---: | ---: |
| Simple service token | 0.04 / 0.05ms | 0.07ms |
| Simple personal key | 0.69 / 0.91ms | 2.45ms |
| Simple key dependency | 0.81 / 1.21ms | 1.42ms |
| Simple seeded service token | 0.04 / 0.07ms | 0.05ms |
| Enterprise service token | 0.04 / 0.05ms | 0.05ms |
| Enterprise unanchored personal key | 0.94 / 1.42ms | 0.91ms |
| Enterprise unanchored key dependency | 0.86 / 1.36ms | 1.06ms |
| Enterprise anchored personal tree key | 1.73 / 5.09ms | 2.18ms |
| Enterprise system global key | 0.98 / 2.60ms | 1.46ms |
| Enterprise system tree key | 1.41 / 2.55ms | 2.34ms |

The same 100-request run with **10 concurrent operations** also has zero SQL,
zero failures and available Redis across all ten scenarios. Candidate p95 values,
in the table's order, are **0.04, 6.56, 5.61, 0.04, 0.06, 6.43, 3.62, 5.42,
3.09 and 4.68ms**; all meet the same 10ms local review ceiling. This is a small
concurrency rehearsal, not a saturation/load-capacity measurement.

The fixture does not establish remote-database p95, committed usage latency or
production hardware capacity. In particular, anchored-key tail
latency differs noticeably between these noisy local runs even with identical zero
SQL budgets; keep this observation in the review rather than claiming a speedup.
The benchmark drops its own schema on exit. Its unique Redis namespace remains
only in the owned disposable Redis instance and is removed with that fixture.

## Reproduction

Set `TEST_DATABASE_URL` and `TEST_REDIS_URL` to owned disposable loopback fixtures:

```bash
AUTH_BUDGET_ITERATIONS=100 TEST_REDIS_REQUIRED=1 uv run --no-sync pytest \
  tests/integration/test_s1_coldpath_budgets.py \
  tests/integration/test_cached_hotpath_budgets.py -q -s
```

Use the same test and environment on an archived comparison commit. Never run
these Redis fixtures against a shared consumer DB: the fixture flushes its selected
Redis database. Keep latency measurements separate from consumer credentials/data.

See [S1 receipt](TENANT_AUTH_SECURITY_PATCH.md) for full-suite and installed-artifact
evidence and [recovery](AUTH_RECOVERY.md) for cache/rollback limitations.
