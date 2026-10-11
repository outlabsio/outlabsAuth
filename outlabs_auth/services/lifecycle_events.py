"""Same-transaction lifecycle observation for host-owned durable evidence.

Observers write through the supplied AsyncSession. They must not commit, open
another transaction or send mail/network side effects. Their failure poisons
the current transaction until rollback, including if a caller catches it.
Empty configuration performs no queries and changes no existing admission.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, SessionTransaction


@dataclass(frozen=True)
class LifecycleEvent:
    event_id: UUID
    kind: str
    occurred_at: datetime
    user_id: UUID | None = None
    entity_id: UUID | None = None
    customer_root_id: UUID | None = None
    membership_id: UUID | None = None
    actor_id: UUID | None = None
    first_name: str | None = None
    last_name: str | None = None
    previous_status: str | None = None
    status: str | None = None
    reason: str | None = None
    source: str = "auth"


LifecycleObserver = Callable[[AsyncSession, LifecycleEvent], Awaitable[None]]
_POISON = "outlabs_auth.lifecycle_observer_failures"
_REGISTERED = "outlabs_auth.lifecycle_observer_guard"
_OBSERVING = "outlabs_auth.lifecycle_observing"


def _before_commit(session: Session) -> None:
    if session.info.get(_OBSERVING):
        raise RuntimeError("Lifecycle observers must not commit the caller's transaction")
    if session.info.get(_POISON):
        raise RuntimeError("Lifecycle evidence failed; rollback is required before commit")


def _after_rollback(session: Session, previous: SessionTransaction) -> None:
    # A rolled-back savepoint discards only its own evidence/mutation. An error
    # in a root transaction cannot be cleared by rolling back a later savepoint.
    failed: set[SessionTransaction] = session.info.get(_POISON, set())
    owner = previous
    while owner.parent is not None and not owner.nested:
        owner = owner.parent
    for transaction in list(failed):
        cursor: SessionTransaction | None = transaction
        while cursor is not None:
            if cursor is owner:
                failed.discard(transaction)
                break
            cursor = cursor.parent


class LifecycleDispatcher:
    def __init__(self, observers: Sequence[LifecycleObserver] = ()) -> None:
        self.observers = tuple(observers)

    async def emit(self, session: AsyncSession, *, kind: str, occurred_at: datetime, **snapshot: Any) -> None:
        if not self.observers:
            return
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise ValueError("Lifecycle event time must be timezone-aware")
        transaction = session.sync_session.get_nested_transaction() or session.sync_session.get_transaction()
        if transaction is None:
            raise RuntimeError("Lifecycle evidence requires the caller's active transaction")
        sync = session.sync_session
        if not sync.info.get(_REGISTERED):
            event.listen(sync, "before_commit", _before_commit)
            event.listen(sync, "after_soft_rollback", _after_rollback)
            sync.info[_REGISTERED] = True
        try:
            evidence = LifecycleEvent(event_id=uuid4(), kind=kind, occurred_at=occurred_at, **snapshot)
            session.info[_OBSERVING] = True
            for observer in self.observers:
                await observer(session, evidence)
        except BaseException:
            session.info.setdefault(_POISON, set()).add(transaction)
            raise
        finally:
            session.info.pop(_OBSERVING, None)
