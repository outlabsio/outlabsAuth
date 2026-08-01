"""
Bulk write-path budgets (perf audit Phase 4).

Archiving an entity's memberships previously cost ~9 queries per membership
(two ~4-query history snapshots plus a user SELECT and a flush per row) —
about 9,000 statements in one transaction for a 1,000-member entity. The
batched path shares one closure-context query and one user fetch across the
batch and flushes history inserts together, so the per-membership cost is the
(batched) INSERT itself.
"""

import pytest
import pytest_asyncio

from outlabs_auth import EnterpriseRBAC
from outlabs_auth.models.sql.enums import MembershipStatus
from tests.integration.query_budget_support import (
    EnterpriseQueryBudgetContext,
    QueryCounter,
    attach_query_counter,
    seed_enterprise_query_budget_context,
)


@pytest_asyncio.fixture
async def auth_instance(test_engine) -> EnterpriseRBAC:
    auth = EnterpriseRBAC(
        engine=test_engine,
        secret_key="test-secret-key-do-not-use-in-production-12345678",
        access_token_expire_minutes=60,
        enable_token_cleanup=False,
    )
    await auth.initialize()
    yield auth
    await auth.shutdown()


@pytest_asyncio.fixture
async def query_counter(auth_instance: EnterpriseRBAC):
    counter, cleanup = attach_query_counter(auth_instance.engine)
    yield counter
    cleanup()


@pytest_asyncio.fixture
async def seeded(auth_instance: EnterpriseRBAC) -> EnterpriseQueryBudgetContext:
    return await seed_enterprise_query_budget_context(auth_instance)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bulk_membership_archive_stays_within_query_budget(
    auth_instance: EnterpriseRBAC,
    query_counter: QueryCounter,
    seeded: EnterpriseQueryBudgetContext,
) -> None:
    service = auth_instance.membership_service

    async with auth_instance.get_session() as session:
        query_counter.reset()
        query_counter.enabled = True
        revoked = await service.archive_memberships_for_entity(
            session,
            seeded.department_id,
            revoked_by_id=seeded.admin_user_id,
            reason="entity archived (budget test)",
        )
        query_counter.enabled = False
        await session.commit()

    member_count = len(revoked)
    assert member_count >= 5, "seed should give the department a real member batch"
    assert all(membership.status == MembershipStatus.REVOKED for membership in revoked)

    # Old shape: ~9 queries per membership. New shape: a handful of shared
    # set-based queries plus batched history/audit inserts. Allow 2/row of
    # slack for the (batched) insert statements before failing.
    budget = 12 + 2 * member_count
    assert query_counter.count <= budget, (
        f"bulk archive of {member_count} memberships used {query_counter.count} queries "
        f"(budget {budget}; pre-batching this was ~{9 * member_count})"
    )
    print(
        f"\n[bench] archive_memberships_for_entity: {member_count} memberships, "
        f"{query_counter.count} queries (was ~{9 * member_count} before batching), "
        f"db_ms={query_counter.db_ms:.1f}"
    )

    # History rows were written for every revoked membership.
    from sqlalchemy import func, select

    from outlabs_auth.models.sql.entity_membership_history import EntityMembershipHistory

    async with auth_instance.get_session() as session:
        archived_events = (
            await session.execute(
                select(func.count())
                .select_from(EntityMembershipHistory)
                .where(
                    EntityMembershipHistory.entity_id == seeded.department_id,
                    EntityMembershipHistory.event_type == "entity_archived",
                )
            )
        ).scalar()
    assert archived_events == member_count
