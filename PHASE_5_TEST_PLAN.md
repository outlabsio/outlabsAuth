# Phase 5: EnterpriseRBAC Testing - Comprehensive Test Plan

**Date**: 2025-11-10
**Status**: In Progress
**Goal**: Achieve >90% test coverage for all Phase 3-4 features

---

## Overview

Phase 5 focuses on comprehensive testing of EnterpriseRBAC features implemented in Phases 3-4:
- **Phase 3**: Entity hierarchy, closure table, tree permissions, entity-scoped API keys
- **Phase 4**: Context-aware roles, ABAC conditions, Redis caching

---

## Current Test Coverage Analysis

### ✅ ALREADY TESTED (Completed)

#### 1. Context-Aware Roles ✅
**File**: `tests/integration/test_context_aware_roles.py`
**Coverage**: 10 comprehensive tests
- ✅ Basic context-aware role functionality
- ✅ Permissions vary by entity type
- ✅ get_permissions_for_entity_type() method
- ✅ Context-aware roles with tree permissions
- ✅ get_user_permissions_in_entity() with context
- ✅ Fallback to default permissions
- ✅ Context-aware roles with wildcard permissions
- ✅ Multiple roles with context awareness

**Status**: COMPLETE - No additional tests needed

#### 2. ABAC Conditions ✅
**File**: `tests/integration/test_abac_conditions.py`
**Coverage**: 17 comprehensive tests

**PolicyEvaluationEngine Unit Tests** (8 tests):
- ✅ EQUALS operator
- ✅ LESS_THAN operator
- ✅ IN operator
- ✅ CONTAINS operator
- ✅ STARTS_WITH operator
- ✅ EXISTS operator
- ✅ IS_TRUE operator
- ✅ Condition groups with AND/OR logic

**ABAC Integration Tests** (9 tests):
- ✅ Department matching condition
- ✅ Budget limit condition
- ✅ Condition denial
- ✅ Multiple conditions (AND logic)
- ✅ Condition groups (OR logic)
- ✅ Custom context (IP range, time)
- ✅ Roles without conditions work normally
- ✅ Build context from models

**Missing Operators** (12 operators not tested):
- NOT_EQUALS
- GREATER_THAN
- LESS_THAN_OR_EQUAL
- GREATER_THAN_OR_EQUAL
- NOT_IN
- NOT_CONTAINS
- ENDS_WITH
- MATCHES (regex)
- IS_FALSE
- IS_NULL
- IS_NOT_NULL
- BEFORE, AFTER, BETWEEN (time operators)

**Status**: MOSTLY COMPLETE - Could add tests for remaining operators (nice-to-have)

#### 3. Tree Permissions ✅
**File**: `examples/enterprise_rbac/test_tree_permissions.py`
**Coverage**: 21/21 tests passing
- ✅ Entity hierarchy navigation
- ✅ Tree permission resolution
- ✅ Ancestor/descendant queries
- ✅ Direct vs tree permissions
- ✅ Permission inheritance patterns

**Status**: COMPLETE - Comprehensive coverage

#### 4. Entity-Scoped API Keys ✅
**File**: `examples/enterprise_rbac/test_entity_scoped_api_keys.py`
**Coverage**: 25/25 tests passing
- ✅ API keys scoped to specific entities
- ✅ Tree permission inheritance for API keys
- ✅ Global vs scoped API keys
- ✅ Parent/child entity access patterns

**Status**: COMPLETE - Comprehensive coverage

---

## 🔴 MISSING TESTS (Need to Create)

### 1. Redis Caching Tests ❌ HIGH PRIORITY
**File to Create**: `tests/integration/test_redis_caching.py`

**Test Cases Needed** (15+ tests):

#### Cache Hit/Miss Behavior (5 tests)
- [ ] Test cache miss on first permission check (DB query)
- [ ] Test cache hit on second permission check (Redis lookup)
- [ ] Test cache TTL expiration (permission re-queried after 300s)
- [ ] Test cache key generation format (`auth:perm:{user}:{permission}:{entity}`)
- [ ] Test cache storage structure (`{has_permission: bool, source: str}`)

#### Cache Invalidation (5 tests)
- [ ] Test cache invalidation on role assignment
- [ ] Test cache invalidation on role revocation
- [ ] Test cache invalidation on role permission changes
- [ ] Test cache invalidation on entity membership changes
- [ ] Test Redis Pub/Sub cache invalidation across instances (DD-037)

#### Performance Tests (3 tests)
- [ ] Benchmark cache hit vs cache miss (expect 20-60x improvement)
- [ ] Test permission check latency: ~1-2ms (cached) vs ~50-200ms (uncached)
- [ ] Test cache impact on throughput (requests per second)

#### Edge Cases (2 tests)
- [ ] Test graceful degradation when Redis unavailable (fallback to DB)
- [ ] Test cache behavior with different TTL configurations

**Implementation Notes**:
- Requires Redis instance running (use local-redis container)
- Use `RedisClient` from `outlabs_auth/utils/redis.py`
- Test with `EnterpriseConfig(redis_enabled=True, redis_url="redis://localhost:6379")`
- Use `pytest-benchmark` for performance tests

---

### 2. Performance Benchmarks ❌ HIGH PRIORITY
**File to Create**: `tests/performance/test_permission_benchmarks.py`

**Test Cases Needed** (8+ tests):

#### Closure Table vs Recursive Queries (2 tests)
- [ ] Benchmark ancestor query with closure table (expect O(1), ~1-5ms)
- [ ] Benchmark ancestor query with recursive approach (expect O(depth × nodes), ~50-200ms)
- [ ] Compare 20x performance improvement (DD-036)

#### Redis Caching Impact (2 tests)
- [ ] Benchmark permission checks without caching (baseline)
- [ ] Benchmark permission checks with Redis caching (expect 20-60x faster)
- [ ] Measure cache hit rate (expect >95% for repeated checks)

#### Entity Hierarchy Performance (2 tests)
- [ ] Test deep hierarchy performance (10 levels deep)
- [ ] Test wide hierarchy performance (100 entities at same level)

#### ABAC Evaluation Performance (2 tests)
- [ ] Benchmark simple condition evaluation (~0.1-1ms)
- [ ] Benchmark complex condition group evaluation (10+ conditions)

**Implementation Notes**:
- Use `pytest-benchmark` plugin
- Create realistic test data (100+ entities, 50+ users, 20+ roles)
- Run tests multiple times for statistical significance
- Compare results against Phase 4 discovery metrics

---

### 3. EnterpriseRBAC Integration Tests ❌ MEDIUM PRIORITY
**File to Create**: `tests/integration/test_enterprise_rbac_complete.py`

**Test Cases Needed** (10+ tests):

#### Feature Flag Combinations (4 tests)
- [ ] Test EnterpriseRBAC with all features enabled
- [ ] Test EnterpriseRBAC with only entity hierarchy (no context-aware, no ABAC)
- [ ] Test EnterpriseRBAC with context-aware roles but no ABAC
- [ ] Test EnterpriseRBAC with ABAC but no context-aware roles

#### End-to-End Scenarios (6 tests)
- [ ] Test complete user onboarding flow (create user → assign to entity → assign roles)
- [ ] Test permission resolution across all layers (RBAC → ReBAC → ABAC)
- [ ] Test entity hierarchy with 5+ levels (platform → region → office → team → squad)
- [ ] Test user with memberships in multiple entities
- [ ] Test user with multiple roles with different permission levels
- [ ] Test combined context-aware roles + ABAC conditions

**Implementation Notes**:
- Use realistic business scenarios (e.g., real estate, healthcare)
- Test common enterprise patterns (matrix management, cross-functional teams)
- Verify all three authorization models work together

---

### 4. Additional Operator Tests ❌ NICE-TO-HAVE (Low Priority)
**File to Update**: `tests/integration/test_abac_conditions.py`

**Missing Operators** (12 tests):
- [ ] NOT_EQUALS operator
- [ ] GREATER_THAN operator
- [ ] LESS_THAN_OR_EQUAL operator
- [ ] GREATER_THAN_OR_EQUAL operator
- [ ] NOT_IN operator
- [ ] NOT_CONTAINS operator
- [ ] ENDS_WITH operator
- [ ] MATCHES (regex) operator
- [ ] IS_FALSE operator
- [ ] IS_NULL operator
- [ ] IS_NOT_NULL operator
- [ ] BEFORE, AFTER, BETWEEN (time operators) - 3 tests

**Status**: Nice-to-have but not critical (existing 8 operators cover most use cases)

---

## Test Execution Plan

### Phase 5A: Redis Caching Tests (Day 1-2) 🔴 HIGH PRIORITY
1. Create `tests/integration/test_redis_caching.py`
2. Implement 15 cache tests (hit/miss, invalidation, performance)
3. Run tests with Redis enabled
4. Document Redis setup requirements

**Success Criteria**:
- All 15 tests passing
- Cache hit/miss behavior verified
- Pub/Sub invalidation working
- 20-60x performance improvement confirmed

---

### Phase 5B: Performance Benchmarks (Day 2-3) 🔴 HIGH PRIORITY
1. Create `tests/performance/test_permission_benchmarks.py`
2. Install `pytest-benchmark` plugin
3. Create realistic test data (100+ entities, 50+ users)
4. Run benchmarks 10+ times for statistical significance
5. Compare results against expected metrics

**Success Criteria**:
- Closure table 20x faster than recursive queries
- Redis caching 20-60x faster than no cache
- Permission checks <5ms at 95th percentile
- Benchmarks documented with graphs

---

### Phase 5C: EnterpriseRBAC Integration Tests (Day 3-4) 🟡 MEDIUM PRIORITY
1. Create `tests/integration/test_enterprise_rbac_complete.py`
2. Implement 10 integration tests
3. Test all feature flag combinations
4. Test end-to-end enterprise scenarios
5. Verify RBAC → ReBAC → ABAC flow

**Success Criteria**:
- All 10 tests passing
- Feature flags work correctly
- Complex scenarios handled properly
- Documentation updated with examples

---

### Phase 5D: Additional Operator Tests (Day 4) 🟢 NICE-TO-HAVE
1. Update `tests/integration/test_abac_conditions.py`
2. Add tests for 12 remaining operators
3. Run full test suite

**Success Criteria**:
- All 29 ABAC tests passing (17 existing + 12 new)
- Complete operator coverage
- Documentation updated

---

### Phase 5E: Test Coverage & Documentation (Day 5)
1. Run full test suite (`uv run pytest`)
2. Generate coverage report (`pytest --cov=outlabs_auth --cov-report=html`)
3. Verify >90% coverage
4. Create `PHASE_5_TEST_RESULTS.md` summary
5. Update `IMPLEMENTATION_ROADMAP.md`

**Success Criteria**:
- Test coverage >90%
- All critical tests passing
- Performance benchmarks meet targets
- Documentation complete

---

## Test Infrastructure Requirements

### Docker Containers
```bash
# Required containers (should already be running)
docker ps | grep -E "outlabs-mongodb|outlabs-redis|local-redis"

# If not running:
docker start outlabs-mongodb outlabs-redis local-redis
```

### Python Dependencies
```bash
# Install test dependencies
uv sync --extra test

# Install benchmark plugin
uv pip install pytest-benchmark
```

### Database Setup
```python
# Test databases (auto-cleaned per test)
- outlabs_auth_test_context_aware (context-aware roles)
- outlabs_auth_test_abac (ABAC conditions)
- outlabs_auth_test_redis (Redis caching)
- outlabs_auth_test_enterprise (integration tests)
- outlabs_auth_test_performance (benchmarks)
```

---

## Expected Test Count

| Test Category | Existing | New | Total | Priority |
|--------------|----------|-----|-------|----------|
| Context-Aware Roles | 10 | 0 | 10 | ✅ Complete |
| ABAC Conditions | 17 | 12 | 29 | ✅ Mostly Complete |
| Tree Permissions | 21 | 0 | 21 | ✅ Complete |
| Entity-Scoped API Keys | 25 | 0 | 25 | ✅ Complete |
| **Redis Caching** | 0 | **15** | **15** | 🔴 High Priority |
| **Performance Benchmarks** | 0 | **8** | **8** | 🔴 High Priority |
| **EnterpriseRBAC Integration** | 0 | **10** | **10** | 🟡 Medium Priority |
| **Additional ABAC Operators** | 0 | 12 | 12 | 🟢 Nice-to-Have |
| **TOTAL** | **73** | **45** | **118** | |

**Critical Path**: Redis Caching (15) + Performance Benchmarks (8) = **23 tests**
**Total with Nice-to-Have**: **130 tests**

---

## Success Criteria for Phase 5

### Must-Have (Phase 5 Complete)
- [x] Context-aware roles tests passing (10/10) ✅
- [x] ABAC conditions tests passing (17/17) ✅
- [x] Tree permissions tests passing (21/21) ✅
- [x] Entity-scoped API keys tests passing (25/25) ✅
- [ ] Redis caching tests passing (0/15) 🔴
- [ ] Performance benchmarks complete (0/8) 🔴
- [ ] EnterpriseRBAC integration tests passing (0/10) 🟡
- [ ] Test coverage >90%
- [ ] All benchmarks meet targets

### Nice-to-Have (Phase 5 Extended)
- [ ] Additional ABAC operator tests (12/12)
- [ ] Test coverage >95%
- [ ] Load testing (100+ concurrent users)
- [ ] Multi-instance cache invalidation tests

---

## Timeline

**Estimated Duration**: 3-5 days (depends on priority level)

### Conservative (Must-Have Only)
- Day 1: Redis caching tests (15 tests)
- Day 2: Performance benchmarks (8 tests)
- Day 3: EnterpriseRBAC integration (10 tests)
- Day 4: Test coverage verification & documentation
- Day 5: Buffer for bug fixes

### Aggressive (All Tests)
- Day 1-2: Redis + Performance (23 tests)
- Day 3: Integration (10 tests)
- Day 4: Additional operators (12 tests)
- Day 5: Coverage + docs

---

## Next Steps

1. **Immediate**: Create Redis caching tests (`tests/integration/test_redis_caching.py`)
2. **Then**: Create performance benchmarks (`tests/performance/test_permission_benchmarks.py`)
3. **Then**: Create integration tests (`tests/integration/test_enterprise_rbac_complete.py`)
4. **Finally**: Run full suite, generate coverage, document results

---

## Notes

- All existing tests (73) are passing and well-designed
- Critical gap is Redis caching tests (performance claims need verification)
- Performance benchmarks will validate DD-036 (closure table) and DD-037 (Redis Pub/Sub)
- EnterpriseRBAC integration tests will ensure all features work together
- Additional operator tests are nice-to-have but not critical
