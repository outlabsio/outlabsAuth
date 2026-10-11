"""Deterministic SQL budgets plus recorded local latency, never production SLAs."""

import json
import statistics
import time
from uuid import uuid4

import pytest
from sqlalchemy import event, insert

from outlabs_auth.models.sql.closure import EntityClosure
from outlabs_auth.models.sql.entity import Entity
from tests.integration.test_administrative_grant_foundation import grant, world as foundation_world
from tests.integration.test_staff_credential_target_lists import context, world

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("depth", [1, 8, 32])
async def test_staff_target_statement_budget_is_independent_of_tree_depth(world, depth, record_property):
    w = world
    w.facade.grants.max_depth = 40
    # Create the complete real parent/closure shape using bulk inserts. Fixture
    # construction is excluded from the measured request, not its dependencies.
    parents = [w.a.id]
    entities, closure = [], []
    for level in range(1, depth):
        identity = uuid4()
        entities.append(
            dict(
                id=identity,
                name=str(identity),
                display_name="Deep target",
                slug=str(identity),
                entity_class="structural",
                entity_type="department",
                parent_id=parents[-1],
                depth=level,
            )
        )
        closure.extend(
            dict(ancestor_id=ancestor, descendant_id=identity, depth=distance)
            for distance, ancestor in enumerate(reversed([*parents, identity]))
        )
        parents.append(identity)
    if entities:
        await w.session.execute(insert(Entity), entities)
        await w.session.execute(insert(EntityClosure), closure)
    await grant(w, w.read, w.a, kind="subtree")
    await w.session.commit()
    ctx = await context(w)
    statements = []

    def observe(conn, cursor, statement, parameters, execution_context, executemany):
        statements.append(statement)

    engine = w.session.bind.sync_engine
    event.listen(engine, "before_cursor_execute", observe)
    samples = []
    try:
        for _ in range(20):
            statements.clear()
            start = time.perf_counter()
            assert (await w.facade.authorize(w.session, ctx, action="case:read", entity_id=parents[-1])).allowed
            samples.append((time.perf_counter() - start) * 1000)
            assert len(statements) <= 10, len(statements)
        read_count = len(statements)
        statements.clear()
        assert (
            await w.facade.authorize(w.session, ctx, action="case:read", entity_id=parents[-1], protected_write=True)
        ).allowed
        assert len(statements) <= 29, len(statements)
        receipt = {
            "depth": depth,
            "read_statements": read_count,
            "write_admission_statements": len(statements),
            "p50_ms": statistics.median(samples),
            "p95_ms": sorted(samples)[18],
            "samples": 20,
        }
        record_property("staff_target_budget", json.dumps(receipt))
    finally:
        event.remove(engine, "before_cursor_execute", observe)


async def test_staff_filtered_list_at_ten_thousand_customer_roots(world, record_property):
    w = world
    roots = [uuid4() for _ in range(10000)]
    await w.session.execute(
        insert(Entity),
        [
            dict(
                id=i,
                name=str(i),
                display_name="Synthetic customer",
                slug=str(i),
                entity_class="structural",
                entity_type="organization",
            )
            for i in roots
        ],
    )
    await w.session.execute(insert(EntityClosure), [dict(ancestor_id=i, descendant_id=i, depth=0) for i in roots])
    await grant(w, w.read, w.a)
    await w.session.commit()
    ctx = await context(w)
    statements = []

    def observe(conn, cursor, statement, parameters, execution_context, executemany):
        statements.append(statement)

    engine = w.session.bind.sync_engine
    event.listen(engine, "before_cursor_execute", observe)
    samples = []
    try:
        for _ in range(20):
            statements.clear()
            start = time.perf_counter()
            page = await w.facade.entity_page(w.session, ctx, action="case:read", limit=10)
            samples.append((time.perf_counter() - start) * 1000)
            assert page.total == 1 and [row.id for row in page.items] == [w.a.id]
            assert len(statements) <= 5, len(statements)
        record_property(
            "staff_list_baseline",
            json.dumps(
                {
                    "extra_roots": 10000,
                    "returned": 1,
                    "statements": len(statements),
                    "p50_ms": statistics.median(samples),
                    "p95_ms": sorted(samples)[18],
                    "samples": 20,
                }
            ),
        )
    finally:
        event.remove(engine, "before_cursor_execute", observe)
