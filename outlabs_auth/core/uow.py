"""
Shared per-request unit-of-work state.

``OutlabsAuth.uow`` registers the request's session in the ASGI scope under
``UOW_SCOPE_KEY`` so ``UnitOfWorkMiddleware`` can commit or roll back BEFORE
the response starts. FastAPI (>=0.106) runs dependency teardown only after
the response has been sent, so a commit there races the client's next
request — see ``outlabs_auth.middleware.uow`` for the full story.

Kept free of project imports so the core class and the middleware can both
use it without dragging in the service layer.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

#: HTTP methods whose unit of work commits on success; all others roll back.
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: ASGI-scope key holding the request's list of ``UnitOfWorkState`` records
#: (a list so multiple OutlabsAuth instances on one app cannot clobber each
#: other's sessions).
UOW_SCOPE_KEY = "outlabs_auth.uow_states"


class UnitOfWorkState:
    """One request-scoped session and serialized finalization state.

    FastAPI may begin dependency teardown while the response-start middleware
    is still awaiting a commit. The lock keeps the session context from
    closing until that commit/rollback completes, while ``finalized`` ensures
    the second caller becomes a no-op.
    """

    __slots__ = ("session", "finalized", "_finalize_lock")

    def __init__(self, session: "AsyncSession") -> None:
        self.session = session
        self.finalized = False
        self._finalize_lock = asyncio.Lock()

    async def finalize(self, *, commit: bool) -> None:
        """Commit or roll back exactly once, waiting for an active finalizer."""
        async with self._finalize_lock:
            if self.finalized:
                return
            try:
                if commit:
                    await self.session.commit()
                else:
                    await self.session.rollback()
            finally:
                # A failed commit is still terminal for this request. The
                # owning caller propagates the error and session close handles
                # transaction cleanup; a second finalizer must not race it.
                self.finalized = True
