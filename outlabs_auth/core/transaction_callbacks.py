"""Await cache publications after the actual owning SQLAlchemy transaction.

SQLAlchemy AsyncSession runs synchronous transaction events inside its async
greenlet bridge. ``await_only`` returns control to that bridge and waits for our
async cache I/O before commit returns. No background task or custom session
subclass is needed, including for sessions supplied by an embedding host.
"""

from collections.abc import Awaitable, Callable
from typing import Any, Optional

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, SessionTransaction
from sqlalchemy.util.concurrency import await_only

AfterCommitAction = Callable[[], Awaitable[Any]]
_ACTIONS = "outlabs_auth.after_commit_actions"
_REGISTERED = "outlabs_auth.after_commit_registered"


def _reset_request_memos() -> None:
    # Import at event time to avoid the service package's eager imports while
    # this core module is being initialized.
    from outlabs_auth.services import request_cache

    request_cache.reset()


def mark_authority_change(session: Optional[AsyncSession]) -> None:
    """Drop local memos now and at transaction end, even without a cache backend."""
    _reset_request_memos()
    if session is not None:
        transaction = session.sync_session.get_nested_transaction() or session.sync_session.get_transaction()
        if transaction is not None:
            _register(session.sync_session)
            session.info.setdefault(_ACTIONS, {}).setdefault(transaction, [])


def _register(session: Session) -> None:
    if not session.info.get(_REGISTERED):
        event.listen(session, "after_commit", _after_commit)
        event.listen(session, "after_soft_rollback", _after_rollback)
        event.listen(session, "after_transaction_end", _after_end)
        session.info[_REGISTERED] = True


def has_pending_cache_changes(session: Optional[AsyncSession]) -> bool:
    """Uncommitted authority must neither consume nor populate shared caches."""
    if session is None:
        return False
    return bool(session.info.get(_ACTIONS))


async def defer_after_commit(session: Optional[AsyncSession], action: AfterCommitAction) -> None:
    """Queue on the current transaction; explicit cache purges without one run now.

    A released savepoint transfers its actions to its parent. A rolled-back
    savepoint discards only its actions. Root rollback, failed flush/commit and
    session close discard the corresponding actions without publication.
    """
    if session is None:
        await action()
        return
    sync = session.sync_session
    transaction = sync.get_nested_transaction() or sync.get_transaction()
    if transaction is None:
        await action()
        return
    _register(sync)
    pending = sync.info.setdefault(_ACTIONS, {})
    pending.setdefault(transaction, []).append(action)


async def _publish(actions: list[AfterCommitAction]) -> None:
    # Try all invalidations even if one fails. The DB has already committed;
    # publication failure propagates rather than masquerading as a rollback.
    first_error: Optional[Exception] = None
    for action in actions:
        try:
            await action()
        except Exception as exc:
            if first_error is None:
                first_error = exc
    if first_error is not None:
        raise first_error


def _after_commit(session: Session) -> None:
    _reset_request_memos()
    pending = session.info.get(_ACTIONS, {})
    nested = session.get_nested_transaction()
    if nested is not None:
        if nested in pending:
            actions = pending.pop(nested)
            pending.setdefault(nested.parent, []).extend(actions)
        return
    actions = pending.pop(session.get_transaction(), [])
    if actions:
        await_only(_publish(actions))


def _after_rollback(session: Session, previous: SessionTransaction) -> None:
    _reset_request_memos()
    # Flush creates an internal, non-savepoint transaction. Its failure belongs
    # to the nearest real savepoint/root, not necessarily to the root session.
    owner = previous
    while owner.parent is not None and not owner.nested:
        owner = owner.parent
    pending = session.info.get(_ACTIONS, {})
    for transaction in list(pending):
        ancestor = transaction
        while ancestor is not None:
            if ancestor is owner:
                pending.pop(transaction, None)
                break
            ancestor = ancestor.parent


def _after_end(session: Session, transaction: SessionTransaction) -> None:
    pending = session.info.get(_ACTIONS, {})
    if transaction.parent is None:
        _reset_request_memos()
        pending.clear()
    else:
        pending.pop(transaction, None)
