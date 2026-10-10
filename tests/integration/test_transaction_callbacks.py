"""Transaction ownership and failure cases for awaited cache publications."""

import asyncio
from functools import partial
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from outlabs_auth.core.transaction_callbacks import defer_after_commit, has_pending_cache_changes, mark_authority_change
from outlabs_auth.services import request_cache
from outlabs_auth.models.sql.user import User


async def append_async(items, value):
    await asyncio.sleep(0)
    items.append(value)


@pytest.mark.asyncio
@pytest.mark.parametrize("nested_commit", [True, False])
async def test_savepoint_publications_belong_to_outer_commit(test_session, nested_commit):
    seen = []
    await test_session.execute(text("SELECT 1"))
    await defer_after_commit(test_session, partial(append_async, seen, "outer"))
    nested = await test_session.begin_nested()
    await defer_after_commit(test_session, partial(append_async, seen, "inner"))
    await (nested.commit() if nested_commit else nested.rollback())
    assert seen == []
    assert has_pending_cache_changes(test_session)
    await test_session.commit()
    assert seen == (["outer", "inner"] if nested_commit else ["outer"])
    assert not has_pending_cache_changes(test_session)


@pytest.mark.asyncio
async def test_failed_savepoint_preserves_outer_publication(test_session):
    seen = []
    email = f"savepoint-{uuid4().hex}@example.test"
    test_session.add(User(email=email))
    await test_session.flush()
    await defer_after_commit(test_session, partial(append_async, seen, "outer"))
    nested = await test_session.begin_nested()
    await defer_after_commit(test_session, partial(append_async, seen, "inner"))
    test_session.add(User(email=email))
    with pytest.raises(IntegrityError):
        await test_session.flush()
    await nested.rollback()
    await test_session.commit()
    assert seen == ["outer"]


@pytest.mark.asyncio
@pytest.mark.parametrize("end", ["rollback", "close", "failed_commit"])
async def test_uncommitted_transaction_never_publishes(test_session, end):
    seen = []
    await test_session.execute(text("SELECT 1"))
    await defer_after_commit(test_session, partial(append_async, seen, "pending"))
    if end == "failed_commit":
        email = f"duplicate-{uuid4().hex}@example.test"
        test_session.add_all([User(email=email), User(email=email)])
        with pytest.raises(IntegrityError):
            await test_session.commit()
        await test_session.rollback()
    else:
        await getattr(test_session, end)()
    assert seen == []
    assert not has_pending_cache_changes(test_session)


@pytest.mark.asyncio
async def test_context_commit_awaits_publication_and_committed_visibility(test_engine, test_session):
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    email = f"committed-{uuid4().hex}@example.test"
    seen = []

    async def publish():
        await asyncio.sleep(0)
        async with factory() as observer:
            assert (await observer.execute(select(User).where(User.email == email))).scalar_one()
        seen.append("committed")

    async with test_session.begin():
        test_session.add(User(email=email))
        await test_session.flush()
        await defer_after_commit(test_session, publish)
        assert seen == []
    assert seen == ["committed"]


@pytest.mark.asyncio
async def test_publication_failure_is_post_commit_and_other_actions_are_attempted(test_engine, test_session):
    factory = async_sessionmaker(test_engine, expire_on_commit=False)
    email = f"publication-{uuid4().hex}@example.test"
    seen = []

    async def fail():
        raise RuntimeError("cache unavailable")

    test_session.add(User(email=email))
    await test_session.flush()
    await defer_after_commit(test_session, fail)
    await defer_after_commit(test_session, partial(append_async, seen, "attempted"))
    with pytest.raises(RuntimeError, match="cache unavailable"):
        await test_session.commit()
    assert seen == ["attempted"]
    async with factory() as observer:
        assert (await observer.execute(select(User).where(User.email == email))).scalar_one()
    # after_commit exceptions leave a committed transaction awaiting close;
    # closing must discard queued state without rerunning actions.
    await test_session.close()
    assert not has_pending_cache_changes(test_session)


@pytest.mark.asyncio
async def test_explicit_purge_without_transaction_runs_immediately(test_session):
    seen = []
    await defer_after_commit(None, partial(append_async, seen, "no session"))
    await defer_after_commit(test_session, partial(append_async, seen, "no transaction"))
    assert seen == ["no session", "no transaction"]


@pytest.mark.asyncio
@pytest.mark.parametrize("commit", [True, False])
async def test_authority_memos_are_reset_at_transaction_end_without_a_backend(test_session, commit):
    await test_session.execute(text("SELECT 1"))
    request_cache.set_value("before mutation", True)
    mark_authority_change(test_session)
    assert not request_cache.contains("before mutation")
    request_cache.set_value("uncommitted authority", True)
    assert has_pending_cache_changes(test_session)
    await (test_session.commit() if commit else test_session.rollback())
    assert not request_cache.contains("uncommitted authority")
    assert not has_pending_cache_changes(test_session)


@pytest.mark.asyncio
async def test_savepoint_change_without_backend_remains_private_until_root_end(test_session):
    await test_session.execute(text("SELECT 1"))
    async with test_session.begin_nested():
        mark_authority_change(test_session)
    assert has_pending_cache_changes(test_session)
    request_cache.set_value("own changes", True)
    await test_session.rollback()
    assert not request_cache.contains("own changes")
    assert not has_pending_cache_changes(test_session)
